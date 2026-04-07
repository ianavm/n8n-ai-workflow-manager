# Prompt Registry — AVM Autonomous Workflow Engineer

## Agent Prompts

| # | Agent | File | Purpose | Triggered By | Output |
|---|---|---|---|---|---|
| 1 | Planner | `autonomous/prompts/planner.md` | Decompose business request into workflow spec draft | New workflow request | Draft spec YAML |
| 2 | Researcher | `autonomous/prompts/researcher.md` | Search for reusable patterns in workflow libraries | Planner (post-draft) | Reuse report YAML |
| 3 | Spec Writer | `autonomous/prompts/spec_writer.md` | Formalize draft into complete workflow spec | Planner + Researcher output | Final spec (WORKFLOW_SPEC_TEMPLATE) |
| 4 | Builder | `autonomous/prompts/builder.md` | Generate n8n workflow JSON and deploy script | Final spec | Deploy script + JSON |
| 5 | Validator | `autonomous/prompts/validator.md` | Check workflow against spec and policies | Builder output | Validation report YAML |
| 6 | Tester | `autonomous/prompts/tester.md` | Generate and execute test cases | Validated workflow | Test results YAML |
| 7 | Debugger | `autonomous/prompts/debugger.md` | Diagnose failures, propose/apply fixes | Incident Responder routing | Diagnosis + fix YAML |
| 8 | Optimizer | `autonomous/prompts/optimizer.md` | Analyze performance, propose improvements | Monitoring Analyst trigger | Optimization report YAML |
| 9 | Revamp Agent | `autonomous/prompts/revamp_agent.md` | Assess workflow health, decide rebuild vs patch | Monitoring Analyst trigger | Revamp assessment YAML |
| 10 | Deployer | `autonomous/prompts/deployer.md` | Manage build → deploy → activate lifecycle | Tester pass | Deployment result YAML |
| 11 | Rollback Agent | `autonomous/prompts/rollback_agent.md` | Revert to previous working state | Post-deploy failure or error spike | Rollback result YAML |
| 12 | Documentation Agent | `autonomous/prompts/documentation_agent.md` | Generate/update SOPs and changelogs | Post-deploy, post-fix, post-revamp | Updated markdown files |
| 13 | Incident Responder | `autonomous/prompts/incident_responder.md` | Triage production issues, classify severity | Monitoring Analyst anomaly detection | Incident response YAML |
| 14 | Monitoring Analyst | `autonomous/prompts/monitoring_analyst.md` | Interpret KPI data, detect anomalies | Scheduled cycle or manual trigger | Health report YAML |

## Prompt Structure Standard

Every agent prompt follows this structure:

1. **Role** — 1 sentence describing the agent's identity
2. **Mission** — what success looks like
3. **Allowed Actions** — explicit list of what the agent can do
4. **Disallowed Actions** — explicit list of what the agent must NOT do
5. **Input Format** — YAML schema of expected input
6. **Reasoning Priorities** — ordered list of how to think
7. **Output Format** — YAML schema of expected output
8. **Success Checks** — checklist to verify output quality
9. **Escalation Rules** — when to stop and ask for help
10. **Next Step** — which agent/module receives the output

## Version Tracking

| Field | Value |
|---|---|
| Current version | 1.0 (initial creation) |
| Version scheme | Major.Minor (major = structural change, minor = content refinement) |
| Change log location | Git history on `autonomous/prompts/` directory |

## Prompt Update Policy

| Trigger | Action |
|---|---|
| Agent produces incorrect output 3+ times | Review and update prompt reasoning priorities |
| New n8n node pattern discovered | Update Builder and Validator prompts |
| New policy created or modified | Update all prompts that reference policies |
| False positive rate > 10% on any agent | Review and refine success checks |
| Escalation rate > 30% on any agent | Review confidence thresholds and reasoning |

### Update Process

1. Identify which prompt needs updating (from incident data or performance metrics)
2. Draft updated prompt
3. Compare old vs new on 3 historical cases (does it produce better output?)
4. If improved: commit update, increment minor version
5. If structural change (sections added/removed): increment major version
6. Update this registry with change date

## Prompt Loading in Engine

The orchestration engine (`autonomous/engine.py`) loads prompts by reading the markdown file and extracting the content. The YAML input/output schemas define the interface contract between modules.

```python
# Pseudocode — how engine loads and uses prompts
def load_prompt(agent_name: str) -> str:
    path = f"autonomous/prompts/{agent_name}.md"
    return Path(path).read_text()

def execute_stage(agent_name: str, input_data: dict) -> dict:
    prompt = load_prompt(agent_name)
    # Claude Code uses this prompt as context for the current stage
    # Input data is formatted per the prompt's Input Format
    # Output is validated against the prompt's Output Format
    return stage_output
```
