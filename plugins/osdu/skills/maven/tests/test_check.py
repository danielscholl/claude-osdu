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
Unit tests for check.py - Maven version checking functionality.

Tests cover:
- Version parsing and comparison logic
- Maven Central API integration (mocked)
- Error code consistency with reference implementation
- JSON output structure validation
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add the scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from check import (
    MavenErrorCode,
    ParsedVersion,
    cache_get,
    cache_set,
    check_version,
    find_latest_versions,
    has_update,
    is_stable_version,
    list_versions,
    parse_version,
    validate_dependency,
)


# =============================================================================
# Test: Version Parsing
# =============================================================================

class TestVersionParsing:
    """Tests for version parsing logic."""

    def test_parse_standard_version(self):
        """Parse standard semantic version."""
        result = parse_version("5.3.20")
        assert result is not None
        assert result.major == 5
        assert result.minor == 3
        assert result.patch == 20
        assert result.qualifier is None
        assert result.original == "5.3.20"

    def test_parse_version_with_release_qualifier(self):
        """Parse version with RELEASE qualifier."""
        result = parse_version("5.3.20.RELEASE")
        assert result is not None
        assert result.major == 5
        assert result.minor == 3
        assert result.patch == 20
        assert result.qualifier == "RELEASE"

    def test_parse_version_with_snapshot(self):
        """Parse SNAPSHOT version."""
        result = parse_version("5.3.21-SNAPSHOT")
        assert result is not None
        assert result.major == 5
        assert result.minor == 3
        assert result.patch == 21
        assert result.qualifier == "SNAPSHOT"

    def test_parse_version_with_rc(self):
        """Parse release candidate version."""
        result = parse_version("6.0.0-RC1")
        assert result is not None
        assert result.major == 6
        assert result.minor == 0
        assert result.patch == 0
        assert result.qualifier == "RC1"

    def test_parse_major_only_version(self):
        """Parse major-only version like some date-based schemes."""
        result = parse_version("21")
        assert result is not None
        assert result.major == 21
        assert result.minor == 0
        assert result.patch == 0

    def test_parse_major_minor_version(self):
        """Parse major.minor version without patch."""
        result = parse_version("3.2")
        assert result is not None
        assert result.major == 3
        assert result.minor == 2
        assert result.patch == 0

    def test_parse_empty_version_returns_none(self):
        """Empty string returns None."""
        assert parse_version("") is None

    def test_parse_invalid_version_returns_none(self):
        """Non-numeric version prefix returns None."""
        assert parse_version("abc.def") is None


# =============================================================================
# Test: Version Comparison
# =============================================================================

class TestVersionComparison:
    """Tests for version comparison logic."""

    def test_compare_major_versions(self):
        """Higher major version is greater."""
        v1 = parse_version("5.0.0")
        v2 = parse_version("6.0.0")
        assert v1 < v2

    def test_compare_minor_versions(self):
        """Higher minor version is greater when major is equal."""
        v1 = parse_version("5.2.0")
        v2 = parse_version("5.3.0")
        assert v1 < v2

    def test_compare_patch_versions(self):
        """Higher patch version is greater when major.minor is equal."""
        v1 = parse_version("5.3.19")
        v2 = parse_version("5.3.20")
        assert v1 < v2

    def test_snapshot_less_than_release(self):
        """SNAPSHOT is less than release version."""
        v1 = parse_version("5.3.20-SNAPSHOT")
        v2 = parse_version("5.3.20")
        assert v1 < v2

    def test_rc_less_than_release(self):
        """RC is less than release version."""
        v1 = parse_version("5.3.20-RC1")
        v2 = parse_version("5.3.20")
        assert v1 < v2

    def test_alpha_less_than_beta(self):
        """Alpha is less than beta."""
        v1 = parse_version("5.3.20-alpha1")
        v2 = parse_version("5.3.20-beta1")
        assert v1 < v2

    def test_qualifier_ranking_order(self):
        """Qualifiers are ranked: SNAPSHOT < alpha < beta < M < RC < RELEASE < none."""
        snapshot = parse_version("1.0.0-SNAPSHOT")
        alpha = parse_version("1.0.0-alpha1")
        beta = parse_version("1.0.0-beta1")
        milestone = parse_version("1.0.0-M1")
        rc = parse_version("1.0.0-RC1")
        release = parse_version("1.0.0.RELEASE")
        final = parse_version("1.0.0")

        assert snapshot < alpha < beta < milestone < rc < release < final


# =============================================================================
# Test: Stability Detection
# =============================================================================

class TestStabilityDetection:
    """Tests for version stability detection."""

    def test_stable_release_version(self):
        """Standard release version is stable."""
        assert is_stable_version("5.3.20") is True

    def test_stable_release_qualifier(self):
        """RELEASE qualifier is stable."""
        assert is_stable_version("5.3.20.RELEASE") is True

    def test_snapshot_is_unstable(self):
        """SNAPSHOT versions are unstable."""
        assert is_stable_version("5.3.21-SNAPSHOT") is False

    def test_alpha_is_unstable(self):
        """Alpha versions are unstable."""
        assert is_stable_version("5.3.20-alpha1") is False

    def test_beta_is_unstable(self):
        """Beta versions are unstable."""
        assert is_stable_version("5.3.20-beta1") is False

    def test_rc_is_unstable(self):
        """Release candidate versions are unstable."""
        assert is_stable_version("5.3.20-RC1") is False

    def test_milestone_is_unstable(self):
        """Milestone versions are unstable."""
        assert is_stable_version("5.3.20-M1") is False


# =============================================================================
# Test: Latest Version Finding
# =============================================================================

class TestLatestVersionFinding:
    """Tests for finding latest versions by track."""

    def test_find_latest_major_minor_patch(self):
        """Find latest versions across all tracks."""
        versions = ["5.3.20", "5.3.21", "5.4.0", "6.0.0", "6.1.0"]
        result = find_latest_versions(versions, "5.3.20")

        assert result["major"] == "6.1.0"
        assert result["minor"] == "5.4.0"
        assert result["patch"] == "5.3.21"

    def test_find_latest_excludes_unstable(self):
        """Latest version finding excludes unstable versions."""
        versions = ["5.3.20", "5.3.21", "5.3.22-SNAPSHOT", "5.4.0-RC1"]
        result = find_latest_versions(versions, "5.3.20")

        assert result["patch"] == "5.3.21"  # Not 5.3.22-SNAPSHOT
        assert result["minor"] == "5.3.21"  # Not 5.4.0-RC1

    def test_find_latest_empty_versions(self):
        """Empty version list returns None values."""
        result = find_latest_versions([], "5.3.20")

        assert result["major"] is None
        assert result["minor"] is None
        assert result["patch"] is None

    def test_find_latest_same_track(self):
        """All versions in same track returns same latest for major/minor/patch."""
        versions = ["5.3.18", "5.3.19", "5.3.20"]
        result = find_latest_versions(versions, "5.3.18")

        assert result["major"] == "5.3.20"
        assert result["minor"] == "5.3.20"
        assert result["patch"] == "5.3.20"


# =============================================================================
# Test: Has Update Detection
# =============================================================================

class TestHasUpdate:
    """Tests for update detection."""

    def test_has_update_when_newer(self):
        """Detects update when latest is newer."""
        assert has_update("5.3.20", "5.3.21") is True

    def test_no_update_when_same(self):
        """No update when versions are same."""
        assert has_update("5.3.20", "5.3.20") is False

    def test_no_update_when_older(self):
        """No update when latest is older."""
        assert has_update("5.3.21", "5.3.20") is False

    def test_no_update_when_none(self):
        """No update when latest is None."""
        assert has_update("5.3.20", None) is False


# =============================================================================
# Test: Dependency Validation
# =============================================================================

class TestDependencyValidation:
    """Tests for Maven coordinate validation."""

    def test_valid_coordinate(self):
        """Valid groupId:artifactId parses correctly."""
        group_id, artifact_id = validate_dependency("org.springframework:spring-core")
        assert group_id == "org.springframework"
        assert artifact_id == "spring-core"

    def test_coordinate_with_extra_colons(self):
        """Coordinate with extra colons parses first two parts."""
        group_id, artifact_id = validate_dependency("org.springframework:spring-core:5.3.0")
        assert group_id == "org.springframework"
        assert artifact_id == "spring-core"

    def test_invalid_coordinate_no_colon(self):
        """Coordinate without colon raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_dependency("spring-core")
        assert "Invalid Maven coordinate" in str(exc_info.value)
        assert "groupId:artifactId" in str(exc_info.value)

    def test_invalid_coordinate_empty_parts(self):
        """Coordinate with empty parts raises ValueError."""
        with pytest.raises(ValueError):
            validate_dependency(":spring-core")

        with pytest.raises(ValueError):
            validate_dependency("org.springframework:")


# =============================================================================
# Test: Cache Functions
# =============================================================================

class TestCache:
    """Tests for caching functionality."""

    def test_cache_set_and_get(self):
        """Cache stores and retrieves values."""
        cache_set("test_key", {"value": 123})
        result = cache_get("test_key")
        assert result == {"value": 123}

    def test_cache_miss_returns_none(self):
        """Cache miss returns None."""
        result = cache_get("nonexistent_key")
        assert result is None


# =============================================================================
# Test: Check Version (Mocked API)
# =============================================================================

class TestCheckVersion:
    """Tests for check_version function with mocked API calls."""

    @patch("check.get_all_versions")
    @patch("check.check_version_exists")
    def test_check_version_success(self, mock_exists, mock_versions):
        """Check version returns success with update info."""
        mock_exists.return_value = True
        mock_versions.return_value = ["5.3.18", "5.3.19", "5.3.20", "5.3.21", "5.4.0", "6.0.0"]

        result = check_version("org.springframework:spring-core", "5.3.20")

        assert result["status"] == "success"
        assert result["result"]["dependency"] == "org.springframework:spring-core"
        assert result["result"]["current_version"] == "5.3.20"
        assert result["result"]["exists"] is True
        assert result["result"]["has_patch_update"] is True
        assert result["result"]["has_minor_update"] is True
        assert result["result"]["has_major_update"] is True

    @patch("check.get_all_versions")
    @patch("check.check_version_exists")
    def test_check_version_not_found(self, mock_exists, mock_versions):
        """Check version returns error when dependency not found."""
        mock_exists.return_value = False
        mock_versions.return_value = []

        result = check_version("org.nonexistent:artifact", "1.0.0")

        assert result["status"] == "error"
        assert result["error_code"] == MavenErrorCode.DEPENDENCY_NOT_FOUND.value

    @patch("check.get_all_versions")
    @patch("check.check_version_exists")
    def test_check_version_json_structure(self, mock_exists, mock_versions):
        """Check version JSON structure matches reference format."""
        mock_exists.return_value = True
        mock_versions.return_value = ["5.3.20", "5.3.21"]

        result = check_version("org.springframework:spring-core", "5.3.20")

        # Verify all required fields exist
        assert "status" in result
        assert "result" in result

        r = result["result"]
        assert "dependency" in r
        assert "current_version" in r
        assert "exists" in r
        assert "latest_versions" in r
        assert "has_major_update" in r
        assert "has_minor_update" in r
        assert "has_patch_update" in r
        assert "total_versions_available" in r

        # Verify latest_versions structure
        lv = r["latest_versions"]
        assert "major" in lv
        assert "minor" in lv
        assert "patch" in lv

    def test_check_version_invalid_coordinate(self):
        """Check version raises for invalid coordinate."""
        with pytest.raises(ValueError):
            check_version("invalid-coord", "1.0.0")


# =============================================================================
# Test: List Versions (Mocked API)
# =============================================================================

class TestListVersions:
    """Tests for list_versions function with mocked API calls."""

    @patch("check.get_all_versions")
    def test_list_versions_success(self, mock_versions):
        """List versions returns grouped tracks."""
        mock_versions.return_value = ["5.3.18", "5.3.19", "5.3.20", "5.4.0", "6.0.0"]

        result = list_versions("org.springframework:spring-core")

        assert result["status"] == "success"
        assert result["result"]["dependency"] == "org.springframework:spring-core"
        assert result["result"]["total_versions"] == 5
        assert "tracks" in result["result"]

    @patch("check.get_all_versions")
    def test_list_versions_tracks_structure(self, mock_versions):
        """List versions tracks are properly grouped by major.minor."""
        mock_versions.return_value = ["5.3.18", "5.3.19", "5.4.0", "6.0.0", "6.1.0"]

        result = list_versions("org.springframework:spring-core")
        tracks = result["result"]["tracks"]

        assert "5.3" in tracks
        assert "5.4" in tracks
        assert "6.0" in tracks
        assert "6.1" in tracks

        # Versions within track should be sorted newest first
        assert tracks["5.3"][0] == "5.3.19"
        assert tracks["5.3"][1] == "5.3.18"

    @patch("check.get_all_versions")
    def test_list_versions_not_found(self, mock_versions):
        """List versions returns error for unknown dependency."""
        mock_versions.return_value = []

        result = list_versions("org.nonexistent:artifact")

        assert result["status"] == "error"
        assert result["error_code"] == MavenErrorCode.DEPENDENCY_NOT_FOUND.value


# =============================================================================
# Test: Error Codes
# =============================================================================

class TestErrorCodes:
    """Tests for error code consistency."""

    def test_error_codes_are_strings(self):
        """Error codes are string values."""
        assert isinstance(MavenErrorCode.INVALID_COORDINATE.value, str)
        assert isinstance(MavenErrorCode.DEPENDENCY_NOT_FOUND.value, str)
        assert isinstance(MavenErrorCode.VERSION_NOT_FOUND.value, str)
        assert isinstance(MavenErrorCode.MAVEN_API_ERROR.value, str)
        assert isinstance(MavenErrorCode.INVALID_INPUT_FORMAT.value, str)

    def test_all_expected_error_codes_exist(self):
        """All expected error codes from reference are defined."""
        expected_codes = [
            "INVALID_COORDINATE",
            "DEPENDENCY_NOT_FOUND",
            "VERSION_NOT_FOUND",
            "MAVEN_API_ERROR",
            "INVALID_INPUT_FORMAT",
        ]
        for code in expected_codes:
            assert hasattr(MavenErrorCode, code)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
