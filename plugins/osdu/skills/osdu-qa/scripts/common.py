# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx",
# ]
# ///
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
OSDU QA Test Common Utilities

Shared functionality for OSDU QA test scripts including configuration management,
authentication with token caching, and Postman collection/environment discovery.
"""

import json
import os
import time
from pathlib import Path

import httpx

# =============================================================================
# Paths
# =============================================================================

SKILL_DIR = Path(__file__).parent.parent
CONFIG_DIR = SKILL_DIR / "config"
REFERENCE_DIR = SKILL_DIR / "reference"
TOKEN_CACHE_DIR = CONFIG_DIR / "tokens"  # Per-environment token cache directory
PLATFORM_CREDENTIALS_FILE = CONFIG_DIR / "platform_credentials.json"  # Synced from GitLab
ENVIRONMENTS_FILE = CONFIG_DIR / "environments.json"  # User-local environment definitions
LEGACY_ENVIRONMENTS_FILE = REFERENCE_DIR / "environments.json"  # Legacy location (pre-migration)
ACTIVE_ENV_FILE = CONFIG_DIR / ".active_env"  # Current environment selection
HISTORY_FILE = CONFIG_DIR / "history.json"
MANIFEST_FILE = CONFIG_DIR / "manifest.json"
RESULTS_DIR = SKILL_DIR / "results"

MAX_HISTORY_ENTRIES = 20


def _get_token_cache_file(platform: str, environment: str) -> Path:
    """Get the token cache file path for a specific environment.

    Args:
        platform: Platform name (azure, cimpl, etc.)
        environment: Environment name (ship, qa, temp, etc.)

    Returns:
        Path to the environment-specific token cache file
    """
    TOKEN_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return TOKEN_CACHE_DIR / f"token_{platform}_{environment}.json"


def _load_platform_credentials(platform: str, environment: str | None = None) -> dict | None:
    """Load credentials for a platform from the synced credentials file.

    Supports per-environment credentials. Checks in order:
    1. Top-level 'environments' key with 'platform/environment' key (new format)
    2. Platform-level 'environments' sub-key with environment name (legacy)
    3. Platform-level credentials (fallback)

    Args:
        platform: Platform name (azure, cimpl, etc.)
        environment: Optional environment name (qa, temp, dev1, etc.)

    Returns:
        Dict with client_id and client_secret, or None if not found
    """
    if not PLATFORM_CREDENTIALS_FILE.exists():
        return None
    try:
        with open(PLATFORM_CREDENTIALS_FILE) as f:
            data = json.load(f)

        # Check for top-level environment-specific credentials first (new format)
        if environment:
            env_key = f"{platform}/{environment}"
            env_creds = data.get("environments", {}).get(env_key)
            if env_creds and env_creds.get("client_id") and env_creds.get("client_secret"):
                return {
                    "client_id": env_creds.get("client_id"),
                    "client_secret": env_creds.get("client_secret"),
                    "tenant_id": env_creds.get("tenant_id"),
                    "resource_id": env_creds.get("resource_id"),
                }

        # Fall back to platform-level credentials
        platform_creds = data.get("platforms", {}).get(platform)
        if not platform_creds:
            return None

        # Start with platform-level credentials
        result = {
            "client_id": platform_creds.get("client_id"),
            "client_secret": platform_creds.get("client_secret"),
            "tenant_id": platform_creds.get("tenant_id"),
            "resource_id": platform_creds.get("resource_id"),
        }

        # Override with environment-specific credentials if available (legacy format)
        if environment:
            env_creds = platform_creds.get("environments", {}).get(environment, {})
            if env_creds.get("client_id"):
                result["client_id"] = env_creds["client_id"]
            if env_creds.get("client_secret"):
                result["client_secret"] = env_creds["client_secret"]
            if env_creds.get("tenant_id"):
                result["tenant_id"] = env_creds["tenant_id"]
            if env_creds.get("resource_id"):
                result["resource_id"] = env_creds["resource_id"]

        return result
    except (json.JSONDecodeError, IOError):
        return None


def _ensure_environments_file() -> None:
    """Ensure environments.json exists in config/, migrating from legacy location if needed.

    Migration logic:
    1. If config/environments.json exists → do nothing
    2. If reference/environments.json exists (legacy) → copy to config/
    3. Otherwise → create empty skeleton {"platforms": {}}
    """
    if ENVIRONMENTS_FILE.exists():
        return

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if LEGACY_ENVIRONMENTS_FILE.exists():
        # One-time migration from legacy location
        import shutil
        shutil.copy2(LEGACY_ENVIRONMENTS_FILE, ENVIRONMENTS_FILE)
        return

    # Bootstrap with empty skeleton
    with open(ENVIRONMENTS_FILE, "w", encoding="utf-8") as f:
        json.dump({"platforms": {}}, f, indent=2)


def _load_environments_config() -> dict:
    """Load environments configuration."""
    _ensure_environments_file()
    if not ENVIRONMENTS_FILE.exists():
        return {}
    try:
        with open(ENVIRONMENTS_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _load_active_environment() -> dict | None:
    """Load active environment selection from state file.

    Returns:
        Dict with platform and environment keys, or None if not set
    """
    if not ACTIVE_ENV_FILE.exists():
        return None
    try:
        with open(ACTIVE_ENV_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _save_active_environment(platform: str, environment: str) -> None:
    """Save active environment selection to state file.

    Args:
        platform: Platform name (azure, cimpl, etc.)
        environment: Environment name (ship, qa, dev1, etc.)
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(ACTIVE_ENV_FILE, "w") as f:
        json.dump({
            "platform": platform,
            "environment": environment,
            "target": f"{platform}/{environment}",
        }, f, indent=2)


def get_active_environment() -> tuple[str, str] | None:
    """Get currently active environment.

    Returns:
        Tuple of (platform, environment) or None if not set
    """
    active = _load_active_environment()
    if active:
        return (active.get("platform"), active.get("environment"))
    return None


def clear_active_environment() -> bool:
    """Clear the active environment selection.

    Returns:
        True if cleared, False if no active environment was set
    """
    if ACTIVE_ENV_FILE.exists():
        ACTIVE_ENV_FILE.unlink()
        return True
    return False


# =============================================================================
# Public API - Environment & Credentials Loading
# =============================================================================

def load_environments() -> dict:
    """Load environments configuration from environments.json.

    Returns:
        Dict containing platforms and their environments, or empty dict on error.
    """
    return _load_environments_config()


def save_environments(config: dict) -> None:
    """Save environments configuration to config/environments.json.

    Args:
        config: Full environments config dict (with "platforms" key)
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(ENVIRONMENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def load_active_environment() -> dict | None:
    """Load active environment selection from state file.

    Returns:
        Dict with platform, environment, and target keys, or None if not set.
    """
    return _load_active_environment()


def save_active_environment(platform: str, environment: str) -> None:
    """Save active environment selection to state file.

    Args:
        platform: Platform name (azure, cimpl, etc.)
        environment: Environment name (ship, qa, dev1, etc.)
    """
    _save_active_environment(platform, environment)


def load_platform_credentials(platform: str, environment: str | None = None) -> dict | None:
    """Load credentials for a platform/environment from credentials file.

    Args:
        platform: Platform name (azure, cimpl, etc.)
        environment: Optional environment name (qa, temp, dev1, etc.)

    Returns:
        Dict with client_id, client_secret, and optionally tenant_id,
        or None if not found.
    """
    return _load_platform_credentials(platform, environment)


# =============================================================================
# Configuration
# =============================================================================

def get_config(platform: str | None = None, environment: str | None = None) -> dict:
    """Get OSDU configuration from files or environment variables.

    Configuration sources (in priority order):
    1. Explicit platform/environment parameter - when user specifies -e platform/env
    2. Active environment file (.active_env) - if user explicitly set an environment
    3. Environment variables (AI_OSDU_*) - fallback when nothing is explicitly set
    4. Environments config file (for host/token URL patterns)

    When an explicit environment is provided (via -e flag or active environment),
    file-based config takes precedence and environment variables are ignored.
    This prevents credential mixing between platforms.

    When no explicit environment is set, environment variables are used as the
    primary source (for backwards compatibility).

    Environment variables (used when no explicit environment):
    - AI_OSDU_HOST - OSDU hostname
    - AI_OSDU_DATA_PARTITION - Data partition ID
    - AI_OSDU_CLIENT - Client ID
    - AI_OSDU_SECRET - Client secret
    - AI_OSDU_TENANT_ID - Azure tenant ID (Azure only)
    - AI_OSDU_TOKEN_URL - Token endpoint URL (Keycloak/CIMPL only)

    Args:
        platform: Platform identifier (azure, cimpl, aws, gcp). If None, uses active environment.
        environment: Environment name (e.g., 'qa', 'dev1'). If None, uses active environment.

    Returns:
        dict with keys: host, partition, client_id, client_secret, tenant_id, token_url, platform, auth_type, environment
    """
    # Track whether we have an explicit environment selection (from args or active env)
    # If explicit, we use file-based config only and ignore env vars (prevents credential mixing)
    using_explicit_env = platform is not None and environment is not None

    # Check for active environment if platform/environment not specified
    if platform is None or environment is None:
        active = _load_active_environment()
        if active:
            platform = platform or active.get("platform")
            environment = environment or active.get("environment")
            using_explicit_env = True

    # Default to azure if still not set
    platform = platform or "azure"

    # Load environment and credentials configurations
    env_config = _load_environments_config()
    platform_config = env_config.get("platforms", {}).get(platform, {})
    # Note: We'll load credentials again after determining env_name
    platform_creds = None

    # Determine which environment to use
    env_name = environment
    if not env_name and platform_config:
        envs = platform_config.get("environments", {})
        if envs:
            env_name = list(envs.keys())[0]

    env_data = {}
    if env_name and platform_config:
        env_data = platform_config.get("environments", {}).get(env_name, {})

    # Load credentials with environment context for per-env overrides
    platform_creds = _load_platform_credentials(platform, env_name)

    # Build configuration from files first
    host = None
    partition = None
    client_id = None
    client_secret = None
    tenant_id = None
    token_url = None

    # Get host from environment config or pattern
    if "host" in env_data:
        host = env_data["host"]
    elif env_name and "api_host_pattern" in platform_config:
        host = platform_config["api_host_pattern"].replace("{env}", env_name)
    elif env_name and "host_pattern" in platform_config:
        host = platform_config["host_pattern"].replace("{env}", env_name)

    # Get partition from environment config
    partition = env_data.get("partition")

    # Get token URL from pattern (Keycloak)
    if env_name and "token_url_pattern" in platform_config:
        token_url = platform_config["token_url_pattern"].replace("{env}", env_name)

    # Get credentials from platform credentials file
    resource_id = None
    if platform_creds:
        client_id = platform_creds.get("client_id")
        client_secret = platform_creds.get("client_secret")
        tenant_id = platform_creds.get("tenant_id")  # May be None for non-Azure
        resource_id = platform_creds.get("resource_id")  # Separate app reg for OAuth scope

    # Environment variables are only used when no explicit environment is set
    # This prevents credential mixing when user explicitly specifies an environment
    if not using_explicit_env:
        host = os.environ.get("AI_OSDU_HOST") or host
        partition = os.environ.get("AI_OSDU_DATA_PARTITION") or partition
        client_id = os.environ.get("AI_OSDU_CLIENT") or client_id
        client_secret = os.environ.get("AI_OSDU_SECRET") or client_secret
        tenant_id = os.environ.get("AI_OSDU_TENANT_ID") or tenant_id
        token_url = os.environ.get("AI_OSDU_TOKEN_URL") or token_url

    # Detect auth type
    if token_url:
        auth_type = "keycloak"
    elif tenant_id:
        auth_type = "azure-ad"
    else:
        auth_type = "unknown"

    return {
        "host": host,
        "partition": partition,
        "client_id": client_id,
        "client_secret": client_secret,
        "tenant_id": tenant_id,
        "resource_id": resource_id,
        "token_url": token_url,
        "platform": platform,
        "environment": env_name,
        "auth_type": auth_type,
    }


def validate_config(config: dict) -> list[str]:
    """Validate required configuration. Returns list of missing vars.

    Args:
        config: Configuration dict from get_config()

    Returns:
        List of missing environment variable names
    """
    missing = []

    # Common required fields
    common_required = ["host", "partition", "client_id", "client_secret"]

    env_names = {
        "host": "AI_OSDU_HOST",
        "partition": "AI_OSDU_DATA_PARTITION",
        "client_id": "AI_OSDU_CLIENT",
        "client_secret": "AI_OSDU_SECRET",
        "tenant_id": "AI_OSDU_TENANT_ID",
        "token_url": "AI_OSDU_TOKEN_URL",
    }

    for key in common_required:
        if not config.get(key):
            missing.append(env_names[key])

    # Auth-type specific validation
    auth_type = config.get("auth_type", "unknown")

    if auth_type == "azure-ad":
        if not config.get("tenant_id"):
            missing.append(env_names["tenant_id"])
    elif auth_type == "keycloak":
        if not config.get("token_url"):
            missing.append(env_names["token_url"])
    elif auth_type == "unknown":
        # Need either tenant_id (Azure) or token_url (Keycloak)
        if not config.get("tenant_id") and not config.get("token_url"):
            missing.append("AI_OSDU_TENANT_ID or AI_OSDU_TOKEN_URL")

    return missing


# =============================================================================
# Token Management
# =============================================================================

def _load_cached_token(platform: str | None = None, environment: str | None = None) -> dict | None:
    """Load cached token from per-environment cache file.

    Args:
        platform: Platform name for environment-specific cache
        environment: Environment name for environment-specific cache

    Returns:
        Cached token data or None if not found
    """
    if not platform or not environment:
        return None

    token_file = _get_token_cache_file(platform, environment)
    if not token_file.exists():
        return None
    try:
        with open(token_file, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _save_cached_token(token_data: dict, platform: str | None = None, environment: str | None = None) -> None:
    """Save token to per-environment cache file.

    Args:
        token_data: Token data to cache
        platform: Platform name for environment-specific cache
        environment: Environment name for environment-specific cache
    """
    if not platform or not environment:
        return  # Cannot cache without platform/environment context

    token_file = _get_token_cache_file(platform, environment)
    TOKEN_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    with open(token_file, "w", encoding="utf-8") as f:
        json.dump(token_data, f, indent=2)


def _is_token_valid(token_data: dict, buffer_seconds: int = 60) -> bool:
    """Check if cached token is still valid.

    Args:
        token_data: Cached token data with 'expires_at' timestamp
        buffer_seconds: Buffer before expiry to consider token invalid

    Returns:
        True if token is valid, False otherwise
    """
    if not token_data or "expires_at" not in token_data:
        return False
    return time.time() < (token_data["expires_at"] - buffer_seconds)


def get_access_token(config: dict, timeout: float = 30.0, force_refresh: bool = False) -> str:
    """Get access token using client credentials flow.

    Supports multiple auth types:
    - azure-ad: Azure Active Directory OAuth2 v2 endpoint
    - keycloak: Keycloak/OIDC token endpoint (CIMPL, etc.)

    Tokens are cached per-environment and reused until expired. This enables
    parallel testing against multiple environments without token conflicts.

    Args:
        config: Configuration dict from get_config()
        timeout: HTTP request timeout in seconds
        force_refresh: Force token refresh even if cached token is valid

    Returns:
        Access token string

    Raises:
        httpx.HTTPStatusError: If authentication fails
        ValueError: If required config is missing
    """
    # Check for missing config
    missing = validate_config(config)
    if missing:
        raise ValueError(f"Missing configuration: {', '.join(missing)}")

    # Get platform and environment for per-environment caching
    platform = config.get("platform")
    environment = config.get("environment")

    # Check cached token (per-environment if available)
    if not force_refresh:
        cached = _load_cached_token(platform, environment)
        if cached and _is_token_valid(cached):
            return cached["access_token"]

    auth_type = config.get("auth_type", "azure-ad")

    if auth_type == "keycloak":
        # Keycloak/OIDC authentication
        token_url = config["token_url"]
        data = {
            "grant_type": "client_credentials",
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
        }
    else:
        # Azure AD authentication (default)
        # Use resource_id for scope when available (separate app registration),
        # otherwise fall back to client_id
        scope_id = config.get("resource_id") or config["client_id"]
        token_url = f"https://login.microsoftonline.com/{config['tenant_id']}/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "scope": f"{scope_id}/.default",
        }

    with httpx.Client(timeout=timeout) as client:
        response = client.post(token_url, data=data)
        response.raise_for_status()
        token_response = response.json()

    # Cache token with expiry time (per-environment)
    expires_in = token_response.get("expires_in", 3600)
    token_data = {
        "access_token": token_response["access_token"],
        "expires_at": time.time() + expires_in,
        "expires_in": expires_in,
        "token_type": token_response.get("token_type", "Bearer"),
        "auth_type": auth_type,
        "platform": platform,
        "environment": environment,
    }
    _save_cached_token(token_data, platform, environment)

    return token_data["access_token"]


def clear_token_cache(platform: str | None = None, environment: str | None = None) -> bool:
    """Clear the cached token(s).

    If platform and environment are specified, clears only that environment's cache.
    Otherwise, clears all per-environment token caches.

    Args:
        platform: Optional platform to clear cache for
        environment: Optional environment to clear cache for

    Returns:
        True if any cache was cleared, False if no cache existed
    """
    cleared = False

    if platform and environment:
        # Clear specific environment cache
        token_file = _get_token_cache_file(platform, environment)
        if token_file.exists():
            token_file.unlink()
            cleared = True
    else:
        # Clear all per-environment caches
        if TOKEN_CACHE_DIR.exists():
            for token_file in TOKEN_CACHE_DIR.glob("token_*.json"):
                token_file.unlink()
                cleared = True

    return cleared


# =============================================================================
# Health Check
# =============================================================================

def check_environment_health(config: dict, timeout: float = 10.0) -> dict:
    """Perform a quick health check on an OSDU environment.

    Makes a lightweight API call to verify the environment is responsive.
    This should be called before running tests to detect connectivity issues early.

    Args:
        config: Configuration dict from get_config()
        timeout: HTTP request timeout in seconds (short for quick detection)

    Returns:
        Dict with health check results:
        {
            "healthy": bool,
            "host": str,
            "auth_ok": bool,
            "api_ok": bool,
            "response_time_ms": int | None,
            "error": str | None
        }
    """
    result = {
        "healthy": False,
        "host": config.get("host", "unknown"),
        "auth_ok": False,
        "api_ok": False,
        "response_time_ms": None,
        "error": None,
    }

    # Step 1: Check authentication
    try:
        token = get_access_token(config, timeout=timeout)
        result["auth_ok"] = True
    except Exception as e:
        result["error"] = f"Authentication failed: {str(e)}"
        return result

    # Step 2: Make a lightweight API call (legal tags list is fast)
    host = config.get("host", "")
    partition = config.get("partition", "opendes")
    api_url = f"https://{host}/api/legal/v1/legaltags:properties"

    headers = {
        "Authorization": f"Bearer {token}",
        "data-partition-id": partition,
        "Accept": "application/json",
    }

    try:
        import time as _time
        start = _time.time()
        with httpx.Client(timeout=timeout) as client:
            response = client.get(api_url, headers=headers)
            elapsed = (_time.time() - start) * 1000
            result["response_time_ms"] = int(elapsed)

            # Consider environment healthy if we get any valid HTTP response
            # (200 = full success, 401/403 = auth issue but API is reachable)
            if response.status_code == 200:
                result["api_ok"] = True
                result["healthy"] = True
            elif response.status_code in (401, 403):
                # API is reachable but auth/permissions issue
                # This might be a test account limitation, not an environment issue
                result["api_ok"] = True
                result["healthy"] = True
                result["error"] = f"API reachable but returned {response.status_code} (auth/permission)"
            elif response.status_code >= 500:
                # Server error - environment has issues
                result["error"] = f"API server error: {response.status_code}"
            else:
                result["error"] = f"API returned {response.status_code}"
    except httpx.TimeoutException:
        result["error"] = "API timeout - environment may be unresponsive"
    except httpx.ConnectError as e:
        result["error"] = f"Connection failed: {str(e)}"
    except Exception as e:
        result["error"] = f"API check failed: {str(e)}"

    return result


# =============================================================================
# File Discovery
# =============================================================================

def find_collections(repo_path: str | Path) -> list[dict]:
    """Find all Postman collection files in the repository.

    Args:
        repo_path: Path to the repository root

    Returns:
        List of dicts with 'path', 'name', 'folder' keys
    """
    repo_path = Path(repo_path)
    collection_dir = repo_path / "Postman Collection"

    if not collection_dir.exists():
        return []

    collections = []
    for path in collection_dir.rglob("*.postman_collection.json"):
        # Extract folder name (e.g., "11_CICD_Setup_LegalAPI")
        folder = path.parent.name
        # Extract name without extension parts
        name_parts = path.stem.split(".")
        name = ".".join(name_parts[:-1]) if len(name_parts) > 1 else name_parts[0]

        collections.append({
            "path": str(path.relative_to(repo_path)),
            "absolute_path": str(path),
            "name": name,
            "folder": folder,
        })

    # Sort by folder name for consistent ordering
    collections.sort(key=lambda x: x["folder"])
    return collections


def find_environments(repo_path: str | Path) -> list[dict]:
    """Find all Postman environment files in the repository.

    Args:
        repo_path: Path to the repository root

    Returns:
        List of dicts with 'path', 'name', 'platform' keys
    """
    repo_path = Path(repo_path)
    env_dir = repo_path / "Postman Collection" / "00_CICD_Setup_Environment"

    if not env_dir.exists():
        return []

    environments = []
    for path in env_dir.glob("*.postman_environment.json"):
        # Extract platform from filename (e.g., "azure" from "azure.OSDU R3...")
        name_parts = path.stem.split(".")
        platform = name_parts[0].lower() if name_parts else "unknown"
        name = ".".join(name_parts[:-1]) if len(name_parts) > 1 else name_parts[0]

        environments.append({
            "path": str(path.relative_to(repo_path)),
            "absolute_path": str(path),
            "name": name,
            "platform": platform,
        })

    # Sort by platform for consistent ordering
    environments.sort(key=lambda x: x["platform"])
    return environments


def parse_collection(path: str | Path) -> dict:
    """Parse a Postman collection file and extract metadata.

    Args:
        path: Path to the collection JSON file

    Returns:
        Dict with collection metadata: name, folders, request_count, test_count
    """
    path = Path(path)

    with open(path) as f:
        data = json.load(f)

    info = data.get("info", {})
    items = data.get("item", [])

    # Extract folders and count requests/tests
    folders = []
    request_count = 0
    test_count = 0

    def process_items(items_list: list, depth: int = 0) -> None:
        nonlocal request_count, test_count

        for item in items_list:
            if "item" in item:
                # This is a folder
                if depth == 0:
                    folders.append(item.get("name", "Unknown"))
                process_items(item["item"], depth + 1)
            else:
                # This is a request
                request_count += 1
                # Count tests in event scripts
                events = item.get("event", [])
                for event in events:
                    if event.get("listen") == "test":
                        script = event.get("script", {})
                        exec_lines = script.get("exec", [])
                        # Count pm.test() calls
                        for line in exec_lines:
                            if isinstance(line, str):
                                test_count += line.count("pm.test(")

    process_items(items)

    return {
        "name": info.get("name", path.stem),
        "description": info.get("description", ""),
        "folders": folders,
        "request_count": request_count,
        "test_count": test_count,
    }


def get_repo_path() -> Path | None:
    """Detect the repository path by looking for 'Postman Collection' directory.

    Walks up from current directory to find the repo root.

    Returns:
        Path to repository root, or None if not found
    """
    current = Path.cwd()

    # Check current and parent directories
    for _ in range(10):  # Limit search depth
        if (current / "Postman Collection").exists():
            return current
        if current.parent == current:
            break
        current = current.parent

    return None


# =============================================================================
# History Management
# =============================================================================

def _load_history() -> list[dict]:
    """Load run history from file."""
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_history(history: list[dict]) -> None:
    """Save run history to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def save_run_result(result: dict) -> None:
    """Save a test run result to history.

    Args:
        result: Test result dict with keys:
            - collection_id: Collection identifier
            - collection_name: Human-readable name
            - folder: Folder name or None
            - platform: Platform used
            - timestamp: ISO timestamp
            - passed: Boolean
            - summary: Dict with counts
            - failures: List of failure details
    """
    history = _load_history()

    # Add new result at the beginning
    history.insert(0, result)

    # Trim to max entries
    history = history[:MAX_HISTORY_ENTRIES]

    _save_history(history)


def get_run_history(limit: int = 10) -> list[dict]:
    """Get recent run history.

    Args:
        limit: Maximum number of entries to return

    Returns:
        List of run results, most recent first
    """
    history = _load_history()
    return history[:limit]


def get_last_run() -> dict | None:
    """Get the most recent run result.

    Returns:
        Last run result dict, or None if no history
    """
    history = _load_history()
    return history[0] if history else None


def get_last_failure() -> dict | None:
    """Get the most recent failed run result.

    Returns:
        Last failed run result dict, or None if no failures
    """
    history = _load_history()
    for run in history:
        if not run.get("passed", True):
            return run
    return None


def clear_history() -> bool:
    """Clear run history.

    Returns:
        True if history was cleared, False if no history existed
    """
    if HISTORY_FILE.exists():
        HISTORY_FILE.unlink()
        return True
    return False


# =============================================================================
# Collection Aliases
# =============================================================================

# Maps alias -> (folder_id, collection_filename)
# This enables precise resolution for multi-file folders (CRS, Search, WellLog)
SERVICE_ALIASES: dict[str, tuple[str, str]] = {
    # Smoke
    "smoke": ("01_CICD_CoreSmokeTest", "Core Smoke Test Collection.postman_collection.json"),
    # P0 - Core Platform
    "legal": ("11_CICD_Setup_LegalAPI", "Compliance_Legal API CI-CD v2.2.postman_collection.json"),
    "entitlements": ("14_CICD_Setup_EntitlementAPI", "Entitlement API CI-CD v2.0.postman_collection.json"),
    "schema": ("25_CICD_Setup_SchemaAPI", "Schema API CI-CD v1.0.postman_collection.json"),
    "storage": ("12_CICD_Setup_StorageAPI", "Storage API CI-CD v2.0.postman_collection.json"),
    "file": ("21_CICD_Setup_FileAPI", "FileAPI UploadDownload CI-CD v3.0.postman_collection.json"),
    "search": ("37_CICD_R3_SearchAPI", "Search API R3 CI-CD v2.0.postman_collection.json"),
    "secret": ("48_CICD_Setup_SecretService_V1", "Secret Service V1.postman_collection.json"),
    # P1 - Core+
    "unit": ("20_CICD_Setup_UnitAPI", "Unit CI-CD v1.0.postman_collection.json"),
    "crs-catalog": ("16_CICD_Setup_ CRSCatalogServiceAPI", "CRSCatalog API CI-CD v1.0.postman_collection.json"),
    "crs-conversion": ("18_CICD_Setup_CRSConversionAPI", "CRS Conversion API CI-CD v1.0.postman_collection.json"),
    "dataset": ("36_CICD_R3_Dataset", "Dataset API CI-CD v3.0.postman_collection.json"),
    "registration": ("22_CICD_Setup_RegistrationAPI", "Registration API CI-CD v1.0.postman_collection.json"),
    "workflow": ("30_CICD_Setup_WorkflowAPI", "Workflow__CI-CD_v1.0.postman_collection.json"),
    "ingestion": ("29_CICD_Setup_Ingestion", "Manifest_Based_Ingestion_Osdu_ingest_CI-CD_v2.0.postman_collection.json"),
    "csv-ingestion": ("31_CICD_Setup_CSVIngestion", "CSVWorkflow_CI-CD_v2.0.postman_collection.json"),
    "ingestion-ref": ("47_CICD_IngestionByReference", "Ingestion By Reference CI-CD v3.0.postman_collection.json"),
    # P2 - DDMS & Domain
    "wellbore-ddms": ("28_CICD_Setup_WellboreDDMSAPI", "Wellbore DDMS CI-CD v3.0.postman_collection.json"),
    "well-delivery": ("44_CICD_Well_Delivery_DMS", "WellDelivery DDMS CI-CD v3.1.postman_collection.json"),
    "well-data": ("32_CICD_R3_WellDataWorkflow", "Well R3 CI-CD v1.0.postman_collection.json"),
    "wellbore-wf": ("33_CICD_R3_WellboreWorkflow", "Wellbore R3 CI-CD v1.0.postman_collection.json"),
    "markers": ("34_CICD_R3_MarkersWorkflow", "WellboreMarker R3 CI-CD v1.0.postman_collection.json"),
    "welllog": ("35_CICD_R3_WellLogWorkflow", "WellLog R3 CI-CD v1.0.postman_collection.json"),
    "welllog-las": ("35_CICD_R3_WellLogWorkflow", "Ingest WellLog using LAS File CI-CD v1.0.postman_collection.json"),
    "trajectory": ("38_CICD_R3_TrajectoryWorkflow", "Trajectory R3 CI-CD v1.0.postman_collection.json"),
    "seismic": ("39_CICD_R3_Seismic", "Seismic R3 CI-CD v1.0.postman_collection.json"),
    "segy-zgy": ("42_CICD_SEGY_ZGY_Conversion", "SegyToZgyConversion Workflow using SeisStore R3 CI-CD v1.0.postman_collection.json"),
    "segy-openvds": ("46_CICD_SEGY_OpenVDS_Conversion_ManualStorageRecordsCreation", "SegyToOpenVDS conversion using Seisstore CI-CD v1.0.postman_collection.json"),
    "witsml": ("41_CICD_Setup_WITSMLIngestion", "WITSML Energistics XML Ingest CI-CD v3.0.postman_collection.json"),
    "energyml": ("49_CICD_EnergymlConverter_And_Delivery", "EnergisticsParser.postman_collection.json"),
    # Secondary aliases (multi-file folder disambiguation)
    "crs-catalog-v3": ("16_CICD_Setup_ CRSCatalogServiceAPI", "CRS Catalog Service API V3 CI-CD v1.0.postman_collection.json"),
    "crs-conv-v3": ("18_CICD_Setup_CRSConversionAPI", "CRS Conversion Service V3 CI-CD v1.0.postman_collection.json"),
    "search-v1": ("37_CICD_R3_SearchAPI", "Search API R3 CI-CD v1.0.postman_collection.json"),
    # Backward compatibility aliases
    "wellbore": ("28_CICD_Setup_WellboreDDMSAPI", "Wellbore DDMS CI-CD v3.0.postman_collection.json"),
    "crs": ("16_CICD_Setup_ CRSCatalogServiceAPI", "CRSCatalog API CI-CD v1.0.postman_collection.json"),
}

# Maps group alias -> list of individual aliases
TIER_ALIASES: dict[str, list[str]] = {
    "p0": ["legal", "entitlements", "schema", "storage", "file", "search", "secret"],
    "core": ["legal", "entitlements", "schema", "storage", "file", "search", "secret"],
    "p1": ["unit", "crs-catalog", "crs-conversion", "dataset", "registration", "workflow", "ingestion", "csv-ingestion", "ingestion-ref"],
    "core+": ["unit", "crs-catalog", "crs-conversion", "dataset", "registration", "workflow", "ingestion", "csv-ingestion", "ingestion-ref"],
    "p2": ["wellbore-ddms", "well-delivery", "well-data", "wellbore-wf", "markers", "welllog", "trajectory", "seismic", "segy-zgy", "segy-openvds", "witsml", "energyml"],
    "ddms": ["wellbore-ddms", "well-delivery", "well-data", "wellbore-wf", "markers", "welllog", "trajectory", "seismic", "segy-zgy", "segy-openvds", "witsml", "energyml"],
    "well-all": ["wellbore-ddms", "well-delivery", "well-data", "wellbore-wf", "markers", "welllog", "welllog-las", "trajectory"],
    "wellbore-all": ["wellbore-ddms", "wellbore-wf"],
    "seismic-all": ["seismic", "segy-zgy", "segy-openvds"],
    "ingestion-all": ["ingestion", "csv-ingestion", "ingestion-ref", "witsml", "welllog-las"],
}


def resolve_collection_aliases(target: str) -> list[str]:
    """Resolve a target to a list of individual collection aliases.

    If target is a tier/group alias, expands to individual aliases.
    Otherwise returns a single-element list with the target.

    Args:
        target: Alias or group name (e.g., 'legal', 'p0', 'well-all')

    Returns:
        List of individual collection aliases
    """
    target_lower = target.lower()
    if target_lower in TIER_ALIASES:
        return TIER_ALIASES[target_lower]
    return [target]


# =============================================================================
# Live Collection Discovery (no caching)
# =============================================================================

# Default repo path - can be overridden
DEFAULT_REPO_PATH = Path.home() / "workspace" / "qa"


def _extract_service_name(folder_name: str) -> str:
    """Extract service name from folder name."""
    import re
    name = re.sub(r"^\d+_CICD_", "", folder_name)
    name = re.sub(r"(_?Setup_?|_?API$)", "", name)
    name = re.sub(r"^R3_", "", name)
    return name or folder_name


def _get_repo_path_with_fallback() -> Path | None:
    """Get repo path, trying detection first, then fallback to default.

    Returns:
        Path to repository root, or None if not found
    """
    # Try to detect from current directory
    detected = get_repo_path()
    if detected:
        return detected

    # Fallback to default location
    if DEFAULT_REPO_PATH.exists() and (DEFAULT_REPO_PATH / "Postman Collection").exists():
        return DEFAULT_REPO_PATH

    return None


def get_collections_live(repo_path: Path | None = None) -> list[dict]:
    """Scan repository and return all collections with full metadata.

    This performs a live scan every time - no caching.

    Args:
        repo_path: Path to repo. If None, auto-detects.

    Returns:
        List of collection dicts with id, name, path, service, folders, counts
    """
    if repo_path is None:
        repo_path = _get_repo_path_with_fallback()

    if not repo_path:
        return []

    collections_raw = find_collections(repo_path)
    collections = []

    for coll in collections_raw:
        try:
            details = parse_collection(coll["absolute_path"])
            collections.append({
                "id": coll["folder"],
                "name": details["name"],
                "path": coll["path"],
                "service": _extract_service_name(coll["folder"]),
                "folders": details["folders"],
                "request_count": details["request_count"],
                "test_count": details["test_count"],
            })
        except Exception:
            # Skip collections that fail to parse
            continue

    return collections


def get_environments_live(repo_path: Path | None = None) -> list[dict]:
    """Scan repository and return all environment files.

    This performs a live scan every time - no caching.

    Args:
        repo_path: Path to repo. If None, auto-detects.

    Returns:
        List of environment dicts with path, name, platform
    """
    if repo_path is None:
        repo_path = _get_repo_path_with_fallback()

    if not repo_path:
        return []

    return find_environments(repo_path)


def load_manifest() -> dict | None:
    """Get manifest data by scanning the repository live.

    NOTE: This function no longer uses a cached file. It scans the repo
    on every call to ensure collections are always up-to-date with the
    git repository.

    Returns:
        Manifest dict with collections and environments, or None if repo not found
    """
    repo_path = _get_repo_path_with_fallback()
    if not repo_path:
        return None

    collections = get_collections_live(repo_path)
    environments = get_environments_live(repo_path)

    if not collections:
        return None

    return {
        "version": "2.0",
        "repo_path": str(repo_path),
        "summary": {
            "total_collections": len(collections),
            "total_requests": sum(c["request_count"] for c in collections),
            "total_tests": sum(c["test_count"] for c in collections),
            "platforms": list(set(e["platform"] for e in environments)),
        },
        "collections": collections,
        "environments": environments,
    }


def find_collection_by_id(collection_id: str) -> dict | None:
    """Find a collection by ID using alias lookup then live scan.

    Resolution order:
    1. SERVICE_ALIASES - exact alias match with precise (folder, filename) targeting
    2. Exact match on folder ID
    3. Partial match on folder ID (single match only)
    4. Partial match on service name (single match only)

    Args:
        collection_id: Collection alias, folder ID, or partial match

    Returns:
        Collection dict or None if not found
    """
    repo_path = _get_repo_path_with_fallback()
    if not repo_path:
        return None

    collection_id_lower = collection_id.lower()

    # Step 1: Check SERVICE_ALIASES for precise resolution
    if collection_id_lower in SERVICE_ALIASES:
        folder_id, filename = SERVICE_ALIASES[collection_id_lower]
        collection_path = repo_path / "Postman Collection" / folder_id / filename
        if collection_path.exists():
            try:
                details = parse_collection(collection_path)
                rel_path = collection_path.relative_to(repo_path)
                return {
                    "id": folder_id,
                    "name": details["name"],
                    "path": str(rel_path),
                    "service": _extract_service_name(folder_id),
                    "folders": details["folders"],
                    "request_count": details["request_count"],
                    "test_count": details["test_count"],
                }
            except Exception:
                pass  # Fall through to live scan

    # Step 2+: Fall through to live scan for backward compat
    collections = get_collections_live(repo_path)
    if not collections:
        return None

    # Exact match on folder ID
    for coll in collections:
        if coll["id"].lower() == collection_id_lower:
            return coll

    # Partial match on ID
    matches = [c for c in collections if collection_id_lower in c["id"].lower()]
    if len(matches) == 1:
        return matches[0]

    # Partial match on service name
    matches = [c for c in collections if collection_id_lower in c["service"].lower()]
    if len(matches) == 1:
        return matches[0]

    return None


def find_environment_by_platform(platform: str) -> dict | None:
    """Find environment file for a platform using live scan.

    Args:
        platform: Platform name (azure, aws, etc.)

    Returns:
        Environment dict or None if not found
    """
    repo_path = _get_repo_path_with_fallback()
    if not repo_path:
        return None

    environments = get_environments_live(repo_path)

    platform_lower = platform.lower()
    for env in environments:
        if env["platform"] == platform_lower:
            return env
    return None
