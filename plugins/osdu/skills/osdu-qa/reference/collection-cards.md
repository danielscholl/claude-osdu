# Collection Cards Reference

Standardized test card data for all OSDU QA collections. Used by `/qa-report` command.

---

## Gate Tier (P0) - Must Pass for Deployment

### SMOKE - Core Smoke Test Collection

| Field | Value |
|-------|-------|
| **ID** | `01_CICD_CoreSmokeTest` |
| **Version** | v1.0 |
| **Tier** | Gate (P0) |
| **Tests / Requests** | 153 / 75 |
| **Signal** | 🟢 Strong |
| **Stability** | Stable |

**Purpose:** Validates service availability, authentication flow, and basic CRUD operations across all core services.

**Dependencies:**
- Seed Data: None (creates own test data)
- Shared Environment: No
- Cleanup Required: Yes (self-cleaning)
- Service Dependencies: All core services

**Pass Criteria:**
- All endpoints return expected HTTP status
- Auth token acquisition succeeds
- Basic CRUD operations complete

**Test Folders:**

| Folder | Intent | Critical Cases |
|--------|--------|----------------|
| Auth | Token validation | Get token, Validate token, Refresh token |
| Legal | Legal tag basics | Create tag, Get tag, List tags |
| Entitlements | Permission basics | Get my groups, Validate membership |
| Storage | Record basics | Create record, Get record, Query by kind |
| Schema | Schema availability | Get schema, List schemas |
| Search | Query basics | Simple query, Filter query |
| Unit | Unit service | Get catalog, Convert units |
| CRS Catalog | CRS availability | Get CRS, EPSG lookup |
| CRS Conversion | Transforms | Point conversion |
| Manifest Ingestion | Ingestion basics | Submit manifest, Check status |

**Risks Covered:**
- Service availability
- Authentication failures
- Basic connectivity
- Core CRUD operations

**Known Gaps:**
- Breadth over depth (other Gate suites provide depth)
- No negative test coverage
- No performance validation

**Failure Triage:**

| Pattern | Cause | Look At |
|---------|-------|---------|
| Auth folder fails | Token issue | Token refresh, auth config |
| All folders fail | Service down | Health endpoints, connectivity |
| Single folder fails | Service-specific issue | That service's logs |

---

### LEGAL - Compliance Legal API

| Field | Value |
|-------|-------|
| **ID** | `11_CICD_Setup_LegalAPI` |
| **Version** | v2.2 |
| **Tier** | Gate (P0) |
| **Tests / Requests** | 94 / 45 |
| **Signal** | 🟢 Strong |
| **Stability** | Stable |

**Purpose:** Validates legal tag lifecycle, compliance validation, and authorization enforcement.

**Dependencies:**
- Seed Data: None
- Shared Environment: No
- Cleanup Required: Yes
- Service Dependencies: Legal Service, Entitlements

**Pass Criteria:**
- CRUD operations succeed with correct responses
- Validation rejects invalid inputs
- Authorization denies unauthorized access
- Expiration handling works correctly

**Test Folders:**

| Folder | Intent | Critical Cases |
|--------|--------|----------------|
| Configure collection | Setup | Env validation, Auth setup |
| Compliance_Legal | Full coverage | Create/Get/Update/Delete tags, Validation, Expiration, Country codes, Auth checks |

**Risks Covered:**
- Invalid legal tag rejection
- Unauthorized access prevention
- Expired tag handling
- Country code validation
- Export classification compliance

**Known Gaps:**
- No bulk operations testing
- No performance/load testing

**Failure Triage:**

| Pattern | Cause | Look At |
|---------|-------|---------|
| Create fails 400 | Invalid payload | Request body, required fields |
| All 401 | Token issue | Auth config |
| All 403 | Permission issue | Entitlements groups |

---

### STORAGE - Storage API

| Field | Value |
|-------|-------|
| **ID** | `12_CICD_Setup_StorageAPI` |
| **Version** | v2.0 |
| **Tier** | Gate (P0) |
| **Tests / Requests** | 149 / 68 |
| **Signal** | 🟢 Strong |
| **Stability** | Stable |

**Purpose:** Validates record lifecycle, versioning, ACL enforcement, and data integrity.

**Dependencies:**
- Seed Data: Requires valid legal tags
- Shared Environment: No
- Cleanup Required: Yes
- Service Dependencies: Storage, Legal, Entitlements, Schema

**Pass Criteria:**
- Record CRUD with proper versioning
- ACL enforcement (viewer vs owner)
- Legal tag validation on create/update
- Bulk operations succeed

**Test Folders:**

| Folder | Intent | Critical Cases |
|--------|--------|----------------|
| Configure collection | Setup | Env validation |
| Storage | Core operations | Create, Get, Update, Delete, Query, Bulk ops, Version history |
| Check Patch/Update | PATCH validation | Partial updates, Field-level changes |
| ConversionCheckForUnitsAndCRS | Data transforms | Unit conversion in records, CRS conversion |

**Risks Covered:**
- Unauthorized access prevention
- Invalid legal tag rejection
- Overwrite protection via versioning
- ACL enforcement
- Data integrity

**Known Gaps:**
- No large-scale performance validation
- No concurrent write testing

**Failure Triage:**

| Pattern | Cause | Look At |
|---------|-------|---------|
| Create 400 | Invalid record | Kind, legal tags, ACL format |
| Create 403 | No write permission | Owner groups |
| Get 404 | Record doesn't exist | Record ID, partition |

---

### ENTITLEMENTS - Entitlement API

| Field | Value |
|-------|-------|
| **ID** | `14_CICD_Setup_EntitlementAPI` |
| **Version** | v2.0 |
| **Tier** | Gate (P0) |
| **Tests / Requests** | 268 / 113 |
| **Signal** | 🟢 Strong |
| **Stability** | Stable |

**Purpose:** Validates group management, member operations, role assignment, and cross-partition isolation.

**Dependencies:**
- Seed Data: None
- Shared Environment: No (creates test groups)
- Cleanup Required: Yes
- Service Dependencies: Entitlements

**Pass Criteria:**
- Group CRUD succeeds
- Member add/remove works
- Role assignment enforced
- Cross-partition access blocked

**Test Folders:**

| Folder | Intent | Critical Cases |
|--------|--------|----------------|
| Configure collection | Setup | Env validation |
| Entitlements | Full coverage | Group CRUD, Member ops, Role validation, My groups, Cross-partition, Hierarchy |

**Risks Covered:**
- Permission escalation prevention
- Invalid group rejection
- Orphaned member handling
- Cross-partition isolation
- Role-based access control

**Known Gaps:**
- No stress testing for large group hierarchies
- No concurrent modification testing

**Failure Triage:**

| Pattern | Cause | Look At |
|---------|-------|---------|
| Create 409 | Duplicate group | Group email already exists |
| Add member 403 | Not owner | Check group ownership |
| Cross-partition 404 | Isolation working | Expected behavior |

---

## Release Tier (P1) - Should Pass for Release

### SCHEMA - Schema API

| Field | Value |
|-------|-------|
| **ID** | `25_CICD_Setup_SchemaAPI` |
| **Version** | v1.0 |
| **Tier** | Release (P1) |
| **Tests / Requests** | 52 / 27 |
| **Signal** | 🟡 Medium |
| **Stability** | Stable |

**Purpose:** Validates schema registration, versioning, and discovery.

**Dependencies:**
- Seed Data: None
- Shared Environment: No
- Cleanup Required: Yes
- Service Dependencies: Schema

**Risks Covered:**
- Invalid schema rejection
- Version conflict handling

**Known Gaps:**
- Limited ACL testing
- No schema migration scenarios
- No bulk registration

---

### SEARCH - Search API R3

| Field | Value |
|-------|-------|
| **ID** | `37_CICD_R3_SearchAPI` |
| **Version** | v2.0 |
| **Tier** | Release (P1) |
| **Tests / Requests** | 119 / 56 |
| **Signal** | 🟢 Strong |
| **Stability** | Stable |

**Purpose:** Validates query syntax, filters, aggregations, spatial/temporal queries, and authorization.

**Dependencies:**
- Seed Data: Requires indexed records
- Shared Environment: Yes (uses indexed data)
- Cleanup Required: No (read-only)
- Service Dependencies: Search, Indexer, Storage

**Risks Covered:**
- Query injection prevention
- Unauthorized result filtering
- Pagination correctness
- Complex query support

**Known Gaps:**
- No large index performance testing
- No concurrent query testing

---

### FILE - File API

| Field | Value |
|-------|-------|
| **ID** | `21_CICD_Setup_FileAPI` |
| **Version** | v3.0 |
| **Tier** | Release (P1) |
| **Tests / Requests** | 39 / 24 |
| **Signal** | 🔴 Weak |
| **Stability** | Intermittent |

**Purpose:** Validates signed URL generation, file upload/download, and metadata management.

**Dependencies:**
- Seed Data: None
- Shared Environment: No
- Cleanup Required: Yes
- Service Dependencies: File, Storage

**Risks Covered:**
- Invalid signed URL handling
- Metadata corruption prevention

**Known Gaps:**
- **No ACL tests** - Critical gap
- **No large file handling** - Critical gap
- Limited negative scenarios
- No multi-part upload stress testing

**Weak Signal Reason:** Mostly happy-path tests, missing security (ACL) and scale (large file) coverage.

**Action Needed:** Add ACL enforcement tests, large file tests, comprehensive negative scenarios.

---

### DATASET - Dataset API

| Field | Value |
|-------|-------|
| **ID** | `36_CICD_R3_Dataset` |
| **Version** | v3.0 |
| **Tier** | Release (P1) |
| **Tests / Requests** | 36 / 18 |
| **Signal** | 🔴 Weak |
| **Stability** | Intermittent |

**Purpose:** Validates dataset registration, storage instructions, and retrieval instructions.

**Dependencies:**
- Seed Data: Requires legal tags
- Shared Environment: No
- Cleanup Required: Yes
- Service Dependencies: Dataset, Storage, File

**Risks Covered:**
- Invalid dataset rejection
- Retrieval instruction generation

**Known Gaps:**
- **No ACL tests** - Critical gap
- Limited error handling tests
- No large dataset testing

**Weak Signal Reason:** Missing authorization testing, limited negative coverage.

**Action Needed:** Add ACL tests, comprehensive error scenarios, performance tests.

---

### WORKFLOW - Workflow API

| Field | Value |
|-------|-------|
| **ID** | `30_CICD_Setup_WorkflowAPI` |
| **Version** | v1.0 |
| **Tier** | Release (P1) |
| **Tests / Requests** | 100 / 53 |
| **Signal** | 🟢 Strong |
| **Stability** | Stable |

**Purpose:** Validates workflow definition, execution, status tracking, and history.

**Dependencies:**
- Seed Data: None
- Shared Environment: No
- Cleanup Required: Yes
- Service Dependencies: Workflow, Airflow

**Risks Covered:**
- Invalid trigger rejection
- Status inconsistency detection
- Auth failure handling

**Known Gaps:**
- No long-running workflow tests
- Limited concurrency testing

---

### INGESTION - Manifest Based Ingestion

| Field | Value |
|-------|-------|
| **ID** | `29_CICD_Setup_Ingestion` |
| **Version** | v2.0 |
| **Tier** | Release (P1) |
| **Tests / Requests** | 99 / 57 |
| **Signal** | 🟢 Strong |
| **Stability** | Stable |

**Purpose:** Validates manifest submission, workflow execution, and record verification.

**Dependencies:**
- Seed Data: Reference data, legal tags
- Shared Environment: Yes
- Cleanup Required: Yes
- Service Dependencies: Ingestion, Workflow, Storage, Schema

**Risks Covered:**
- Invalid manifest rejection
- Workflow failure handling
- Partial ingestion detection
- Reference data validation

**Known Gaps:**
- Limited retry scenario testing
- No large manifest testing

---

## Regression Tier (P2) - Increases Confidence

### UNIT - Unit API

| Field | Value |
|-------|-------|
| **ID** | `20_CICD_Setup_UnitAPI` |
| **Version** | v1.0 |
| **Tier** | Regression (P2) |
| **Tests / Requests** | 332 / 167 |
| **Signal** | 🟡 Medium |
| **Stability** | Stable |

**Purpose:** Validates unit catalog queries and unit conversions.

**Note:** Public API - no authentication required for most endpoints.

**Known Gaps:**
- No auth tests (public API)
- No negative scenarios

---

### CRS - CRS Catalog & Conversion

| Field | Value |
|-------|-------|
| **ID** | `16_CICD_Setup_CRSCatalogServiceAPI` + `18_CICD_Setup_CRSConversionAPI` |
| **Tier** | Regression (P2) |
| **Tests / Requests** | 357 / 189 |
| **Signal** | 🟡 Medium |
| **Stability** | Stable |

**Purpose:** Validates CRS catalog (EPSG codes) and coordinate transformations.

**Note:** Public API - no authentication required for most endpoints.

**Known Gaps:**
- No auth tests (public API)
- No negative scenarios

---

### CSV INGESTION - CSV Workflow

| Field | Value |
|-------|-------|
| **ID** | `31_CICD_Setup_CSVIngestion` |
| **Version** | v2.0 |
| **Tier** | Regression (P2) |
| **Tests / Requests** | 85 / 37 |
| **Signal** | 🟢 Strong |
| **Stability** | Stable |

**Known Gaps:**
- No large file handling
- Limited encoding tests

---

### WITSML INGESTION

| Field | Value |
|-------|-------|
| **ID** | `41_CICD_Setup_WITSMLIngestion` |
| **Version** | v3.0 |
| **Tier** | Regression (P2) |
| **Tests / Requests** | 121 / 45 |
| **Signal** | 🟡 Medium |
| **Stability** | Intermittent |

**Known Gaps:**
- Limited WITSML 2.0 coverage
- No streaming scenarios

---

### WELLBORE DDMS

| Field | Value |
|-------|-------|
| **ID** | `28_CICD_Setup_WellboreDDMSAPI` |
| **Version** | v3.0 |
| **Tier** | Regression (P2) |
| **Tests / Requests** | 82 / 37 |
| **Signal** | 🟡 Medium |
| **Stability** | Stable |

**Known Gaps:**
- No smoke tests
- Limited negative scenarios
- No bulk operations

---

## Extended Tier (P3) - Domain Specific

### WELL DELIVERY DDMS

| Field | Value |
|-------|-------|
| **ID** | `44_CICD_Well_Delivery_DMS` |
| **Version** | v3.1 |
| **Tier** | Extended (P3) |
| **Tests / Requests** | 46 / 37 |
| **Signal** | 🔴 Weak |
| **Stability** | Intermittent |

**Weak Signal Reason:** No smoke tests, no negative scenarios, limited auth tests.

---

### SEISMIC

| Field | Value |
|-------|-------|
| **ID** | `39_CICD_R3_Seismic` + conversion collections |
| **Tier** | Extended (P3) |
| **Tests / Requests** | 114 / 66 |
| **Signal** | 🟡 Medium |
| **Stability** | Intermittent |

**Known Gaps:**
- No smoke tests
- Limited format coverage
- No large file testing
