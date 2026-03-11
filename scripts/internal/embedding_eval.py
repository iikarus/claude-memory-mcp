"""Embedding model evaluation harness for Phase 14.

Three-stage pipeline:
  1. Export — Pull entities from FalkorDB, generate synthetic query/relevance pairs
  2. Benchmark — Encode with each candidate model, measure precision@10 + latency
  3. Report — Output structured JSON + markdown summary

Usage:
    python scripts/embedding_eval.py                      # full pipeline
    python scripts/embedding_eval.py --export-only         # stage 1 only
    python scripts/embedding_eval.py --dataset eval_dataset.json  # skip export
    python scripts/embedding_eval.py --models bge-m3 minilm  # specific models

No production code is modified. This script is excluded from the test suite.
"""

from __future__ import annotations

import argparse
import gc
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ─── Configuration ────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent

# Candidate models: alias → HuggingFace model ID + vector dimension
MODEL_REGISTRY: dict[str, dict[str, Any]] = {
    "bge-m3": {
        "hf_id": "BAAI/bge-m3",
        "dim": 1024,
        "notes": "Current production model",
    },
    "gte-qwen2": {
        "hf_id": "Alibaba-NLP/gte-Qwen2-1.5B-instruct",
        "dim": 1536,
        "notes": "Strong multilingual, larger model",
    },
    "minilm": {
        "hf_id": "sentence-transformers/all-MiniLM-L6-v2",
        "dim": 384,
        "notes": "Fast/lightweight baseline",
    },
}

MAX_ENTITIES = 200
QUERIES_PER_ENTITY = 3  # name, partial name, description snippet
TOP_K = 10


# ─── Data Structures ─────────────────────────────────────────────────


@dataclass
class EvalEntity:
    """A single entity exported for evaluation."""

    id: str
    name: str
    description: str
    project_id: str


@dataclass
class EvalQuery:
    """A query with its known-relevant entity IDs."""

    text: str
    relevant_ids: list[str]
    source: str  # "name", "partial", "description"


@dataclass
class EvalDataset:
    """The full evaluation dataset."""

    entities: list[EvalEntity]
    queries: list[EvalQuery]
    exported_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-safe dict."""
        return {
            "exported_at": self.exported_at,
            "entity_count": len(self.entities),
            "query_count": len(self.queries),
            "entities": [asdict(e) for e in self.entities],
            "queries": [asdict(q) for q in self.queries],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvalDataset:
        """Deserialize from JSON dict."""
        return cls(
            entities=[EvalEntity(**e) for e in data["entities"]],
            queries=[EvalQuery(**q) for q in data["queries"]],
            exported_at=data.get("exported_at", ""),
        )


@dataclass
class ModelResult:
    """Benchmark results for a single model."""

    alias: str
    hf_id: str
    dim: int
    precision_at_k: float = 0.0
    recall_at_k: float = 0.0
    mean_encoding_latency_ms: float = 0.0
    peak_memory_mb: float = 0.0
    total_queries: int = 0
    notes: str = ""
    per_query: list[dict[str, Any]] = field(default_factory=list)


# ─── Stage 1: Dataset Export ──────────────────────────────────────────


def _get_graph() -> Any:
    """Connect to FalkorDB and return the graph handle."""
    from falkordb import FalkorDB

    host = os.getenv("FALKORDB_HOST", "localhost")
    port = int(os.getenv("FALKORDB_PORT", "6379"))
    password = os.getenv("FALKORDB_PASSWORD")
    client = FalkorDB(host=host, port=port, password=password)
    return client.select_graph("claude_memory")


def _export_entities(graph: Any, limit: int = MAX_ENTITIES) -> list[EvalEntity]:
    """Pull entities from FalkorDB for evaluation."""
    query = """
    MATCH (n:Entity)
    WHERE n.name IS NOT NULL AND n.name <> ''
    RETURN n.id AS id,
           n.name AS name,
           COALESCE(n.description, n.name) AS description,
           COALESCE(n.project_id, 'unknown') AS project_id
    ORDER BY COALESCE(n.salience_score, 0) DESC
    LIMIT $limit
    """
    result = graph.query(query, {"limit": limit})
    entities = []
    for row in result.result_set:
        entities.append(
            EvalEntity(
                id=str(row[0]),
                name=str(row[1]),
                description=str(row[2]),
                project_id=str(row[3]),
            )
        )
    logger.info("Exported %d entities from FalkorDB", len(entities))
    return entities


def _generate_queries(entities: list[EvalEntity]) -> list[EvalQuery]:
    """Generate synthetic queries from entity data.

    For each entity, creates up to 3 query variants:
    1. Full name (exact match test)
    2. Partial name (first 2 words for multi-word names)
    3. Description snippet (first 60 chars, semantic match test)
    """
    queries: list[EvalQuery] = []

    for entity in entities:
        # Query 1: Full name
        queries.append(
            EvalQuery(
                text=entity.name,
                relevant_ids=[entity.id],
                source="name",
            )
        )

        # Query 2: Partial name (only for multi-word names)
        words = entity.name.split()
        if len(words) >= 2:
            partial = " ".join(words[:2])
            queries.append(
                EvalQuery(
                    text=partial,
                    relevant_ids=[entity.id],
                    source="partial",
                )
            )

        # Query 3: Description snippet (only if different from name)
        desc = entity.description.strip()
        if desc and desc != entity.name and len(desc) > 10:
            snippet = desc[:60].rsplit(" ", 1)[0]  # Cut at word boundary
            queries.append(
                EvalQuery(
                    text=snippet,
                    relevant_ids=[entity.id],
                    source="description",
                )
            )

    logger.info("Generated %d queries from %d entities", len(queries), len(entities))
    return queries


def export_dataset(output_path: Path, max_entities: int = MAX_ENTITIES) -> EvalDataset:
    """Stage 1: Export entities and generate query/relevance pairs."""
    from datetime import UTC, datetime

    graph = _get_graph()
    entities = _export_entities(graph, limit=max_entities)

    if not entities:
        logger.error("No entities found in FalkorDB — cannot build eval dataset")
        sys.exit(1)

    queries = _generate_queries(entities)
    dataset = EvalDataset(
        entities=entities,
        queries=queries,
        exported_at=datetime.now(UTC).isoformat(),
    )

    with open(output_path, "w") as f:
        json.dump(dataset.to_dict(), f, indent=2)

    logger.info(
        "Dataset saved to %s (%d entities, %d queries)", output_path, len(entities), len(queries)
    )
    return dataset


# ─── Stage 2: Benchmark ──────────────────────────────────────────────


def _get_memory_mb() -> float:
    """Get current process RSS in MB."""
    try:
        import psutil

        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    except ImportError:
        return 0.0


def _cosine_similarity_matrix(query_vecs: np.ndarray, entity_vecs: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between all query-entity pairs.

    Args:
        query_vecs: (Q, D) array of query embeddings
        entity_vecs: (E, D) array of entity embeddings

    Returns:
        (Q, E) similarity matrix
    """
    # Normalize
    q_norm = query_vecs / (np.linalg.norm(query_vecs, axis=1, keepdims=True) + 1e-10)
    e_norm = entity_vecs / (np.linalg.norm(entity_vecs, axis=1, keepdims=True) + 1e-10)
    return q_norm @ e_norm.T


def benchmark_model(
    alias: str,
    model_info: dict[str, Any],
    dataset: EvalDataset,
    top_k: int = TOP_K,
) -> ModelResult:
    """Benchmark a single embedding model on the eval dataset."""
    from sentence_transformers import SentenceTransformer

    hf_id = model_info["hf_id"]
    logger.info("=" * 60)
    logger.info("Benchmarking: %s (%s)", alias, hf_id)
    logger.info("=" * 60)

    # Measure memory before load
    mem_before = _get_memory_mb()

    # Load model
    load_start = time.perf_counter()
    print(f"\n⏳ Loading model '{alias}' ({hf_id})... this may download on first run")
    model = SentenceTransformer(hf_id)
    load_time = time.perf_counter() - load_start
    print(f"✅ Model loaded in {load_time:.1f}s")
    logger.info("Model loaded in %.1fs", load_time)

    mem_after_load = _get_memory_mb()
    peak_memory = mem_after_load - mem_before

    # Encode entities
    entity_texts = [f"{e.name}: {e.description}" for e in dataset.entities]
    entity_ids = [e.id for e in dataset.entities]

    encode_start = time.perf_counter()
    entity_vecs = model.encode(entity_texts, show_progress_bar=True, batch_size=32)
    entity_encode_time = time.perf_counter() - encode_start
    logger.info("Encoded %d entities in %.1fs", len(entity_texts), entity_encode_time)

    # Encode queries
    query_texts = [q.text for q in dataset.queries]

    print(f"⏳ Encoding {len(query_texts)} queries...")
    query_start = time.perf_counter()
    query_vecs = model.encode(query_texts, show_progress_bar=True, batch_size=32)
    query_encode_time = time.perf_counter() - query_start
    print(f"✅ Queries encoded in {query_encode_time:.1f}s")

    mean_latency_ms = (query_encode_time / len(query_texts)) * 1000 if query_texts else 0

    # Compute similarities
    sim_matrix = _cosine_similarity_matrix(
        np.array(query_vecs),
        np.array(entity_vecs),
    )

    # Evaluate precision@K and recall@K
    precisions = []
    recalls = []
    per_query_results = []

    for i, query in enumerate(dataset.queries):
        # Get top-K indices by similarity
        top_indices = np.argsort(sim_matrix[i])[::-1][:top_k]
        top_ids = [entity_ids[idx] for idx in top_indices]

        # Count how many relevant IDs appear in top-K
        relevant_set = set(query.relevant_ids)
        hits = sum(1 for rid in top_ids if rid in relevant_set)

        precision = hits / top_k
        recall = hits / len(relevant_set) if relevant_set else 0.0

        precisions.append(precision)
        recalls.append(recall)

        per_query_results.append(
            {
                "query": query.text,
                "source": query.source,
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "top_3_ids": top_ids[:3],
                "expected_ids": query.relevant_ids,
                "hit": hits > 0,
            }
        )

    # Cleanup model to free memory
    del model
    gc.collect()

    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass

    result = ModelResult(
        alias=alias,
        hf_id=hf_id,
        dim=model_info["dim"],
        precision_at_k=float(np.mean(precisions)),
        recall_at_k=float(np.mean(recalls)),
        mean_encoding_latency_ms=mean_latency_ms,
        peak_memory_mb=peak_memory,
        total_queries=len(dataset.queries),
        notes=model_info.get("notes", ""),
        per_query=per_query_results,
    )

    logger.info(
        "  precision@%d = %.4f | recall@%d = %.4f | latency = %.1fms/q | mem = %.0fMB",
        top_k,
        result.precision_at_k,
        top_k,
        result.recall_at_k,
        result.mean_encoding_latency_ms,
        result.peak_memory_mb,
    )

    return result


# ─── Stage 3: Report ──────────────────────────────────────────────────


def generate_report(results: list[ModelResult], output_path: Path) -> None:
    """Save structured results to JSON and print markdown summary."""
    # JSON report
    report = {
        "results": [asdict(r) for r in results],
        "top_k": TOP_K,
    }
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info("Results saved to %s", output_path)

    # Markdown summary to stdout
    print("\n" + "=" * 70)
    print("EMBEDDING EVALUATION REPORT")
    print("=" * 70)
    print(f"\n{'Model':<20} {'Dim':>5} {'P@10':>8} {'R@10':>8} {'Latency':>10} {'Memory':>10}")
    print("-" * 70)

    for r in sorted(results, key=lambda x: x.precision_at_k, reverse=True):
        print(
            f"{r.alias:<20} {r.dim:>5} {r.precision_at_k:>8.4f} {r.recall_at_k:>8.4f}"
            f" {r.mean_encoding_latency_ms:>8.1f}ms {r.peak_memory_mb:>8.0f}MB"
        )

    print("-" * 70)

    # Per-source breakdown for the best model
    best = max(results, key=lambda x: x.precision_at_k)
    print(f"\nBest model: {best.alias} ({best.hf_id})")
    print(f"\nPer-source recall breakdown for {best.alias}:")

    source_recalls: dict[str, list[float]] = {}
    for pq in best.per_query:
        source_recalls.setdefault(pq["source"], []).append(pq["recall"])

    for source, recalls_list in sorted(source_recalls.items()):
        mean_r = np.mean(recalls_list)
        print(f"  {source:<15} recall@{TOP_K} = {mean_r:.4f} ({len(recalls_list)} queries)")

    # Decision guidance
    print("\n" + "=" * 70)
    print("DECISION GUIDANCE")
    print("=" * 70)

    current = next((r for r in results if r.alias == "bge-m3"), None)
    if current:
        better = [r for r in results if r.precision_at_k > current.precision_at_k * 1.05]
        if better:
            top_alt = max(better, key=lambda x: x.precision_at_k)
            delta = (
                (top_alt.precision_at_k - current.precision_at_k) / current.precision_at_k
            ) * 100
            print(f"\n⚠ {top_alt.alias} shows {delta:+.1f}% improvement over current bge-m3")
            print("  Consider switching if latency/memory tradeoffs are acceptable.")
        else:
            print("\n✅ bge-m3 remains competitive. No switch recommended.")
    else:
        print("\n⚠ bge-m3 baseline not included — cannot make comparison.")

    print()


# ─── CLI ──────────────────────────────────────────────────────────────


def main() -> None:
    """Entry point for the evaluation harness."""
    parser = argparse.ArgumentParser(description="Embedding model evaluation harness")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=SCRIPT_DIR / "eval_dataset.json",
        help="Path to eval dataset JSON (default: scripts/eval_dataset.json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=SCRIPT_DIR / "eval_results.json",
        help="Path for results JSON output",
    )
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="Only export dataset, skip benchmarking",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        choices=list(MODEL_REGISTRY.keys()),
        default=None,
        help="Model aliases to benchmark (default: all)",
    )
    parser.add_argument(
        "--max-entities",
        type=int,
        default=MAX_ENTITIES,
        help="Maximum entities to export (default: 200)",
    )

    args = parser.parse_args()

    # Stage 1: Export or load dataset
    if args.dataset.exists() and not args.export_only:
        logger.info("Loading existing dataset from %s", args.dataset)
        with open(args.dataset) as f:
            dataset = EvalDataset.from_dict(json.load(f))
        logger.info("Loaded %d entities, %d queries", len(dataset.entities), len(dataset.queries))
    else:
        logger.info("Exporting dataset from FalkorDB...")
        dataset = export_dataset(args.dataset, max_entities=args.max_entities)

    if args.export_only:
        logger.info("Export complete. Exiting (--export-only).")
        return

    # Stage 2: Benchmark
    model_aliases = args.models or list(MODEL_REGISTRY.keys())
    results: list[ModelResult] = []

    for i, alias in enumerate(model_aliases, 1):
        if alias not in MODEL_REGISTRY:
            logger.warning("Unknown model alias: %s — skipping", alias)
            continue
        print(f"\n{'=' * 60}")
        print(f"📊 Model {i}/{len(model_aliases)}: {alias}")
        print(f"{'=' * 60}")
        try:
            result = benchmark_model(alias, MODEL_REGISTRY[alias], dataset)
            results.append(result)
            print(f"✅ {alias} complete — p@10={result.precision_at_k:.4f}")
        except Exception:
            logger.exception("Failed to benchmark %s", alias)
            print(f"❌ {alias} FAILED")

    if not results:
        logger.error("No models benchmarked successfully")
        sys.exit(1)

    # Stage 3: Report
    generate_report(results, args.output)


if __name__ == "__main__":
    main()
