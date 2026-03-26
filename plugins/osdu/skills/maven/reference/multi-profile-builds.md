# Multi-Profile Maven Builds

When modifying shared modules in multi-profile Maven projects, changes must be validated against ALL profiles to prevent CI failures.

## The Problem

Maven profiles separate cloud-provider-specific implementations:

```
partition/
├── partition-core/          # Shared - no cloud deps
├── partition-core-plus/     # Shared - extended core
├── partition-azure/         # -Pazure profile
├── partition-gc/            # -Pgc profile
├── partition-aws/           # -Paws profile
└── partition-ibm/           # -Pibm profile
```

**Local default build:** `mvn test` only builds `core` profile modules.
**CI build:** `mvn test -Pcore,azure,gc,aws,ibm` builds ALL modules.

If you modify `partition-core-plus` and only run `mvn test`, you won't catch compile errors in `partition-gc` that depend on the changed code.

## Shared Module Detection

A module is "shared" if ANY of these are true:

| Indicator | Example |
|-----------|---------|
| Name contains `core` | `partition-core`, `partition-core-plus` |
| Name contains `common` | `common-lib`, `os-common` |
| Name contains `shared` | `shared-utils` |
| Name contains `api` | `partition-api` |
| Name contains `model` | `data-model` |
| Listed in parent `<dependencyManagement>` | Any centrally managed dependency |
| Imported by multiple profile-specific modules | Check with `grep -r "artifactId"` |

## Profile Discovery

### Find all profile IDs in a project

```bash
# From project root
grep -h "<id>" pom.xml */pom.xml 2>/dev/null | \
  sed 's/.*<id>\(.*\)<\/id>.*/\1/' | \
  sort -u
```

### Check if profiles exist

```bash
grep -l "<profiles>" pom.xml ../pom.xml 2>/dev/null
```

### Extract profile details

```bash
grep -A5 "<profile>" pom.xml | head -30
```

## Build Commands

### Default (non-shared modules)

```bash
mvn verify
```

### Shared modules - validate all profiles

```bash
# OSDU standard profiles
mvn verify -Pcore,azure,gc,aws,ibm

# Or discover and use all profiles dynamically
PROFILES=$(grep -h "<id>" pom.xml */pom.xml 2>/dev/null | sed 's/.*<id>\(.*\)<\/id>.*/\1/' | sort -u | tr '\n' ',' | sed 's/,$//')
mvn verify -P$PROFILES
```

### Specific profile testing

```bash
# Test only core + one cloud provider
mvn verify -Pcore,gc

# Test specific provider
mvn verify -Pazure
```

## Common Profile Patterns in OSDU

| Profile | Purpose | Typical Module Suffix |
|---------|---------|----------------------|
| `core` | Core functionality, no cloud dependencies | `-core`, `-core-plus` |
| `azure` | Azure-specific implementations | `-azure` |
| `gc` / `gcp` | Google Cloud implementations | `-gc`, `-gcp` |
| `aws` | AWS implementations | `-aws` |
| `ibm` | IBM Cloud implementations | `-ibm` |

## Integration with build-runner Agent

The `build-runner` agent automatically detects shared modules and builds with all profiles when:

1. The module name matches shared module patterns
2. The request includes "shared module" in the prompt
3. Profiles are detected in the project's pom.xml

**Example prompts:**

```
# Explicit shared module hint
"Run verify for /path/to/partition-core-plus. This is a shared module."

# Auto-detection (build-runner checks module name)
"Run verify for /path/to/partition-core-plus."
```

## Troubleshooting

### "Symbol not found" in profile-specific module

**Symptom:** Local build passes, CI fails with compilation error in `-azure` or `-gc` module.

**Cause:** Changed shared module code that profile-specific modules depend on.

**Fix:** Build with all profiles locally before pushing:
```bash
mvn verify -Pcore,azure,gc,aws,ibm
```

### Profile not activating

**Symptom:** Expected module not building.

**Check:** Verify profile ID matches exactly:
```bash
grep -A2 "<profile>" pom.xml | grep "<id>"
```

### Missing dependencies in profile module

**Symptom:** Dependency resolution fails for profile-specific module.

**Cause:** Parent POM may have profile-conditional dependencies.

**Fix:** Ensure building from correct directory with profile activated:
```bash
cd project-root && mvn verify -Pazure
```
