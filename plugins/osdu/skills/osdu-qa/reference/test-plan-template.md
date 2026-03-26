# Test Plan Report Template

Generate this report when the user runs `/osdu-qa test` with no arguments. Fill in all `{placeholders}` with real data from the environment status, connectivity check, and test catalog commands.

---

## Output Format

```markdown
# OSDU QA Test Plan — {environment_target}

**Environment:** {host} (`{partition}`)
**Platform:** {platform_type} | **Auth:** {auth_type}
**Report Date:** {date}

---

## 1. Connectivity Status

| Check | Status | Details |
|-------|--------|---------|
| Newman CLI | {OK/FAIL} | {version or error} |
| Repository | {OK/FAIL} | {path or "Not found"} |
| Collections | {OK/FAIL} | {count} collections, {test_count} tests |
| Configuration | {OK/FAIL} | {Complete/Missing: details} |
| Authentication | {OK/FAIL} | {Token valid/expired/error} |

{If any check fails, show a warning box:}
> **Resolve connectivity issues before running tests.** Run `/osdu-qa check` for details.

---

## 2. Coverage & Risk Snapshot

| Metric | Value |
|--------|-------|
| Total Collections | {count} |
| Total Tests | {count} |
| Platform Coverage | {list: Legal, Storage, Search, etc.} |
| DDMS Coverage | {list: Wellbore, Seismic, etc.} |
| Ingestion Coverage | {list: Manifest, CSV, Reference, WITSML} |

### Top Gaps & Recommended Actions

{Analyze the test catalog and identify gaps. Common examples:}

| Gap | Risk | Recommendation |
|-----|------|----------------|
| No Notification service tests | Medium | Manual verification or custom collection |
| No Indexer-specific tests | Low | Covered indirectly by Search tests |
| No Policy service tests | Low | Service may not be deployed |

---

## 3. Service Coverage Matrix

Show what each service tests and its priority tier.

### Core Services (P0 — Run First)

| Service | Collection | Tests | Capabilities Tested |
|---------|------------|-------|---------------------|
| Legal | Legal API | 94 | Tag CRUD, compliance validation, batch operations |
| Entitlements | Entitlements API | 268 | Group CRUD, member management, ACL operations |
| Schema | Schema API | 52 | Schema registration, retrieval, listing |
| Storage | Storage API | 149 | Record CRUD, versioning, batch operations, patches |
| File | File API | 39 | Upload, download, metadata, health checks |
| Search | Search API R3 v2.0 | 119 | Query, cursor, aggregation, geo-spatial |
| Secret | Secret Service | 23 | Secret CRUD, status, authentication |

### Data Management Services (P1)

| Service | Collection | Tests | Capabilities Tested |
|---------|------------|-------|---------------------|
| Unit | Unit API | 332 | Unit conversions, catalog queries |
| CRS Catalog | CRS Catalog API v1.0 | 302 | Coordinate reference system lookups |
| CRS Conversion | CRS Conversion API v1.0 | 41 | Coordinate transforms |
| Dataset | Dataset API | 36 | Dataset registration, retrieval |
| Registration | Registration API | 94 | Subscription management |
| Workflow | Workflow API | 100 | DAG management, workflow runs |

### Ingestion Pipelines (P1)

| Service | Collection | Tests | Capabilities Tested |
|---------|------------|-------|---------------------|
| Manifest Ingestion | Manifest Ingestion | 99 | Master/reference/WPC data ingest |
| CSV Ingestion | CSV Ingestion Workflow | 85 | CSV schema, master, reference workflows |
| Ingestion By Ref | Ingestion By Reference | 69 | External reference ingestion |

### DDMS & Domain Services (P2)

| Service | Collection | Tests | Capabilities Tested |
|---------|------------|-------|---------------------|
| Wellbore DDMS | Wellbore DDMS | 82 | v3 CRUD, about/version |
| Well Delivery | Well Delivery DDMS | 46 | UC1-UC5 use cases |
| Well Data | Well R3 Workflow | 30 | Well ingestion workflows |
| Wellbore Workflow | Wellbore R3 Workflow | 29 | Wellbore ingestion workflows |
| Markers | Markers R3 Workflow | 28 | Wellbore marker workflows |
| WellLog | WellLog R3 | 28 | Well log data workflows |
| WellLog LAS | WellLog LAS Ingest | 36 | LAS file ingestion |
| Trajectory | Trajectory R3 Workflow | 32 | Trajectory data workflows |
| Seismic | Seismic R3 | 59 | Seismic data operations |
| SEGY-ZGY | SEGY-ZGY Conversion | 27 | Format conversion workflows |
| SEGY-OpenVDS | SEGY-OpenVDS Conversion | 28 | OpenVDS conversion workflows |
| WITSML | WITSML Ingestion | 121 | Well/wellbore/log/trajectory/markers/tubular |
| Energyml | Energyml Converter | 24 | EPC/h5/XML parsing and delivery |

---

## 4. CI Execution Guide

Recommended execution phases. Each phase gates the next — stop and investigate failures before proceeding.

### Phase 1: Smoke Test (Pre-flight)

```
/osdu-qa test smoke                    # 153 tests, ~2-3 min
```

Validates: Auth, Legal, Entitlements, Storage, Schema, Search, Unit, CRS, Ingestion.
**Gate:** 100% pass required before proceeding.

### Phase 2: Core Platform (P0)

```
/osdu-qa test p0                       # 7 collections, 745 tests
```

Individual collections if needed:
```
/osdu-qa test legal                    # 94 tests
/osdu-qa test entitlements             # 268 tests
/osdu-qa test schema                   # 52 tests
/osdu-qa test storage                  # 149 tests
/osdu-qa test file                     # 39 tests
/osdu-qa test search                   # 119 tests
/osdu-qa test secret                   # 23 tests
```

**Gate:** All P0 collections must pass for deployment readiness.

### Phase 3: Extended Platform (P1)

```
/osdu-qa test p1                       # 9 collections, 958 tests
```

Individual collections if needed:
```
/osdu-qa test unit                     # 332 tests
/osdu-qa test crs-catalog              # 302 tests
/osdu-qa test crs-conversion           # 41 tests
/osdu-qa test dataset                  # 36 tests
/osdu-qa test registration             # 94 tests
/osdu-qa test workflow                 # 100 tests
/osdu-qa test ingestion                # 99 tests
/osdu-qa test csv-ingestion            # 85 tests
/osdu-qa test ingestion-ref            # 69 tests
```

**Non-blocking** for deployment, but failures indicate functional gaps.

### Phase 4: DDMS & Domain (P2)

```
/osdu-qa test p2                       # 13 collections, 608 tests
```

Domain-specific groups:
```
/osdu-qa test well-all                 # 8 collections — all well services
/osdu-qa test seismic-all              # 3 collections — all seismic services
/osdu-qa test ingestion-all            # 5 collections — all ingestion workflows
```

**Non-blocking** — specialized functionality validation.

---

## 5. Service Test Profiles

Compact view of what each collection validates.

### Core Services

| Collection | Folders | Key Validations |
|------------|---------|-----------------|
| **Smoke** (153) | Auth, Legal, Entitlements, Storage, Schema, Search, Unit, CRS Catalog, CRS Conversion, Manifest Ingestion | End-to-end platform health |
| **Legal** (94) | Configure, Compliance_Legal | Tag CRUD, validation rules, batch ops, error handling |
| **Entitlements** (268) | Configure, Entitlements | Group lifecycle, member ops, ACL management, edge cases |
| **Storage** (149) | Configure, Storage, Patch/Update, ConversionCheck | Record CRUD, versioning, unit/CRS conversion |
| **Schema** (52) | Configure, Schema, List entities | Registration, retrieval, scope filtering |
| **Search** (119) | Configure, Search | Full-text, cursor, aggregation, spatial, sorting |
| **File** (39) | Configure, Health, Functional, Negative | Upload/download, metadata, error handling |
| **Secret** (23) | Auth, Status/Info, Service APIs | Secret CRUD, authentication |

### Data & Ingestion

| Collection | Folders | Key Validations |
|------------|---------|-----------------|
| **Unit** (332) | Configure, Unit | Comprehensive unit conversion catalog |
| **CRS Catalog** (302) | Configure, CRSCatalog | Coordinate reference system lookups |
| **CRS Conversion** (41) | Configure, CRS Conversion | Coordinate transforms |
| **Dataset** (36) | Configure, Functional, Negative | Registration, retrieval, error handling |
| **Registration** (94) | Configure, Registration | Subscription CRUD |
| **Workflow** (100) | Configure, Health, Manager, Run | DAG registration, execution, monitoring |
| **Ingestion** (99) | Configure, Master, Reference, Surrogate Key, WPC, Integrity | Multi-format ingestion pipelines |
| **CSV Ingestion** (85) | Configure, Custom Schema, Master, Reference | CSV workflow variants |
| **Ingestion By Ref** (69) | Configure, Master, Reference, WPC | External reference ingestion |

### DDMS & Domain

| Collection | Folders | Key Validations |
|------------|---------|-----------------|
| **Wellbore DDMS** (82) | Configure, About/Version, v3, Cleanup | Wellbore CRUD via DDMS API |
| **Well Delivery** (46) | Configure, Legal, Schemas, UC1-UC5 | 5 well delivery use cases |
| **WITSML** (121) | Configure, Legal, Well/Wellbore/WellLog/Trajectory/Markers/Tubular | Full WITSML XML ingest |
| **Seismic** (59) | Configure, Seismic | Seismic data operations |
| **SEGY-ZGY** (27) | Token, Legal, File, WPC, DAG, Validate, ZGY, Cleanup | End-to-end conversion |
| **SEGY-OpenVDS** (28) | Configure, Legal, Ingest, Storage, Conversion, Validate, VDS, Cleanup | OpenVDS pipeline |
| **Energyml** (24) | Configure, Upload, Parser, Delivery | EPC/h5 processing |

---

## 6. Quick Start

Based on what you want to validate:

| Goal | Command | Time Estimate |
|------|---------|---------------|
| Quick health check | `/osdu-qa test smoke` | ~2-3 min |
| Deployment readiness | `/osdu-qa test p0` | ~10-15 min |
| Full platform validation | `/osdu-qa test p0` then `/osdu-qa test p1` | ~25-30 min |
| Complete coverage | `/osdu-qa test p0` then `/osdu-qa test p1` then `/osdu-qa test p2` | ~45-60 min |
| Well services only | `/osdu-qa test well-all` | ~10 min |
| Seismic services only | `/osdu-qa test seismic-all` | ~5 min |

### After Testing

```
/qa-report summary                     # Quick status overview
/qa-report detailed                    # Full analysis with RCA
/qa-report slides                      # Full report + PowerPoint
```
```

---

## Notes for Report Generation

- **Always run the data-gathering commands first** (Steps 1 and 2 in test.md) to get real values
- **Fill in all placeholders** — never show `{placeholder}` syntax in output
- **Connectivity section is critical** — if checks fail, highlight that prominently
- **Adapt the gaps section** based on what the test catalog actually contains
- **Time estimates are approximate** — actual times depend on environment performance
