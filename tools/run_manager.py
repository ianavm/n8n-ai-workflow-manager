"""
n8n Agentic Workflows Manager - Main Entry Point

Orchestrates workflow management operations across multiple modes:
  status    - Quick health check and workflow status overview
  monitor   - Full monitoring cycle (fetch executions, detect errors)
  analyze   - Deep performance analysis with charts and recommendations
  report    - Generate and deliver full performance report (Slides + Email)
  deploy    - Deploy workflow from JSON file
  docs      - Generate documentation for all workflows
  ai-audit  - Audit AI nodes across all workflows
  revision  - Run full revision (health + drift + quality + SOP) — dry-run by default; pass --apply to write
"""

import sys
import time
from pathlib import Path


def run_tool(tool_name: str) -> int:
    """
    Run a specific tool module.

    Args:
        tool_name: Name of the Python tool file

    Returns:
        Exit code (0 = success, non-zero = failure)
    """
    import subprocess

    tools_dir = Path(__file__).parent
    tool_path = tools_dir / tool_name

    if not tool_path.exists():
        print(f"  Tool not found: {tool_name}")
        return 1

    try:
        result = subprocess.run(
            [sys.executable, str(tool_path)],
            capture_output=False,
            text=True
        )
        return result.returncode

    except Exception as e:
        print(f"  Error running {tool_name}: {e}")
        return 1


def run_status():
    """Quick status check - health check and workflow overview."""
    print("=" * 60)
    print("N8N AGENTIC WORKFLOWS MANAGER - STATUS CHECK")
    print("=" * 60)

    start_time = time.time()

    print("\n[1/1] Checking n8n connection and listing workflows...")
    print("-" * 60)
    result = run_tool('n8n_client.py')
    if result != 0:
        print("\n  CRITICAL: Cannot connect to n8n instance")
        return 1

    elapsed = time.time() - start_time
    print(f"\n  Status check complete ({elapsed:.1f}s)")
    return 0


def run_monitor():
    """Full monitoring cycle - fetch executions and detect errors."""
    print("=" * 60)
    print("N8N AGENTIC WORKFLOWS MANAGER - MONITORING")
    print("=" * 60)

    start_time = time.time()

    # Step 1: Connect to n8n
    print("\n[1/3] Connecting to n8n...")
    print("-" * 60)
    result = run_tool('n8n_client.py')
    if result != 0:
        print("\n  CRITICAL: Cannot connect to n8n instance")
        return 1

    # Step 2: Monitor executions
    print("\n[2/3] Monitoring executions...")
    print("-" * 60)
    result = run_tool('execution_monitor.py')
    if result != 0:
        print("  WARNING: Execution monitoring had issues")

    # Step 3: Summary
    elapsed = time.time() - start_time
    print(f"\n[3/3] Monitoring Complete!")
    print("=" * 60)
    print(f"  Total time: {elapsed:.1f}s")
    print("=" * 60)

    return 0


def run_analyze():
    """Deep analysis cycle with charts and recommendations."""
    print("=" * 60)
    print("N8N AGENTIC WORKFLOWS MANAGER - ANALYSIS")
    print("=" * 60)

    start_time = time.time()

    # Step 1: Fetch execution data
    print("\n[1/4] Fetching execution data...")
    print("-" * 60)
    result = run_tool('execution_monitor.py')
    if result != 0:
        print("\n  CRITICAL: Could not fetch execution data")
        return 1

    # Step 2: Analyze metrics
    print("\n[2/4] Analyzing workflow performance...")
    print("-" * 60)
    result = run_tool('workflow_analyzer.py')
    if result != 0:
        print("\n  CRITICAL: Analysis failed")
        return 1

    # Step 3: Generate charts
    print("\n[3/4] Generating performance charts...")
    print("-" * 60)
    result = run_tool('generate_charts.py')
    if result != 0:
        print("\n  WARNING: Chart generation failed")

    # Step 4: Summary
    elapsed = time.time() - start_time
    print(f"\n[4/4] Analysis Complete!")
    print("=" * 60)
    print(f"  Total time: {elapsed:.1f}s")
    print("\nNext steps:")
    print("  1. Review charts in .tmp/charts/")
    print("  2. Check analysis_results.json for detailed metrics")
    print("  3. Run 'report' mode to generate Google Slides report")
    print("=" * 60)

    return 0


def run_report():
    """Full report generation - analysis + charts + slides + email."""
    print("=" * 60)
    print("N8N AGENTIC WORKFLOWS MANAGER - REPORT GENERATION")
    print("=" * 60)

    start_time = time.time()

    # Step 1: Fetch execution data
    print("\n[1/6] Fetching execution data...")
    print("-" * 60)
    result = run_tool('execution_monitor.py')
    if result != 0:
        print("\n  CRITICAL: Could not fetch execution data")
        return 1

    # Step 2: Analyze metrics
    print("\n[2/6] Analyzing workflow performance...")
    print("-" * 60)
    result = run_tool('workflow_analyzer.py')
    if result != 0:
        print("\n  CRITICAL: Analysis failed")
        return 1

    # Step 3: Generate charts
    print("\n[3/6] Generating performance charts...")
    print("-" * 60)
    result = run_tool('generate_charts.py')
    if result != 0:
        print("\n  CRITICAL: Chart generation failed")
        return 1

    # Step 4: Create presentation
    print("\n[4/6] Creating Google Slides report...")
    print("-" * 60)
    result = run_tool('create_report.py')
    if result != 0:
        print("\n  CRITICAL: Report creation failed")
        print("  Check Google OAuth credentials and API access")
        return 1

    # Step 5: Send email
    print("\n[5/6] Sending email report...")
    print("-" * 60)
    result = run_tool('send_email.py')
    if result != 0:
        print("\n  WARNING: Email sending failed")
        print("  Report was created, but email delivery failed")

    # Step 6: Summary
    elapsed = time.time() - start_time
    print(f"\n[6/6] Report Complete!")
    print("=" * 60)
    print(f"  Total time: {elapsed:.1f}s")
    print("\nNext steps:")
    print("  1. Check your email for the report link")
    print("  2. Review the Google Slides presentation")
    print("  3. Share insights with your team")
    print("=" * 60)

    return 0


def run_deploy():
    """Deploy a workflow from JSON file."""
    print("=" * 60)
    print("N8N AGENTIC WORKFLOWS MANAGER - DEPLOYMENT")
    print("=" * 60)

    result = run_tool('workflow_deployer.py')
    return result


def run_docs():
    """Generate workflow documentation."""
    print("=" * 60)
    print("N8N AGENTIC WORKFLOWS MANAGER - DOCUMENTATION")
    print("=" * 60)

    result = run_tool('workflow_docs_generator.py')
    return result


def run_ai_audit():
    """Audit AI nodes across all workflows."""
    print("=" * 60)
    print("N8N AGENTIC WORKFLOWS MANAGER - AI AUDIT")
    print("=" * 60)

    result = run_tool('ai_node_manager.py')
    return result


def run_revision():
    """Run full revision across active departments. Dry-run unless --apply passed."""
    import subprocess
    tools_dir = Path(__file__).parent
    extra_args = sys.argv[2:]  # pass-through flags: --apply, --dept, --skip-live-health
    print("=" * 60)
    print("N8N AGENTIC WORKFLOWS MANAGER - FULL REVISION")
    print("=" * 60)
    try:
        result = subprocess.run(
            [sys.executable, str(tools_dir / 'run_full_revision.py'), *extra_args],
            capture_output=False,
            text=True,
        )
        return result.returncode
    except Exception as e:
        print(f"  Error running revision: {e}")
        return 1


# ── AWLM Modes ──────────────────────────────────────────────

def run_lifecycle():
    """Run all AWLM loops once (repair + optimize scan)."""
    result = run_tool('lifecycle_orchestrator.py')
    return result


def run_repair():
    """Run one autonomous repair cycle."""
    import subprocess
    tools_dir = Path(__file__).parent
    try:
        result = subprocess.run(
            [sys.executable, str(tools_dir / 'lifecycle_orchestrator.py'), 'repair'],
            capture_output=False, text=True,
        )
        return result.returncode
    except Exception as e:
        print(f"  Error: {e}")
        return 1


def run_optimize():
    """Run one optimisation cycle."""
    import subprocess
    tools_dir = Path(__file__).parent
    try:
        result = subprocess.run(
            [sys.executable, str(tools_dir / 'lifecycle_orchestrator.py'), 'optimize'],
            capture_output=False, text=True,
        )
        return result.returncode
    except Exception as e:
        print(f"  Error: {e}")
        return 1


def run_revamp_scan():
    """Scan for workflows needing revamp."""
    import subprocess
    tools_dir = Path(__file__).parent
    try:
        result = subprocess.run(
            [sys.executable, str(tools_dir / 'lifecycle_orchestrator.py'), 'revamp-scan'],
            capture_output=False, text=True,
        )
        return result.returncode
    except Exception as e:
        print(f"  Error: {e}")
        return 1


def run_awlm_status():
    """Show AWLM system status."""
    import subprocess
    tools_dir = Path(__file__).parent
    try:
        result = subprocess.run(
            [sys.executable, str(tools_dir / 'lifecycle_orchestrator.py'), 'status'],
            capture_output=False, text=True,
        )
        return result.returncode
    except Exception as e:
        print(f"  Error: {e}")
        return 1


def main():
    """Main entry point with command routing."""
    modes = {
        'status': run_status,
        'monitor': run_monitor,
        'analyze': run_analyze,
        'report': run_report,
        'deploy': run_deploy,
        'docs': run_docs,
        'ai-audit': run_ai_audit,
        'revision': run_revision,
        # AWLM modes
        'lifecycle': run_lifecycle,
        'repair': run_repair,
        'optimize': run_optimize,
        'revamp-scan': run_revamp_scan,
        'awlm-status': run_awlm_status,
    }

    mode = sys.argv[1] if len(sys.argv) > 1 else 'status'

    if mode in ('-h', '--help', 'help'):
        print("n8n Agentic Workflows Manager")
        print("\nUsage: python run_manager.py [mode]")
        print("\nModes:")
        for name in modes:
            print(f"  {name:12} - {modes[name].__doc__.strip()}")
        sys.exit(0)

    if mode not in modes:
        print(f"Unknown mode: {mode}")
        print(f"Available modes: {', '.join(modes.keys())}")
        sys.exit(1)

    try:
        exit_code = modes[mode]()
        sys.exit(exit_code)

    except KeyboardInterrupt:
        print("\n\nWorkflow interrupted by user")
        sys.exit(1)

    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
