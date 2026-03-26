# Maven Troubleshooting Guide

## Common Errors

### INVALID_COORDINATE

**Error:** `Invalid Maven coordinate: <dependency>. Expected format: groupId:artifactId`

**Cause:** The dependency string is not in the correct format.

**Solution:**
- Use the format `groupId:artifactId` (e.g., `org.springframework:spring-core`)
- Ensure both groupId and artifactId are provided
- Do not include the version in the dependency string for the `--dependency` option

**Examples:**
```bash
# Correct
--dependency "org.springframework:spring-core"

# Incorrect
--dependency "spring-core"
--dependency "org.springframework:spring-core:5.3.0"
```

---

### DEPENDENCY_NOT_FOUND

**Error:** `Dependency <dependency> not found in Maven Central`

**Cause:** The specified artifact does not exist in Maven Central.

**Solution:**
1. Verify the groupId and artifactId are spelled correctly
2. Check if the artifact is published to Maven Central (some are only in private repos)
3. Search on https://search.maven.org to confirm the artifact exists

---

### VERSION_NOT_FOUND

**Error:** The `exists` field in the response is `false`

**Cause:** The specific version does not exist, though the artifact may exist.

**Solution:**
1. Use the `list` command to see available versions
2. Verify the version string is correct (including qualifiers like `-RELEASE`)
3. Check if the version is still available (old versions may be removed)

```bash
uv run check.py list --dependency "org.springframework:spring-core"
```

---

### MAVEN_API_ERROR

**Error:** `Maven API error: <details>`

**Cause:** Communication issue with Maven Central API.

**Solutions:**
1. Check your internet connection
2. Try again later (Maven Central may be experiencing issues)
3. Check if Maven Central is accessible: https://search.maven.org
4. If behind a proxy, ensure it's configured correctly

---

### TRIVY_NOT_AVAILABLE

**Error:** `Trivy not available. Install: brew install trivy`

**Cause:** Trivy security scanner is not installed or not in PATH.

**Solution:**

**macOS:**
```bash
brew install trivy
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt-get install trivy
```

**Linux (other):**
```bash
curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin
```

**Verify installation:**
```bash
trivy --version
```

---

### TRIVY_SCAN_FAILED

**Error:** `Trivy scan failed: <details>`

**Possible Causes and Solutions:**

1. **Timeout**
   - Large projects may take longer to scan
   - Try scanning a smaller subset of the project

2. **Permission denied**
   - Ensure you have read access to all project files
   - Check file permissions

3. **Invalid project structure**
   - Ensure pom.xml is valid XML
   - Check for syntax errors in POM files

4. **Network issues**
   - Trivy downloads vulnerability databases
   - Ensure internet access for first run

---

### INVALID_PATH

**Error:** `Path does not exist: <path>`

**Cause:** The specified file or directory path is invalid.

**Solution:**
1. Verify the path exists
2. Use absolute paths when possible
3. Check for typos in the path

---

### POM_PARSE_ERROR

**Error:** `XML parse error: <details>` or `Invalid POM file`

**Cause:** The POM file contains invalid XML or is not a valid Maven POM.

**Solutions:**
1. Validate the XML structure (check for unclosed tags, encoding issues)
2. Ensure the file is a Maven POM (should have `<project>` as root element)
3. Check for XML namespace issues

**Validate your POM:**
```bash
xmllint --noout pom.xml
```

---

## Performance Issues

### Slow Version Checks

**Symptoms:** Version checks take a long time

**Solutions:**
1. Use batch checking instead of multiple single checks
2. The script caches results for 1 hour - subsequent checks are faster
3. Check your network latency to Maven Central

### Slow Security Scans

**Symptoms:** Trivy scans take many minutes

**Solutions:**
1. First scan downloads vulnerability database (can take 1-2 minutes)
2. Subsequent scans are faster due to caching
3. Use `--severity critical,high` to reduce output processing time
4. Scan specific directories instead of entire projects

---

## Debug Mode

To get more verbose output for troubleshooting, use the `--json` flag and examine the full response:

```bash
uv run check.py check \
  --dependency "org.springframework:spring-core" \
  --version "5.3.0" \
  --json 2>&1 | jq .
```

---

## Getting Help

### Check Script Version
```bash
uv run check.py --help
uv run scan.py --help
```

### Report Issues
If you encounter persistent issues:
1. Capture the full error output with `--json`
2. Note the command you ran
3. Include your environment (OS, Python version)

---

## Environment Requirements

### Python
- Python 3.11 or higher
- `uv` package manager

### For Version Checking
- Internet access to Maven Central API
- No additional dependencies required

### For Security Scanning
- Trivy installed and in PATH
- Internet access (for vulnerability database updates)
- Read access to project files
