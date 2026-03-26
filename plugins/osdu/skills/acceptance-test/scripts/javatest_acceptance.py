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
OSDU Java Acceptance Test Runner

Runs Java acceptance or integration tests from an OSDU service repository
against a live cimpl environment. Resolves environment configuration (URLs,
auth credentials) from the cimpl-azure-provisioning azd environment automatically.

Usage:
  uv run javatest_acceptance.py --service partition
  uv run javatest_acceptance.py --service partition --dry-run
  uv run javatest_acceptance.py --service storage --provisioning-dir /path/to/prov

Features:
  - Automatic environment resolution from azd .azure/<env>/.env
  - Config.java parsing to discover required env vars
  - Secure credential handling (secrets never appear in logs or command lines)
  - SSL truststore creation for Let's Encrypt certs
  - Surefire XML result parsing with structured output
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from defusedxml import ElementTree

# =============================================================================
# CONSTANTS
# =============================================================================

PROVISIONING_REPO = "cimpl-azure-provisioning"
DEFAULT_BRANCH = "main"

SECRET_PATTERNS = {"secret", "token", "password", "credential"}

# Service API path prefixes — used by HOST_URL which some services expect to
# include the full API path (e.g., legal expects "https://host/api/legal/v1/")
# Services not listed here get just the base endpoint with trailing slash.
SERVICE_API_PATHS = {
    "legal": "/api/legal/v1/",
    "storage": "/api/storage/v2/",
    "search": "/api/search/v2/",
    "indexer": "/api/indexer/v2/",
    "file": "/api/file/v2/",
    "workflow": "/api/workflow/v1/",
    "notification": "/api/notification/v1/",
    "register": "/api/register/v1/",
    "schema": "/api/schema-service/v1/",
    "dataset": "/api/dataset/v1/",
    "unit": "/api/unit/v3/",
    "crs-catalog": "/api/crs/catalog/",
    "crs-conversion": "/api/crs/converter/",
    "entitlements": "/api/entitlements/v2/",
}

# Static mapping: env var name -> lambda(AzdConfig) -> value
# Only variables discovered in Config.java (or core auth vars) will be set.
# Note: Service URL vars include a trailing slash — many test Config.java files
# expect it (e.g., partition's Config.java: "PARTITION_BASE_URL has a '/' at the end")
MAPPING_RULES = {
    # Service URL variables (trailing slash required by test conventions)
    "PARTITION_BASE_URL": lambda c: c.osdu_endpoint + "/",
    "STORAGE_URL": lambda c: c.osdu_endpoint + "/",
    "LEGAL_URL": lambda c: c.osdu_endpoint + "/",
    "SEARCH_URL": lambda c: c.osdu_endpoint + "/",
    "ENTITLEMENTS_URL": lambda c: c.osdu_endpoint + "/",
    "SCHEMA_URL": lambda c: c.osdu_endpoint + "/",
    "FILE_URL": lambda c: c.osdu_endpoint + "/",
    "WORKFLOW_URL": lambda c: c.osdu_endpoint + "/",
    "UNIT_URL": lambda c: c.osdu_endpoint + "/",
    "REGISTER_URL": lambda c: c.osdu_endpoint + "/",
    "DATASET_URL": lambda c: c.osdu_endpoint + "/",
    "NOTIFICATION_URL": lambda c: c.osdu_endpoint + "/",
    "CRS_CATALOG_URL": lambda c: c.osdu_endpoint + "/",
    "CRS_CONVERSION_URL": lambda c: c.osdu_endpoint + "/",
    # HOST_URL is set dynamically per-service — see build_mapping()
    # Tenant variables
    "MY_TENANT": lambda c: c.tenant,
    "DATA_PARTITION_ID": lambda c: c.tenant,
    "DEFAULT_PARTITION": lambda c: c.tenant,
    "CLIENT_TENANT": lambda _: "common",
    # OIDC auth variables
    "TEST_OPENID_PROVIDER_URL": lambda c: c.openid_provider_url,
    "OPENID_PROVIDER_URL": lambda c: c.openid_provider_url,
    "PRIVILEGED_USER_OPENID_PROVIDER_CLIENT_ID": lambda c: c.client_id,
    "PRIVILEGED_USER_OPENID_PROVIDER_CLIENT_SECRET": lambda c: c.client_secret,
    "PRIVILEGED_USER_OPENID_PROVIDER_SCOPE": lambda _: "openid",
    # Environment trigger
    "ENVIRONMENT": lambda _: "dev",
}

# Core auth env vars that are always needed but often referenced via Java
# constants (System.getenv(CONSTANT) instead of System.getenv("literal")),
# so discovery may miss them. Always include these in the mapping.
CORE_AUTH_VARS = {
    "TEST_OPENID_PROVIDER_URL",
    "PRIVILEGED_USER_OPENID_PROVIDER_CLIENT_ID",
    "PRIVILEGED_USER_OPENID_PROVIDER_CLIENT_SECRET",
    "PRIVILEGED_USER_OPENID_PROVIDER_SCOPE",
}


def log(msg: str) -> None:
    """Print diagnostic message to stderr."""
    print(msg, file=sys.stderr)


def mask_value(key: str, value: str) -> str:
    """Mask sensitive values for display."""
    if any(p in key.lower() for p in SECRET_PATTERNS):
        return "[resolved]"
    return value


def parse_dotenv(path: Path) -> dict[str, str]:
    """Parse a .env file into a dict, stripping quotes and comments."""
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        env[key.strip()] = value
    return env


# =============================================================================
# AZD ENVIRONMENT RESOLUTION
# =============================================================================


@dataclass
class AzdConfig:
    """Resolved environment configuration from azd."""

    osdu_endpoint: str
    keycloak_url: str
    openid_provider_url: str
    tenant: str
    client_id: str
    client_secret: str
    provisioning_dir: Path


class AzdEnvironment:
    """Resolve cimpl environment from azd provisioning repo."""

    def __init__(self, workspace: Path | None = None, provisioning_dir: Path | None = None):
        self.workspace = workspace or Path(os.environ.get("OSDU_WORKSPACE", ""))
        self.provisioning_dir_override = provisioning_dir

    def resolve(self) -> AzdConfig:
        """Find provisioning repo and resolve all environment values."""
        prov_dir = self._find_provisioning_dir()
        azure_dir = prov_dir / ".azure"

        if not (azure_dir / "config.json").is_file():
            raise FileNotFoundError(f"No .azure/config.json found in {prov_dir}")

        config = json.loads((azure_dir / "config.json").read_text(encoding="utf-8"))
        env_name = config.get("defaultEnvironment", "")
        if not env_name:
            raise ValueError(f"No defaultEnvironment set in {azure_dir / 'config.json'}")

        env_file = azure_dir / env_name / ".env"
        if not env_file.is_file():
            raise FileNotFoundError(f"Environment file not found: {env_file}")

        azd_vars = parse_dotenv(env_file)
        log(f"Loaded {len(azd_vars)} azd variables from {env_file}")

        prefix = azd_vars.get("CIMPL_INGRESS_PREFIX", "")
        zone = azd_vars.get("DNS_ZONE_NAME", "")
        if not prefix or not zone:
            raise ValueError(
                f"Missing required azd variables: "
                f"CIMPL_INGRESS_PREFIX={'set' if prefix else 'MISSING'}, "
                f"DNS_ZONE_NAME={'set' if zone else 'MISSING'}"
            )

        tenant = azd_vars.get("TF_VAR_cimpl_tenant", "osdu")
        secret = azd_vars.get("TF_VAR_datafier_client_secret", "")
        if not secret:
            raise ValueError("TF_VAR_datafier_client_secret not found in azd environment")

        keycloak_url = f"https://{prefix}-keycloak.{zone}"
        return AzdConfig(
            osdu_endpoint=f"https://{prefix}.{zone}",
            keycloak_url=keycloak_url,
            openid_provider_url=f"{keycloak_url}/realms/osdu",
            tenant=tenant,
            client_id="datafier",
            client_secret=secret,
            provisioning_dir=prov_dir,
        )

    def _find_provisioning_dir(self) -> Path:
        """Locate the cimpl-azure-provisioning repo."""
        if self.provisioning_dir_override:
            return self._validate_prov_dir(self.provisioning_dir_override)

        if self.workspace and self.workspace.is_dir():
            base = self.workspace / PROVISIONING_REPO
            # Worktree layout: main/ subdirectory
            candidate = base / DEFAULT_BRANCH
            if (candidate / ".azure" / "config.json").is_file():
                return candidate
            # Flat clone
            if (base / ".azure" / "config.json").is_file():
                return base

        # Walk up from CWD
        current = Path.cwd().resolve()
        for _ in range(10):
            candidate = current / ".azure"
            if (candidate / "config.json").is_file():
                return current
            parent = current.parent
            if parent == current:
                break
            current = parent

        raise FileNotFoundError(
            f"Cannot find provisioning repo. Searched:\n"
            f"  - $OSDU_WORKSPACE/{PROVISIONING_REPO}/main/\n"
            f"  - $OSDU_WORKSPACE/{PROVISIONING_REPO}/\n"
            f"  - Walk up from CWD\n"
            f"Set --provisioning-dir or $OSDU_WORKSPACE."
        )

    def _validate_prov_dir(self, path: Path) -> Path:
        """Validate that a path looks like a provisioning repo."""
        # Check worktree layout first
        candidate = path / DEFAULT_BRANCH
        if (candidate / ".azure" / "config.json").is_file():
            return candidate
        if (path / ".azure" / "config.json").is_file():
            return path
        raise FileNotFoundError(f"No .azure/config.json found in {path} or {path}/main")


# =============================================================================
# SERVICE TEST DISCOVERY
# =============================================================================


@dataclass
class TestInfo:
    """Discovered test module information."""

    pattern: str  # "A" or "B"
    test_module_dir: Path
    needs_core_build: bool
    core_module_dir: Path | None
    java_source_dirs: list[Path] = field(default_factory=list)


class ServiceTestDiscovery:
    """Find service repos and detect test patterns."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    def find_service(self, service_name: str) -> tuple[Path, TestInfo]:
        """Locate service root and discover test structure."""
        if not re.match(r"^[\w][\w.-]*$", service_name):
            raise ValueError(f"Invalid service name: '{service_name}'")

        service_root = self._find_service_root(service_name)
        test_info = self._detect_test_pattern(service_root, service_name)
        return service_root, test_info

    def find_service_with_pattern(
        self, service_name: str, force_pattern: str | None
    ) -> tuple[Path, TestInfo]:
        """Locate service and optionally force a test pattern."""
        service_root = self._find_service_root(service_name)
        if force_pattern:
            test_info = self._force_pattern(service_root, service_name, force_pattern)
        else:
            test_info = self._detect_test_pattern(service_root, service_name)
        return service_root, test_info

    def _find_service_root(self, service_name: str) -> Path:
        """Find the service repository root directory."""
        candidates = []

        if self.workspace.is_dir():
            base = self.workspace / service_name
            # Worktree layout
            candidates.append(base / "master")
            # Flat clone
            candidates.append(base)

        for candidate in candidates:
            if candidate.is_dir() and (candidate / "pom.xml").is_file():
                return candidate

        raise FileNotFoundError(
            f"Service '{service_name}' not found. Searched:\n"
            + "\n".join(f"  - {c}" for c in candidates)
        )

    def _detect_test_pattern(self, service_root: Path, service_name: str) -> TestInfo:
        """Auto-detect whether the service uses Pattern A or B.

        Pattern A (acceptance-test) is preferred for cimpl environments because
        it uses OIDC auth which maps directly to Keycloak. Pattern B (test-azure)
        expects Azure SP credentials that don't apply to cimpl.
        """
        # Pattern A: <service>-acceptance-test/ (preferred for cimpl)
        for child in service_root.iterdir():
            if child.name.endswith("-acceptance-test") and (child / "pom.xml").is_file():
                return TestInfo(
                    pattern="A",
                    test_module_dir=child,
                    needs_core_build=False,
                    core_module_dir=None,
                    java_source_dirs=[child / "src"],
                )

        # Pattern B: testing/<service>-test-azure/ (fallback)
        testing_dir = service_root / "testing"
        if testing_dir.is_dir():
            for child in testing_dir.iterdir():
                if child.name.endswith("-test-azure") and (child / "pom.xml").is_file():
                    core_dir = self._find_core_module(testing_dir)
                    java_dirs = [child / "src"]
                    if core_dir:
                        java_dirs.insert(0, core_dir / "src")
                    return TestInfo(
                        pattern="B",
                        test_module_dir=child,
                        needs_core_build=core_dir is not None,
                        core_module_dir=core_dir,
                        java_source_dirs=java_dirs,
                    )

        raise FileNotFoundError(
            f"No acceptance tests found for '{service_name}' in {service_root}.\n"
            f"Checked: testing/*-test-azure/ and *-acceptance-test/"
        )

    def _force_pattern(self, service_root: Path, service_name: str, pattern: str) -> TestInfo:
        """Force a specific test pattern."""
        if pattern == "B":
            testing_dir = service_root / "testing"
            for child in testing_dir.iterdir() if testing_dir.is_dir() else []:
                if child.name.endswith("-test-azure") and (child / "pom.xml").is_file():
                    core_dir = self._find_core_module(testing_dir)
                    java_dirs = [child / "src"]
                    if core_dir:
                        java_dirs.insert(0, core_dir / "src")
                    return TestInfo(
                        pattern="B",
                        test_module_dir=child,
                        needs_core_build=core_dir is not None,
                        core_module_dir=core_dir,
                        java_source_dirs=java_dirs,
                    )
            raise FileNotFoundError(f"Pattern B test module not found in {testing_dir}")
        else:
            for child in service_root.iterdir():
                if child.name.endswith("-acceptance-test") and (child / "pom.xml").is_file():
                    return TestInfo(
                        pattern="A",
                        test_module_dir=child,
                        needs_core_build=False,
                        core_module_dir=None,
                        java_source_dirs=[child / "src"],
                    )
            raise FileNotFoundError(f"Pattern A acceptance-test module not found in {service_root}")

    def _find_core_module(self, testing_dir: Path) -> Path | None:
        """Find a test-core module in the testing directory."""
        for child in testing_dir.iterdir():
            if child.name.endswith("-test-core") and (child / "pom.xml").is_file():
                return child
        return None


# =============================================================================
# CONFIG.JAVA PARSER
# =============================================================================

# Regex patterns for extracting env var references from Java source
_GETENV_RE = re.compile(r'System\.getenv\(\s*"([^"]+)"\s*\)')
_GETPROP_RE = re.compile(r'System\.getProperty\(\s*"([^"]+)"')


class ConfigJavaParser:
    """Extract required environment variable names from Java test source."""

    @staticmethod
    def discover_env_vars(source_dirs: list[Path]) -> set[str]:
        """Scan Java source files for System.getenv() and System.getProperty() calls."""
        env_vars: set[str] = set()
        for src_dir in source_dirs:
            if not src_dir.is_dir():
                continue
            for java_file in src_dir.rglob("*.java"):
                try:
                    content = java_file.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                env_vars.update(_GETENV_RE.findall(content))
                env_vars.update(_GETPROP_RE.findall(content))
        return env_vars


# =============================================================================
# ENV VAR MAPPER
# =============================================================================


class EnvVarMapper:
    """Map resolved azd config to test-expected environment variables."""

    @staticmethod
    def build_mapping(azd_config: AzdConfig, required_vars: set[str],
                      service_name: str = "") -> dict[str, str]:
        """Build env var dict for the variables the tests need.

        Args:
            azd_config: Resolved environment configuration.
            required_vars: Env vars discovered from Java source.
            service_name: Service name (used for HOST_URL path resolution).
        """
        # Always include core auth vars — they're often referenced via Java
        # constants so discovery misses them
        all_vars = required_vars | CORE_AUTH_VARS
        mapped = {}
        unmapped = []

        for var_name in sorted(all_vars):
            rule = MAPPING_RULES.get(var_name)
            if rule is not None:
                mapped[var_name] = rule(azd_config)
            else:
                unmapped.append(var_name)

        # Set HOST_URL with service-specific API path if applicable
        if "HOST_URL" in all_vars or "HOST_URL" in required_vars:
            api_path = SERVICE_API_PATHS.get(service_name, "/")
            mapped["HOST_URL"] = azd_config.osdu_endpoint + api_path
            # Remove from unmapped since we handle it here
            unmapped = [v for v in unmapped if v != "HOST_URL"]

        if unmapped:
            log(f"Warning: {len(unmapped)} env var(s) not auto-mapped: {', '.join(unmapped)}")
            log("  These may need manual values or have defaults in the test code.")

        return mapped


# =============================================================================
# SSL TRUSTSTORE
# =============================================================================


class SslTruststore:
    """Create a Java truststore with SSL certificates for all cimpl endpoints."""

    CACHE_DIR = Path.home() / ".osdu-acceptance-test"
    TRUSTSTORE_PATH = CACHE_DIR / "truststore.jks"
    TRUSTSTORE_PASSWORD = "changeit"
    MAX_AGE_SECONDS = 86400  # 24 hours

    @classmethod
    def ensure_truststore(cls, hostnames: list[str]) -> Path | None:
        """Create or reuse a cached truststore for multiple hosts.

        Downloads the full certificate chain from each hostname (needed for
        Let's Encrypt staging certs) and imports all certs into a single
        Java truststore.

        Args:
            hostnames: List of hostnames to trust (e.g., OSDU endpoint + Keycloak).

        Returns:
            Path to the truststore, or None on failure.
        """
        # Check cache
        if cls.TRUSTSTORE_PATH.is_file():
            age = time.time() - cls.TRUSTSTORE_PATH.stat().st_mtime
            if age < cls.MAX_AGE_SECONDS:
                log(f"Using cached truststore ({int(age)}s old): {cls.TRUSTSTORE_PATH}")
                return cls.TRUSTSTORE_PATH

        # Check tool availability
        if not shutil.which("openssl") or not shutil.which("keytool"):
            log("Warning: openssl or keytool not found — skipping SSL truststore setup.")
            log("  Tests may fail with PKIX path building errors.")
            log("  Install a JDK (provides keytool) and OpenSSL to fix this.")
            return None

        cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Remove old truststore if it exists
        if cls.TRUSTSTORE_PATH.is_file():
            cls.TRUSTSTORE_PATH.unlink()

        imported = 0
        for hostname in hostnames:
            certs = cls._download_cert_chain(hostname)
            for idx, cert_pem in enumerate(certs):
                alias = f"{hostname.replace('.', '-')}-{idx}"
                cert_path = cls.CACHE_DIR / f"{alias}.pem"
                cert_path.write_text(cert_pem)
                if cls._import_cert(alias, cert_path):
                    imported += 1

        if imported == 0:
            log("Warning: No certificates imported into truststore.")
            return None

        log(f"Truststore created with {imported} cert(s) from {len(hostnames)} host(s): {cls.TRUSTSTORE_PATH}")
        return cls.TRUSTSTORE_PATH

    @classmethod
    def _download_cert_chain(cls, hostname: str) -> list[str]:
        """Download the full certificate chain from a hostname.

        Returns a list of PEM-encoded certificates (leaf + intermediates + root).
        This is critical for Let's Encrypt staging certs where the intermediate
        CA is not in the default Java truststore.
        """
        log(f"Downloading SSL certificate chain from {hostname}...")
        try:
            result = subprocess.run(
                ["openssl", "s_client", "-showcerts", "-servername", hostname,
                 "-connect", f"{hostname}:443"],
                input="",
                capture_output=True,
                text=True,
                timeout=15,
            )
            # Extract ALL PEM certificates from the chain
            certs = re.findall(
                r"(-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----)",
                result.stdout,
                re.DOTALL,
            )
            if not certs:
                log(f"  Warning: Could not extract certificates from {hostname}.")
                return []
            log(f"  Found {len(certs)} cert(s) in chain for {hostname}")
            return certs
        except (subprocess.TimeoutExpired, OSError) as e:
            log(f"  Warning: Failed to download certificate from {hostname}: {e}")
            return []

    @classmethod
    def _import_cert(cls, alias: str, cert_path: Path) -> bool:
        """Import a single PEM certificate into the truststore."""
        try:
            subprocess.run(
                ["keytool", "-importcert", "-noprompt",
                 "-alias", alias,
                 "-file", str(cert_path),
                 "-keystore", str(cls.TRUSTSTORE_PATH),
                 "-storepass", cls.TRUSTSTORE_PASSWORD],
                capture_output=True,
                text=True,
                timeout=15,
                check=True,
            )
            return True
        except (subprocess.CalledProcessError, OSError) as e:
            log(f"  Warning: Failed to import cert {alias}: {e}")
            return False


# =============================================================================
# TEST RUNNER
# =============================================================================


class TestRunner:
    """Build and execute Maven test commands."""

    @staticmethod
    def detect_git_skip(path: Path) -> str:
        """Detect worktree layout and return git-skip flag if needed."""
        git_path = path / ".git"
        if git_path.is_file():  # worktree: .git is a file, not a directory
            return "-Dmaven.gitcommitid.skip=true"
        return ""

    def run(
        self,
        test_info: TestInfo,
        env_mapping: dict[str, str],
        truststore_path: Path | None,
        service_root: Path,
    ) -> int:
        """Execute the full test flow. Returns exit code."""
        git_skip = self.detect_git_skip(service_root)

        # Auto-detect community Maven settings file
        settings_flag = ""
        for candidate in [
            service_root / ".mvn" / "community-maven.settings.xml",
            service_root / ".mvn" / "settings.xml",
        ]:
            if candidate.is_file():
                settings_flag = f"-s {candidate}"
                log(f"Using Maven settings: {candidate}")
                break

        # Build SSL truststore flags
        # Use JAVA_TOOL_OPTIONS so the truststore is inherited by ALL JVM
        # processes — including Surefire's forked test JVM (which ignores
        # MAVEN_OPTS and doesn't use ${argLine} unless the POM configures it).
        exec_env = {**os.environ, **env_mapping}
        if truststore_path:
            ssl_flags = (
                f"-Djavax.net.ssl.trustStore={truststore_path} "
                f"-Djavax.net.ssl.trustStorePassword={SslTruststore.TRUSTSTORE_PASSWORD}"
            )
            java_tool_opts = os.environ.get("JAVA_TOOL_OPTIONS", "")
            java_tool_opts = f"{java_tool_opts} {ssl_flags}".strip()
            exec_env["JAVA_TOOL_OPTIONS"] = java_tool_opts
            log(f"SSL truststore set via JAVA_TOOL_OPTIONS")

        # Phase 1: Build test-core if Pattern B
        if test_info.needs_core_build and test_info.core_module_dir:
            log(f"\n{'=' * 60}")
            log("BUILDING TEST-CORE")
            log(f"{'=' * 60}")
            core_cmd = f"mvn clean install -q {settings_flag} {git_skip}".strip()
            log(f"Command: {core_cmd}")
            log(f"Directory: {test_info.core_module_dir}")

            rc = self._exec(core_cmd, test_info.core_module_dir, exec_env)
            if rc != 0:
                log("\nTest-core build FAILED")
                return rc
            log("Test-core build succeeded")

        # Phase 2: Run tests
        log(f"\n{'=' * 60}")
        log("RUNNING ACCEPTANCE TESTS")
        log(f"{'=' * 60}")
        test_cmd = f"mvn clean test {settings_flag} {git_skip}".strip()
        log(f"Command: {test_cmd}")
        log(f"Directory: {test_info.test_module_dir}")

        rc = self._exec(test_cmd, test_info.test_module_dir, exec_env)
        return rc

    def _exec(self, command: str, work_dir: Path, env: dict[str, str]) -> int:
        """Execute a maven command via subprocess."""
        try:
            result = subprocess.run(
                shlex.split(command),
                cwd=work_dir,
                env=env,
                timeout=300,
            )
            return result.returncode
        except subprocess.TimeoutExpired:
            log("Error: Test execution timed out after 5 minutes")
            return 1
        except OSError as e:
            log(f"Error executing command: {e}")
            return 1


# =============================================================================
# SUREFIRE PARSER
# =============================================================================


@dataclass
class TestResult:
    """A single test case result."""

    classname: str
    name: str
    time: float
    status: str  # PASS, FAIL, ERROR, SKIP
    message: str | None = None


class SurefireParser:
    """Parse Maven Surefire XML reports."""

    @staticmethod
    def parse(test_module_dir: Path) -> list[TestResult]:
        """Parse all surefire report XMLs in the test module."""
        reports_dir = test_module_dir / "target" / "surefire-reports"
        if not reports_dir.is_dir():
            return []

        results = []
        for xml_file in sorted(reports_dir.glob("TEST-*.xml")):
            try:
                tree = ElementTree.parse(str(xml_file))
            except Exception:
                continue

            root = tree.getroot()
            for tc in root.findall("testcase"):
                status = "PASS"
                message = None
                if tc.find("failure") is not None:
                    status = "FAIL"
                    elem = tc.find("failure")
                    message = elem.get("message", "") if elem is not None else ""
                elif tc.find("error") is not None:
                    status = "ERROR"
                    elem = tc.find("error")
                    message = elem.get("message", "") if elem is not None else ""
                elif tc.find("skipped") is not None:
                    status = "SKIP"

                results.append(TestResult(
                    classname=tc.get("classname", ""),
                    name=tc.get("name", ""),
                    time=float(tc.get("time", "0")),
                    status=status,
                    message=message[:200] if message else None,
                ))
        return results


# =============================================================================
# OUTPUT FORMATTING
# =============================================================================


def print_results(service_name: str, test_info: TestInfo, results: list[TestResult],
                  azd_config: AzdConfig, exit_code: int) -> None:
    """Print structured test results to stdout."""
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    errors = sum(1 for r in results if r.status == "ERROR")
    skipped = sum(1 for r in results if r.status == "SKIP")
    total_time = sum(r.time for r in results)

    overall = "PASSED" if exit_code == 0 else "FAILED"

    print(f"\nAcceptance Tests: {service_name}")
    print(f"Test Module: {test_info.test_module_dir.name} (Pattern {test_info.pattern})")
    print(f"Environment: {azd_config.osdu_endpoint}")
    print(f"Duration: {total_time:.1f}s")
    print(f"Status: {overall}")
    print()

    if results:
        # Header
        print(f"  {'Test Class':<45} {'Result':<8} {'Time':>6}")
        print(f"  {'-' * 45} {'-' * 8} {'-' * 6}")
        for r in results:
            short_class = r.classname.rsplit(".", 1)[-1] if "." in r.classname else r.classname
            label = f"{short_class}#{r.name}"
            if len(label) > 45:
                label = label[:42] + "..."
            print(f"  {label:<45} {r.status:<8} {r.time:>5.1f}s")

    print()
    print(f"Tests: {passed} passed, {failed} failed, {errors} errors, {skipped} skipped")

    # Show failure details
    failures = [r for r in results if r.status in ("FAIL", "ERROR")]
    if failures:
        print("\nFailures:")
        for r in failures:
            short_class = r.classname.rsplit(".", 1)[-1]
            msg = r.message or "(no message)"
            print(f"  - {short_class}#{r.name}: {msg}")


def print_dry_run(service_name: str, test_info: TestInfo, azd_config: AzdConfig,
                  env_mapping: dict[str, str], truststore_path: Path | None,
                  service_root: Path) -> None:
    """Print what would be executed without running."""
    git_skip = TestRunner.detect_git_skip(service_root)

    print(f"=== DRY RUN: Acceptance Test for {service_name} ===")
    print()
    print("Provisioning:")
    print(f"  Directory: {azd_config.provisioning_dir}")
    print(f"  Endpoint:  {azd_config.osdu_endpoint}")
    print()
    print(f"Test Pattern: {test_info.pattern} ({test_info.test_module_dir.name})")
    print(f"  Test Module: {test_info.test_module_dir}")
    if test_info.core_module_dir:
        print(f"  Core Module: {test_info.core_module_dir}")
    print()
    print(f"Environment Variables ({len(env_mapping)} resolved):")
    for key in sorted(env_mapping):
        display = mask_value(key, env_mapping[key])
        print(f"  {key:<50} = {display}")

    unmapped_note = [v for v in env_mapping if MAPPING_RULES.get(v) is None]
    if unmapped_note:
        print(f"\n  Warning: unmapped vars: {', '.join(unmapped_note)}")

    print()
    print("SSL Truststore:")
    if truststore_path:
        print(f"  Path: {truststore_path}")
    else:
        print("  Not configured (openssl/keytool not available or --skip-ssl-setup)")

    print()
    print("Commands (would execute):")
    step = 1
    if test_info.needs_core_build and test_info.core_module_dir:
        cmd = f"mvn clean install -q {git_skip}".strip()
        print(f"  {step}. cd {test_info.core_module_dir} && {cmd}")
        step += 1
    test_cmd = f"mvn clean test {git_skip}".strip()
    print(f"  {step}. cd {test_info.test_module_dir} && {test_cmd}")


# =============================================================================
# MAIN
# =============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="OSDU Java Acceptance Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --service partition
  %(prog)s --service partition --dry-run
  %(prog)s --service storage --provisioning-dir /path/to/prov
  %(prog)s --service legal --pattern A
""",
    )
    parser.add_argument("--service", required=True, help="OSDU service name (e.g., partition)")
    parser.add_argument("--provisioning-dir", type=Path, help="Path to cimpl-azure-provisioning")
    parser.add_argument("--workspace", type=Path, help="OSDU workspace path (default: $OSDU_WORKSPACE)")
    parser.add_argument("--pattern", choices=["A", "B"], help="Force test pattern (default: auto-detect)")
    parser.add_argument("--skip-ssl-setup", action="store_true", help="Skip SSL truststore creation")
    parser.add_argument("--dry-run", action="store_true", help="Show config and commands without executing")
    args = parser.parse_args()

    try:
        # Phase 1: Resolve azd environment
        log("Resolving environment...")
        workspace = args.workspace or Path(os.environ.get("OSDU_WORKSPACE", str(Path.cwd().parent)))
        azd_env = AzdEnvironment(workspace=workspace, provisioning_dir=args.provisioning_dir)
        azd_config = azd_env.resolve()
        log(f"  Endpoint: {azd_config.osdu_endpoint}")
        log(f"  Tenant:   {azd_config.tenant}")

        # Phase 2: Find service and test module
        log(f"\nDiscovering tests for '{args.service}'...")
        discovery = ServiceTestDiscovery(workspace)
        service_root, test_info = discovery.find_service_with_pattern(args.service, args.pattern)
        log(f"  Pattern:     {test_info.pattern}")
        log(f"  Test module: {test_info.test_module_dir}")
        if test_info.core_module_dir:
            log(f"  Core module: {test_info.core_module_dir}")

        # Phase 3: Parse Config.java for required env vars
        log("\nDiscovering required env vars from Java source...")
        required_vars = ConfigJavaParser.discover_env_vars(test_info.java_source_dirs)
        log(f"  Found {len(required_vars)} env var references")

        # Phase 4: Map azd values to test env vars
        env_mapping = EnvVarMapper.build_mapping(azd_config, required_vars, args.service)
        log(f"  Mapped {len(env_mapping)} env vars")

        # Phase 5: SSL truststore (covers both OSDU endpoint and Keycloak)
        truststore_path = None
        if not args.skip_ssl_setup:
            osdu_host = azd_config.osdu_endpoint.replace("https://", "").split("/")[0]
            keycloak_host = azd_config.keycloak_url.replace("https://", "").split("/")[0]
            truststore_path = SslTruststore.ensure_truststore([osdu_host, keycloak_host])

        # Dry run: show what would happen and exit
        if args.dry_run:
            print_dry_run(args.service, test_info, azd_config, env_mapping,
                          truststore_path, service_root)
            return 0

        # Phase 6: Execute tests
        runner = TestRunner()
        exit_code = runner.run(test_info, env_mapping, truststore_path, service_root)

        # Phase 7: Parse and report results
        results = SurefireParser.parse(test_info.test_module_dir)
        print_results(args.service, test_info, results, azd_config, exit_code)

        return exit_code

    except (FileNotFoundError, ValueError) as e:
        log(f"\nError: {e}")
        return 1
    except KeyboardInterrupt:
        log("\nInterrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
