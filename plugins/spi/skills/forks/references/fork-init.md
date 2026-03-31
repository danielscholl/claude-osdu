# Fork Initialization

Complete reference for creating new SPI service fork repos from the osdu-spi template.

**Tested and verified:** Full lifecycle completes in under 60 seconds.

## Configuration

```bash
# GitHub org for fork repos (default: azure for production)
ORG="${SPI_ORG:-azure}"

# Template repo (default: azure/osdu-spi)
TEMPLATE="${SPI_TEMPLATE:-azure/osdu-spi}"
```

For engineering system testing with a personal org:
```bash
export SPI_ORG=danielscholl-osdu
export SPI_TEMPLATE=azure/osdu-spi
```

## Service-to-Upstream URL Mapping

| Service | Upstream GitLab URL |
|---------|-------------------|
| partition | `https://community.opengroup.org/osdu/platform/system/partition` |
| entitlements | `https://community.opengroup.org/osdu/platform/security-and-compliance/entitlements` |
| legal | `https://community.opengroup.org/osdu/platform/security-and-compliance/legal` |
| schema | `https://community.opengroup.org/osdu/platform/system/schema-service` |
| file | `https://community.opengroup.org/osdu/platform/system/file` |
| storage | `https://community.opengroup.org/osdu/platform/system/storage` |
| indexer | `https://community.opengroup.org/osdu/platform/system/indexer-service` |
| indexer-queue | `https://community.opengroup.org/osdu/platform/system/indexer-queue` |
| search | `https://community.opengroup.org/osdu/platform/system/search-service` |
| workflow | `https://community.opengroup.org/osdu/platform/data-flow/ingestion/ingestion-workflow` |

The 8 primary forks are partition through search. `indexer-queue` and `workflow` are
additional services that can also be forked.

## Standard Initialization (from main)

**Important:** Do NOT use `gh repo create --template`. The template repo (`azure/osdu-spi`)
is in a Microsoft enterprise org that enforces SAML SSO, which blocks the GraphQL API
even for public repos. Use the clone+push approach below instead.

### Step 1: Check if repo exists

```bash
ORG="${SPI_ORG:-azure}"
SERVICE="partition"
REPO="$ORG/osdu-spi-$SERVICE"

if gh repo view "$REPO" --json name >/dev/null 2>&1; then
  echo "Repository $REPO already exists — skipping creation"
else
  echo "Repository $REPO does not exist — will create"
fi
```

### Step 2: Clone template and create repo

Clone the public template, then create a new repo from the local source:

```bash
TEMPLATE="${SPI_TEMPLATE:-azure/osdu-spi}"
WORK_DIR=$(mktemp -d)

# Clone the public template (no auth needed)
git clone "https://github.com/$TEMPLATE" "$WORK_DIR/osdu-spi-$SERVICE"

# Prepare for new repo
cd "$WORK_DIR/osdu-spi-$SERVICE"
git remote remove origin
git branch -M main

# Create the repo and push
gh repo create "$REPO" --source . --public --push

cd -
rm -rf "$WORK_DIR"
```

The push triggers the `Initialize Fork` workflow automatically.

### Step 3: Wait for "Initialize Fork" workflow (~15s)

```bash
echo "Waiting for Initialize Fork workflow..."
TIMEOUT=300; ELAPSED=0; INTERVAL=15
while [ $ELAPSED -lt $TIMEOUT ]; do
  STATUS=$(gh run list --repo "$REPO" --limit 10 --json name,status,conclusion \
    --jq '[.[] | select(.name | test("Initialize Fork"; "i"))][0] | "\(.status) \(.conclusion)"' 2>/dev/null)
  case "$STATUS" in
    "completed success")
      echo "  [$ELAPSED s] Initialize Fork SUCCEEDED"
      break ;;
    "completed "*)
      echo "  [$ELAPSED s] Initialize Fork FAILED: $STATUS"
      break ;;
    *)
      echo "  [$ELAPSED s] Status: ${STATUS:-pending}..."
      sleep $INTERVAL
      ELAPSED=$((ELAPSED + INTERVAL)) ;;
  esac
done
[ $ELAPSED -ge $TIMEOUT ] && echo "  TIMED OUT after ${TIMEOUT}s"
```

When complete, the workflow has:
- Created labels (upstream-sync, cascade-blocked, human-required, etc.)
- Opened Issue #1 "Repository Initialization Required" with `initialization` label

### Step 4: Comment upstream URL on initialization issue

Look up the upstream URL for the service (see mapping table above) and post it
as a comment on the initialization issue:

```bash
# Use the correct upstream URL for the service
UPSTREAM_URL="https://community.opengroup.org/osdu/platform/system/partition"

ISSUE_NUM=$(gh issue list --repo "$REPO" --state open --json number,title \
  --jq '.[] | select(.title | test("initialization required"; "i")) | .number' | head -1)

if [ -n "$ISSUE_NUM" ]; then
  gh issue comment "$ISSUE_NUM" --repo "$REPO" --body "$UPSTREAM_URL"
  echo "Commented upstream URL on issue #$ISSUE_NUM"
else
  echo "ERROR: Initialization issue not found — check workflow logs"
fi
```

### Step 5: Wait for "Initialize Complete" workflow (~30s)

```bash
echo "Waiting for Initialize Complete workflow..."
TIMEOUT=600; ELAPSED=0; INTERVAL=15
while [ $ELAPSED -lt $TIMEOUT ]; do
  STATUS=$(gh run list --repo "$REPO" --limit 10 --json name,status,conclusion \
    --jq '[.[] | select(.name | test("Initialize Complete"; "i"))][0] | "\(.status) \(.conclusion)"' 2>/dev/null)
  case "$STATUS" in
    "completed success")
      echo "  [$ELAPSED s] Initialize Complete SUCCEEDED"
      break ;;
    "completed "*)
      echo "  [$ELAPSED s] Initialize Complete FAILED: $STATUS"
      break ;;
    *)
      echo "  [$ELAPSED s] Status: ${STATUS:-pending}..."
      sleep $INTERVAL
      ELAPSED=$((ELAPSED + INTERVAL)) ;;
  esac
done
[ $ELAPSED -ge $TIMEOUT ] && echo "  TIMED OUT after ${TIMEOUT}s"
```

When complete, the workflow has:
- Cloned upstream code into `fork_upstream` branch
- Created `fork_integration` branch
- Set `UPSTREAM_REPO_URL` repository variable
- Set `INITIALIZATION_COMPLETE=true` repository variable
- Closed the initialization issue
- Triggered post-init workflows (Maven build, CodeQL, Release Management)

### Step 6: Verify

```bash
echo "Branches:"
gh api "repos/$REPO/branches" --jq '.[].name' | sort
# Expected: fork_integration, fork_upstream, main

echo "Variables:"
gh api "repos/$REPO/actions/variables" --jq '.variables[] | "\(.name)=\(.value)"'
# Expected: INITIALIZATION_COMPLETE=true, UPSTREAM_REPO_URL=https://...

echo "Issue #1:"
gh issue view 1 --repo "$REPO" --json state --jq '.state'
# Expected: CLOSED
```

## Branch-Based Testing (Engineering System Testing)

When testing template changes before merging to `azure/osdu-spi` main,
clone from a feature branch instead:

```bash
# For testing: use personal org (production would leave SPI_ORG unset to default to "azure")
ORG="${SPI_ORG:-danielscholl-osdu}"
TEMPLATE="azure/osdu-spi"
TEMPLATE_BRANCH="feature/new-sync-logic"
SERVICE="partition"
REPO="$ORG/osdu-spi-$SERVICE"
WORK_DIR=$(mktemp -d)

# Clone at the feature branch
git clone --branch "$TEMPLATE_BRANCH" "https://github.com/$TEMPLATE" "$WORK_DIR/osdu-spi-$SERVICE"
cd "$WORK_DIR/osdu-spi-$SERVICE"
git branch -M main
git remote remove origin
gh repo create "$REPO" --source . --public --push
cd -
rm -rf "$WORK_DIR"

# Continue with Steps 3-6 as normal
```

The push triggers the Initialize Fork workflow just like the standard path.

## Bulk Initialization

Initialize all 8 primary services:

```bash
ORG="${SPI_ORG:-azure}"
TEMPLATE="${SPI_TEMPLATE:-azure/osdu-spi}"

declare -A UPSTREAMS=(
  ["partition"]="https://community.opengroup.org/osdu/platform/system/partition"
  ["entitlements"]="https://community.opengroup.org/osdu/platform/security-and-compliance/entitlements"
  ["legal"]="https://community.opengroup.org/osdu/platform/security-and-compliance/legal"
  ["schema"]="https://community.opengroup.org/osdu/platform/system/schema-service"
  ["file"]="https://community.opengroup.org/osdu/platform/system/file"
  ["storage"]="https://community.opengroup.org/osdu/platform/system/storage"
  ["indexer"]="https://community.opengroup.org/osdu/platform/system/indexer-service"
  ["search"]="https://community.opengroup.org/osdu/platform/system/search-service"
)

# Phase 1: Create all repos (fast — no waiting)
for SERVICE in "${!UPSTREAMS[@]}"; do
  REPO="$ORG/osdu-spi-$SERVICE"
  if gh repo view "$REPO" --json name >/dev/null 2>&1; then
    echo "$SERVICE: already exists — skipping"
    continue
  fi
  WORK_DIR=$(mktemp -d)
  git clone --quiet "https://github.com/$TEMPLATE" "$WORK_DIR/osdu-spi-$SERVICE"
  cd "$WORK_DIR/osdu-spi-$SERVICE"
  git remote remove origin && git branch -M main
  gh repo create "$REPO" --source . --public --push 2>&1 | tail -1
  cd - >/dev/null
  rm -rf "$WORK_DIR"
  echo "$SERVICE: created"
done

echo ""
echo "Waiting 30s for Initialize Fork workflows to complete..."
sleep 30

# Phase 2: Comment upstream URLs on all init issues
for SERVICE in "${!UPSTREAMS[@]}"; do
  REPO="$ORG/osdu-spi-$SERVICE"
  UPSTREAM="${UPSTREAMS[$SERVICE]}"
  ISSUE_NUM=$(gh issue list --repo "$REPO" --state open --json number,title \
    --jq '.[] | select(.title | test("initialization required"; "i")) | .number' 2>/dev/null | head -1)
  if [ -n "$ISSUE_NUM" ]; then
    gh issue comment "$ISSUE_NUM" --repo "$REPO" --body "$UPSTREAM" 2>/dev/null
    echo "$SERVICE: commented upstream URL on issue #$ISSUE_NUM"
  else
    echo "$SERVICE: init issue not found (may still be creating)"
  fi
done

echo ""
echo "Waiting 60s for Initialize Complete workflows..."
sleep 60

# Phase 3: Verify all repos
for SERVICE in "${!UPSTREAMS[@]}"; do
  REPO="$ORG/osdu-spi-$SERVICE"
  BRANCHES=$(gh api "repos/$REPO/branches" --jq '[.[].name] | sort | join(", ")' 2>/dev/null)
  INIT=$(gh api "repos/$REPO/actions/variables" --jq '.variables[] | select(.name=="INITIALIZATION_COMPLETE") | .value' 2>/dev/null)
  echo "$SERVICE: branches=[$BRANCHES] init_complete=$INIT"
done
```

## Cleanup (Delete a Fork)

```bash
gh repo delete "$ORG/osdu-spi-$SERVICE" --yes
```

Requires the `delete_repo` scope: `gh auth refresh -h github.com -s delete_repo`

## Troubleshooting

### `--template` flag fails with SSO error

The `azure/osdu-spi` template is in a Microsoft enterprise org. Even though it's
public, the GraphQL API enforces SAML SSO. **Always use the clone+push approach.**

### Initialize Fork workflow doesn't appear

The workflow triggers on `push` to the default branch. Check that the push to
`main` completed and the workflow files exist:
```bash
gh api "repos/$REPO/contents/.github/workflows" --jq '.[].name'
```

### Initialization issue not found

The Initialize Fork workflow creates the issue. Wait for that workflow to complete
first (Step 3), then retry Step 4.

### Initialize Complete times out

The workflow waits for the upstream URL comment on the init issue. Verify:
```bash
gh issue view 1 --repo "$REPO" --comments
```

### Missing branches after init

Check workflow run logs:
```bash
gh run list --repo "$REPO" --limit 5 --json name,conclusion \
  --jq '.[] | "\(.name): \(.conclusion)"'
```

Re-run failed workflows:
```bash
RUN_ID=$(gh run list --repo "$REPO" --json databaseId,conclusion \
  --jq '.[] | select(.conclusion=="failure") | .databaseId' | head -1)
gh run rerun "$RUN_ID" --repo "$REPO"
```
