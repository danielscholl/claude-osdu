# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "click",
#     "httpx",
#     "requests",
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
OSDU Credential Sync

Fetches OSDU test credentials from GitLab CI/CD variables using glab CLI
and stores them locally for use by test scripts.

This keeps credentials out of conversation context with LLMs.

Usage:
    uv run skills/osdu-qa/scripts/sync_credentials.py sync
    uv run skills/osdu-qa/scripts/sync_credentials.py list
    uv run skills/osdu-qa/scripts/sync_credentials.py show
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import requests

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add parent directory to path for common imports
sys.path.insert(0, str(Path(__file__).parent))
from common import (
    CONFIG_DIR,
    ENVIRONMENTS_FILE,
    PLATFORM_CREDENTIALS_FILE as CREDENTIALS_FILE,
)

console = Console()


def mask_secret(secret: str | None) -> str:
    """Mask a secret string for display, showing only first/last 4 chars."""
    if not secret:
        return "-"
    if len(secret) > 8:
        return secret[:4] + "*" * (len(secret) - 8) + secret[-4:]
    return "*" * len(secret)

# GitLab project (full URL required to specify host)
DEFAULT_GITLAB_PROJECT = "https://community.opengroup.org/osdu/qa"

# Default platform-level credential variable names (fallback when not in environments.json)
DEFAULT_PLATFORM_VARIABLES = {
    "azure": "AZURE_TEST_COLLECTION_CONFIG",
    "cimpl": "CIMPL_TEST_COLLECTION_CONFIG",
    "anthos": "ANTHOS_TEST_COLLECTION_CONFIG",
}


def _get_credential_mappings(environments: dict) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    """Build credential variable mappings from environments.json.

    Returns:
        Tuple of (platform_variables, environment_variables) where:
        - platform_variables: {platform: variable_name} for platforms without per-env creds
        - environment_variables: {platform: {env: variable_name}} for platforms with per-env creds
    """
    platform_variables = dict(DEFAULT_PLATFORM_VARIABLES)
    environment_variables: dict[str, dict[str, str]] = {}

    for platform_name, platform in environments.get("platforms", {}).items():
        envs = platform.get("environments", {})
        has_per_env = any(e.get("credential_var") for e in envs.values())

        if has_per_env:
            env_vars = {}
            for env_name, env_data in envs.items():
                cred_var = env_data.get("credential_var")
                if cred_var:
                    env_vars[env_name] = cred_var
            if env_vars:
                environment_variables[platform_name] = env_vars
                # Also set platform default to first env var if not already set
                if platform_name not in platform_variables:
                    platform_variables[platform_name] = next(iter(env_vars.values()))
        elif platform_name not in platform_variables:
            # Platform exists in config but has no credential mappings — skip
            pass

    return platform_variables, environment_variables


def run_glab(args: list[str]) -> tuple[bool, str]:
    """Run glab command and return success status and output."""
    try:
        result = subprocess.run(
            ["glab"] + args,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip()
    except FileNotFoundError:
        return False, "glab CLI not found. Install with: brew install glab"
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)


def fetch_variable(variable_name: str, project: str = DEFAULT_GITLAB_PROJECT) -> tuple[bool, str | None]:
    """Fetch a CI/CD variable value from GitLab."""
    success, output = run_glab(["variable", "get", variable_name, "-R", project])
    if success:
        return True, output
    return False, None


def parse_test_collection_config(config_json: str, platform: str = None) -> dict | None:
    """Parse TEST_COLLECTION_CONFIG JSON to extract credentials.

    Args:
        config_json: JSON string from CI/CD variable
        platform: Platform name (used to extract platform-specific fields)

    Returns:
        Dict with client_id, client_secret, and optionally tenant_id
    """
    try:
        config = json.loads(config_json)
        if isinstance(config, list) and len(config) > 0:
            entry = config[0]
            result = {
                "client_id": entry.get("CLIENT_ID"),
                "client_secret": entry.get("CLIENT_SECRET"),
            }
            # Azure also needs tenant_id
            if platform == "azure" and "TENANT_ID" in entry:
                result["tenant_id"] = entry.get("TENANT_ID")
            return result
        return None
    except json.JSONDecodeError:
        return None


def load_credentials() -> dict:
    """Load existing credentials from file."""
    if CREDENTIALS_FILE.exists():
        try:
            with open(CREDENTIALS_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"platforms": {}}


def save_credentials(credentials: dict) -> None:
    """Save credentials to file with secure permissions."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Create file with restrictive permissions from the start (no race window)
    fd = os.open(CREDENTIALS_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(credentials, f, indent=2)
    except Exception:
        os.close(fd)
        raise


def load_environments() -> dict:
    """Load environments configuration."""
    if ENVIRONMENTS_FILE.exists():
        try:
            with open(ENVIRONMENTS_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"platforms": {}}


@click.group()
def cli():
    """OSDU Credential Sync - Fetch credentials from GitLab CI/CD."""
    pass


@cli.command()
@click.option("--platform", "-p", help="Sync only specific platform")
@click.option("--environment", "-e", help="Sync only specific environment (for platforms with per-env credentials)")
@click.option("--force", "-f", is_flag=True, help="Overwrite existing credentials")
@click.option("--project", default=None, help="GitLab project URL (default: community.opengroup.org/osdu/qa)")
def sync(platform: str | None, environment: str | None, force: bool, project: str | None):
    """Sync credentials from GitLab CI/CD variables."""
    gitlab_project = project or DEFAULT_GITLAB_PROJECT
    console.print(Panel(f"Syncing credentials from GitLab CI/CD\n[dim]{gitlab_project}[/dim]", style="blue"))

    # Check glab is available
    success, output = run_glab(["--version"])
    if not success:
        console.print(f"[red]Error: {output}[/red]")
        raise SystemExit(1)

    # Build credential mappings from environments.json
    environments = load_environments()
    PLATFORM_VARIABLES, ENVIRONMENT_VARIABLES = _get_credential_mappings(environments)

    credentials = load_credentials()
    platforms_to_sync = [platform] if platform else list(PLATFORM_VARIABLES.keys())

    synced = 0
    failed = 0

    for plat in platforms_to_sync:
        if plat not in PLATFORM_VARIABLES:
            console.print(f"[yellow]Unknown platform: {plat}[/yellow]")
            continue

        # Check if this platform has per-environment credentials
        if plat in ENVIRONMENT_VARIABLES:
            env_vars = ENVIRONMENT_VARIABLES[plat]
            envs_to_sync = [environment] if environment else list(env_vars.keys())

            for env in envs_to_sync:
                if env not in env_vars:
                    console.print(f"[yellow]Unknown environment for {plat}: {env}[/yellow]")
                    continue

                var_name = env_vars[env]
                cred_key = f"{plat}/{env}"
                console.print(f"Fetching [cyan]{var_name}[/cyan] for {plat}/{env}...", end=" ")

                # Skip if already exists and not forcing
                if not force and cred_key in credentials.get("environments", {}):
                    console.print("[dim]skipped (already exists, use --force to overwrite)[/dim]")
                    continue

                success, value = fetch_variable(var_name, gitlab_project)

                if success and value:
                    parsed = parse_test_collection_config(value, platform=plat)
                    if parsed and parsed.get("client_id") and parsed.get("client_secret"):
                        if "environments" not in credentials:
                            credentials["environments"] = {}
                        credentials["environments"][cred_key] = parsed
                        console.print(f"[green]OK[/green]")
                        synced += 1
                    else:
                        console.print("[yellow]invalid format[/yellow]")
                        failed += 1
                else:
                    console.print("[dim]not found[/dim]")
                    failed += 1
        else:
            # Platform uses single credential variable
            var_name = PLATFORM_VARIABLES[plat]
            console.print(f"Fetching [cyan]{var_name}[/cyan]...", end=" ")

            # Skip if already exists and not forcing
            if not force and plat in credentials.get("platforms", {}):
                console.print("[dim]skipped (already exists, use --force to overwrite)[/dim]")
                continue

            success, value = fetch_variable(var_name, gitlab_project)

            if success and value:
                parsed = parse_test_collection_config(value, platform=plat)
                if parsed and parsed.get("client_id") and parsed.get("client_secret"):
                    if "platforms" not in credentials:
                        credentials["platforms"] = {}
                    credentials["platforms"][plat] = parsed
                    # Show what was found
                    extras = []
                    if parsed.get("tenant_id"):
                        extras.append("tenant_id")
                    extra_str = f" (+{', '.join(extras)})" if extras else ""
                    console.print(f"[green]OK{extra_str}[/green]")
                    synced += 1
                else:
                    console.print("[yellow]invalid format[/yellow]")
                    failed += 1
            else:
                console.print("[dim]not found[/dim]")
                failed += 1

    # Save credentials
    if synced > 0:
        save_credentials(credentials)
        console.print()
        console.print(f"[green]Saved {synced} credential(s) to:[/green]")
        console.print(f"  {CREDENTIALS_FILE}")
        console.print()
        console.print("[dim]File permissions set to 600 (owner read/write only)[/dim]")


@cli.command("list")
def list_variables():
    """List available CI/CD variables in GitLab."""
    console.print(Panel("GitLab CI/CD Variables", style="blue"))

    success, output = run_glab(["variable", "list", "-R", DEFAULT_GITLAB_PROJECT])

    if not success:
        console.print(f"[red]Error: {output}[/red]")
        raise SystemExit(1)

    # Filter to show only TEST_COLLECTION_CONFIG variables
    lines = output.split("\n")
    console.print("[bold]Test Collection Config Variables:[/bold]")
    for line in lines:
        if "TEST_COLLECTION_CONFIG" in line:
            console.print(f"  {line}")


@cli.command()
def show():
    """Show locally stored credentials (masked)."""
    credentials = load_credentials()

    has_platform_creds = bool(credentials.get("platforms"))
    has_env_creds = bool(credentials.get("environments"))

    if not has_platform_creds and not has_env_creds:
        console.print("[yellow]No credentials stored locally.[/yellow]")
        console.print("Run [cyan]sync[/cyan] to fetch from GitLab.")
        return

    # Platform-level credentials
    if has_platform_creds:
        table = Table(title="Platform Credentials", show_header=True)
        table.add_column("Platform", style="cyan")
        table.add_column("Client ID")
        table.add_column("Client Secret")
        table.add_column("Status")

        for plat, creds in credentials.get("platforms", {}).items():
            client_id = creds.get("client_id", "")
            client_secret = creds.get("client_secret", "")
            masked = mask_secret(client_secret)
            status = "[green]Ready[/green]" if client_id and client_secret else "[red]Incomplete[/red]"

            table.add_row(plat, client_id, masked, status)

        console.print(table)
        console.print()

    # Environment-specific credentials
    if has_env_creds:
        table = Table(title="Environment Credentials", show_header=True)
        table.add_column("Environment", style="cyan")
        table.add_column("Client ID")
        table.add_column("Client Secret")
        table.add_column("Status")

        for env_key, creds in credentials.get("environments", {}).items():
            client_id = creds.get("client_id", "")
            client_secret = creds.get("client_secret", "")
            masked = mask_secret(client_secret)
            status = "[green]Ready[/green]" if client_id and client_secret else "[red]Incomplete[/red]"

            table.add_row(env_key, client_id, masked, status)

        console.print(table)
        console.print()

    console.print(f"[dim]Credentials file: {CREDENTIALS_FILE}[/dim]")


@cli.command()
def clear():
    """Clear locally stored credentials."""
    if CREDENTIALS_FILE.exists():
        CREDENTIALS_FILE.unlink()
        console.print("[green]Credentials cleared.[/green]")
    else:
        console.print("[dim]No credentials file found.[/dim]")


@cli.command()
@click.argument("platform")
@click.option("--env", "-e", "environment", help="Environment name (e.g., qa, dev1)")
def test(platform: str, environment: str | None):
    """Test credentials for a platform by getting a token."""
    credentials = load_credentials()
    environments = load_environments()

    # Build dynamic credential mappings
    _, env_variables = _get_credential_mappings(environments)

    # Check for environment-specific credentials first
    if platform in env_variables:
        env_creds = credentials.get("environments", {})
        available_envs = [k.split("/")[1] for k in env_creds if k.startswith(f"{platform}/")]
        if not available_envs:
            console.print(f"[red]No credentials stored for platform: {platform}[/red]")
            console.print("Run [cyan]sync[/cyan] first.")
            raise SystemExit(1)
        env_name = environment if environment else available_envs[0]
        cred_key = f"{platform}/{env_name}"
        if cred_key not in env_creds:
            console.print(f"[red]No credentials for {cred_key}[/red]")
            console.print(f"Available: {', '.join(available_envs)}")
            raise SystemExit(1)
        creds = env_creds[cred_key]
    elif platform not in credentials.get("platforms", {}):
        console.print(f"[red]No credentials stored for platform: {platform}[/red]")
        console.print("Run [cyan]sync[/cyan] first.")
        raise SystemExit(1)
    else:
        creds = credentials["platforms"][platform]
        env_name = environment

    client_id = creds.get("client_id")
    client_secret = creds.get("client_secret")

    # Validate credentials are present
    if not client_id or not client_secret:
        console.print("[red]Credentials incomplete (missing client_id or client_secret)[/red]")
        console.print("Run [cyan]sync --force[/cyan] to re-fetch credentials.")
        raise SystemExit(1)

    # Get token URL from environments config
    platform_config = environments.get("platforms", {}).get(platform, {})
    token_url_pattern = platform_config.get("token_url_pattern")

    # For Azure, use a different token URL pattern
    if platform == "azure":
        tenant_id = creds.get("tenant_id")
        if not tenant_id:
            console.print("[red]Azure credentials missing tenant_id[/red]")
            console.print("Ensure AZURE_TEST_COLLECTION_CONFIG contains TENANT_ID.")
            raise SystemExit(1)
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        console.print(f"Testing credentials for [cyan]{platform}[/cyan]...")
        console.print(f"Token URL: {token_url}")
        _fetch_token(
            token_url,
            client_id,
            client_secret,
            scope="https://graph.microsoft.com/.default",
        )
        return

    if not token_url_pattern:
        console.print(f"[red]No token URL pattern configured for platform: {platform}[/red]")
        raise SystemExit(1)

    # Get environment (use specified or first available)
    envs = platform_config.get("environments", {})
    if not envs:
        console.print(f"[red]No environments configured for platform: {platform}[/red]")
        raise SystemExit(1)

    if environment:
        if environment not in envs:
            console.print(f"[red]Unknown environment: {environment}[/red]")
            console.print(f"Available: {', '.join(envs.keys())}")
            raise SystemExit(1)
        env_name = environment
    else:
        env_name = list(envs.keys())[0]

    token_url = token_url_pattern.replace("{env}", env_name)

    console.print(f"Testing credentials for [cyan]{platform}/{env_name}[/cyan]...")
    console.print(f"Token URL: {token_url}")

    _fetch_token(token_url, client_id, client_secret)


def _fetch_token(
    token_url: str,
    client_id: str,
    client_secret: str,
    scope: str | None = None,
) -> None:
    """Fetch OAuth token using requests library (secrets not exposed in process list)."""
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }
    if scope:
        data["scope"] = scope

    try:
        response = requests.post(
            token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        if response.status_code == 200:
            console.print("[green]Authentication successful![/green]")
        else:
            console.print("[red]Authentication failed[/red]")
            try:
                error = response.json()
                console.print(f"Error: {error.get('error_description', error.get('error', 'Unknown'))}")
            except (json.JSONDecodeError, KeyError):
                console.print(f"HTTP {response.status_code}: {response.text[:200]}")
    except requests.Timeout:
        console.print("[red]Request timed out[/red]")
        raise SystemExit(1)
    except requests.RequestException as e:
        console.print(f"[red]Request failed: {e}[/red]")
        raise SystemExit(1)


if __name__ == "__main__":
    cli()
