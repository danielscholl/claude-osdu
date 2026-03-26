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
OSDU Service Versions

Queries /info endpoints on all OSDU services and displays version information.
"""

import json
import sys
from pathlib import Path

import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from common import get_config, get_access_token

console = Console()


def get_service_info(host: str, headers: dict, services: list[tuple[str, str]]) -> list[dict]:
    """Query service info endpoints and return results."""
    results = []

    for name, url in services:
        try:
            resp = httpx.get(url, headers=headers, timeout=30, follow_redirects=True)
            if resp.status_code == 200:
                data = resp.json()
                results.append({
                    'service': name,
                    'version': data.get('version', 'N/A'),
                    'artifact': data.get('artifactId', data.get('service', 'N/A')),
                    'branch': data.get('branch', data.get('release', 'N/A')),
                    'build_time': data.get('buildTime', 'N/A'),
                    'connected': data.get('connectedOuterServices', []),
                    'status': 'ok'
                })
            else:
                results.append({
                    'service': name,
                    'status': 'error',
                    'code': resp.status_code
                })
        except Exception as e:
            results.append({
                'service': name,
                'status': 'error',
                'error': str(e)
            })

    return results


def main():
    """Main entry point.

    Usage:
        service_versions.py                    # Use active environment
        service_versions.py -e azure/ship      # Use specific environment
        service_versions.py --environment cimpl/qa
    """
    # Parse command line for environment override
    platform = None
    environment = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] in ('-e', '--environment') and i + 1 < len(args):
            env_target = args[i + 1]
            if "/" in env_target:
                platform, environment = env_target.split("/", 1)
            else:
                console.print(f"[red]Error:[/red] Invalid environment format: {env_target}")
                console.print("Use format: platform/environment (e.g., azure/ship, cimpl/qa)")
                sys.exit(1)
            i += 2
        else:
            i += 1

    # Get config and token (with explicit environment for parallel execution support)
    try:
        config = get_config(platform, environment)
        token = get_access_token(config)
    except Exception as e:
        console.print(f"[red]Error getting config/token: {e}[/red]")
        sys.exit(1)

    host = config['host']
    headers = {
        'Authorization': f'Bearer {token}',
        'data-partition-id': config['partition']
    }

    # Define services to query
    core_services = [
        ('Legal', f'https://{host}/api/legal/v1/info'),
        ('Storage', f'https://{host}/api/storage/v2/info'),
        ('Search', f'https://{host}/api/search/v2/info'),
        ('Entitlements', f'https://{host}/api/entitlements/v2/info'),
        ('Schema', f'https://{host}/api/schema-service/v1/info'),
        ('Partition', f'https://{host}/api/partition/v1/info'),
    ]

    data_services = [
        ('File', f'https://{host}/api/file/v2/info'),
        ('Dataset', f'https://{host}/api/dataset/v1/info'),
        ('Unit', f'https://{host}/api/unit/v3/info'),
        ('Indexer', f'https://{host}/api/indexer/v2/info'),
    ]

    workflow_services = [
        ('Workflow', f'https://{host}/api/workflow/v1/info'),
        ('Notification', f'https://{host}/api/notification/v1/info'),
        ('Register', f'https://{host}/api/register/v1/info'),
    ]

    ddms_services = [
        ('Wellbore DDMS', f'https://{host}/api/os-wellbore-ddms/ddms/v2/version'),
    ]

    # Print header
    console.print()
    console.print(Panel.fit(
        f"[bold]OSDU Service Versions[/bold]\n\n"
        f"Host: {host}\n"
        f"Partition: {config['partition']}",
        title="Environment"
    ))
    console.print()

    # Query and display each category
    def display_table(title: str, services: list[tuple[str, str]]):
        results = get_service_info(host, headers, services)

        table = Table(title=title, show_header=True)
        table.add_column("Service", style="cyan", width=20)
        table.add_column("Version", style="green", width=12)
        table.add_column("Branch", width=20)
        table.add_column("Build Date", width=12)

        for r in results:
            if r['status'] == 'ok':
                build_date = r.get('build_time', 'N/A')
                if build_date and build_date != 'N/A':
                    build_date = build_date.split('T')[0]  # Just the date part
                table.add_row(
                    r['service'],
                    r['version'],
                    r['branch'],
                    build_date
                )
            else:
                code = r.get('code', 'ERR')
                table.add_row(
                    r['service'],
                    f"[dim]{code}[/dim]",
                    "[dim]-[/dim]",
                    "[dim]-[/dim]"
                )

        console.print(table)
        console.print()
        return results

    all_results = []
    all_results.extend(display_table("Core Services", core_services))
    all_results.extend(display_table("Data Management", data_services))
    all_results.extend(display_table("Workflow & Integration", workflow_services))
    all_results.extend(display_table("Domain Services (DDMS)", ddms_services))

    # Show connected services if any
    connected = []
    for r in all_results:
        if r['status'] == 'ok' and r.get('connected'):
            for c in r['connected']:
                connected.append(f"{r['service']}: {c.get('name', 'unknown')} {c.get('version', '')}")

    if connected:
        console.print(Panel(
            "\n".join(connected),
            title="Connected Services"
        ))
        console.print()

    # Summary
    ok_count = sum(1 for r in all_results if r['status'] == 'ok')
    err_count = sum(1 for r in all_results if r['status'] == 'error')

    # Determine platform release from versions
    versions = [r.get('version', '') for r in all_results if r['status'] == 'ok']
    if versions:
        # Most services should be on same major.minor
        common_prefix = versions[0].rsplit('.', 1)[0] if versions[0] else 'unknown'
        console.print(f"[bold]Platform Release:[/bold] {common_prefix}.x")

    console.print(f"[bold]Services Responding:[/bold] {ok_count}/{ok_count + err_count}")

    if err_count > 0:
        console.print(f"[yellow]Services Not Found:[/yellow] {err_count}")


if __name__ == "__main__":
    main()
