"""AWE CLI — Command-line interface for the Autonomous Workflow Engineer.

Usage:
    python -m autonomous status       Health dashboard + recent decisions
    python -m autonomous monitor      Run detection only (no fixes)
    python -m autonomous repair       Full repair loop at current tier
    python -m autonomous audit        Show decision log + escalation queue
    python -m autonomous patterns     List patterns with success rates
    python -m autonomous seed         Run pattern seeding
    python -m autonomous tier [N]     Show/set current autonomy tier
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _get_engine():
    """Lazy-import and create the engine to avoid heavy imports on --help."""
    from autonomous.engine import AutonomousEngine
    return AutonomousEngine()


def cmd_status(args: argparse.Namespace) -> int:
    """Show system health dashboard."""
    engine = _get_engine()
    status = engine.run_status()
    dashboard = status["dashboard"]
    stats = dashboard["overall_stats"]

    print(f"\n{'=' * 60}")
    print(f"  AWE STATUS — Tier {status['autonomy_tier']} ({status['tier_name']})")
    if status["emergency_stopped"]:
        print("  !! EMERGENCY STOP ACTIVE !!")
    print(f"{'=' * 60}")

    # Health
    health = dashboard["health_status"].upper()
    print(f"\n  System Health:  {health}")
    print(f"  Workflows:      {dashboard['active_workflows']} active / {dashboard['total_workflows']} total")
    print(f"  Executions:     {stats['total']} (last 24h)")
    print(f"  Success Rate:   {stats['success_rate']}%")
    print(f"  Avg Duration:   {stats.get('avg_duration_seconds', 0):.1f}s")

    # Failing workflows
    failing = dashboard.get("failing_workflows", [])
    if failing:
        print(f"\n  Failing Workflows ({len(failing)}):")
        for wf in failing[:10]:
            print(f"    [{wf['error_rate']}% err] {wf['workflow_name']} ({wf['errors']}/{wf['total_executions']})")

    # Stale workflows
    stale = dashboard.get("stale_workflows", [])
    if stale:
        print(f"\n  Stale Workflows ({len(stale)}):")
        for wf in stale[:5]:
            print(f"    {wf['workflow_name']}")

    # Recent decisions
    decisions = status.get("recent_decisions", [])
    if decisions:
        print(f"\n  Recent Decisions ({len(decisions)}, last 24h):")
        for dec in decisions[:5]:
            print(f"    [{dec.get('Outcome', '?')}] {dec.get('Workflow_ID', '?')[:12]}.. "
                  f"conf={dec.get('Confidence_Score', 0):.2f} {dec.get('Classification', '')}")

    # Pattern stats summary
    pattern_stats = status.get("pattern_stats", {})
    if pattern_stats:
        print(f"\n  Registered Patterns: {len(pattern_stats)}")

    print()
    return 0


def cmd_monitor(args: argparse.Namespace) -> int:
    """Run detection only — no fixes applied."""
    engine = _get_engine()
    print(f"\n  AWE MONITOR — Tier {engine.current_tier} ({engine.tier_name})")
    print(f"  Running detection scan...\n")

    issues = engine.detect()

    if not issues:
        print("  No issues detected. All workflows healthy.")
        return 0

    print(f"  Detected {len(issues)} issue(s):\n")
    for i, issue in enumerate(issues, 1):
        print(f"  {i}. [{issue.severity}] {issue.workflow_name}")
        print(f"     Errors: {issue.error_count} | Node: {issue.node_name or 'unknown'}")
        print(f"     Error: {issue.error_message[:120]}")
        print()

    return 0


def cmd_repair(args: argparse.Namespace) -> int:
    """Run full repair loop at current tier."""
    engine = _get_engine()
    print(f"\n  AWE REPAIR — Tier {engine.current_tier} ({engine.tier_name})")
    if engine.current_tier == 1:
        print("  Mode: ADVISORY (proposals only, no live changes)")
    print(f"  Running repair loop...\n")

    result = engine.run_repair_loop()

    print(f"  {'=' * 50}")
    print(f"  Repair Loop Complete")
    print(f"  {'=' * 50}")
    print(f"  Detected:        {result.detected}")
    print(f"  Classified:      {result.classified}")
    print(f"  Fixed:           {result.fixed}")
    print(f"  Proposals:       {result.proposals_written}")
    print(f"  Escalated:       {result.escalated}")
    print(f"  Skipped (dedup): {result.skipped_dedup}")

    if result.errors:
        print(f"\n  Errors ({len(result.errors)}):")
        for err in result.errors:
            print(f"    {err}")

    if result.proposals_written > 0:
        proposals_dir = Path(__file__).parent / "memory" / "recommendations"
        print(f"\n  Proposals written to: {proposals_dir}")

    print()
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    """Show recent decision log."""
    engine = _get_engine()
    hours = args.hours if hasattr(args, "hours") else 48
    decisions = engine.logger.get_recent_decisions(hours=hours)

    print(f"\n  AWE AUDIT — Last {hours}h ({len(decisions)} decisions)")
    print(f"  {'=' * 60}\n")

    if not decisions:
        print("  No decisions in the audit log.")
        return 0

    for dec in decisions:
        ts = dec.get("Timestamp", "")[:19]
        wf_id = dec.get("Workflow_ID", "?")[:16]
        outcome = dec.get("Outcome", "?")
        conf = dec.get("Confidence_Score", 0)
        risk = dec.get("Risk_Level", "?")
        classification = dec.get("Classification", "")
        action = dec.get("Action_Taken", "")
        issue = dec.get("Issue_Detected", "")[:80]

        print(f"  {ts} | {wf_id}.. | {outcome:>10} | conf={conf:.2f} | {risk}")
        print(f"    Class: {classification} | Action: {action}")
        if issue:
            print(f"    Issue: {issue}")
        print()

    return 0


def cmd_patterns(args: argparse.Namespace) -> int:
    """List all registered patterns with success rates."""
    engine = _get_engine()
    stats = engine.repair.get_pattern_stats()

    print(f"\n  AWE PATTERNS — {len(stats)} registered")
    print(f"  {'=' * 70}\n")
    print(f"  {'Pattern':<35} {'Confidence':>10} {'Success':>10} {'Risk':>10}")
    print(f"  {'-' * 35} {'-' * 10} {'-' * 10} {'-' * 10}")

    for pid, info in sorted(stats.items()):
        name = info["name"][:34]
        conf = f"{info['confidence']:.2f}"
        success = f"{info['observed_success_rate']:.2f}"
        risk = info["risk_level"]
        print(f"  {name:<35} {conf:>10} {success:>10} {risk:>10}")

    print()
    return 0


def cmd_seed(args: argparse.Namespace) -> int:
    """Run pattern seeding."""
    from autonomous.scripts.seed_patterns import seed_patterns
    force = args.force if hasattr(args, "force") else False
    counts = seed_patterns(force=force)

    total = counts["builtin"] + counts["additional"]
    print(f"\n  AWE SEED — Pattern seeding complete")
    print(f"  Builtin:    {counts['builtin']}")
    print(f"  Additional: {counts['additional']}")
    print(f"  Skipped:    {counts['skipped']}")
    print(f"  Total:      {total}\n")
    return 0


def cmd_tier(args: argparse.Namespace) -> int:
    """Show or set the current autonomy tier."""
    import yaml

    config_path = Path(__file__).parent / "config.yaml"

    if args.level is not None:
        level = args.level
        if level < 1 or level > 5:
            print(f"  Error: Tier must be 1-5, got {level}")
            return 1

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        config.setdefault("system", {})["current_tier"] = level

        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        tier_names = {1: "Advisory", 2: "Supervised", 3: "Semi-autonomous", 4: "Autonomous", 5: "Near-full"}
        print(f"\n  Autonomy tier set to {level} ({tier_names.get(level, '?')})\n")
    else:
        engine = _get_engine()
        print(f"\n  Current tier: {engine.current_tier} ({engine.tier_name})\n")

    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize memory directories."""
    from autonomous.scripts.init_memory import init_memory_dirs
    dirs = init_memory_dirs()
    print(f"\n  AWE INIT — Memory initialized ({len(dirs)} directories)\n")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="autonomous",
        description="AWE — Autonomous Workflow Engineer for n8n",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # status
    sub.add_parser("status", help="Health dashboard + recent decisions")

    # monitor
    sub.add_parser("monitor", help="Run detection only (no fixes)")

    # repair
    sub.add_parser("repair", help="Full repair loop at current tier")

    # audit
    audit_p = sub.add_parser("audit", help="Show decision log")
    audit_p.add_argument("--hours", type=int, default=48, help="Hours of history (default: 48)")

    # patterns
    sub.add_parser("patterns", help="List patterns with success rates")

    # seed
    seed_p = sub.add_parser("seed", help="Run pattern seeding")
    seed_p.add_argument("--force", action="store_true", help="Overwrite existing patterns")

    # tier
    tier_p = sub.add_parser("tier", help="Show/set autonomy tier")
    tier_p.add_argument("level", nargs="?", type=int, help="Tier level (1-5)")

    # init
    sub.add_parser("init", help="Initialize memory directories")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    commands = {
        "status": cmd_status,
        "monitor": cmd_monitor,
        "repair": cmd_repair,
        "audit": cmd_audit,
        "patterns": cmd_patterns,
        "seed": cmd_seed,
        "tier": cmd_tier,
        "init": cmd_init,
    }

    handler = commands.get(args.command)
    if handler:
        sys.exit(handler(args))
    else:
        parser.print_help()
        sys.exit(1)
