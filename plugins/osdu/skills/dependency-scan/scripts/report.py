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
#     "click",
#     "rich",
#     "defusedxml",
# ]
# ///
"""
Dependency Analysis Report Generator

Analyzes project dependencies, scans for vulnerabilities, and generates
risk-prioritized remediation reports.

Usage:
    uv run report.py [project-path]
    uv run report.py /path/to/project --output reports/
    uv run report.py . --json
"""

import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import click
from rich.console import Console

console = Console(stderr=True)

# =============================================================================
# Constants and Types
# =============================================================================


class ProjectType(str, Enum):
    """Supported project types."""

    MAVEN = "maven"
    NODE = "node"
    PYTHON = "python"
    UNKNOWN = "unknown"


class Severity(str, Enum):
    """Vulnerability severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BumpType(str, Enum):
    """Version bump types."""

    PATCH = "patch"
    MINOR = "minor"
    MAJOR = "major"


class RiskLevel(str, Enum):
    """Risk classification for updates."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class Vulnerability:
    """Represents a security vulnerability."""

    cve_id: str
    severity: Severity
    package_name: str
    installed_version: str
    fixed_version: str
    description: str = ""

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
class DependencyUpdate:
    """Represents an available dependency update."""

    package_name: str
    current_version: str
    latest_version: str
    bump_type: BumpType
    risk_level: RiskLevel
    has_cve: bool = False
    cve_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_name": self.package_name,
            "current_version": self.current_version,
            "latest_version": self.latest_version,
            "bump_type": self.bump_type.value,
            "risk_level": self.risk_level.value,
            "has_cve": self.has_cve,
            "cve_ids": self.cve_ids,
        }


@dataclass
class AnalysisReport:
    """Complete dependency analysis report."""

    project_name: str
    project_version: str
    project_type: ProjectType
    project_path: str
    analyzed_at: str
    vulnerabilities: list[Vulnerability] = field(default_factory=list)
    updates: list[DependencyUpdate] = field(default_factory=list)
    severity_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "success",
            "result": {
                "project_name": self.project_name,
                "project_version": self.project_version,
                "project_type": self.project_type.value,
                "project_path": self.project_path,
                "analyzed_at": self.analyzed_at,
                "severity_counts": self.severity_counts,
                "total_vulnerabilities": len(self.vulnerabilities),
                "total_updates": len(self.updates),
                "vulnerabilities": [v.to_dict() for v in self.vulnerabilities],
                "updates": [u.to_dict() for u in self.updates],
            },
        }


# =============================================================================
# Project Detection
# =============================================================================


def detect_project_type(path: Path) -> ProjectType:
    """Detect project type from build files."""
    if (path / "pom.xml").exists():
        return ProjectType.MAVEN
    if (path / "package.json").exists():
        return ProjectType.NODE
    if (path / "pyproject.toml").exists() or (path / "requirements.txt").exists():
        return ProjectType.PYTHON
    return ProjectType.UNKNOWN


def get_project_info(path: Path, project_type: ProjectType) -> tuple[str, str]:
    """Extract project name and version from build files."""
    if project_type == ProjectType.MAVEN:
        return _get_maven_project_info(path)
    elif project_type == ProjectType.NODE:
        return _get_node_project_info(path)
    elif project_type == ProjectType.PYTHON:
        return _get_python_project_info(path)
    return path.name, "unknown"


def _get_maven_project_info(path: Path) -> tuple[str, str]:
    """Extract project info from pom.xml."""
    import defusedxml.ElementTree as ET

    pom_path = path / "pom.xml"
    if not pom_path.exists():
        return path.name, "unknown"

    try:
        tree = ET.parse(pom_path)
        root = tree.getroot()

        # Handle namespace
        ns = {"m": "http://maven.apache.org/POM/4.0.0"}
        if root.tag.startswith("{"):
            artifact_id = root.find("m:artifactId", ns)
            version = root.find("m:version", ns)
        else:
            artifact_id = root.find("artifactId")
            version = root.find("version")

        name = artifact_id.text if artifact_id is not None else path.name
        ver = version.text if version is not None else "unknown"
        return name, ver
    except Exception:
        return path.name, "unknown"


def _get_node_project_info(path: Path) -> tuple[str, str]:
    """Extract project info from package.json."""
    pkg_path = path / "package.json"
    if not pkg_path.exists():
        return path.name, "unknown"

    try:
        with open(pkg_path) as f:
            data = json.load(f)
        return data.get("name", path.name), data.get("version", "unknown")
    except Exception:
        return path.name, "unknown"


def _get_python_project_info(path: Path) -> tuple[str, str]:
    """Extract project info from pyproject.toml."""
    # Simplified - would need toml parser for full support
    return path.name, "unknown"


# =============================================================================
# Maven Analysis
# =============================================================================


def run_maven_scan(path: Path) -> list[Vulnerability]:
    """Run Trivy vulnerability scan via maven skill."""
    script_path = Path(__file__).parent.parent.parent / "maven" / "scripts" / "scan.py"

    try:
        result = subprocess.run(
            ["uv", "run", str(script_path), "scan", "--path", str(path), "--json"],
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode != 0:
            console.print(f"[yellow]Scan warning: {result.stderr}[/yellow]")
            return []

        data = json.loads(result.stdout)
        if data.get("status") != "success":
            return []

        vulns = []
        for v in data.get("result", {}).get("vulnerabilities", []):
            vulns.append(
                Vulnerability(
                    cve_id=v.get("cve_id", ""),
                    severity=Severity(v.get("severity", "medium").lower()),
                    package_name=v.get("package_name", ""),
                    installed_version=v.get("installed_version", ""),
                    fixed_version=v.get("fixed_version", ""),
                    description=v.get("description", ""),
                )
            )
        return vulns

    except subprocess.TimeoutExpired:
        console.print("[yellow]Scan timed out[/yellow]")
        return []
    except Exception as e:
        console.print(f"[yellow]Scan error: {e}[/yellow]")
        return []


def run_maven_version_check(path: Path) -> list[DependencyUpdate]:
    """Check Maven dependency versions via maven skill."""
    # First, analyze the POM to get dependencies
    script_path = Path(__file__).parent.parent.parent / "maven" / "scripts" / "scan.py"

    try:
        result = subprocess.run(
            [
                "uv",
                "run",
                str(script_path),
                "analyze",
                "--path",
                str(path),
                "--check-versions",
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            return []

        data = json.loads(result.stdout)
        if data.get("status") != "success":
            return []

        updates = []
        for dep in data.get("result", {}).get("dependencies", []):
            if dep.get("has_update"):
                bump_type = _classify_bump(
                    dep.get("version", ""), dep.get("latest_version", "")
                )
                updates.append(
                    DependencyUpdate(
                        package_name=f"{dep.get('group_id', '')}:{dep.get('artifact_id', '')}",
                        current_version=dep.get("version", ""),
                        latest_version=dep.get("latest_version", ""),
                        bump_type=bump_type,
                        risk_level=_bump_to_risk(bump_type),
                    )
                )
        return updates

    except Exception as e:
        console.print(f"[yellow]Version check error: {e}[/yellow]")
        return []


def _classify_bump(current: str, latest: str) -> BumpType:
    """Classify version bump type."""
    try:
        current_parts = current.split(".")
        latest_parts = latest.split(".")

        curr_major = int(current_parts[0]) if current_parts else 0
        latest_major = int(latest_parts[0]) if latest_parts else 0

        if latest_major > curr_major:
            return BumpType.MAJOR

        if len(current_parts) > 1 and len(latest_parts) > 1:
            curr_minor = int(current_parts[1]) if current_parts[1].isdigit() else 0
            latest_minor = int(latest_parts[1]) if latest_parts[1].isdigit() else 0
            if latest_minor > curr_minor:
                return BumpType.MINOR

        return BumpType.PATCH
    except Exception:
        return BumpType.PATCH


def _bump_to_risk(bump_type: BumpType) -> RiskLevel:
    """Convert bump type to risk level."""
    return {
        BumpType.PATCH: RiskLevel.LOW,
        BumpType.MINOR: RiskLevel.MEDIUM,
        BumpType.MAJOR: RiskLevel.HIGH,
    }.get(bump_type, RiskLevel.MEDIUM)


# =============================================================================
# Report Generation
# =============================================================================


def generate_report(path: Path) -> AnalysisReport:
    """Generate complete dependency analysis report."""
    project_type = detect_project_type(path)
    project_name, project_version = get_project_info(path, project_type)

    report = AnalysisReport(
        project_name=project_name,
        project_version=project_version,
        project_type=project_type,
        project_path=str(path.resolve()),
        analyzed_at=datetime.now().isoformat(),
    )

    if project_type == ProjectType.MAVEN:
        console.print("[blue]Scanning for vulnerabilities...[/blue]")
        report.vulnerabilities = run_maven_scan(path)

        console.print("[blue]Checking for version updates...[/blue]")
        report.updates = run_maven_version_check(path)

    elif project_type == ProjectType.NODE:
        console.print("[yellow]Node.js support not yet implemented[/yellow]")

    elif project_type == ProjectType.PYTHON:
        console.print("[yellow]Python support not yet implemented[/yellow]")

    else:
        console.print("[red]Unknown project type - no pom.xml, package.json, or pyproject.toml found[/red]")

    # Calculate severity counts
    report.severity_counts = {
        "critical": sum(1 for v in report.vulnerabilities if v.severity == Severity.CRITICAL),
        "high": sum(1 for v in report.vulnerabilities if v.severity == Severity.HIGH),
        "medium": sum(1 for v in report.vulnerabilities if v.severity == Severity.MEDIUM),
        "low": sum(1 for v in report.vulnerabilities if v.severity == Severity.LOW),
    }

    # Link CVEs to updates
    vuln_packages = {v.package_name: v for v in report.vulnerabilities}
    for update in report.updates:
        if update.package_name in vuln_packages:
            update.has_cve = True
            update.cve_ids.append(vuln_packages[update.package_name].cve_id)

    return report


def render_markdown_report(report: AnalysisReport) -> str:
    """Render report as markdown."""
    lines = [
        f"# Dependency Analysis: {report.project_name}",
        "",
        "## Summary",
        f"- **Analyzed**: {report.analyzed_at[:10]}",
        f"- **Project**: {report.project_name} v{report.project_version}",
        f"- **Type**: {report.project_type.value.title()}",
        f"- **Location**: {report.project_path}",
        "",
    ]

    # Security Vulnerabilities Section
    lines.append("## Security Vulnerabilities")
    lines.append("")

    total_vulns = len(report.vulnerabilities)
    if total_vulns == 0:
        lines.append("No known vulnerabilities detected.")
        lines.append("")
    else:
        lines.append("| Severity | Count |")
        lines.append("|----------|-------|")
        for sev in ["critical", "high", "medium", "low"]:
            count = report.severity_counts.get(sev, 0)
            if count > 0:
                lines.append(f"| {sev.upper()} | {count} |")
        lines.append("")

        # Critical CVEs
        critical = [v for v in report.vulnerabilities if v.severity == Severity.CRITICAL]
        if critical:
            lines.append("### Critical CVEs (Immediate Action Required)")
            lines.append("")
            lines.append("| CVE | Package | Current | Fix Version | Description |")
            lines.append("|-----|---------|---------|-------------|-------------|")
            for v in critical:
                desc = v.description[:50] + "..." if len(v.description) > 50 else v.description
                lines.append(f"| {v.cve_id} | {v.package_name} | {v.installed_version} | {v.fixed_version} | {desc} |")
            lines.append("")

        # High CVEs
        high = [v for v in report.vulnerabilities if v.severity == Severity.HIGH]
        if high:
            lines.append("### High Severity CVEs (Plan for Current Sprint)")
            lines.append("")
            lines.append("| CVE | Package | Current | Fix Version |")
            lines.append("|-----|---------|---------|-------------|")
            for v in high:
                lines.append(f"| {v.cve_id} | {v.package_name} | {v.installed_version} | {v.fixed_version} |")
            lines.append("")

        # Medium CVEs
        medium = [v for v in report.vulnerabilities if v.severity == Severity.MEDIUM]
        if medium:
            lines.append("### Medium Severity CVEs (Maintenance Backlog)")
            lines.append("")
            lines.append("| CVE | Package | Current | Fix Version |")
            lines.append("|-----|---------|---------|-------------|")
            for v in medium:
                lines.append(f"| {v.cve_id} | {v.package_name} | {v.installed_version} | {v.fixed_version} |")
            lines.append("")

    # Dependency Updates Section
    lines.append("## Dependency Updates (Non-CVE)")
    lines.append("")

    non_cve_updates = [u for u in report.updates if not u.has_cve]

    patch_updates = [u for u in non_cve_updates if u.bump_type == BumpType.PATCH]
    minor_updates = [u for u in non_cve_updates if u.bump_type == BumpType.MINOR]
    major_updates = [u for u in non_cve_updates if u.bump_type == BumpType.MAJOR]

    if patch_updates:
        lines.append("### Patch Updates (Low Risk)")
        lines.append("Safe to apply immediately.")
        lines.append("")
        lines.append("| Package | Current | Update To |")
        lines.append("|---------|---------|-----------|")
        for u in patch_updates:
            lines.append(f"| {u.package_name} | {u.current_version} | {u.latest_version} |")
        lines.append("")

    if minor_updates:
        lines.append("### Minor Updates (Medium Risk)")
        lines.append("Review changelog before applying.")
        lines.append("")
        lines.append("| Package | Current | Update To |")
        lines.append("|---------|---------|-----------|")
        for u in minor_updates:
            lines.append(f"| {u.package_name} | {u.current_version} | {u.latest_version} |")
        lines.append("")

    if major_updates:
        lines.append("### Major Updates (High Risk)")
        lines.append("Requires planning and potential code changes.")
        lines.append("")
        lines.append("| Package | Current | Latest |")
        lines.append("|---------|---------|--------|")
        for u in major_updates:
            lines.append(f"| {u.package_name} | {u.current_version} | {u.latest_version} |")
        lines.append("")

    if not patch_updates and not minor_updates and not major_updates:
        lines.append("No non-CVE updates available.")
        lines.append("")

    # Recommendations Section
    lines.append("## Recommendations")
    lines.append("")

    lines.append("### Phase 1: Immediate (Low Risk)")
    phase1 = [u for u in report.updates if u.bump_type == BumpType.PATCH]
    if phase1:
        for u in phase1:
            cve_note = f" (fixes {', '.join(u.cve_ids)})" if u.has_cve else ""
            lines.append(f"- Update {u.package_name} to {u.latest_version}{cve_note}")
    else:
        lines.append("- No immediate updates required")
    lines.append("")

    lines.append("### Phase 2: Short-term (Medium Risk)")
    phase2 = [u for u in report.updates if u.bump_type == BumpType.MINOR]
    if phase2:
        for u in phase2:
            cve_note = f" (fixes {', '.join(u.cve_ids)})" if u.has_cve else ""
            lines.append(f"- Update {u.package_name} to {u.latest_version}{cve_note}")
    else:
        lines.append("- No short-term updates required")
    lines.append("")

    lines.append("### Phase 3: Planned (High Risk)")
    phase3 = [u for u in report.updates if u.bump_type == BumpType.MAJOR]
    if phase3:
        for u in phase3:
            cve_note = f" (fixes {', '.join(u.cve_ids)})" if u.has_cve else ""
            lines.append(f"- Update {u.package_name} to {u.latest_version}{cve_note}")
    else:
        lines.append("- No major updates planned")
    lines.append("")

    # Testing Section
    if report.project_type == ProjectType.MAVEN:
        lines.append("## Testing")
        lines.append("```bash")
        lines.append("# Validate changes")
        lines.append("mvn clean verify")
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


# =============================================================================
# CLI Interface
# =============================================================================


@click.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--output", "-o", default="reports", help="Output directory for report")
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
def main(path: str, output: str, use_json: bool):
    """Generate dependency analysis report."""
    project_path = Path(path).resolve()

    console.print(f"[blue]Analyzing: {project_path}[/blue]")

    report = generate_report(project_path)

    if use_json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        # Ensure output directory exists
        output_dir = Path(output)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"dependencies-{report.project_name}-{date_str}.md"
        output_path = output_dir / filename

        # Write report
        markdown = render_markdown_report(report)
        output_path.write_text(markdown)

        console.print(f"[green]Report written to: {output_path}[/green]")
        print(markdown)


if __name__ == "__main__":
    main()
