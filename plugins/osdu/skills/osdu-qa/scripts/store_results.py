# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx",
#     "rich",
# ]
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
"""
OSDU QA Result Storage

Store and retrieve historical test results for trend analysis and comparison.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

# Add parent directory to path for common imports
sys.path.insert(0, str(Path(__file__).parent))
from common import SKILL_DIR, RESULTS_DIR

console = Console()


def save_results(results: dict, environment: str) -> Path:
    """Save test results to history.

    Args:
        results: Test results dictionary
        environment: Environment name (e.g., 'cimpl/temp')

    Returns:
        Path to saved file
    """
    RESULTS_DIR.mkdir(exist_ok=True)

    # Sanitize environment name for filename
    env_safe = environment.replace("/", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{env_safe}.json"
    filepath = RESULTS_DIR / filename

    # Add metadata
    results["_saved_at"] = datetime.now().isoformat()
    results["_environment"] = environment

    filepath.write_text(json.dumps(results, indent=2))
    console.print(f"[green]Results saved:[/green] {filepath}")
    return filepath


def get_history(environment: Optional[str] = None, limit: int = 10) -> list[dict]:
    """Retrieve historical results.

    Args:
        environment: Filter by environment (optional)
        limit: Maximum number of results to return

    Returns:
        List of result dictionaries
    """
    if not RESULTS_DIR.exists():
        return []

    files = sorted(RESULTS_DIR.glob("*.json"), reverse=True)

    if environment:
        env_pattern = environment.replace("/", "_")
        files = [f for f in files if env_pattern in f.name]

    results = []
    for f in files[:limit]:
        try:
            results.append(json.loads(f.read_text()))
        except json.JSONDecodeError:
            continue

    return results


def compare_with_baseline(current: dict, baseline: dict) -> dict:
    """Compare current results with baseline.

    Args:
        current: Current test results
        baseline: Baseline test results

    Returns:
        Comparison results with regressions and improvements
    """
    regressions = []
    improvements = []
    unchanged = []

    current_collections = {c.get("name"): c for c in current.get("collections", [])}
    baseline_collections = {c.get("name"): c for c in baseline.get("collections", [])}

    for name, curr in current_collections.items():
        if name not in baseline_collections:
            continue

        base = baseline_collections[name]
        curr_failed = curr.get("assertions", {}).get("failed", 0)
        base_failed = base.get("assertions", {}).get("failed", 0)

        if curr_failed > base_failed:
            regressions.append({
                "collection": name,
                "current_failures": curr_failed,
                "baseline_failures": base_failed,
                "delta": curr_failed - base_failed
            })
        elif curr_failed < base_failed:
            improvements.append({
                "collection": name,
                "current_failures": curr_failed,
                "baseline_failures": base_failed,
                "delta": base_failed - curr_failed
            })
        else:
            unchanged.append(name)

    return {
        "regressions": regressions,
        "improvements": improvements,
        "unchanged": unchanged,
        "summary": {
            "regressions_count": len(regressions),
            "improvements_count": len(improvements),
            "unchanged_count": len(unchanged)
        }
    }


def get_trends(environment: str, days: int = 7) -> list[dict]:
    """Get trends for an environment over time.

    Args:
        environment: Environment to analyze
        days: Number of days to look back

    Returns:
        List of daily summaries
    """
    history = get_history(environment, limit=days * 5)  # Assume max 5 runs per day

    # Group by date
    by_date = {}
    for result in history:
        date = result.get("timestamp", "")[:10]
        if date not in by_date:
            by_date[date] = []
        by_date[date].append(result)

    # Calculate daily stats
    trends = []
    for date in sorted(by_date.keys(), reverse=True)[:days]:
        runs = by_date[date]
        # Take the last run of the day
        latest = runs[0]
        summary = latest.get("summary", {})
        trends.append({
            "date": date,
            "pass_rate": summary.get("pass_rate", 0),
            "passed": summary.get("collections_passed", 0),
            "failed": summary.get("collections_failed", 0),
            "runs": len(runs)
        })

    return trends


def show_history(environment: Optional[str] = None, limit: int = 10):
    """Display test history in a table."""
    history = get_history(environment, limit)

    if not history:
        console.print("[yellow]No historical results found.[/yellow]")
        return

    table = Table(title="Test History")
    table.add_column("Date", style="cyan")
    table.add_column("Environment", style="blue")
    table.add_column("Pass Rate", justify="right")
    table.add_column("Passed", justify="right", style="green")
    table.add_column("Failed", justify="right", style="red")

    for result in history:
        timestamp = result.get("timestamp", "")[:19]
        env = result.get("environment", result.get("_environment", "unknown"))
        summary = result.get("summary", {})
        pass_rate = summary.get("pass_rate", 0)
        passed = summary.get("collections_passed", 0)
        failed = summary.get("collections_failed", 0)

        table.add_row(
            timestamp,
            env,
            f"{pass_rate:.1f}%",
            str(passed),
            str(failed)
        )

    console.print(table)


def show_trends(environment: str, days: int = 7):
    """Display trend analysis."""
    trends = get_trends(environment, days)

    if not trends:
        console.print(f"[yellow]No trends found for {environment}[/yellow]")
        return

    table = Table(title=f"Trends: {environment} (Last {days} days)")
    table.add_column("Date", style="cyan")
    table.add_column("Pass Rate", justify="right")
    table.add_column("Passed", justify="right", style="green")
    table.add_column("Failed", justify="right", style="red")
    table.add_column("Trend", justify="center")

    prev_rate = None
    for trend in trends:
        rate = trend["pass_rate"]
        if prev_rate is not None:
            if rate > prev_rate:
                trend_icon = "⬆️"
            elif rate < prev_rate:
                trend_icon = "⬇️"
            else:
                trend_icon = "➡️"
        else:
            trend_icon = "➡️"

        table.add_row(
            trend["date"],
            f"{rate:.1f}%",
            str(trend["passed"]),
            str(trend["failed"]),
            trend_icon
        )
        prev_rate = rate

    console.print(table)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="OSDU QA Result Storage")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # History command
    history_parser = subparsers.add_parser("history", help="Show test history")
    history_parser.add_argument("-e", "--environment", help="Filter by environment")
    history_parser.add_argument("-n", "--limit", type=int, default=10, help="Number of results")

    # Trends command
    trends_parser = subparsers.add_parser("trends", help="Show trends")
    trends_parser.add_argument("environment", help="Environment to analyze")
    trends_parser.add_argument("-d", "--days", type=int, default=7, help="Number of days")

    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare results")
    compare_parser.add_argument("current", type=Path, help="Current results file")
    compare_parser.add_argument("baseline", type=Path, help="Baseline results file")

    args = parser.parse_args()

    if args.command == "history":
        show_history(args.environment, args.limit)
    elif args.command == "trends":
        show_trends(args.environment, args.days)
    elif args.command == "compare":
        current = json.loads(args.current.read_text())
        baseline = json.loads(args.baseline.read_text())
        comparison = compare_with_baseline(current, baseline)
        console.print_json(json.dumps(comparison, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
