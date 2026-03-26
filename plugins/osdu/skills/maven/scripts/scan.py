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
Maven Security Scanning Script

Scan Maven projects for security vulnerabilities using Trivy and analyze POM files.

Usage:
    uv run maven_scan.py scan --path "/path/to/project"
    uv run maven_scan.py analyze --path "/path/to/pom.xml"
"""

import json
import subprocess
import sys
import tempfile
import defusedxml.ElementTree as ET  # noqa: N817
from xml.etree.ElementTree import Element  # type annotation only
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console(stderr=True)


# =============================================================================
# Self-Check: Fail-Fast Dependency Validation
# =============================================================================


def require_trivy() -> None:
    """Check trivy is installed, exit with guidance if missing.

    This function implements the fail-fast pattern - it runs at script start
    and exits immediately with clear installation guidance if trivy is not found.
    """
    try:
        result = subprocess.run(
            ["trivy", "--version"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            raise FileNotFoundError
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("Error: trivy is not installed or not working", file=sys.stderr)
        print("", file=sys.stderr)
        print("Install trivy:", file=sys.stderr)
        print("  macOS:   brew install trivy", file=sys.stderr)
        print(
            "  Linux:   curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin",
            file=sys.stderr,
        )
        print("  Windows: winget install AquaSecurity.Trivy", file=sys.stderr)
        print("", file=sys.stderr)
        print("Then re-run this command.", file=sys.stderr)
        sys.exit(1)


# Fail-fast: Check trivy is available before doing anything else
require_trivy()

# =============================================================================
# Constants and Types
# =============================================================================

MAVEN_NAMESPACE = {"m": "http://maven.apache.org/POM/4.0.0"}


class MavenErrorCode(str, Enum):
    """Error codes matching reference implementation."""

    INVALID_PATH = "INVALID_PATH"
    POM_PARSE_ERROR = "POM_PARSE_ERROR"
    TRIVY_NOT_AVAILABLE = "TRIVY_NOT_AVAILABLE"
    TRIVY_SCAN_FAILED = "TRIVY_SCAN_FAILED"


class VulnerabilitySeverity(str, Enum):
    """Vulnerability severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


@dataclass
class Vulnerability:
    """Vulnerability information matching reference format."""

    cve_id: str
    severity: VulnerabilitySeverity
    package_name: str
    installed_version: str
    fixed_version: str | None
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "cve_id": self.cve_id,
            "severity": self.severity.value,
            "package_name": self.package_name,
            "installed_version": self.installed_version,
            "fixed_version": self.fixed_version,
            "description": self.description,
        }


@dataclass
class DeduplicatedVulnerability:
    """Deduplicated vulnerability with version tracking."""

    cve_id: str
    severity: VulnerabilitySeverity
    package_name: str
    versions_found: list[str]
    occurrence_count: int
    fixed_version: str | None
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "cve_id": self.cve_id,
            "severity": self.severity.value,
            "package_name": self.package_name,
            "versions_found": sorted(set(self.versions_found)),
            "occurrence_count": self.occurrence_count,
            "fixed_version": self.fixed_version,
            "description": self.description,
        }


@dataclass
class PomDependency:
    """Dependency from POM file."""

    group_id: str
    artifact_id: str
    version: str | None
    scope: str
    optional: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "artifact_id": self.artifact_id,
            "version": self.version,
            "scope": self.scope,
            "optional": self.optional,
        }


# =============================================================================
# Trivy Integration
# =============================================================================

_trivy_checked = False
_trivy_available: bool | None = None


def check_trivy_available() -> bool:
    """Check if Trivy is installed and available."""
    global _trivy_checked, _trivy_available

    if _trivy_checked:
        return _trivy_available or False

    _trivy_checked = True
    try:
        result = subprocess.run(
            ["trivy", "--version"],
            capture_output=True,
            timeout=10,
        )
        _trivy_available = result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        _trivy_available = False

    return _trivy_available


def run_trivy_scan(
    target: str, severity_filter: list[str] | None = None
) -> tuple[bool, list[Vulnerability] | str]:
    """Run Trivy security scan on target.

    Returns:
        Tuple of (success, vulnerabilities or error_message)
    """
    if not check_trivy_available():
        return False, "Trivy not available. Install: brew install trivy"

    if severity_filter is None:
        severity_filter = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    severity_filter = [s.upper() for s in severity_filter]

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        output_file = tmp.name

    try:
        cmd = [
            "trivy",
            "fs",
            "--security-checks",
            "vuln",
            "--format",
            "json",
            "--output",
            output_file,
            "--severity",
            ",".join(severity_filter),
            target,
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
        )

        if result.returncode != 0:
            return False, f"Trivy scan failed: {result.stderr}"

        with open(output_file) as f:
            trivy_data = json.load(f)

        vulnerabilities = process_trivy_results(trivy_data)
        return True, vulnerabilities

    except subprocess.TimeoutExpired:
        return False, "Trivy scan timed out after 5 minutes"
    except json.JSONDecodeError as e:
        return False, f"Failed to parse Trivy output: {e}"
    except Exception as e:
        return False, f"Trivy scan error: {e}"
    finally:
        Path(output_file).unlink(missing_ok=True)


def process_trivy_results(trivy_data: dict) -> list[Vulnerability]:
    """Parse Trivy JSON output into Vulnerability objects."""
    vulnerabilities = []

    for result in trivy_data.get("Results", []):
        for vuln in result.get("Vulnerabilities", []):
            # Parse package info
            pkg_id = vuln.get("PkgID", "")
            parts = pkg_id.split(":")
            if len(parts) >= 2:
                package_name = f"{parts[0]}:{parts[1]}"
                installed_version = (
                    parts[2] if len(parts) >= 3 else vuln.get("InstalledVersion", "")
                )
            else:
                package_name = pkg_id
                installed_version = vuln.get("InstalledVersion", "")

            # Parse severity
            severity_str = vuln.get("Severity", "UNKNOWN").upper()
            try:
                severity = VulnerabilitySeverity(severity_str.lower())
            except ValueError:
                severity = VulnerabilitySeverity.UNKNOWN

            vulnerabilities.append(
                Vulnerability(
                    cve_id=vuln.get("VulnerabilityID", ""),
                    severity=severity,
                    package_name=package_name,
                    installed_version=installed_version,
                    fixed_version=vuln.get("FixedVersion"),
                    description=vuln.get("Description", "")[:500],  # Truncate long descriptions
                )
            )

    return vulnerabilities


def deduplicate_vulnerabilities(
    vulnerabilities: list[Vulnerability],
    detail_severities: list[str] | None = None,
    description_limit: int = 200,
) -> dict[str, Any]:
    """Deduplicate vulnerabilities by (CVE_ID, package_name).

    Args:
        vulnerabilities: List of raw vulnerabilities
        detail_severities: Severities to include in detail (default: CRITICAL, HIGH)
        description_limit: Max description length (default: 200)

    Returns:
        Dict with 'detailed' (deduplicated list) and 'summary' (counts by severity)
    """
    if detail_severities is None:
        detail_severities = ["critical", "high"]

    # Track unique CVEs by (cve_id, package_name)
    seen: dict[tuple[str, str], DeduplicatedVulnerability] = {}

    # Count all severities (including those not in detail)
    severity_counts = {s.value: 0 for s in VulnerabilitySeverity}
    unique_cve_ids: set[str] = set()

    for vuln in vulnerabilities:
        severity_counts[vuln.severity.value] += 1
        unique_cve_ids.add(vuln.cve_id)

        # Only track details for specified severities
        if vuln.severity.value not in detail_severities:
            continue

        key = (vuln.cve_id, vuln.package_name)

        if key in seen:
            # Add version to existing entry
            existing = seen[key]
            existing.versions_found.append(vuln.installed_version)
            existing.occurrence_count += 1
            # Keep the most specific fixed version (prefer non-None)
            if vuln.fixed_version and not existing.fixed_version:
                existing.fixed_version = vuln.fixed_version
        else:
            # Create new deduplicated entry
            desc = vuln.description
            if len(desc) > description_limit:
                desc = desc[:description_limit] + "..."

            seen[key] = DeduplicatedVulnerability(
                cve_id=vuln.cve_id,
                severity=vuln.severity,
                package_name=vuln.package_name,
                versions_found=[vuln.installed_version],
                occurrence_count=1,
                fixed_version=vuln.fixed_version,
                description=desc,
            )

    # Sort by severity (critical first) then by CVE ID
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "unknown": 4}
    detailed = sorted(
        seen.values(), key=lambda v: (severity_order.get(v.severity.value, 5), v.cve_id)
    )

    return {
        "summary": {
            "total_entries": len(vulnerabilities),
            "unique_cves": len(unique_cve_ids),
            "deduplicated_count": len(detailed),
            "severity_counts": severity_counts,
        },
        "detailed": [v.to_dict() for v in detailed],
    }


# =============================================================================
# POM Analysis
# =============================================================================


def find_text(elem: Element, path: str, ns: dict[str, str]) -> str | None:
    """Find text in element with namespace handling."""
    # Try with namespace
    found = elem.find(f"m:{path}", ns)
    if found is not None and found.text:
        return found.text
    # Try without namespace
    found = elem.find(path)
    if found is not None and found.text:
        return found.text
    return None


def extract_dependencies(root: Element, path: str, ns: dict[str, str]) -> list[PomDependency]:
    """Extract dependencies from POM element."""
    dependencies: list[PomDependency] = []

    # Navigate to container
    parts = path.split("/")
    container = root
    for part in parts:
        found = container.find(f"m:{part}", ns) or container.find(part)
        if found is None:
            return dependencies
        container = found

    # Find dependencies
    dep_elems = container.findall("m:dependency", ns) or container.findall("dependency")

    for dep in dep_elems:
        group_id = find_text(dep, "groupId", ns) or ""
        artifact_id = find_text(dep, "artifactId", ns) or ""
        version = find_text(dep, "version", ns)
        scope = find_text(dep, "scope", ns) or "compile"
        optional_str = find_text(dep, "optional", ns)
        optional = optional_str == "true" if optional_str else False

        if group_id and artifact_id:
            dependencies.append(
                PomDependency(
                    group_id=group_id,
                    artifact_id=artifact_id,
                    version=version,
                    scope=scope,
                    optional=optional,
                )
            )

    return dependencies


def analyze_pom(pom_path: Path) -> dict[str, Any]:
    """Analyze POM file and extract project information."""
    try:
        tree = ET.parse(pom_path)
        root = tree.getroot()
        ns = MAVEN_NAMESPACE

        # Extract basic project info
        group_id = find_text(root, "groupId", ns)
        artifact_id = find_text(root, "artifactId", ns)
        version = find_text(root, "version", ns)
        packaging = find_text(root, "packaging", ns) or "jar"

        # Extract parent if present
        parent: dict[str, str] | None = None
        parent_elem = root.find("m:parent", ns) or root.find("parent")
        if parent_elem is not None:
            parent = {
                "group_id": find_text(parent_elem, "groupId", ns) or "",
                "artifact_id": find_text(parent_elem, "artifactId", ns) or "",
                "version": find_text(parent_elem, "version", ns) or "",
            }

        # Extract properties
        properties: dict[str, str] = {}
        props_elem = root.find("m:properties", ns) or root.find("properties")
        if props_elem is not None:
            for prop in props_elem:
                tag = prop.tag.replace(f"{{{ns.get('m', '')}}}", "")
                if prop.text:
                    properties[tag] = prop.text

        # Extract dependencies
        dependencies = extract_dependencies(root, "dependencies", ns)
        dep_mgmt = extract_dependencies(root, "dependencyManagement/dependencies", ns)

        # Extract modules
        modules: list[str] = []
        modules_elem = root.find("m:modules", ns) or root.find("modules")
        if modules_elem is not None:
            for module in modules_elem.findall("m:module", ns) or modules_elem.findall("module"):
                if module.text:
                    modules.append(module.text)

        return {
            "status": "success",
            "result": {
                "pom_path": str(pom_path),
                "group_id": group_id,
                "artifact_id": artifact_id,
                "version": version,
                "packaging": packaging,
                "parent": parent,
                "dependencies": [d.to_dict() for d in dependencies],
                "dependency_management": [d.to_dict() for d in dep_mgmt],
                "properties": properties,
                "modules": modules,
            },
        }

    except ET.ParseError as e:
        return {
            "status": "error",
            "error_code": MavenErrorCode.POM_PARSE_ERROR.value,
            "message": f"XML parse error: {e}",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_code": MavenErrorCode.POM_PARSE_ERROR.value,
            "message": f"POM analysis error: {e}",
        }


# =============================================================================
# CLI Commands
# =============================================================================


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Maven security scanning - Scan for vulnerabilities and analyze POMs."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
@click.option("--path", "-p", required=True, help="Path to project directory or pom.xml")
@click.option(
    "--severity", "-s", default="critical,high,medium,low", help="Severity filter (comma-separated)"
)
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option(
    "--compact", is_flag=True, help="Deduplicate CVEs and show details only for CRITICAL/HIGH"
)
def scan(path: str, severity: str, output_json: bool, compact: bool):
    """Scan project for security vulnerabilities using Trivy."""
    scan_path = Path(path).expanduser().resolve()

    # Validate path
    if not scan_path.exists():
        result = {
            "status": "error",
            "error_code": MavenErrorCode.INVALID_PATH.value,
            "message": f"Path does not exist: {path}",
        }
        if output_json:
            print(json.dumps(result, indent=2))
        else:
            console.print(f"[red]Error:[/red] {result['message']}")
        sys.exit(1)

    # Determine target
    if scan_path.is_file() and scan_path.name.endswith(".xml"):
        target = str(scan_path.parent)  # Scan the directory containing the POM
    elif scan_path.is_dir():
        if not (scan_path / "pom.xml").exists():
            result = {
                "status": "error",
                "error_code": MavenErrorCode.POM_PARSE_ERROR.value,
                "message": f"No pom.xml found in directory: {path}",
            }
            if output_json:
                print(json.dumps(result, indent=2))
            else:
                console.print(f"[red]Error:[/red] {result['message']}")
            sys.exit(1)
        target = str(scan_path)
    else:
        result = {
            "status": "error",
            "error_code": MavenErrorCode.INVALID_PATH.value,
            "message": f"Invalid path: {path}",
        }
        if output_json:
            print(json.dumps(result, indent=2))
        else:
            console.print(f"[red]Error:[/red] {result['message']}")
        sys.exit(1)

    # Parse severity filter
    severity_filter = [s.strip().upper() for s in severity.split(",")]

    if not output_json:
        console.print(f"\n[bold]Scanning:[/bold] {target}")
        console.print(f"[dim]Severity filter: {', '.join(severity_filter)}[/dim]")
        console.print("[dim]Running Trivy scan...[/dim]\n")

    # Run scan
    success, result_data = run_trivy_scan(target, severity_filter)

    if not success:
        error_code = (
            MavenErrorCode.TRIVY_NOT_AVAILABLE.value
            if "not available" in str(result_data)
            else MavenErrorCode.TRIVY_SCAN_FAILED.value
        )
        result = {
            "status": "error",
            "error_code": error_code,
            "message": result_data,
        }
        if output_json:
            print(json.dumps(result, indent=2))
        else:
            console.print(f"[red]Error:[/red] {result_data}")
            if "not available" in str(result_data):
                console.print("\n[dim]Install Trivy: brew install trivy[/dim]")
        sys.exit(1)

    # Process vulnerabilities
    vulnerabilities = result_data
    severity_counts = {s.value: 0 for s in VulnerabilitySeverity}
    for vuln in vulnerabilities:
        severity_counts[vuln.severity.value] += 1

    if compact:
        # Deduplicate and tier by severity
        deduped = deduplicate_vulnerabilities(
            vulnerabilities,
            detail_severities=["critical", "high"],
            description_limit=200,
        )
        scan_result = {
            "status": "success",
            "result": {
                "mode": "compact",
                "vulnerabilities_found": len(vulnerabilities) > 0,
                "scan_target": target,
                "trivy_available": True,
                "summary": deduped["summary"],
                "vulnerabilities": deduped["detailed"],
            },
        }
    else:
        scan_result = {
            "status": "success",
            "result": {
                "mode": "full",
                "vulnerabilities_found": len(vulnerabilities) > 0,
                "total_vulnerabilities": len(vulnerabilities),
                "severity_counts": severity_counts,
                "scan_target": target,
                "trivy_available": True,
                "vulnerabilities": [v.to_dict() for v in vulnerabilities],
            },
        }

    if output_json:
        print(json.dumps(scan_result, indent=2))
        return

    # Pretty print
    if not vulnerabilities:
        console.print(Panel("[green]No vulnerabilities found![/green]", title="Scan Result"))
        return

    if compact:
        summary = scan_result["result"]["summary"]
        console.print(
            Panel(
                f"[yellow]Found {summary['total_entries']} vulnerability entries ({summary['unique_cves']} unique CVEs)[/yellow]\n\n"
                f"Critical: {summary['severity_counts']['critical']} | "
                f"High: {summary['severity_counts']['high']} | "
                f"Medium: {summary['severity_counts']['medium']} | "
                f"Low: {summary['severity_counts']['low']}\n\n"
                f"[dim]Showing {summary['deduplicated_count']} deduplicated CRITICAL/HIGH entries[/dim]",
                title="Scan Result (Compact Mode)",
            )
        )

        table = Table(title="CRITICAL/HIGH Vulnerabilities (Deduplicated)")
        table.add_column("CVE", style="red")
        table.add_column("Severity")
        table.add_column("Package", style="cyan")
        table.add_column("Versions Found")
        table.add_column("Count")
        table.add_column("Fixed")

        severity_colors = {
            "critical": "red bold",
            "high": "red",
        }

        for vuln in scan_result["result"]["vulnerabilities"][:50]:
            sev_style = severity_colors.get(vuln["severity"], "white")
            versions = ", ".join(vuln["versions_found"][:3])
            if len(vuln["versions_found"]) > 3:
                versions += f" (+{len(vuln['versions_found']) - 3})"
            table.add_row(
                vuln["cve_id"],
                f"[{sev_style}]{vuln['severity'].upper()}[/{sev_style}]",
                vuln["package_name"],
                versions,
                str(vuln["occurrence_count"]),
                vuln["fixed_version"] or "-",
            )

        console.print(table)

        shown = len(scan_result["result"]["vulnerabilities"])
        if shown > 50:
            console.print(
                f"\n[dim]Showing 50 of {shown} deduplicated entries. Use --json for full output.[/dim]"
            )
    else:
        console.print(
            Panel(
                f"[yellow]Found {len(vulnerabilities)} vulnerabilities[/yellow]\n\n"
                f"Critical: {severity_counts['critical']} | "
                f"High: {severity_counts['high']} | "
                f"Medium: {severity_counts['medium']} | "
                f"Low: {severity_counts['low']}",
                title="Scan Result",
            )
        )

        table = Table(title="Vulnerabilities")
        table.add_column("CVE", style="red")
        table.add_column("Severity")
        table.add_column("Package", style="cyan")
        table.add_column("Installed")
        table.add_column("Fixed")

        severity_colors = {
            "critical": "red bold",
            "high": "red",
            "medium": "yellow",
            "low": "blue",
        }

        for vuln in vulnerabilities[:50]:  # Show top 50
            sev_style = severity_colors.get(vuln.severity.value, "white")
            table.add_row(
                vuln.cve_id,
                f"[{sev_style}]{vuln.severity.value.upper()}[/{sev_style}]",
                vuln.package_name,
                vuln.installed_version,
                vuln.fixed_version or "-",
            )

        console.print(table)

        if len(vulnerabilities) > 50:
            console.print(
                f"\n[dim]Showing 50 of {len(vulnerabilities)} vulnerabilities. Use --json for full output.[/dim]"
            )


@cli.command()
@click.option("--path", "-p", required=True, help="Path to pom.xml file")
@click.option("--check-versions", is_flag=True, help="Also check for version updates")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def analyze(path: str, check_versions: bool, output_json: bool):
    """Analyze POM file structure and dependencies."""
    pom_path = Path(path).expanduser().resolve()

    # If directory, look for pom.xml
    if pom_path.is_dir():
        pom_path = pom_path / "pom.xml"

    # Validate path
    if not pom_path.exists():
        result = {
            "status": "error",
            "error_code": MavenErrorCode.INVALID_PATH.value,
            "message": f"POM file not found: {path}",
        }
        if output_json:
            print(json.dumps(result, indent=2))
        else:
            console.print(f"[red]Error:[/red] {result['message']}")
        sys.exit(1)

    if not pom_path.is_file() or not pom_path.name.endswith(".xml"):
        result = {
            "status": "error",
            "error_code": MavenErrorCode.POM_PARSE_ERROR.value,
            "message": f"Invalid POM file: {path}",
        }
        if output_json:
            print(json.dumps(result, indent=2))
        else:
            console.print(f"[red]Error:[/red] {result['message']}")
        sys.exit(1)

    # Analyze POM
    result = analyze_pom(pom_path)

    if result["status"] == "error":
        if output_json:
            print(json.dumps(result, indent=2))
        else:
            console.print(f"[red]Error:[/red] {result['message']}")
        sys.exit(1)

    # Check versions if requested
    if check_versions and result["result"]["dependencies"]:
        from check import check_version as check_dep_version

        version_checks = []
        for dep in result["result"]["dependencies"]:
            if dep["version"] and not dep["version"].startswith("${"):
                try:
                    coord = f"{dep['group_id']}:{dep['artifact_id']}"
                    check_result = check_dep_version(coord, dep["version"])
                    if check_result["status"] == "success":
                        version_checks.append(
                            {
                                "dependency": coord,
                                "current": dep["version"],
                                "latest_versions": check_result["result"]["latest_versions"],
                                "has_updates": (
                                    check_result["result"]["has_major_update"]
                                    or check_result["result"]["has_minor_update"]
                                    or check_result["result"]["has_patch_update"]
                                ),
                            }
                        )
                except Exception:
                    pass  # Skip failed version checks

        result["result"]["version_checks"] = version_checks

    if output_json:
        print(json.dumps(result, indent=2))
        return

    # Pretty print
    r = result["result"]

    console.print(f"\n[bold]POM Analysis: {pom_path.name}[/bold]")

    # Project info
    info_table = Table(title="Project Information", show_header=False)
    info_table.add_column("Field", style="cyan")
    info_table.add_column("Value")

    info_table.add_row("Group ID", r["group_id"] or "[dim]inherited[/dim]")
    info_table.add_row("Artifact ID", r["artifact_id"] or "-")
    info_table.add_row("Version", r["version"] or "[dim]inherited[/dim]")
    info_table.add_row("Packaging", r["packaging"])

    if r["parent"]:
        parent_str = (
            f"{r['parent']['group_id']}:{r['parent']['artifact_id']}:{r['parent']['version']}"
        )
        info_table.add_row("Parent", parent_str)

    console.print(info_table)

    # Modules
    if r["modules"]:
        console.print(f"\n[bold]Modules ({len(r['modules'])}):[/bold]")
        for module in r["modules"]:
            console.print(f"  - {module}")

    # Dependencies
    deps = r["dependencies"]
    if deps:
        dep_table = Table(title=f"Dependencies ({len(deps)})")
        dep_table.add_column("Group ID", style="cyan")
        dep_table.add_column("Artifact ID")
        dep_table.add_column("Version")
        dep_table.add_column("Scope")

        for dep in deps[:30]:  # Show top 30
            version = dep["version"] or "[dim]managed[/dim]"
            dep_table.add_row(
                dep["group_id"],
                dep["artifact_id"],
                version,
                dep["scope"],
            )

        console.print(dep_table)

        if len(deps) > 30:
            console.print(
                f"[dim]Showing 30 of {len(deps)} dependencies. Use --json for full output.[/dim]"
            )

    # Dependency management
    dep_mgmt = r["dependency_management"]
    if dep_mgmt:
        console.print(f"\n[bold]Dependency Management ({len(dep_mgmt)} entries)[/bold]")

    # Properties
    if r["properties"]:
        console.print(f"\n[bold]Properties ({len(r['properties'])} defined)[/bold]")
        for key, value in list(r["properties"].items())[:10]:
            console.print(f"  {key}: {value[:50]}{'...' if len(value) > 50 else ''}")
        if len(r["properties"]) > 10:
            console.print(f"  [dim]... and {len(r['properties']) - 10} more[/dim]")

    # Version checks
    if check_versions and "version_checks" in r:
        vc = r["version_checks"]
        if vc:
            console.print(
                f"\n[bold]Version Updates ({len([v for v in vc if v['has_updates']])} available)[/bold]"
            )
            for check in vc:
                if check["has_updates"]:
                    latest = check["latest_versions"]["major"] or check["latest_versions"]["minor"]
                    console.print(
                        f"  [yellow]{check['dependency']}[/yellow]: {check['current']} -> {latest}"
                    )


if __name__ == "__main__":
    cli()
