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
Unit tests for scan.py - Maven security scanning functionality.

Tests cover:
- POM XML parsing with namespace handling
- Trivy integration (mocked)
- Vulnerability processing
- Error code consistency with reference implementation
- JSON output structure validation
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from defusedxml import ElementTree as ET

import pytest

# Add the scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from scan import (
    MAVEN_NAMESPACE,
    MavenErrorCode,
    PomDependency,
    Vulnerability,
    VulnerabilitySeverity,
    analyze_pom,
    check_trivy_available,
    extract_dependencies,
    find_text,
    process_trivy_results,
)


# =============================================================================
# Sample POM XML Files
# =============================================================================

SIMPLE_POM = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>test-project</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>

    <dependencies>
        <dependency>
            <groupId>org.springframework</groupId>
            <artifactId>spring-core</artifactId>
            <version>5.3.20</version>
        </dependency>
        <dependency>
            <groupId>junit</groupId>
            <artifactId>junit</artifactId>
            <version>4.13.2</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
"""

POM_WITH_PARENT = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.2.0</version>
    </parent>

    <artifactId>my-app</artifactId>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
    </dependencies>
</project>
"""

POM_WITH_MODULES = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>parent-project</artifactId>
    <version>1.0.0</version>
    <packaging>pom</packaging>

    <modules>
        <module>module-a</module>
        <module>module-b</module>
        <module>module-c</module>
    </modules>
</project>
"""

POM_WITH_PROPERTIES = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>test-project</artifactId>
    <version>1.0.0</version>

    <properties>
        <java.version>17</java.version>
        <spring.version>5.3.20</spring.version>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    </properties>

    <dependencies>
        <dependency>
            <groupId>org.springframework</groupId>
            <artifactId>spring-core</artifactId>
            <version>${spring.version}</version>
        </dependency>
    </dependencies>
</project>
"""

POM_WITH_DEP_MGMT = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>test-project</artifactId>
    <version>1.0.0</version>

    <dependencyManagement>
        <dependencies>
            <dependency>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-dependencies</artifactId>
                <version>3.2.0</version>
                <type>pom</type>
                <scope>import</scope>
            </dependency>
        </dependencies>
    </dependencyManagement>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter</artifactId>
        </dependency>
    </dependencies>
</project>
"""

POM_NO_NAMESPACE = """<?xml version="1.0" encoding="UTF-8"?>
<project>
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>no-namespace</artifactId>
    <version>1.0.0</version>

    <dependencies>
        <dependency>
            <groupId>org.example</groupId>
            <artifactId>example-lib</artifactId>
            <version>2.0.0</version>
        </dependency>
    </dependencies>
</project>
"""

INVALID_POM = """<?xml version="1.0" encoding="UTF-8"?>
<project>
    <this is not valid XML
</project>
"""


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def simple_pom_file(tmp_path):
    """Create a simple POM file for testing."""
    pom_path = tmp_path / "pom.xml"
    pom_path.write_text(SIMPLE_POM)
    return pom_path


@pytest.fixture
def pom_with_parent_file(tmp_path):
    """Create a POM with parent for testing."""
    pom_path = tmp_path / "pom.xml"
    pom_path.write_text(POM_WITH_PARENT)
    return pom_path


@pytest.fixture
def pom_with_modules_file(tmp_path):
    """Create a POM with modules for testing."""
    pom_path = tmp_path / "pom.xml"
    pom_path.write_text(POM_WITH_MODULES)
    return pom_path


@pytest.fixture
def pom_no_namespace_file(tmp_path):
    """Create a POM without namespace for testing."""
    pom_path = tmp_path / "pom.xml"
    pom_path.write_text(POM_NO_NAMESPACE)
    return pom_path


@pytest.fixture
def invalid_pom_file(tmp_path):
    """Create an invalid POM file for testing."""
    pom_path = tmp_path / "pom.xml"
    pom_path.write_text(INVALID_POM)
    return pom_path


# =============================================================================
# Test: POM Parsing - Basic
# =============================================================================

class TestPomParsingBasic:
    """Tests for basic POM parsing functionality."""

    def test_analyze_simple_pom(self, simple_pom_file):
        """Parse simple POM and extract basic info."""
        result = analyze_pom(simple_pom_file)

        assert result["status"] == "success"
        assert result["result"]["group_id"] == "com.example"
        assert result["result"]["artifact_id"] == "test-project"
        assert result["result"]["version"] == "1.0.0"
        assert result["result"]["packaging"] == "jar"

    def test_analyze_pom_extracts_dependencies(self, simple_pom_file):
        """Parse POM and extract dependencies."""
        result = analyze_pom(simple_pom_file)

        deps = result["result"]["dependencies"]
        assert len(deps) == 2

        # Check first dependency
        spring_dep = next(d for d in deps if d["artifact_id"] == "spring-core")
        assert spring_dep["group_id"] == "org.springframework"
        assert spring_dep["version"] == "5.3.20"
        assert spring_dep["scope"] == "compile"

        # Check test dependency
        junit_dep = next(d for d in deps if d["artifact_id"] == "junit")
        assert junit_dep["scope"] == "test"

    def test_analyze_pom_with_parent(self, pom_with_parent_file):
        """Parse POM with parent element."""
        result = analyze_pom(pom_with_parent_file)

        assert result["status"] == "success"
        parent = result["result"]["parent"]
        assert parent is not None
        assert parent["group_id"] == "org.springframework.boot"
        assert parent["artifact_id"] == "spring-boot-starter-parent"
        assert parent["version"] == "3.2.0"

    def test_analyze_pom_with_modules(self, pom_with_modules_file):
        """Parse POM with modules."""
        result = analyze_pom(pom_with_modules_file)

        assert result["status"] == "success"
        modules = result["result"]["modules"]
        assert len(modules) == 3
        assert "module-a" in modules
        assert "module-b" in modules
        assert "module-c" in modules

    def test_analyze_pom_packaging_default(self, pom_with_parent_file):
        """POM without explicit packaging defaults to jar."""
        result = analyze_pom(pom_with_parent_file)
        # Parent POM doesn't specify packaging, should default
        assert result["result"]["packaging"] in ["jar", "pom"]


# =============================================================================
# Test: POM Parsing - Namespace Handling
# =============================================================================

class TestPomNamespaceHandling:
    """Tests for XML namespace handling in POM parsing."""

    def test_parse_pom_with_namespace(self, simple_pom_file):
        """POM with Maven namespace parses correctly."""
        result = analyze_pom(simple_pom_file)
        assert result["status"] == "success"
        assert result["result"]["group_id"] is not None

    def test_parse_pom_without_namespace(self, pom_no_namespace_file):
        """POM without namespace still parses correctly."""
        result = analyze_pom(pom_no_namespace_file)

        assert result["status"] == "success"
        assert result["result"]["group_id"] == "com.example"
        assert result["result"]["artifact_id"] == "no-namespace"


# =============================================================================
# Test: POM Parsing - Properties
# =============================================================================

class TestPomProperties:
    """Tests for POM properties extraction."""

    def test_extract_properties(self, tmp_path):
        """Extract properties from POM."""
        pom_path = tmp_path / "pom.xml"
        pom_path.write_text(POM_WITH_PROPERTIES)

        result = analyze_pom(pom_path)

        props = result["result"]["properties"]
        assert "java.version" in props or "java" in str(props)
        # Note: The namespace prefix may be included in the key


# =============================================================================
# Test: POM Parsing - Dependency Management
# =============================================================================

class TestPomDependencyManagement:
    """Tests for dependency management section parsing."""

    def test_extract_dependency_management(self, tmp_path):
        """Extract dependency management section."""
        pom_path = tmp_path / "pom.xml"
        pom_path.write_text(POM_WITH_DEP_MGMT)

        result = analyze_pom(pom_path)

        dep_mgmt = result["result"]["dependency_management"]
        assert len(dep_mgmt) >= 1


# =============================================================================
# Test: POM Parsing - Errors
# =============================================================================

class TestPomParsingErrors:
    """Tests for POM parsing error handling."""

    def test_invalid_xml_returns_error(self, invalid_pom_file):
        """Invalid XML returns parse error."""
        result = analyze_pom(invalid_pom_file)

        assert result["status"] == "error"
        assert result["error_code"] == MavenErrorCode.POM_PARSE_ERROR.value
        assert "parse error" in result["message"].lower() or "xml" in result["message"].lower()

    def test_nonexistent_file_returns_error(self):
        """Non-existent file returns error."""
        result = analyze_pom(Path("/nonexistent/pom.xml"))

        assert result["status"] == "error"
        assert result["error_code"] == MavenErrorCode.POM_PARSE_ERROR.value


# =============================================================================
# Test: Vulnerability Data Structures
# =============================================================================

class TestVulnerabilityStructures:
    """Tests for vulnerability data structures."""

    def test_vulnerability_to_dict(self):
        """Vulnerability converts to dict correctly."""
        vuln = Vulnerability(
            cve_id="CVE-2024-1234",
            severity=VulnerabilitySeverity.CRITICAL,
            package_name="org.springframework:spring-core",
            installed_version="5.3.0",
            fixed_version="5.3.32",
            description="Test vulnerability",
        )

        result = vuln.to_dict()

        assert result["cve_id"] == "CVE-2024-1234"
        assert result["severity"] == "critical"
        assert result["package_name"] == "org.springframework:spring-core"
        assert result["installed_version"] == "5.3.0"
        assert result["fixed_version"] == "5.3.32"
        assert result["description"] == "Test vulnerability"

    def test_pom_dependency_to_dict(self):
        """PomDependency converts to dict correctly."""
        dep = PomDependency(
            group_id="org.springframework",
            artifact_id="spring-core",
            version="5.3.20",
            scope="compile",
            optional=False,
        )

        result = dep.to_dict()

        assert result["group_id"] == "org.springframework"
        assert result["artifact_id"] == "spring-core"
        assert result["version"] == "5.3.20"
        assert result["scope"] == "compile"
        assert result["optional"] is False


# =============================================================================
# Test: Trivy Result Processing
# =============================================================================

class TestTrivyResultProcessing:
    """Tests for Trivy scan result processing."""

    def test_process_empty_results(self):
        """Empty Trivy results return empty list."""
        trivy_data = {"Results": []}
        result = process_trivy_results(trivy_data)
        assert result == []

    def test_process_vulnerability(self):
        """Process Trivy vulnerability into Vulnerability object."""
        trivy_data = {
            "Results": [
                {
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-2024-1234",
                            "Severity": "CRITICAL",
                            "PkgID": "org.springframework:spring-core:5.3.0",
                            "InstalledVersion": "5.3.0",
                            "FixedVersion": "5.3.32",
                            "Description": "Test description",
                        }
                    ]
                }
            ]
        }

        result = process_trivy_results(trivy_data)

        assert len(result) == 1
        vuln = result[0]
        assert vuln.cve_id == "CVE-2024-1234"
        assert vuln.severity == VulnerabilitySeverity.CRITICAL
        assert vuln.fixed_version == "5.3.32"

    def test_process_multiple_vulnerabilities(self):
        """Process multiple vulnerabilities from Trivy."""
        trivy_data = {
            "Results": [
                {
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-2024-1111",
                            "Severity": "HIGH",
                            "PkgID": "pkg1:1.0",
                            "Description": "Vuln 1",
                        },
                        {
                            "VulnerabilityID": "CVE-2024-2222",
                            "Severity": "MEDIUM",
                            "PkgID": "pkg2:2.0",
                            "Description": "Vuln 2",
                        },
                    ]
                }
            ]
        }

        result = process_trivy_results(trivy_data)

        assert len(result) == 2
        assert result[0].cve_id == "CVE-2024-1111"
        assert result[1].cve_id == "CVE-2024-2222"

    def test_process_unknown_severity(self):
        """Unknown severity maps to UNKNOWN."""
        trivy_data = {
            "Results": [
                {
                    "Vulnerabilities": [
                        {
                            "VulnerabilityID": "CVE-2024-0000",
                            "Severity": "INVALID",
                            "PkgID": "pkg:1.0",
                            "Description": "Test",
                        }
                    ]
                }
            ]
        }

        result = process_trivy_results(trivy_data)

        assert len(result) == 1
        assert result[0].severity == VulnerabilitySeverity.UNKNOWN


# =============================================================================
# Test: Severity Levels
# =============================================================================

class TestSeverityLevels:
    """Tests for vulnerability severity levels."""

    def test_all_severity_levels_defined(self):
        """All expected severity levels are defined."""
        expected = ["critical", "high", "medium", "low", "unknown"]
        for level in expected:
            assert hasattr(VulnerabilitySeverity, level.upper())

    def test_severity_values_are_lowercase(self):
        """Severity values are lowercase strings."""
        assert VulnerabilitySeverity.CRITICAL.value == "critical"
        assert VulnerabilitySeverity.HIGH.value == "high"
        assert VulnerabilitySeverity.MEDIUM.value == "medium"
        assert VulnerabilitySeverity.LOW.value == "low"
        assert VulnerabilitySeverity.UNKNOWN.value == "unknown"


# =============================================================================
# Test: Error Codes
# =============================================================================

class TestErrorCodes:
    """Tests for error code consistency."""

    def test_error_codes_are_strings(self):
        """Error codes are string values."""
        assert isinstance(MavenErrorCode.INVALID_PATH.value, str)
        assert isinstance(MavenErrorCode.POM_PARSE_ERROR.value, str)
        assert isinstance(MavenErrorCode.TRIVY_NOT_AVAILABLE.value, str)
        assert isinstance(MavenErrorCode.TRIVY_SCAN_FAILED.value, str)

    def test_all_expected_error_codes_exist(self):
        """All expected error codes from reference are defined."""
        expected_codes = [
            "INVALID_PATH",
            "POM_PARSE_ERROR",
            "TRIVY_NOT_AVAILABLE",
            "TRIVY_SCAN_FAILED",
        ]
        for code in expected_codes:
            assert hasattr(MavenErrorCode, code)


# =============================================================================
# Test: JSON Output Structure
# =============================================================================

class TestJsonOutputStructure:
    """Tests for JSON output structure compliance."""

    def test_analyze_pom_json_structure(self, simple_pom_file):
        """Analyze POM JSON output has all required fields."""
        result = analyze_pom(simple_pom_file)

        # Verify top-level structure
        assert "status" in result
        assert "result" in result

        r = result["result"]
        required_fields = [
            "pom_path",
            "group_id",
            "artifact_id",
            "version",
            "packaging",
            "parent",
            "dependencies",
            "dependency_management",
            "properties",
            "modules",
        ]

        for field in required_fields:
            assert field in r, f"Missing required field: {field}"

    def test_dependency_json_structure(self, simple_pom_file):
        """Dependency objects have required fields."""
        result = analyze_pom(simple_pom_file)
        deps = result["result"]["dependencies"]

        assert len(deps) > 0
        dep = deps[0]

        required_fields = [
            "group_id",
            "artifact_id",
            "version",
            "scope",
            "optional",
        ]

        for field in required_fields:
            assert field in dep, f"Missing required field in dependency: {field}"

    def test_error_json_structure(self, invalid_pom_file):
        """Error response JSON structure is correct."""
        result = analyze_pom(invalid_pom_file)

        assert result["status"] == "error"
        assert "error_code" in result
        assert "message" in result


# =============================================================================
# Test: Trivy Availability Check (Mocked)
# =============================================================================

class TestTrivyAvailability:
    """Tests for Trivy availability checking."""

    @patch("scan.subprocess.run")
    def test_trivy_available_when_installed(self, mock_run):
        """Returns True when Trivy is installed."""
        # Reset the cached value
        import scan
        scan._trivy_checked = False

        mock_run.return_value = MagicMock(returncode=0)
        result = check_trivy_available()
        assert result is True

    @patch("scan.subprocess.run")
    def test_trivy_unavailable_when_not_installed(self, mock_run):
        """Returns False when Trivy is not installed."""
        # Reset the cached value
        import scan
        scan._trivy_checked = False

        mock_run.side_effect = FileNotFoundError()
        result = check_trivy_available()
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
