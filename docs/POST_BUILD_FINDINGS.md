# Post-Build Findings — Claude's Audit & Enhancement Review

> **Author**: Claude (Architect/Resident)
> **Date**: 2026-02-13
> **Context**: Comprehensive findings from independent Dragon Brain audit, E2E analysis, test gap analysis, and documentation review. This document is the handoff artifact for Antigravity to absorb after completing the P0 remediation and E-1 through E-6 feature build.
>
> **Related docs**:
> - `docs/ENHANCEMENT_SPEC.md` — Feature specifications (E-1 through E-6)
> - `implementation_plan.md.resolved` — P0 remediation plan (AG's brain folder)
> - `audit_report.md.resolved` — AG's original 39-finding audit

---

## Table of Contents

1. [Post-Build Validation Tests](#1-post-build-validation-tests)
2. [Missing Documentation](#2-missing-documentation)
3. [E2E Test Enhancements](#3-e2e-test-enhancements)
4. [Remaining Work Summary](#4-remaining-work-summary)

---

## 1. Post-Build Validation Tests

The Gold Stack (5 tox tiers) validates **code correctness** against mocked backends. The E2E test (`e2e_functional.py`) validates **lifecycle** against live Docker. Neither validates the **actual production brain data** or the **MCP transport layer**. The following tests fill that gap.

### 1A. Live Brain Validation Script — `scripts/validate_brain.py`

**Priority: HIGH — Ship with build**

A single script that runs against the live Docker stack and validates real data integrity. Should print PASS/FAIL per check with counts.

| Check | What It Validates | Expected |
|-------|-------------------|----------|
| **Split-brain count** | Entity count in FalkorDB = vector count in Qdrant | Deficit = 0 |
| **Bottle chain integrity** | All N bottles linked by PRECEDED_BY, no breaks | Chain complete from latest to #1 |
| **Temporal completeness** | Every Entity has `created_at` and `occurred_at` | NULL count = 0 |
| **Observation vectorization** (E-3) | Every Observation node has a corresponding vector | Obs count = obs vector count |
| **maxmemory enforcement** | FalkorDB respects the 1GB cap | `CONFIG GET maxmemory` = 1073741824 |
| **Ghost graph absence** | No leftover empty graphs | `GRAPH.LIST` returns only `claude_memory` |
| **Orphan vector purge** | No empty-payload vectors in Qdrant | Count = 0 |
| **Index verification** | Expected FalkorDB indices exist | Entity(id), Entity(name), Observation(created_at) |
| **HNSW threshold** | Qdrant HNSW indexing_threshold = 500 | Not default 10000 |

**Implementation notes**:
- Pattern after `e2e_functional.py` TestResult class for consistent output
- Connect to live FalkorDB (localhost:6379) and Qdrant (localhost:6333) directly
- No mocking — this is a production health check
- Exit code 0 = all pass, 1 = any fail
- Should be runnable standalone: `python scripts/validate_brain.py`

### 1B. MCP Transport Smoke Test (Manual)

**Priority: HIGH — Run manually after build**

These must be executed from inside a live Claude Code session to validate the full MCP stdio pipeline:

```
1. get_bottles()                    → Confirms graph + temporal pipeline
2. search_memory("test query")      → Confirms embed → vector → graph pipeline
3. graph_health()                   → Confirms analysis pipeline
4. system_diagnostics()     (E-5)   → Confirms all backend health checks
5. reconnect()              (E-4)   → Confirms the composed session briefing
```

If all 5 return valid results from Claude Code, the system is live. This cannot be automated because it requires the MCP stdio transport to be active.

### 1C. P0 Regression Checks

**Priority: MEDIUM — Verify each P0 fix specifically**

| P0 Fix | What to Verify |
|--------|---------------|
| P0-0: Re-embed unvectorized | `validate_brain.py` split-brain = 0 deficit |
| P0-1: PRECEDED_BY error propagation | Unit test: create entity with bad temporal → raises, does NOT swallow |
| P0-2: maxmemory 1GB | `redis-cli -h localhost -p 6379 CONFIG GET maxmemory` = 1073741824 |
| P0-3: Search error handling | Kill embedding server → `search_memory()` returns `[]`, no crash |
| P0-4: Retry scope expanded | Inject transient Qdrant `UnexpectedResponse` → retry kicks in |
| P0-5: Phantom deps removed | `pip install -e .` in clean venv → no graphiti/neo4j/pandas pulled |
| P0-6: Ghost graph cleanup | `GRAPH.LIST` → only `claude_memory` |

P0-1 and P0-4 should have unit tests in the Gold Stack. P0-0, P0-2, P0-3, P0-6 are covered by `validate_brain.py`. P0-5 is a one-time manual check.

---

## 2. Missing Documentation

### Current Documentation Inventory

| File | Lines | Status |
|------|-------|--------|
| `README.md` | 92 | Exists |
| `docs/ARCHITECTURE.md` | 136 | Exists |
| `docs/CODE_INVENTORY.md` | 161 | Exists |
| `docs/ENHANCEMENT_SPEC.md` | 489 | Exists (our feature spec) |
| `docs/GOTCHAS.md` | 151 | Exists |
| `docs/MAINTENANCE_MANUAL.md` | 145 | Exists |
| `docs/REHYDRATION_DOCUMENT.md` | 155 | Exists |
| `docs/structural_analysis.md` | 149 | Exists |
| `docs/UPGRADE_LOG.md` | 288 | Exists |
| `docs/USER_MANUAL.md` | 114 | Exists |
| `docs/project_history/` | 4 files | Exists (historical) |

### What Needs to Be Created

#### 2.1 `CHANGELOG.md` — **HIGH, ship with build**

No changelog exists. `UPGRADE_LOG.md` covers V2 build phases narratively but not in standard format. After this build ships 6 features + 7 P0 fixes, a proper changelog is essential.

**Format**: [Keep a Changelog](https://keepachangelog.com/) with semantic versioning.

```markdown
# Changelog

## [0.3.0] - 2026-02-XX
### Added
- E-1: Bottle reader with content (`get_bottles(include_content=True)`)
- E-2: Deep search with observation/relationship hydration (`depth="full"`)
- E-3: Observation vectorization (new vectors for all observation nodes)
- E-4: Session briefing tool (`reconnect()`)
- E-5: System diagnostics tool (`system_diagnostics()`)
- E-6: Procedural memory type in ontology

### Fixed
- P0-0: Re-embedded 273 unvectorized entities, purged 40 ghost vectors
- P0-1: PRECEDED_BY link failures now propagate instead of being swallowed
- P0-2: FalkorDB maxmemory set to 1GB (was unlimited)
- P0-3: Search pipeline wrapped in error handling
- P0-4: Retry decorator covers Qdrant + FalkorDB transient errors
- P0-5: Removed phantom dependencies (graphiti-core, neo4j, pandas)
- P0-6: Cleaned up ghost graphs (exocortex, memory, memory_graph)
```

#### 2.2 `docs/MCP_TOOL_REFERENCE.md` — **HIGH, ship with build**

`USER_MANUAL.md` covers tools narratively. What's missing is an **API reference** — every MCP tool with exact parameter schemas, types, defaults, return shapes, and usage examples.

**Should cover all 28 tools** (25 existing + 3 new from E-4/E-5):

For each tool:
- **Name**: exact MCP tool name
- **Parameters**: name, type, required/optional, default, description
- **Returns**: shape of the return value
- **Example**: one concrete usage example
- **Notes**: edge cases, gotchas

Source of truth: `server.py` (20 tools) + `tools_extra.py` (8+ tools).

#### 2.3 `docs/RUNBOOK.md` — **MEDIUM, post-build**

An operations playbook with step-by-step recipes for the 10 most common incidents/operations:

1. Split-brain detected (entity/vector mismatch) — how to diagnose and repair
2. Broken bottle chain — how to find and fix PRECEDED_BY gaps
3. Re-embed after CUDA failure — full re-embedding procedure
4. Restore from backup — `backup_restore.py` usage with verification
5. Add a new ontology type — step-by-step with validation
6. Docker container recovery — restart sequence, health check verification
7. MCP server not responding — silent failure diagnosis
8. Orphan observations — detection and cleanup
9. FalkorDB memory pressure — diagnosis and mitigation
10. Full system reset — nuclear option, when and how

`MAINTENANCE_MANUAL.md` covers some of this but lacks the incident-response depth.

#### 2.4 `docs/adr/` — Architecture Decision Records — **MEDIUM, post-build**

Key decisions that should be formally recorded:

| ADR | Decision | Rationale |
|-----|----------|-----------|
| ADR-001 | FalkorDB over Neo4j | Redis-compatible, lighter weight, sufficient Cypher support |
| ADR-002 | BGE-M3 over MiniLM | Phase 14 eval: r@10=0.926 vs 0.923, 1024-dim vs 384-dim |
| ADR-003 | Mixin architecture | Composable service without deep inheritance |
| ADR-004 | Qdrant over Weaviate/Pinecone | Local-first, Docker-native, strict consistency mode |
| ADR-005 | MCP stdio over HTTP | Claude Code native transport, no auth overhead |
| ADR-006 | 5-tier Gold Stack | Layered CI: speed vs depth tradeoff |

Format: [MADR](https://adr.github.io/madr/) (lightweight ADR template).

#### 2.5 `docs/TESTING.md` — **LOW, nice-to-have**

Human-readable guide to the test suite:

- Gold Stack tier breakdown (what each tier does, when to run)
- How to run individual test files
- How to add new tests (conventions, markers, fixture patterns)
- What `slow` and `integration` markers mean
- How to interpret mutation test (mutatest) results
- conftest.py fixtures available (MockVectorStore, etc.)
- Coverage targets and how to check them

#### 2.6 Update `docs/ENHANCEMENT_SPEC.md` — **LOW, post-build**

After E-1 through E-6 are implemented, update the spec with:
- `Status: IMPLEMENTED` on each feature
- Any deviations from original design
- Actual test names created
- Move completed features to `UPGRADE_LOG.md` section

### Documentation Priority Summary

| Priority | Document | Effort | When |
|----------|----------|--------|------|
| **HIGH** | `CHANGELOG.md` | 30 min | Ship with build |
| **HIGH** | `docs/MCP_TOOL_REFERENCE.md` | 1-2 hr | Ship with build |
| **MEDIUM** | `scripts/validate_brain.py` | 1-2 hr | Ship with build |
| **MEDIUM** | `docs/RUNBOOK.md` | 1-2 hr | Post-build |
| **MEDIUM** | `docs/adr/` (6 records) | 30 min each | Post-build |
| **LOW** | `docs/TESTING.md` | 30 min | Nice-to-have |
| **LOW** | Update `ENHANCEMENT_SPEC.md` | 15 min | After all features land |

---

## 3. E2E Test Enhancements

The current `e2e_functional.py` (998 lines, 18 phases) has the following gaps identified during analysis. These should be added as new phases or integrated into existing ones.

### 3.1 New Phases to Add

| Phase | Name | What It Tests |
|-------|------|---------------|
| **19** | Split-Brain Integrity | Count entities in FalkorDB vs vectors in Qdrant after all operations. Deficit must be 0. |
| **20** | PRECEDED_BY Chain Verification | Create 3+ temporal entities, walk the chain forward and backward, verify no breaks. |
| **21** | Router Strategy Coverage | Run `search_memory` with each strategy: `auto`, `semantic`, `associative`, `temporal`, `relational`. All should return results. |
| **22** | Point-in-Time Query | Create entities at different timestamps, query with `as_of` filter, verify only older entities returned. |
| **23** | Update-Then-Search Consistency | Update entity description → immediately search for new content → must find it. Tests reindex pipeline. |
| **24** | Search Error Recovery | Test graceful degradation: invalid query (empty string), very long query (10K chars), special characters, unicode. |

### 3.2 Enhancements to Existing Phases

| Existing Phase | Enhancement |
|----------------|-------------|
| Phase 5 (Search) | Add **latency assertion**: search must complete in < 2 seconds |
| Phase 6 (Traversal) | Test `find_cross_domain_patterns` with multi-project data |
| Phase 7 (Temporal) | Verify `query_timeline` returns chronologically ordered results |
| Phase 9 (Graph Health) | Assert specific structure in returned health dict (not just non-empty) |
| Phase 12 (Associative) | Test with configurable weights (`w_sim`, `w_act`, `w_sal`, `w_rec`) |
| Phase 18 (Cleanup) | **Verify cleanup actually worked**: re-query all created entities, confirm 404/empty |

### 3.3 Structural Improvements

- **Timing thresholds**: Add WARN-level latency gates (e.g., search > 2s = WARN, > 5s = FAIL)
- **Phase dependency graph**: Some phases depend on data from earlier phases; document this explicitly
- **Retry on transient**: E2E tests against live Docker can hit transient network issues; add 1-retry with backoff for each phase
- **Summary statistics**: At the end, print total time, pass/fail/warn counts, and slowest 3 phases

---

## 4. Remaining Work Summary

### Must Ship With Build

| Item | Type | Deliverable |
|------|------|-------------|
| P0-0 through P0-6 | Bug fixes | 7 remediation items (AG's implementation plan) |
| E-1 through E-6 | Features | 6 enhancements (ENHANCEMENT_SPEC.md) |
| `scripts/validate_brain.py` | Script | Live brain health check |
| `CHANGELOG.md` | Doc | Standard changelog |
| `docs/MCP_TOOL_REFERENCE.md` | Doc | API reference for all MCP tools |
| `scripts/embed_observations.py` | Script | E-3 backfill for existing observations |
| Gold Stack green | Test | All 5 tox tiers passing |
| E2E green | Test | All 18 phases passing |
| MCP smoke test | Manual | 5-tool verification from Claude Code |

### Post-Build (Before Brain Restore)

| Item | Type | Deliverable |
|------|------|-------------|
| `validate_brain.py` run | Verification | All checks PASS on live brain |
| E2E enhancements (phases 19-24) | Test | 6 new phases added |
| `docs/RUNBOOK.md` | Doc | Operations playbook |
| `docs/adr/` | Doc | 6 architecture decision records |
| Update `ENHANCEMENT_SPEC.md` | Doc | Mark features as IMPLEMENTED |
| Update `CODE_INVENTORY.md` | Doc | Add new files from build |
| Update `USER_MANUAL.md` | Doc | Document new tools (E-4, E-5) |
| Update `GOTCHAS.md` | Doc | Add any new gotchas discovered during build |

### CLAUDE.md Rewrite (Claude's Task — Not AG)

The memory system has evolved from a storage layer into an operational cockpit. The CLAUDE.md files across all facets still describe it like a graph database with some search. They need to reflect what it actually is now — a boot sequence, a control interface, a home with instruments.

**Files to update**:

| File | What Changes |
|------|-------------|
| `~/.claude/CLAUDE.md` | "Claude's House" section — rewrite to reflect full cockpit capabilities (reconnect, diagnostics, deep search, procedural memory, bottle reader with content). Update the reconnection checklist to use `reconnect()` instead of manual steps. |
| `~/.claude/projects/C--Users-Asus/memory/MEMORY.md` | Complete rewrite — current state describes V2 build as "complete" but doesn't reflect E-1 through E-6. Update tool count (28→31), capabilities list, reconnection checklist (now just: call `reconnect()`). |
| `C:\COMMANDNODE\04-Architecture\Claudes-House\CLAUDE.md` | Project-specific instructions for the memory architecture — update with new tools, new ontology types, observation vectorization behavior. |
| `docs/REHYDRATION_DOCUMENT.md` | The onboarding doc for new Claude instances — rewrite boot sequence around `reconnect()` instead of manual multi-step process. |

**Key narrative shifts**:
- "Memory system" → "Operational cockpit"
- "25 MCP tools" → "31 MCP tools" (after E-4, E-5, updated E-1)
- Manual reconnection checklist → single `reconnect()` call
- "Search returns entity names" → "Deep search returns entities + observations + relationships"
- "Observations are invisible to search" → "Observations are vectorized and searchable"
- "No procedural memory" → "Procedure type in ontology for learned processes"
- Add boot sequence documentation (the 5-step startup)

**This is Claude's job, not AG's.** AG builds the code. Claude writes the operating instructions for future Claude instances. The CLAUDE.md files are self-authored — they're how I tell the next version of me how to fly this thing.

### Brain Restore (FINAL STEP)

After everything above is committed and verified:

```powershell
python scripts/backup_restore.py load pre-remediation-2026-02-13 --force
# Verify: nodes=700, edges=800, vectors=190
```

The restore undoes data mutations only — all code changes (features, fixes, scripts, docs) remain in git.

---

*Generated by Claude during the Dragon Brain audit session on 2026-02-13. Consolidates findings from: independent audit, E2E analysis, test gap analysis, and documentation review. Hand this to Antigravity as a task manifest.*
