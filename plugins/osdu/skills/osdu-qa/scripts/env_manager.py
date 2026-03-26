# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "click",
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
OSDU Environment Manager

Manage OSDU test environment configuration. Discovers available environments
and persists the active selection to a state file for use by test scripts.

Commands:
    list      - List available environments
    status    - Show current configuration
    use       - Switch to an environment (saves to state file)
    platforms - List supported platforms
    clear     - Clear the active environment selection
"""

import json
import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add parent directory to path for common imports
sys.path.insert(0, str(Path(__file__).parent))
from common import (
    ENVIRONMENTS_FILE,
    ACTIVE_ENV_FILE,
    PLATFORM_CREDENTIALS_FILE,
    load_active_environment,
    save_active_environment,
    load_platform_credentials,
    save_environments,
    clear_active_environment,
    clear_token_cache,
)

console = Console()

# Constants
DEFAULT_PARTITION = "opendes"
AUTH_TYPE_AZURE_AD = "azure-ad"
AUTH_TYPE_KEYCLOAK = "keycloak"
AUTH_TYPE_UNKNOWN = "unknown"


def load_environments() -> dict[str, dict]:
    """Load environments configuration with CLI-friendly error handling."""
    if not ENVIRONMENTS_FILE.exists():
        return {"platforms": {}}
    try:
        with open(ENVIRONMENTS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise click.ClickException(
            f"Invalid JSON in environments.json: {e.msg} (line {e.lineno}, col {e.colno})"
        ) from e
    except OSError as e:
        raise click.ClickException(f"Cannot read environments.json: {e}") from e


def get_current_config() -> dict[str, str | None]:
    """Get current environment configuration from env vars."""
    return {
        "host": os.environ.get("AI_OSDU_HOST"),
        "partition": os.environ.get("AI_OSDU_DATA_PARTITION"),
        "client_id": os.environ.get("AI_OSDU_CLIENT"),
        "client_secret": os.environ.get("AI_OSDU_SECRET"),
        "tenant_id": os.environ.get("AI_OSDU_TENANT_ID"),
        "token_url": os.environ.get("AI_OSDU_TOKEN_URL"),
    }


def resolve_host(platform_config: dict, env_name: str, env_data: dict) -> str | None:
    """Resolve the host URL for an environment.

    Checks in order:
    1. Direct host in environment data
    2. API host pattern from platform config
    3. Host pattern from platform config
    """
    if "host" in env_data:
        return env_data["host"]
    if "api_host_pattern" in platform_config:
        return platform_config["api_host_pattern"].replace("{env}", env_name)
    if "host_pattern" in platform_config:
        return platform_config["host_pattern"].replace("{env}", env_name)
    return None


def add_config_row(
    table: Table,
    label: str,
    config_value: str | None,
    env_value: str | None,
    using_active_env: bool,
    mask_value: bool = False,
    source_label: str = "config file",
) -> None:
    """Add a configuration row to the status table with proper precedence.

    When an active environment is set, only config file values are used (env vars ignored).
    When no active environment is set, env vars take precedence over config files.

    Args:
        table: Rich Table to add the row to
        label: Setting name to display
        config_value: Value from config/credentials file
        env_value: Value from environment variable
        using_active_env: Whether active environment is set (env vars ignored when True)
        mask_value: Whether to mask the displayed value (for secrets)
        source_label: Label for config source (e.g., "config file", "credentials file")
    """
    display_value = "********" if mask_value else None

    if using_active_env:
        # Active environment set: only use config values, ignore env vars entirely
        if config_value:
            table.add_row(label, display_value or config_value, f"[green]{source_label}[/green]")
        else:
            table.add_row(label, "-", "[red]missing[/red]")
    else:
        # No active environment: env vars take precedence
        if env_value:
            table.add_row(label, display_value or env_value, "[yellow]env var[/yellow]")
        elif config_value:
            table.add_row(label, display_value or config_value, f"[green]{source_label}[/green]")
        else:
            table.add_row(label, "-", "[red]missing[/red]")


def detect_current_environment(config: dict, environments: dict) -> tuple[str, str] | None:
    """Detect which environment is currently configured."""
    host = config.get("host", "")
    if not host:
        return None

    for platform_name, platform in environments.get("platforms", {}).items():
        # Check for exact host match in environments
        for env_name, env in platform.get("environments", {}).items():
            if env.get("host") == host:
                return (platform_name, env_name)

        # Check for pattern match (CIMPL style)
        host_pattern = platform.get("host_pattern", "")
        api_host_pattern = platform.get("api_host_pattern", "")
        if host_pattern or api_host_pattern:
            for env_name in platform.get("environments", {}).keys():
                expected_host = host_pattern.replace("{env}", env_name)
                expected_api_host = api_host_pattern.replace("{env}", env_name)
                if host == expected_host or host == expected_api_host:
                    return (platform_name, env_name)

    return None


@click.group()
def cli() -> None:
    """OSDU Environment Manager"""
    pass


@cli.command(name="list")
def list_envs() -> None:
    """List available environments."""
    environments = load_environments()

    table = Table(title="Available OSDU Environments", show_header=True)
    table.add_column("Target", style="cyan")
    table.add_column("Provider", style="blue")
    table.add_column("Auth", style="yellow")
    table.add_column("Notes")
    table.add_column("Host")

    for platform_name, platform in environments.get("platforms", {}).items():
        auth_type = platform.get("auth_type", AUTH_TYPE_UNKNOWN)
        platform_desc = platform.get("description", "")

        envs = platform.get("environments", {})
        if not envs:
            table.add_row(
                f"{platform_name}/*",
                platform_desc,
                auth_type,
                "(no environments configured)",
                platform.get("host_pattern", "-")
            )
        else:
            for env_name, env in envs.items():
                target = f"{platform_name}/{env_name}"
                env_desc = env.get("description", "")
                host = resolve_host(platform, env_name, env) or "-"
                table.add_row(target, platform_desc, auth_type, env_desc, host)

    if not any(
        platform.get("environments")
        for platform in environments.get("platforms", {}).values()
    ):
        console.print(table)
        console.print()
        console.print("[yellow]No environments configured.[/yellow]")
        console.print("Add one with: [cyan]env add <platform>/<name> --host <host> --partition <partition> --auth-type <type>[/cyan]")
        console.print("Or copy [cyan]reference/environments.example.json[/cyan] to [cyan]config/environments.json[/cyan]")
        return

    console.print(table)
    console.print()
    console.print("[dim]Use [cyan]/env use <target>[/cyan] to switch environments[/dim]")


def _print_environment_config(
    environments: dict,
    platform_name: str,
    env_name: str,
    using_active_env: bool,
) -> None:
    """Print the configuration table for an environment."""
    platform_config = environments.get("platforms", {}).get(platform_name, {})
    env_data = platform_config.get("environments", {}).get(env_name, {})
    creds = load_platform_credentials(platform_name, env_name)
    auth_type = platform_config.get("auth_type", AUTH_TYPE_UNKNOWN)

    # Resolve configuration values
    host = resolve_host(platform_config, env_name, env_data)
    partition = env_data.get("partition", DEFAULT_PARTITION)

    # Resolve token URL (Keycloak)
    token_url = None
    if "token_url_pattern" in platform_config:
        token_url = platform_config["token_url_pattern"].replace("{env}", env_name)

    # Build configuration table
    table = Table(show_header=True, title="Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")
    table.add_column("Source")

    # Get environment variable values
    env_host = os.environ.get("AI_OSDU_HOST")
    env_partition = os.environ.get("AI_OSDU_DATA_PARTITION")
    env_client = os.environ.get("AI_OSDU_CLIENT")
    env_secret = os.environ.get("AI_OSDU_SECRET")

    # Add rows using helper
    add_config_row(table, "Host", host, env_host, using_active_env)
    add_config_row(table, "Partition", partition, env_partition, using_active_env)
    add_config_row(
        table, "Client ID",
        creds.get("client_id") if creds else None,
        env_client,
        using_active_env,
        source_label="credentials file",
    )
    add_config_row(
        table, "Client Secret",
        creds.get("client_secret") if creds else None,
        env_secret,
        using_active_env,
        mask_value=True,
        source_label="credentials file",
    )

    # Auth-type specific fields
    if auth_type == AUTH_TYPE_AZURE_AD:
        env_tenant = os.environ.get("AI_OSDU_TENANT_ID")
        add_config_row(
            table, "Tenant ID",
            creds.get("tenant_id") if creds else None,
            env_tenant,
            using_active_env,
            source_label="credentials file",
        )
    elif auth_type == AUTH_TYPE_KEYCLOAK:
        env_token_url = os.environ.get("AI_OSDU_TOKEN_URL")
        add_config_row(table, "Token URL", token_url, env_token_url, using_active_env)

    table.add_row("Auth Type", auth_type, "[dim]derived[/dim]")

    # Show warning if env vars are being ignored
    if using_active_env and (env_host or env_client or env_secret):
        console.print()
        console.print("[dim]Note: Environment variables are ignored when an active environment is set.[/dim]")

    console.print(table)


def _print_status_indicators() -> None:
    """Print credentials file status."""
    console.print()

    if PLATFORM_CREDENTIALS_FILE.exists():
        console.print("[dim]Credentials file: [green]Present[/green][/dim]")
    else:
        console.print("[dim]Credentials file: [yellow]Not found[/yellow] (run [cyan]sync_credentials.py sync[/cyan])[/dim]")


def _validate_environment_exists(
    environments: dict, platform_name: str | None, env_name: str | None
) -> bool:
    """Check if the given platform/environment exists in environments.json."""
    if not platform_name or not env_name:
        return False
    platform = environments.get("platforms", {}).get(platform_name)
    if not platform:
        return False
    return env_name in platform.get("environments", {})


@cli.command()
def status() -> None:
    """Show current environment configuration."""
    environments = load_environments()
    active = load_active_environment()

    # Determine active environment
    if active:
        platform_name = active.get("platform")
        env_name = active.get("environment")

        # Validate the active environment still exists
        if _validate_environment_exists(environments, platform_name, env_name):
            title = f"Active Environment: [green]{platform_name}/{env_name}[/green]"
        else:
            # Active environment no longer exists in config
            title = f"Active Environment: [red]{platform_name}/{env_name}[/red] (not found in config)"
            console.print(Panel(title, style="bold"))
            console.print()
            console.print("[yellow]Warning: The saved active environment no longer exists in environments.json[/yellow]")
            console.print("Run [cyan]/env clear[/cyan] to reset, or [cyan]/env use <target>[/cyan] to switch.")
            console.print()
            _print_status_indicators()
            return
    else:
        # Fall back to env var detection for backwards compatibility
        config = get_current_config()
        detected = detect_current_environment(config, environments)
        if detected:
            platform_name, env_name = detected
            title = f"Detected Environment: [yellow]{platform_name}/{env_name}[/yellow] (from env vars)"
        else:
            platform_name, env_name = None, None
            title = "Environment: [red]Not configured[/red]"

    console.print(Panel(title, style="bold"))
    console.print()

    # Build effective configuration
    if platform_name and env_name:
        _print_environment_config(environments, platform_name, env_name, active is not None)
    else:
        console.print("[yellow]No environment configured.[/yellow]")
        console.print("Use [cyan]/env use <platform/environment>[/cyan] to set one.")

    _print_status_indicators()


@cli.command()
@click.argument("target")
def use(target: str) -> None:
    """Switch to an environment.

    TARGET should be in format: platform/environment (e.g., azure/ship, cimpl/dev1)

    This saves the environment selection to a state file. Test scripts will
    automatically use credentials from the platform credentials file.
    """
    environments = load_environments()

    # Parse target
    if "/" not in target:
        console.print(f"[red]Invalid target format: {target}[/red]")
        console.print("Use format: [cyan]platform/environment[/cyan] (e.g., azure/ship, cimpl/dev1)")
        raise SystemExit(1)

    platform_name, env_name = target.split("/", 1)

    # Find platform
    platform = environments.get("platforms", {}).get(platform_name)
    if not platform:
        console.print(f"[red]Unknown platform: {platform_name}[/red]")
        console.print("Available platforms: " + ", ".join(environments.get("platforms", {}).keys()))
        raise SystemExit(1)

    # Find environment
    env = platform.get("environments", {}).get(env_name)
    if not env:
        console.print(f"[red]Unknown environment: {env_name}[/red]")
        available = list(platform.get("environments", {}).keys())
        if available:
            console.print(f"Available {platform_name} environments: " + ", ".join(available))
        else:
            console.print(f"No environments configured for {platform_name}")
        raise SystemExit(1)

    # Get configuration details for display
    auth_type = platform.get("auth_type", AUTH_TYPE_UNKNOWN)
    host = resolve_host(platform, env_name, env) or "(unknown)"
    partition = env.get("partition", DEFAULT_PARTITION)

    # Check for credentials (check environment-specific first, then platform-level)
    creds = load_platform_credentials(platform_name, env_name)
    has_credentials = creds and creds.get("client_id") and creds.get("client_secret")

    # For Azure, also need tenant_id
    if auth_type == AUTH_TYPE_AZURE_AD:
        has_credentials = has_credentials and creds.get("tenant_id")

    # Save active environment
    save_active_environment(platform_name, env_name)

    # Output
    console.print(Panel(
        f"[bold green]Switched to {platform_name}/{env_name}[/bold green]\n\n"
        f"Host: {host}\n"
        f"Partition: {partition}\n"
        f"Auth: {auth_type}",
        title="Environment Activated",
        border_style="green"
    ))

    console.print()

    if has_credentials:
        console.print("[green]Credentials found in credentials file[/green]")
        console.print()
        console.print("[bold]Ready to run tests![/bold] Try:")
        console.print("  [cyan]/qa status[/cyan] - Verify configuration")
        console.print("  [cyan]/qa legal[/cyan]  - Run Legal API tests")
    else:
        console.print("[yellow]Credentials not found for this platform[/yellow]")
        console.print()
        console.print("To sync credentials from GitLab:")
        console.print("  [cyan]uv run skills/osdu-qa/scripts/sync_credentials.py sync[/cyan]")
        console.print()
        console.print("Or set environment variables as override:")
        if auth_type == AUTH_TYPE_AZURE_AD:
            console.print("  [dim]export AI_OSDU_CLIENT='...'[/dim]")
            console.print("  [dim]export AI_OSDU_SECRET='...'[/dim]")
            console.print("  [dim]export AI_OSDU_TENANT_ID='...'[/dim]")
        else:
            console.print("  [dim]export AI_OSDU_CLIENT='...'[/dim]")
            console.print("  [dim]export AI_OSDU_SECRET='...'[/dim]")


@cli.command()
def platforms() -> None:
    """List supported platforms and their auth types."""
    environments = load_environments()

    table = Table(title="Supported Platforms", show_header=True)
    table.add_column("Platform", style="cyan")
    table.add_column("Auth Type", style="yellow")
    table.add_column("Description")
    table.add_column("Environments")

    for platform_name, platform in environments.get("platforms", {}).items():
        env_count = len(platform.get("environments", {}))
        table.add_row(
            platform_name,
            platform.get("auth_type", AUTH_TYPE_UNKNOWN),
            platform.get("description", ""),
            str(env_count) if env_count > 0 else "[dim]none[/dim]"
        )

    console.print(table)


@cli.command()
def clear() -> None:
    """Clear the active environment selection."""
    if ACTIVE_ENV_FILE.exists():
        ACTIVE_ENV_FILE.unlink()
        console.print("[green]Active environment cleared.[/green]")
        console.print()
        console.print("The system will fall back to environment variables or defaults.")
    else:
        console.print("[dim]No active environment was set.[/dim]")


def _get_cluster_info(environments: dict, target: str) -> dict:
    """Get cluster metadata for an environment from environments.json.

    Reads cluster/namespace from the environment entry dynamically.

    Args:
        environments: Full environments config dict
        target: Target string like "platform/env"

    Returns:
        Dict with cluster, cli, and namespace keys
    """
    if "/" not in target:
        return {}

    platform_name, env_name = target.split("/", 1)
    platform = environments.get("platforms", {}).get(platform_name, {})
    env_data = platform.get("environments", {}).get(env_name, {})

    cluster_name = env_data.get("cluster", "")
    namespace = env_data.get("namespace", "")

    # Determine CLI tool based on platform type
    auth_type = platform.get("auth_type", AUTH_TYPE_UNKNOWN)
    if auth_type == AUTH_TYPE_KEYCLOAK:
        cli_tool = "oc"
    else:
        cli_tool = "kubectl"

    # Enrich cluster name with platform-level cluster metadata if available
    cluster_display = cluster_name
    clusters_meta = platform.get("clusters", {})
    if cluster_name and cluster_name in clusters_meta:
        cluster_meta = clusters_meta[cluster_name]
        desc = cluster_meta.get("description", "")
        if auth_type == AUTH_TYPE_KEYCLOAK:
            cluster_display = f"{cluster_name} (ROSA)"
        elif auth_type == AUTH_TYPE_AZURE_AD:
            cluster_display = f"{cluster_name} (AKS)"
        else:
            cluster_display = cluster_name

    return {
        "cluster": cluster_display or "-",
        "cli": cli_tool,
        "namespace": namespace or "-",
    }


def _check_api_health(platform: str, env_name: str, timeout: float = 10.0) -> tuple[bool, str]:
    """Quick health check for an environment.

    Returns:
        Tuple of (is_online, status_message)
    """
    from common import get_config, check_environment_health

    try:
        config = get_config(platform, env_name)
        result = check_environment_health(config, timeout=timeout)
        if result["healthy"]:
            return True, "Online"
        else:
            return False, result.get("error", "Offline")[:30]
    except Exception as e:
        return False, str(e)[:30]


@cli.command()
@click.option("--check", is_flag=True, help="Include API health check (slower)")
def audit(check: bool) -> None:
    """Audit all environments with details in list format.

    Shows cluster, credentials, and optionally API health for all environments.
    """
    environments = load_environments()

    console.print()
    console.print("[bold]Environment Audit[/bold]")
    console.print("=" * 40)

    for platform_name, platform in environments.get("platforms", {}).items():
        auth_type = platform.get("auth_type", AUTH_TYPE_UNKNOWN)

        for env_name, env_data in platform.get("environments", {}).items():
            target = f"{platform_name}/{env_name}"

            # Get cluster info
            cluster_info = _get_cluster_info(environments, target)
            cluster = cluster_info.get("cluster", "-")
            cli_tool = cluster_info.get("cli", "-")
            namespace = cluster_info.get("namespace", "-")

            # Get host
            host = resolve_host(platform, env_name, env_data) or "-"

            # Get partition
            partition = env_data.get("partition", DEFAULT_PARTITION)

            # Get auth endpoint
            if auth_type == AUTH_TYPE_AZURE_AD:
                auth_endpoint = "login.microsoftonline.com"
            elif "token_url_pattern" in platform:
                auth_endpoint = platform["token_url_pattern"].replace("{env}", env_name)
                # Extract just the host part
                auth_endpoint = auth_endpoint.replace("https://", "").split("/")[0]
            else:
                auth_endpoint = "-"

            # Get credentials
            creds = load_platform_credentials(platform_name, env_name)
            client_id = creds.get("client_id", "-") if creds else "-"
            has_secret = "********" if creds and creds.get("client_secret") else "[ ] missing"

            # Check API health if requested
            if check:
                is_online, status = _check_api_health(platform_name, env_name)
                api_status = "Online" if is_online else f"Offline ({status})"
            else:
                api_status = "(use --check)"

            # Print in list format
            console.print()
            console.print(f"[bold cyan]### {target}[/bold cyan]")
            console.print(f"- [bold]Cluster:[/bold] {cluster}")
            console.print(f"- [bold]CLI:[/bold] {cli_tool}")
            console.print(f"- [bold]Namespace:[/bold] {namespace}")
            console.print(f"- [bold]OSDU Host:[/bold] {host}")
            console.print(f"- [bold]Partition:[/bold] {partition}")
            console.print(f"- [bold]Auth Endpoint:[/bold] {auth_endpoint}")
            console.print(f"- [bold]Client ID:[/bold] {client_id}")
            console.print(f"- [bold]Client Secret:[/bold] {has_secret}")
            console.print(f"- [bold]API Status:[/bold] {api_status}")

    console.print()


@cli.command()
@click.argument("target")
@click.option("--host", required=True, help="OSDU API hostname (e.g., osdu-test.example.com)")
@click.option("--partition", required=True, help="Data partition ID (e.g., opendes)")
@click.option("--auth-type", type=click.Choice(["azure-ad", "keycloak"]), required=True, help="Authentication type")
@click.option("--tenant-id", default=None, help="Azure AD tenant ID (azure-ad only)")
@click.option("--token-url", default=None, help="Keycloak token URL (keycloak only)")
@click.option("--credential-var", default=None, help="GitLab CI/CD variable name for credentials")
@click.option("--cluster", default=None, help="Cluster name")
@click.option("--namespace", default=None, help="Kubernetes namespace")
@click.option("--description", default="", help="Environment description")
def add(
    target: str,
    host: str,
    partition: str,
    auth_type: str,
    tenant_id: str | None,
    token_url: str | None,
    credential_var: str | None,
    cluster: str | None,
    namespace: str | None,
    description: str,
) -> None:
    """Add a new environment.

    TARGET should be in format: platform/environment (e.g., azure/myenv, cimpl/qa)
    """
    if "/" not in target:
        console.print(f"[red]Invalid target format: {target}[/red]")
        console.print("Use format: [cyan]platform/environment[/cyan] (e.g., azure/myenv)")
        raise SystemExit(1)

    platform_name, env_name = target.split("/", 1)

    environments = load_environments()

    # Create platform entry if it doesn't exist
    if platform_name not in environments.get("platforms", {}):
        if "platforms" not in environments:
            environments["platforms"] = {}

        platform_entry = {
            "type": platform_name,
            "description": f"{platform_name.upper()} OSDU",
            "auth_type": auth_type,
            "env_vars": {
                "host": "AI_OSDU_HOST",
                "partition": "AI_OSDU_DATA_PARTITION",
                "client_id": "AI_OSDU_CLIENT",
                "client_secret": "AI_OSDU_SECRET",
            },
            "environments": {},
        }
        if auth_type == "azure-ad":
            platform_entry["env_vars"]["tenant_id"] = "AI_OSDU_TENANT_ID"
        elif auth_type == "keycloak":
            platform_entry["env_vars"]["token_url"] = "AI_OSDU_TOKEN_URL"

        environments["platforms"][platform_name] = platform_entry

    platform = environments["platforms"][platform_name]

    # Build environment entry
    env_entry = {
        "host": host,
        "partition": partition,
        "description": description,
    }
    if credential_var:
        env_entry["credential_var"] = credential_var
    if cluster:
        env_entry["cluster"] = cluster
    if namespace:
        env_entry["namespace"] = namespace

    # Add/update the environment
    if "environments" not in platform:
        platform["environments"] = {}

    is_update = env_name in platform["environments"]
    platform["environments"][env_name] = env_entry

    save_environments(environments)

    action = "Updated" if is_update else "Added"
    console.print(Panel(
        f"[bold green]{action} {target}[/bold green]\n\n"
        f"Host: {host}\n"
        f"Partition: {partition}\n"
        f"Auth: {auth_type}",
        title=f"Environment {action}",
        border_style="green",
    ))
    console.print()
    console.print(f"[dim]Saved to {ENVIRONMENTS_FILE}[/dim]")
    console.print()
    console.print("Next steps:")
    console.print(f"  [cyan]env use {target}[/cyan] - Activate this environment")
    console.print("  [cyan]sync_credentials.py sync[/cyan] - Sync credentials from GitLab")


@cli.command()
@click.argument("target")
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
def remove(target: str, confirm: bool) -> None:
    """Remove an environment.

    TARGET should be in format: platform/environment (e.g., azure/myenv, cimpl/qa)
    """
    if "/" not in target:
        console.print(f"[red]Invalid target format: {target}[/red]")
        console.print("Use format: [cyan]platform/environment[/cyan] (e.g., azure/myenv)")
        raise SystemExit(1)

    platform_name, env_name = target.split("/", 1)

    environments = load_environments()

    # Validate environment exists
    platform = environments.get("platforms", {}).get(platform_name)
    if not platform or env_name not in platform.get("environments", {}):
        console.print(f"[red]Environment not found: {target}[/red]")
        raise SystemExit(1)

    if not confirm:
        console.print(f"[yellow]Remove environment {target}?[/yellow]")
        console.print("Use [cyan]--confirm[/cyan] flag to proceed.")
        raise SystemExit(1)

    # Remove the environment
    del platform["environments"][env_name]

    # Remove empty platform entries
    if not platform.get("environments"):
        del environments["platforms"][platform_name]

    save_environments(environments)

    # Clear token cache for removed environment
    clear_token_cache(platform_name, env_name)

    # Clear active env if it was the removed one
    active = load_active_environment()
    if active and active.get("platform") == platform_name and active.get("environment") == env_name:
        clear_active_environment()
        console.print("[dim]Active environment cleared (was pointing to removed environment)[/dim]")

    console.print(f"[green]Removed environment: {target}[/green]")


if __name__ == "__main__":
    cli()
