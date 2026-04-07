# Memory Model — AVM Autonomous Workflow Engineer

## Purpose

AWE needs persistent memory to make informed decisions across sessions. Without memory, every repair loop starts from zero — the system can't learn from past incidents, can't recognize recurring patterns, and can't improve its confidence scores over time.

## Memory Categories

### 1. Workflow Memory

**What it stores:** The intent, business rules, and integration details behind each workflow.

| Field | Type | Example |
|---|---|---|
| `workflow_id` | string | `"mrzwNb9Eul9Lq2uM"` |
| `name` | string | `"ADS-01 Strategy Engine"` |
| `department` | string | `"ads"` |
| `business_purpose` | string | `"Generate weekly ad campaign strategies based on performance data"` |
| `owner_agent` | string | `"growth_paid"` |
| `integrations` | list | `["Airtable", "OpenRouter", "Google Ads API"]` |
| `credentials` | list | `["airtable-marketing", "openrouter-api", "google-ads-oauth"]` |
| `risk_level` | string | `"medium"` |
| `safety_caps` | dict | `{"daily_zar": 2000, "weekly_zar": 10000}` |
| `deploy_script` | string | `"tools/deploy_ads_dept.py"` |
| `spec_file` | string | `"autonomous/memory/specs/ads-01-strategy.md"` |
| `created_at` | datetime | `"2026-04-02T10:00:00Z"` |
| `last_modified` | datetime | `"2026-04-04T14:30:00Z"` |
| `health_score` | float | `85.0` |

**Storage:** `autonomous/memory/workflows/` — one JSON file per workflow.

**When written:** On workflow creation, after every deployment, after health score update.

**When read:** Before any operation on a workflow (repair, optimize, update, revamp).

---

### 2. Incident Memory

**What it stores:** Past failures, their root causes, what fixed them, and what didn't.

| Field | Type | Example |
|---|---|---|
| `incident_id` | string | `"INC-2026-04-07-001"` |
| `workflow_id` | string | `"cfDyiFLx0X89s3VL"` |
| `workflow_name` | string | `"ADS-05 Optimizer"` |
| `severity` | string | `"P2"` |
| `detected_at` | datetime | `"2026-04-07T08:15:00Z"` |
| `resolved_at` | datetime | `"2026-04-07T08:42:00Z"` |
| `error_type` | string | `"node_execution_error"` |
| `error_message` | string | `"Code doesn't return items properly"` |
| `root_cause` | string | `"Missing numberOfOutputs parameter on Code node with multiple outputs"` |
| `fix_applied` | string | `"Added numberOfOutputs: 2 to Parse Optimizations node parameters"` |
| `fix_confidence` | float | `95.0` |
| `fix_success` | bool | `true` |
| `failed_fixes` | list | `[]` |
| `resolution_time_min` | int | `27` |
| `affected_downstream` | list | `["ADS-08 Reporting"]` |
| `tags` | list | `["n8n-code-node", "multi-output", "parameter-missing"]` |

**Storage:** `autonomous/memory/incidents/` — one JSON file per incident, indexed by `incidents_index.json`.

**When written:** After every incident resolution (successful or escalated).

**When read:** During debugger diagnosis (search for matching error patterns), during revamp assessment (incident frequency).

---

### 3. Pattern Memory

**What it stores:** Proven approaches and anti-patterns discovered through operations.

| Field | Type | Example |
|---|---|---|
| `pattern_id` | string | `"PAT-001"` |
| `name` | string | `"n8n Code Node Multi-Output"` |
| `type` | string | `"gotcha"` (or `"best-practice"`, `"anti-pattern"`, `"workaround"`) |
| `description` | string | `"Code nodes with N>1 output branches MUST set numberOfOutputs: N in parameters"` |
| `applies_to` | list | `["n8n-code-node", "multi-output"]` |
| `discovered_from` | string | `"INC-2026-04-04-003"` |
| `confidence` | float | `100.0` |
| `times_applied` | int | `4` |
| `last_applied` | datetime | `"2026-04-07T08:42:00Z"` |
| `verified` | bool | `true` |

**Storage:** `autonomous/memory/patterns/` — one JSON file per pattern, indexed by `patterns_index.json`.

**Seeded from:** Existing knowledge in CLAUDE.md memory files (`n8n-common-issues.md`, `feedback-n8n-node-issues.md`, `patterns.md`, `n8n-node-reference.md`).

**When written:** After a new failure type is resolved, after a best practice is validated in production.

**When read:** During building (check patterns before generating workflow), during debugging (match error against known patterns), during validation (check for anti-patterns).

---

### 4. Decision Log

**What it stores:** Every significant decision AWE makes, with rationale and outcome.

| Field | Type | Example |
|---|---|---|
| `decision_id` | string | `"DEC-2026-04-07-001"` |
| `timestamp` | datetime | `"2026-04-07T09:00:00Z"` |
| `context` | string | `"ADS-05 failing with Code node error"` |
| `decision` | string | `"Auto-fix: add numberOfOutputs parameter"` |
| `alternatives` | list | `["Rebuild node from scratch", "Escalate to Ian"]` |
| `rationale` | string | `"Known pattern PAT-001, confidence 95%, P2 severity allows auto-fix"` |
| `risk_level` | string | `"low"` |
| `outcome` | string | `"success"` |
| `confidence_before` | float | `95.0` |
| `confidence_after` | float | `100.0` |

**Storage:** `autonomous/memory/decisions/` — append-only JSON log, rotated monthly.

**When written:** Before every autonomous action.

**When read:** During audits, during confidence calibration (compare predicted vs actual outcomes).

---

### 5. Test History

**What it stores:** Test results across all workflows over time.

| Field | Type | Example |
|---|---|---|
| `test_run_id` | string | `"TEST-2026-04-07-001"` |
| `workflow_id` | string | `"mrzwNb9Eul9Lq2uM"` |
| `trigger` | string | `"pre-deploy"` (or `"regression"`, `"post-fix"`, `"scheduled"`) |
| `test_count` | int | `12` |
| `passed` | int | `11` |
| `failed` | int | `1` |
| `coverage_score` | float | `83.0` |
| `failed_tests` | list | `[{"test_id": "TC-003", "reason": "API timeout"}]` |
| `duration_sec` | float | `45.2` |
| `timestamp` | datetime | `"2026-04-07T09:30:00Z"` |

**Storage:** `autonomous/memory/test_history/` — one JSON per test run, indexed by `test_index.json`.

**When written:** After every test execution.

**When read:** During deploy readiness checks, during revamp assessment (test reliability trends).

---

## Storage Strategy

### Primary: Local JSON Files

All memory is stored as JSON files in `autonomous/memory/`. This is chosen over Airtable or Supabase for the AWE memory because:

| Consideration | Local JSON | Airtable | Supabase |
|---|---|---|---|
| **Latency** | Instant (filesystem) | 200-500ms per API call | 100-300ms per query |
| **Cost** | Free | Counts against API limits | Free tier sufficient |
| **Git trackable** | Yes — full audit trail | No | No |
| **Claude Code access** | Direct file read/write | MCP tool call | MCP tool call |
| **Offline access** | Yes | No | No |
| **Schema flexibility** | Full | Limited by field types | Requires migrations |

**Trade-off accepted:** Local JSON doesn't support concurrent access or complex queries. This is acceptable because AWE runs as a single Claude Code session, and searches are done with simple file reads + index lookups.

### Index Files

Each memory category has an `*_index.json` that maps IDs to file paths and key metadata for fast lookup without reading every file:

```json
// autonomous/memory/incidents/incidents_index.json
{
  "INC-2026-04-07-001": {
    "file": "inc_2026_04_07_001.json",
    "workflow_id": "cfDyiFLx0X89s3VL",
    "severity": "P2",
    "error_type": "node_execution_error",
    "tags": ["n8n-code-node", "multi-output"],
    "resolved": true
  }
}
```

### Directory Structure

```
autonomous/memory/
├── workflows/
│   ├── ads-01-strategy.json
│   ├── ads-02-copy-generator.json
│   ├── ...
│   └── workflows_index.json
│
├── incidents/
│   ├── inc_2026_04_07_001.json
│   ├── ...
│   └── incidents_index.json
│
├── patterns/
│   ├── pat_001_code_node_multi_output.json
│   ├── pat_002_airtable_v2_matching_columns.json
│   ├── ...
│   └── patterns_index.json
│
├── decisions/
│   ├── decisions_2026_04.json  (monthly append-only log)
│   └── decisions_index.json
│
├── test_history/
│   ├── test_2026_04_07_001.json
│   ├── ...
│   └── test_index.json
│
└── specs/
    ├── ads-01-strategy-spec.md
    ├── ...
    └── specs_index.json
```

---

## Query Patterns

### "Find incidents similar to this error"

```python
# Pseudocode — implemented in autonomous/engine.py
def find_similar_incidents(error_type: str, tags: list[str]) -> list[dict]:
    index = load_json("autonomous/memory/incidents/incidents_index.json")
    matches = []
    for inc_id, meta in index.items():
        if meta["error_type"] == error_type:
            matches.append(meta)
        elif set(tags) & set(meta.get("tags", [])):
            matches.append(meta)
    return sorted(matches, key=lambda x: x.get("resolved", False), reverse=True)
```

### "What patterns apply to this node type?"

```python
def find_patterns(node_type: str) -> list[dict]:
    index = load_json("autonomous/memory/patterns/patterns_index.json")
    return [p for p in index.values() if node_type in p.get("applies_to", [])]
```

### "Is this workflow healthy enough to skip repair?"

```python
def assess_workflow_health(workflow_id: str) -> dict:
    wf = load_json(f"autonomous/memory/workflows/{workflow_id}.json")
    recent_incidents = count_recent_incidents(workflow_id, days=30)
    test_history = get_recent_test_results(workflow_id, count=5)
    return {
        "health_score": wf.get("health_score", 0),
        "incidents_30d": recent_incidents,
        "test_pass_rate": avg([t["passed"] / t["test_count"] for t in test_history]),
        "recommendation": "healthy" if recent_incidents < 3 and wf["health_score"] > 70 else "needs_attention"
    }
```

---

## Seeding from Existing Knowledge

AWE memory should be seeded from these existing sources on first initialization:

| Source | Seeds | Target Memory |
|---|---|---|
| CLAUDE.md `n8n Node Rules` section | 13+ node-specific gotchas | Pattern memory |
| `~/.claude/projects/.../n8n-common-issues.md` | Common workflow issues | Pattern memory |
| `~/.claude/projects/.../patterns.md` | Deploy/fix script patterns | Pattern memory |
| `~/.claude/projects/.../n8n-node-reference.md` | Node internals | Pattern memory |
| `tools/agent_registry.py` AGENTS dict | Workflow-to-agent mapping | Workflow memory |
| Deployed workflow IDs (from MEMORY.md) | Workflow inventory | Workflow memory |
| `config.json` department sections | Integration details, schedules | Workflow memory |

**Seeding script:** `autonomous/scripts/seed_memory.py` (to be created in Session 5).

---

## Retention and Cleanup

| Memory Type | Retention | Cleanup Rule |
|---|---|---|
| Workflow memory | Permanent | Remove when workflow deleted |
| Incidents | 6 months detailed, summary permanent | Archive to `incidents/archive/` after 6 months |
| Patterns | Permanent | Remove only if proven incorrect (confidence drops to 0) |
| Decision log | 3 months detailed, summary permanent | Rotate monthly, archive old months |
| Test history | 3 months detailed, trends permanent | Aggregate into monthly summaries |
| Specs | Permanent | Archive when workflow replaced |

### Cleanup trigger

Run cleanup monthly (or when `autonomous/memory/` exceeds 50MB):
1. Archive incidents older than 6 months (keep index entry with `archived: true`)
2. Aggregate test history into monthly summaries
3. Rotate decision logs
4. Remove orphaned records (workflow deleted but memory remains)

---

## Relationship to Existing Memory Systems

AWE memory is **separate from** but **complementary to**:

| System | Purpose | AWE Relationship |
|---|---|---|
| Claude Code auto-memory (`~/.claude/projects/.../memory/`) | Cross-session user preferences, project context | AWE reads for context, does NOT write here |
| Airtable tables (KPI_Snapshots, Events, etc.) | Live operational state for n8n workflows | AWE reads via `orchestrator_kpi_engine.py`, writes incident records |
| Supabase (agent_status, orchestrator_alerts) | Portal-facing data | AWE reads for health checks, does NOT write directly |
| Git history | Code change audit trail | AWE relies on for deploy script versioning and rollback |

AWE memory stores **operational intelligence** — the patterns, decisions, and outcomes that make the system smarter over time. The other systems store **live state** and **user context**.
