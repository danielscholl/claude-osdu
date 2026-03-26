# Maven Commands Reference

## Version Checking Commands

### `check` - Check Single Dependency

Check if a specific Maven dependency version exists and find available updates.

```bash
uv run skills/maven/scripts/check.py check \
  --dependency "org.springframework:spring-core" \
  --version "5.3.0" \
  [--packaging jar] \
  [--json]
```

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| `--dependency`, `-d` | Yes | Maven coordinate in `groupId:artifactId` format |
| `--version`, `-v` | Yes | Version string to check |
| `--packaging`, `-p` | No | Package type: `jar` (default), `pom`, `war` |
| `--json` | No | Output in JSON format |

**Output Fields (JSON):**
```json
{
  "status": "success",
  "result": {
    "dependency": "org.springframework:spring-core",
    "current_version": "5.3.0",
    "exists": true,
    "latest_versions": {
      "major": "6.1.5",
      "minor": "5.3.32",
      "patch": "5.3.32"
    },
    "has_major_update": true,
    "has_minor_update": true,
    "has_patch_update": false,
    "total_versions_available": 187
  }
}
```

---

### `batch` - Check Multiple Dependencies

Check multiple Maven dependencies in a single request.

```bash
uv run skills/maven/scripts/check.py batch \
  --dependencies '[
    {"dependency": "org.springframework:spring-core", "version": "5.3.0"},
    {"dependency": "com.google.guava:guava", "version": "31.0-jre"}
  ]' \
  [--json]
```

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| `--dependencies`, `-d` | Yes | JSON array of dependency objects |
| `--json` | No | Output in JSON format |

**Dependency Object Format:**
```json
{
  "dependency": "groupId:artifactId",
  "version": "1.0.0",
  "packaging": "jar"  // optional
}
```

**Output Fields (JSON):**
```json
{
  "status": "success",
  "result": {
    "total": 2,
    "success": 2,
    "failed": 0,
    "with_updates": 1,
    "results": [...]
  }
}
```

---

### `list` - List Available Versions

List all available versions for a dependency, grouped by version track.

```bash
uv run skills/maven/scripts/check.py list \
  --dependency "org.springframework:spring-core" \
  [--json]
```

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| `--dependency`, `-d` | Yes | Maven coordinate in `groupId:artifactId` format |
| `--json` | No | Output in JSON format |

**Output Fields (JSON):**
```json
{
  "status": "success",
  "result": {
    "dependency": "org.springframework:spring-core",
    "total_versions": 187,
    "tracks": {
      "6.1": ["6.1.5", "6.1.4", ...],
      "6.0": ["6.0.17", ...],
      "5.3": ["5.3.32", ...]
    }
  }
}
```

---

## Security Scanning Commands

### `scan` - Security Vulnerability Scan

Scan a Maven project for security vulnerabilities using Trivy.

```bash
uv run skills/maven/scripts/scan.py scan \
  --path "/path/to/project" \
  [--severity "critical,high"] \
  [--json]
```

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| `--path`, `-p` | Yes | Path to project directory or pom.xml |
| `--severity`, `-s` | No | Comma-separated severity filter (default: all) |
| `--json` | No | Output in JSON format |

**Severity Levels:**
- `critical` - Critical vulnerabilities
- `high` - High severity
- `medium` - Medium severity
- `low` - Low severity

**Output Fields (JSON):**
```json
{
  "status": "success",
  "result": {
    "vulnerabilities_found": true,
    "total_vulnerabilities": 5,
    "severity_counts": {
      "critical": 1,
      "high": 2,
      "medium": 2,
      "low": 0
    },
    "scan_target": "/path/to/project",
    "trivy_available": true,
    "vulnerabilities": [
      {
        "cve_id": "CVE-2024-1234",
        "severity": "critical",
        "package_name": "org.springframework:spring-core",
        "installed_version": "5.3.0",
        "fixed_version": "5.3.32",
        "description": "..."
      }
    ]
  }
}
```

---

### `analyze` - POM File Analysis

Parse and analyze a Maven POM file to extract project structure and dependencies.

```bash
uv run skills/maven/scripts/scan.py analyze \
  --path "/path/to/pom.xml" \
  [--check-versions] \
  [--json]
```

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| `--path`, `-p` | Yes | Path to pom.xml file or directory containing it |
| `--check-versions` | No | Also check for version updates on dependencies |
| `--json` | No | Output in JSON format |

**Output Fields (JSON):**
```json
{
  "status": "success",
  "result": {
    "pom_path": "/path/to/pom.xml",
    "group_id": "com.example",
    "artifact_id": "my-project",
    "version": "1.0.0",
    "packaging": "jar",
    "parent": {
      "group_id": "org.springframework.boot",
      "artifact_id": "spring-boot-starter-parent",
      "version": "3.2.0"
    },
    "dependencies": [...],
    "dependency_management": [...],
    "properties": {...},
    "modules": [...]
  }
}
```

---

## Error Codes

| Code | Description |
|------|-------------|
| `INVALID_COORDINATE` | Invalid Maven coordinate format |
| `DEPENDENCY_NOT_FOUND` | Dependency not found in Maven Central |
| `VERSION_NOT_FOUND` | Specific version not found |
| `MAVEN_API_ERROR` | Error communicating with Maven Central API |
| `INVALID_PATH` | Path does not exist or is invalid |
| `POM_PARSE_ERROR` | Error parsing POM XML file |
| `TRIVY_NOT_AVAILABLE` | Trivy is not installed |
| `TRIVY_SCAN_FAILED` | Trivy scan failed |

---

## Common Examples

### Check Spring Boot version
```bash
uv run check.py check -d "org.springframework.boot:spring-boot" -v "2.7.0"
```

### Check multiple libraries
```bash
uv run check.py batch -d '[
  {"dependency": "org.springframework:spring-core", "version": "5.3.0"},
  {"dependency": "com.fasterxml.jackson.core:jackson-core", "version": "2.14.0"},
  {"dependency": "org.apache.commons:commons-lang3", "version": "3.12.0"}
]' --json
```

### Scan project for critical vulnerabilities only
```bash
uv run scan.py scan -p /path/to/project -s critical,high
```

### Analyze POM and check for updates
```bash
uv run scan.py analyze -p pom.xml --check-versions
```
