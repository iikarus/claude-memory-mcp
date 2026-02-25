import argparse
import json
import random
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, List, Dict

# Monkey-patch random.sample for Python 3.12 compatibility
_original_sample = random.sample

def _patched_sample(population, k, *, counts=None):
    if isinstance(population, (set, frozenset, dict)):
        population = sorted(population, key=str)
    if counts is not None:
        return _original_sample(population, k, counts=counts)
    return _original_sample(population, k)

random.sample = _patched_sample

import mutatest.run
import mutatest.transformers

MODULE_TEST_MAP = {
    # Batch 1
    "src/claude_memory/analysis.py": "tests/unit/test_analyze_graph.py",
    "src/claude_memory/search.py": "tests/unit/test_search_associative.py",
    "src/claude_memory/crud.py": "tests/unit/test_crud_split_brain.py",
    # Batch 2
    "src/claude_memory/vector_store.py": "tests/unit/test_vector_store.py",
    "src/claude_memory/repository.py": "tests/unit/test_repository.py",
    "src/claude_memory/repository_queries.py": "tests/unit/test_repository.py", # Fallback
    "src/claude_memory/repository_traversal.py": "tests/unit/test_graph_traversal.py",
    # Batch 3
    "src/claude_memory/clustering.py": "tests/unit/test_clustering.py",
    "src/claude_memory/activation.py": "tests/unit/test_activation.py",
    "src/claude_memory/search_advanced.py": "tests/unit/test_search_associative.py",
    "src/claude_memory/router.py": "tests/unit/test_router.py",
    # Batch 4
    "src/claude_memory/schema.py": "tests/unit/test_validation.py", # Fallback
    "src/claude_memory/temporal.py": "tests/unit/test_temporal.py",
    "src/claude_memory/lock_manager.py": "tests/unit/test_locking.py",
    "src/claude_memory/retry.py": "tests/unit/test_retry.py",
    # Batch 5
    "src/claude_memory/embedding.py": "tests/unit/test_embedding_client.py",
    "src/claude_memory/ontology.py": "tests/unit/test_ontology.py",
    "src/claude_memory/librarian.py": "tests/unit/test_librarian.py",
    "src/claude_memory/crud_maintenance.py": "tests/unit/test_crud_split_brain.py", # Fallback
    "src/claude_memory/context_manager.py": "tests/unit/test_context.py",
    "src/claude_memory/logging_config.py": "tests/unit/test_logging_config.py",
    # Batch 6
    "src/claude_memory/server.py": "tests/unit/test_server.py",
    "src/claude_memory/tools.py": "tests/unit/test_memory_service.py",
    "src/claude_memory/tools_extra.py": "tests/unit/test_memory_service.py", # Fallback
    "src/claude_memory/graph_algorithms.py": "tests/unit/test_graph_traversal.py",
    "src/claude_memory/interfaces.py": "tests/unit/test_interfaces.py",
}

OUTPUT_DIR = Path("gauntlet_results")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def restore_src():
    print("Restoring src/...", file=sys.stderr)
    subprocess.run(["git", "restore", "src/"], check=True)

def run_clean_trial(test_cmds: List[str]) -> float:
    print(f"Running clean trial: {test_cmds}", file=sys.stderr)
    start = time.time()
    try:
        # Reduced timeout as these should be fast
        subprocess.run(
            test_cmds,
            check=True,
            capture_output=True,
            timeout=60
        )
    except subprocess.TimeoutExpired:
        print("Clean trial timed out!", file=sys.stderr)
        return -1
    except subprocess.CalledProcessError as e:
        print(f"Clean trial failed! return code {e.returncode}", file=sys.stderr)
        print(e.stderr.decode(), file=sys.stderr)
        return -1
    return time.time() - start

def serialize_results(results_summary: mutatest.run.ResultsSummary) -> Dict[str, Any]:
    output = {
        "n_locs_mutated": results_summary.n_locs_mutated,
        "n_locs_identified": results_summary.n_locs_identified,
        "total_runtime": str(results_summary.total_runtime),
        "results": []
    }

    for trial_result in results_summary.results:
        mutant = trial_result.mutant
        output["results"].append({
            "status": trial_result.status,
            "return_code": trial_result.return_code,
            "mutant": {
                "src_file": str(mutant.src_file),
                "src_idx": {
                    "ast_class": mutant.src_idx.ast_class,
                    "lineno": mutant.src_idx.lineno,
                    "col_offset": mutant.src_idx.col_offset,
                    "op_type": str(mutant.src_idx.op_type),
                    "end_lineno": mutant.src_idx.end_lineno,
                    "end_col_offset": mutant.src_idx.end_col_offset
                },
                "mutation": str(mutant.mutation) if not isinstance(mutant.mutation, str) else mutant.mutation
            }
        })
    return output

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", help="Run specific module (substring match)")
    args = parser.parse_args()

    modules_to_run = list(MODULE_TEST_MAP.keys())
    if args.module:
        modules_to_run = [m for m in MODULE_TEST_MAP.keys() if args.module in m]
        if not modules_to_run:
            print(f"No modules matched '{args.module}'", file=sys.stderr)
            return

    for module_path in modules_to_run:
        print(f"\nProcessing {module_path}...", file=sys.stderr)

        restore_src()

        target_test_file = MODULE_TEST_MAP.get(module_path)
        if not target_test_file or not Path(target_test_file).exists():
             print(f"Target test file {target_test_file} for {module_path} not found! Skipping.", file=sys.stderr)
             continue

        # Construct specific test command for this module
        test_cmds = [
            "pytest",
            target_test_file,
            # Ignore problematic files even if target is specific, just in case of imports
            "--ignore=tests/unit/test_dynamic_validation.py",
            "--ignore=tests/unit/test_embedding_filter.py",
            "--ignore=tests/unit/test_retry.py",
            "--ignore=tests/unit/test_analyze_graph.py",
            "--ignore=tests/unit/test_memory_service.py"
        ]

        clean_time = run_clean_trial(test_cmds)
        if clean_time < 0:
            print(f"Skipping {module_path} due to clean trial failure/timeout.", file=sys.stderr)
            result_file = OUTPUT_DIR / f"mutants_{Path(module_path).stem}_FAILED.json"
            with open(result_file, "w") as f:
                json.dump({"error": "Clean trial failed"}, f)
            continue

        # Use 200s timeout as requested, though ideally it should be much faster now
        config = mutatest.run.Config(
            n_locations=2,
            max_runtime=200,
            break_on_survival=False,
            break_on_detected=False
        )

        src_loc = Path(module_path)
        if not src_loc.exists():
             print(f"Module {module_path} not found!", file=sys.stderr)
             continue

        try:
            print(f"Running mutations on {module_path}...", file=sys.stderr)
            results_summary = mutatest.run.run_mutation_trials(
                src_loc=src_loc,
                test_cmds=test_cmds,
                config=config
            )

            serialized = serialize_results(results_summary)
            result_file = OUTPUT_DIR / f"mutants_{src_loc.stem}.json"
            with open(result_file, "w") as f:
                json.dump(serialized, f, indent=2)
            print(f"Saved results to {result_file}", file=sys.stderr)

        except Exception as e:
            print(f"Error running mutatest on {module_path}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
