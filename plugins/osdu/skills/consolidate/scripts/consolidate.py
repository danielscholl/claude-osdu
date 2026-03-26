#!/usr/bin/env -S uv run --script
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
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "click>=8.0",
#   "rich>=13.0",
#   "pyyaml>=6.0",
# ]
# ///
"""Vault consolidation — detect stale and contradictory knowledge notes.

Scans 03-knowledge/ and 04-reports/ for notes that haven't been verified
in a configurable window (default 90 days). Human-corrected notes (source: human)
never decay.

Usage:
    uv run skills/consolidate/scripts/consolidate.py --dry-run
    uv run skills/consolidate/scripts/consolidate.py --age-days 60
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.table import Table


def _parse_frontmatter(path: Path) -> dict:
    """Extract YAML frontmatter from a markdown file."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end == -1:
        return {}
    try:
        return yaml.safe_load(text[3:end]) or {}
    except yaml.YAMLError:
        return {}


def _git_last_modified(path: Path) -> datetime | None:
    """Get last commit date for a file via git log."""
    try:
        result = subprocess.run(
            ["git", "log", "--format=%aI", "-1", "--", str(path)],
            capture_output=True,
            text=True,
            check=True,
        )
        date_str = result.stdout.strip()
        if date_str:
            return datetime.fromisoformat(date_str)
    except (subprocess.CalledProcessError, ValueError):
        pass
    return None


def _last_verified_date(fm: dict, path: Path) -> datetime | None:
    """Determine last-verified date from frontmatter or git history."""
    # Prefer explicit last-verified field
    lv = fm.get("last-verified")
    if lv:
        if isinstance(lv, datetime):
            return lv.replace(tzinfo=timezone.utc) if lv.tzinfo is None else lv
        try:
            return datetime.fromisoformat(str(lv)).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    # Fall back to git log
    return _git_last_modified(path)


def _is_human_source(fm: dict) -> bool:
    """Check if the note was human-corrected (never decays)."""
    source = fm.get("source", "")
    if isinstance(source, str):
        return source.strip().lower() == "human"
    return False


def scan_stale_notes(
    vault_path: Path, age_days: int, scan_dirs: list[str]
) -> list[dict]:
    """Scan vault directories for stale notes."""
    now = datetime.now(timezone.utc)
    results = []

    for dir_name in scan_dirs:
        scan_dir = vault_path / dir_name
        if not scan_dir.exists():
            continue

        for md_file in scan_dir.rglob("*.md"):
            fm = _parse_frontmatter(md_file)

            # Skip human-corrected notes
            if _is_human_source(fm):
                continue

            last_verified = _last_verified_date(fm, md_file)
            if last_verified is None:
                results.append(
                    {
                        "path": str(md_file.relative_to(vault_path)),
                        "status": "unknown",
                        "age_days": None,
                        "reason": "No last-verified date or git history",
                    }
                )
                continue

            age = (now - last_verified).days
            if age > age_days:
                results.append(
                    {
                        "path": str(md_file.relative_to(vault_path)),
                        "status": "stale",
                        "age_days": age,
                        "last_verified": last_verified.isoformat(),
                        "reason": f"Not verified in {age} days (threshold: {age_days})",
                    }
                )

    return results


def detect_contradictions(vault_path: Path) -> list[dict]:
    """Detect potential contradictions in decisions directory.

    Flags multiple active decisions with the same scope value.
    """
    decisions_dir = vault_path / "03-knowledge" / "decisions"
    if not decisions_dir.exists():
        return []

    # Group active decisions by scope
    scope_groups: dict[str, list[str]] = {}
    for md_file in decisions_dir.glob("*.md"):
        fm = _parse_frontmatter(md_file)
        if fm.get("status") != "active":
            continue
        scope = fm.get("scope", "")
        if scope:
            scope_groups.setdefault(scope, []).append(
                str(md_file.relative_to(vault_path))
            )

    contradictions = []
    for scope, files in scope_groups.items():
        if len(files) > 1:
            contradictions.append(
                {
                    "scope": scope,
                    "files": files,
                    "reason": f"{len(files)} active decisions share scope '{scope}'",
                }
            )

    return contradictions


@click.command()
@click.option(
    "--path",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to the Obsidian vault (default: $OSDU_BRAIN or ~/.osdu-brain)",
)
@click.option(
    "--age-days",
    type=int,
    default=90,
    help="Flag notes older than this many days (default: 90)",
)
@click.option(
    "--dry-run/--no-dry-run",
    default=True,
    help="Preview results without making changes (default: dry-run)",
)
def main(path: Path | None, age_days: int, dry_run: bool) -> None:
    """Scan the vault for stale knowledge and contradictions."""
    if path is None:
        env = os.environ.get("OSDU_BRAIN")
        path = Path(env).expanduser().resolve() if env else Path.home() / ".osdu-brain"
    if not path.exists():
        click.echo(f"Error: vault not found at {path}", err=True)
        raise SystemExit(1)

    console = Console(stderr=True)

    if dry_run:
        console.print("[dim]DRY RUN — no changes will be made[/dim]\n")

    # Scan stale notes
    stale = scan_stale_notes(path, age_days, ["03-knowledge", "04-reports"])

    if stale:
        table = Table(title=f"Stale Notes (>{age_days} days)")
        table.add_column("Path", style="cyan")
        table.add_column("Status", style="yellow")
        table.add_column("Age (days)", justify="right")
        table.add_column("Reason")

        for item in stale:
            table.add_row(
                item["path"],
                item["status"],
                str(item["age_days"] or "?"),
                item["reason"],
            )
        console.print(table)
    else:
        console.print(f"[green]No stale notes found (threshold: {age_days} days)[/green]")

    # Detect contradictions
    contradictions = detect_contradictions(path)

    if contradictions:
        console.print()
        ctable = Table(title="Potential Contradictions")
        ctable.add_column("Scope", style="magenta")
        ctable.add_column("Files", style="cyan")
        ctable.add_column("Reason")

        for item in contradictions:
            ctable.add_row(
                item["scope"],
                "\n".join(item["files"]),
                item["reason"],
            )
        console.print(ctable)
    else:
        console.print("[green]No contradictions detected[/green]")

    # JSON output to stdout
    output = {
        "stale_notes": stale,
        "contradictions": contradictions,
        "config": {"age_days": age_days, "vault_path": str(path), "dry_run": dry_run},
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
