# ADR-006: Gold Stack Quality Gate

**Status:** Accepted
**Date:** 2026-02-04
**Context:** The project needed a mandatory, non-negotiable quality gate to prevent regressions and enforce code standards across all commits.
**Decision:** Adopt the "Gold Stack" — a 16-tool TDD/CI suite organized into 4 tiers:

- **Pulse** (`pytest`, `ruff`, `ruff-format`): Fast feedback loop (~30s)
- **Gate** (`mypy`, `bandit`, `safety`, `codespell`): Security and type safety
- **Hammer** (`hypothesis`, `coverage`, `mutatest`): Deep testing
- **Polish** (`pre-commit`, `detect-secrets`, `tox`): Final gate

**Consequences:**

- All commits must pass pre-commit hooks (ruff, codespell, detect-secrets).
- `tox -e pulse` runs the fast feedback loop.
- Mutation testing (via `mutatest`) validates test quality, not just coverage.
