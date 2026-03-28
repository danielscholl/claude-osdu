#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "requests>=2.31.0",
#   "rich>=13.0.0",
# ]
# ///
"""
OSDU Data Load - Load datasets into any OSDU instance.

Supports:
  - CIMPL (auto-detected via kubectl, Keycloak auth)
  - Azure ADME (environment variables, Azure AD auth)
  - Manual Keycloak (OSDU_TOKEN_URL environment variable)

Datasets sourced from:
  - data-definitions: reference-data, schemas, activity-templates
  - open-test-data:   tno, volve, nopims
"""

import base64
import json
import os
import subprocess
import sys
import time
import re
import signal
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import requests
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

console = Console()

# ---------------------------------------------------------------------------
# Dataset registry
# ---------------------------------------------------------------------------
REPOS = {
    "data-definitions": "https://community.opengroup.org/osdu/data/data-definitions.git",
    "open-test-data":   "https://community.opengroup.org/osdu/data/open-test-data.git",
}

DATASETS = {
    "reference-data":     ("data-definitions", "ReferenceValues/Manifests/reference-data",       "ReferenceData",  "ReferenceValues/Manifests/reference-data/IngestionSequence.json"),
    "schemas":            ("data-definitions", "SchemaRegistrationResources/shared-schemas",      "ReferenceData",  None),
    "activity-templates": ("data-definitions", "OsduStandardRecords/ActivityTemplates",           "MasterData",     None),
    "tno":                ("open-test-data",   "rc--3.0.0/4-instances/TNO",                       None,             None),
    "volve":              ("open-test-data",   "rc--3.0.0/4-instances/Volve",                     None,             None),
    "nopims":             ("open-test-data",   "rc--3.0.0/4-instances/NOPIMS",                    None,             None),
}

# Template placeholders used in data-definitions manifests
TEMPLATE_VARS = {
    "{{NAMESPACE}}":          lambda cfg: cfg["partition"],
    "{{DATA_OWNERS_GROUP}}":  lambda cfg: cfg["acl_owners"],
    "{{DATA_VIEWERS_GROUP}}": lambda cfg: cfg["acl_viewers"],
    "{{LEGAL_TAG}}":          lambda cfg: cfg["legal_tag"],
    "{{ISO_3166_ALPHA_2_CODE}}": lambda _: "US",
    "{{DATA_PARTITION_ID}}":  lambda cfg: cfg["partition"],
}


# ---------------------------------------------------------------------------
# CIMPL auto-detection
# ---------------------------------------------------------------------------
def _kubectl_get(args: list[str], timeout: int = 10) -> str | None:
    """Run a kubectl command and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            ["kubectl"] + args,
            capture_output=True, text=True, timeout=timeout,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def _detect_cimpl() -> dict | None:
    """Auto-detect CIMPL environment from kubectl context.

    Reads datafier-secret from osdu namespace, derives Keycloak URL,
    and builds a complete config dict. Returns None if not a CIMPL cluster.
    """
    # Check if datafier-secret exists in osdu namespace
    client_id_b64 = _kubectl_get([
        "get", "secret", "datafier-secret", "-n", "osdu",
        "-o", "jsonpath={.data.OPENID_PROVIDER_CLIENT_ID}",
    ])
    if not client_id_b64:
        return None

    client_secret_b64 = _kubectl_get([
        "get", "secret", "datafier-secret", "-n", "osdu",
        "-o", "jsonpath={.data.OPENID_PROVIDER_CLIENT_SECRET}",
    ])
    if not client_secret_b64:
        return None

    try:
        client_id = base64.b64decode(client_id_b64).decode()
        client_secret = base64.b64decode(client_secret_b64).decode()
    except Exception:
        return None

    # Detect partition from namespace label or default
    partition = os.environ.get("OSDU_DATA_PARTITION", "osdu")

    # Use port-forward for service access (set in config, managed at call sites)
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "partition": partition,
        "legal_tag": os.environ.get("OSDU_LEGAL_TAG", "osdu-demo-legaltag"),
        "token_url": "__cimpl_portforward__",  # sentinel: use port-forward to keycloak
        "url": "__cimpl_portforward__",         # sentinel: use port-forward to services
        "acl_owners": f"data.default.owners@{partition}.group",
        "acl_viewers": f"data.default.viewers@{partition}.group",
        "cimpl": True,
    }


# ---------------------------------------------------------------------------
# Port-forward management (CIMPL only)
# ---------------------------------------------------------------------------
_active_port_forwards: list[subprocess.Popen] = []


@contextmanager
def port_forward(namespace: str, service: str, local_port: int, remote_port: int = 80):
    """Start a kubectl port-forward, yield the local URL, clean up on exit."""
    proc = subprocess.Popen(
        ["kubectl", "port-forward", "-n", namespace, f"svc/{service}", f"{local_port}:{remote_port}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    _active_port_forwards.append(proc)
    time.sleep(2)
    if proc.poll() is not None:
        raise RuntimeError(f"Port-forward to {service} failed to start")
    try:
        yield f"http://localhost:{local_port}"
    finally:
        proc.terminate()
        proc.wait(timeout=5)
        _active_port_forwards.remove(proc)


def _cleanup_port_forwards(signum=None, frame=None):
    for proc in _active_port_forwards:
        try:
            proc.terminate()
        except Exception:
            pass
    if signum:
        sys.exit(1)

signal.signal(signal.SIGINT, _cleanup_port_forwards)
signal.signal(signal.SIGTERM, _cleanup_port_forwards)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
def get_config() -> dict:
    # Try CIMPL auto-detection first
    cimpl_cfg = _detect_cimpl()
    if cimpl_cfg:
        console.print("[green]Auto-detected CIMPL environment[/green]")
        # Allow env var overrides
        for key, env_var in [("partition", "OSDU_DATA_PARTITION"), ("legal_tag", "OSDU_LEGAL_TAG")]:
            val = os.environ.get(env_var)
            if val:
                cimpl_cfg[key] = val
        for key, (env_var, default) in [
            ("data_definitions_dir", ("OSDU_DATA_DEFINITIONS_DIR", str(Path.home() / "workspace" / "data-definitions"))),
            ("open_test_data_dir",   ("OSDU_OPEN_TEST_DATA_DIR",   str(Path.home() / "workspace" / "open-test-data"))),
        ]:
            cimpl_cfg[key] = os.environ.get(env_var, default)
        return cimpl_cfg

    # Fall back to environment variables
    required = {
        "url":            "OSDU_URL",
        "partition":      "OSDU_DATA_PARTITION",
        "client_id":      "OSDU_CLIENT_ID",
        "client_secret":  "OSDU_CLIENT_SECRET",
        "legal_tag":      "OSDU_LEGAL_TAG",
    }
    optional = {
        "tenant_id":    ("OSDU_TENANT_ID",    None),
        "token_url":    ("OSDU_TOKEN_URL",    None),
        "resource_id":  ("OSDU_RESOURCE_ID",  None),
        "acl_owners":   ("OSDU_ACL_OWNERS",   None),
        "acl_viewers":  ("OSDU_ACL_VIEWERS",  None),
        "data_definitions_dir": ("OSDU_DATA_DEFINITIONS_DIR", str(Path.home() / "workspace" / "data-definitions")),
        "open_test_data_dir":   ("OSDU_OPEN_TEST_DATA_DIR",   str(Path.home() / "workspace" / "open-test-data")),
    }

    cfg = {"cimpl": False}
    missing = []
    for key, env_var in required.items():
        val = os.environ.get(env_var)
        if not val:
            missing.append(env_var)
        cfg[key] = val

    for key, (env_var, default) in optional.items():
        cfg[key] = os.environ.get(env_var, default)

    # tenant_id is required only for Azure AD (no token_url)
    if not cfg.get("token_url") and not cfg.get("tenant_id"):
        missing.append("OSDU_TENANT_ID (or OSDU_TOKEN_URL for Keycloak)")

    if missing:
        console.print(f"[red]Missing required environment variables:[/red] {', '.join(missing)}")
        console.print("[dim]Tip: For CIMPL environments, ensure kubectl is configured and pointing at your cluster.[/dim]")
        sys.exit(1)

    # Derive ACL groups
    partition = cfg["partition"]
    acl_suffix = ".group" if cfg.get("token_url") else ".dataservices.energy"
    if not cfg["acl_owners"]:
        cfg["acl_owners"] = f"data.default.owners@{partition}{acl_suffix}"
    if not cfg["acl_viewers"]:
        cfg["acl_viewers"] = f"data.default.viewers@{partition}{acl_suffix}"

    return cfg


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
_token_cache: dict = {}


def get_token(cfg: dict) -> str:
    now = time.time()
    if _token_cache.get("token") and _token_cache.get("expires", 0) > now + 60:
        return _token_cache["token"]

    token_url = cfg.get("token_url")

    if token_url and token_url != "__cimpl_portforward__":
        # Keycloak / OIDC flow
        resp = requests.post(token_url, data={
            "grant_type":    "client_credentials",
            "scope":         "openid",
            "client_id":     cfg["client_id"],
            "client_secret": cfg["client_secret"],
        })
        resp.raise_for_status()
        data = resp.json()
        _token_cache["token"] = data.get("id_token") or data.get("access_token")
        _token_cache["expires"] = now + int(data.get("expires_in", 300))
    else:
        # Azure AD flow
        url = f"https://login.microsoftonline.com/{cfg['tenant_id']}/oauth2/v2.0/token"
        scope_id = cfg.get("resource_id") or cfg["client_id"]
        resp = requests.post(url, data={
            "grant_type":    "client_credentials",
            "client_id":     cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "scope":         f"{scope_id}/.default",
        })
        resp.raise_for_status()
        data = resp.json()
        _token_cache["token"] = data["access_token"]
        _token_cache["expires"] = now + int(data.get("expires_in", 3600))

    if not _token_cache.get("token"):
        console.print("[red]Failed to obtain auth token[/red]")
        sys.exit(1)

    return _token_cache["token"]


def _get_token_cimpl(keycloak_url: str, cfg: dict) -> str:
    """Get token via Keycloak port-forward for CIMPL."""
    now = time.time()
    if _token_cache.get("token") and _token_cache.get("expires", 0) > now + 60:
        return _token_cache["token"]

    resp = requests.post(f"{keycloak_url}/realms/osdu/protocol/openid-connect/token", data={
        "grant_type":    "client_credentials",
        "scope":         "openid",
        "client_id":     cfg["client_id"],
        "client_secret": cfg["client_secret"],
    })
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"] = data.get("id_token") or data.get("access_token")
    _token_cache["expires"] = now + int(data.get("expires_in", 300))
    return _token_cache["token"]


def headers(cfg: dict, token: str | None = None) -> dict:
    tok = token or get_token(cfg)
    return {
        "Authorization":    f"Bearer {tok}",
        "data-partition-id": cfg["partition"],
        "Content-Type":     "application/json",
    }


# ---------------------------------------------------------------------------
# Repo / path resolution
# ---------------------------------------------------------------------------
def repo_dir(cfg: dict, repo_name: str) -> Path:
    if repo_name == "data-definitions":
        return Path(cfg["data_definitions_dir"])
    return Path(cfg["open_test_data_dir"])


def dataset_path(cfg: dict, name: str) -> Optional[Path]:
    if name not in DATASETS:
        return None
    repo, rel_path, _, _ = DATASETS[name]
    return repo_dir(cfg, repo) / rel_path


def ensure_repo(cfg: dict, repo_name: str) -> bool:
    path = repo_dir(cfg, repo_name)
    if path.exists():
        return True
    console.print(f"[yellow]Repo not found at {path}[/yellow]")
    console.print(f"[dim]Clone with: git clone {REPOS[repo_name]} {path}[/dim]")
    return False


# ---------------------------------------------------------------------------
# Template substitution
# ---------------------------------------------------------------------------
def substitute_templates(content: str, cfg: dict) -> str:
    for placeholder, resolver in TEMPLATE_VARS.items():
        content = content.replace(placeholder, resolver(cfg))
    return content


# ---------------------------------------------------------------------------
# Manifest discovery
# ---------------------------------------------------------------------------
def collect_manifests(path: Path, sequence_file: Optional[Path] = None) -> list[Path]:
    if sequence_file and sequence_file.exists():
        with open(sequence_file) as f:
            sequence = json.load(f)
        manifests = []
        base = sequence_file.parent
        while base != base.parent:
            if (base / ".git").exists():
                break
            base = base.parent
        for entry in sequence:
            rel = entry.get("FileName", "")
            candidate = base / rel
            if candidate.exists():
                manifests.append(candidate)
        return manifests
    return sorted(path.rglob("*.json"))


# ---------------------------------------------------------------------------
# Workflow submission
# ---------------------------------------------------------------------------
def submit_manifest(cfg: dict, manifest_content: dict, data_key: str,
                    base_url: str | None = None, token: str | None = None) -> tuple[bool, str]:
    url = f"{(base_url or cfg['url']).rstrip('/')}/api/workflow/v1/workflow/Osdu_ingest/workflowRun"
    payload = {
        "executionContext": {
            "Payload": {
                "AppKey": "osdu-data-load",
                "data-partition-id": cfg["partition"],
            },
            "manifest": manifest_content,
        }
    }
    try:
        resp = requests.post(url, json=payload, headers=headers(cfg, token), timeout=30)
        if resp.status_code in (200, 201):
            run_id = resp.json().get("runId", "unknown")
            return True, run_id
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# Direct Storage submission
# ---------------------------------------------------------------------------
STORAGE_BATCH_SIZE = 500

def submit_records_direct(cfg: dict, records: list[dict],
                          base_url: str | None = None, token: str | None = None,
                          progress_cb=None) -> tuple[int, int, list[str]]:
    url = f"{(base_url or cfg['url']).rstrip('/')}/api/storage/v2/records?skipdupes=true"
    total_ok = 0
    total_fail = 0
    errors = []

    seen = {}
    for r in records:
        rid = r.get("id", "")
        if rid:
            seen[rid] = r
        else:
            seen[id(r)] = r
    records = list(seen.values())

    dot_records = [r for r in records if str(r.get("id", "")).endswith(".")]
    non_dot_records = [r for r in records if not str(r.get("id", "")).endswith(".")]
    ordered_records = non_dot_records + dot_records

    for i in range(0, len(ordered_records), STORAGE_BATCH_SIZE):
        batch = ordered_records[i:i + STORAGE_BATCH_SIZE]
        has_dot = any(str(r.get("id", "")).endswith(".") for r in batch)
        has_non_dot = any(not str(r.get("id", "")).endswith(".") for r in batch)
        if has_dot and has_non_dot:
            split_idx = next(j for j, r in enumerate(batch) if str(r.get("id", "")).endswith("."))
            sub_batches = [batch[:split_idx], batch[split_idx:]]
        else:
            sub_batches = [batch]

        for sub_batch in sub_batches:
            if not sub_batch:
                continue
            try:
                resp = requests.put(url, json=sub_batch, headers=headers(cfg, token), timeout=120)
                if resp.status_code in (200, 201):
                    result = resp.json()
                    total_ok += result.get("recordCount", len(sub_batch))
                elif resp.status_code == 409:
                    total_ok += len(sub_batch)
                else:
                    total_fail += len(sub_batch)
                    errors.append(f"Batch {i//STORAGE_BATCH_SIZE}: HTTP {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                total_fail += len(sub_batch)
                errors.append(f"Batch {i//STORAGE_BATCH_SIZE}: {e}")
            if progress_cb:
                progress_cb(len(sub_batch))

    return total_ok, total_fail, errors


# ---------------------------------------------------------------------------
# Open-test-data fixup
# ---------------------------------------------------------------------------
def fixup_open_test_data(content: str, cfg: dict) -> str:
    partition = cfg["partition"]
    content = content.replace('"osdu:', f'"{partition}:')
    content = content.replace(f'"{partition}:wks:', '"osdu:wks:')
    if "{{NAMESPACE}}" in content:
        content = substitute_templates(content, cfg)
    return content


def _resolve_surrogate_id(record: dict, partition: str) -> bool:
    rec_id = str(record.get("id", ""))
    if not rec_id.startswith("surrogate-key:"):
        return True
    kind = record.get("kind", "")
    if "work-product-component--" not in kind:
        return False
    name = record.get("data", {}).get("Name", "")
    if not name:
        return False
    parts = kind.split(":")
    entity_type = parts[2] if len(parts) >= 3 else ""
    if not entity_type:
        return False
    safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', name)
    record["id"] = f"{partition}:{entity_type}:{safe_name}"
    return True


def extract_records_from_manifest(manifest, direct: bool = False,
                                  partition: str = "") -> list[dict]:
    if isinstance(manifest, list):
        records = [r for r in manifest if isinstance(r, dict)]
        if direct:
            records = [r for r in records if _resolve_surrogate_id(r, partition)]
        return records
    records = []
    for key in ("ReferenceData", "MasterData"):
        val = manifest.get(key, [])
        if isinstance(val, list):
            records.extend(r for r in val if isinstance(r, dict))
    data = manifest.get("Data", [])
    if isinstance(data, list):
        records.extend(r for r in data if isinstance(r, dict))
    elif isinstance(data, dict):
        wp = data.get("WorkProduct")
        if isinstance(wp, dict):
            records.append(wp)
        for sub_key in ("WorkProductComponents", "Datasets"):
            sub = data.get(sub_key, [])
            if isinstance(sub, list):
                records.extend(r for r in sub if isinstance(r, dict))
    if direct:
        records = [r for r in records if _resolve_surrogate_id(r, partition)]
    return records


def fixup_record_acl_legal(record: dict, cfg: dict) -> dict:
    record["acl"] = {
        "owners": [cfg["acl_owners"]],
        "viewers": [cfg["acl_viewers"]],
    }
    record["legal"] = {
        "legaltags": [cfg["legal_tag"]],
        "otherRelevantDataCountries": ["US"],
    }
    return record


def load_manifest_file(cfg: dict, path: Path, needs_substitution: bool, data_key: str,
                       direct: bool = False, base_url: str | None = None,
                       token: str | None = None) -> tuple[bool, str, int]:
    try:
        content = path.read_text(encoding="utf-8")
        if needs_substitution:
            content = substitute_templates(content, cfg)
        else:
            content = fixup_open_test_data(content, cfg)
        manifest = json.loads(content)
    except Exception as e:
        return False, f"Parse error: {e}", 0

    if direct:
        records = extract_records_from_manifest(manifest, direct=True, partition=cfg["partition"])
        if not records:
            return True, "No records in manifest", 0
        if not needs_substitution:
            records = [fixup_record_acl_legal(r, cfg) for r in records]
        ok_count, fail_count, errors = submit_records_direct(cfg, records, base_url=base_url, token=token)
        if fail_count == 0:
            return True, f"{ok_count} records", ok_count
        else:
            return False, f"{ok_count} ok, {fail_count} failed: {'; '.join(errors[:3])}", ok_count
    else:
        if "kind" not in manifest:
            manifest["kind"] = "osdu:wks:Manifest:1.0.0"
        ok, run_id_or_err = submit_manifest(cfg, manifest, data_key, base_url=base_url, token=token)
        return ok, run_id_or_err, 0


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cmd_datasets(cfg: dict):
    table = Table(title="Available OSDU Datasets", show_header=True, header_style="bold cyan")
    table.add_column("Dataset", style="bold")
    table.add_column("Repo")
    table.add_column("Path")
    table.add_column("Manifests", justify="right")
    table.add_column("Repo Present", justify="center")

    for name, (repo, rel_path, data_key, seq) in DATASETS.items():
        path = repo_dir(cfg, repo) / rel_path
        present = "[green]yes[/green]" if path.exists() else "[red]no[/red]"
        count = 0
        if path.exists():
            seq_path = (repo_dir(cfg, repo) / seq) if seq else None
            manifests = collect_manifests(path, seq_path)
            count = len(manifests)
        table.add_row(name, repo, rel_path, str(count) if path.exists() else "-", present)

    console.print(table)
    console.print()
    for repo, url in REPOS.items():
        path = repo_dir(cfg, repo)
        status = "[green]present[/green]" if path.exists() else "[red]missing[/red]"
        console.print(f"  {repo}: {path} ({status})")
        if not path.exists():
            console.print(f"    [dim]git clone {url} {path}[/dim]")


def cmd_check(cfg: dict, dataset: str):
    names = list(DATASETS.keys()) if dataset == "all" else [dataset]

    def _do_check(search_url: str, token: str | None):
        for name in names:
            if name not in DATASETS:
                console.print(f"[red]Unknown dataset: {name}[/red]")
                continue
            repo, rel_path, _, _ = DATASETS[name]
            kind_pattern = "osdu:wks:reference-data--*:*" if name == "reference-data" else "*:*:*:*"
            console.print(f"\n[bold cyan]Checking: {name}[/bold cyan]")
            payload = {"kind": kind_pattern, "limit": 1, "query": "*"}
            try:
                resp = requests.post(f"{search_url}/api/search/v2/query",
                                     json=payload, headers=headers(cfg, token), timeout=15)
                if resp.status_code == 200:
                    total = resp.json().get("totalCount", 0)
                    console.print(f"  Records matching [dim]{kind_pattern}[/dim]: [bold]{total:,}[/bold]")
                else:
                    console.print(f"  [red]Search failed: HTTP {resp.status_code}[/red]")
            except Exception as e:
                console.print(f"  [red]Error: {e}[/red]")

            path = repo_dir(cfg, repo) / rel_path
            if path.exists():
                seq_path_str = DATASETS[name][3]
                seq_path = (repo_dir(cfg, repo) / seq_path_str) if seq_path_str else None
                manifests = collect_manifests(path, seq_path)
                console.print(f"  Manifest files available locally: [bold]{len(manifests)}[/bold]")

    if cfg.get("cimpl"):
        with port_forward("platform", "keycloak", 18082, 8080) as kc_url:
            token = _get_token_cimpl(kc_url, cfg)
            with port_forward("osdu", "search", 18084) as search_url:
                _do_check(search_url, token)
    else:
        _do_check(cfg["url"], None)


def cmd_load(cfg: dict, dataset: str, dry_run: bool = False, filter_str: Optional[str] = None,
             direct: bool = False):
    names = list(DATASETS.keys()) if dataset == "all" else [dataset]

    def _do_load(base_url: str, token: str | None):
        for name in names:
            if name not in DATASETS:
                console.print(f"[red]Unknown dataset: {name}[/red]")
                continue
            repo, rel_path, data_key, seq_rel = DATASETS[name]
            if not ensure_repo(cfg, repo):
                console.print(f"[red]Skipping {name} — repo not available[/red]")
                continue
            path = repo_dir(cfg, repo) / rel_path
            if not path.exists():
                console.print(f"[red]Dataset path not found: {path}[/red]")
                continue
            seq_path = (repo_dir(cfg, repo) / seq_rel) if seq_rel else None
            manifests = collect_manifests(path, seq_path)
            if filter_str:
                manifests = [m for m in manifests if filter_str.lower() in m.name.lower()]
            if not manifests:
                console.print(f"[yellow]No manifests found for {name}[/yellow]")
                continue

            needs_substitution = repo == "data-definitions"
            mode = "direct -> Storage API" if direct else "async -> Workflow/Airflow"
            console.print(f"\n[bold cyan]Loading: {name}[/bold cyan] ({len(manifests)} manifests, {mode})")
            if dry_run:
                console.print("[yellow]  DRY RUN — no data will be submitted[/yellow]")

            success = failed = skipped = 0
            total_records = 0
            failed_files = []

            if direct and not dry_run:
                all_records: list[dict] = []
                parse_errors = 0
                with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                              BarColumn(), TaskProgressColumn(), console=console) as progress:
                    task = progress.add_task("  Reading manifests", total=len(manifests))
                    for manifest_path in manifests:
                        progress.update(task, description=f"  {manifest_path.name[:50]:<50}")
                        try:
                            content = manifest_path.read_text(encoding="utf-8")
                            if needs_substitution:
                                content = substitute_templates(content, cfg)
                            else:
                                content = fixup_open_test_data(content, cfg)
                            manifest = json.loads(content)
                            records = extract_records_from_manifest(manifest, direct=True, partition=cfg["partition"])
                            if not needs_substitution:
                                records = [fixup_record_acl_legal(r, cfg) for r in records]
                            all_records.extend(records)
                            success += 1
                        except Exception as e:
                            parse_errors += 1
                            failed_files.append((manifest_path.name, f"Parse error: {e}"))
                        progress.advance(task)

                if all_records:
                    console.print(f"  Parsed {len(all_records):,} records from {success:,} manifests, uploading...")
                    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                                  BarColumn(), TaskProgressColumn(), console=console) as progress:
                        upload_task = progress.add_task("  Uploading", total=len(all_records))
                        def on_batch(n):
                            progress.advance(upload_task, n)
                        ok_count, fail_count, errors = submit_records_direct(
                            cfg, all_records, base_url=base_url, token=token, progress_cb=on_batch)
                    total_records = ok_count
                    if fail_count:
                        failed += 1
                        for err in errors[:5]:
                            failed_files.append(("batch", err))
                failed += parse_errors
            else:
                with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                              BarColumn(), TaskProgressColumn(), console=console) as progress:
                    task = progress.add_task(f"  {name}", total=len(manifests))
                    for manifest_path in manifests:
                        progress.update(task, description=f"  {manifest_path.name[:50]:<50}")
                        if dry_run:
                            skipped += 1
                            progress.advance(task)
                            continue
                        ok, result, rec_count = load_manifest_file(
                            cfg, manifest_path, needs_substitution,
                            data_key or "ReferenceData", direct=direct,
                            base_url=base_url, token=token)
                        total_records += rec_count
                        if ok:
                            success += 1
                        else:
                            failed += 1
                            failed_files.append((manifest_path.name, result))
                        progress.advance(task)

            if dry_run:
                console.print(f"  [dim]Would submit {len(manifests)} manifests[/dim]")
            else:
                records_msg = f"  ({total_records:,} records)" if total_records else ""
                console.print(f"  [green]Success: {success}[/green]  [red]Failed: {failed}[/red]{records_msg}")
                if failed_files:
                    console.print(f"\n  [red]Failed manifests:[/red]")
                    for fname, err in failed_files[:10]:
                        console.print(f"    [dim]{fname}[/dim]: {err}")

    if cfg.get("cimpl"):
        with port_forward("platform", "keycloak", 18082, 8080) as kc_url:
            token = _get_token_cimpl(kc_url, cfg)
            svc = "storage" if direct else "workflow"
            port = 18081 if direct else 18083
            with port_forward("osdu", svc, port) as svc_url:
                _do_load(svc_url, token)
    else:
        _do_load(cfg["url"], None)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="OSDU Data Load — load datasets into any OSDU instance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run load.py datasets
  uv run load.py check --dataset reference-data
  uv run load.py load --dataset reference-data --direct
  uv run load.py load --dataset tno --direct
  uv run load.py load --dataset all --direct
  uv run load.py load --dataset reference-data --dry-run

CIMPL environments are auto-detected via kubectl (zero config needed).
For Azure ADME, set OSDU_URL, OSDU_DATA_PARTITION, OSDU_CLIENT_ID,
OSDU_CLIENT_SECRET, OSDU_TENANT_ID, and OSDU_LEGAL_TAG.
        """
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("datasets", help="List available datasets")

    check_parser = subparsers.add_parser("check", help="Check what is loaded vs available")
    check_parser.add_argument("--dataset", default="all",
                              choices=list(DATASETS.keys()) + ["all"])

    load_parser = subparsers.add_parser("load", help="Load a dataset into OSDU")
    load_parser.add_argument("--dataset", required=True,
                             choices=list(DATASETS.keys()) + ["all"])
    load_parser.add_argument("--dry-run", action="store_true")
    load_parser.add_argument("--direct", action="store_true",
                             help="Use Storage API directly (fast) instead of Workflow/Airflow")
    load_parser.add_argument("--filter", dest="filter_str", default=None)

    args = parser.parse_args()
    cfg = get_config()

    if args.command == "datasets":
        cmd_datasets(cfg)
    elif args.command == "check":
        cmd_check(cfg, args.dataset)
    elif args.command == "load":
        cmd_load(cfg, args.dataset, dry_run=args.dry_run, filter_str=args.filter_str,
                 direct=args.direct)


if __name__ == "__main__":
    main()
