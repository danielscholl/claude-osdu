# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "click",
#     "rich",
#     "httpx",
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
OSDU QA Newman Test Runner

Execute Postman collections with automatic authentication and AI-friendly results.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add parent directory to path for common imports
sys.path.insert(0, str(Path(__file__).parent))
from common import SKILL_DIR, get_config, validate_config, get_access_token, get_repo_path

console = Console()

MANIFEST_FILE = SKILL_DIR / "config" / "manifest.json"


def load_manifest() -> dict | None:
    """Load manifest from file."""
    if not MANIFEST_FILE.exists():
        return None
    try:
        with open(MANIFEST_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def find_collection_in_manifest(manifest: dict, collection_id: str) -> dict | None:
    """Find a collection by ID in the manifest."""
    collection_id_lower = collection_id.lower()

    # Exact match first
    for coll in manifest["collections"]:
        if coll["id"].lower() == collection_id_lower:
            return coll

    # Partial match
    matches = [c for c in manifest["collections"] if collection_id_lower in c["id"].lower()]
    if len(matches) == 1:
        return matches[0]

    return None


def find_environment_for_platform(manifest: dict, platform: str) -> dict | None:
    """Find environment file for a platform."""
    platform_lower = platform.lower()
    for env in manifest["environments"]:
        if env["platform"] == platform_lower:
            return env
    return None


def check_newman_installed() -> bool:
    """Check if newman is installed."""
    try:
        result = subprocess.run(
            ["newman", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def parse_newman_results(results_file: Path) -> dict:
    """Parse Newman JSON results into AI-friendly summary."""
    with open(results_file) as f:
        results = json.load(f)

    run = results.get("run", {})
    stats = run.get("stats", {})
    timings = run.get("timings", {})

    # Extract execution stats
    assertions = stats.get("assertions", {})
    requests = stats.get("requests", {})

    # Collect failures
    failures = []
    for execution in run.get("executions", []):
        for assertion in execution.get("assertions", []):
            if assertion.get("error"):
                failures.append({
                    "request": execution.get("item", {}).get("name", "Unknown"),
                    "assertion": assertion.get("assertion", "Unknown"),
                    "error": assertion.get("error", {}).get("message", "Unknown error"),
                })

    return {
        "summary": {
            "total_requests": requests.get("total", 0),
            "failed_requests": requests.get("failed", 0),
            "total_assertions": assertions.get("total", 0),
            "passed_assertions": assertions.get("total", 0) - assertions.get("failed", 0),
            "failed_assertions": assertions.get("failed", 0),
            "duration_ms": timings.get("completed", 0) - timings.get("started", 0),
        },
        "failures": failures,
        "passed": assertions.get("failed", 0) == 0,
    }


def display_results(results: dict, collection_name: str):
    """Display test results in AI-friendly format."""
    summary = results["summary"]
    passed = results["passed"]

    # Status panel
    status_color = "green" if passed else "red"
    status_text = "PASSED" if passed else "FAILED"

    console.print(Panel(
        f"[bold {status_color}]{status_text}[/bold {status_color}]",
        title=collection_name,
        subtitle=f"Duration: {summary['duration_ms']}ms",
    ))

    # Stats table
    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")

    table.add_row("Requests", f"{summary['total_requests'] - summary['failed_requests']}/{summary['total_requests']}")
    table.add_row("Assertions", f"{summary['passed_assertions']}/{summary['total_assertions']}")

    console.print(table)

    # Failures
    if results["failures"]:
        console.print("\n[bold red]Failures:[/bold red]")
        for i, failure in enumerate(results["failures"][:10], 1):
            console.print(f"\n  {i}. [cyan]{failure['request']}[/cyan]")
            console.print(f"     Assertion: {failure['assertion']}")
            console.print(f"     Error: [red]{failure['error']}[/red]")

        if len(results["failures"]) > 10:
            console.print(f"\n  ... and {len(results['failures']) - 10} more failures")


@click.group()
def cli():
    """OSDU QA Newman Test Runner."""
    pass


@cli.command()
@click.argument("collection_id")
@click.option("--platform", "-p", default="azure", help="Platform (azure, aws, gcp, ibm, cimpl)")
@click.option("--folder", "-f", help="Run specific folder within collection")
@click.option("--dry-run", is_flag=True, help="Show command without executing")
@click.option("--json", "output_json", is_flag=True, help="Output results as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Show Newman CLI output")
def execute(collection_id: str, platform: str, folder: str | None, dry_run: bool, output_json: bool, verbose: bool):
    """Execute a collection with automatic authentication.

    COLLECTION_ID can be the full folder name (e.g., 11_CICD_Setup_LegalAPI)
    or a partial match (e.g., Legal).
    """
    # Load manifest
    manifest = load_manifest()
    if not manifest:
        console.print("[red]Error:[/red] No manifest found.")
        console.print("Run: uv run skills/osdu-qa/scripts/manifest.py generate")
        raise SystemExit(1)

    # Find collection
    collection = find_collection_in_manifest(manifest, collection_id)
    if not collection:
        console.print(f"[red]Error:[/red] Collection '{collection_id}' not found.")
        console.print("Run: uv run skills/osdu-qa/scripts/manifest.py list")
        raise SystemExit(1)

    # Find environment
    environment = find_environment_for_platform(manifest, platform)
    if not environment:
        console.print(f"[red]Error:[/red] No environment found for platform '{platform}'.")
        console.print(f"Available platforms: {', '.join(manifest['summary']['platforms'])}")
        raise SystemExit(1)

    # Validate folder if specified
    if folder and folder not in collection["folders"]:
        # Try partial match
        matches = [f for f in collection["folders"] if folder.lower() in f.lower()]
        if len(matches) == 1:
            folder = matches[0]
        elif matches:
            console.print(f"[red]Error:[/red] Ambiguous folder '{folder}'. Matches:")
            for m in matches:
                console.print(f"  - {m}")
            raise SystemExit(1)
        else:
            console.print(f"[red]Error:[/red] Folder '{folder}' not found in collection.")
            console.print("Available folders:")
            for f in collection["folders"]:
                console.print(f"  - {f}")
            raise SystemExit(1)

    # Check newman
    if not check_newman_installed():
        console.print("[red]Error:[/red] Newman is not installed.")
        console.print("Install with: npm install -g newman")
        raise SystemExit(1)

    # Get configuration and token
    config = get_config(platform)
    missing = validate_config(config)
    if missing:
        console.print("[red]Error:[/red] Missing configuration:")
        for var in missing:
            console.print(f"  export {var}=...")
        raise SystemExit(1)

    if not output_json and not dry_run:
        console.print(f"[blue]Authenticating...[/blue]")

    try:
        token = get_access_token(config)
    except Exception as e:
        console.print(f"[red]Error:[/red] Authentication failed: {e}")
        raise SystemExit(1)

    # Build paths
    repo_path = Path(manifest["repo_path"])
    collection_path = repo_path / collection["path"]
    environment_path = repo_path / environment["path"]

    # Build Newman command
    cmd = [
        "newman", "run", str(collection_path),
        "-e", str(environment_path),
        "--env-var", f"access_token={token}",
        "--reporters", "cli,json",
    ]

    if folder:
        cmd.extend(["--folder", folder])

    # Add JSON reporter output
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        results_file = Path(tmp.name)

    cmd.extend(["--reporter-json-export", str(results_file)])

    if dry_run:
        # Redact token in dry run output
        display_cmd = cmd.copy()
        for i, arg in enumerate(display_cmd):
            if arg.startswith("access_token="):
                display_cmd[i] = "access_token=[REDACTED]"

        console.print("[bold]Dry run - command would be:[/bold]")
        console.print(" ".join(display_cmd))
        return

    # Execute Newman
    if not output_json:
        console.print(f"[blue]Running:[/blue] {collection['name']}")
        if folder:
            console.print(f"[blue]Folder:[/blue] {folder}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=not verbose,
            text=True,
            timeout=600,  # 10 minute timeout
            cwd=str(repo_path),  # Run from qa repo root so relative file paths resolve
        )
    except subprocess.TimeoutExpired:
        console.print("[red]Error:[/red] Test execution timed out (10 minutes)")
        raise SystemExit(1)

    # Parse results
    if results_file.exists():
        try:
            results = parse_newman_results(results_file)
        except Exception as e:
            console.print(f"[yellow]Warning:[/yellow] Could not parse results: {e}")
            results = None
        finally:
            results_file.unlink()  # Clean up temp file
    else:
        results = None

    if output_json:
        if results:
            console.print_json(json.dumps(results))
        else:
            console.print_json(json.dumps({"error": "Could not parse results"}))
        raise SystemExit(0 if results and results["passed"] else 1)

    # Display results
    if results:
        console.print()
        display_results(results, collection["name"])
    else:
        console.print("\n[yellow]Results could not be parsed.[/yellow]")
        if result.returncode != 0:
            console.print("[red]Newman exited with errors.[/red]")

    raise SystemExit(0 if results and results["passed"] else 1)


@cli.command("list-folders")
@click.argument("collection_id")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def list_folders(collection_id: str, output_json: bool):
    """List folders in a collection."""
    manifest = load_manifest()
    if not manifest:
        console.print("[red]Error:[/red] No manifest found.")
        raise SystemExit(1)

    collection = find_collection_in_manifest(manifest, collection_id)
    if not collection:
        console.print(f"[red]Error:[/red] Collection '{collection_id}' not found.")
        raise SystemExit(1)

    if output_json:
        console.print_json(json.dumps(collection["folders"]))
        return

    console.print(f"\n[bold]{collection['name']}[/bold]")
    console.print(f"Folders ({len(collection['folders'])}):")
    for folder in collection["folders"]:
        console.print(f"  - {folder}")


if __name__ == "__main__":
    cli()
