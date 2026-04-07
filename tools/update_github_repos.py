#!/usr/bin/env python3
"""
Update Github Access repos from upstream GitHub sources.

Usage:
    python tools/update_github_repos.py                  # Update all repos
    python tools/update_github_repos.py --list           # List repos and status
    python tools/update_github_repos.py --only n8n-master context7-master  # Update specific repos
    python tools/update_github_repos.py --priority       # Update high-priority repos only
    python tools/update_github_repos.py --dry-run        # Show what would be updated
    python tools/update_github_repos.py --add owner/repo # Add a new repo to the registry
"""

import sys
import os

# Fix Windows console encoding
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import argparse
import json
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# ─── Configuration ──────────────────────────────────────────────────────────

GITHUB_ACCESS_DIR = Path(__file__).resolve().parent.parent / "Github Access"
REGISTRY_FILE = GITHUB_ACCESS_DIR / "repos_registry.json"

# Map: directory name -> { repo: "owner/repo", branch: "main"|"master"|null (auto-detect), priority: "high"|"medium"|"low" }
# priority=high: actively used in workflows/skills, update frequently
# priority=medium: reference repos, update occasionally
# priority=low: archived/rarely used, update on demand
DEFAULT_REGISTRY = {
    # ── High priority: actively used in skills, workflows, and tooling ──
    "n8n-master": {
        "repo": "n8n-io/n8n",
        "branch": None,
        "priority": "high",
        "description": "Full n8n source — node implementations"
    },
    "n8n-docs": {
        "repo": "n8n-io/n8n-docs",
        "branch": None,
        "priority": "high",
        "description": "Official n8n documentation",
        "method": "git"
    },
    "n8n-workflows-main": {
        "repo": "Zie619/n8n-workflows",
        "branch": None,
        "priority": "high",
        "description": "4,343 production workflows in 188 categories"
    },
    "ultimate-n8n-ai-workflows-main": {
        "repo": "oxbshw/ultimate-n8n-ai-workflows",
        "branch": None,
        "priority": "high",
        "description": "3,400+ AI-first workflows"
    },
    "everything-claude-code-main": {
        "repo": "affaan-m/everything-claude-code",
        "branch": None,
        "priority": "high",
        "description": "84 skills, 17 agents, 43 commands for Claude Code"
    },
    "get-shit-done-main": {
        "repo": "gsd-build/get-shit-done",
        "branch": None,
        "priority": "high",
        "description": "Meta-prompting + context engineering framework"
    },
    "superpowers-main": {
        "repo": "obra/superpowers",
        "branch": None,
        "priority": "high",
        "description": "Dev workflow framework (14 skills, 3 commands)"
    },
    "claude-ads-main": {
        "repo": "AgriciDaniel/claude-ads",
        "branch": None,
        "priority": "high",
        "description": "Paid advertising audit & optimization skill"
    },
    "claude-seo-main": {
        "repo": "AgriciDaniel/claude-seo",
        "branch": None,
        "priority": "high",
        "description": "Production-ready SEO analysis skill"
    },
    "context7-master": {
        "repo": "upstash/context7",
        "branch": None,
        "priority": "high",
        "description": "MCP server for live API docs"
    },
    "n8n-workflow-builder-main": {
        "repo": "makafeli/n8n-workflow-builder",
        "branch": None,
        "priority": "high",
        "description": "MCP server with 23 n8n API tools"
    },
    "awesome-claude-skills-master": {
        "repo": "ComposioHQ/awesome-claude-skills",
        "branch": None,
        "priority": "high",
        "description": "40+ Claude skills (skill-creator, mcp-builder)"
    },
    "ui-ux-pro-max-skill-main": {
        "repo": "nextlevelbuilder/ui-ux-pro-max-skill",
        "branch": None,
        "priority": "high",
        "description": "Design intelligence toolkit (BM25 search, 100+ product types)"
    },
    "tavily-mcp-main": {
        "repo": "tavily-ai/tavily-mcp",
        "branch": None,
        "priority": "high",
        "description": "Tavily MCP server for web search"
    },

    # ── Medium priority: reference repos, update occasionally ──
    "LightRAG-main": {
        "repo": "HKUDS/LightRAG",
        "branch": None,
        "priority": "medium",
        "description": "RAG framework with knowledge graphs"
    },
    "langchain-master": {
        "repo": "langchain-ai/langchain",
        "branch": None,
        "priority": "medium",
        "description": "LangChain LLM framework"
    },
    "supabase-master": {
        "repo": "supabase/supabase",
        "branch": None,
        "priority": "medium",
        "description": "Postgres Development Platform"
    },
    "activepieces-main": {
        "repo": "activepieces/activepieces",
        "branch": None,
        "priority": "medium",
        "description": "Open-source automation platform"
    },
    "directus-main": {
        "repo": "directus/directus",
        "branch": None,
        "priority": "medium",
        "description": "Instant REST+GraphQL API for any SQL database"
    },
    "open-interpreter-main": {
        "repo": "OpenInterpreter/open-interpreter",
        "branch": None,
        "priority": "medium",
        "description": "Natural language code execution"
    },
    "windmill-main": {
        "repo": "windmill-labs/windmill",
        "branch": None,
        "priority": "medium",
        "description": "Developer platform for scripts/workflows/UIs"
    },
    "paperless-ngx-dev": {
        "repo": "paperless-ngx/paperless-ngx",
        "branch": "dev",
        "priority": "medium",
        "description": "Document management system"
    },

    # ── Low priority: niche references, update on demand ──
    "cal.com-main": {
        "repo": "calcom/cal.com",
        "branch": None,
        "priority": "low",
        "description": "Scheduling infrastructure"
    },
    "discord.py-master": {
        "repo": "Rapptz/discord.py",
        "branch": None,
        "priority": "low",
        "description": "Discord bot library"
    },
    "tweepy-master": {
        "repo": "tweepy/tweepy",
        "branch": None,
        "priority": "low",
        "description": "Twitter/X API wrapper"
    },
    "networkx-main": {
        "repo": "networkx/networkx",
        "branch": None,
        "priority": "low",
        "description": "Graph algorithms library"
    },
    "newspaper-master": {
        "repo": "codelucas/newspaper",
        "branch": None,
        "priority": "low",
        "description": "Article scraping & NLP"
    },
    "instagram-private-api-master": {
        "repo": "dilame/instagram-private-api",
        "branch": None,
        "priority": "low",
        "description": "Instagram private API client"
    },
    "minGPT-master": {
        "repo": "karpathy/minGPT",
        "branch": None,
        "priority": "low",
        "description": "Minimal GPT training (reference)"
    },
    "commerce-main": {
        "repo": "vercel/commerce",
        "branch": None,
        "priority": "low",
        "description": "Next.js commerce template"
    },
    "realworld-main": {
        "repo": "gothinkster/realworld",
        "branch": None,
        "priority": "low",
        "description": "Fullstack app spec (Conduit)"
    },
    "blitz-main": {
        "repo": "blitz-js/blitz",
        "branch": None,
        "priority": "low",
        "description": "Next.js fullstack toolkit"
    },
    "bulletproof-nodejs-master": {
        "repo": "santiq/bulletproof-nodejs",
        "branch": None,
        "priority": "low",
        "description": "Node.js project architecture"
    },
    "mern-starter-master": {
        "repo": "Hashnode/mern-starter",
        "branch": None,
        "priority": "low",
        "description": "MERN stack boilerplate"
    },
    "saas-master": {
        "repo": "async-labs/saas",
        "branch": None,
        "priority": "low",
        "description": "SaaS boilerplate"
    },
    "windmill-dashboard-master": {
        "repo": "estevanmaito/windmill-dashboard",
        "branch": None,
        "priority": "low",
        "description": "Dashboard UI template"
    },
    "react-dashboard-master": {
        "repo": "creativetimofficial/material-dashboard-react",
        "branch": None,
        "priority": "low",
        "description": "Material UI dashboard"
    },
    "docspell-master": {
        "repo": "eikek/docspell",
        "branch": None,
        "priority": "low",
        "description": "Document management"
    },
    "docspell-master-2": {
        "repo": "eikek/docspell",
        "branch": None,
        "priority": "low",
        "description": "Document management (duplicate)"
    },
    "mailrise-main": {
        "repo": "YoRyan/mailrise",
        "branch": None,
        "priority": "low",
        "description": "SMTP to notification gateway"
    },
    "appsmith-release": {
        "repo": "appsmithorg/appsmith",
        "branch": "release",
        "priority": "low",
        "description": "Low-code app builder"
    },
    "appsmith-release-2": {
        "repo": "appsmithorg/appsmith",
        "branch": "release",
        "priority": "low",
        "description": "Low-code app builder (duplicate)"
    },
}


# ─── Helpers ────────────────────────────────────────────────────────────────

class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def log(msg, color=None):
    prefix = f"{color}" if color else ""
    suffix = Colors.RESET if color else ""
    print(f"{prefix}{msg}{suffix}")


def run(cmd, cwd=None, capture=True):
    """Run a shell command, return (returncode, stdout)."""
    result = subprocess.run(
        cmd, shell=True, cwd=cwd,
        capture_output=capture, text=True,
        timeout=300
    )
    return result.returncode, result.stdout.strip()


def load_registry():
    """Load registry from file, or create from defaults."""
    if REGISTRY_FILE.exists():
        with open(REGISTRY_FILE, "r") as f:
            return json.load(f)
    return dict(DEFAULT_REGISTRY)


def save_registry(registry):
    """Save registry to file."""
    with open(REGISTRY_FILE, "w") as f:
        json.dump(registry, f, indent=2)
    log(f"  Registry saved: {REGISTRY_FILE.name}", Colors.DIM)


def get_default_branch(owner_repo):
    """Get the default branch for a GitHub repo via gh CLI."""
    code, output = run(f'gh api repos/{owner_repo} --jq .default_branch')
    if code == 0 and output:
        return output
    return "main"  # fallback


def get_local_age(dir_path):
    """Get the age of a local directory based on most recent file modification."""
    try:
        most_recent = max(
            (f.stat().st_mtime for f in dir_path.rglob("*") if f.is_file()),
            default=0
        )
        if most_recent == 0:
            return "unknown"
        delta = time.time() - most_recent
        days = int(delta / 86400)
        if days == 0:
            return "today"
        elif days == 1:
            return "1 day ago"
        elif days < 30:
            return f"{days} days ago"
        elif days < 365:
            return f"{days // 30} months ago"
        else:
            return f"{days // 365}y {(days % 365) // 30}m ago"
    except Exception:
        return "unknown"


def get_upstream_date(owner_repo, branch):
    """Get the date of the latest commit on the upstream branch."""
    code, output = run(
        f'gh api repos/{owner_repo}/commits/{branch} --jq .commit.committer.date'
    )
    if code == 0 and output:
        try:
            dt = datetime.fromisoformat(output.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass
    return "unknown"


def update_via_git(dir_path, owner_repo, branch):
    """Update a repo that has its own .git directory."""
    log(f"  Pulling latest via git...", Colors.DIM)
    code, output = run("git fetch origin", cwd=str(dir_path))
    if code != 0:
        return False, f"git fetch failed: {output}"

    code, output = run(f"git reset --hard origin/{branch}", cwd=str(dir_path))
    if code != 0:
        return False, f"git reset failed: {output}"

    return True, "Updated via git pull"


def download_zip(owner_repo, branch, dest_file):
    """Download a repo zip using gh CLI (handles auth/SSL on Windows)."""
    # gh api gives us the zipball URL which handles redirects properly
    code, output = run(
        f'gh api repos/{owner_repo}/zipball/{branch} -H "Accept: application/vnd.github+json" > "{dest_file}"',
    )
    if code == 0 and dest_file.exists() and dest_file.stat().st_size > 1000:
        return True

    # Fallback: try Python urllib (handles Windows SSL better than curl)
    try:
        import urllib.request
        import ssl
        url = f"https://github.com/{owner_repo}/archive/refs/heads/{branch}.zip"
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers={"User-Agent": "update-github-repos/1.0"})
        with urllib.request.urlopen(req, context=ctx, timeout=120) as resp:
            with open(dest_file, "wb") as f:
                shutil.copyfileobj(resp, f)
        if dest_file.exists() and dest_file.stat().st_size > 1000:
            return True
    except Exception:
        pass

    return False


def update_via_zip(dir_path, owner_repo, branch):
    """Update a repo by downloading and extracting a fresh zip."""
    dir_name = dir_path.name

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        zip_file = tmp_path / "repo.zip"

        # Download zip
        log(f"  Downloading {owner_repo}@{branch}...", Colors.DIM)
        if not download_zip(owner_repo, branch, zip_file):
            return False, "Download failed — check repo name and branch"

        # Extract
        log(f"  Extracting...", Colors.DIM)
        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()
        try:
            import zipfile
            with zipfile.ZipFile(zip_file) as zf:
                zf.extractall(extract_dir)
        except Exception as e:
            return False, f"Extraction failed: {e}"

        # Find the single extracted directory (GitHub zips contain one root dir)
        extracted_dirs = [d for d in extract_dir.iterdir() if d.is_dir()]
        if not extracted_dirs:
            return False, "No directory found in zip"
        source_dir = extracted_dirs[0]

        # Replace: remove old, move new
        log(f"  Replacing {dir_name}/...", Colors.DIM)
        try:
            if dir_path.exists():
                shutil.rmtree(dir_path)
            shutil.move(str(source_dir), str(dir_path))
        except Exception as e:
            return False, f"Replace failed: {e}"

    return True, "Updated via fresh download"


# ─── Commands ───────────────────────────────────────────────────────────────

def cmd_list(registry):
    """List all repos with their status."""
    log(f"\n{'Dir Name':<42} {'Priority':<10} {'Repo':<40} {'Local Age'}", Colors.BOLD)
    log("-" * 120)

    for dir_name in sorted(registry.keys()):
        info = registry[dir_name]
        dir_path = GITHUB_ACCESS_DIR / dir_name
        exists = dir_path.exists()

        priority = info.get("priority", "?")
        repo = info.get("repo", "?")
        age = get_local_age(dir_path) if exists else "NOT FOUND"

        color = {
            "high": Colors.CYAN,
            "medium": Colors.YELLOW,
            "low": Colors.DIM,
        }.get(priority, "")

        status = "" if exists else f" {Colors.RED}[MISSING]{Colors.RESET}"
        log(f"  {color}{dir_name:<40}{Colors.RESET} {priority:<10} {repo:<40} {age}{status}")

    total = len(registry)
    existing = sum(1 for d in registry if (GITHUB_ACCESS_DIR / d).exists())
    log(f"\n  {existing}/{total} repos present locally\n")


def cmd_update(registry, targets=None, priority_filter=None, dry_run=False):
    """Update repos from upstream."""
    to_update = {}

    for dir_name, info in registry.items():
        if targets and dir_name not in targets:
            continue
        if priority_filter and info.get("priority") not in priority_filter:
            continue
        to_update[dir_name] = info

    if not to_update:
        log("No repos matched the filter.", Colors.YELLOW)
        return

    log(f"\n  Updating {len(to_update)} repos...\n", Colors.BOLD)

    results = {"updated": [], "failed": [], "skipped": []}

    for i, (dir_name, info) in enumerate(to_update.items(), 1):
        repo = info["repo"]
        branch = info.get("branch")
        method = info.get("method", "zip")
        dir_path = GITHUB_ACCESS_DIR / dir_name

        log(f"[{i}/{len(to_update)}] {dir_name}", Colors.CYAN)
        log(f"  Source: {repo}", Colors.DIM)

        if dry_run:
            log(f"  [DRY RUN] Would update from {repo}", Colors.YELLOW)
            results["skipped"].append(dir_name)
            continue

        # Resolve branch if not specified
        if not branch:
            branch = get_default_branch(repo)
            info["branch"] = branch  # cache it
        log(f"  Branch: {branch}", Colors.DIM)

        # Choose update method
        has_own_git = (dir_path / ".git").is_dir()
        if has_own_git or method == "git":
            success, msg = update_via_git(dir_path, repo, branch)
        else:
            success, msg = update_via_zip(dir_path, repo, branch)

        if success:
            log(f"  OK: {msg}", Colors.GREEN)
            results["updated"].append(dir_name)
        else:
            log(f"  FAILED: {msg}", Colors.RED)
            results["failed"].append(dir_name)

    # Summary
    log(f"\n{'-' * 60}", Colors.DIM)
    log(f"  Updated: {len(results['updated'])}  |  "
        f"Failed: {len(results['failed'])}  |  "
        f"Skipped: {len(results['skipped'])}", Colors.BOLD)

    if results["failed"]:
        log(f"\n  Failed repos:", Colors.RED)
        for name in results["failed"]:
            log(f"    - {name}", Colors.RED)

    # Save registry with cached branches
    save_registry(registry)

    return results


def cmd_add(registry, owner_repo):
    """Add a new repo to the registry."""
    # Validate repo exists
    code, output = run(f'gh api repos/{owner_repo} --jq ".full_name,.default_branch,.description"')
    if code != 0:
        log(f"  Repo {owner_repo} not found on GitHub.", Colors.RED)
        return

    lines = output.split("\n")
    full_name = lines[0] if len(lines) > 0 else owner_repo
    default_branch = lines[1] if len(lines) > 1 else "main"
    description = lines[2] if len(lines) > 2 else ""

    # Generate directory name: repo-name + branch suffix
    repo_name = full_name.split("/")[1]
    dir_name = f"{repo_name}-{default_branch}"

    if dir_name in registry:
        log(f"  {dir_name} already in registry.", Colors.YELLOW)
        return

    registry[dir_name] = {
        "repo": full_name,
        "branch": default_branch,
        "priority": "medium",
        "description": description[:80]
    }

    save_registry(registry)
    log(f"  Added: {dir_name} -> {full_name} ({default_branch})", Colors.GREEN)
    log(f"  Run: python tools/update_github_repos.py --only {dir_name}", Colors.DIM)


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Update Github Access repos from upstream GitHub sources."
    )
    parser.add_argument("--list", action="store_true",
                        help="List all repos and their status")
    parser.add_argument("--only", nargs="+", metavar="DIR",
                        help="Update only specific repos by directory name")
    parser.add_argument("--priority", action="store_true",
                        help="Update high-priority repos only")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be updated without doing it")
    parser.add_argument("--add", metavar="OWNER/REPO",
                        help="Add a new repo to the registry (e.g., --add n8n-io/n8n)")
    parser.add_argument("--init-registry", action="store_true",
                        help="Create/overwrite registry file with defaults")

    args = parser.parse_args()

    # Load or initialize registry
    registry = load_registry()

    if args.init_registry:
        save_registry(DEFAULT_REGISTRY)
        log(f"  Registry initialized with {len(DEFAULT_REGISTRY)} repos.", Colors.GREEN)
        return

    if not REGISTRY_FILE.exists():
        log("  First run — creating registry file...", Colors.YELLOW)
        save_registry(registry)

    if args.list:
        cmd_list(registry)
        return

    if args.add:
        cmd_add(registry, args.add)
        return

    # Update
    priority_filter = {"high"} if args.priority else None
    cmd_update(registry, targets=args.only, priority_filter=priority_filter, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
