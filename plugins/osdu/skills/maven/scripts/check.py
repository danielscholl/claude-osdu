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
#     "httpx",
#     "click",
#     "rich",
#     "defusedxml",
# ]
# ///
"""
Maven Version Checking Script

Check Maven dependency versions and find available updates via Maven Central API.

Usage:
    uv run maven_check.py check --dependency "org.springframework:spring-core" --version "5.3.0"
    uv run maven_check.py batch --dependencies '[{"dependency": "spring-core", "version": "5.3.0"}]'
    uv run maven_check.py list --dependency "org.springframework:spring-core"
"""

import json
import re
import subprocess
import sys
import time
import defusedxml.ElementTree as ET  # noqa: N817
from xml.etree.ElementTree import Element  # type annotation only
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import click
import httpx
from rich.console import Console
from rich.table import Table

console = Console(stderr=True)


# =============================================================================
# Self-Check: Fail-Fast Dependency Validation
# =============================================================================
#
# This script uses the Maven Central REST API via httpx (a Python library)
# and does not require external CLI tools. The require_tool pattern below
# is included for consistency with scan.py and can be used if external
# dependencies are added in the future.
#
# Pattern usage:
#   require_tool("tool-name", ["tool", "--version"], {
#       "macOS": "brew install tool",
#       "Linux": "apt install tool",
#       "Windows": "winget install tool",
#   })


def require_tool(name: str, check_cmd: list[str], install_hints: dict[str, str]) -> None:
    """Check tool is installed, exit with guidance if missing.

    Args:
        name: Tool name for error message
        check_cmd: Command to verify installation (e.g., ["trivy", "--version"])
        install_hints: Platform-specific install commands {"macOS": "...", "Linux": "...", "Windows": "..."}
    """
    try:
        result = subprocess.run(check_cmd, capture_output=True, timeout=5)
        if result.returncode != 0:
            raise FileNotFoundError
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print(f"Error: {name} is not installed or not working", file=sys.stderr)
        print("", file=sys.stderr)
        print(f"Install {name}:", file=sys.stderr)
        for platform, cmd in install_hints.items():
            print(f"  {platform}:  {cmd}", file=sys.stderr)
        print("", file=sys.stderr)
        print("Then re-run this command.", file=sys.stderr)
        sys.exit(1)


# No external tool dependencies for this script - uses Maven Central REST API only

# =============================================================================
# Constants and Error Codes
# =============================================================================

MAVEN_SEARCH_URL = "https://search.maven.org/solrsearch/select"
MAVEN_REPO_URL = "https://repo1.maven.org/maven2"
DEFAULT_TIMEOUT = 30
CACHE_TTL = 3600  # 1 hour


class MavenErrorCode(str, Enum):
    """Error codes matching reference implementation."""

    INVALID_COORDINATE = "INVALID_COORDINATE"
    DEPENDENCY_NOT_FOUND = "DEPENDENCY_NOT_FOUND"
    VERSION_NOT_FOUND = "VERSION_NOT_FOUND"
    MAVEN_API_ERROR = "MAVEN_API_ERROR"
    INVALID_INPUT_FORMAT = "INVALID_INPUT_FORMAT"


# Simple in-memory cache
_cache: dict[str, tuple[float, Any]] = {}


def cache_get(key: str) -> Any | None:
    """Get value from cache if not expired."""
    if key in _cache:
        timestamp, value = _cache[key]
        if time.time() - timestamp < CACHE_TTL:
            return value
        del _cache[key]
    return None


def cache_set(key: str, value: Any) -> None:
    """Set value in cache."""
    _cache[key] = (time.time(), value)


# =============================================================================
# Version Parsing and Comparison
# =============================================================================


@dataclass
class ParsedVersion:
    """Parsed version components."""

    major: int
    minor: int
    patch: int
    qualifier: str | None
    original: str

    def __lt__(self, other: "ParsedVersion") -> bool:
        # Compare major.minor.patch
        if (self.major, self.minor, self.patch) != (other.major, other.minor, other.patch):
            return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)
        # Compare qualifiers: no qualifier > RELEASE > RC > beta > alpha > SNAPSHOT
        return self._qualifier_rank() < other._qualifier_rank()

    def _qualifier_rank(self) -> int:
        """Return rank for qualifier comparison."""
        if self.qualifier is None:
            return 100
        q = self.qualifier.upper()
        if "SNAPSHOT" in q:
            return 0
        if "ALPHA" in q or q.startswith("A"):
            return 10
        if "BETA" in q or q.startswith("B"):
            return 20
        if "M" in q or "MILESTONE" in q:
            return 30
        if "RC" in q or "CR" in q:
            return 40
        if "RELEASE" in q or "FINAL" in q or "GA" in q:
            return 90
        return 50  # Unknown qualifiers


def parse_version(version_str: str) -> ParsedVersion | None:
    """Parse version string into components."""
    if not version_str:
        return None

    original = version_str
    # Strip common qualifiers for parsing
    qualifier = None
    qualifier_patterns = [
        r"[._-](SNAPSHOT|RELEASE|FINAL|GA|RC\d*|CR\d*|M\d*|alpha\d*|beta\d*|a\d*|b\d*)$",
        r"[._-](\d{8}\.\d{6}[-_]\d+)$",  # Timestamp snapshots
    ]
    for pattern in qualifier_patterns:
        match = re.search(pattern, version_str, re.IGNORECASE)
        if match:
            qualifier = match.group(1)
            version_str = version_str[: match.start()]
            break

    # Parse major.minor.patch
    parts = re.split(r"[._-]", version_str)
    try:
        major = int(parts[0]) if parts else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        # Calendar versioning or other formats
        try:
            major = int(parts[0]) if parts else 0
            minor = 0
            patch = 0
        except ValueError:
            return None

    return ParsedVersion(
        major=major, minor=minor, patch=patch, qualifier=qualifier, original=original
    )


def is_stable_version(version: str) -> bool:
    """Check if version is stable (no SNAPSHOT, alpha, beta, etc.)."""
    v_upper = version.upper()
    unstable_markers = ["SNAPSHOT", "ALPHA", "BETA", "-A", "-B", "-M", "RC", "CR"]
    return not any(marker in v_upper for marker in unstable_markers)


def find_latest_versions(versions: list[str], current_version: str) -> dict[str, str | None]:
    """Find latest major, minor, and patch versions relative to current."""
    if not versions:
        return {"major": None, "minor": None, "patch": None}

    current = parse_version(current_version)
    if not current:
        return {"major": None, "minor": None, "patch": None}

    # Filter to stable versions only
    stable_versions = [v for v in versions if is_stable_version(v)]
    parsed_versions = [(v, parse_version(v)) for v in stable_versions]
    parsed_versions = [(v, p) for v, p in parsed_versions if p is not None]

    latest_major = None
    latest_minor = None
    latest_patch = None

    for version_str, parsed in parsed_versions:
        # Latest overall (major update)
        if latest_major is None or parsed > parse_version(latest_major):
            latest_major = version_str

        # Same major, latest minor
        if parsed.major == current.major:
            if latest_minor is None or parsed > parse_version(latest_minor):
                latest_minor = version_str

            # Same major.minor, latest patch
            if parsed.minor == current.minor:  # noqa: SIM102
                if latest_patch is None or parsed > parse_version(latest_patch):
                    latest_patch = version_str

    return {
        "major": latest_major,
        "minor": latest_minor,
        "patch": latest_patch,
    }


def has_update(current: str, latest: str | None) -> bool:
    """Check if latest is newer than current."""
    if not latest:
        return False
    current_parsed = parse_version(current)
    latest_parsed = parse_version(latest)
    if not current_parsed or not latest_parsed:
        return False
    return latest_parsed > current_parsed


# =============================================================================
# Maven API Functions
# =============================================================================


def validate_dependency(dependency: str) -> tuple[str, str]:
    """Validate and parse dependency string into groupId and artifactId."""
    if ":" not in dependency:
        raise ValueError(
            f"Invalid Maven coordinate: {dependency}. Expected format: groupId:artifactId"
        )

    parts = dependency.split(":")
    if len(parts) < 2:
        raise ValueError(
            f"Invalid Maven coordinate: {dependency}. Expected format: groupId:artifactId"
        )

    group_id = parts[0].strip()
    artifact_id = parts[1].strip()

    if not group_id or not artifact_id:
        raise ValueError(
            f"Invalid Maven coordinate: {dependency}. Both groupId and artifactId are required"
        )

    return group_id, artifact_id


def check_version_exists(
    group_id: str, artifact_id: str, version: str, packaging: str = "jar"
) -> bool:
    """Check if specific version exists via HEAD request."""
    cache_key = f"exists:{group_id}:{artifact_id}:{version}:{packaging}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    group_path = group_id.replace(".", "/")

    # Determine file extension based on packaging
    ext = packaging
    if packaging == "bundle":
        ext = "jar"

    url = f"{MAVEN_REPO_URL}/{group_path}/{artifact_id}/{version}/{artifact_id}-{version}.{ext}"

    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            response = client.head(url)
            exists = response.status_code == 200
            cache_set(cache_key, exists)
            return exists
    except httpx.RequestError:
        return False


def get_all_versions(group_id: str, artifact_id: str) -> list[str]:
    """Get all available versions for a dependency from Maven Central."""
    cache_key = f"versions:{group_id}:{artifact_id}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    params = {
        "q": f'g:"{group_id}" AND a:"{artifact_id}"',
        "rows": 200,
        "wt": "json",
        "core": "gav",
    }

    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            response = client.get(MAVEN_SEARCH_URL, params=params)
            response.raise_for_status()
            data = response.json()

            versions = []
            for doc in data.get("response", {}).get("docs", []):
                version = doc.get("v")
                if version:
                    versions.append(version)

            cache_set(cache_key, versions)
            return versions
    except (httpx.RequestError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Maven API error: {e}")


def check_version(dependency: str, version: str, packaging: str = "jar") -> dict[str, Any]:
    """Check dependency version and find updates. Returns dict matching reference format."""
    group_id, artifact_id = validate_dependency(dependency)

    # Check if version exists
    exists = check_version_exists(group_id, artifact_id, version, packaging)

    # Get all available versions
    all_versions = get_all_versions(group_id, artifact_id)

    if not all_versions and not exists:
        return {
            "status": "error",
            "error_code": MavenErrorCode.DEPENDENCY_NOT_FOUND.value,
            "message": f"Dependency {dependency} not found in Maven Central",
        }

    # Find latest versions
    latest = find_latest_versions(all_versions, version)

    # Calculate update flags based on which version component changes
    current_parsed = parse_version(version)

    # Has patch update: there's a newer version in the same major.minor
    has_patch = has_update(version, latest["patch"])

    # Has minor update: latest_minor has a HIGHER minor version than current
    has_minor = False
    if latest["minor"] and current_parsed:
        minor_parsed = parse_version(latest["minor"])
        if minor_parsed and minor_parsed.minor > current_parsed.minor:
            has_minor = True

    # Has major update: latest_major has a HIGHER major version than current
    has_major = False
    if latest["major"] and current_parsed:
        major_parsed = parse_version(latest["major"])
        if major_parsed and major_parsed.major > current_parsed.major:
            has_major = True

    return {
        "status": "success",
        "result": {
            "dependency": dependency,
            "current_version": version,
            "exists": exists,
            "latest_versions": {
                "major": latest["major"],
                "minor": latest["minor"],
                "patch": latest["patch"],
            },
            "has_major_update": has_major,
            "has_minor_update": has_minor,
            "has_patch_update": has_patch,
            "total_versions_available": len(all_versions),
        },
    }


def list_versions(dependency: str) -> dict[str, Any]:
    """List all available versions grouped by track."""
    group_id, artifact_id = validate_dependency(dependency)

    all_versions = get_all_versions(group_id, artifact_id)

    if not all_versions:
        return {
            "status": "error",
            "error_code": MavenErrorCode.DEPENDENCY_NOT_FOUND.value,
            "message": f"Dependency {dependency} not found in Maven Central",
        }

    # Group by major.minor track
    tracks: dict[str, list[str]] = {}
    for version in all_versions:
        parsed = parse_version(version)
        if parsed:
            track_key = f"{parsed.major}.{parsed.minor}"
            if track_key not in tracks:
                tracks[track_key] = []
            tracks[track_key].append(version)

    # Sort tracks and versions
    sorted_tracks = {}
    for track in sorted(tracks.keys(), key=lambda x: tuple(map(int, x.split("."))), reverse=True):
        # Sort versions within track (newest first)
        track_versions = tracks[track]
        parsed_sorted = sorted(
            [(v, parse_version(v)) for v in track_versions if parse_version(v)],
            key=lambda x: x[1],
            reverse=True,
        )
        sorted_tracks[track] = [v for v, _ in parsed_sorted]

    return {
        "status": "success",
        "result": {
            "dependency": dependency,
            "total_versions": len(all_versions),
            "tracks": sorted_tracks,
        },
    }


# =============================================================================
# CLI Commands
# =============================================================================


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Maven version checking - Check dependencies and find updates."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
@click.option("--dependency", "-d", required=True, help="Maven coordinate (groupId:artifactId)")
@click.option("--version", "-v", required=True, help="Version to check")
@click.option("--packaging", "-p", default="jar", help="Package type (jar, pom, war)")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def check(dependency: str, version: str, packaging: str, output_json: bool):
    """Check a single dependency version and find available updates."""
    try:
        result = check_version(dependency, version, packaging)

        if output_json:
            print(json.dumps(result, indent=2))
            return

        if result["status"] == "error":
            console.print(f"[red]Error:[/red] {result['message']}")
            sys.exit(1)

        r = result["result"]

        # Build status indicator
        if r["has_major_update"] or r["has_minor_update"] or r["has_patch_update"]:
            status = "[yellow]Updates available[/yellow]"
        elif r["exists"]:
            status = "[green]Up to date[/green]"
        else:
            status = "[red]Version not found[/red]"

        console.print(f"\n[bold]{dependency}:{version}[/bold]")
        console.print(f"Status: {status}")
        console.print(f"Exists: {'Yes' if r['exists'] else 'No'}")

        table = Table(title="Latest Versions")
        table.add_column("Type", style="cyan")
        table.add_column("Version", style="green")
        table.add_column("Update Available")

        latest = r["latest_versions"]
        table.add_row("Major", latest["major"] or "-", "Yes" if r["has_major_update"] else "No")
        table.add_row("Minor", latest["minor"] or "-", "Yes" if r["has_minor_update"] else "No")
        table.add_row("Patch", latest["patch"] or "-", "Yes" if r["has_patch_update"] else "No")

        console.print(table)
        console.print(f"\nTotal versions available: {r['total_versions_available']}")

    except ValueError as e:
        if output_json:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "error_code": MavenErrorCode.INVALID_COORDINATE.value,
                        "message": str(e),
                    }
                )
            )
        else:
            console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        if output_json:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "error_code": MavenErrorCode.MAVEN_API_ERROR.value,
                        "message": str(e),
                    }
                )
            )
        else:
            console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@cli.command()
@click.option(
    "--dependencies", "-d", required=True, help="JSON array of {dependency, version} objects"
)
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def batch(dependencies: str, output_json: bool):
    """Check multiple dependencies for updates."""
    try:
        deps = json.loads(dependencies)
        if not isinstance(deps, list):
            raise ValueError("Dependencies must be a JSON array")
    except json.JSONDecodeError as e:
        if output_json:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "error_code": MavenErrorCode.INVALID_INPUT_FORMAT.value,
                        "message": f"Invalid JSON: {e}",
                    }
                )
            )
        else:
            console.print(f"[red]Error:[/red] Invalid JSON: {e}")
        sys.exit(1)

    results = []
    success_count = 0
    with_updates = 0

    for dep in deps:
        dependency = dep.get("dependency", "")
        version = dep.get("version", "")
        packaging = dep.get("packaging", "jar")

        if not dependency or not version:
            results.append(
                {
                    "dependency": dependency,
                    "version": version,
                    "status": "error",
                    "error": "Missing dependency or version",
                }
            )
            continue

        try:
            result = check_version(dependency, version, packaging)
            if result["status"] == "success":
                results.append(
                    {
                        "dependency": dependency,
                        "version": version,
                        "status": "success",
                        "result": result["result"],
                    }
                )
                success_count += 1
                r = result["result"]
                if r["has_major_update"] or r["has_minor_update"] or r["has_patch_update"]:
                    with_updates += 1
            else:
                results.append(
                    {
                        "dependency": dependency,
                        "version": version,
                        "status": "error",
                        "error": result.get("message", "Unknown error"),
                    }
                )
        except Exception as e:
            results.append(
                {
                    "dependency": dependency,
                    "version": version,
                    "status": "error",
                    "error": str(e),
                }
            )

    batch_result = {
        "status": "success",
        "result": {
            "total": len(deps),
            "success": success_count,
            "failed": len(deps) - success_count,
            "with_updates": with_updates,
            "results": results,
        },
    }

    if output_json:
        print(json.dumps(batch_result, indent=2))
        return

    # Pretty print
    console.print("\n[bold]Batch Version Check[/bold]")
    console.print(
        f"Total: {len(deps)} | Success: {success_count} | Failed: {len(deps) - success_count} | With Updates: {with_updates}"
    )

    table = Table()
    table.add_column("Dependency", style="cyan")
    table.add_column("Version")
    table.add_column("Status")
    table.add_column("Latest")

    for r in results:
        if r["status"] == "success":
            res = r["result"]
            latest = res["latest_versions"]["major"] or "-"
            has_update = (
                res["has_major_update"] or res["has_minor_update"] or res["has_patch_update"]
            )
            status_str = "[yellow]Update available[/yellow]" if has_update else "[green]OK[/green]"
            table.add_row(r["dependency"], r["version"], status_str, latest)
        else:
            table.add_row(r["dependency"], r["version"], f"[red]{r['error']}[/red]", "-")

    console.print(table)


@cli.command("list")
@click.option("--dependency", "-d", required=True, help="Maven coordinate (groupId:artifactId)")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def list_cmd(dependency: str, output_json: bool):
    """List all available versions for a dependency."""
    try:
        result = list_versions(dependency)

        if output_json:
            print(json.dumps(result, indent=2))
            return

        if result["status"] == "error":
            console.print(f"[red]Error:[/red] {result['message']}")
            sys.exit(1)

        r = result["result"]
        console.print(f"\n[bold]{dependency}[/bold]")
        console.print(f"Total versions: {r['total_versions']}")

        # Show top tracks with latest versions
        tracks = r["tracks"]
        table = Table(title="Version Tracks (newest first)")
        table.add_column("Track", style="cyan")
        table.add_column("Latest", style="green")
        table.add_column("All Versions")

        for track, versions in list(tracks.items())[:10]:  # Show top 10 tracks
            latest = versions[0] if versions else "-"
            all_vers = ", ".join(versions[:5])
            if len(versions) > 5:
                all_vers += f" (+{len(versions) - 5} more)"
            table.add_row(track, latest, all_vers)

        console.print(table)

        if len(tracks) > 10:
            console.print(
                f"\n[dim]Showing 10 of {len(tracks)} tracks. Use --json for full output.[/dim]"
            )

    except ValueError as e:
        if output_json:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "error_code": MavenErrorCode.INVALID_COORDINATE.value,
                        "message": str(e),
                    }
                )
            )
        else:
            console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        if output_json:
            print(
                json.dumps(
                    {
                        "status": "error",
                        "error_code": MavenErrorCode.MAVEN_API_ERROR.value,
                        "message": str(e),
                    }
                )
            )
        else:
            console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


# =============================================================================
# POM Parsing Functions
# =============================================================================

MAVEN_NAMESPACE = {"m": "http://maven.apache.org/POM/4.0.0"}


def find_pom_text(elem: Element, path: str) -> str | None:
    """Find text in element with namespace handling."""
    ns = MAVEN_NAMESPACE
    # Try with namespace
    found = elem.find(f"m:{path}", ns)
    if found is not None and found.text:
        return found.text
    # Try without namespace
    found = elem.find(path)
    if found is not None and found.text:
        return found.text
    return None


def extract_pom_properties(root: Element) -> dict[str, str]:
    """Extract properties from POM."""
    ns = MAVEN_NAMESPACE
    properties: dict[str, str] = {}
    props_elem = root.find("m:properties", ns) or root.find("properties")
    if props_elem is not None:
        for prop in props_elem:
            # Handle namespace in tag name
            tag = prop.tag
            if "}" in tag:
                tag = tag.split("}")[1]
            if prop.text:
                properties[tag] = prop.text
    return properties


def resolve_property(value: str, properties: dict[str, str]) -> str | None:
    """Resolve ${property} references."""
    if not value:
        return None
    if not value.startswith("${"):
        return value
    # Extract property name
    prop_name = value[2:-1]  # Remove ${ and }
    # Handle project.version specially
    if prop_name == "project.version":
        return None  # Can't resolve without more context
    return properties.get(prop_name)


def parse_pom_dependencies(pom_path: Path) -> dict[str, Any]:
    """Parse POM file and extract dependencies with resolved versions."""
    try:
        tree = ET.parse(pom_path)
        root = tree.getroot()
        ns = MAVEN_NAMESPACE

        # Extract properties for version resolution
        properties = extract_pom_properties(root)

        # Also get parent properties if version references them
        parent_elem = root.find("m:parent", ns) or root.find("parent")
        parent_version = None
        if parent_elem is not None:
            parent_version = find_pom_text(parent_elem, "version")

        # Get project version
        project_version = find_pom_text(root, "version") or parent_version
        if project_version:
            properties["project.version"] = project_version

        dependencies = []

        # Extract from <dependencies> section
        deps_sections = [
            ("dependencies", "direct"),
            ("dependencyManagement/dependencies", "managed"),
        ]

        for section_path, dep_type in deps_sections:
            # Navigate to section
            parts = section_path.split("/")
            container = root
            for part in parts:
                found = container.find(f"m:{part}", ns) or container.find(part)
                if found is None:
                    container = None
                    break
                container = found

            if container is None:
                continue

            # Find all dependencies
            dep_elems = container.findall("m:dependency", ns) or container.findall("dependency")

            for dep in dep_elems:
                group_id = find_pom_text(dep, "groupId")
                artifact_id = find_pom_text(dep, "artifactId")
                version_raw = find_pom_text(dep, "version")
                scope = find_pom_text(dep, "scope") or "compile"
                dep_type_attr = find_pom_text(dep, "type") or "jar"

                if not group_id or not artifact_id:
                    continue

                # Skip test dependencies for version checking (optional)
                # if scope == "test":
                #     continue

                # Resolve version
                version = None
                if version_raw:
                    version = resolve_property(version_raw, properties)

                # Skip BOM imports (type=pom, scope=import)
                if dep_type_attr == "pom" and scope == "import":
                    continue

                dependencies.append(
                    {
                        "group_id": group_id,
                        "artifact_id": artifact_id,
                        "version": version,
                        "version_raw": version_raw,
                        "scope": scope,
                        "type": dep_type,
                    }
                )

        return {
            "status": "success",
            "result": {
                "pom_path": str(pom_path),
                "properties": properties,
                "dependencies": dependencies,
            },
        }

    except ET.ParseError as e:
        return {
            "status": "error",
            "error_code": "POM_PARSE_ERROR",
            "message": f"XML parse error: {e}",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_code": "POM_PARSE_ERROR",
            "message": f"Error parsing POM: {e}",
        }


@cli.command()
@click.option("--path", "-p", required=True, help="Path to pom.xml file or directory")
@click.option("--include-managed", is_flag=True, help="Include dependencyManagement entries")
@click.option("--include-test", is_flag=True, help="Include test-scoped dependencies")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def pom(path: str, include_managed: bool, include_test: bool, output_json: bool):
    """Check all dependencies in a POM file for available updates."""
    pom_path = Path(path).expanduser().resolve()

    # If directory, look for pom.xml
    if pom_path.is_dir():
        pom_path = pom_path / "pom.xml"

    if not pom_path.exists():
        error = {
            "status": "error",
            "error_code": "FILE_NOT_FOUND",
            "message": f"POM file not found: {path}",
        }
        if output_json:
            print(json.dumps(error, indent=2))
        else:
            console.print(f"[red]Error:[/red] {error['message']}")
        sys.exit(1)

    # Parse POM
    parse_result = parse_pom_dependencies(pom_path)
    if parse_result["status"] == "error":
        if output_json:
            print(json.dumps(parse_result, indent=2))
        else:
            console.print(f"[red]Error:[/red] {parse_result['message']}")
        sys.exit(1)

    pom_deps = parse_result["result"]["dependencies"]

    # Filter dependencies
    deps_to_check = []
    for dep in pom_deps:
        # Skip if no version (managed elsewhere)
        if not dep["version"]:
            continue
        # Skip managed unless requested
        if dep["type"] == "managed" and not include_managed:
            continue
        # Skip test unless requested
        if dep["scope"] == "test" and not include_test:
            continue
        deps_to_check.append(dep)

    if not output_json:
        console.print(
            f"\n[bold]Checking {len(deps_to_check)} dependencies from {pom_path.name}[/bold]\n"
        )

    # Check each dependency
    results = []
    with_patch = 0
    with_minor = 0
    with_major = 0
    errors = 0

    for dep in deps_to_check:
        coord = f"{dep['group_id']}:{dep['artifact_id']}"
        version = dep["version"]

        if not output_json:
            console.print(f"[dim]Checking {coord}...[/dim]", end="\r")

        try:
            check_result = check_version(coord, version)
            if check_result["status"] == "success":
                r = check_result["result"]
                results.append(
                    {
                        "dependency": coord,
                        "current_version": version,
                        "scope": dep["scope"],
                        "latest_patch": r["latest_versions"]["patch"],
                        "latest_minor": r["latest_versions"]["minor"],
                        "latest_major": r["latest_versions"]["major"],
                        "has_patch_update": r["has_patch_update"],
                        "has_minor_update": r["has_minor_update"],
                        "has_major_update": r["has_major_update"],
                    }
                )
                if r["has_patch_update"]:
                    with_patch += 1
                if r["has_minor_update"]:
                    with_minor += 1
                if r["has_major_update"]:
                    with_major += 1
            else:
                results.append(
                    {
                        "dependency": coord,
                        "current_version": version,
                        "scope": dep["scope"],
                        "error": check_result.get("message", "Unknown error"),
                    }
                )
                errors += 1
        except Exception as e:
            results.append(
                {
                    "dependency": coord,
                    "current_version": version,
                    "scope": dep["scope"],
                    "error": str(e),
                }
            )
            errors += 1

    # Extract version properties (properties ending in .version or -version)
    version_properties = {}
    for prop_name, prop_value in parse_result["result"]["properties"].items():
        if prop_name.endswith(".version") or prop_name.endswith("-version"):  # noqa: SIM102
            # Skip non-version-like values
            if prop_value and not prop_value.startswith("$"):
                version_properties[prop_name] = prop_value

    # Build final result
    final_result = {
        "status": "success",
        "result": {
            "pom_path": str(pom_path),
            "total_checked": len(deps_to_check),
            "with_patch_updates": with_patch,
            "with_minor_updates": with_minor,
            "with_major_updates": with_major,
            "errors": errors,
            "dependencies": results,
            "version_properties": version_properties,
        },
    }

    if output_json:
        print(json.dumps(final_result, indent=2))
        return

    # Pretty print
    console.print("[bold]Results:[/bold]")
    console.print(f"  Total checked: {len(deps_to_check)}")
    console.print(f"  With patch updates: {with_patch}")
    console.print(f"  With minor updates: {with_minor}")
    console.print(f"  With major updates: {with_major}")
    console.print(f"  Errors: {errors}")

    # Show table of updates
    updates = [
        r
        for r in results
        if r.get("has_patch_update") or r.get("has_minor_update") or r.get("has_major_update")
    ]

    if updates:
        console.print(f"\n[bold]Available Updates ({len(updates)}):[/bold]")

        table = Table()
        table.add_column("Dependency", style="cyan")
        table.add_column("Current", style="yellow")
        table.add_column("Patch", style="green")
        table.add_column("Minor", style="green")
        table.add_column("Major", style="red")

        for r in updates:
            patch = r.get("latest_patch", "-") or "-"
            minor = r.get("latest_minor", "-") or "-"
            major = r.get("latest_major", "-") or "-"

            # Highlight if update available
            if r.get("has_patch_update") and patch != "-":
                patch = f"[bold]{patch}[/bold]"
            if r.get("has_minor_update") and minor != "-":
                minor = f"[bold]{minor}[/bold]"
            if r.get("has_major_update") and major != "-":
                major = f"[bold]{major}[/bold]"

            table.add_row(r["dependency"], r["current_version"], patch, minor, major)

        console.print(table)

    # Show errors if any
    error_results = [r for r in results if "error" in r]
    if error_results:
        console.print(f"\n[bold red]Errors ({len(error_results)}):[/bold red]")
        for r in error_results:
            console.print(f"  {r['dependency']}: {r['error']}")


if __name__ == "__main__":
    cli()
