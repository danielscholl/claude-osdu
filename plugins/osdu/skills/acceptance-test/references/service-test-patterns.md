# OSDU Service Test Patterns

OSDU Java services follow two test patterns. Identifying which pattern a service uses determines the build order, test module path, and auth mechanism.

## Pattern A: Standalone Acceptance Test

```
<service>/
├── <service>-acceptance-test/
│   ├── pom.xml
│   └── src/test/java/.../
│       ├── api/
│       │   ├── HealthCheckApiTest.java
│       │   ├── SwaggerApiTest.java
│       │   └── <Service>ApiTest.java
│       └── util/
│           ├── Config.java
│           ├── TestTokenUtils.java
│           └── conf/OpenIDTokenProvider.java
```

**Characteristics:**
- Self-contained Maven module — no dependency on test-core
- Auth: OIDC client credentials or direct token
- Simpler env var set (typically just `SERVICE_BASE_URL` + `MY_TENANT` + OIDC vars)
- Provider-agnostic — same tests run against any cloud

**Build command:**
```bash
cd <service>-acceptance-test && mvn clean test
```

**Config discovery:**
```bash
find <service>-acceptance-test/src -name "Config.java"
```

## Pattern B: Provider-Specific Test (Core + Azure)

```
<service>/
├── testing/
│   ├── pom.xml                          # Parent POM for all test modules
│   ├── <service>-test-core/
│   │   ├── pom.xml
│   │   └── src/main/java/.../           # Note: main/, not test/
│   │       ├── api/
│   │       │   ├── BaseTestTemplate.java
│   │       │   ├── ListApiTest.java
│   │       │   └── CreateTest.java
│   │       └── util/
│   │           ├── Config.java
│   │           ├── TestUtils.java
│   │           └── RestDescriptor.java
│   ├── <service>-test-azure/
│   │   ├── pom.xml
│   │   └── src/test/java/.../
│   │       ├── api/
│   │       │   ├── TestListPartitions.java   # Extends core tests
│   │       │   └── TestCreate.java
│   │       └── util/
│   │           ├── AzureTestUtils.java
│   │           └── AzureServicePrincipal.java
│   ├── <service>-test-aws/
│   ├── <service>-test-gc/
│   └── <service>-test-ibm/
```

**Characteristics:**
- Core module contains shared test logic (packaged as JAR in `main/` scope)
- Provider modules extend core tests with provider-specific auth
- Azure module has Azure SP auth code, but **cimpl environments use Keycloak OIDC** — pass a Keycloak token via `INTEGRATION_TESTER_ACCESS_TOKEN` to bypass the SP flow
- Richer test coverage — includes CRUD operations, not just smoke tests
- Requires building test-core first

**Build commands:**
```bash
# Step 1: Install test-core
cd testing/<service>-test-core && mvn clean install -q $GIT_SKIP

# Step 2: Run Azure tests
cd testing/<service>-test-azure && mvn clean test $GIT_SKIP
```

**Config discovery:**
```bash
# Core config (base env vars)
find testing/<service>-test-core/src -name "Config.java"

# Azure-specific auth
find testing/<service>-test-azure/src -name "*TestUtils*" -o -name "*ServicePrincipal*"
```

## How to Identify the Pattern

```bash
SERVICE_ROOT="$OSDU_WORKSPACE/<service>"
# Check for worktree layout
[ -d "$SERVICE_ROOT/master" ] && SERVICE_ROOT="$SERVICE_ROOT/master"

# Pattern B (preferred)
if [ -d "$SERVICE_ROOT/testing" ]; then
    echo "Pattern B: testing/<service>-test-azure/"
    ls "$SERVICE_ROOT/testing/"*-test-azure/pom.xml 2>/dev/null

# Pattern A (fallback)
elif ls "$SERVICE_ROOT/"*-acceptance-test/pom.xml 2>/dev/null; then
    echo "Pattern A: <service>-acceptance-test/"

else
    echo "No acceptance tests found"
fi
```

## Worktree Build Fix

When the service repo uses a bare clone + worktree layout (`.git` is a file, not a directory), the `git-commit-id` Maven plugin fails. Always detect and skip:

```bash
[ -f .git ] && GIT_SKIP="-Dmaven.gitcommitid.skip=true" || GIT_SKIP=""
```

Apply `$GIT_SKIP` to all `mvn` commands.

## Common Env Var Names by Service

These are the most common env var names. **Always verify by reading Config.java** — services are not perfectly consistent.

| Service | Base URL Var | Tenant Var |
|---------|-------------|------------|
| partition | `PARTITION_BASE_URL` | `MY_TENANT` |
| storage | `STORAGE_URL` | `MY_TENANT` |
| legal | `LEGAL_URL` | `MY_TENANT` |
| search | `SEARCH_URL` | `MY_TENANT` |
| entitlements | `ENTITLEMENTS_URL` | `MY_TENANT` |
| schema | `SCHEMA_URL` | `MY_TENANT` |
| file | `FILE_URL` | `MY_TENANT` |
| workflow | `WORKFLOW_URL` | `MY_TENANT` |
| unit | `UNIT_URL` | `MY_TENANT` |
| register | `REGISTER_URL` | `MY_TENANT` |
| dataset | `DATASET_URL` | `MY_TENANT` |
| notification | `NOTIFICATION_URL` | `MY_TENANT` |

**Note:** The actual var names may differ. The table above is a starting reference — Phase 2 (Analyze) is the authoritative source.
