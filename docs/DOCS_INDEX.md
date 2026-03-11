# Documentation Index

> **Last updated**: March 11, 2026 — Post-gauntlet remediation, security hardening, docs audit

This is the master table of contents for all Claude Memory MCP documentation. Use this to find the right doc, and to know **when each doc needs updating**.

## Canonical Stats (Single Source of Truth)

| Metric                                | Value                        | As Of   |
| ------------------------------------- | ---------------------------- | ------- |
| Source modules (`src/claude_memory/`) | 29                           | Mar 11  |
| Scripts (`scripts/`)                  | 42                           | Mar 11  |
| Unit tests                            | 904 (904 passed + 0 skipped) | Mar 11  |
| Test files                            | 66                           | Mar 11  |
| Coverage                              | ~98%                         | Mar 2   |
| MCP tools                             | 30 (19 decorator + 11 runtime) | Mar 11 |
| FalkorDB nodes                        | ~1,492                       | Mar 11  |
| FalkorDB edges                        | ~2,951                       | Mar 9   |
| Qdrant vectors                        | 1,436                        | Mar 11  |
| Gold Stack tiers                      | 4 (pulse/gate/hammer/polish) | Mar 9   |
| Gauntlet score                        | A- (95/100)                  | Mar 11  |

> **Update rule**: When any of these numbers change, update this table first, then propagate to the docs that reference them (mainly README.md, ARCHITECTURE.md).

---

## Root-Level Files

| File                                                                                                         | Purpose                                     | Audience | Update When                                            |
| ------------------------------------------------------------------------------------------------------------ | ------------------------------------------- | -------- | ------------------------------------------------------ |
| [README.md](../README.md)       | Project overview, quick start, feature list | Everyone | New features, test count changes, architecture changes |
| [CHANGELOG.md](CHANGELOG.md) | Keep-a-Changelog format release notes | Everyone | Every release / significant commit batch |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | How to contribute, testing policy, code style | Contributors | Testing policy or workflow changes |
| [GAUNTLET_RESULTS.md](GAUNTLET_RESULTS.md) | 20-round quality audit results (A- 95/100) | Testing enthusiasts | After re-running the gauntlet |

## `docs/` — Core Documentation

| File                                                                                                                                    | Purpose                                            | Audience               | Update When                                       |
| --------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- | ---------------------- | ------------------------------------------------- |
| **This file** (`DOCS_INDEX.md`)                                                                                                         | Master TOC and update guide                        | All maintainers        | Any doc is added/removed/renamed                  |
| [ARCHITECTURE.md](ARCHITECTURE.md)                 | System design, data model, component diagram       | Developers, new agents | New components, data model changes, infra changes |
| [CODE_INVENTORY.md](CODE_INVENTORY.md)             | File-by-file manifest with descriptions            | Developers, auditors   | Any file added/removed/renamed                    |
| [USER_MANUAL.md](USER_MANUAL.md)                   | How to use the 30 MCP tools with Claude            | End users              | New tools added, tool signatures change           |
| [MCP_TOOL_REFERENCE.md](MCP_TOOL_REFERENCE.md)     | API reference: all 30 tools, params, return shapes | Developers, AI agents  | Tool added/removed, params change                 |
| [MAINTENANCE_MANUAL.md](MAINTENANCE_MANUAL.md)     | Backups, monitoring, troubleshooting               | Operators              | Infra changes, new backup procedures              |
| [RUNBOOK.md](RUNBOOK.md)                           | 10 incident response recipes                       | Operators              | New incident types, procedure changes             |
| [GOTCHAS.md](GOTCHAS.md)                           | Known traps, edge cases, subtleties                | Developers, agents     | New bugs discovered, workarounds found            |
| [UPGRADE_LOG.md](UPGRADE_LOG.md)                   | Phase-by-phase changelog of V2 build               | Auditors               | Historical, rarely updated                        |
| [DRAGON_BRAIN_GAUNTLET.md](DRAGON_BRAIN_GAUNTLET.md) | 20-round quality audit spec (testing methodology) | Testing enthusiasts    | Methodology changes, new rounds                   |

## `docs/adr/` — Architecture Decision Records

| File                                                                                                                                                          | Decision                         | Status   |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------- | -------- |
| [001-hybrid-storage.md](adr/001-hybrid-storage.md)                       | FalkorDB + Qdrant hybrid storage | Accepted |
| [002-service-repository.md](adr/002-service-repository.md)               | Service-Repository pattern       | Accepted |
| [003-python-graph-algos.md](adr/003-python-graph-algos.md)               | Python-side graph algorithms     | Accepted |
| [004-observation-vectorization.md](adr/004-observation-vectorization.md) | Observation embedding strategy   | Accepted |
| [005-associative-search.md](adr/005-associative-search.md)               | Spreading activation for search  | Accepted |
| [006-gold-stack.md](adr/006-gold-stack.md)                               | 5-tier Gold Stack CI/CD          | Accepted |



## Documentation Update Protocol (MANDATORY)

> **No doc update ships without a structural diff against the codebase.**

### Phase 1: Structural Diff (Trust Nothing)

Run these commands from the project root. If any produce output, the docs are **stale**.

```powershell
# 1. Source modules — compare actual files to CODE_INVENTORY.md
$inv = Get-Content docs/CODE_INVENTORY.md | Select-String "\w+\.py\s*\|" |
  ForEach-Object { if ($_.Line -match '`(\w+\.py)`') { $matches[1] } } |
  Sort-Object -Unique
$actual = Get-ChildItem src/claude_memory -Filter "*.py" |
  Select-Object -ExpandProperty Name | Sort-Object -Unique
Write-Host "PHANTOM (in docs, not on disk):"
$inv | Where-Object { $_ -notin $actual }
Write-Host "MISSING (on disk, not in docs):"
$actual | Where-Object { $_ -notin $inv }

# 2. Test files — cross-check inventory vs disk
$tinv = Get-Content docs/CODE_INVENTORY.md |
  Select-String "test_\w+\.py" |
  ForEach-Object { if ($_.Line -match '(test_[\w]+\.py)') { $matches[1] } } |
  Sort-Object -Unique
$tactual = Get-ChildItem tests -Recurse -Filter "test_*.py" |
  Select-Object -ExpandProperty Name | Sort-Object -Unique
Write-Host "PHANTOM TESTS:" ; $tinv | Where-Object { $_ -notin $tactual }
Write-Host "MISSING TESTS:" ; $tactual | Where-Object { $_ -notin $tinv }

# 3. Script files — cross-check inventory vs disk
# (same pattern as above, adapted for scripts/)

# 4. MCP tool count — decorator + runtime registrations
$decorators = (Select-String -Path src/claude_memory/server.py -Pattern "@mcp.tool").Count
$runtime = (Select-String -Path src/claude_memory/tools_extra.py -Pattern "mcp.tool\(\)").Count
Write-Host "MCP tools: $($decorators + $runtime) (server=$decorators, extra=$runtime)"

# 5. Test count — actual passing tests
python -m pytest tests/unit/ -q --no-header --tb=no 2>&1 | Select-Object -Last 1
```

### Phase 2: Update Cascade (Order Matters)

1. **`DOCS_INDEX.md`** — Update the Canonical Stats table **first** (single source of truth)
2. **`CODE_INVENTORY.md`** — Add/remove file entries, update totals and date
3. **`ARCHITECTURE.md`** — Update test count in Gold Stack tier table
4. **`CHANGELOG.md`** — Add entry under `[Unreleased]`, update test count in Changed
5. **`UPGRADE_LOG.md`** — Update the Cumulative Summary table at the bottom
6. **`README.md`** — Update feature bullets if test count or quality claims changed
7. **`adr/*.md`** — Grep for stale test counts (`grep -r "460\|463\|784" docs/adr/`)
8. **`MAINTENANCE_MANUAL.md`** / **`USER_MANUAL.md`** — Bump `Last updated` date
9. **`GOTCHAS.md`** — Add any new gotchas discovered during the work
10. **`MCP_TOOL_REFERENCE.md`** — Update if tools were added/removed/changed

### Phase 3: Verification

```powershell
# Grep for any remaining stale numbers (adapt pattern to old values)
Select-String -Path docs/*.md,README.md -Pattern "OLD_NUMBER" -CaseSensitive

# Confirm no phantom/missing files remain
# (re-run Phase 1 commands — output must be empty)
```
