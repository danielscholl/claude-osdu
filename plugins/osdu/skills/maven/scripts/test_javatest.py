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
# requires-python = ">=3.8"
# dependencies = ["pytest"]
# ///
"""
Tests for javatest.py - OSDU Java Project Test Runner

Run with: uv run pytest test_javatest.py -v
Or directly: uv run test_javatest.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Import the module under test
from javatest import (
    OSDU_PROFILES,
    SHARED_MODULE_PATTERNS,
    CommandBuilder,
    EnvironmentLoader,
    ServiceConfig,
    ServiceDiscovery,
    discover_profiles_from_pom,
    get_all_profiles,
    get_service_config,
    is_shared_module,
)

# =============================================================================
# SHARED MODULE DETECTION TESTS
# =============================================================================


class TestIsSharedModule:
    """Tests for is_shared_module() function."""

    @pytest.mark.parametrize(
        "module_name,expected",
        [
            # Should match - contains pattern keywords
            ("partition-core", True),
            ("partition-core-plus", True),
            ("os-core-common", True),
            ("common-lib", True),
            ("shared-utils", True),
            ("partition-api", True),
            ("data-model", True),
            ("os-core-lib-azure", True),
            # Case insensitive
            ("PARTITION-CORE", True),
            ("Common-Lib", True),
            # Should NOT match - no pattern keywords
            ("partition", False),
            ("partition-azure", False),
            ("legal", False),
            ("storage", False),
            ("search-service", False),
            ("indexer-queue-azure-enqueue", False),
        ],
    )
    def test_shared_module_detection(self, module_name: str, expected: bool):
        """Test various module names for shared module detection."""
        assert is_shared_module(module_name) == expected

    def test_all_patterns_are_detected(self):
        """Ensure all defined patterns are actually detected."""
        for pattern in SHARED_MODULE_PATTERNS:
            test_name = f"test-{pattern}-module"
            assert is_shared_module(test_name), f"Pattern '{pattern}' not detected in '{test_name}'"


# =============================================================================
# PROFILE DISCOVERY TESTS
# =============================================================================


class TestDiscoverProfilesFromPom:
    """Tests for discover_profiles_from_pom() function."""

    def test_nonexistent_pom_returns_empty(self, tmp_path: Path):
        """Non-existent POM file should return empty set."""
        result = discover_profiles_from_pom(tmp_path / "nonexistent.xml")
        assert result == set()

    def test_pom_with_namespace(self, tmp_path: Path):
        """POM with Maven namespace should extract profiles."""
        pom_content = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <profiles>
        <profile>
            <id>core</id>
        </profile>
        <profile>
            <id>azure</id>
        </profile>
        <profile>
            <id>gc</id>
        </profile>
    </profiles>
</project>
"""
        pom_path = tmp_path / "pom.xml"
        pom_path.write_text(pom_content)

        result = discover_profiles_from_pom(pom_path)
        assert result == {"core", "azure", "gc"}

    def test_pom_without_namespace(self, tmp_path: Path):
        """POM without namespace should still extract profiles."""
        pom_content = """<?xml version="1.0" encoding="UTF-8"?>
<project>
    <profiles>
        <profile>
            <id>aws</id>
        </profile>
        <profile>
            <id>ibm</id>
        </profile>
    </profiles>
</project>
"""
        pom_path = tmp_path / "pom.xml"
        pom_path.write_text(pom_content)

        result = discover_profiles_from_pom(pom_path)
        assert result == {"aws", "ibm"}

    def test_pom_with_no_profiles(self, tmp_path: Path):
        """POM without profiles section should return empty set."""
        pom_content = """<?xml version="1.0" encoding="UTF-8"?>
<project>
    <groupId>org.opengroup.osdu</groupId>
    <artifactId>test</artifactId>
</project>
"""
        pom_path = tmp_path / "pom.xml"
        pom_path.write_text(pom_content)

        result = discover_profiles_from_pom(pom_path)
        assert result == set()

    def test_pom_with_whitespace_in_profile_id(self, tmp_path: Path):
        """Profile IDs with whitespace should be trimmed."""
        pom_content = """<?xml version="1.0" encoding="UTF-8"?>
<project>
    <profiles>
        <profile>
            <id>  core  </id>
        </profile>
    </profiles>
</project>
"""
        pom_path = tmp_path / "pom.xml"
        pom_path.write_text(pom_content)

        result = discover_profiles_from_pom(pom_path)
        assert result == {"core"}


class TestGetAllProfiles:
    """Tests for get_all_profiles() function."""

    def test_returns_osdu_profiles_when_none_found(self, tmp_path: Path):
        """When no profiles found, should return default OSDU profiles."""
        result = get_all_profiles(tmp_path)
        assert result == OSDU_PROFILES

    def test_discovers_profiles_from_project_pom(self, tmp_path: Path):
        """Should discover profiles from project's pom.xml."""
        pom_content = """<?xml version="1.0" encoding="UTF-8"?>
<project>
    <profiles>
        <profile><id>core</id></profile>
        <profile><id>azure</id></profile>
    </profiles>
</project>
"""
        (tmp_path / "pom.xml").write_text(pom_content)

        result = get_all_profiles(tmp_path)
        assert "core" in result
        assert "azure" in result


# =============================================================================
# SERVICE CONFIG TESTS
# =============================================================================


class TestGetServiceConfig:
    """Tests for get_service_config() function."""

    def test_default_config_for_unknown_service(self):
        """Unknown service should get default pattern-based config."""
        config = get_service_config("my-new-service")

        assert config["base_patterns"] == ["my-new-service"]
        assert config["test_module"] == "my-new-service-test-azure"
        assert "my-new-service-azure" in config["provider_patterns"]
        assert "my-new-service-core" in config["core_patterns"]

    def test_override_for_entitlements(self):
        """Entitlements service should use v2 override patterns."""
        config = get_service_config("entitlements")

        assert "entitlements-v2" in config["base_patterns"]
        assert config["test_module"] == "entitlements-v2-test-azure"

    def test_override_for_search_service(self):
        """Search service should use override patterns."""
        config = get_service_config("search-service")

        assert "search" in config["base_patterns"]
        assert config["test_module"] == "search-test-azure"

    def test_override_for_schema_service(self):
        """Schema service should use core test module."""
        config = get_service_config("schema-service")

        assert config["test_module"] == "schema-test-core"


# =============================================================================
# SERVICE DISCOVERY TESTS
# =============================================================================


class TestServiceDiscovery:
    """Tests for ServiceDiscovery class."""

    def test_validates_empty_service_name(self, tmp_path: Path):
        """Empty service name should raise ValueError."""
        discovery = ServiceDiscovery(tmp_path)

        with pytest.raises(ValueError, match="cannot be empty"):
            discovery.find_service("", "test")

    def test_validates_service_name_with_path_traversal(self, tmp_path: Path):
        """Service name with path traversal should be rejected."""
        discovery = ServiceDiscovery(tmp_path)

        with pytest.raises(ValueError, match="Invalid service name"):
            discovery.find_service("../../../etc/passwd", "test")

    def test_validates_service_name_with_spaces(self, tmp_path: Path):
        """Service name with spaces should be rejected."""
        discovery = ServiceDiscovery(tmp_path)

        with pytest.raises(ValueError, match="Invalid service name"):
            discovery.find_service("my service", "test")

    def test_validates_service_name_with_special_chars(self, tmp_path: Path):
        """Service name with special characters should be rejected."""
        discovery = ServiceDiscovery(tmp_path)

        for invalid_name in ["service;rm -rf /", "service|cat", "service`whoami`"]:
            with pytest.raises(ValueError, match="Invalid service name"):
                discovery.find_service(invalid_name, "test")

    def test_accepts_valid_service_names(self, tmp_path: Path):
        """Valid service names should be accepted (even if service not found)."""
        discovery = ServiceDiscovery(tmp_path)

        valid_names = [
            "partition",
            "partition-core",
            "os-core-common",
            "crs-catalog-service",
            "indexer_queue",
            "service.name",
            "Service123",
        ]

        for name in valid_names:
            # Should raise FileNotFoundError (not ValueError) because service doesn't exist
            with pytest.raises(FileNotFoundError):
                discovery.find_service(name, "test")

    def test_finds_service_in_src_core(self, tmp_path: Path):
        """Service in src/core should be discovered."""
        service_dir = tmp_path / "src" / "core" / "partition"
        service_dir.mkdir(parents=True)
        (service_dir / "pom.xml").write_text("<project/>")
        (service_dir / "provider").mkdir()

        discovery = ServiceDiscovery(tmp_path)
        config = discovery.find_service("partition", "compile")

        assert config.service_dir == service_dir
        assert config.name == "partition"

    def test_finds_service_in_src_reference(self, tmp_path: Path):
        """Service in src/reference should be discovered."""
        service_dir = tmp_path / "src" / "reference" / "unit-service"
        service_dir.mkdir(parents=True)
        (service_dir / "pom.xml").write_text("<project/>")

        discovery = ServiceDiscovery(tmp_path)
        config = discovery.find_service("unit-service", "compile")

        assert config.service_dir == service_dir

    def test_finds_standalone_service(self, tmp_path: Path):
        """Standalone service at root should be discovered."""
        service_dir = tmp_path / "legal"
        service_dir.mkdir(parents=True)
        (service_dir / "pom.xml").write_text("<project/>")

        discovery = ServiceDiscovery(tmp_path)
        config = discovery.find_service("legal", "compile")

        assert config.service_dir == service_dir

    def test_detects_shared_module(self, tmp_path: Path):
        """Shared module should be detected in config."""
        service_dir = tmp_path / "src" / "core" / "partition-core-plus"
        service_dir.mkdir(parents=True)
        (service_dir / "pom.xml").write_text("<project/>")

        discovery = ServiceDiscovery(tmp_path)
        config = discovery.find_service("partition-core-plus", "validate")

        assert config.is_shared_module is True


# =============================================================================
# ENVIRONMENT LOADER TESTS
# =============================================================================


class TestEnvironmentLoader:
    """Tests for EnvironmentLoader class."""

    def test_loads_env_file(self, tmp_path: Path):
        """Should load environment variables from .env file."""
        env_content = """
# Comment line
DATABASE_URL=postgresql://localhost/db
API_KEY=secret123
EMPTY_VAR=
"""
        env_file = tmp_path / ".env"
        env_file.write_text(env_content)

        loader = EnvironmentLoader()
        result = loader.load_environment(env_file)

        assert result["DATABASE_URL"] == "postgresql://localhost/db"
        assert result["API_KEY"] == "secret123"
        assert result["EMPTY_VAR"] == ""

    def test_strips_quotes_from_values(self, tmp_path: Path):
        """Should strip quotes from values."""
        env_content = """
DOUBLE_QUOTED="value with spaces"
SINGLE_QUOTED='another value'
"""
        env_file = tmp_path / ".env"
        env_file.write_text(env_content)

        loader = EnvironmentLoader()
        result = loader.load_environment(env_file)

        assert result["DOUBLE_QUOTED"] == "value with spaces"
        assert result["SINGLE_QUOTED"] == "another value"

    def test_applies_overrides(self, tmp_path: Path):
        """Overrides should take precedence over file values."""
        env_content = "KEY1=original\nKEY2=also_original"
        env_file = tmp_path / ".env"
        env_file.write_text(env_content)

        loader = EnvironmentLoader()
        result = loader.load_environment(env_file, {"KEY1": "overridden", "KEY3": "new"})

        assert result["KEY1"] == "overridden"
        assert result["KEY2"] == "also_original"
        assert result["KEY3"] == "new"

    def test_skips_dummy_env_file(self, tmp_path: Path):
        """Dummy env file should be skipped."""
        dummy_file = tmp_path / ".env.dummy"

        loader = EnvironmentLoader()
        result = loader.load_environment(dummy_file)

        assert result == {}

    def test_applies_osdu_istio_mapping(self, tmp_path: Path):
        """Should apply OSDU Istio auth mapping."""
        env_content = "AZURE_ISTIOAUTH_ENABLED=true"
        env_file = tmp_path / ".env"
        env_file.write_text(env_content)

        loader = EnvironmentLoader()
        result = loader.load_environment(env_file)

        assert result["azure_istioauth_enabled"] == "true"

    def test_defaults_istio_to_false(self, tmp_path: Path):
        """Istio auth should default to false if not set."""
        env_content = "OTHER_VAR=value"
        env_file = tmp_path / ".env"
        env_file.write_text(env_content)

        loader = EnvironmentLoader()
        result = loader.load_environment(env_file)

        assert result["azure_istioauth_enabled"] == "false"


# =============================================================================
# COMMAND BUILDER TESTS
# =============================================================================


class TestCommandBuilder:
    """Tests for CommandBuilder class."""

    def test_compile_command(self, tmp_path: Path):
        """Compile action should generate mvn compile."""
        builder = CommandBuilder(tmp_path)
        config = ServiceConfig(
            name="partition",
            service_dir=tmp_path / "partition",
            env_file=tmp_path / ".env",
        )

        result = builder.build_command("compile", config)
        assert result == "mvn compile"

    def test_package_command(self, tmp_path: Path):
        """Package action should generate mvn package."""
        builder = CommandBuilder(tmp_path)
        config = ServiceConfig(
            name="partition",
            service_dir=tmp_path / "partition",
            env_file=tmp_path / ".env",
        )

        result = builder.build_command("package", config)
        assert result == "mvn package"

    def test_validate_command_for_shared_module(self, tmp_path: Path):
        """Validate on shared module should include all profiles."""
        builder = CommandBuilder(tmp_path)
        config = ServiceConfig(
            name="partition-core",
            service_dir=tmp_path / "partition-core",
            env_file=tmp_path / ".env",
            is_shared_module=True,
            available_profiles=["core", "azure", "gc"],
        )

        result = builder.build_command("validate", config)
        assert "-P" in result
        assert "core" in result
        assert "azure" in result
        assert "gc" in result

    def test_validate_command_for_non_shared_module(self, tmp_path: Path):
        """Validate on non-shared module should use default profile."""
        builder = CommandBuilder(tmp_path)
        config = ServiceConfig(
            name="partition",
            service_dir=tmp_path / "partition",
            env_file=tmp_path / ".env",
            is_shared_module=False,
        )

        result = builder.build_command("validate", config)
        assert result == "mvn verify"
        assert "-P" not in result

    def test_run_command_basic(self, tmp_path: Path):
        """Run action should generate spring-boot:run."""
        builder = CommandBuilder(tmp_path)
        config = ServiceConfig(
            name="partition",
            service_dir=tmp_path / "partition",
            env_file=tmp_path / ".env",
        )

        result = builder.build_command("run", config)
        assert "mvn spring-boot:run" in result


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
