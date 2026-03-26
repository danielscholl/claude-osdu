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
OSDU QA Test - Unified CLI

Run OSDU API tests with automatic authentication and AI-friendly results.

Commands:
    list     - List available test collections
    run      - Execute tests
    status   - Check prerequisites and last run
    analyze  - Debug failures from history
    history  - Show recent test runs
"""

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add parent directory to path for common imports
sys.path.insert(0, str(Path(__file__).parent))
from common import (
    SKILL_DIR,
    CONFIG_DIR,
    SERVICE_ALIASES,
    TIER_ALIASES,
    resolve_collection_aliases,
    get_config,
    validate_config,
    get_access_token,
    get_repo_path,
    clear_token_cache,
    load_manifest,
    find_collection_by_id,
    find_environment_by_platform,
    save_run_result,
    get_run_history,
    get_last_run,
    get_last_failure,
    clear_history,
    get_active_environment,
    get_collections_live,
    _get_repo_path_with_fallback,
    check_environment_health,
)

console = Console()


# =============================================================================
# Helper Functions
# =============================================================================

def check_newman_installed() -> tuple[bool, str]:
    """Check if newman is installed."""
    try:
        result = subprocess.run(
            ["newman", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, "Command failed"
    except FileNotFoundError:
        return False, "Not installed"
    except subprocess.TimeoutExpired:
        return False, "Timeout"


def parse_newman_results(results_file: Path) -> dict:
    """Parse Newman JSON results into summary."""
    with open(results_file) as f:
        results = json.load(f)

    run = results.get("run", {})
    stats = run.get("stats", {})
    timings = run.get("timings", {})

    assertions = stats.get("assertions", {})
    requests = stats.get("requests", {})

    failures = []
    for execution in run.get("executions", []):
        item_name = execution.get("item", {}).get("name", "Unknown")
        request_info = execution.get("request", {})
        response_info = execution.get("response", {})

        for assertion in execution.get("assertions", []):
            if assertion.get("error"):
                failures.append({
                    "request": item_name,
                    "method": request_info.get("method", ""),
                    "url": request_info.get("url", {}).get("raw", ""),
                    "assertion": assertion.get("assertion", "Unknown"),
                    "error": assertion.get("error", {}).get("message", "Unknown error"),
                    "status_code": response_info.get("code"),
                    "response_time": response_info.get("responseTime"),
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


def display_results(results: dict, collection_name: str, folder: str | None = None):
    """Display test results."""
    summary = results["summary"]
    passed = results["passed"]

    status_color = "green" if passed else "red"
    status_text = "PASSED" if passed else "FAILED"

    subtitle = f"Duration: {summary['duration_ms']}ms"
    if folder:
        subtitle = f"Folder: {folder} | {subtitle}"

    console.print(Panel(
        f"[bold {status_color}]{status_text}[/bold {status_color}]",
        title=collection_name,
        subtitle=subtitle,
    ))

    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")
    table.add_row("Requests", f"{summary['total_requests'] - summary['failed_requests']}/{summary['total_requests']}")
    table.add_row("Assertions", f"{summary['passed_assertions']}/{summary['total_assertions']}")
    console.print(table)

    if results["failures"]:
        console.print("\n[bold red]Failures:[/bold red]")
        for i, failure in enumerate(results["failures"][:5], 1):
            console.print(f"\n  {i}. [cyan]{failure['request']}[/cyan]")
            if failure.get("method") and failure.get("url"):
                console.print(f"     {failure['method']} {failure['url'][:60]}...")
            console.print(f"     Assertion: {failure['assertion']}")
            console.print(f"     Error: [red]{failure['error']}[/red]")

        if len(results["failures"]) > 5:
            console.print(f"\n  ... and {len(results['failures']) - 5} more failures")
            console.print("  Run [cyan]analyze[/cyan] for full details")


# =============================================================================
# CLI Commands
# =============================================================================

@click.group()
@click.version_option(version="1.0.0", prog_name="osdu-test")
def cli():
    """OSDU QA Test Runner - AI-friendly test execution."""
    pass


@cli.command("list")
@click.argument("service", required=False)
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def list_collections(service: str | None, output_json: bool):
    """List available test collections.

    Optionally filter by SERVICE name (e.g., 'legal', 'storage').
    Scans the repository live to ensure collections are always up-to-date.
    """
    repo_path = _get_repo_path_with_fallback()
    if not repo_path:
        console.print("[red]Error:[/red] QA repository not found.")
        console.print("Ensure ~/workspace/qa exists or run from within the repo.")
        raise SystemExit(1)

    collections = get_collections_live(repo_path)
    if not collections:
        console.print("[red]Error:[/red] No collections found in repository.")
        raise SystemExit(1)

    if service:
        service_lower = service.lower()
        collections = [c for c in collections
                       if service_lower in c["service"].lower()
                       or service_lower in c["id"].lower()]

    if output_json:
        console.print_json(json.dumps(collections))
        return

    if not collections:
        console.print(f"[yellow]No collections found matching '{service}'[/yellow]")
        return

    table = Table(title="OSDU Test Collections")
    table.add_column("ID", style="cyan", max_width=25)
    table.add_column("Service", style="green")
    table.add_column("Name", max_width=35)
    table.add_column("Tests", justify="right")

    for coll in collections:
        table.add_row(
            coll["id"][:25],
            coll["service"],
            coll["name"][:35],
            str(coll["test_count"]),
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(collections)} collections[/dim]")
    console.print(f"[dim]Source: {repo_path}[/dim]")
    console.print("[dim]Use: osdu_test.py run <ID> to execute[/dim]")


@cli.command()
@click.argument("target")
@click.option("--folder", "-f", help="Run specific folder within collection")
@click.option("--environment", "-e", "env_target", help="Target environment (platform/env, e.g., 'azure/ship', 'cimpl/qa'). Enables parallel execution.")
@click.option("--platform", "-p", default=None, help="Platform (azure, cimpl, aws, gcp). Defaults to active environment. Deprecated: use --environment.")
@click.option("--timeout", "-t", default=1800, help="Timeout in seconds (default: 1800 = 30 minutes)")
@click.option("--skip-health-check", is_flag=True, help="Skip preflight health check")
@click.option("--dry-run", is_flag=True, help="Show command without executing")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Show Newman output")
def run(target: str, folder: str | None, env_target: str | None, platform: str | None, timeout: int, skip_health_check: bool, dry_run: bool, output_json: bool, verbose: bool):
    """Run tests for a collection.

    TARGET can be collection ID or service name (e.g., 'legal', 'LegalAPI').

    Use --environment (-e) to specify target environment explicitly for parallel execution:
        osdu_test.py run legal -e azure/ship
        osdu_test.py run legal -e cimpl/qa
    """
    # Parse environment target if provided (enables parallel execution)
    environment = None
    if env_target:
        if "/" not in env_target:
            console.print(f"[red]Error:[/red] Invalid environment format: {env_target}")
            console.print("Use format: [cyan]platform/environment[/cyan] (e.g., azure/ship, cimpl/qa)")
            raise SystemExit(1)
        platform, environment = env_target.split("/", 1)
    elif platform is None:
        # Resolve platform from active environment if not specified
        active = get_active_environment()
        if active:
            platform, environment = active
        else:
            platform = "azure"  # fallback default
    manifest = load_manifest()
    if not manifest:
        console.print("[red]Error:[/red] No manifest found. Run status first.")
        raise SystemExit(1)

    # Find collection
    collection = find_collection_by_id(target)
    if not collection:
        console.print(f"[red]Error:[/red] Collection '{target}' not found.")
        console.print("Run: [cyan]osdu_test.py list[/cyan] to see available")
        raise SystemExit(1)

    # Find Postman environment file (separate from environment name)
    postman_env = find_environment_by_platform(platform)
    if not postman_env:
        console.print(f"[red]Error:[/red] No environment for platform '{platform}'.")
        raise SystemExit(1)

    # Validate folder
    if folder:
        matches = [f for f in collection["folders"] if folder.lower() in f.lower()]
        if len(matches) == 1:
            folder = matches[0]
        elif len(matches) > 1:
            console.print(f"[red]Error:[/red] Ambiguous folder '{folder}':")
            for m in matches:
                console.print(f"  - {m}")
            raise SystemExit(1)
        elif not matches:
            console.print(f"[red]Error:[/red] Folder '{folder}' not found.")
            console.print("Available folders:")
            for f in collection["folders"]:
                console.print(f"  - {f}")
            raise SystemExit(1)

    # Check newman
    newman_ok, _ = check_newman_installed()
    if not newman_ok:
        console.print("[red]Error:[/red] Newman not installed. Run: npm install -g newman")
        raise SystemExit(1)

    # Get token - pass explicit environment for parallel execution support
    config = get_config(platform, environment)
    missing = validate_config(config)
    if missing:
        console.print("[red]Error:[/red] Missing configuration:")
        for var in missing:
            console.print(f"  export {var}=...")
        raise SystemExit(1)

    # Preflight health check (skip for dry-run)
    env_display = f"{platform}/{environment}" if environment else platform
    if not skip_health_check and not dry_run:
        if not output_json:
            console.print(f"[blue]Checking {env_display} health...[/blue]")
        health = check_environment_health(config, timeout=15.0)
        if not health["healthy"]:
            if output_json:
                console.print_json(json.dumps({"error": "health_check_failed", "details": health}))
            else:
                console.print(f"[red]Error:[/red] Environment {env_display} is not healthy")
                console.print(f"  Host: {health['host']}")
                console.print(f"  Auth: {'OK' if health['auth_ok'] else 'FAILED'}")
                console.print(f"  API: {'OK' if health['api_ok'] else 'FAILED'}")
                if health.get("error"):
                    console.print(f"  Error: [red]{health['error']}[/red]")
                console.print("\n[dim]Tip: Use --skip-health-check to bypass (not recommended)[/dim]")
            raise SystemExit(1)
        if not output_json:
            console.print(f"[green]Health OK[/green] ({health['response_time_ms']}ms)")

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
    environment_path = repo_path / postman_env["path"]

    # Build command
    # Pass all necessary env vars so Postman collection can authenticate
    # and use the correct host for the selected environment
    cmd = [
        "newman", "run", str(collection_path),
        "-e", str(environment_path),
        "--env-var", f"access_token={token}",
        "--env-var", f"CLIENT_ID={config['client_id']}",
        "--env-var", f"CLIENT_SECRET={config['client_secret']}",
        "--reporters", "cli,json",
    ]

    # Pass host and partition overrides so Newman uses the correct target
    # regardless of what's in the static Postman environment file
    if config.get("host"):
        cmd.extend(["--env-var", f"HOSTNAME={config['host']}"])
    if config.get("partition"):
        cmd.extend(["--env-var", f"data-partition-id={config['partition']}"])
    if config.get("tenant_id"):
        cmd.extend(["--env-var", f"TENANT_ID={config['tenant_id']}"])

    # Override grant_type and Scope so the collection's "Refresh Token" setup
    # request works with client_credentials (collections default to refresh_token)
    if config.get("auth_type") == "azure-ad":
        scope_id = config.get("resource_id") or config.get("client_id", "")
        scope_value = f"{scope_id}/.default"
        cmd.extend([
            "--env-var", "grant_type=client_credentials",
            "--env-var", f"Scope={scope_value}",
            "--env-var", f"scope={scope_value}",
        ])

    # Pass the environment name so host patterns resolve correctly
    # (e.g., HOSTNAME={{env}}.osdu-cimpl.opengroup.org)
    if config.get("environment"):
        cmd.extend(["--env-var", f"env={config['environment']}"])

    if folder:
        cmd.extend(["--folder", folder])

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        results_file = Path(tmp.name)
    cmd.extend(["--reporter-json-export", str(results_file)])

    if dry_run:
        display_cmd = cmd.copy()
        for i, arg in enumerate(display_cmd):
            if arg.startswith("access_token="):
                display_cmd[i] = "access_token=[REDACTED]"
            elif arg.startswith("CLIENT_SECRET="):
                display_cmd[i] = "CLIENT_SECRET=[REDACTED]"
            elif arg.startswith("TENANT_ID="):
                display_cmd[i] = "TENANT_ID=[REDACTED]"
        console.print("[bold]Command:[/bold]")
        console.print(" ".join(display_cmd))
        return

    if not output_json:
        console.print(f"[blue]Running:[/blue] {collection['name']}")
        if folder:
            console.print(f"[blue]Folder:[/blue] {folder}")

    # Execute
    try:
        result = subprocess.run(cmd, cwd=repo_path, capture_output=not verbose, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        timeout_mins = timeout // 60
        console.print(f"[red]Error:[/red] Timeout ({timeout_mins} minutes)")
        console.print("[dim]Tip: Use --timeout to increase (e.g., --timeout 3600 for 1 hour)[/dim]")
        raise SystemExit(1)

    # Parse results
    results = None
    if results_file.exists():
        try:
            results = parse_newman_results(results_file)
        except Exception as e:
            if not output_json:
                console.print(f"[yellow]Warning:[/yellow] Could not parse results: {e}")
        finally:
            results_file.unlink()

    # Save to history
    if results:
        history_entry = {
            "collection_id": collection["id"],
            "collection_name": collection["name"],
            "folder": folder,
            "platform": platform,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "passed": results["passed"],
            "summary": results["summary"],
            "failures": results["failures"],
        }
        save_run_result(history_entry)

    if output_json:
        console.print_json(json.dumps(results or {"error": "Could not parse"}))
        raise SystemExit(0 if results and results["passed"] else 1)

    if results:
        console.print()
        display_results(results, collection["name"], folder)
    else:
        console.print("[yellow]Results could not be parsed.[/yellow]")

    raise SystemExit(0 if results and results["passed"] else 1)


@cli.command()
@click.option("--environment", "-e", "env_target", help="Target environment (platform/env, e.g., 'azure/ship', 'cimpl/qa')")
@click.option("--platform", "-p", default=None, help="Platform to check. Deprecated: use --environment.")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def status(env_target: str | None, platform: str | None, output_json: bool):
    """Check prerequisites, auth status, and last run."""
    # Parse environment target if provided
    environment = None
    if env_target:
        if "/" not in env_target:
            console.print(f"[red]Error:[/red] Invalid environment format: {env_target}")
            console.print("Use format: [cyan]platform/environment[/cyan] (e.g., azure/ship, cimpl/qa)")
            raise SystemExit(1)
        platform, environment = env_target.split("/", 1)
    elif platform is None:
        # Resolve platform from active environment if not specified
        active = get_active_environment()
        if active:
            platform, environment = active
        else:
            platform = "azure"  # fallback default
    results = {}

    # Newman
    newman_ok, newman_msg = check_newman_installed()
    results["newman"] = {"ok": newman_ok, "message": newman_msg}

    # Repository - scan live (no cached manifest)
    repo_path = _get_repo_path_with_fallback()
    results["repository"] = {"ok": bool(repo_path), "message": str(repo_path) if repo_path else "Not found"}

    # Collections - scan live from repository
    if repo_path:
        collections = get_collections_live(repo_path)
        if collections:
            total_tests = sum(c["test_count"] for c in collections)
            results["collections"] = {"ok": True, "message": f"{len(collections)} collections, {total_tests} tests"}
        else:
            results["collections"] = {"ok": False, "message": "No collections found in repository"}
    else:
        results["collections"] = {"ok": False, "message": "Repository not found"}

    # Config - pass explicit environment for parallel execution support
    config = get_config(platform, environment)
    missing = validate_config(config)
    results["config"] = {"ok": not missing, "message": "Complete" if not missing else f"Missing: {', '.join(missing)}"}

    # Auth
    if not missing:
        try:
            get_access_token(config)
            results["auth"] = {"ok": True, "message": "Token valid"}
        except Exception as e:
            results["auth"] = {"ok": False, "message": str(e)}
    else:
        results["auth"] = {"ok": False, "message": "Skipped (config incomplete)"}

    # Last run
    last = get_last_run()
    if last:
        status_str = "passed" if last["passed"] else "FAILED"
        results["last_run"] = {
            "ok": last["passed"],
            "collection": last["collection_id"],
            "folder": last.get("folder"),
            "status": status_str,
            "timestamp": last["timestamp"],
        }
    else:
        results["last_run"] = None

    if output_json:
        console.print_json(json.dumps(results))
        return

    # Display
    env_display = f"{platform}/{environment}" if environment else platform
    table = Table(title=f"OSDU QA Status ({env_display})")
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    checks = [
        ("Newman CLI", results["newman"]),
        ("Repository", results["repository"]),
        ("Collections", results["collections"]),
        ("Configuration", results["config"]),
        ("Authentication", results["auth"]),
    ]

    for name, result in checks:
        status_icon = "[green]OK[/green]" if result["ok"] else "[red]FAIL[/red]"
        table.add_row(name, status_icon, result["message"])

    console.print(table)

    # Last run
    if last:
        console.print()
        status_color = "green" if last["passed"] else "red"
        console.print(f"[bold]Last Run:[/bold] [{status_color}]{results['last_run']['status']}[/{status_color}]")
        console.print(f"  Collection: {last['collection_id']}")
        if last.get("folder"):
            console.print(f"  Folder: {last['folder']}")
        console.print(f"  Time: {last['timestamp']}")

    all_ok = all(r["ok"] for r in [results["newman"], results["collections"], results["config"], results["auth"]])
    if all_ok:
        console.print("\n[bold green]Ready to run tests![/bold green]")
    else:
        console.print("\n[bold red]Some checks failed.[/bold red]")


@cli.command()
@click.option("--last", "show_last", is_flag=True, help="Analyze last failed run")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def analyze(show_last: bool, output_json: bool):
    """Analyze failures from test history.

    Shows detailed failure information for debugging.
    """
    if show_last:
        run = get_last_failure()
        if not run:
            console.print("[yellow]No failed runs in history.[/yellow]")
            return
    else:
        run = get_last_run()
        if not run:
            console.print("[yellow]No runs in history. Run some tests first.[/yellow]")
            return

    if output_json:
        console.print_json(json.dumps(run))
        return

    # Display header
    status_color = "green" if run["passed"] else "red"
    status_text = "PASSED" if run["passed"] else "FAILED"

    console.print(Panel(
        f"[bold {status_color}]{status_text}[/bold {status_color}]",
        title=f"Analysis: {run['collection_name']}",
        subtitle=f"Platform: {run['platform']} | {run['timestamp']}",
    ))

    # Summary
    summary = run["summary"]
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  Requests: {summary['total_requests'] - summary['failed_requests']}/{summary['total_requests']}")
    console.print(f"  Assertions: {summary['passed_assertions']}/{summary['total_assertions']}")
    console.print(f"  Duration: {summary['duration_ms']}ms")

    # Failures
    failures = run.get("failures", [])
    if not failures:
        console.print("\n[green]No failures to analyze.[/green]")
        return

    console.print(f"\n[bold red]Failures ({len(failures)}):[/bold red]")

    for i, failure in enumerate(failures, 1):
        console.print(f"\n[bold cyan]#{i} {failure['request']}[/bold cyan]")

        if failure.get("method") and failure.get("url"):
            console.print(f"  [dim]Request:[/dim] {failure['method']} {failure['url']}")

        if failure.get("status_code"):
            console.print(f"  [dim]Status:[/dim] {failure['status_code']}")

        if failure.get("response_time"):
            console.print(f"  [dim]Response Time:[/dim] {failure['response_time']}ms")

        console.print(f"  [dim]Assertion:[/dim] {failure['assertion']}")
        console.print(f"  [red]Error:[/red] {failure['error']}")

    # Suggestions
    console.print("\n[bold]Debugging Tips:[/bold]")
    console.print("  1. Check if the API endpoint is accessible")
    console.print("  2. Verify the test data exists (legal tags, records)")
    console.print("  3. Run with --verbose to see full Newman output")
    console.print(f"  4. Try running just the failing folder: --folder \"<folder>\"")


@cli.command()
@click.option("--limit", "-n", default=10, help="Number of entries to show")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def history(limit: int, output_json: bool):
    """Show recent test run history."""
    runs = get_run_history(limit)

    if not runs:
        console.print("[yellow]No test history found.[/yellow]")
        return

    if output_json:
        console.print_json(json.dumps(runs))
        return

    table = Table(title="Test Run History")
    table.add_column("#", style="dim")
    table.add_column("Collection")
    table.add_column("Folder")
    table.add_column("Status")
    table.add_column("Assertions")
    table.add_column("Time")

    for i, run in enumerate(runs, 1):
        status_color = "green" if run["passed"] else "red"
        status_text = "PASS" if run["passed"] else "FAIL"
        summary = run["summary"]

        table.add_row(
            str(i),
            run["collection_id"][:20],
            (run.get("folder") or "-")[:15],
            f"[{status_color}]{status_text}[/{status_color}]",
            f"{summary['passed_assertions']}/{summary['total_assertions']}",
            run["timestamp"][:19],
        )

    console.print(table)


@cli.command("clear-history")
def clear_history_cmd():
    """Clear test run history."""
    if clear_history():
        console.print("[green]History cleared.[/green]")
    else:
        console.print("[yellow]No history to clear.[/yellow]")


@cli.command("clear-cache")
def clear_cache_cmd():
    """Clear authentication token cache."""
    if clear_token_cache():
        console.print("[green]Token cache cleared.[/green]")
    else:
        console.print("[yellow]No cache to clear.[/yellow]")


# =============================================================================
# Command Aliases (for simpler CLI)
# =============================================================================

@cli.command("check")
@click.option("--environment", "-e", "env_target", help="Target environment (platform/env, e.g., 'azure/ship', 'cimpl/qa')")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.pass_context
def check(ctx, env_target: str | None, output_json: bool):
    """Check connectivity to OSDU (alias for status)."""
    ctx.invoke(status, env_target=env_target, output_json=output_json)


@cli.command("health")
@click.option("--environment", "-e", "env_target", help="Target environment (platform/env, e.g., 'azure/ship', 'cimpl/qa')")
@click.option("--all", "check_all", is_flag=True, help="Check all known environments")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def health(env_target: str | None, check_all: bool, output_json: bool):
    """Quick health check for OSDU environment(s).

    Performs a lightweight API call to verify environment responsiveness.
    Use this before running tests to detect connectivity issues early.
    """
    from common import ENVIRONMENTS_FILE

    environments_to_check = []

    if check_all:
        # Load all configured environments
        from common import load_environments as _load_envs
        env_data = _load_envs()
        for platform_name, platform in env_data.get("platforms", {}).items():
            for env_name in platform.get("environments", {}).keys():
                environments_to_check.append(f"{platform_name}/{env_name}")
        if not environments_to_check:
            console.print("[yellow]No environments configured.[/yellow]")
            console.print("Add one with: [cyan]/osdu-qa env add <platform>/<name> --host ... --partition ... --auth-type ...[/cyan]")
            raise SystemExit(1)
    elif env_target:
        environments_to_check = [env_target]
    else:
        # Use active environment
        active = get_active_environment()
        if active:
            environments_to_check = [f"{active[0]}/{active[1]}"]
        else:
            console.print("[red]Error:[/red] No environment specified. Use -e or --all")
            raise SystemExit(1)

    results = []
    for env in environments_to_check:
        if "/" not in env:
            console.print(f"[yellow]Skipping invalid environment: {env}[/yellow]")
            continue

        platform, environment = env.split("/", 1)
        config = get_config(platform, environment)
        missing = validate_config(config)

        if missing:
            result = {
                "environment": env,
                "healthy": False,
                "error": f"Missing config: {', '.join(missing)}",
            }
        else:
            if not output_json:
                console.print(f"[blue]Checking {env}...[/blue]", end=" ")
            result = check_environment_health(config, timeout=15.0)
            result["environment"] = env

        results.append(result)

        if not output_json:
            if result["healthy"]:
                console.print(f"[green]OK[/green] ({result.get('response_time_ms', '?')}ms)")
            else:
                console.print(f"[red]FAILED[/red] - {result.get('error', 'Unknown error')}")

    if output_json:
        console.print_json(json.dumps(results if check_all or len(results) > 1 else results[0]))

    # Exit with error if any environment is unhealthy
    if not all(r["healthy"] for r in results):
        raise SystemExit(1)


@cli.command("test")
@click.argument("target")
@click.option("--folder", "-f", help="Run specific folder within collection")
@click.option("--environment", "-e", "env_target", help="Target environment (platform/env, e.g., 'azure/ship', 'cimpl/qa')")
@click.option("--timeout", "-t", default=1800, help="Timeout in seconds (default: 1800 = 30 minutes)")
@click.option("--skip-health-check", is_flag=True, help="Skip preflight health check")
@click.option("--json", "output_json", is_flag=True, help="Output results as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Show Newman output")
@click.pass_context
def test(ctx, target: str, folder: str | None, env_target: str | None, timeout: int, skip_health_check: bool, output_json: bool, verbose: bool):
    """Run tests for a service (alias for run).

    Use --environment (-e) for parallel execution against multiple environments:
        osdu_test.py test legal -e azure/ship
        osdu_test.py test legal -e cimpl/qa
    """
    ctx.invoke(run, target=target, folder=folder, env_target=env_target, platform=None, timeout=timeout, skip_health_check=skip_health_check, dry_run=False, output_json=output_json, verbose=verbose)


if __name__ == "__main__":
    cli()
