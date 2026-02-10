# Upgrade Log: V2 Intelligence Layer

> Tracks what was added, changed, or upgraded from the Phase 3 baseline (Feb 6, 2026) through the current V2 build (Feb 10, 2026).

---

## Baseline (Phase 3 — `7e135bb`, Feb 6)

The system at Phase 3 completion had:

| Metric         | Value                                     |
| -------------- | ----------------------------------------- |
| MCP Tools      | 17                                        |
| Source Modules | 14                                        |
| Unit Tests     | 255                                       |
| Coverage       | 100%                                      |
| Test Files     | 15                                        |
| Scripts        | 12                                        |
| Tox Tiers      | 4 (pulse, gate, hammer, polish)           |
| Search         | Vector-only (Qdrant cosine similarity)    |
| Retrieval      | Hologram (BFS subgraph expansion)         |
| Maintenance    | Librarian (cluster + consolidate + prune) |

---

## Phase 10: Qdrant + Salience (`0580f04`, `2a9f763`)

**What changed:**

| Before                     | After                                                               |
| -------------------------- | ------------------------------------------------------------------- |
| Basic cosine search        | **MMR diversity search** (`mmr=True` flag)                          |
| Default HNSW threshold     | **Optimized HNSW** indexing (threshold: 5000)                       |
| No payload index on `name` | **Full-text payload index** on `name` field                         |
| No salience scoring        | **Salience scoring** — nodes gain weight on access, decay over time |
| 255 tests                  | 271 tests                                                           |

**New modules:** None
**New MCP tools:** None (salience is transparent to consumers)

---

## Phase 11: Temporal Graph Layer (`c52a69c` → `2ddf17c`)

**What changed:**

| Before                      | After                                                                |
| --------------------------- | -------------------------------------------------------------------- |
| No time awareness           | **`occurred_at` timestamp** on all entities                          |
| No temporal edges           | **`PRECEDED_BY`** and **`CONCURRENT_WITH`** edges                    |
| No timeline queries         | **`query_timeline(start, end)`** — chronological retrieval           |
| No temporal neighbors       | **`get_temporal_neighbors(id, direction)`** — before/after traversal |
| No time-travel search       | **`point_in_time_query(query, as_of)`** — historical search          |
| No message bottles          | **`get_bottles()`** — timestamped notes to future self               |
| Sessions are plain entities | **Sessions as temporal anchors** — automatic PRECEDED_BY linking     |
| 271 tests                   | 313 tests                                                            |

**New modules:** None (temporal logic embedded in `repository.py`, `tools.py`, `schema.py`)
**New MCP tools:** `query_timeline`, `get_temporal_neighbors`, `get_bottles` (+3)
**New scripts:** `scripts/backfill_temporal.py` (migration)

---

## Phase 12: Spreading Activation Retrieval (`a3eb081`, `6a6d09b`)

**What changed:**

| Before                   | After                                                                     |
| ------------------------ | ------------------------------------------------------------------------- |
| Vector-only search       | **Spreading activation** — energy propagation through graph edges         |
| No associative retrieval | **`search_associative()`** — combines vector + graph + salience + recency |
| Fixed scoring            | **Configurable score weights** (env vars + per-query overrides)           |
| 313 tests                | 340+ tests                                                                |

**New modules:** `activation.py` (ActivationEngine)
**New MCP tools:** `search_associative` (+1)

---

## Phase 13: Adaptive Query Routing (`4423b79`, `6649c42`)

**What changed:**

| Before                          | After                                                                              |
| ------------------------------- | ---------------------------------------------------------------------------------- |
| All queries go to vector search | **Automatic intent classification** → appropriate strategy                         |
| No query routing                | **`QueryRouter`** — classifies `SEMANTIC`, `ASSOCIATIVE`, `TEMPORAL`, `RELATIONAL` |
| No strategy override            | **`strategy` param** on `search_memory()` MCP tool                                 |
| Manual search selection         | **`search(strategy='auto')`** — router picks best path                             |

**New modules:** `router.py` (QueryRouter)
**New MCP tools:** None (wired into existing `search_memory`)

---

## Testing Directive Audit (`0b45a9b`, `a971589`)

**What changed:**

| Before                            | After                                                       |
| --------------------------------- | ----------------------------------------------------------- |
| 4 tox tiers                       | **5 tox tiers** — added `forge` (focused unit tests)        |
| Some implementation-coupled tests | **11 impl assertions removed** — tests verify behavior only |
| 3 overly-deep mock tests          | **Dropped and replaced** with pragmatic alternatives        |
| 1 pure-branch test                | **Deleted** — didn't catch real bugs                        |

---

## Phase 14: Embedding Evaluation (`8e58f24`, `0b1fcf9`)

**What changed:**

| Before                  | After                                                                          |
| ----------------------- | ------------------------------------------------------------------------------ |
| No embedding benchmarks | **`scripts/embedding_eval.py`** — 3-stage eval harness                         |
| Assumed BGE-M3 is best  | **Benchmarked**: BGE-M3 (r@10=0.926, 14.4ms) vs MiniLM (r@10=0.923, 0.8ms)     |
| No model decision       | **Decision: STAY with BGE-M3** — marginal recall advantage, acceptable latency |

**New scripts:** `scripts/embedding_eval.py`

---

## Phase 15: Structural Gap Analysis (`87a2906` → `0dfa554`)

**What changed:**

| Before                     | After                                                                          |
| -------------------------- | ------------------------------------------------------------------------------ |
| No graph health metrics    | **`graph_health()`** — nodes, edges, density, orphans, communities, avg degree |
| No gap detection           | **`detect_gaps()`** — finds disconnected but similar knowledge clusters        |
| No research prompts        | **Auto-generated research prompts** per detected gap                           |
| No knowledge gap MCP tool  | **`find_knowledge_gaps()`** MCP tool                                           |
| Librarian: cluster + prune | Librarian: cluster + prune + **gap detection + GapReport entities**            |

**New MCP tools:** `graph_health`, `find_knowledge_gaps` (+2)

---

## Hotfix: Logging to stderr (`1f36e09`)

**What changed:**

| Before                            | After                                                  |
| --------------------------------- | ------------------------------------------------------ |
| Logging handler used `sys.stdout` | **`sys.stderr`** — stdout is reserved for MCP JSON-RPC |

**Impact**: All MCP clients (Desktop, CLI, VS Code, Antigravity) failed with "Unexpected non-whitespace character after JSON" because log messages corrupted the stdio transport.

---

## Cumulative Summary

| Metric                | Phase 3 (Baseline) | Current (V2)                                       | Delta |
| --------------------- | ------------------ | -------------------------------------------------- | ----- |
| **MCP Tools**         | 17                 | 25                                                 | +8    |
| **Source Modules**    | 14                 | 18                                                 | +4    |
| **Unit Tests**        | 255                | 386                                                | +131  |
| **Test Files**        | 15                 | 35                                                 | +20   |
| **Scripts**           | 12                 | 30                                                 | +18   |
| **Tox Tiers**         | 4                  | 5                                                  | +1    |
| **Search Strategies** | 1 (vector)         | 4 (semantic, associative, temporal, relational)    | +3    |
| **Graph Features**    | Basic CRUD         | Temporal edges, salience, activation, gap analysis | —     |

### New Source Modules (V2)

- `activation.py` — Spreading activation engine
- `router.py` — Query intent classification
- `context_manager.py` — Session context management
- `ontology.py` — Runtime type system (existed but undocumented)

### New MCP Tools (V2)

1. `search_associative` — Graph-aware associative search
2. `query_timeline` — Chronological time-window queries
3. `get_temporal_neighbors` — Before/after temporal traversal
4. `get_bottles` — Message-in-a-bottle retrieval
5. `graph_health` — Graph health metrics
6. `find_knowledge_gaps` — Structural gap detection
7. `search_memory` (upgraded) — `strategy` and `mmr` params added
8. `create_entity` (upgraded) — Auto-links `PRECEDED_BY` edges
