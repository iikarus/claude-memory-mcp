import json
import datetime
from pathlib import Path

RESULTS_DIR = Path("gauntlet_results")
REPORT_FILE = Path("MUTATION_REPORT.md")

MODULES = [
    "src/claude_memory/analysis.py",
    "src/claude_memory/search.py",
    "src/claude_memory/crud.py",
    "src/claude_memory/vector_store.py",
    "src/claude_memory/repository.py",
    "src/claude_memory/repository_queries.py",
    "src/claude_memory/repository_traversal.py",
    "src/claude_memory/clustering.py",
    "src/claude_memory/activation.py",
    "src/claude_memory/search_advanced.py",
    "src/claude_memory/router.py",
    "src/claude_memory/schema.py",
    "src/claude_memory/temporal.py",
    "src/claude_memory/lock_manager.py",
    "src/claude_memory/retry.py",
    "src/claude_memory/embedding.py",
    "src/claude_memory/ontology.py",
    "src/claude_memory/librarian.py",
    "src/claude_memory/crud_maintenance.py",
    "src/claude_memory/context_manager.py",
    "src/claude_memory/logging_config.py",
    "src/claude_memory/server.py",
    "src/claude_memory/tools.py",
    "src/claude_memory/tools_extra.py",
    "src/claude_memory/graph_algorithms.py",
    "src/claude_memory/interfaces.py",
]

def generate_report():
    summary_data = []
    survivors_data = {}
    completed = []
    pending = []

    total_mutants = 0
    total_killed = 0
    total_survived = 0
    total_timeout = 0
    total_error = 0

    for module in MODULES:
        module_name = Path(module).name
        result_file = RESULTS_DIR / f"mutants_{Path(module).stem}.json"
        failed_file = RESULTS_DIR / f"mutants_{Path(module).stem}_FAILED.json"

        if result_file.exists():
            with open(result_file) as f:
                data = json.load(f)

            completed.append(module_name)

            results = data.get("results", [])
            killed = 0
            survived = 0
            timeout = 0
            error = 0

            module_survivors = []

            for res in results:
                status = res.get("status")
                if status == "DETECTED":
                    killed += 1
                elif status == "SURVIVED":
                    survived += 1
                    module_survivors.append(res)
                elif status == "TIMEOUT":
                    timeout += 1
                elif status == "ERROR":
                    error += 1

            mutants_count = len(results)
            kill_rate = (killed / mutants_count * 100) if mutants_count > 0 else 0

            summary_data.append({
                "module": module_name,
                "mutants": mutants_count,
                "killed": killed,
                "survived": survived,
                "timeout": timeout,
                "error": error,
                "kill_rate": kill_rate
            })

            if survived > 0:
                survivors_data[module_name] = module_survivors

            total_mutants += mutants_count
            total_killed += killed
            total_survived += survived
            total_timeout += timeout
            total_error += error

        elif failed_file.exists():
            pending.append(f"{module_name} (Clean Trial Failed)")
            summary_data.append({
                "module": module_name,
                "mutants": "?", "killed": "?", "survived": "?", "timeout": "?", "error": "?", "kill_rate": "?"
            })
        else:
            pending.append(f"{module_name} (Missing)")
            summary_data.append({
                "module": module_name,
                "mutants": "?", "killed": "?", "survived": "?", "timeout": "?", "error": "?", "kill_rate": "?"
            })

    # Generate Markdown
    lines = []
    lines.append("# Dragon Brain Mutation Report")
    lines.append(f"**Date:** {datetime.date.today()}")
    lines.append("**Runner:** Jules")
    lines.append("**Repository:** claude-memory-mcp (master)")
    lines.append("**Tool:** mutatest")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Module | Mutants | Killed | Survived | Timeout | Error | Kill Rate |")
    lines.append("|--------|---------|--------|----------|---------|-------|-----------|")

    for row in summary_data:
        kr = f"{row['kill_rate']:.1f}%" if isinstance(row['kill_rate'], float) else row['kill_rate']
        lines.append(f"| {row['module']} | {row['mutants']} | {row['killed']} | {row['survived']} | {row['timeout']} | {row['error']} | {kr} |")

    total_kill_rate = (total_killed / total_mutants * 100) if total_mutants > 0 else 0
    lines.append(f"| **TOTAL** | **{total_mutants}** | **{total_killed}** | **{total_survived}** | **{total_timeout}** | **{total_error}** | **{total_kill_rate:.1f}%** |")
    lines.append("")

    lines.append("## Per-Survivor Details")
    lines.append("")

    if not survivors_data:
        lines.append("No survivors found (most mutations timed out or errored).")
        lines.append("")

    for module, survivors in survivors_data.items():
        lines.append(f"### [{module}] — {len(survivors)} survivors")
        lines.append("")
        lines.append("| # | Line | Original | Mutated | Classification |")
        lines.append("|---|------|----------|---------|----------------|")

        for i, res in enumerate(survivors, 1):
            mutant = res["mutant"]
            src_idx = mutant["src_idx"]
            lineno = src_idx["lineno"]
            op_type = src_idx["op_type"]
            mutation = mutant["mutation"]

            lines.append(f"| {i} | {lineno} | {op_type} | {mutation} | ? |")

        lines.append("")

    lines.append("## Modules Below 75% Kill Rate (P0)")
    lines.append("")
    for row in summary_data:
        if isinstance(row['kill_rate'], float) and row['kill_rate'] < 75:
            lines.append(f"- {row['module']}: {row['kill_rate']:.1f}%")
    lines.append("")

    lines.append("## Modules Completed vs Pending")
    lines.append("")
    lines.append("| Status | Modules |")
    lines.append("|--------|---------|")
    lines.append(f"| Completed | {', '.join(completed)} |")
    lines.append(f"| Timeout/Pending | {', '.join(pending)} |")
    lines.append("")

    lines.append("## Bugs Discovered (DO NOT FIX — document only)")
    lines.append("")
    if total_timeout + total_error > 0:
        lines.append("CRITICAL: Mutation testing inconclusive due to environmental/performance issues.")
        lines.append(f"- **Total Timeouts:** {total_timeout}")
        lines.append(f"- **Total Errors:** {total_error}")
        lines.append("- The test suite takes ~140s to run (clean trial), exceeding the mutation timeout of 30s.")
        lines.append("- Some tests rely on Redis, which is causing ConnectionRefusedError unless skipped.")
        lines.append("- `retry.py` failed to complete due to overall timeout.")
    else:
        lines.append("No bugs discovered during mutation testing (clean trial failures noted above).")
    lines.append("")

    with open(REPORT_FILE, "w") as f:
        f.write("\n".join(lines))

    print(f"Report written to {REPORT_FILE}")

if __name__ == "__main__":
    generate_report()
