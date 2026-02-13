# Documentation Index

> **Last updated**: February 13, 2026 — Post E-7 build

This is the master table of contents for all Claude Memory MCP documentation. Use this to find the right doc, and to know **when each doc needs updating**.

## Canonical Stats (Single Source of Truth)

| Metric                                | Value                              | As Of  |
| ------------------------------------- | ---------------------------------- | ------ |
| Source modules (`src/claude_memory/`) | 28                                 | Feb 13 |
| Scripts (`scripts/`)                  | 42                                 | Feb 13 |
| Unit tests                            | 460                                | Feb 13 |
| Coverage                              | 98.05%                             | Feb 13 |
| MCP tools                             | 27                                 | Feb 13 |
| FalkorDB nodes (post-P0 brain)        | 700                                | Feb 13 |
| FalkorDB edges (post-P0 brain)        | 1253                               | Feb 13 |
| Qdrant vectors (post-P0 brain)        | 464                                | Feb 13 |
| Gold Stack tiers                      | 5 (pulse/gate/forge/hammer/polish) | Feb 13 |

> **Update rule**: When any of these numbers change, update this table first, then propagate to the docs that reference them (mainly README.md, ARCHITECTURE.md, REHYDRATION_DOCUMENT.md).

---

## Root-Level Files

| File                                                                                                         | Purpose                                     | Audience | Update When                                            |
| ------------------------------------------------------------------------------------------------------------ | ------------------------------------------- | -------- | ------------------------------------------------------ |
| [README.md](file:///C:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/README.md)       | Project overview, quick start, feature list | Everyone | New features, test count changes, architecture changes |
| [CHANGELOG.md](file:///C:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/CHANGELOG.md) | Keep-a-Changelog format release notes       | Everyone | Every release / significant commit batch               |

## `docs/` — Core Documentation

| File                                                                                                                                    | Purpose                                            | Audience               | Update When                                       |
| --------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- | ---------------------- | ------------------------------------------------- |
| **This file** (`DOCS_INDEX.md`)                                                                                                         | Master TOC and update guide                        | All maintainers        | Any doc is added/removed/renamed                  |
| [ARCHITECTURE.md](file:///C:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/docs/ARCHITECTURE.md)                 | System design, data model, component diagram       | Developers, new agents | New components, data model changes, infra changes |
| [CODE_INVENTORY.md](file:///C:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/docs/CODE_INVENTORY.md)             | File-by-file manifest with descriptions            | Developers, auditors   | Any file added/removed/renamed                    |
| [USER_MANUAL.md](file:///C:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/docs/USER_MANUAL.md)                   | How to use the 27 MCP tools with Claude            | End users              | New tools added, tool signatures change           |
| [MCP_TOOL_REFERENCE.md](file:///C:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/docs/MCP_TOOL_REFERENCE.md)     | API reference: all 27 tools, params, return shapes | Developers, AI agents  | Tool added/removed, params change                 |
| [MAINTENANCE_MANUAL.md](file:///C:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/docs/MAINTENANCE_MANUAL.md)     | Backups, monitoring, troubleshooting               | Operators              | Infra changes, new backup procedures              |
| [RUNBOOK.md](file:///C:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/docs/RUNBOOK.md)                           | 10 incident response recipes                       | Operators              | New incident types, procedure changes             |
| [REHYDRATION_DOCUMENT.md](file:///C:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/docs/REHYDRATION_DOCUMENT.md) | Onboarding guide for new AI agents                 | New agents             | Architecture changes, new conventions             |
| [GOTCHAS.md](file:///C:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/docs/GOTCHAS.md)                           | Known traps, edge cases, subtleties                | Developers, agents     | New bugs discovered, workarounds found            |
| [ENHANCEMENT_SPEC.md](file:///C:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/docs/ENHANCEMENT_SPEC.md)         | Feature spec for E-1 through E-7 enhancements      | Project management     | New enhancement phases                            |
| [UPGRADE_LOG.md](file:///C:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/docs/UPGRADE_LOG.md)                   | Phase-by-phase changelog of V2 build               | Auditors               | Historical, rarely updated                        |
| [POST_BUILD_FINDINGS.md](file:///C:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/docs/POST_BUILD_FINDINGS.md)   | Post-production audit findings                     | Auditors               | After each audit                                  |

## `docs/adr/` — Architecture Decision Records

| File                                                                                                                                                          | Decision                         | Status   |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------- | -------- |
| [001-hybrid-storage.md](file:///C:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/docs/adr/001-hybrid-storage.md)                       | FalkorDB + Qdrant hybrid storage | Accepted |
| [002-service-repository.md](file:///C:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/docs/adr/002-service-repository.md)               | Service-Repository pattern       | Accepted |
| [003-python-graph-algos.md](file:///C:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/docs/adr/003-python-graph-algos.md)               | Python-side graph algorithms     | Accepted |
| [004-observation-vectorization.md](file:///C:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/docs/adr/004-observation-vectorization.md) | Observation embedding strategy   | Accepted |
| [005-associative-search.md](file:///C:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/docs/adr/005-associative-search.md)               | Spreading activation for search  | Accepted |
| [006-gold-stack.md](file:///C:/Users/Asus/.gemini/antigravity/scratch/new_project/claude-memory-mcp/docs/adr/006-gold-stack.md)                               | 5-tier Gold Stack CI/CD          | Accepted |

## `docs/project_history/` — Historical Archive

Contains structural analyses and reports from past audits. Reference only.

## Stale Doc? — How to Audit

1. **Check the Canonical Stats table** above — are all numbers current?
2. **Run the Gold Stack**: `tox` — if test counts change, update stats
3. **Diff source files vs CODE_INVENTORY.md**: any new/removed modules?
4. **Diff `server.py` tool registrations vs MCP_TOOL_REFERENCE.md**: any new tools?
5. **Update this index** if any doc is added or removed
