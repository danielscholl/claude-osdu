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
Pytest configuration and shared fixtures for maven skill tests.
"""

import sys
from pathlib import Path

import pytest

# Add the scripts directory to Python path for all tests
scripts_dir = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))


@pytest.fixture(autouse=True)
def reset_caches():
    """Reset caches between tests to ensure isolation."""
    # Reset check cache
    try:
        from check import _cache
        _cache.clear()
    except ImportError:
        pass

    # Reset trivy availability cache
    try:
        import scan
        scan._trivy_checked = False
        scan._trivy_available = None
    except ImportError:
        pass

    yield


@pytest.fixture
def sample_versions():
    """Sample version list for testing."""
    return [
        "5.3.18",
        "5.3.19",
        "5.3.20",
        "5.3.21",
        "5.3.22-SNAPSHOT",
        "5.4.0",
        "5.4.1-RC1",
        "6.0.0",
        "6.0.1",
        "6.1.0",
    ]


@pytest.fixture
def trivy_vulnerability_response():
    """Sample Trivy JSON response with vulnerabilities."""
    return {
        "Results": [
            {
                "Target": "pom.xml",
                "Type": "pom",
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": "CVE-2024-22243",
                        "PkgID": "org.springframework:spring-web:5.3.0",
                        "PkgName": "spring-web",
                        "InstalledVersion": "5.3.0",
                        "FixedVersion": "5.3.32, 6.0.17, 6.1.4",
                        "Severity": "CRITICAL",
                        "Description": "Spring Web vulnerability allowing...",
                    },
                    {
                        "VulnerabilityID": "CVE-2024-22234",
                        "PkgID": "org.springframework:spring-security:5.7.0",
                        "PkgName": "spring-security",
                        "InstalledVersion": "5.7.0",
                        "FixedVersion": "5.7.11",
                        "Severity": "HIGH",
                        "Description": "Spring Security vulnerability...",
                    },
                ]
            }
        ]
    }


@pytest.fixture
def trivy_no_vulnerabilities_response():
    """Sample Trivy JSON response with no vulnerabilities."""
    return {
        "Results": [
            {
                "Target": "pom.xml",
                "Type": "pom",
                "Vulnerabilities": None
            }
        ]
    }
