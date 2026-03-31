# /// script
# requires-python = ">=3.11"
# dependencies = ["tzdata"]
# ///
# Copyright 2026, Microsoft
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Daily briefing generator for the agent.

Gathers data from GitLab (osdu-activity),
reads the task board and goals from the Obsidian vault,
and writes a formatted daily note to $OSDU_BRAIN/00-inbox/ (default: ~/.osdu-brain).

Usage:
    uv run skills/briefing/scripts/daily-briefing.py
    uv run skills/briefing/scripts/daily-briefing.py --dry-run   # print to stdout only
    uv run skills/briefing/scripts/daily-briefing.py --date 2026-02-15
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("America/Chicago")

# Pipeline status constants
_RUNNING_STATUSES = frozenset({"running", "pending", "created"})


def _pipeline_label(status: str) -> str:
    """Map a GitLab pipeline status string to a display label."""
    if status == "success":
        return "✅ Passing"
    if status in _RUNNING_STATUSES:
        return "🔄 Running"
    if status == "canceled":
        return "⊘ Canceled"
    return "❌ Failed"


def _pipeline_is_actionable_failure(status: str | None) -> bool:
    """Return True only for statuses that represent a real failure (not running/pending)."""
    if status is None or status in _RUNNING_STATUSES or status == "success":
        return False
    return True


def brain_path() -> Path:
    """Resolve the brain vault path from $OSDU_BRAIN or default ~/.osdu-brain."""
    env = os.environ.get("OSDU_BRAIN")
    if env:
        return Path(env).expanduser().resolve()
    return Path.home() / ".osdu-brain"


def _load_env() -> dict[str, str]:
    """Load key=value pairs from .github/.env relative to workspace root."""
    env: dict[str, str] = {}
    env_path = workspace_root() / ".github" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


_ENV = {}  # populated in main()

GITLAB_USER = os.environ.get("GITLAB_USER", "danielscholl")

QUOTES = [
    ('"First, solve the problem. Then, write the code."', "John Johnson"),
    ('"The best way to predict the future is to implement it."', "David Heinemeier Hansson"),
    ('"Simplicity is the soul of efficiency."', "Austin Freeman"),
    ('"Code is like humor. When you have to explain it, it\'s bad."', "Cory House"),
    ('"Any fool can write code that a computer can understand. Good programmers write code that humans can understand."', "Martin Fowler"),
    ('"The most dangerous phrase in the language is: we\'ve always done it this way."', "Grace Hopper"),
    ('"It works on my machine. Then we\'ll ship your machine."', "Anonymous"),
    ('"A ship in harbor is safe, but that is not what ships are built for."', "John A. Shedd"),
    ('"Talk is cheap. Show me the code."', "Linus Torvalds"),
    ('"Weeks of coding can save you hours of planning."', "Anonymous"),
    ('"The only way to go fast is to go well."', "Robert C. Martin"),
    ('"Debugging is twice as hard as writing the code in the first place."', "Brian Kernighan"),
    ('"In theory, theory and practice are the same. In practice, they are not."', "Albert Einstein"),
    ('"Delete code. It\'s the only way to be sure."', "Anonymous"),
]


def workspace_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    )
    return Path(result.stdout.strip())


def utc_to_local_date(iso_str: str) -> str:
    """Convert a UTC ISO-8601 timestamp to a local (Central) date string."""
    if not iso_str:
        return ""
    try:
        ts = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts).astimezone(TIMEZONE)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return iso_str[:10] if len(iso_str) >= 10 else iso_str


def run_cmd(cmd: list[str], timeout: int = 120) -> str | None:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
    except FileNotFoundError:
        print(f"  ⚠️ Command not found: {cmd[0]}", file=sys.stderr)
        return None
    except subprocess.TimeoutExpired:
        print(f"  ⚠️ Command timed out after {timeout}s: {' '.join(cmd)}", file=sys.stderr)
        return None
    if result.returncode != 0:
        stderr = result.stderr.strip()
        message = f"  ⚠️ Command failed ({result.returncode}): {' '.join(cmd)}"
        if stderr:
            message += f" — {stderr}"
        print(message, file=sys.stderr)
        return None
    output = result.stdout.strip()
    if output:
        return output
    print(f"  ⚠️ Command returned no output: {' '.join(cmd)}", file=sys.stderr)
    return None


def run_json(cmd: list[str], timeout: int = 120) -> list | dict | None:
    raw = run_cmd(cmd, timeout=timeout)
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            print(f"  ⚠️ Failed to parse JSON from: {' '.join(cmd)}", file=sys.stderr)
    return None


# ── Data Gathering ──────────────────────────────────────────────


def get_gitlab_mrs(user: str | None = None) -> dict | None:
    cmd = ["osdu-activity", "mr", "--output", "json"]
    if user:
        cmd += ["--user", user]
    return run_json(cmd, timeout=180)


def get_cimpl_env_status() -> dict:
    """Detect CIMPL Azure environment status via azd and az CLI.

    Returns a dict with keys:
      - env_name: str | None
      - resource_group: str | None
      - cluster_name: str | None
      - rg_exists: bool
      - cluster_status: str | None  (e.g., "Running", "Stopped", error message)
      - provisioning_state: str | None
      - error: str | None  (if tools aren't available)
    """
    status: dict = {
        "env_name": None,
        "resource_group": None,
        "cluster_name": None,
        "rg_exists": False,
        "cluster_status": None,
        "provisioning_state": None,
        "error": None,
    }

    # Check azd env list
    env_list_raw = run_cmd(["azd", "env", "list", "--output", "json"], timeout=30)
    if env_list_raw is None:
        status["error"] = "azd not available or not authenticated"
        return status

    try:
        env_list = json.loads(env_list_raw)
    except json.JSONDecodeError:
        status["error"] = "Failed to parse azd env list output"
        return status

    if not env_list:
        return status  # No environments — env_name stays None

    # Find the default (IsDefault=true) or first environment
    active_env = None
    for env in env_list:
        if env.get("IsDefault"):
            active_env = env
            break
    if not active_env and env_list:
        active_env = env_list[0]

    if active_env:
        status["env_name"] = active_env.get("Name") or active_env.get("name")

    if not status["env_name"]:
        return status

    # Get environment values
    rg = run_cmd(["azd", "env", "get-value", "AZURE_RESOURCE_GROUP", "--environment", status["env_name"]], timeout=15)
    cluster = run_cmd(["azd", "env", "get-value", "AZURE_AKS_CLUSTER_NAME", "--environment", status["env_name"]], timeout=15)

    status["resource_group"] = rg
    status["cluster_name"] = cluster

    if not rg:
        return status

    # Check resource group existence
    rg_exists_raw = run_cmd(["az", "group", "exists", "-n", rg], timeout=15)
    status["rg_exists"] = rg_exists_raw and rg_exists_raw.strip().lower() == "true"

    if not status["rg_exists"] or not cluster:
        return status

    # Check AKS cluster status
    aks_raw = run_cmd([
        "az", "aks", "show", "-g", rg, "-n", cluster,
        "--query", "{state: powerState.code, provisioning: provisioningState}",
        "-o", "json",
    ], timeout=30)

    if aks_raw:
        try:
            aks = json.loads(aks_raw)
            status["cluster_status"] = aks.get("state")
            status["provisioning_state"] = aks.get("provisioning")
        except json.JSONDecodeError:
            status["cluster_status"] = "unknown"

    return status


def render_cimpl_section(cimpl_status: dict) -> str:
    """Render CIMPL Azure environment health section."""
    lines = ["\n## CIMPL Environment · Azure\n"]

    if cimpl_status.get("error"):
        lines.append(f"> [!warning] ⚠️ Environment detection unavailable")
        lines.append(f"> {cimpl_status['error']}")
        lines.append(f"> Run `azd auth login` and `az login` to enable environment health checks.")
        lines.append("")
        return "\n".join(lines)

    env_name = cimpl_status.get("env_name")
    if not env_name:
        lines.append("> [!danger] 🚨 No CIMPL environment deployed")
        lines.append("> No `azd` environment found. You don't have a running CIMPL deployment.")
        lines.append("> To provision: `azd provision`")
        lines.append("")
        return "\n".join(lines)

    rg = cimpl_status.get("resource_group", "—")
    cluster = cimpl_status.get("cluster_name", "—")
    rg_exists = cimpl_status.get("rg_exists", False)
    cluster_status = cimpl_status.get("cluster_status")
    prov_state = cimpl_status.get("provisioning_state")

    if rg_exists and cluster_status:
        if cluster_status == "Running" and prov_state == "Succeeded":
            health = "✅ Healthy"
            callout = "success"
        elif cluster_status == "Stopped":
            health = "⏸️ Stopped"
            callout = "warning"
        else:
            health = f"⚠️ {cluster_status} ({prov_state})"
            callout = "warning"
    elif rg_exists:
        health = "⚠️ Resource group exists but cluster not found"
        callout = "warning"
    else:
        health = "🚨 Resource group not found — environment may have been deleted"
        callout = "danger"

    lines.append(f"> [!{callout}] {health}")
    lines.append(f"> | Property | Value |")
    lines.append(f"> |----------|-------|")
    lines.append(f"> | Environment | `{env_name}` |")
    lines.append(f"> | Resource Group | `{rg}` | {'✅' if rg_exists else '❌'} |")
    if cluster:
        lines.append(f"> | AKS Cluster | `{cluster}` |")
    if cluster_status:
        lines.append(f"> | Cluster State | {cluster_status} |")
    if prov_state:
        lines.append(f"> | Provisioning | {prov_state} |")
    lines.append("")
    return "\n".join(lines)



def parse_frontmatter(text: str) -> dict[str, str]:
    """Parse YAML frontmatter from markdown. Simple key:value extraction."""
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end == -1:
        return {}
    fm = {}
    for line in text[3:end].strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fm[key.strip()] = value.strip().strip('"').strip("'")
    return fm


def extract_wikilink(value: str) -> str | None:
    """Extract target from a wikilink like '[[venus-mvp-completion]]'."""
    m = re.search(r"\[\[([^\]|]+?)(?:\|[^\]]+)?\]\]", value)
    return m.group(1) if m else None


def scan_goals(root: Path) -> list[dict]:
    """Discover and parse all goal files from 01-goals/."""
    goals_dir = brain_path() / "01-goals"
    if not goals_dir.exists():
        return []

    goals = []
    for path in sorted(goals_dir.glob("*.md")):
        if path.name.startswith("."):
            continue
        text = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)

        # Extract title from first H1
        title = path.stem.replace("-", " ").title()
        for line in text.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break

        # Parse numbered objective sections
        objectives = []
        current_obj: dict | None = None
        in_key_results = False

        for line in text.splitlines():
            obj_match = re.match(r"^## (\d+)\.\s+(.+)$", line)
            if obj_match:
                if current_obj:
                    objectives.append(current_obj)
                current_obj = {
                    "number": int(obj_match.group(1)),
                    "name": obj_match.group(2).strip(),
                    "key_results": [],
                    "done": 0,
                    "total": 0,
                }
                in_key_results = False
                continue

            if current_obj:
                if line.strip() == "### Key Results":
                    in_key_results = True
                    continue
                if in_key_results:
                    kr_match = re.match(r"^- \[([ xX])\]\s+(.+)$", line)
                    if kr_match:
                        done = kr_match.group(1).lower() == "x"
                        current_obj["key_results"].append({
                            "text": kr_match.group(2).strip(),
                            "done": done,
                        })
                        current_obj["total"] += 1
                        if done:
                            current_obj["done"] += 1
                    elif line.startswith("## ") or line.startswith("---"):
                        in_key_results = False

        if current_obj:
            objectives.append(current_obj)

        total_done = sum(o["done"] for o in objectives)
        total_kr = sum(o["total"] for o in objectives)

        goals.append({
            "name": title,
            "slug": path.stem,
            "quarter": fm.get("quarter", ""),
            "tags": fm.get("tags", ""),
            "objectives": objectives,
            "total_done": total_done,
            "total_kr": total_kr,
            "projects": [],
        })

    return goals


def scan_projects(root: Path) -> list[dict]:
    """Discover and parse all project files from 02-projects/."""
    projects_dir = brain_path() / "02-projects"
    if not projects_dir.exists():
        return []

    projects = []
    for path in sorted(projects_dir.glob("*.md")):
        if path.name.startswith("."):
            continue
        text = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)

        title = path.stem.replace("-", " ").title()
        for line in text.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break

        # Parse phase and next milestone
        phase = ""
        next_milestone = ""
        for line in text.splitlines():
            if "**Phase:**" in line:
                phase = line.split("**Phase:**")[1].strip()
            elif "**Next milestone:**" in line:
                next_milestone = line.split("**Next milestone:**")[1].strip()

        # Parse all checkbox tasks (Active Tasks, CI/CD Integration, etc.)
        active_tasks = []
        in_task_section = False
        for line in text.splitlines():
            if re.match(r"^## (Active Tasks|CI/CD Integration)", line):
                in_task_section = True
                continue
            if in_task_section:
                if line.startswith("## ") or line.startswith("---"):
                    in_task_section = False
                    continue
                task_match = re.match(r"^- \[([ xX])\]\s+(.+)$", line)
                if task_match:
                    done = task_match.group(1).lower() == "x"
                    active_tasks.append({"text": task_match.group(2).strip(), "done": done})

        # Parse blockers
        blockers = []
        in_blockers = False
        for line in text.splitlines():
            if line.strip() == "## Blockers":
                in_blockers = True
                continue
            if in_blockers:
                if line.startswith("## ") or line.startswith("---"):
                    break
                stripped = line.strip()
                if stripped.startswith("- ") and not stripped.startswith("_"):
                    blockers.append(stripped[2:].strip())

        goal_link = extract_wikilink(fm.get("goal", ""))
        tasks_done = sum(1 for t in active_tasks if t["done"])

        projects.append({
            "name": title,
            "slug": path.stem,
            "status": fm.get("status", ""),
            "goal_link": goal_link,
            "repo": fm.get("repo", ""),
            "phase": phase,
            "next_milestone": next_milestone,
            "active_tasks": active_tasks,
            "blockers": blockers,
            "tasks_done": tasks_done,
            "tasks_total": len(active_tasks),
        })

    return projects


def link_goals_projects(goals: list[dict], projects: list[dict]) -> None:
    """Link projects to their parent goals via frontmatter wikilink."""
    goal_map = {g["slug"]: g for g in goals}
    for proj in projects:
        if proj["goal_link"] and proj["goal_link"] in goal_map:
            goal_map[proj["goal_link"]]["projects"].append(proj)


def get_github_tasks() -> list[dict]:
    """Fetch open GitHub issues assigned to the current user."""
    raw = run_cmd(
        ["gh", "issue", "list", "--assignee", "@me", "--state", "open",
         "--json", "number,title,labels,updatedAt", "--limit", "20"],
        timeout=30,
    )
    if not raw:
        return []
    try:
        issues = json.loads(raw)
        return [{"number": i["number"], "title": i["title"],
                 "labels": [l["name"] for l in i.get("labels", [])],
                 "updated": i.get("updatedAt", "")}
                for i in issues]
    except (json.JSONDecodeError, KeyError):
        return []


def build_mr_goal_tags(
    all_mrs: list[dict],
    goals: list[dict],
) -> dict[int, list[str]]:
    """Tag MRs with related goal names by matching service keywords."""
    tags: dict[int, list[str]] = {}
    for goal in goals:
        keywords: set[str] = set()
        for obj in goal["objectives"]:
            for kr in obj["key_results"]:
                text_lower = kr["text"].lower()
                for svc in ["partition", "entitlements", "legal", "schema",
                            "file", "storage", "indexer", "search",
                            "notification", "workflow", "wellbore",
                            "eds-dms", "register", "policy", "secret",
                            "dataset", "unit", "crs"]:
                    if svc in text_lower:
                        keywords.add(svc)
        if keywords:
            for mr in all_mrs:
                svc = mr.get("service", "").lower()
                if any(kw in svc for kw in keywords):
                    tags.setdefault(mr["iid"], []).append(goal["name"])
    return tags


# ── Rendering ───────────────────────────────────────────────────


def generate_daily_quote() -> tuple[str, str, bool]:
    """Generate a daily quote/encouragement/joke via Azure OpenAI, with fallback.

    Returns (quote_text, author, ai_generated).
    """
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    api_key = os.environ.get("AZURE_API_KEY", "")
    api_version = os.environ.get("AZURE_OPENAI_VERSION", "2025-03-01-preview")
    if not endpoint or not api_key:
        q, a = secrets.choice(QUOTES)
        return (q, a, False)
    try:
        quote_type = secrets.choice([
            "an inspiring quote about engineering, leadership, or perseverance — use a REAL attribution",
            "a short word of encouragement for starting the day — attribute to 'Daily Brief'",
            "a short safe-for-work tech humor one-liner — attribute to 'Daily Brief'",
        ])
        url = f"{endpoint.rstrip('/')}/openai/deployments/gpt-4o/chat/completions?api-version={api_version}"
        body = json.dumps({
            "messages": [{"role": "user", "content":
                f"Generate {quote_type} for a software engineering leader's daily briefing. "
                "Reply with EXACTLY two lines: "
                "Line 1: the quote in double quotes. Line 2: the attribution name only."}],
            "max_tokens": 80,
            "temperature": 1.2,
        })
        result = subprocess.run(
            ["curl", "-s", url,
             "-H", f"api-key: {api_key}",
             "-H", "Content-Type: application/json",
             "-d", body],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            q, a = secrets.choice(QUOTES)
            return (q, a, False)
        data = json.loads(result.stdout)
        text = data["choices"][0]["message"]["content"].strip()
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if len(lines) >= 2:
            quote = lines[0].strip('"').strip("*").strip()
            author = lines[1].lstrip("-–— ").strip()
            return (f'"{quote}"', author, True)
        elif lines:
            return (lines[0], "Daily Brief", True)
    except Exception:
        pass
    q, a = secrets.choice(QUOTES)
    return (q, a, False)


def pick_quote() -> tuple[str, str, bool]:
    return generate_daily_quote()


def render_header(now: datetime) -> str:
    day_name = now.strftime("%A")
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    tz_abbr = now.strftime("%Z")  # CST or CDT depending on DST
    quote_text, quote_author, _ai_generated = pick_quote()

    return f"""---
date: {date_str}
day: {day_name}
tags: [daily, briefing]
---

# Daily Briefing — {day_name}, {date_str}

> [!quote] Good morning
> *{quote_text}* — {quote_author}
>
> It's {day_name}, {date_str} ({time_str} {tz_abbr}).

---"""


def _detect_mr_role(mr: dict, gitlab_user: str) -> str:
    """Determine the user's role on an MR: Author, Reviewer, or Assignee."""
    if mr.get("author", "").lower() == gitlab_user.lower():
        return "Author"
    reviewers = mr.get("reviewers", [])
    if isinstance(reviewers, list):
        for r in reviewers:
            name = r if isinstance(r, str) else r.get("username", "")
            if name.lower() == gitlab_user.lower():
                return "Reviewer"
    assignees = mr.get("assignees", [])
    if isinstance(assignees, list):
        for a in assignees:
            name = a if isinstance(a, str) else a.get("username", "")
            if name.lower() == gitlab_user.lower():
                return "Assignee"
    return "Participant"


GITLAB_DASHBOARD_URL = "https://community.opengroup.org/"


def render_gitlab_section(
    my_mrs_data: dict | None,
    all_mrs_data: dict | None,
    now: datetime,
    mr_goal_tags: dict[int, list[str]] | None = None,
    gitlab_user: str = "",
) -> str:
    lines = [
        f"\n## [[osdu-platform|OSDU Platform]] · [GitLab Upstream]({GITLAB_DASHBOARD_URL})\n"
    ]

    # Your MRs — with correct role detection
    lines.append("> [!status] 🎯 Your MRs")
    my_mrs = []
    if my_mrs_data:
        for proj in my_mrs_data.get("data", {}).get("projects", []):
            for mr in proj.get("merge_requests", []):
                role = _detect_mr_role(mr, gitlab_user) if gitlab_user else "Author"
                my_mrs.append({
                    "iid": mr["iid"],
                    "service": proj["project_name"],
                    "role": role,
                    "pipeline": mr.get("latest_pipeline_status", "unknown"),
                    "url": mr["web_url"],
                    "created": utc_to_local_date(mr["created_at"]),
                    "title": mr.get("title", ""),
                })

    if my_mrs:
        lines.append("> | MR | Service | Role | Pipeline | Age |")
        lines.append("> |----|---------|------|----------|-----|")
        for mr in my_mrs:
            created = datetime.strptime(mr["created"], "%Y-%m-%d")
            age = (now.replace(tzinfo=None) - created).days
            pip = _pipeline_label(mr["pipeline"])
            goal_tag = ""
            if mr_goal_tags and mr["iid"] in mr_goal_tags:
                goal_tag = " 🎯 " + ", ".join(mr_goal_tags[mr["iid"]])
            lines.append(f"> | [!{mr['iid']}]({mr['url']}) | {mr['service']} | {mr['role']} | {pip} | {age}d |{goal_tag}")
    else:
        lines.append("> No open MRs.")
    lines.append("")

    # Items that need your attention
    review_needed = [m for m in my_mrs if m["role"] == "Reviewer"]
    action_needed = [m for m in my_mrs if m["role"] in ("Author", "Assignee")]
    if review_needed or action_needed:
        lines.append("> [!warning] Items that need your attention")
        for mr in review_needed:
            created = datetime.strptime(mr["created"], "%Y-%m-%d")
            age = (now.replace(tzinfo=None) - created).days
            lines.append(f"> - 👀 **Review requested** — [!{mr['iid']}]({mr['url']}) {mr['service']}: {mr['title'][:60]} ({age}d)")
        for mr in action_needed:
            pip = mr["pipeline"]
            if pip == "success":
                hint = "pipeline passing — merge candidate"
            elif pip == "failed":
                hint = "pipeline failing — needs fix"
            else:
                hint = f"pipeline {pip}"
            created = datetime.strptime(mr["created"], "%Y-%m-%d")
            age = (now.replace(tzinfo=None) - created).days
            lines.append(f"> - 🔧 **Your MR** — [!{mr['iid']}]({mr['url']}) {mr['service']}: {hint} ({age}d)")
        lines.append("")

    # Recent MRs
    lines.append("> [!pipeline] Recent MRs · last 21 days")
    cutoff = now.replace(tzinfo=None) - timedelta(days=21)
    my_iids = {m["iid"] for m in my_mrs}
    recent = []
    total_open = 0
    total_failed = 0
    services: set[str] = set()

    if all_mrs_data:
        for proj in all_mrs_data.get("data", {}).get("projects", []):
            for mr in proj.get("merge_requests", []):
                total_open += 1
                services.add(proj["project_name"])
                if mr.get("latest_pipeline_status") == "failed":
                    total_failed += 1
                created = datetime.strptime(utc_to_local_date(mr["created_at"]), "%Y-%m-%d")
                if created >= cutoff and mr["iid"] not in my_iids:
                    recent.append({
                        "iid": mr["iid"],
                        "service": proj["project_name"],
                        "author": mr["author"],
                        "pipeline": mr.get("latest_pipeline_status", "unknown"),
                        "created": utc_to_local_date(mr["created_at"]),
                        "url": mr["web_url"],
                    })

    if recent:
        recent.sort(key=lambda x: x["created"], reverse=True)
        lines.append("> | MR | Service | Author | Pipeline | Created |")
        lines.append("> |----|---------|--------|----------|---------|")
        for mr in recent[:10]:
            pip = _pipeline_label(mr["pipeline"])
            lines.append(f"> | [!{mr['iid']}]({mr['url']}) | {mr['service']} | @{mr['author']} | {pip} | {mr['created']} |")
    else:
        lines.append("> No recent MRs from other contributors.")
    lines.append(f">\n> **{total_open} open** across {len(services)} services · {total_failed} failing pipelines")
    lines.append("")

    return "\n".join(lines)



def render_goals(goals: list[dict]) -> str:
    """Render goals section with real progress from vault checkboxes."""
    lines = ["\n## Goals\n"]
    if not goals:
        lines.append("> [!abstract] No goals found in vault (`01-goals/`).")
        lines.append("")
        return "\n".join(lines)

    lines.append("> [!abstract] Progress")
    lines.append("> | Goal | Progress | Objectives |")
    lines.append("> |------|----------|------------|")
    for g in goals:
        done = g["total_done"]
        total = g["total_kr"]
        pct = int(done / total * 100) if total else 0
        bar_filled = round(pct / 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        if pct == 0:
            icon = "🔴"
        elif pct < 50:
            icon = "🟡"
        elif pct < 100:
            icon = "🟢"
        else:
            icon = "✅"
        # Brief objective summary
        obj_summary = " · ".join(
            f"{o['name']} ({o['done']}/{o['total']})" for o in g["objectives"]
        )
        quarter_tag = f" `{g['quarter']}`" if g["quarter"] else ""
        lines.append(
            f"> | {icon} {g['name']}{quarter_tag} | `{bar}` **{pct}%** ({done}/{total}) | {obj_summary} |"
        )
    lines.append("")

    # Per-goal detail callouts
    for g in goals:
        if not g["objectives"]:
            continue
        lines.append(f"> [!goal]- {g['name']}")
        for o in g["objectives"]:
            o_pct = int(o["done"] / o["total"] * 100) if o["total"] else 0
            o_icon = "✅" if o_pct == 100 else "🟡" if o_pct > 0 else "⬜"
            lines.append(f"> **{o['number']}. {o['name']}** — {o_icon} {o['done']}/{o['total']} key results")
            for kr in o["key_results"]:
                check = "x" if kr["done"] else " "
                lines.append(f">   - [{check}] {kr['text']}")
        # Show linked project status
        for proj in g.get("projects", []):
            lines.append(f"> 📋 **Project:** [[{proj['slug']}|{proj['name']}]] — {proj['phase']}")
            if proj["next_milestone"]:
                lines.append(f">   Next: {proj['next_milestone']}")
        lines.append("")

    return "\n".join(lines)


def render_projects(projects: list[dict], gh_tasks: list[dict]) -> str:
    """Render per-project operational sections."""
    if not projects and not gh_tasks:
        return ""

    lines = ["\n---\n"]
    for proj in projects:
        if proj["status"] != "active":
            continue
        lines.append(f"## [[{proj['slug']}|{proj['name']}]]\n")

        # Phase
        if proj["phase"]:
            lines.append(f"> **Phase:** {proj['phase']}")
        if proj["next_milestone"]:
            lines.append(f"> **Next:** {proj['next_milestone']}")
        lines.append("")

        # Active tasks
        if proj["active_tasks"]:
            done = proj["tasks_done"]
            total = proj["tasks_total"]
            lines.append(f"> [!todo] Tasks ({done}/{total} done)")
            for t in proj["active_tasks"]:
                check = "x" if t["done"] else " "
                lines.append(f"> - [{check}] {t['text']}")
            lines.append("")

        # Blockers
        if proj["blockers"]:
            lines.append("> [!danger] Blockers")
            for b in proj["blockers"]:
                lines.append(f"> - {b}")
            lines.append("")

    # GitHub Issues
    if gh_tasks:
        lines.append("> [!info] GitHub Issues (@me)")
        for t in gh_tasks:
            label_str = " · ".join(f"`{l}`" for l in t["labels"]) if t["labels"] else ""
            lines.append(f"> - [ ] **#{t['number']}** {t['title']} {label_str}")
        lines.append("")

    return "\n".join(lines)


def render_recommendations(
    my_mrs: list[dict],
    goals: list[dict],
    projects: list[dict],
    now: datetime,
) -> str:
    """Generate rule-based Top 3 Actions from collected data."""
    actions: list[tuple[int, str]] = []  # (priority_score, text)

    # Rule 1: Failing MRs — push the closest to green
    if my_mrs:
        failing = [m for m in my_mrs if _pipeline_is_actionable_failure(m.get("pipeline"))]
        if failing:
            actions.append((
                80,
                f"**Push MRs toward merge** — {len(failing)} MR{'s' if len(failing) > 1 else ''} "
                f"with failing pipelines. Check pipeline status and address blocking failures.",
            ))

    # Rule 2: Goals with low progress
    stalled_goals = [g for g in goals if g.get("total_done", 0) == 0 and g.get("total_kr", 0) > 0]
    if stalled_goals:
        actions.append((
            70,
            f"**Score a goal win** — {len(stalled_goals)} of {len(goals)} goals at 0%. "
            f"Pick the smallest actionable key result and close it to build momentum.",
        ))

    # Rule 3: Projects with blockers
    blocked_projects = [p for p in projects if p.get("blockers")]
    if blocked_projects:
        names = ", ".join(p["name"] for p in blocked_projects)
        actions.append((
            85,
            f"**Clear blockers** — {names} has blocking issues that need resolution.",
        ))

    if not actions:
        return ""

    actions.sort(key=lambda x: x[0], reverse=True)
    lines = ["\n## Recommendations\n"]
    lines.append("> [!tip] Top 3 Actions for Today")
    for idx, (_, text) in enumerate(actions[:3], 1):
        lines.append(f"> {idx}. {text}")
    lines.append("")
    return "\n".join(lines)


def render_risks(
    goals: list[dict],
    projects: list[dict],
    total_open_mrs: int,
    total_failed_mrs: int,
    now: datetime,
) -> str:
    """Detect and surface risks from collected data."""
    risks: list[str] = []

    # Risk 1: Goals with no progress
    stalled = [g for g in goals if g.get("total_done", 0) == 0 and g.get("total_kr", 0) > 0]
    if stalled:
        stalled_names = ", ".join(g["name"] for g in stalled)
        risks.append(
            f"{len(stalled)} goals at 0% ({stalled_names}) — need to start scoring wins to avoid end-of-quarter crunch."
        )

    # Risk 2: Systemic CI failure rate
    if total_open_mrs > 0:
        fail_rate = total_failed_mrs / total_open_mrs
        if fail_rate > 0.5:
            pct = int(fail_rate * 100)
            risks.append(
                f"{total_failed_mrs}/{total_open_mrs} upstream MRs failing ({pct}%) — "
                f"systemic CI issue may block all MRs regardless of code quality."
            )

    # Risk 3: Project blockers
    blocked = [p for p in projects if p.get("blockers")]
    if blocked:
        for p in blocked:
            risks.append(
                f"**{p['name']}** has {len(p['blockers'])} blocker(s): {', '.join(p['blockers'][:3])}"
            )

    if not risks:
        return ""

    lines = ["\n> [!warning] Risk"]
    for r in risks:
        lines.append(f"> - {r}")
    lines.append("")
    return "\n".join(lines)


def render_notes(
    my_mrs: list[dict],
) -> str:
    """Surface notable data points."""
    notes: list[str] = []

    # Note: MR nearest to merge
    for mr in my_mrs:
        if mr.get("pipeline") == "success":
            notes.append(f"!{mr['iid']} ({mr['service']}) pipeline passing — candidate for merge.")
            break

    if not notes:
        return ""

    lines = ["\n## Notes\n"]
    for n in notes:
        lines.append(f"- {n}")
    lines.append("")
    return "\n".join(lines)


def scan_brain_context(
    my_mrs: list[dict],
    goals: list[dict],
    projects: list[dict],
    now: datetime,
) -> str:
    """Scan brain knowledge to surface relevant context for today's briefing.

    Looks for recent reports, RCAs, decisions, and knowledge notes that relate
    to today's active MRs, goals, and projects. Provides raw material for the
    presenting agent to reason over.
    """
    vault = brain_path()
    if not vault.exists():
        return ""

    context_items: list[dict] = []  # {category, path, title, relevance, age_days}

    # Collect service names from MRs and project slugs for relevance matching
    active_services: set[str] = set()
    for mr in my_mrs:
        svc = mr.get("service", "").lower()
        if svc:
            active_services.add(svc)
            # Also add key fragments (e.g., "search-service" -> "search")
            for part in svc.split("-"):
                if len(part) > 3:
                    active_services.add(part)

    active_projects: set[str] = set()
    for proj in projects:
        slug = proj.get("slug", "").lower()
        if slug:
            active_projects.add(slug)
            for part in slug.split("-"):
                if len(part) > 3:
                    active_projects.add(part)

    for goal in goals:
        slug = goal.get("slug", "").lower()
        if slug:
            active_projects.add(slug)
            for part in slug.split("-"):
                if len(part) > 3:
                    active_projects.add(part)

    all_keywords = active_services | active_projects

    def _relevance_score(text: str, path_str: str) -> int:
        """Score how relevant a note is to today's active work."""
        combined = (text + " " + path_str).lower()
        return sum(1 for kw in all_keywords if kw in combined)

    def _extract_title(text: str, fallback: str) -> str:
        for line in text.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return fallback.replace("-", " ").title()

    def _file_age_days(path: Path) -> int:
        try:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=TIMEZONE)
            return (now - mtime).days
        except OSError:
            return 999

    # Scan 04-reports/ for recent reports (last 60 days)
    reports_dir = vault / "04-reports"
    if reports_dir.exists():
        for md_path in reports_dir.rglob("*.md"):
            age = _file_age_days(md_path)
            if age > 60:
                continue
            text = md_path.read_text(encoding="utf-8", errors="replace")[:500]
            score = _relevance_score(text, str(md_path))
            category = md_path.parent.name if md_path.parent != reports_dir else "report"
            context_items.append({
                "category": category,
                "path": str(md_path.relative_to(vault)),
                "title": _extract_title(text, md_path.stem),
                "score": score,
                "age_days": age,
                "type": "report",
            })

    # Scan 03-knowledge/ for relevant knowledge
    knowledge_dir = vault / "03-knowledge"
    if knowledge_dir.exists():
        for md_path in knowledge_dir.rglob("*.md"):
            text = md_path.read_text(encoding="utf-8", errors="replace")[:500]
            score = _relevance_score(text, str(md_path))
            if score == 0:
                continue  # Only include knowledge that relates to active work
            age = _file_age_days(md_path)
            subdomain = md_path.parent.name if md_path.parent != knowledge_dir else "general"
            context_items.append({
                "category": subdomain,
                "path": str(md_path.relative_to(vault)),
                "title": _extract_title(text, md_path.stem),
                "score": score,
                "age_days": age,
                "type": "knowledge",
            })

    if not context_items:
        return ""

    # Sort by relevance score (desc), then recency (asc)
    context_items.sort(key=lambda x: (-x["score"], x["age_days"]))

    # Render brain context section
    lines = ["\n## Brain Context\n"]
    lines.append("> [!brain] Knowledge relevant to today's briefing")
    lines.append("> The following vault notes relate to today's active MRs, goals, and projects.")
    lines.append("> Use these to inform insights and recommendations.")
    lines.append(">")

    # Group by type
    reports = [i for i in context_items if i["type"] == "report"]
    knowledge = [i for i in context_items if i["type"] == "knowledge"]

    if reports:
        lines.append("> **Recent Reports:**")
        for item in reports[:8]:
            age_str = f"{item['age_days']}d ago" if item['age_days'] < 30 else f"{item['age_days']}d"
            lines.append(f"> - [[{Path(item['path']).stem}|{item['title']}]] ({item['category']}, {age_str})")
        lines.append(">")

    if knowledge:
        lines.append("> **Related Knowledge:**")
        for item in knowledge[:8]:
            lines.append(f"> - [[{Path(item['path']).stem}|{item['title']}]] ({item['category']})")
        lines.append(">")

    lines.append("")
    return "\n".join(lines)


def render_delegation(
    my_mrs: list[dict],
    goals: list[dict],
    projects: list[dict],
    now: datetime,
) -> str:
    """Generate delegation recommendations routed to real agents."""
    items: list[tuple[int, str]] = []

    # Rule 1: Failing personal MRs → OSDU agent investigates pipeline
    failing_mrs = [m for m in my_mrs if _pipeline_is_actionable_failure(m.get("pipeline"))]
    for mr in failing_mrs:
        try:
            created = datetime.strptime(mr["created"], "%Y-%m-%d")
            age = (now.replace(tzinfo=None) - created).days
        except (ValueError, KeyError):
            age = 0
        items.append((
            90,
            f"**OSDU agent** → Investigate failing pipeline on !{mr['iid']} ({mr['service']}, {age}d old)",
        ))

    # Rule 2: Goals at 0% → Agent plans strategy
    stalled = [g for g in goals if g.get("total_done", 0) == 0 and g.get("total_kr", 0) > 0]
    for g in stalled:
        items.append((
            70,
            f"**Agent** → Plan key result acceleration for {g['name']}",
        ))

    # Rule 3: Projects with pending tasks → suggest next action
    for proj in projects:
        pending = [t for t in proj.get("active_tasks", []) if not t["done"]]
        if pending and proj["status"] == "active":
            items.append((
                60,
                f"**Manual** → Next task on {proj['name']}: {pending[0]['text']}",
            ))

    lines = ["\n## Delegation\n"]
    lines.append("> [!tip] What I'd Have the Agents Work On")
    if items:
        items.sort(key=lambda x: x[0], reverse=True)
        for idx, (_, text) in enumerate(items[:5], 1):
            lines.append(f"> {idx}. {text}")
    else:
        lines.append("> All clear — no delegation-routable actions detected.")
    lines.append("")
    return "\n".join(lines)


def render_footer(
    my_mrs: list[dict],
    goals: list[dict],
    projects: list[dict],
    total_open_mrs: int,
    total_failed_mrs: int,
    now: datetime,
) -> str:
    """Render all synthesis sections."""
    output = ""
    output += "\n---"
    output += render_recommendations(my_mrs, goals, projects, now)
    output += render_risks(goals, projects, total_open_mrs, total_failed_mrs, now)
    output += "\n---\n"
    output += render_delegation(my_mrs, goals, projects, now)
    return output


# ── Main ────────────────────────────────────────────────────────


def main() -> None:
    global GITLAB_USER

    parser = argparse.ArgumentParser(description="Generate daily briefing note")
    parser.add_argument("--dry-run", action="store_true", help="Print to stdout, don't write file")
    parser.add_argument("--date", help="Override date (YYYY-MM-DD)")
    args = parser.parse_args()

    root = workspace_root()

    env = _load_env()
    GITLAB_USER = env.get("GITLAB_USER", GITLAB_USER)

    now = datetime.now(TIMEZONE)
    if args.date:
        now = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=TIMEZONE)

    print("📋 Generating daily briefing...", file=sys.stderr)

    # ── Vault data ──
    print("  ↳ Vault: scanning goals...", file=sys.stderr)
    goals = scan_goals(root)

    print("  ↳ Vault: scanning projects...", file=sys.stderr)
    projects = scan_projects(root)
    link_goals_projects(goals, projects)

    # ── GitLab data ──
    print("  ↳ GitLab: your MRs...", file=sys.stderr)
    my_mrs_data = get_gitlab_mrs(user=GITLAB_USER)

    print("  ↳ GitLab: all MRs...", file=sys.stderr)
    all_mrs_data = get_gitlab_mrs()

    # ── GitHub tasks ──
    print("  ↳ GitHub: issues...", file=sys.stderr)
    gh_tasks = get_github_tasks()

    # ── CIMPL environment ──
    print("  ↳ Azure: CIMPL environment...", file=sys.stderr)
    cimpl_status = get_cimpl_env_status()

    # ── Parse MR data ──
    my_mrs_parsed: list[dict] = []
    all_mrs_parsed: list[dict] = []
    total_open_mrs = 0
    total_failed_mrs = 0

    if my_mrs_data:
        for proj in my_mrs_data.get("data", {}).get("projects", []):
            for mr in proj.get("merge_requests", []):
                role = _detect_mr_role(mr, GITLAB_USER)
                my_mrs_parsed.append({
                    "iid": mr["iid"],
                    "service": proj["project_name"],
                    "role": role,
                    "pipeline": mr.get("latest_pipeline_status", "unknown"),
                    "url": mr["web_url"],
                    "created": utc_to_local_date(mr["created_at"]),
                })

    if all_mrs_data:
        for proj in all_mrs_data.get("data", {}).get("projects", []):
            for mr in proj.get("merge_requests", []):
                total_open_mrs += 1
                if mr.get("latest_pipeline_status") == "failed":
                    total_failed_mrs += 1
                all_mrs_parsed.append({
                    "iid": mr["iid"],
                    "service": proj["project_name"],
                    "pipeline": mr.get("latest_pipeline_status", "unknown"),
                    "url": mr["web_url"],
                    "created": utc_to_local_date(mr["created_at"]),
                })

    # ── MR↔Goal correlation ──
    mr_goal_tags = build_mr_goal_tags(all_mrs_parsed, goals)

    # ── Render ──
    output = render_header(now)
    output += render_goals(goals)
    output += render_projects(projects, gh_tasks)
    output += "\n---"
    output += render_cimpl_section(cimpl_status)
    output += "\n---"
    output += render_gitlab_section(my_mrs_data, all_mrs_data, now, mr_goal_tags, gitlab_user=GITLAB_USER)
    output += render_notes(my_mrs_parsed)
    output += scan_brain_context(my_mrs_parsed, goals, projects, now)
    output += render_footer(
        my_mrs_parsed, goals, projects,
        total_open_mrs, total_failed_mrs, now,
    )

    # ── Session Digests placeholder ──
    output += "\n---\n\n## Session Digests\n\n<!-- Agent appends session digests below this line. -->\n"

    vault = brain_path()
    vault_exists = vault.exists() and (vault / "00-inbox").exists()

    if args.dry_run or not vault_exists:
        print(output)
        if not vault_exists and not args.dry_run:
            print(
                "  ℹ️  Brain vault not found — briefing printed to stdout only. "
                "Run 'init brain' to enable persistent briefings.",
                file=sys.stderr,
            )
    else:
        date_str = now.strftime("%Y-%m-%d")
        out_dir = vault / "00-inbox"
        out_path = out_dir / f"{date_str}.md"
        out_path.write_text(output, encoding="utf-8")
        print(f"  ✅ Written to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
