# Contributing

Thanks for your interest in contributing to Claude Memory MCP!

## Getting Started

1. **Fork** the repo and clone locally
2. **Install** dependencies: `pip install -e ".[dev]"`
3. **Start services**: `docker-compose up -d` (FalkorDB, Qdrant, Embedding API)
4. **Run tests**: `tox -e pulse`

## Development Workflow

This project follows strict TDD with the **Gold Stack** — a 4-tier quality suite:

| Tier | Command | What It Checks |
|------|---------|---------------|
| Pulse | `tox -e pulse` | Unit tests (904), type checking (mypy), linting (ruff) |
| Gate | `tox -e gate` | Pre-commit hooks, formatting, secrets scanning |
| Hammer | `tox -e hammer` | Security analysis (bandit, semgrep) |
| Polish | `tox -e polish` | Spell checking (codespell) |

### Testing Policy

Every function needs at minimum:
- **3 evil paths** (bad input, edge cases, failure modes)
- **1 sad path** (expected error handling)
- **1 happy path** (normal operation)

### Code Style

- **Type hints**: 100% mypy strict compliance required
- **Linting**: ruff with aggressive rules, zero violations
- **Formatting**: ruff format (consistent with black)
- **Mocking**: Use `patch.object` + `addCleanup`, never class-level `@patch`

## Submitting Changes

1. Create a feature branch from `master`
2. Write tests first (TDD)
3. Ensure `tox -e pulse` passes
4. Submit a pull request with a clear description

## Reporting Issues

Open an issue with:
- Steps to reproduce
- Expected vs actual behavior
- Python version + OS

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
