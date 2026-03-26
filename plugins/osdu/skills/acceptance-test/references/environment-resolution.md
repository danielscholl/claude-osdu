# Environment Resolution

How to extract environment configuration from a cimpl-azure-provisioning deployment for use in acceptance tests.

## Locate the Provisioning Repository

```bash
OSDU_WORKSPACE="${OSDU_WORKSPACE:-$(pwd)/..}"
PROV_DIR="$OSDU_WORKSPACE/cimpl-azure-provisioning"

# Check for worktree layout first, then regular clone
ls "$PROV_DIR/main/azure.yaml" 2>/dev/null || \
ls "$PROV_DIR/azure.yaml" 2>/dev/null || echo "Not found"
```

If the provisioning repo is not at the expected path, ask the user for the correct location.

## Read Values from azd

The preferred method uses `azd env get-value` from within the provisioning repo:

```bash
cd "$PROV_DIR"  # or "$PROV_DIR/main" for worktree layout

# Core URL components
INGRESS_PREFIX=$(azd env get-value CIMPL_INGRESS_PREFIX)
DNS_ZONE=$(azd env get-value DNS_ZONE_NAME)

# Auth credentials
DATAFIER_SECRET=$(azd env get-value TF_VAR_datafier_client_secret)
TENANT=$(azd env get-value TF_VAR_cimpl_tenant 2>/dev/null || echo "osdu")
```

### Fallback: Parse .env Directly

If `azd` is not available, parse the environment file directly:

```bash
# Find the active environment
ENV_DIR=$(ls -d "$PROV_DIR/.azure"/*/  2>/dev/null || ls -d "$PROV_DIR/main/.azure"/*/ 2>/dev/null | head -1)

# Extract values
grep "^CIMPL_INGRESS_PREFIX=" "$ENV_DIR/.env" | cut -d= -f2- | tr -d '"'
grep "^DNS_ZONE_NAME=" "$ENV_DIR/.env" | cut -d= -f2- | tr -d '"'
grep "^TF_VAR_datafier_client_secret=" "$ENV_DIR/.env" | cut -d= -f2- | tr -d '"'
```

## URL Construction

### OSDU Service Endpoint

```
OSDU_ENDPOINT=https://${INGRESS_PREFIX}.${DNS_ZONE}
```

All OSDU services are routed through this single gateway domain. Individual service paths follow the pattern `/api/<service>/v1/`.

**Important:** Read each service's `Config.java` to determine whether it expects the bare domain or includes the service path. Common patterns:

| Service Env Var | Typical Value |
|----------------|---------------|
| `PARTITION_BASE_URL` | `https://{domain}` (tests append `/api/partition/v1`) |
| `STORAGE_URL` | `https://{domain}` or `https://{domain}/api/storage/v2` |
| `LEGAL_URL` | `https://{domain}` or `https://{domain}/api/legal/v1` |
| `SEARCH_URL` | `https://{domain}` or `https://{domain}/api/search/v2` |

Always verify by reading the test code — do not assume the pattern.

### Keycloak (OpenID Provider)

The cimpl environment uses Keycloak for all API authentication. Services authenticate via OIDC client credentials — there is no Azure AD / Service Principal path for API access.

**Internal URL** (used by services inside the cluster):
```
http://keycloak.platform.svc.cluster.local:8080/realms/osdu
```

**External URL** (used by acceptance tests running outside the cluster):
```
KEYCLOAK_URL=https://${INGRESS_PREFIX}-keycloak.${DNS_ZONE}
OPENID_PROVIDER_URL=${KEYCLOAK_URL}/realms/osdu
```

The token endpoint is:
```
${OPENID_PROVIDER_URL}/protocol/openid-connect/token
```

## Auth Credential Mapping

### OIDC Client Credentials

The cimpl environment stores auth credentials in the `datafier-secret` Kubernetes secret (namespace `osdu`) with three keys:
- `OPENID_PROVIDER_CLIENT_ID` → `datafier`
- `OPENID_PROVIDER_CLIENT_SECRET` → the client secret
- `OPENID_PROVIDER_URL` → internal Keycloak URL

For acceptance tests running externally, map these to the test's expected env vars:

| Test Env Var | Value |
|-------------|-------|
| `TEST_OPENID_PROVIDER_URL` | `https://{prefix}-keycloak.{zone}/realms/osdu` |
| `PRIVILEGED_USER_OPENID_PROVIDER_CLIENT_ID` | `datafier` |
| `PRIVILEGED_USER_OPENID_PROVIDER_CLIENT_SECRET` | `{TF_VAR_datafier_client_secret}` from azd env |
| `PRIVILEGED_USER_OPENID_PROVIDER_SCOPE` | `openid` (usually default) |

### Direct Token (Quick Debugging)

For quick one-off testing, a pre-obtained bearer token can bypass the OIDC flow:

```bash
# Obtain token via Keycloak
TOKEN=$(curl -s -X POST "${OPENID_PROVIDER_URL}/protocol/openid-connect/token" \
  -d "grant_type=client_credentials" \
  -d "client_id=datafier" \
  -d "client_secret=${DATAFIER_SECRET}" \
  -d "scope=openid" | jq -r '.access_token')
```

Then set `ROOT_USER_TOKEN=$TOKEN` or `PRIVILEGED_USER_TOKEN=$TOKEN`.

**Note:** Tokens expire (typically 5 minutes). Only use for quick debugging, not full test suites.

## Common Defaults

| Variable | Default | Notes |
|----------|---------|-------|
| `MY_TENANT` | `osdu` | Standard cimpl data partition name |
| `DATA_PARTITION_ID` | Same as `MY_TENANT` | Usually identical |
| `CLIENT_TENANT` | `common` | Used by some test-core Config.java |
| `ENVIRONMENT` | `dev` | Triggers cloud-mode config in test-core |
| `DEFAULT_PARTITION` | Same as `MY_TENANT` | Bypass partition for some tests |

## Note on Azure Service Principal

Azure Service Principal credentials in the cimpl environment are used **only for Terraform provisioning** of Azure resources (AKS, DNS, managed identities). They do not have access to the OSDU API layer. Do not attempt to use `INTEGRATION_TESTER`, `AZURE_TESTER_SERVICEPRINCIPAL_SECRET`, or `AZURE_AD_APP_RESOURCE_ID` for acceptance tests — those variables are specific to the legacy Azure OSDU environment, not cimpl.

If a test module's `*TestUtils.java` expects Azure SP credentials (e.g., `AzureTestUtils.java`), check whether it also supports a direct token fallback (`INTEGRATION_TESTER_ACCESS_TOKEN`). If so, obtain a Keycloak token and pass it via that variable.
