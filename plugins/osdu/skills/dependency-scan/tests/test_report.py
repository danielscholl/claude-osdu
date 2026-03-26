#!/usr/bin/env python3
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
Unit tests for report.py - Dependency analysis report generation.

Tests cover:
- Project type detection
- Risk classification
- Report generation
- JSON output structure
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add the scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from report import (
    AnalysisReport,
    BumpType,
    DependencyUpdate,
    ProjectType,
    RiskLevel,
    Severity,
    Vulnerability,
    detect_project_type,
    render_markdown_report,
    _classify_bump,
    _bump_to_risk,
)


# =============================================================================
# Test: Project Type Detection
# =============================================================================


class TestProjectTypeDetection:
    """Tests for project type detection."""

    def test_detect_maven_project(self, tmp_path):
        """Detect Maven project from pom.xml."""
        (tmp_path / "pom.xml").write_text("<project></project>")
        assert detect_project_type(tmp_path) == ProjectType.MAVEN

    def test_detect_node_project(self, tmp_path):
        """Detect Node project from package.json."""
        (tmp_path / "package.json").write_text("{}")
        assert detect_project_type(tmp_path) == ProjectType.NODE

    def test_detect_python_project_pyproject(self, tmp_path):
        """Detect Python project from pyproject.toml."""
        (tmp_path / "pyproject.toml").write_text("[project]")
        assert detect_project_type(tmp_path) == ProjectType.PYTHON

    def test_detect_python_project_requirements(self, tmp_path):
        """Detect Python project from requirements.txt."""
        (tmp_path / "requirements.txt").write_text("click")
        assert detect_project_type(tmp_path) == ProjectType.PYTHON

    def test_detect_unknown_project(self, tmp_path):
        """Return unknown for unrecognized project."""
        assert detect_project_type(tmp_path) == ProjectType.UNKNOWN

    def test_maven_takes_precedence(self, tmp_path):
        """Maven detection takes precedence over others."""
        (tmp_path / "pom.xml").write_text("<project></project>")
        (tmp_path / "package.json").write_text("{}")
        assert detect_project_type(tmp_path) == ProjectType.MAVEN


# =============================================================================
# Test: Version Bump Classification
# =============================================================================


class TestBumpClassification:
    """Tests for version bump type classification."""

    def test_classify_major_bump(self):
        """Classify major version bump."""
        assert _classify_bump("1.0.0", "2.0.0") == BumpType.MAJOR
        assert _classify_bump("5.3.0", "6.0.0") == BumpType.MAJOR

    def test_classify_minor_bump(self):
        """Classify minor version bump."""
        assert _classify_bump("1.0.0", "1.1.0") == BumpType.MINOR
        assert _classify_bump("5.3.0", "5.4.0") == BumpType.MINOR

    def test_classify_patch_bump(self):
        """Classify patch version bump."""
        assert _classify_bump("1.0.0", "1.0.1") == BumpType.PATCH
        assert _classify_bump("5.3.0", "5.3.1") == BumpType.PATCH

    def test_classify_same_version(self):
        """Same version returns patch."""
        assert _classify_bump("1.0.0", "1.0.0") == BumpType.PATCH


# =============================================================================
# Test: Risk Level Mapping
# =============================================================================


class TestRiskLevelMapping:
    """Tests for bump type to risk level mapping."""

    def test_patch_is_low_risk(self):
        """Patch bumps are low risk."""
        assert _bump_to_risk(BumpType.PATCH) == RiskLevel.LOW

    def test_minor_is_medium_risk(self):
        """Minor bumps are medium risk."""
        assert _bump_to_risk(BumpType.MINOR) == RiskLevel.MEDIUM

    def test_major_is_high_risk(self):
        """Major bumps are high risk."""
        assert _bump_to_risk(BumpType.MAJOR) == RiskLevel.HIGH


# =============================================================================
# Test: Data Structures
# =============================================================================


class TestDataStructures:
    """Tests for data structure serialization."""

    def test_vulnerability_to_dict(self):
        """Vulnerability serializes correctly."""
        vuln = Vulnerability(
            cve_id="CVE-2024-1234",
            severity=Severity.CRITICAL,
            package_name="spring-core",
            installed_version="5.3.0",
            fixed_version="5.3.32",
            description="Test vulnerability",
        )
        result = vuln.to_dict()
        assert result["cve_id"] == "CVE-2024-1234"
        assert result["severity"] == "critical"
        assert result["package_name"] == "spring-core"

    def test_dependency_update_to_dict(self):
        """DependencyUpdate serializes correctly."""
        update = DependencyUpdate(
            package_name="spring-core",
            current_version="5.3.0",
            latest_version="5.3.32",
            bump_type=BumpType.PATCH,
            risk_level=RiskLevel.LOW,
            has_cve=True,
            cve_ids=["CVE-2024-1234"],
        )
        result = update.to_dict()
        assert result["package_name"] == "spring-core"
        assert result["bump_type"] == "patch"
        assert result["risk_level"] == "low"
        assert result["has_cve"] is True

    def test_analysis_report_to_dict(self):
        """AnalysisReport serializes correctly."""
        report = AnalysisReport(
            project_name="test-project",
            project_version="1.0.0",
            project_type=ProjectType.MAVEN,
            project_path="/test/path",
            analyzed_at="2025-01-09T10:00:00",
        )
        result = report.to_dict()
        assert result["status"] == "success"
        assert result["result"]["project_name"] == "test-project"
        assert result["result"]["project_type"] == "maven"


# =============================================================================
# Test: Markdown Report Rendering
# =============================================================================


class TestMarkdownRendering:
    """Tests for markdown report rendering."""

    def test_render_empty_report(self):
        """Render report with no vulnerabilities or updates."""
        report = AnalysisReport(
            project_name="test-project",
            project_version="1.0.0",
            project_type=ProjectType.MAVEN,
            project_path="/test/path",
            analyzed_at="2025-01-09T10:00:00",
            severity_counts={"critical": 0, "high": 0, "medium": 0, "low": 0},
        )
        markdown = render_markdown_report(report)
        assert "# Dependency Analysis: test-project" in markdown
        assert "No known vulnerabilities detected" in markdown

    def test_render_report_with_vulnerabilities(self):
        """Render report with vulnerabilities."""
        report = AnalysisReport(
            project_name="test-project",
            project_version="1.0.0",
            project_type=ProjectType.MAVEN,
            project_path="/test/path",
            analyzed_at="2025-01-09T10:00:00",
            vulnerabilities=[
                Vulnerability(
                    cve_id="CVE-2024-1234",
                    severity=Severity.CRITICAL,
                    package_name="spring-core",
                    installed_version="5.3.0",
                    fixed_version="5.3.32",
                    description="Test",
                )
            ],
            severity_counts={"critical": 1, "high": 0, "medium": 0, "low": 0},
        )
        markdown = render_markdown_report(report)
        assert "Critical CVEs" in markdown
        assert "CVE-2024-1234" in markdown

    def test_render_report_with_updates(self):
        """Render report with dependency updates."""
        report = AnalysisReport(
            project_name="test-project",
            project_version="1.0.0",
            project_type=ProjectType.MAVEN,
            project_path="/test/path",
            analyzed_at="2025-01-09T10:00:00",
            updates=[
                DependencyUpdate(
                    package_name="spring-core",
                    current_version="5.3.0",
                    latest_version="5.3.32",
                    bump_type=BumpType.PATCH,
                    risk_level=RiskLevel.LOW,
                )
            ],
            severity_counts={"critical": 0, "high": 0, "medium": 0, "low": 0},
        )
        markdown = render_markdown_report(report)
        assert "Patch Updates" in markdown
        assert "spring-core" in markdown


# =============================================================================
# Test: Enums
# =============================================================================


class TestEnums:
    """Tests for enum definitions."""

    def test_severity_values(self):
        """All severity levels defined."""
        assert Severity.CRITICAL.value == "critical"
        assert Severity.HIGH.value == "high"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.LOW.value == "low"

    def test_bump_type_values(self):
        """All bump types defined."""
        assert BumpType.PATCH.value == "patch"
        assert BumpType.MINOR.value == "minor"
        assert BumpType.MAJOR.value == "major"

    def test_risk_level_values(self):
        """All risk levels defined."""
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"

    def test_project_type_values(self):
        """All project types defined."""
        assert ProjectType.MAVEN.value == "maven"
        assert ProjectType.NODE.value == "node"
        assert ProjectType.PYTHON.value == "python"
        assert ProjectType.UNKNOWN.value == "unknown"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
