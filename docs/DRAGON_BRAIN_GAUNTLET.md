# DRAGON BRAIN GAUNTLET — Unhinged Testing Specification

**Target:** claude-memory-mcp (Dragon Brain V2 Intelligence Layer)
**Location:** `./`
**Runner:** Claude (local execution with Docker)
**Date:** 2026-02-22
**Author:** Claude (Architect)
**Derived from:** `JULES_TESTING_GAUNTLET.md` (Tesseract V2 variant)

---

## EXECUTION MODEL

**This is NOT a Jules spec.** The runner executes everything locally with full Docker access. No output-capture infrastructure needed. No "trick the runner" framing. Execute, assert, and report.

**Prerequisites:**
```bash
# Docker containers must be healthy
docker ps --filter "name=claude-memory" --format "{{.Names}}: {{.Status}}"
# Expected: all 4 services healthy (graphdb, qdrant, embeddings, dashboard)

# Tox must be available
cd ./
tox --version

# Python environment
python --version  # 3.12+
pip install -e ".[dev]"
```

**Execution order:** Rounds 1-20, sequential. Each round has EXIT CRITERIA — if a round fails, note it and continue (don't block subsequent rounds).

**Reporting:** After all 20 rounds, produce `GAUNTLET_RESULTS.md` in the project root with per-round pass/fail, metrics, and a prioritized findings list.

---

## ROUND 1: IRON BASELINE

**Goal:** Establish the current state before we break anything.

### 1A. Gold Stack (existing tox tiers)

```bash
tox -e pulse    # lint + type check + 388 tests + 90% branch coverage
tox -e gate     # Hypothesis CI + diff-cover
tox -e hammer   # bandit + pip-audit + detect-secrets
tox -e polish   # docstr-coverage + codespell
```

Record: pass/fail per tier, total test count, total time, coverage percentage.

### 1B. Per-Module Coverage Breakdown

```bash
coverage run -m pytest tests/ --tb=short
coverage report --show-missing --sort=cover | tee coverage_baseline.txt
```

Flag every module below 90% coverage. These are Round 4 mutation targets.

### 1C. Test Inventory

```bash
pytest --collect-only -q | tail -5    # total test count
pytest --co -q | wc -l               # function count
find tests/ -name "*.py" | wc -l     # file count
```

### EXIT CRITERIA
- All 4 tox tiers pass (pulse, gate, hammer, polish)
- Coverage ≥ 90% branch
- Test count ≥ 388
- Record all baselines for comparison in Round 20

---

## ROUND 2: STRESS TEST

**Goal:** Find flaky tests, state leakage, and ordering dependencies.

### 2A. Repeat Battery

```bash
# 5x repeat — every test runs 5 times in sequence
pytest tests/ --count=5 --tb=short -q

# 3 random seeds — shuffle test order
pytest tests/ -p randomly --randomly-seed=42 -q
pytest tests/ -p randomly --randomly-seed=1337 -q
pytest tests/ -p randomly --randomly-seed=31415 -q
```

**Assert:** Zero failures across all runs. Any failure = flaky test = P1 bug.

### 2B. Parallel Execution

```bash
# Run tests in parallel across 4 workers
pytest tests/ -n 4 --tb=short -q
```

**Assert:** Same pass count as serial. Any new failure = thread-safety issue in test fixtures.

### 2C. Docker Resilience

```bash
# Restart embedding service mid-test
pytest tests/unit/test_embedding_coverage.py -v &
sleep 5
docker restart claude-memory-mcp-embeddings-1
wait

# Restart FalkorDB mid-E2E
pytest tests/e2e_functional.py -v &
sleep 10
docker restart claude-memory-mcp-graphdb-1
wait
```

**Assert:** Tests either pass (retry logic works) or fail with clean error messages (no hangs, no zombie processes). Document which tests survive container restarts and which don't.

### EXIT CRITERIA
- Zero flaky tests across 2,000+ executions (388 x 5 + 3 random orderings)
- Parallel execution matches serial results
- Container restart behavior documented

---

## ROUND 3: PROPERTY STORM (Hypothesis)

**Goal:** Find edge cases that hand-written tests miss. Expand the existing `gate` tier.

### 3A. Schema Validation Properties

**File:** `tests/gauntlet/test_hypothesis_schema.py`

Target: `src/claude_memory/schema.py` — 15+ Pydantic models

```python
# Properties to test:
# 1. EntityCreateParams accepts any non-empty name string
# 2. EntityCreateParams rejects empty name
# 3. All valid entity_types are accepted (13 types in ontology)
# 4. RelationshipCreateParams validates source_id != target_id (if applicable)
# 5. SearchResult scores are always 0.0 <= score <= 1.0
# 6. ObservationParams content is never empty after validation
# 7. TemporalQueryParams date parsing handles ISO format correctly
# 8. BottleQueryParams include_content default is False
# 9. GapDetectionParams min_connections >= 1
# 10. Round-trip: any valid params → serialize to JSON → deserialize → equals original
```

**Config:** `max_examples=5000` per property, `deadline=None`.

### 3B. Router Classification Properties

**File:** `tests/gauntlet/test_hypothesis_router.py`

Target: `src/claude_memory/router.py` — `QueryRouter.classify()`

```python
# Properties to test:
# 1. classify() always returns a valid QueryIntent enum member
# 2. Empty string → returns SEMANTIC (default fallback)
# 3. Temporal keywords ("when", "before", "after", "timeline") → TEMPORAL
# 4. Relational keywords ("related", "connected", "neighbors") → RELATIONAL
# 5. Associative keywords ("reminds", "similar", "pattern") → ASSOCIATIVE
# 6. Random gibberish → never crashes, always returns valid intent
# 7. Very long strings (10K+ chars) → doesn't hang, returns valid intent
# 8. Unicode/emoji → doesn't crash
```

**Config:** `max_examples=5000`, `deadline=None`.

### 3C. Activation Engine Properties

**File:** `tests/gauntlet/test_hypothesis_activation.py`

Target: `src/claude_memory/activation.py` — Spreading activation engine

```python
# Properties to test:
# 1. Initial energy = 1.0 for seed nodes
# 2. Energy decays monotonically with hops (decay=0.6 per hop)
# 3. No node receives more energy than the seed
# 4. max_hops=0 → returns only seed nodes
# 5. max_hops=N → no result has path_length > N
# 6. Empty graph → returns empty results, no crash
# 7. Single-node graph → returns only that node
# 8. Disconnected graph → activation doesn't leak across components
```

**Config:** `max_examples=2000`, `deadline=None`.

### 3D. Cypher Query Builder Properties

**File:** `tests/gauntlet/test_hypothesis_cypher.py`

Target: `src/claude_memory/repository_queries.py` — Query builders

```python
# Properties to test:
# 1. All generated Cypher strings are valid (no unclosed quotes, balanced brackets)
# 2. All user-supplied strings go through parameterization (never interpolated)
# 3. Special characters in entity names don't break queries
# 4. Empty filter dict → query returns all results
# 5. Filter with unknown key → raises ValueError (not Cypher injection)
# 6. Very long entity names (1000+ chars) → parameterized correctly
# 7. Entity names with Cypher operators (MATCH, RETURN, DELETE) → treated as data, not code
```

**Config:** `max_examples=3000`, `deadline=None`.

### 3E. Search Pipeline Properties

**File:** `tests/gauntlet/test_hypothesis_search.py`

Target: `src/claude_memory/search.py` + `search_advanced.py`

```python
# Properties to test:
# 1. Search results are sorted by score (descending)
# 2. limit=N → at most N results returned
# 3. limit=0 → empty results, no crash
# 4. Empty query string → returns results (fallback behavior) or clean empty
# 5. Search with non-existent entity_type → empty results, no crash
# 6. Hologram retrieval with depth=0 → returns only anchor entity
# 7. Hologram retrieval with depth=N → all results within N hops of anchor
# 8. MMR diversity: with lambda=0.0, results maximize diversity; with lambda=1.0, pure relevance
```

**Config:** `max_examples=2000`, `deadline=None`.

### 3F. Clustering Properties

**File:** `tests/gauntlet/test_hypothesis_clustering.py`

Target: `src/claude_memory/clustering.py` — DBSCAN + gap detection

```python
# Properties to test:
# 1. Clusters are non-overlapping (no entity in two clusters)
# 2. Every entity is either in a cluster or noise (-1)
# 3. Empty input → empty clusters, no crash
# 4. Single entity → single cluster or noise
# 5. eps=0 → every entity is noise (no neighbors within 0 distance)
# 6. min_samples=1 → every entity is in its own cluster (no noise)
# 7. Gap detection: identified gaps have fewer connections than min_connections threshold
```

**Config:** `max_examples=1000`, `deadline=None`.

### EXIT CRITERIA
- All property tests pass with zero falsifying examples
- Total examples: 25,000+
- No crashes, hangs, or unhandled exceptions

---

## ROUND 4: MUTATION MASSACRE

**Goal:** Measure real test quality. Line coverage lies. Mutation kill rate doesn't.

### 4A. Full Mutation Run

```bash
# Run mutatest with FULL mutant count (not sampled)
tox -e forge
```

If `forge` uses a sample size, override:

```bash
# Direct mutatest invocation with all mutants
mutatest --src src/claude_memory/ --runner "pytest tests/" --timeout 60
```

### 4B. Per-Module Kill Rates

Record kill rate for EVERY source module:

| Module | Mutants | Killed | Survived | Timeout | Kill Rate |
|--------|---------|--------|----------|---------|-----------|
| repository.py | ? | ? | ? | ? | ?% |
| vector_store.py | ? | ? | ? | ? | ?% |
| ... | | | | | |

**Flag every module below 75% kill rate.** These need targeted mutation killer tests.

### 4C. Surviving Mutant Analysis

For the 5 modules with lowest kill rates, extract the surviving mutants:

```bash
# Show what survived
mutatest --src src/claude_memory/<module>.py --runner "pytest tests/" --report surviving
```

For each survivor: document the exact mutation (line, original, mutated) and WHY the test suite missed it. Categorize:
- **Missing assertion** — test runs the code but doesn't check the output
- **Mocked away** — test mocks the function being mutated
- **Untested branch** — code path has no coverage
- **Retry/config mutation** — timing/retry parameters (acceptable survivors)

### 4D. Mutation Killer Tests

**File:** `tests/gauntlet/test_mutation_killers.py`

Write targeted assertion tests to kill the top 50 survivors. Focus on:
- Return value assertions (not just "didn't crash")
- Side effect assertions (graph was written, vector was stored)
- Error path assertions (correct exception type raised)
- Boundary assertions (off-by-one, empty collection, None handling)

### EXIT CRITERIA
- Kill rate ≥ 75% across all modules (hard threshold)
- All surviving mutants categorized
- Mutation killer tests written and passing
- If any module is below 75% after killers, escalate to P0

---

## ROUND 5: FUZZ BLITZ

**Goal:** Throw garbage at every input surface and see what breaks.

### 5A. Hypothesis Fuzzer Mode

**File:** `tests/gauntlet/test_fuzz_blitz.py`

```python
# Target 1: Schema validation (Pydantic models)
# Feed random dicts → EntityCreateParams, RelationshipCreateParams, etc.
# Assert: either valid construction or clean ValidationError — never unhandled crash
# Config: max_examples=50000

# Target 2: Cypher query builders
# Feed random strings as entity names, relationship types, filter keys
# Assert: parameterized query or ValueError — never raw string interpolation
# Config: max_examples=50000

# Target 3: Search pipeline
# Feed random bytes, unicode, empty strings, very long strings
# Assert: empty results or clean error — never crash
# Config: max_examples=50000

# Target 4: Embedding client
# Feed random bytes as embedding response
# Assert: clean error handling — never None embedding stored
# Config: max_examples=10000

# Target 5: MCP tool input parsing
# Feed random JSON to each of the 29 tool handlers
# Assert: clean error response with "error" key — never unhandled exception
# Config: max_examples=5000 per tool (145,000 total)
```

### 5B. Boundary Conditions

Specific edge cases to test:
- Entity name = empty string `""`
- Entity name = single character `"a"`
- Entity name = 100,000 characters
- Entity name = null bytes `"\x00"`
- Entity name = only whitespace `"   "`
- Entity name = SQL injection `"'; DROP TABLE --"`
- Entity name = Cypher injection `"') RETURN n //"`
- Relationship to self (source_id = target_id)
- Circular relationships (A→B→C→A)
- 10,000 observations on single entity
- Search with embedding dimension mismatch (512-dim instead of 1024)
- Timestamp in year 1900, year 9999, epoch 0, negative epoch

### EXIT CRITERIA
- Zero unhandled crashes across 300,000+ fuzz inputs
- All failures are clean ValidationError or documented error responses
- No silent data corruption (garbage stored as valid data)

---

## ROUND 6: STATIC INQUISITION

**Goal:** Let the machines find what humans miss.

### 6A. Type Checking

```bash
# Standard mode (already in pulse)
mypy src/claude_memory/ --ignore-missing-imports

# Strict mode — find the real gaps
mypy src/claude_memory/ --strict --ignore-missing-imports 2>&1 | tee mypy_strict.txt
wc -l mypy_strict.txt
```

Record: standard errors (must be 0), strict errors (document count).

### 6B. Linting

```bash
# Full ruff check (already in pulse)
ruff check src/ tests/

# All rules (not just defaults)
ruff check src/ --select ALL --ignore E501,D,ANN 2>&1 | head -50
```

### 6C. Complexity Analysis

```bash
# Cyclomatic complexity — grade C or worse
radon cc src/claude_memory/ -n C -s 2>&1 | tee complexity.txt

# Maintainability index — anything below B
radon mi src/claude_memory/ -n B -s 2>&1 | tee maintainability.txt

# Halstead metrics (optional)
radon hal src/claude_memory/ 2>&1 | tee halstead.txt
```

**Document:** Every function with CC grade C or worse. Every module with MI below 'A'.

### 6D. Dead Code

```bash
vulture src/claude_memory/ --min-confidence 80 2>&1 | tee dead_code.txt
```

### 6E. Exception Census

```bash
# Count bare except Exception
grep -rn "except Exception" src/claude_memory/ | wc -l

# Count logger.error without exc_info
grep -rn "logger.error" src/claude_memory/ | grep -v "exc_info" | wc -l

# Count bare except (no type)
grep -rn "except:" src/claude_memory/ | wc -l
```

### EXIT CRITERIA
- mypy standard: 0 errors
- ruff: 0 errors on default rules
- radon CC: document all grade C+ functions
- vulture: document all dead code
- Exception census: count and categorize

---

## ROUND 7: SECURITY SWEEP

**Goal:** Find vulnerabilities before someone else does.

### 7A. Security Linting

```bash
# Bandit (already in hammer)
bandit -r src/claude_memory/ -ll -ii 2>&1 | tee bandit.txt

# Semgrep (if available)
semgrep --config=auto src/claude_memory/ 2>&1 | tee semgrep.txt
```

### 7B. Dependency Audit

```bash
# Known CVEs
pip-audit 2>&1 | tee pip_audit.txt

# Secret scanning
detect-secrets scan src/ tests/ 2>&1 | tee secrets.txt
```

### 7C. Cypher Injection Audit (CRITICAL — Dragon Brain specific)

**This is the #1 security concern for a graph database system.**

```bash
# Find all f-string Cypher queries
grep -rn 'f".*MATCH\|f".*CREATE\|f".*MERGE\|f".*SET\|f".*DELETE\|f".*RETURN' src/claude_memory/ | tee cypher_fstrings.txt

# Find all .format() Cypher queries
grep -rn '\.format.*MATCH\|\.format.*CREATE\|\.format.*MERGE' src/claude_memory/ | tee cypher_format.txt

# Find parameterized queries (the SAFE pattern)
grep -rn 'params=' src/claude_memory/repository*.py | wc -l
```

**For every f-string/format Cypher query found:**
1. Trace the input source — is the interpolated value user-controlled?
2. Is there input validation before interpolation?
3. Can it be converted to parameterized query?

**Write injection test:**
```python
# Test: malicious entity name doesn't execute as Cypher
service.create_entity(name="') RETURN n //", entity_type="Entity")
# Assert: entity created with literal name, no Cypher execution

# Test: malicious filter key doesn't execute
service.search_memory(query="test", filters={"name'] RETURN n //": "value"})
# Assert: ValueError raised, no Cypher execution
```

### 7D. Authentication & Transport

```bash
# Verify MCP uses stdio (not HTTP) — no auth surface
grep -rn "uvicorn\|FastAPI\|flask\|http.server" src/claude_memory/server.py

# Verify no hardcoded credentials
grep -rn "password\|secret\|token\|api_key" src/claude_memory/ --include="*.py" | grep -v "test" | grep -v "#"
```

### EXIT CRITERIA
- Bandit: 0 medium+ issues (suppressed with justification only)
- pip-audit: 0 known CVEs (or documented + accepted)
- detect-secrets: 0 real secrets
- Cypher injection: all f-string queries audited, all user-facing queries parameterized
- No hardcoded credentials

---

## ROUND 8: CONTRACTS & SNAPSHOTS

**Goal:** Lock down API contracts so regressions are caught immediately.

### 8A. MCP Tool Input/Output Contracts

**File:** `tests/gauntlet/test_mcp_contracts.py`

For each of the 29 MCP tools:
```python
# 1. Valid input → returns dict with expected keys
# 2. Missing required param → returns {"error": ...} with descriptive message
# 3. Wrong type for param → returns {"error": ...} or raises TypeError
# 4. Extra unexpected params → ignored (not crash)
# 5. Return shape matches documented schema
```

**Tools to test (all 29):**
```
create_entity, add_observation, create_relationship,
search_memory, get_entity, get_neighbors, update_entity,
delete_entity, delete_relationship, delete_observation,
traverse_path, find_cross_domain_patterns,
start_session, end_session, record_breakthrough,
query_timeline, get_temporal_neighbors, point_in_time_query,
analyze_graph, graph_health, find_knowledge_gaps,
archive_entity, prune_stale, consolidate_similar,
get_bottles, search_associative, reconnect,
system_diagnostics, get_hologram
```

### 8B. Snapshot Tests

**File:** `tests/gauntlet/test_snapshots.py`

Capture the output shape of key operations and snapshot-test them:

```python
# 1. create_entity → snapshot response structure
# 2. search_memory → snapshot result list structure
# 3. graph_health → snapshot health dict structure
# 4. system_diagnostics → snapshot diagnostics structure
# 5. get_hologram → snapshot hologram structure
# 6. reconnect → snapshot briefing structure
```

Use `pytest-snapshot` or manual JSON comparison. The point is regression detection — if the response shape changes, the test fails.

### 8C. Contract Library (`deal`)

**File:** `tests/gauntlet/test_deal_contracts.py`

```python
import deal

# Contract: search_memory always returns a list
@deal.ensure(lambda result: isinstance(result, list))
@deal.ensure(lambda result: all(hasattr(r, 'score') for r in result))

# Contract: create_entity returns a dict with 'id' key
@deal.ensure(lambda result: 'id' in result or 'error' in result)

# Contract: graph_health returns dict with 'total_nodes' key
@deal.ensure(lambda result: 'total_nodes' in result)
```

### EXIT CRITERIA
- All 29 MCP tools have input/output contract tests
- Snapshot tests pass on current codebase (baseline established)
- `deal` contracts pass for all decorated functions

---

## ROUND 9: PERFORMANCE & MEMORY

**Goal:** Find slow queries, memory leaks, and scalability cliffs.

### 9A. Search Latency Gates

```python
# File: tests/gauntlet/test_performance.py
import time

def test_search_latency():
    """Search must complete in < 2 seconds."""
    start = time.monotonic()
    results = service.search_memory("test query", limit=10)
    elapsed = time.monotonic() - start
    assert elapsed < 2.0, f"Search took {elapsed:.2f}s (limit: 2.0s)"

def test_hologram_latency():
    """Hologram retrieval must complete in < 5 seconds."""
    start = time.monotonic()
    result = service.get_hologram(entity_id, depth=2)
    elapsed = time.monotonic() - start
    assert elapsed < 5.0, f"Hologram took {elapsed:.2f}s (limit: 5.0s)"

def test_graph_health_latency():
    """Graph health check must complete in < 10 seconds."""
    start = time.monotonic()
    health = service.graph_health()
    elapsed = time.monotonic() - start
    assert elapsed < 10.0, f"Health check took {elapsed:.2f}s (limit: 10.0s)"
```

### 9B. Embedding Throughput

```python
def test_embedding_batch_throughput():
    """Embedding 100 texts should complete in < 30 seconds."""
    texts = [f"Test text number {i}" for i in range(100)]
    start = time.monotonic()
    embeddings = embedding_service.embed_batch(texts)
    elapsed = time.monotonic() - start
    assert elapsed < 30.0
    assert len(embeddings) == 100
    assert all(len(e) == 1024 for e in embeddings)
```

### 9C. Memory Profiling

```python
import tracemalloc

def test_bulk_create_memory():
    """Creating 1000 entities should not leak memory."""
    tracemalloc.start()
    snapshot1 = tracemalloc.take_snapshot()

    for i in range(1000):
        service.create_entity(name=f"test_entity_{i}", entity_type="Entity")

    snapshot2 = tracemalloc.take_snapshot()
    stats = snapshot2.compare_to(snapshot1, 'lineno')

    # Top allocator should not exceed 50MB for 1000 entities
    top_stat = stats[0]
    assert top_stat.size_diff < 50 * 1024 * 1024, f"Memory grew by {top_stat.size_diff / 1024 / 1024:.1f}MB"
```

### 9D. FalkorDB Query Performance

```python
def test_cypher_query_timing():
    """Complex Cypher queries should complete in < 1 second."""
    queries = [
        "MATCH (e:Entity) RETURN count(e)",
        "MATCH (e:Entity)-[r]->(e2:Entity) RETURN count(r)",
        "MATCH (e:Entity) WHERE e.entity_type = 'Concept' RETURN e.name LIMIT 100",
        "MATCH p=(e1:Entity)-[*1..3]-(e2:Entity) WHERE e1.name = 'test' RETURN p LIMIT 10",
    ]
    for query in queries:
        start = time.monotonic()
        result = graph.query(query)
        elapsed = time.monotonic() - start
        assert elapsed < 1.0, f"Query took {elapsed:.2f}s: {query[:50]}"
```

### EXIT CRITERIA
- Search latency < 2s
- Hologram latency < 5s
- Health check latency < 10s
- Embedding throughput: 100 texts in < 30s
- No memory leaks > 50MB for 1000 entity creates
- All Cypher queries < 1s

---

## ROUND 10: ARCHITECTURE FORENSICS

**Goal:** Verify the architecture actually matches the design.

### 10A. Layer Contracts (import-linter)

**File:** `.importlinter` in project root

```ini
[importlinter]
root_packages = claude_memory

[importlinter:contract:layered-architecture]
name = Layered architecture
type = layers
layers =
    claude_memory.server
    claude_memory.tools | claude_memory.tools_extra
    claude_memory.crud | claude_memory.search | claude_memory.temporal | claude_memory.analysis
    claude_memory.repository | claude_memory.vector_store | claude_memory.embedding
containers =
    claude_memory
```

```bash
lint-imports 2>&1 | tee import_contracts.txt
```

**Assert:** No layer violations. Services don't import from server. Repository doesn't import from services.

### 10B. Dependency Graph

```bash
# Module coupling analysis
pydeps src/claude_memory/ --max-bacon=3 --cluster 2>&1 | tee dep_graph.txt

# Or simpler: just check import depth
python -c "
import ast, os
for f in sorted(os.listdir('src/claude_memory')):
    if f.endswith('.py') and not f.startswith('__'):
        with open(f'src/claude_memory/{f}') as fh:
            tree = ast.parse(fh.read())
        imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
        print(f'{f}: {len(imports)} imports')
"
```

### 10C. Circular Dependency Check

```bash
pipdeptree --warn silence 2>&1 | grep -i "circular\|conflict" | tee circular.txt
```

### 10D. Module Size Check

```bash
find src/claude_memory/ -name "*.py" -exec wc -l {} + | sort -rn | head -20
```

**Flag any module over 300 lines.** From the explore, these are close:
- `analysis.py` (343 LOC) — over threshold
- `server.py` (295 LOC) — close
- `search.py` (284 LOC) — close
- `crud.py` (271 LOC) — close
- `vector_store.py` (270 LOC) — close

### EXIT CRITERIA
- No layer violations
- No circular dependencies
- All modules ≤ 300 lines (or documented exception)
- Import depth documented

---

## ROUND 11: COMPLEXITY ARCHAEOLOGY

**Goal:** Find the functions that are too complex to test effectively.

### 11A. Full Complexity Report

```bash
# Every function, sorted by complexity
radon cc src/claude_memory/ -s -a 2>&1 | tee complexity_full.txt

# Only grade C or worse (the dangerous ones)
radon cc src/claude_memory/ -n C -s 2>&1 | tee complexity_hotspots.txt

# Maintainability index
radon mi src/claude_memory/ -s 2>&1 | tee maintainability_full.txt
```

### 11B. Cognitive Complexity (if available)

```bash
# flake8-cognitive-complexity
flake8 src/claude_memory/ --select CCR --max-cognitive-complexity 15 2>&1 | tee cognitive.txt
```

### 11C. Dead Code Sweep

```bash
vulture src/claude_memory/ --min-confidence 80 2>&1 | tee dead_code.txt
vulture src/claude_memory/ tests/ --min-confidence 60 2>&1 | tee dead_code_low.txt
```

### 11D. Exception Anti-Pattern Census

```bash
# Bare except Exception
grep -rn "except Exception" src/claude_memory/ --include="*.py" | tee bare_except.txt
wc -l bare_except.txt

# Logger.error without exc_info
grep -rn "logger\.error" src/claude_memory/ --include="*.py" | grep -v "exc_info" | tee missing_excinfo.txt
wc -l missing_excinfo.txt

# Bare except (no type at all)
grep -rn "^[[:space:]]*except:" src/claude_memory/ --include="*.py" | tee bare_except_untyped.txt
wc -l bare_except_untyped.txt
```

### EXIT CRITERIA
- All grade C+ functions documented with line numbers
- All dead code documented
- Exception anti-patterns counted and categorized
- MI scores recorded per module

---

## ROUND 12: DEPENDENCY DEEP SCAN

**Goal:** Find supply chain risks and version conflicts.

### 12A. Dependency Tree

```bash
pipdeptree 2>&1 | tee dep_tree.txt
pipdeptree --reverse 2>&1 | tee dep_reverse.txt
```

### 12B. Version Conflicts

```bash
pip check 2>&1 | tee pip_check.txt
```

### 12C. License Audit

```bash
pip-licenses --format=table 2>&1 | tee licenses.txt
pip-licenses --format=table --fail-on="GPL" 2>&1 | tee license_check.txt
```

### 12D. Outdated Dependencies

```bash
pip list --outdated --format=table 2>&1 | tee outdated.txt
```

### EXIT CRITERIA
- No version conflicts
- No GPL-only dependencies (copyleft risk)
- All CVEs documented (pip-audit)
- Outdated dependencies listed (informational, not blocking)

---

## ROUND 13: GRAPH INTEGRITY (Dragon Brain specific)

**Goal:** Validate the live FalkorDB + Qdrant data is consistent and healthy.

**IMPORTANT:** This round runs against the LIVE Docker stack. It touches REAL data. Run `validate_brain.py` first as a safety check.

### 13A. Split-Brain Check

```python
# Count entities in FalkorDB
graph_count = graph.query("MATCH (e:Entity) RETURN count(e)").result_set[0][0]

# Count vectors in Qdrant
from qdrant_client import QdrantClient
qdrant = QdrantClient(host="localhost", port=6333)
vector_count = qdrant.count("memory_embeddings").count

# Assert: deficit = 0
deficit = graph_count - vector_count
assert deficit == 0, f"Split-brain detected: {graph_count} entities, {vector_count} vectors, deficit={deficit}"
```

### 13B. Bottle Chain Integrity

```python
# Walk the PRECEDED_BY chain from latest bottle to #1
bottles = service.get_bottles(include_content=False)
assert len(bottles) >= 40, f"Expected 40+ bottles, got {len(bottles)}"

# Verify chain is unbroken
for i in range(1, len(bottles)):
    prev = bottles[i]
    curr = bottles[i-1]
    relationships = service.get_neighbors(curr['id'])
    preceded_by = [r for r in relationships if r['type'] == 'PRECEDED_BY']
    assert len(preceded_by) >= 1, f"Bottle {curr['name']} has no PRECEDED_BY link"
```

### 13C. Temporal Completeness

```python
# Every Entity should have created_at
result = graph.query("MATCH (e:Entity) WHERE e.created_at IS NULL RETURN count(e)")
null_count = result.result_set[0][0]
assert null_count == 0, f"{null_count} entities missing created_at"
```

### 13D. Observation Vectorization (E-3 check)

```python
# Every Observation should have a corresponding vector
obs_count = graph.query("MATCH (o:Observation) RETURN count(o)").result_set[0][0]
obs_vectors = qdrant.count("memory_embeddings",
    count_filter={"must": [{"key": "node_type", "match": {"value": "observation"}}]}
).count
assert obs_count == obs_vectors, f"Obs split-brain: {obs_count} obs, {obs_vectors} vectors"
```

### 13E. Infrastructure Checks

```python
# maxmemory enforcement (1GB)
import redis
r = redis.Redis(host='localhost', port=6379)
maxmem = int(r.config_get('maxmemory')['maxmemory'])
assert maxmem == 1073741824, f"maxmemory={maxmem}, expected 1GB"

# Ghost graph absence
graphs = r.execute_command('GRAPH.LIST')
assert graphs == [b'claude_memory'], f"Ghost graphs found: {graphs}"

# HNSW indexing threshold
collection_info = qdrant.get_collection("memory_embeddings")
threshold = collection_info.config.optimizer_config.indexing_threshold
assert threshold == 500, f"HNSW threshold={threshold}, expected 500"

# Expected FalkorDB indices
indices = graph.query("CALL db.indexes()").result_set
index_names = [idx[0] for idx in indices]
for expected in ['Entity', 'Observation']:
    assert any(expected in name for name in index_names), f"Missing index on {expected}"
```

### EXIT CRITERIA
- Split-brain deficit = 0
- Bottle chain unbroken (40+ bottles, all linked)
- Zero entities missing timestamps
- Observation vectors match observation count
- maxmemory = 1GB
- No ghost graphs
- HNSW threshold = 500
- All expected indices present

---

## ROUND 14: MCP TOOL CONTRACTS (Dragon Brain specific)

**Goal:** Every MCP tool works correctly with valid input AND fails gracefully with garbage.

### 14A. Happy Path — All 29 Tools

**File:** `tests/gauntlet/test_mcp_tools_happy.py`

For each tool, create a test entity/relationship first (setup), then call the tool with valid params, then assert the response shape.

```python
# Pattern for each tool:
async def test_create_entity_happy():
    result = await mcp_create_entity(name="Test", entity_type="Concept",
                                      observations=["A test entity"])
    assert "id" in result
    assert result["name"] == "Test"
    assert result["entity_type"] == "Concept"

async def test_search_memory_happy():
    result = await mcp_search_memory(query="test", limit=5)
    assert isinstance(result, list)
    assert len(result) <= 5
    for r in result:
        assert "name" in r
        assert "score" in r

# ... repeat for all 29 tools
```

### 14B. Sad Path — All 29 Tools

```python
# Pattern for each tool:
async def test_create_entity_empty_name():
    result = await mcp_create_entity(name="", entity_type="Concept")
    assert "error" in result

async def test_create_entity_invalid_type():
    result = await mcp_create_entity(name="Test", entity_type="InvalidType")
    # Either succeeds (custom types allowed) or returns clean error

async def test_search_memory_empty_query():
    result = await mcp_search_memory(query="")
    # Either returns empty results or fallback results — never crash

# ... repeat for all 29 tools with invalid/edge-case inputs
```

### 14C. Strategy Routing

```python
# All 4 search strategies must work
for strategy in ["semantic", "associative", "temporal", "relational", "auto"]:
    result = await mcp_search_memory(query="test query", strategy=strategy)
    assert isinstance(result, list), f"Strategy {strategy} failed"
```

### EXIT CRITERIA
- All 29 tools pass happy path tests
- All 29 tools return clean errors on invalid input (no crashes)
- All 5 search strategies return valid results
- Response shapes match documented schemas

---

## ROUND 15: CONCURRENT OPERATIONS (Dragon Brain specific)

**Goal:** Stress-test the locking system and concurrent access patterns.

### 15A. Lock Manager Stress Test

```python
import threading
import time

def test_concurrent_lock_acquisition():
    """50 threads competing for the same lock."""
    lock_manager = LockManager()
    results = []

    def acquire_and_work(thread_id):
        acquired = lock_manager.acquire("test_lock", timeout=10)
        if acquired:
            results.append(thread_id)
            time.sleep(0.01)  # simulate work
            lock_manager.release("test_lock")

    threads = [threading.Thread(target=acquire_and_work, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    # All 50 threads should eventually acquire the lock
    assert len(results) == 50, f"Only {len(results)}/50 threads completed"
```

### 15B. Concurrent Entity Creates

```python
def test_concurrent_entity_creates():
    """50 threads creating entities simultaneously — no duplicates, no crashes."""
    results = []
    errors = []

    def create_entity(i):
        try:
            result = service.create_entity(
                name=f"concurrent_test_{i}",
                entity_type="Entity",
                observations=[f"Created by thread {i}"]
            )
            results.append(result)
        except Exception as e:
            errors.append((i, str(e)))

    threads = [threading.Thread(target=create_entity, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert len(errors) == 0, f"Errors: {errors}"
    assert len(results) == 50
    # Verify no duplicates
    ids = [r['id'] for r in results]
    assert len(set(ids)) == 50, f"Duplicate IDs found"
```

### 15C. Read-Write Consistency

```python
def test_write_then_read_consistency():
    """Write entity, immediately search — must find it."""
    entity = service.create_entity(
        name="consistency_test_unique_name_xyz",
        entity_type="Entity",
        observations=["This should be immediately searchable"]
    )

    # Immediate search
    results = service.search_memory("consistency_test_unique_name_xyz")
    found = any(r['name'] == "consistency_test_unique_name_xyz" for r in results)
    assert found, "Entity not found immediately after creation"
```

### 15D. Lock Fallback (Redis → File)

```python
def test_lock_fallback_to_file():
    """When Redis is unavailable, file-based locking should work."""
    # This test requires temporarily stopping Redis
    # or configuring lock_manager with an unreachable Redis
    lock_manager = LockManager(redis_url="redis://nonexistent:9999")

    acquired = lock_manager.acquire("fallback_test", timeout=5)
    assert acquired, "File-based fallback lock should succeed"
    lock_manager.release("fallback_test")
```

### EXIT CRITERIA
- 50 concurrent lock acquisitions: all complete, no deadlocks
- 50 concurrent entity creates: all succeed, no duplicates
- Write-then-read consistency: immediate find
- Lock fallback: file-based works when Redis unavailable

---

## ROUND 16: EMBEDDING PIPELINE (Dragon Brain specific)

**Goal:** Validate the full embedding lifecycle: generate → store → search → retrieve.

### 16A. Round-Trip Verification

```python
def test_embedding_round_trip():
    """Create entity → embedding stored → search finds it → embedding matches."""
    # Create
    entity = service.create_entity(
        name="embedding_roundtrip_test",
        entity_type="Concept",
        observations=["The Riemann hypothesis concerns the distribution of prime numbers"]
    )

    # Search with semantically similar query
    results = service.search_memory("prime number distribution")
    found = any(r['name'] == "embedding_roundtrip_test" for r in results)
    assert found, "Semantic search should find the entity"

    # Verify embedding dimensions
    from qdrant_client import QdrantClient
    qdrant = QdrantClient(host="localhost", port=6333)
    points = qdrant.scroll("memory_embeddings",
        scroll_filter={"must": [{"key": "entity_id", "match": {"value": entity['id']}}]},
        limit=1
    )
    assert len(points[0]) == 1
    assert len(points[0][0].vector) == 1024, f"Expected 1024-dim, got {len(points[0][0].vector)}"
```

### 16B. Embedding Service Health

```python
def test_embedding_service_health():
    """Embedding service responds to health check."""
    import httpx
    response = httpx.get("http://localhost:8001/health")
    assert response.status_code == 200

def test_embedding_generation():
    """Single text → embedding of correct dimension."""
    embedding = embedding_service.generate(["test text"])
    assert len(embedding) == 1
    assert len(embedding[0]) == 1024
    assert all(isinstance(x, float) for x in embedding[0])
```

### 16C. Embedding Error Recovery

```python
def test_embedding_service_down():
    """When embedding service is down, search degrades gracefully."""
    # Stop embedding container
    # service.search_memory("test") should return graph-only results or clean error
    # NOT crash or hang
```

### 16D. Observation Embedding (E-3)

```python
def test_observation_auto_embedded():
    """Adding an observation auto-generates and stores its embedding."""
    entity = service.create_entity(name="obs_embed_test", entity_type="Entity")
    service.add_observation(entity['id'], "This observation should be auto-embedded")

    # Check Qdrant for observation vector
    from qdrant_client import QdrantClient
    qdrant = QdrantClient(host="localhost", port=6333)
    points = qdrant.scroll("memory_embeddings",
        scroll_filter={"must": [
            {"key": "node_type", "match": {"value": "observation"}},
            {"key": "parent_entity_id", "match": {"value": entity['id']}}
        ]},
        limit=10
    )
    assert len(points[0]) >= 1, "Observation vector not found in Qdrant"
```

### EXIT CRITERIA
- Round-trip: create → search → find works
- Embedding dimension: 1024 for all generated vectors
- Service health: 200 response
- Error recovery: graceful degradation when service down
- Observation auto-embedding: E-3 feature verified

---

## ROUND 17: TEMPORAL CONSISTENCY (Dragon Brain specific)

**Goal:** Validate time-based operations and the temporal graph.

### 17A. Point-in-Time Query

```python
import datetime

def test_point_in_time_query():
    """Entities created at different times, point-in-time returns correct slice."""
    t1 = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
    t2 = datetime.datetime(2026, 2, 1, tzinfo=datetime.timezone.utc)

    e1 = service.create_entity(name="temporal_test_jan", entity_type="Entity",
                                created_at=t1.isoformat())
    e2 = service.create_entity(name="temporal_test_feb", entity_type="Entity",
                                created_at=t2.isoformat())

    # Query as of Jan 15 — should see e1, not e2
    results = service.point_in_time_query(as_of="2026-01-15T00:00:00Z")
    names = [r['name'] for r in results]
    assert "temporal_test_jan" in names
    assert "temporal_test_feb" not in names
```

### 17B. Timeline Ordering

```python
def test_timeline_ordering():
    """query_timeline returns chronologically ordered results."""
    results = service.query_timeline(entity_type="Entity", limit=50)
    timestamps = [r.get('created_at') or r.get('occurred_at') for r in results]
    timestamps = [t for t in timestamps if t is not None]
    assert timestamps == sorted(timestamps), "Timeline not chronologically ordered"
```

### 17C. PRECEDED_BY Chain

```python
def test_preceded_by_chain():
    """Create 5 sequential entities with PRECEDED_BY, walk the chain."""
    entities = []
    for i in range(5):
        e = service.create_entity(name=f"chain_test_{i}", entity_type="Entity")
        if i > 0:
            service.create_relationship(
                source_id=e['id'],
                target_id=entities[-1]['id'],
                relationship_type="PRECEDED_BY"
            )
        entities.append(e)

    # Walk chain from last to first
    current = entities[-1]
    chain = [current]
    for _ in range(10):  # safety limit
        neighbors = service.get_neighbors(current['id'])
        preceded = [n for n in neighbors if n.get('relationship_type') == 'PRECEDED_BY']
        if not preceded:
            break
        current = preceded[0]
        chain.append(current)

    assert len(chain) == 5, f"Chain length {len(chain)}, expected 5"
```

### 17D. Session Tracking

```python
def test_session_lifecycle():
    """start_session → do work → end_session → session is recorded."""
    session = service.start_session(session_type="test")
    assert session is not None

    # Do some work
    service.create_entity(name="session_work_test", entity_type="Entity")

    # End session
    result = service.end_session()
    assert result is not None
    # Session should be queryable via timeline
```

### EXIT CRITERIA
- Point-in-time queries return correct time slices
- Timeline is chronologically ordered
- PRECEDED_BY chains are walkable with no breaks
- Session lifecycle (start → work → end) works correctly

---

## ROUND 18: LIVE BRAIN VALIDATION (Dragon Brain specific)

**Goal:** Run the production validation script against the live brain.

### 18A. validate_brain.py

```bash
python scripts/validate_brain.py
```

**Expected output:** All 9 checks PASS:
1. Split-brain count: deficit = 0
2. Bottle chain integrity: complete
3. Temporal completeness: zero NULL timestamps
4. Observation vectorization: obs count = obs vector count
5. maxmemory enforcement: 1GB
6. Ghost graph absence: only `claude_memory`
7. Orphan vector purge: count = 0
8. Index verification: Entity(id), Entity(name), Observation(created_at)
9. HNSW threshold: 500

### 18B. E2E Functional Suite

```bash
python tests/e2e_functional.py
```

**Expected:** All 31 phases pass.

### 18C. MCP Smoke Test (manual, if Claude Code session available)

```
1. get_bottles()                    → Confirms graph + temporal pipeline
2. search_memory("test query")      → Confirms embed → vector → graph pipeline
3. graph_health()                   → Confirms analysis pipeline
4. system_diagnostics()             → Confirms all backend health checks
5. reconnect()                      → Confirms composed session briefing
```

### EXIT CRITERIA
- validate_brain.py: all 9 checks PASS
- E2E: all 31 phases PASS
- MCP smoke test: all 5 tools return valid results (if session available)

---

## ROUND 19: REGRESSION BATTERY

**Goal:** Run everything one more time to catch any test pollution from gauntlet rounds.

### 19A. Full Gold Stack

```bash
tox -e pulse,gate,forge,hammer,polish
```

### 19B. Coverage Delta

```bash
coverage run -m pytest tests/ --tb=short
coverage report --show-missing --sort=cover | tee coverage_final.txt

# Compare to baseline from Round 1
diff coverage_baseline.txt coverage_final.txt
```

**Assert:** Coverage has not decreased. Test count has not decreased. No new failures.

### 19C. Gauntlet Test Suite

```bash
# Run all gauntlet tests
pytest tests/gauntlet/ -v --tb=short
```

### EXIT CRITERIA
- All 5 tox tiers pass
- Coverage ≥ baseline from Round 1
- Test count ≥ baseline from Round 1
- All gauntlet tests pass
- No regressions from earlier rounds

---

## ROUND 20: FINAL VERDICT

**Goal:** Produce the final report.

### 20A. GAUNTLET_RESULTS.md

Create `GAUNTLET_RESULTS.md` in the project root with:

```markdown
# Dragon Brain Gauntlet Results
**Date:** [date]
**Runner:** Claude
**Rounds completed:** [X]/20

## Per-Round Results
| Round | Name | Status | Key Findings |
|-------|------|--------|-------------|
| 1 | Iron Baseline | PASS/FAIL | [details] |
| 2 | Stress Test | PASS/FAIL | [details] |
| ... | | | |

## Metrics Summary
| Metric | Baseline (R1) | Final (R19) | Delta |
|--------|---------------|-------------|-------|
| Test count | | | |
| Coverage | | | |
| Mutation kill rate | | | |
| Complexity (avg CC) | | | |
| Dead code items | | | |
| Exception anti-patterns | | | |
| Security issues | | | |

## Confirmed Bugs
| # | Severity | Component | Description |
|---|----------|-----------|-------------|
| | | | |

## Architectural Concerns
[List any structural issues found]

## Recommendations
[Prioritized action items]
```

### 20B. Health Score

Calculate an overall health score:

| Category | Weight | Score (0-100) | Weighted |
|----------|--------|---------------|----------|
| Test pass rate | 20% | | |
| Coverage | 15% | | |
| Mutation kill rate | 20% | | |
| Security | 15% | | |
| Architecture | 10% | | |
| Performance | 10% | | |
| Data integrity | 10% | | |
| **Total** | **100%** | | |

### EXIT CRITERIA
- GAUNTLET_RESULTS.md produced
- Health score calculated
- All findings prioritized
- Recommendations documented

---

## APPENDIX A: MODULE INVENTORY

| Module | LOC | Category | Test File(s) |
|--------|-----|----------|-------------|
| `server.py` | 295 | Infrastructure | `test_server.py` |
| `tools.py` | 82 | Service Facade | `test_memory_service.py` |
| `tools_extra.py` | 184 | MCP Tools | `test_server.py` |
| `crud.py` | 271 | Business Logic | `test_memory_service.py`, `test_edge_cases.py` |
| `crud_maintenance.py` | 96 | Business Logic | `test_memory_service.py` |
| `search.py` | 284 | Business Logic | `test_memory_service.py`, `test_search_associative.py` |
| `search_advanced.py` | 174 | Business Logic | `test_search_associative.py` |
| `temporal.py` | 161 | Business Logic | `test_memory_service.py`, `test_temporal.py` |
| `repository.py` | 178 | Data Access | `test_repository.py` |
| `repository_queries.py` | 251 | Data Access | `test_repository.py` |
| `repository_traversal.py` | 192 | Data Access | `test_repository.py`, `test_graph_traversal.py` |
| `vector_store.py` | 270 | Data Access | `test_vector_store.py` |
| `embedding.py` | 111 | ML/Analytics | `test_embedding_coverage.py` |
| `embedding_server.py` | 79 | ML/Analytics | — |
| `clustering.py` | 248 | ML/Analytics | `test_clustering.py` |
| `activation.py` | 216 | ML/Analytics | `test_search_associative.py`, `test_activation.py` |
| `analysis.py` | 343 | Infrastructure | `test_analysis.py` |
| `router.py` | 205 | Infrastructure | `test_router.py` |
| `lock_manager.py` | 201 | Infrastructure | `test_lock_manager.py`, `test_lock_fallback.py` |
| `retry.py` | 115 | Infrastructure | `test_retry.py` |
| `graph_algorithms.py` | 121 | ML/Analytics | — |
| `logging_config.py` | 57 | Infrastructure | `test_logging.py` |
| `context_manager.py` | 114 | Infrastructure | `test_context.py` |
| `ontology.py` | 118 | Infrastructure | `test_ontology.py` |
| `schema.py` | 217 | Data Access | `test_schema.py`, `test_validation.py` |
| `interfaces.py` | 57 | Data Access | `test_interfaces.py` |
| `librarian.py` | 145 | Infrastructure | `test_librarian.py` |
| `dashboard/app.py` | 212 | UI | `test_dashboard_app.py` |

**Untested modules** (no dedicated test file):
- `embedding_server.py` (79 LOC) — standalone microservice, test via HTTP
- `graph_algorithms.py` (121 LOC) — NetworkX wrappers, test via integration

---

## APPENDIX B: DOCKER SERVICES

| Service | Image | Port | Health Check |
|---------|-------|------|-------------|
| graphdb | `falkordb/falkordb:v4.14.11` | 6379, 3000 | `redis-cli ping` |
| qdrant | `qdrant/qdrant:v1.16.3` | 6333 | TCP check |
| embeddings | Custom (BGE-M3 + GPU) | 8001 | `curl :8000/health` |
| dashboard | Custom (Streamlit) | 8501 | `curl :8501/_stcore/health` |

---

## APPENDIX C: EXISTING TOX TIERS

| Tier | Tools | Gate |
|------|-------|------|
| pulse | ruff, mypy strict, pytest + coverage | 90% branch |
| gate | Hypothesis CI, diff-cover | 100% on changed lines |
| forge | mutatest, 10-seed campaign | kill rate threshold |
| hammer | bandit, pip-audit, detect-secrets | 0 issues |
| polish | docstr-coverage, codespell | 80% docstr |

The gauntlet adds a `[testenv:gauntlet]` tier for Rounds 3-5, 8, 9, 14-17 tests.

---

*Generated by Claude (Architect) for the project maintainer — Dragon Brain Gauntlet, February 2026*
*Adapted from JULES_TESTING_GAUNTLET.md (Tesseract V2 variant)*
*Runner: Claude (local execution, Docker access, no Jules dependency)*
