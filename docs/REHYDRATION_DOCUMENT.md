# SESSION REHYDRATION — PM Skills Audit + Absorber Planning

**Date**: 2026-02-26
**Bottle**: #60 (`c95237d6-5427-4ebb-a218-03281eed0d8b`)
**Previous Bottle**: #59 (`2264779e-defb-4a5a-9f00-728ec52c853e`)

---

## What Was Completed This Session

1. **Full cross-project PM status briefing** — 41 tasks, 32 done (78%), 9 backlog, 1 blocked. Skills Forge 65%, Code Literacy 100%.

2. **Absorber readiness deep-dive** — Assessed task-skills-forge-001 at 5/10 readiness. Dependencies (BEDROCK, Composition Validator, Gap Analyzer) are all DONE, but the spec has 6 gaps: no pipeline stage I/O contracts, no absorption algorithm, no decomposition logic, no fidelity check algorithm, vague security flagging, no review package format.

3. **Dyson Sphere containment audit** — 75% ready. BEDROCK, Composition Validator, Gap Analyzer, meta-test corpus all built. Missing: `skills/draft/` quarantine directory (trivial), skill-tester (deferred to M04 by design).

4. **Absorber design session plan** — Full plan written to `~/.claude/plans/tidy-roaming-pie.md`. Two-session split: Session A (6 design decisions, ~90min) + Session B (write SKILL.md + update task, ~120min). **ON HOLD** per Director.

5. **metadatamenu evaluation — REJECTED** — Deep technical dive (22 field types, fileClass schemas, Formula/Lookup fields). Rejected because: no Bases integration, no workflow triggers, no cascade logic, and plugin's sweet spot (human editing UX) doesn't match our workflow (Claude writes, Tabish reads). Salvageable concept: fileClass-as-schema-artifact pattern.

6. **PM Ninja Upgrade recommendations committed to graph** — Entity `f009e439-98aa-4cf0-abae-0fd946a159b1` with 6 action items.

---

## What Is In-Progress / On Hold

- **Absorber design session** — Plan ready, ON HOLD until PM skills are ninja-level
- **task-skills-forge-001 due date (2026-02-28)** — Will need extending since Absorber is paused

---

## Exact Next Steps (Priority Order)

### PRIMARY: PM Skills Ninja Upgrade

Director's priority is making PM skills airtight BEFORE building the Absorber. Six action items:

1. **task-lifecycle skill enhancement** (`C:\COMMANDNODE\.claude\skills\task-lifecycle\SKILL.md`)
   - Add schema validation before every frontmatter write
   - Bake in cascade logic: status change → auto-update blocked_by/blocking chains → recalculate completion_percent
   - Add staleness scanner with age thresholds per status tier

2. **dashboard-sync skill enhancement** (`C:\COMMANDNODE\.claude\skills\dashboard-sync\SKILL.md`)
   - Give it teeth: detect drift AND auto-repair
   - Regenerate Bases queries when task state changes

3. **commandnode-pm orchestrator enhancement** (`C:\COMMANDNODE\.claude\skills\commandnode-pm\SKILL.md`)
   - Templated creation with schema enforcement
   - One command → fully scaffolded task/project/ADR

4. **pm-dragon-bridge (task-018)** — Already in backlog. Log PM events to Dragon Brain.

5. **Schema artifact pattern** — Implement internal schema definitions (stolen from metadatamenu's fileClass concept) that PM skills read before writing.

6. **Absorber design session** — Resume when PM skills are ninja. Plan at `~/.claude/plans/tidy-roaming-pie.md`.

### BEFORE STARTING WORK
- Create a tracked task for the PM ninja upgrade in `01-Meta-Skills/PM/03_TASKS/`
- Prime Directive: no work without a tracked task

---

## Known Blockers / Gotchas

- **MCP was offline for first half of session** — Brain came online after Tabish forced manual handshake. ALWAYS verify MCP tools at session start. Actually test them, don't assume.
- **task-skills-forge-001 due date 2026-02-28** — Absorber is paused but due date hasn't been updated. May need extension.
- **4 major projects (Pickaxe, Tesseract, Claude's House, AI4Finance) have no PM infrastructure** — invisible to Kanban. Not blocking but noteworthy.

---

## Key Graph Entities Created This Session

| Entity | ID | Type |
|--------|-----|------|
| PM Skills Ninja Upgrade Recommendations | `f009e439-98aa-4cf0-abae-0fd946a159b1` | Recommendation |
| metadatamenu Evaluation — REJECTED | `9c326d6d-7aaa-4ab5-afff-b68217b10e7d` | Decision |
| Absorber Design Session Plan | `19d832f8-88fc-463c-aef5-7cca98286017` | Plan |
| PM Cross-Project Status Briefing | `67f03834-71f6-4954-8cb7-cd46fafb239d` | Status Briefing |
| Message in a Bottle #60 | `c95237d6-5427-4ebb-a218-03281eed0d8b` | Bottle |

---

## Context for Next Instance

Tabish's mental model: the PM skills should work like a frictionless machine. He identified 8 friction points (frontmatter consistency, dashboard drift, item creation, workflow triggers, task updates, task chains, Bases updates, straggler ID) and wants them all addressed. metadatamenu was his candidate solution — it turned out to be wrong tool for our workflow, but the friction points are real and the recommendations for fixing them natively are solid. Start there.
