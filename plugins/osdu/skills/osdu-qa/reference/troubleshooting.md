# OSDU QA Test Troubleshooting Guide

## Common Issues and Solutions

### Authentication Issues

#### "Missing AI_OSDU_CLIENT" or similar

**Cause:** Required environment variables are not set.

**Solution:**
```bash
# Set all required variables
export AI_OSDU_HOST="your-host.example.com"
export AI_OSDU_DATA_PARTITION="opendes"
export AI_OSDU_CLIENT="client-id"
export AI_OSDU_SECRET="client-secret"
export AI_OSDU_TENANT_ID="tenant-id"

# Verify
uv run skills/osdu-qa/scripts/status.py check
```

#### "Authentication failed: 401 Unauthorized"

**Cause:** Invalid client credentials or expired secret.

**Solution:**
1. Verify client ID and secret are correct
2. Check if the service principal has required permissions
3. Clear cached token and retry:
   ```bash
   uv run skills/osdu-qa/scripts/status.py clear-cache
   uv run skills/osdu-qa/scripts/status.py auth azure --force
   ```

#### "Authentication failed: AADSTS700016"

**Cause:** Application not found in tenant.

**Solution:**
- Verify AI_OSDU_CLIENT is the correct application/client ID
- Ensure the app is registered in the specified tenant
- Check AI_OSDU_TENANT_ID matches the app's tenant

#### Token Expired During Test Run

**Cause:** Long-running test exceeded token lifetime (1 hour).

**Solution:**
- Tokens are cached for 1 hour with 60-second buffer
- For very long tests, break into smaller folder runs
- The skill automatically refreshes expired tokens

### Newman Issues

#### "Newman is not installed"

**Solution:**
```bash
npm install -g newman

# Verify installation
newman --version
```

#### "newman: command not found"

**Cause:** npm global bin not in PATH.

**Solution:**
```bash
# Find npm global bin directory
npm bin -g

# Add to PATH (bash)
export PATH="$PATH:$(npm bin -g)"

# Or reinstall newman
npm install -g newman
```

#### Newman Timeout

**Cause:** Tests taking longer than 10 minutes.

**Solution:**
- Run specific folders instead of full collection
- Check API responsiveness
- Increase timeout in run.py if needed

### Manifest Issues

#### "No manifest found"

**Solution:**
```bash
uv run skills/osdu-qa/scripts/manifest.py generate
```

#### "Could not detect repository path"

**Cause:** Running from outside the QA repository.

**Solution:**
```bash
# Option 1: Change to repo directory
cd /path/to/qa

# Option 2: Specify path explicitly
uv run skills/osdu-qa/scripts/manifest.py generate --repo-path /path/to/qa
```

#### Manifest Out of Date

**Symptom:** New collections not showing up.

**Solution:**
```bash
# Regenerate manifest
uv run skills/osdu-qa/scripts/manifest.py generate
```

### Test Execution Issues

#### "Collection not found"

**Solution:**
```bash
# List available collections
uv run skills/osdu-qa/scripts/manifest.py list

# Search for collection
uv run skills/osdu-qa/scripts/manifest.py search "your-search"
```

#### "Folder not found in collection"

**Solution:**
```bash
# List folders in collection
uv run skills/osdu-qa/scripts/run.py list-folders COLLECTION_ID
```

#### Tests Pass Locally but Fail in CI

**Possible causes:**
1. Different environment configuration
2. Network/firewall restrictions
3. Rate limiting
4. Data dependencies between tests

**Debugging:**
```bash
# Run with verbose output
uv run skills/osdu-qa/scripts/run.py execute COLLECTION --verbose

# Run specific folder to isolate
uv run skills/osdu-qa/scripts/run.py execute COLLECTION --folder "Folder Name"
```

### API Connectivity Issues

#### "API connectivity: HTTP 403"

**Cause:** Insufficient permissions for the data partition.

**Solution:**
1. Verify the service principal is entitled to the data partition
2. Check entitlements in OSDU:
   - `users.datalake.viewers@{partition}.dataservices.energy`
   - `users.datalake.editors@{partition}.dataservices.energy`

#### "API connectivity: Request failed"

**Cause:** Network issues or OSDU host unreachable.

**Solution:**
1. Verify AI_OSDU_HOST is correct (no https:// prefix)
2. Check network connectivity
3. Verify OSDU services are running

### Python/uv Issues

#### "ModuleNotFoundError: No module named 'click'"

**Cause:** Dependencies not installed by uv.

**Solution:**
```bash
# uv should install automatically, but you can force:
uv pip install click rich httpx
```

#### "uv: command not found"

**Solution:**
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or via pip
pip install uv
```

## Diagnostic Commands

```bash
# Full status check
uv run skills/osdu-qa/scripts/status.py check

# Just authentication test
uv run skills/osdu-qa/scripts/status.py auth azure

# Force fresh token
uv run skills/osdu-qa/scripts/status.py auth azure --force

# JSON output for debugging
uv run skills/osdu-qa/scripts/status.py check --json
```

## Getting Help

1. Check this troubleshooting guide
2. Run status check: `uv run skills/osdu-qa/scripts/status.py check`
3. Review the SKILL.md documentation
4. Check OSDU service status
5. Verify network connectivity and firewall rules
