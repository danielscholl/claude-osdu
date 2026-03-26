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
OSDU QA Test Manifest Generator

Discovers and indexes Postman collections for quick querying.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

# Add parent directory to path for common imports
sys.path.insert(0, str(Path(__file__).parent))
from common import SKILL_DIR, find_collections, find_environments, parse_collection, get_repo_path

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


def save_manifest(manifest: dict) -> None:
    """Save manifest to file."""
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)


def extract_service_name(folder_name: str) -> str:
    """Extract service name from folder name.

    Examples:
        '11_CICD_Setup_LegalAPI' -> 'Legal'
        '01_CICD_CoreSmokeTest' -> 'CoreSmokeTest'
        '36_CICD_R3_Dataset' -> 'Dataset'
    """
    # Remove numeric prefix and CICD_ prefix
    name = re.sub(r"^\d+_CICD_", "", folder_name)
    # Remove common suffixes
    name = re.sub(r"(_?Setup_?|_?API$)", "", name)
    # Clean up R3_ prefix
    name = re.sub(r"^R3_", "", name)
    return name or folder_name


@click.group()
def cli():
    """OSDU QA Test Manifest Generator."""
    pass


@cli.command()
@click.option("--repo-path", "-r", type=click.Path(exists=True),
              help="Path to QA repository root")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def generate(repo_path: str | None, output_json: bool):
    """Generate manifest from Postman collections."""
    # Detect or use provided repo path
    if repo_path:
        repo = Path(repo_path)
    else:
        repo = get_repo_path()
        if not repo:
            console.print("[red]Error:[/red] Could not detect repository path.")
            console.print("Run from within the QA repository or specify --repo-path")
            raise SystemExit(1)

    if not output_json:
        console.print(f"[blue]Scanning:[/blue] {repo}")

    # Find collections and environments
    collections_raw = find_collections(repo)
    environments = find_environments(repo)

    if not output_json:
        console.print(f"Found {len(collections_raw)} collections, {len(environments)} environments")

    # Parse each collection for details
    collections = []
    for coll in collections_raw:
        try:
            details = parse_collection(coll["absolute_path"])
            collections.append({
                "id": coll["folder"],
                "name": details["name"],
                "path": coll["path"],
                "service": extract_service_name(coll["folder"]),
                "folders": details["folders"],
                "request_count": details["request_count"],
                "test_count": details["test_count"],
            })
        except Exception as e:
            if not output_json:
                console.print(f"[yellow]Warning:[/yellow] Failed to parse {coll['path']}: {e}")

    # Build manifest
    manifest = {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_path": str(repo),
        "summary": {
            "total_collections": len(collections),
            "total_requests": sum(c["request_count"] for c in collections),
            "total_tests": sum(c["test_count"] for c in collections),
            "platforms": [e["platform"] for e in environments],
        },
        "collections": collections,
        "environments": environments,
    }

    # Save manifest
    save_manifest(manifest)

    if output_json:
        console.print_json(json.dumps(manifest))
    else:
        console.print(f"[green]Generated manifest:[/green] {MANIFEST_FILE}")
        console.print(f"  Collections: {manifest['summary']['total_collections']}")
        console.print(f"  Requests: {manifest['summary']['total_requests']}")
        console.print(f"  Tests: {manifest['summary']['total_tests']}")
        console.print(f"  Platforms: {', '.join(manifest['summary']['platforms'])}")


@cli.command("list")
@click.option("--service", "-s", help="Filter by service name")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def list_collections(service: str | None, output_json: bool):
    """List all collections in the manifest."""
    manifest = load_manifest()
    if not manifest:
        console.print("[red]Error:[/red] No manifest found. Run 'generate' first.")
        raise SystemExit(1)

    collections = manifest["collections"]

    # Filter by service if specified
    if service:
        service_lower = service.lower()
        collections = [c for c in collections if service_lower in c["service"].lower()]

    if output_json:
        console.print_json(json.dumps(collections))
        return

    if not collections:
        console.print("[yellow]No collections found matching criteria.[/yellow]")
        return

    # Build table
    table = Table(title="Postman Collections")
    table.add_column("ID", style="cyan")
    table.add_column("Service", style="green")
    table.add_column("Name")
    table.add_column("Requests", justify="right")
    table.add_column("Tests", justify="right")

    for coll in collections:
        table.add_row(
            coll["id"],
            coll["service"],
            coll["name"][:50] + "..." if len(coll["name"]) > 50 else coll["name"],
            str(coll["request_count"]),
            str(coll["test_count"]),
        )

    console.print(table)
    console.print(f"\nTotal: {len(collections)} collections")


@cli.command()
@click.argument("collection_id")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def show(collection_id: str, output_json: bool):
    """Show details for a specific collection."""
    manifest = load_manifest()
    if not manifest:
        console.print("[red]Error:[/red] No manifest found. Run 'generate' first.")
        raise SystemExit(1)

    # Find collection by ID (case-insensitive partial match)
    collection_id_lower = collection_id.lower()
    matches = [c for c in manifest["collections"] if collection_id_lower in c["id"].lower()]

    if not matches:
        console.print(f"[red]Error:[/red] Collection '{collection_id}' not found.")
        console.print("Run 'list' to see available collections.")
        raise SystemExit(1)

    if len(matches) > 1 and not any(c["id"].lower() == collection_id_lower for c in matches):
        console.print(f"[yellow]Multiple matches found:[/yellow]")
        for m in matches:
            console.print(f"  - {m['id']}")
        raise SystemExit(1)

    # Use exact match if available, otherwise first partial match
    coll = next((c for c in matches if c["id"].lower() == collection_id_lower), matches[0])

    if output_json:
        console.print_json(json.dumps(coll))
        return

    # Display details
    console.print(f"\n[bold cyan]{coll['id']}[/bold cyan]")
    console.print(f"  Name: {coll['name']}")
    console.print(f"  Service: {coll['service']}")
    console.print(f"  Path: {coll['path']}")
    console.print(f"  Requests: {coll['request_count']}")
    console.print(f"  Tests: {coll['test_count']}")

    if coll["folders"]:
        console.print("\n  [bold]Folders:[/bold]")
        for folder in coll["folders"]:
            console.print(f"    - {folder}")


@cli.command()
@click.argument("query")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def search(query: str, output_json: bool):
    """Search collections by name, service, or folder."""
    manifest = load_manifest()
    if not manifest:
        console.print("[red]Error:[/red] No manifest found. Run 'generate' first.")
        raise SystemExit(1)

    query_lower = query.lower()
    matches = []

    for coll in manifest["collections"]:
        # Search in ID, name, service, and folders
        searchable = [
            coll["id"].lower(),
            coll["name"].lower(),
            coll["service"].lower(),
        ] + [f.lower() for f in coll["folders"]]

        if any(query_lower in s for s in searchable):
            matches.append(coll)

    if output_json:
        console.print_json(json.dumps(matches))
        return

    if not matches:
        console.print(f"[yellow]No matches found for '{query}'[/yellow]")
        return

    # Build table
    table = Table(title=f"Search Results: '{query}'")
    table.add_column("ID", style="cyan")
    table.add_column("Service", style="green")
    table.add_column("Name")
    table.add_column("Match In")

    for coll in matches:
        # Determine where the match was found
        match_in = []
        if query_lower in coll["id"].lower():
            match_in.append("id")
        if query_lower in coll["name"].lower():
            match_in.append("name")
        if query_lower in coll["service"].lower():
            match_in.append("service")
        if any(query_lower in f.lower() for f in coll["folders"]):
            match_in.append("folder")

        table.add_row(
            coll["id"],
            coll["service"],
            coll["name"][:40] + "..." if len(coll["name"]) > 40 else coll["name"],
            ", ".join(match_in),
        )

    console.print(table)
    console.print(f"\nFound: {len(matches)} collections")


if __name__ == "__main__":
    cli()
