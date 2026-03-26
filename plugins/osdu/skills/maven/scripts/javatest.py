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
# dependencies = [
#     "defusedxml",
# ]
# ///
"""
OSDU Java Project Test Runner - Automated Project Discovery & Testing

This enhanced script provides automated OSDU project discovery and testing with:
- Convention-based service discovery (automatically finds services in src/core and src/reference)
- Intelligent environment file prioritization (test environments for testing, main for startup)
- Automatic shared-module detection with multi-profile builds
- Service startup validation with port monitoring
- Support for service-specific configurations and overrides
- Cross-platform support (Windows, Linux, macOS)

Usage:
  uv run javatest.py --project <name> --test [KEY=VALUE ...]
  uv run javatest.py --project <name> --validate [KEY=VALUE ...]
  uv run javatest.py --project <name> --run [KEY=VALUE ...]
  uv run javatest.py --project <name> --startup-test [KEY=VALUE ...]

Examples:
  uv run javatest.py --project partition --test
  uv run javatest.py --project partition --validate  # Auto-detects profiles for shared modules
  uv run javatest.py --project legal --run SERVER_PORT=8100
  uv run javatest.py --project partition --startup-test SERVER_PORT=8080
  uv run javatest.py --project entitlements --test TENANT_ID=opendes

Supported Projects (auto-discovered):
  Core Services: partition, entitlements, legal, schema-service, storage, search-service, file,
                 indexer-service, indexer-queue, ingestion-workflow
  Reference Services: crs-catalog-service, crs-conversion-service, unit-service
  Libraries: os-core-common, os-core-lib-azure

Key Features:
  - Automatic project directory discovery using conventions
  - Smart environment file selection based on action type
  - Automatic shared-module detection with all-profile builds (--validate)
  - Startup validation with port monitoring for --startup-test (services only)
  - Project-specific overrides for non-standard directory structures
  - Secure environment variable handling with Azure Istio mappings
  - Cross-platform support (Windows, Linux, macOS)
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shlex
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from defusedxml import ElementTree

# =============================================================================
# SHARED MODULE DETECTION
# =============================================================================

# Patterns that indicate a shared/core module requiring multi-profile validation
SHARED_MODULE_PATTERNS = [
    "core",
    "common",
    "shared",
    "api",
    "model",
    "lib",
]

# Standard OSDU profiles
OSDU_PROFILES = ["core", "azure", "gc", "aws", "ibm"]


def is_shared_module(module_name: str) -> bool:
    """Detect if a module is shared (requires multi-profile build)."""
    module_lower = module_name.lower()
    return any(pattern in module_lower for pattern in SHARED_MODULE_PATTERNS)


def discover_profiles_from_pom(pom_path: Path) -> set[str]:
    """Extract profile IDs from a pom.xml file."""
    profiles = set()

    if not pom_path.exists():
        return profiles

    try:
        tree = ElementTree.parse(pom_path)
        root = tree.getroot()

        # Handle Maven namespace
        ns = {"m": "http://maven.apache.org/POM/4.0.0"}

        # Try with namespace first
        for profile in root.findall(".//m:profiles/m:profile/m:id", ns):
            if profile.text:
                profiles.add(profile.text.strip())

        # Try without namespace (some POMs don't use it)
        if not profiles:
            for profile in root.findall(".//profiles/profile/id"):
                if profile.text:
                    profiles.add(profile.text.strip())

    except ElementTree.ParseError:
        # Fallback to regex parsing if XML parsing fails
        try:
            content = pom_path.read_text(encoding="utf-8")
            # Match <id>profile-name</id> within <profile> blocks
            profile_blocks = re.findall(r"<profile>.*?</profile>", content, re.DOTALL)
            for block in profile_blocks:
                id_match = re.search(r"<id>([^<]+)</id>", block)
                if id_match:
                    profiles.add(id_match.group(1).strip())
        except Exception:
            pass

    return profiles


def get_all_profiles(project_dir: Path) -> list[str]:
    """Discover all available profiles in a Maven project."""
    profiles = set()

    # Check current directory pom.xml
    profiles.update(discover_profiles_from_pom(project_dir / "pom.xml"))

    # Check parent directory pom.xml
    profiles.update(discover_profiles_from_pom(project_dir.parent / "pom.xml"))

    # Check common locations
    for subdir in [".", "..", "provider", "testing"]:
        pom_path = project_dir / subdir / "pom.xml"
        if pom_path.exists():
            profiles.update(discover_profiles_from_pom(pom_path))

    # Filter to known OSDU profiles if we found too many
    osdu_profiles = profiles.intersection(set(OSDU_PROFILES))
    if osdu_profiles:
        return sorted(osdu_profiles)

    # Return discovered profiles or default OSDU profiles
    return sorted(profiles) if profiles else OSDU_PROFILES


# =============================================================================
# SERVICE CONFIGURATION
# =============================================================================

# Default patterns that work for most OSDU services
DEFAULT_SERVICE_CONFIG = {
    "base_patterns": lambda name: [name],
    "test_module": lambda name: f"{name}-test-azure",
    "provider_patterns": lambda name: [f"{name}-azure", f"{name}-aws", f"{name}-gc", f"{name}-ibm"],
    "core_patterns": lambda name: [f"{name}-core-plus", f"{name}-core"],
}

# Service-specific overrides for services that don't follow standard patterns
SERVICE_OVERRIDES = {
    "entitlements": {
        "base_patterns": ["entitlements-v2", "entitlements"],
        "test_module": "entitlements-v2-test-azure",
        "provider_patterns": [
            "entitlements-v2-azure",
            "entitlements-v2-aws",
            "entitlements-v2-jdbc",
            "entitlements-v2-ibm",
        ],
        "core_patterns": ["entitlements-v2-core-plus", "entitlements-v2-core"],
    },
    "search-service": {
        "base_patterns": ["search", "search-service"],
        "test_module": "search-test-azure",
        "provider_patterns": ["search-azure", "search-aws", "search-gc", "search-ibm"],
        "core_patterns": ["search-core-plus", "search-core"],
    },
    "indexer-queue": {
        "base_patterns": ["indexer-queue"],
        "test_module": "indexer-queue-azure-enqueue",
        "provider_patterns": [
            "indexer-queue-azure-enqueue",
            "indexer-queue-aws",
            "indexer-queue-azure-requeue",
            "indexer-queue-ibm",
        ],
        "core_patterns": ["indexer-queue-azure-enqueue", "indexer-queue-aws"],
    },
    "indexer-service": {
        "base_patterns": ["indexer-service"],
        "test_module": "indexer-test-azure",
        "provider_patterns": ["indexer-azure", "indexer-aws", "indexer-gc", "indexer-ibm"],
        "core_patterns": ["indexer-core-plus", "indexer-core"],
    },
    "ingestion-workflow": {
        "base_patterns": ["workflow", "ingestion-workflow"],
        "test_module": "workflow-test-azure",
        "provider_patterns": ["workflow-azure", "workflow-aws", "workflow-gc", "workflow-ibm"],
        "core_patterns": ["workflow-core-plus", "workflow-core"],
    },
    "schema-service": {
        "base_patterns": ["schema", "schema-service"],
        "test_module": "schema-test-core",
        "provider_patterns": ["schema-azure", "schema-aws", "schema-gc", "schema-ibm"],
        "core_patterns": ["schema-core-plus", "schema-core"],
    },
    "crs-catalog-service": {
        "base_patterns": ["crs-catalog", "crs-catalog-service"],
        "test_module": "catalog_test_azure",
        "provider_patterns": [
            "crs-catalog-azure/crs-catalog-aks",
            "crs-catalog-aws",
            "crs-catalog-gc/crs-catalog-gke",
            "crs-catalog-ibm/crs-catalog-ocp",
        ],
        "core_patterns": ["crs-catalog-core-plus", "crs-catalog-core"],
    },
    "crs-conversion-service": {
        "base_patterns": ["crs-converter", "crs-conversion-service"],
        "test_module": "crs_converter_test_azure",
        "provider_patterns": [
            "crs-converter-azure/crs-converter-aks",
            "crs-converter-aws",
            "crs-converter-gc/crs-converter-gke",
            "crs-converter-ibm/crs-converter-ocp",
        ],
        "core_patterns": ["crs-converter-core-plus", "crs-converter-core"],
    },
    "unit-service": {
        "base_patterns": ["unit", "unit-service"],
        "test_module": "unit_test_azure",
        "provider_patterns": [
            "unit-azure/unit-aks",
            "unit-aws",
            "unit-gc/unit-gke",
            "unit-ibm/unit-ocp",
        ],
        "core_patterns": ["unit-core-plus", "unit-core"],
    },
}


def get_service_config(service_name: str) -> dict:
    """Get configuration for a service, applying overrides if they exist."""
    if service_name in SERVICE_OVERRIDES:
        return SERVICE_OVERRIDES[service_name]

    # Apply default patterns
    return {
        "base_patterns": DEFAULT_SERVICE_CONFIG["base_patterns"](service_name),
        "test_module": DEFAULT_SERVICE_CONFIG["test_module"](service_name),
        "provider_patterns": DEFAULT_SERVICE_CONFIG["provider_patterns"](service_name),
        "core_patterns": DEFAULT_SERVICE_CONFIG["core_patterns"](service_name),
    }


@dataclass
class ServiceConfig:
    """Configuration for an OSDU service."""

    name: str
    service_dir: Path
    env_file: Path
    main_class_dir: Path | None = None
    test_dir: Path | None = None
    is_shared_module: bool = False
    available_profiles: list[str] | None = None


class ServiceDiscovery:
    """Discovers OSDU service directories using conventions."""

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def find_service(self, service_name: str, action: str) -> ServiceConfig:
        """Find service configuration using convention-based discovery."""

        # Validate service name to prevent path traversal and invalid characters
        if not service_name:
            raise ValueError("Service name cannot be empty")
        if not re.match(r"^[\w][\w.-]*$", service_name):
            raise ValueError(
                f"Invalid service name: '{service_name}'. "
                "Must start with alphanumeric and contain only alphanumeric, hyphen, underscore, or dot."
            )

        # Base service directory discovery - try all possible locations
        service_dir = None

        # Priority 1: Monorepo structure (src/core, src/reference, src/lib)
        # Must have pom.xml to be valid (not just config directories)
        for subdir in ["src/core", "src/reference", "src/lib"]:
            candidate = self.project_root / subdir / service_name
            if candidate.exists() and (candidate / "pom.xml").exists():
                service_dir = candidate
                break

        # Priority 2: Standalone repo at root level (osdu-agent clones repos here)
        if service_dir is None:
            candidate = self.project_root / service_name
            if candidate.exists() and (candidate / "pom.xml").exists():
                service_dir = candidate

        # Priority 3: Current directory IS the service (running from within service repo)
        if (
            service_dir is None
            and (self.project_root / "pom.xml").exists()
            and (
                (self.project_root / "provider").exists()
                or (self.project_root / "testing").exists()
                or (self.project_root / "src" / "main" / "java").exists()
            )
        ):
            service_dir = self.project_root

        if service_dir is None:
            raise FileNotFoundError(
                f"Service '{service_name}' not found. Searched:\n"
                f"  - {self.project_root}/src/core/{service_name}\n"
                f"  - {self.project_root}/src/reference/{service_name}\n"
                f"  - {self.project_root}/src/lib/{service_name}\n"
                f"  - {self.project_root}/{service_name} (standalone repo)\n"
                f"  - {self.project_root} (current directory)"
            )

        # Environment file discovery with clear priority
        env_file = self._find_env_file(service_dir, action)

        # Detect service type for test logic
        is_reference_service = "src/reference" in str(service_dir)

        # Detect if this is a shared module
        shared_module = is_shared_module(service_name)

        # Discover available profiles
        available_profiles = get_all_profiles(service_dir) if action == "validate" else None

        # Main application directory discovery for startup
        main_class_dir = None
        if action in ["run", "startup-test"]:
            main_class_dir = self._find_main_class_directory(service_dir)

        # Test directory discovery for test actions
        # Skip Java test discovery for reference services (they use Python tests)
        test_dir = None
        if action in ["test", "validate"] and not is_reference_service:
            test_dir = self._find_test_directory(service_dir)

        return ServiceConfig(
            name=service_name,
            service_dir=service_dir,
            env_file=env_file,
            main_class_dir=main_class_dir,
            test_dir=test_dir,
            is_shared_module=shared_module,
            available_profiles=available_profiles,
        )

    def _find_env_file(self, service_dir: Path, action: str) -> Path:
        """Find environment file with clear priority rules."""

        # Compile, package, validate, and library test actions don't need environment files
        # Detect library: in src/lib path OR no provider/testing directories with src/main/java
        is_library = "src/lib" in str(service_dir) or (
            not (service_dir / "provider").exists()
            and not (service_dir / "testing").exists()
            and (service_dir / "src" / "main" / "java").exists()
        )
        if action in ["compile", "package", "validate"] or (is_library and action == "test"):
            # Return a dummy path - environment loading will be skipped
            return self.project_root / ".env.dummy"

        service_name = service_dir.name

        if action == "test":
            # Test actions prioritize testing environments
            candidates = [
                service_dir / "testing" / ".vscode" / ".env",
                service_dir / ".vscode" / ".env",
                # Fallback: check src/core path for legacy monorepo setups
                self.project_root / "src" / "core" / service_name / "testing" / ".vscode" / ".env",
                self.project_root / "src" / "core" / service_name / ".vscode" / ".env",
                self.project_root / ".vscode" / f".env.{service_name}",
            ]
        else:
            # Startup actions prioritize main service environments
            candidates = [
                service_dir / ".vscode" / ".env",
                service_dir / "testing" / ".vscode" / ".env",
                # Fallback: check src/core path for legacy monorepo setups
                self.project_root / "src" / "core" / service_name / ".vscode" / ".env",
                self.project_root / "src" / "core" / service_name / "testing" / ".vscode" / ".env",
                self.project_root / ".vscode" / f".env.{service_name}",
            ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        raise FileNotFoundError(
            f"No .env file found for service '{service_name}'. Searched:\n"
            + "\n".join(f"  - {c}" for c in candidates)
        )

    def _find_main_class_directory(self, service_dir: Path) -> Path:
        """Find directory containing main application class using conventions."""

        service_name = service_dir.name
        config = get_service_config(service_name)

        candidates = []

        # Provider directories (most common for runnable services)
        for provider in config["provider_patterns"]:
            candidates.append(service_dir / "provider" / provider)

        # Core modules
        for core in config["core_patterns"]:
            candidates.append(service_dir / core)

        # Always try root service directory last
        candidates.append(service_dir)

        for candidate in candidates:
            if candidate.exists() and self._has_main_class(candidate):
                return candidate

        # Fallback to first existing candidate
        for candidate in candidates:
            if candidate.exists():
                return candidate

        return service_dir

    def _find_test_directory(self, service_dir: Path) -> Path:
        """Find test directory using conventions."""

        # For test actions, we need the parent directory that contains the pom.xml
        # managing all test modules, not the individual test module
        testing_parent = service_dir / "testing"
        if testing_parent.exists() and (testing_parent / "pom.xml").exists():
            return testing_parent

        # Fallback to individual test modules
        candidates = [
            # Azure test modules (most common)
            service_dir / "testing" / "integration-tests" / f"{service_dir.name}-test-azure",
            service_dir / "testing" / f"{service_dir.name}-test-azure",
            # Generic test directories
            service_dir / "testing" / "integration-tests",
            service_dir / "testing",
            service_dir,
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return service_dir / "testing"

    def _has_main_class(self, directory: Path) -> bool:
        """Check if directory contains a main application class."""
        java_dir = directory / "src" / "main" / "java"
        if not java_dir.exists():
            return False

        # Look for Application classes
        return any(True for _ in java_dir.rglob("*Application.java"))


class EnvironmentLoader:
    """Loads and processes environment variables."""

    def load_environment(self, env_file: Path, overrides: dict = None) -> dict:
        """Load environment variables from file with overrides."""

        env_vars = {}

        # Skip environment loading for dummy env files (compile/package/validate actions)
        if env_file.name == ".env.dummy":
            print(
                "Skipping environment loading for compile/package/validate action", file=sys.stderr
            )
            return env_vars

        # Load from file
        if env_file.exists():
            print(f"Loading environment from: {env_file}", file=sys.stderr)
            with open(env_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    if "=" not in line:
                        continue

                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip("\"'")
                    env_vars[key] = value

        # Apply overrides
        if overrides:
            env_vars.update(overrides)

        # Apply OSDU-specific environment variable mappings
        enhanced_env = dict(env_vars)
        self._apply_osdu_mappings(env_vars, enhanced_env)

        return enhanced_env

    def _apply_osdu_mappings(self, original_env: dict, enhanced_env: dict):
        """Apply OSDU-specific environment variable mappings."""

        # Azure Istio auth configuration mapping
        istio_auth_vars = [
            "AZURE_ISTIOAUTH_ENABLED",
            "azure_istioauth_enabled",
            "AZURE_ISTIO_AUTH_ENABLED",
        ]
        for var in istio_auth_vars:
            if var in original_env:
                enhanced_env["azure_istioauth_enabled"] = original_env[var]
                break
        else:
            # Default to false if not found
            enhanced_env["azure_istioauth_enabled"] = "false"


class CommandBuilder:
    """Builds Maven commands for different actions."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.app_insights_agent = project_root / "src" / "applicationinsights-agent-3.7.1.jar"

    def build_command(
        self, action: str, service_config: ServiceConfig, env_vars: dict = None
    ) -> str:
        """Build Maven command based on action and service configuration."""

        if action == "test":
            return self._build_test_command(service_config, env_vars)
        elif action == "validate":
            return self._build_validate_command(service_config)
        elif action in ["run", "startup-test"]:
            return self._build_run_command(service_config)
        elif action == "compile":
            return "mvn compile"
        elif action == "package":
            return "mvn package"
        else:
            raise ValueError(f"Unsupported action: {action}")

    def _build_validate_command(self, service_config: ServiceConfig) -> str:
        """Build validate command with all profiles for shared modules."""

        profiles = service_config.available_profiles or OSDU_PROFILES

        if service_config.is_shared_module:
            # Shared module: build with ALL profiles
            profile_str = ",".join(profiles)
            print(
                f"Shared module detected: building with profiles [{profile_str}]", file=sys.stderr
            )
            return f"mvn verify -P{profile_str}"
        else:
            # Non-shared module: use default profile
            print("Non-shared module: using default profile", file=sys.stderr)
            return "mvn verify"

    def _build_test_command(
        self,
        service_config: ServiceConfig,
        env_vars: dict = None,
        test_type: str = "integration",
    ) -> str:
        """Build test command.

        Args:
            service_config: Service configuration
            env_vars: Environment variables
            test_type: 'unit' for unit tests only, 'integration' for integration tests only
        """

        # Base command logic
        # Detect library projects: in src/lib path OR no provider/testing directories
        is_library = "src/lib" in str(service_config.service_dir) or (
            not (service_config.service_dir / "provider").exists()
            and not (service_config.service_dir / "testing").exists()
            and (service_config.service_dir / "src" / "main" / "java").exists()
        )
        if is_library:
            base_command = "mvn test"  # Libraries just need simple mvn test
        elif test_type == "unit":
            # Unit tests: run from service root, exclude testing directory
            base_command = "mvn test -pl '!testing'"
        elif service_config.name == "schema-service":
            # Schema service uses Maven Failsafe plugin for Cucumber integration tests
            config = get_service_config(service_config.name)
            test_module = config["test_module"]
            base_command = f"mvn verify -pl {test_module}"
        else:
            # Integration tests: Use inclusion-based targeting for Azure test module
            # This is explicit and future-proof - only runs the configured test module
            config = get_service_config(service_config.name)
            test_module = config["test_module"]
            base_command = f"mvn test -pl {test_module}"

        # Add test skip logic (only for integration tests)
        if test_type != "unit":
            skip_options = self._build_skip_test_options(env_vars or {})
            if skip_options:
                return f"{base_command} {skip_options}"

        return base_command

    def _build_skip_test_options(self, env_vars: dict) -> str:
        """Build Maven test skip options from environment variables."""
        skip_tests = env_vars.get("SKIP_TESTS", "").strip()
        skip_classes = env_vars.get("SKIP_TEST_CLASSES", "").strip()

        exclusions = []

        if skip_tests:
            # Parse individual test methods: "TestFile#testMethod:reason,TestOther#otherMethod"
            for skip_entry in skip_tests.split(","):
                test_spec = skip_entry.split(":")[0].strip()  # Remove reason if present
                if test_spec:
                    exclusions.append(f"!{test_spec}")

        if skip_classes:
            # Parse entire test classes: "TestClass:reason,OtherTestClass"
            for skip_entry in skip_classes.split(","):
                class_spec = skip_entry.split(":")[0].strip()  # Remove reason if present
                if class_spec:
                    exclusions.append(f"!{class_spec}")

        if exclusions:
            # Maven Surefire syntax: -Dtest=!TestClass#testMethod,!OtherClass
            excluded_tests = ",".join(exclusions)

            # Log which tests are being skipped
            print(f"Skipping tests: {excluded_tests}", file=sys.stderr)
            if skip_tests:
                print(f"  Individual test methods: {skip_tests}", file=sys.stderr)
            if skip_classes:
                print(f"  Entire test classes: {skip_classes}", file=sys.stderr)

            return f'-Dtest="{excluded_tests}"'

        return ""

    def _build_run_command(self, service_config: ServiceConfig) -> str:
        """Build run command."""
        jvm_args = []

        if self.app_insights_agent.exists():
            jvm_args.append(f"-javaagent:{self.app_insights_agent}")

        # Add client-id for crs-catalog-service as specified in README
        if service_config.name == "crs-catalog-service":
            client_id = os.getenv("CLIENT_ID") or os.getenv("AAD_CLIENT_ID")
            if client_id:
                jvm_args.append(f"-Dclient-id={client_id}")

        if jvm_args:
            jvm_args_str = " ".join(jvm_args)
            return f'mvn spring-boot:run -Dspring-boot.run.jvmArguments="{jvm_args_str}"'
        else:
            return "mvn spring-boot:run"

    def _is_azure_service(self, service_config: ServiceConfig) -> bool:
        """Detect if this is an Azure service configuration."""
        config = get_service_config(service_config.name)

        # Look for Azure provider in the configured patterns
        azure_providers = [p for p in config["provider_patterns"] if "azure" in p.lower()]
        if not azure_providers:
            return False

        # Check if Azure provider directory exists
        azure_provider_path = service_config.service_dir / "provider" / azure_providers[0]
        return azure_provider_path.exists()


class ServiceRunner:
    """Executes and monitors OSDU services."""

    def run_test(self, command: str, work_dir: Path, env_vars: dict) -> int:
        """Execute integration tests."""
        return self._execute_command(command, work_dir, env_vars)

    def run_validate(self, command: str, work_dir: Path) -> int:
        """Execute validation build (no environment needed)."""
        return self._execute_command_simple(command, work_dir)

    def run_service(self, command: str, work_dir: Path, env_vars: dict) -> int:
        """Start service and run indefinitely."""
        return self._execute_command(command, work_dir, env_vars)

    def run_compile_or_package(self, command: str, work_dir: Path) -> int:
        """Execute compile or package commands without environment variables."""
        return self._execute_command_simple(command, work_dir)

    def run_startup_test(self, command: str, work_dir: Path, env_vars: dict, port: int) -> int:
        """Start service, validate startup, then stop."""

        exec_env = {**os.environ, **env_vars}
        print(f"Starting service in {work_dir}: {command}", file=sys.stderr)
        print(f"Monitoring port {port} for startup validation", file=sys.stderr)

        process = None
        try:
            # Start service
            use_shell = self._should_use_shell(command)
            cmd_args = self._prepare_command(command, use_shell)

            # Cross-platform process creation with proper process group handling
            creation_flags = 0
            if platform.system() == "Windows":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

            process = subprocess.Popen(
                cmd_args,
                cwd=work_dir,
                env=exec_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True,
                shell=use_shell,
                creationflags=creation_flags,
            )

            # Monitor startup with live log streaming
            startup_success = self._wait_for_startup(process, port, timeout=120)

            if startup_success:
                print("Service startup validation successful", file=sys.stderr)
                return 0
            else:
                print("Service startup validation failed", file=sys.stderr)
                return 1

        except Exception as e:
            print(f"Error during startup test: {e}", file=sys.stderr)
            return 1
        finally:
            if process:
                self._terminate_process_tree(process, port)

    def _execute_command(self, command: str, work_dir: Path, env_vars: dict) -> int:
        """Execute a command with environment."""
        exec_env = {**os.environ, **env_vars}

        try:
            # Cross-platform command execution
            use_shell = self._should_use_shell(command)
            cmd_args = self._prepare_command(command, use_shell)

            result = subprocess.run(cmd_args, cwd=work_dir, env=exec_env, shell=use_shell)
            return result.returncode
        except Exception as e:
            print(f"Error executing command: {e}", file=sys.stderr)
            return 1

    def _execute_command_simple(self, command: str, work_dir: Path) -> int:
        """Execute a command without environment variables (for compile/package/validate)."""
        try:
            # Cross-platform command execution
            use_shell = self._should_use_shell(command)
            cmd_args = self._prepare_command(command, use_shell)

            result = subprocess.run(cmd_args, cwd=work_dir, shell=use_shell)
            return result.returncode
        except Exception as e:
            print(f"Error executing command: {e}", file=sys.stderr)
            return 1

    def _wait_for_startup(self, process: subprocess.Popen, port: int, timeout: int = 120) -> bool:
        """Wait for service to start up successfully while streaming logs."""
        import queue
        import threading

        # Queue to collect log lines
        log_queue = queue.Queue()

        def log_reader():
            """Read logs from process stdout in a separate thread."""
            if process.stdout:
                try:
                    for line in iter(process.stdout.readline, ""):
                        log_queue.put(line)
                except Exception:
                    pass

        # Start log reader thread
        log_thread = threading.Thread(target=log_reader, daemon=True)
        log_thread.start()

        start_time = time.time()

        while time.time() - start_time < timeout:
            # Display any available log lines
            while not log_queue.empty():
                try:
                    line = log_queue.get_nowait()
                    print(line, end="")
                except queue.Empty:
                    break

            # Check if process is still running
            if process.poll() is not None:
                # Process exited, flush remaining logs
                while not log_queue.empty():
                    try:
                        line = log_queue.get_nowait()
                        print(line, end="")
                    except queue.Empty:
                        break
                print(f"Service process exited early with code {process.poll()}", file=sys.stderr)
                return False

            # Check if port is listening
            if self._is_port_listening(port):
                print(f"Port {port} is now listening", file=sys.stderr)
                return True

            time.sleep(0.5)

        print(f"Timeout waiting for port {port} to become available", file=sys.stderr)
        return False

    def _should_use_shell(self, command: str) -> bool:
        """Determine if shell should be used for command execution."""
        # Always use shell on Windows for proper command resolution
        if platform.system() == "Windows":
            return True

        # On Unix-like systems, use shell only for complex commands
        return ";" in command or "&&" in command or "|" in command or "||" in command

    def _prepare_command(self, command: str, use_shell: bool):
        """Prepare command arguments based on shell usage."""
        if use_shell:
            # When using shell, pass command as string
            return command
        else:
            # When not using shell, split command properly (Unix only)
            return shlex.split(command)

    def _is_port_listening(self, port: int) -> bool:
        """Check if a port is listening."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex(("localhost", port))
                return result == 0
        except Exception:
            return False

    def _terminate_process_tree(self, process: subprocess.Popen, port: int):
        """Terminate the entire process tree robustly across platforms."""
        print("Terminating service and all child processes...", file=sys.stderr)

        try:
            if platform.system() == "Windows":
                self._terminate_windows_process_tree(process, port)
            else:
                self._terminate_unix_process_tree(process, port)
        except Exception as e:
            print(f"Warning: Error during process termination: {e}", file=sys.stderr)

        # Dynamic waiting - check port status with early exit
        for i in range(10):  # Check every 0.5s for up to 5s max
            if not self._is_port_listening(port):
                elapsed = i * 0.5
                if elapsed == 0:
                    print(
                        f"Service stopped successfully, port {port} freed immediately",
                        file=sys.stderr,
                    )
                else:
                    print(
                        f"Service stopped successfully, port {port} freed in {elapsed}s",
                        file=sys.stderr,
                    )
                return
            time.sleep(0.5)

        # If we get here, port is still occupied after 5 seconds
        print(
            f"Warning: Port {port} is still occupied after 5s termination timeout", file=sys.stderr
        )

    def _terminate_windows_process_tree(self, process: subprocess.Popen, port: int):
        """Terminate process tree on Windows using process groups and taskkill."""
        try:
            # First try: Send CTRL_BREAK_EVENT to the process group
            if process.poll() is None:
                try:
                    os.kill(process.pid, signal.CTRL_BREAK_EVENT)
                    process.wait(timeout=3)
                    print("Process terminated gracefully via CTRL_BREAK_EVENT", file=sys.stderr)
                    return
                except (subprocess.TimeoutExpired, ProcessLookupError, OSError):
                    pass

            # Second try: Use taskkill to terminate the entire process tree
            if process.poll() is None:
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                        check=False,
                        capture_output=True,
                        timeout=10,
                    )
                    process.wait(timeout=3)
                    print("Process tree terminated via taskkill", file=sys.stderr)
                    return
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass

            # Third try: Terminate process directly
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                    print("Process terminated via terminate()", file=sys.stderr)
                    return
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)

        except Exception as e:
            print(f"Windows termination error: {e}", file=sys.stderr)

    def _terminate_unix_process_tree(self, process: subprocess.Popen, port: int):
        """Terminate process tree on Unix-like systems."""
        try:
            # Send SIGTERM to the process group
            if process.poll() is None:
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    process.wait(timeout=3)
                    print("Process terminated gracefully via SIGTERM", file=sys.stderr)
                    return
                except (subprocess.TimeoutExpired, ProcessLookupError, OSError):
                    pass

            # If that fails, terminate the process directly
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                    print("Process terminated via terminate()", file=sys.stderr)
                    return
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
                    print("Process forcefully killed via kill()", file=sys.stderr)

        except Exception as e:
            print(f"Unix termination error: {e}", file=sys.stderr)


def find_project_root() -> Path:
    """Find OSDU project root by looking for common markers."""
    current = Path.cwd()

    # Markers that indicate we're in an OSDU service repo or workspace
    service_markers = ["src/core", "src/reference", "src/lib", "pom.xml"]
    workspace_markers = [".git", "AGENTS.md"]

    for parent in [current] + list(current.parents):
        # Check for service structure
        service_match = sum(1 for marker in service_markers if (parent / marker).exists())
        workspace_match = sum(1 for marker in workspace_markers if (parent / marker).exists())

        if service_match >= 1 or workspace_match >= 2:
            return parent

    return current


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="OSDU Java Project Test Runner - Clean Architecture",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run unit tests with specific profiles
  %(prog)s --project partition --test --profiles core,azure --unit

  # Run integration tests only
  %(prog)s --project partition --test --integration

  # Validate shared module with auto-detected profiles
  %(prog)s --project partition-core-plus --validate

  # Start service locally
  %(prog)s --project partition --run
""",
    )

    parser.add_argument("--project", required=True, help="OSDU project name (service or library)")

    # Action group - exactly one required
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument(
        "--test", action="store_true", help="Run tests (use --unit/--integration to specify type)"
    )
    action_group.add_argument(
        "--validate",
        action="store_true",
        help="Validate build with all profiles (auto-detects shared modules)",
    )
    action_group.add_argument(
        "--run", action="store_true", help="Start the service (services only)"
    )
    action_group.add_argument(
        "--startup-test", action="store_true", help="Test service startup (services only)"
    )
    action_group.add_argument(
        "--compile", action="store_true", help="Compile the project (mvn compile)"
    )
    action_group.add_argument(
        "--package", action="store_true", help="Build and test the project (mvn package)"
    )

    # Test type selection (for --test action)
    test_type_group = parser.add_mutually_exclusive_group()
    test_type_group.add_argument(
        "--unit", action="store_true", help="Run unit tests only (from service root with profiles)"
    )
    test_type_group.add_argument(
        "--integration", action="store_true", help="Run integration tests only (from testing/ dir)"
    )

    # Maven profile control
    parser.add_argument(
        "--profiles",
        type=str,
        help="Maven profiles to activate (comma-separated, e.g., core,azure)",
    )

    parser.add_argument("overrides", nargs="*", help="Environment variable overrides (KEY=VALUE)")

    args = parser.parse_args()

    # Determine action
    if args.test:
        action = "test"
    elif args.validate:
        action = "validate"
    elif args.startup_test:
        action = "startup-test"
    elif args.compile:
        action = "compile"
    elif args.package:
        action = "package"
    else:
        action = "run"

    # Parse environment overrides
    env_overrides = {}
    for override in args.overrides:
        if "=" in override:
            key, value = override.split("=", 1)
            env_overrides[key] = value

    try:
        # Initialize components
        project_root = find_project_root()
        discovery = ServiceDiscovery(project_root)
        env_loader = EnvironmentLoader()
        cmd_builder = CommandBuilder(project_root)
        runner = ServiceRunner()

        # Discover project configuration
        service_config = discovery.find_service(args.project, action)
        print(f"Project: {service_config.name}", file=sys.stderr)
        print(f"Project directory: {service_config.service_dir}", file=sys.stderr)
        if action not in ["compile", "package", "validate"]:
            print(f"Environment file: {service_config.env_file}", file=sys.stderr)

        # Show shared module detection for validate action
        if action == "validate":
            print(f"Shared module: {service_config.is_shared_module}", file=sys.stderr)
            if service_config.available_profiles:
                print(
                    f"Available profiles: {', '.join(service_config.available_profiles)}",
                    file=sys.stderr,
                )

        # Load environment
        env_vars = env_loader.load_environment(service_config.env_file, env_overrides)
        if action not in ["compile", "package", "validate"]:
            print(f"Loaded {len(env_vars)} environment variables", file=sys.stderr)
        if action == "test":
            print(f"Test directory: {service_config.test_dir}", file=sys.stderr)

        # Determine working directory
        if action == "test" and service_config.test_dir:
            work_dir = service_config.test_dir
        elif action in ["run", "startup-test"] and service_config.main_class_dir:
            work_dir = service_config.main_class_dir
        elif action in ["compile", "package", "validate"]:
            # Compile, package, validate actions work from the service root directory
            work_dir = service_config.service_dir
        else:
            work_dir = service_config.service_dir

        # Build command (for non-test actions, printed here; test actions print in each phase)
        if action != "test":
            command = cmd_builder.build_command(action, service_config, env_vars)
            print(f"Command: {command}", file=sys.stderr)
            print(f"Working directory: {work_dir}", file=sys.stderr)

        # Execute action
        if action == "validate":
            return runner.run_validate(command, work_dir)
        elif action == "test":
            # Determine what tests to run based on flags
            run_unit = args.unit or (
                not args.unit and not args.integration
            )  # Default: run unit if not specified
            run_integration = args.integration or (
                not args.unit and not args.integration
            )  # Default: run integration if not specified

            results = []

            # Phase 1: Unit tests (if requested)
            if run_unit and args.profiles:
                print("\n" + "=" * 60, file=sys.stderr)
                print("UNIT TESTS", file=sys.stderr)
                print("=" * 60, file=sys.stderr)

                unit_command = f"mvn test -P{args.profiles}"
                print(f"Command: {unit_command}", file=sys.stderr)
                print(f"Working directory: {service_config.service_dir}", file=sys.stderr)
                print(f"Profiles: {args.profiles}", file=sys.stderr)

                unit_result = runner.run_test(unit_command, service_config.service_dir, {})
                if unit_result != 0:
                    print("\n✗ UNIT TESTS FAILED", file=sys.stderr)
                    if not run_integration:
                        return unit_result
                    results.append(("unit", False))
                else:
                    print("\n✓ UNIT TESTS PASSED", file=sys.stderr)
                    results.append(("unit", True))
            elif run_unit and not args.profiles:
                # No profiles specified - skip unit tests with a warning
                if not args.integration:
                    print(
                        "\nNote: No --profiles specified. Use --profiles to run unit tests.",
                        file=sys.stderr,
                    )
                    print("      Example: --profiles core,azure", file=sys.stderr)

            # Phase 2: Integration tests (if requested and test_dir exists)
            if not run_integration:
                print("\nSkipping integration tests (--unit flag specified)", file=sys.stderr)
            elif not service_config.test_dir:
                print("\nSkipping integration tests (test_dir is None)", file=sys.stderr)
            elif not service_config.test_dir.exists():
                print(
                    f"\nSkipping integration tests (test_dir does not exist: {service_config.test_dir})",
                    file=sys.stderr,
                )

            if run_integration and service_config.test_dir and service_config.test_dir.exists():
                print("\n" + "=" * 60, file=sys.stderr)
                print("INTEGRATION TESTS", file=sys.stderr)
                print("=" * 60, file=sys.stderr)

                int_command = cmd_builder._build_test_command(
                    service_config, env_vars, test_type="integration"
                )
                print(f"Command: {int_command}", file=sys.stderr)
                print(f"Working directory: {work_dir}", file=sys.stderr)

                int_result = runner.run_test(int_command, work_dir, env_vars)
                if int_result != 0:
                    print("\n✗ INTEGRATION TESTS FAILED", file=sys.stderr)
                    results.append(("integration", False))
                else:
                    print("\n✓ INTEGRATION TESTS PASSED", file=sys.stderr)
                    results.append(("integration", True))

            # Summary
            if results:
                print("\n" + "=" * 60, file=sys.stderr)
                print("TEST SUMMARY", file=sys.stderr)
                print("=" * 60, file=sys.stderr)
                for test_type, passed in results:
                    status = "✓ PASSED" if passed else "✗ FAILED"
                    print(f"  {test_type.upper():15} {status}", file=sys.stderr)

                # Return failure if any test failed
                if any(not passed for _, passed in results):
                    return 1
                return 0
            else:
                # No tests were run
                print(
                    "\nNo tests were run. Specify --profiles for unit tests or ensure testing/ exists for integration tests.",
                    file=sys.stderr,
                )
                return 1
        elif action == "run":
            return runner.run_service(command, work_dir, env_vars)
        elif action == "startup-test":
            port = int(env_vars.get("SERVER_PORT", 8080))
            return runner.run_startup_test(command, work_dir, env_vars, port)
        elif action in ["compile", "package"]:
            # Compile and package actions use simple execution (no environment variables needed)
            return runner.run_compile_or_package(command, work_dir)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
