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
OSDU QA Test Status Checker

Check prerequisites, authentication, and API connectivity.
"""

import json
import subprocess
import sys
from pathlib import Path

import click
import httpx
from rich.console import Console
from rich.table import Table

# Add parent directory to path for common imports
sys.path.insert(0, str(Path(__file__).parent))
from common import (
    SKILL_DIR,
    get_config,
    validate_config,
    get_access_token,
    get_repo_path,
    clear_token_cache,
)

console = Console()

MANIFEST_FILE = SKILL_DIR / "config" / "manifest.json"


def check_newman() -> tuple[bool, str]:
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


def check_manifest() -> tuple[bool, str]:
    """Check if manifest exists and is valid."""
    if not MANIFEST_FILE.exists():
        return False, "Not found"
    try:
        with open(MANIFEST_FILE) as f:
            manifest = json.load(f)
        count = manifest.get("summary", {}).get("total_collections", 0)
        return True, f"{count} collections"
    except (json.JSONDecodeError, IOError) as e:
        return False, f"Invalid: {e}"


def check_repo() -> tuple[bool, str]:
    """Check if repository is detected."""
    repo = get_repo_path()
    if repo:
        return True, str(repo)
    return False, "Not detected"


def check_config(platform: str) -> tuple[bool, str, list[str]]:
    """Check if configuration is complete."""
    config = get_config(platform)
    missing = validate_config(config)
    if not missing:
        return True, "Complete", []
    return False, f"Missing {len(missing)} vars", missing


def check_api_connectivity(config: dict, token: str) -> tuple[bool, str]:
    """Check API connectivity by calling Legal service info endpoint."""
    host = config.get("host")
    partition = config.get("partition")

    if not host or not partition:
        return False, "Missing host/partition"

    url = f"https://{host}/api/legal/v1/info"
    headers = {
        "Authorization": f"Bearer {token}",
        "data-partition-id": partition,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, headers=headers)
            if response.status_code == 200:
                return True, "Connected"
            return False, f"HTTP {response.status_code}"
    except httpx.RequestError as e:
        return False, f"Request failed: {type(e).__name__}"


@click.group()
def cli():
    """OSDU QA Test Status Checker."""
    pass


@cli.command()
@click.option("--platform", "-p", default="azure", help="Platform to check")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def check(platform: str, output_json: bool):
    """Check all prerequisites and status."""
    results = {}

    # Check Newman
    newman_ok, newman_msg = check_newman()
    results["newman"] = {"ok": newman_ok, "message": newman_msg}

    # Check Repository
    repo_ok, repo_msg = check_repo()
    results["repository"] = {"ok": repo_ok, "message": repo_msg}

    # Check Manifest
    manifest_ok, manifest_msg = check_manifest()
    results["manifest"] = {"ok": manifest_ok, "message": manifest_msg}

    # Check Configuration
    config_ok, config_msg, missing_vars = check_config(platform)
    results["configuration"] = {
        "ok": config_ok,
        "message": config_msg,
        "missing": missing_vars,
    }

    # Check Authentication (only if config is complete)
    if config_ok:
        config = get_config(platform)
        try:
            token = get_access_token(config)
            results["authentication"] = {"ok": True, "message": "Token acquired"}

            # Check API connectivity
            api_ok, api_msg = check_api_connectivity(config, token)
            results["api_connectivity"] = {"ok": api_ok, "message": api_msg}
        except Exception as e:
            results["authentication"] = {"ok": False, "message": str(e)}
            results["api_connectivity"] = {"ok": False, "message": "Skipped (no token)"}
    else:
        results["authentication"] = {"ok": False, "message": "Skipped (config incomplete)"}
        results["api_connectivity"] = {"ok": False, "message": "Skipped (config incomplete)"}

    # Calculate overall status
    all_ok = all(r["ok"] for r in results.values())
    results["overall"] = {"ok": all_ok, "platform": platform}

    if output_json:
        console.print_json(json.dumps(results))
        raise SystemExit(0 if all_ok else 1)

    # Display table
    table = Table(title=f"OSDU QA Status ({platform})")
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    checks = [
        ("Newman CLI", results["newman"]),
        ("Repository", results["repository"]),
        ("Manifest", results["manifest"]),
        ("Configuration", results["configuration"]),
        ("Authentication", results["authentication"]),
        ("API Connectivity", results["api_connectivity"]),
    ]

    for name, result in checks:
        status = "[green]OK[/green]" if result["ok"] else "[red]FAIL[/red]"
        table.add_row(name, status, result["message"])

    console.print(table)

    # Show missing vars if any
    if missing_vars:
        console.print("\n[yellow]Missing environment variables:[/yellow]")
        for var in missing_vars:
            console.print(f"  export {var}=...")

    # Overall status
    if all_ok:
        console.print("\n[bold green]All checks passed![/bold green]")
    else:
        console.print("\n[bold red]Some checks failed.[/bold red]")

    raise SystemExit(0 if all_ok else 1)


@cli.command()
@click.argument("platform", default="azure")
@click.option("--force", "-f", is_flag=True, help="Force new token (ignore cache)")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def auth(platform: str, force: bool, output_json: bool):
    """Test authentication for a platform."""
    config = get_config(platform)
    missing = validate_config(config)

    if missing:
        if output_json:
            console.print_json(json.dumps({
                "success": False,
                "error": "missing_config",
                "missing": missing,
            }))
        else:
            console.print("[red]Error:[/red] Missing configuration:")
            for var in missing:
                console.print(f"  export {var}=...")
        raise SystemExit(1)

    if force:
        clear_token_cache()
        if not output_json:
            console.print("[blue]Cleared token cache[/blue]")

    if not output_json:
        console.print(f"[blue]Authenticating to {platform}...[/blue]")

    try:
        token = get_access_token(config, force_refresh=force)

        if output_json:
            console.print_json(json.dumps({
                "success": True,
                "platform": platform,
                "token_preview": token[:20] + "..." if len(token) > 20 else token,
            }))
        else:
            console.print(f"[green]Authentication successful![/green]")
            console.print(f"Token: {token[:50]}...")

            # Test API
            console.print("\n[blue]Testing API connectivity...[/blue]")
            api_ok, api_msg = check_api_connectivity(config, token)
            if api_ok:
                console.print(f"[green]API connectivity OK[/green]")
            else:
                console.print(f"[yellow]API connectivity: {api_msg}[/yellow]")

    except Exception as e:
        if output_json:
            console.print_json(json.dumps({
                "success": False,
                "error": "auth_failed",
                "message": str(e),
            }))
        else:
            console.print(f"[red]Authentication failed:[/red] {e}")
        raise SystemExit(1)


@cli.command()
def clear_cache():
    """Clear the authentication token cache."""
    if clear_token_cache():
        console.print("[green]Token cache cleared.[/green]")
    else:
        console.print("[yellow]No cache to clear.[/yellow]")


if __name__ == "__main__":
    cli()
