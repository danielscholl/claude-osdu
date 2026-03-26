# OSDU Test Collections Reference

Detailed information about available test collections (30 aliases, 33 collection files, ~2,295 tests).

## Table of Contents

1. [Coverage Summary](#coverage-summary)
2. [Smoke - Pre-flight](#smoke---pre-flight)
3. [P0 - Core Platform](#p0---core-platform) - LEGAL, ENTITLEMENTS, SCHEMA, STORAGE, FILE, SEARCH, SECRET
4. [P1 - Core+](#p1---core) - UNIT, CRS, DATASET, REGISTRATION, WORKFLOW, INGESTION, CSV, INGESTION-REF
5. [P2 - DDMS & Domain](#p2---ddms--domain) - WELLBORE, WELL DELIVERY, WELL DATA, MARKERS, WELLLOG, TRAJECTORY, SEISMIC, SEGY, WITSML, ENERGYML
6. [Priority Tiers](#priority-tiers)
7. [Signal Quality](#signal-quality)

## Coverage Summary

| Tier | Collections | Tests | Risk |
|------|-------------|-------|------|
| Smoke | 1 | 153 | LOW |
| P0 - Core Platform | 7 | 745 | LOW |
| P1 - Core+ | 9 | 958 | LOW-MEDIUM |
| P2 - DDMS & Domain | 13 | 608 | MEDIUM-HIGH |
| **Total** | **30** | **~2,464** | |

## Smoke - Pre-flight

### SMOKE
- **Alias**: `smoke`
- **Tests**: 153
- **Collection**: Core Smoke Test Collection
- **Folder**: `01_CICD_CoreSmokeTest`
- **Signal**: Strong
- **Capabilities**: Health checks, Basic CRUD, Auth flow validation
- **Spans**: Auth, Legal, Entitlements, Storage, Schema, Search, Unit, CRS Catalog, CRS Conversion, Manifest Ingestion
- **Risks Covered**: Service availability, Auth failures, Connectivity

## P0 - Core Platform

Foundation services every OSDU instance must have (7 collections, 745 tests).

### LEGAL
- **Alias**: `legal`
- **Tests**: 94
- **Collection**: Compliance_Legal API CI/CD v2.2
- **Folder**: `11_CICD_Setup_LegalAPI`
- **Signal**: Strong
- **Capabilities**: Legal tag CRUD, Country codes, Expiration handling
- **Risks Covered**: Invalid tags, Unauthorized access, Expired tags
- **Known Gaps**: No bulk operations, No perf testing

### ENTITLEMENTS
- **Alias**: `entitlements`
- **Tests**: 268
- **Collection**: Entitlement API CI/CD v2.0
- **Folder**: `14_CICD_Setup_EntitlementAPI`
- **Signal**: Strong
- **Capabilities**: Group mgmt, Member ops, ACL validation, Cross-partition
- **Risks Covered**: Permission escalation, Invalid groups, Orphaned members
- **Known Gaps**: No stress testing for large group hierarchies

### SCHEMA
- **Alias**: `schema`
- **Tests**: 52
- **Collection**: Schema API CI/CD v1.0
- **Folder**: `25_CICD_Setup_SchemaAPI`
- **Signal**: Medium
- **Capabilities**: Schema registration, Versioning, Search, JSON Schema
- **Risks Covered**: Invalid schemas, Version conflicts
- **Known Gaps**: Limited ACL testing, No schema migration scenarios

### STORAGE
- **Alias**: `storage`
- **Tests**: 149
- **Collection**: Storage API CI/CD v2.0
- **Folder**: `12_CICD_Setup_StorageAPI`
- **Signal**: Strong
- **Capabilities**: Record CRUD, Versioning, Bulk ops, ACL enforcement
- **Risks Covered**: Unauthorized access, Invalid legal tags, Overwrites
- **Known Gaps**: No large-scale perf validation

### FILE
- **Alias**: `file`
- **Tests**: 39
- **Collection**: FileAPI UploadDownload CI/CD v3.0
- **Folder**: `21_CICD_Setup_FileAPI`
- **Signal**: Weak
- **Capabilities**: Signed URL upload/download, Metadata mgmt, Multi-part
- **Risks Covered**: Invalid signed URLs, Metadata corruption
- **Known Gaps**: No ACL tests, No negative scenarios, No large files

### SEARCH
- **Alias**: `search` (v2.0), `search-v1` (v1.0)
- **Tests**: 119 (v2.0), 119 (v1.0)
- **Collection**: Search API R3 CI-CD v2.0
- **Folder**: `37_CICD_R3_SearchAPI` (2 files)
- **Signal**: Strong
- **Capabilities**: Query syntax, Filters, Aggregations, Spatial/temporal
- **Risks Covered**: Query injection, Unauthorized results, Pagination
- **Known Gaps**: No large index perf testing

### SECRET
- **Alias**: `secret`
- **Tests**: 23
- **Collection**: Secret Service V1
- **Folder**: `48_CICD_Setup_SecretService_V1`
- **Signal**: Medium
- **Capabilities**: Authentication, Status & Info, Service APIs
- **Risks Covered**: Secret CRUD, Auth validation
- **Known Gaps**: Limited negative scenarios

## P1 - Core+

Extends core with data services, workflow, and ingestion (9 collections, 958 tests).

### UNIT
- **Alias**: `unit`
- **Tests**: 332
- **Collection**: Unit CI/CD v1.0
- **Folder**: `20_CICD_Setup_UnitAPI`
- **Signal**: Medium
- **Capabilities**: Unit catalog queries, Conversions, Measurement families
- **Risks Covered**: Invalid conversions, Unknown unit symbols
- **Known Gaps**: No auth tests (public API), No negative scenarios

### CRS CATALOG
- **Alias**: `crs-catalog` (v1.0, 302 tests), `crs-catalog-v3` (V3, 9 tests)
- **Tests**: 302 (v1.0) + 9 (V3)
- **Collection**: CRSCatalog API CI/CD v1.0
- **Folder**: `16_CICD_Setup_ CRSCatalogServiceAPI` (2 files)
- **Signal**: Medium
- **Capabilities**: CRS catalog (EPSG), WKT parsing, Coordinate reference lookups
- **Risks Covered**: Invalid EPSG codes, Catalog query failures
- **Known Gaps**: No auth tests (public API), No negative scenarios

### CRS CONVERSION
- **Alias**: `crs-conversion` (v1.0, 41 tests), `crs-conv-v3` (V3, 5 tests)
- **Tests**: 41 (v1.0) + 5 (V3)
- **Collection**: CRS Conversion API CI/CD v1.0
- **Folder**: `18_CICD_Setup_CRSConversionAPI` (2 files)
- **Signal**: Medium
- **Capabilities**: Coordinate transforms, Projection conversions
- **Risks Covered**: Projection errors, Invalid coordinate inputs
- **Known Gaps**: No auth tests (public API), No negative scenarios

### DATASET
- **Alias**: `dataset`
- **Tests**: 36
- **Collection**: Dataset API CI/CD v3.0
- **Folder**: `36_CICD_R3_Dataset`
- **Signal**: Weak
- **Capabilities**: Dataset registration, Retrieval instructions, Storage
- **Risks Covered**: Invalid dataset records, Retrieval failures
- **Known Gaps**: No ACL tests, No negative scenarios, Limited error checks

### REGISTRATION
- **Alias**: `registration`
- **Tests**: 94
- **Collection**: Registration API CI/CD v1.0
- **Folder**: `22_CICD_Setup_RegistrationAPI`
- **Signal**: Medium
- **Capabilities**: Subscription registration, Topic management, Push endpoints
- **Risks Covered**: Invalid registrations, Endpoint failures
- **Known Gaps**: Limited negative scenarios

### WORKFLOW
- **Alias**: `workflow`
- **Tests**: 100
- **Collection**: Workflow_CI-CD_v1.0
- **Folder**: `30_CICD_Setup_WorkflowAPI`
- **Signal**: Strong
- **Capabilities**: DAG triggers, Status queries, Execution history
- **Risks Covered**: Invalid triggers, Status inconsistencies, Auth failures
- **Known Gaps**: No long-running workflow tests, Limited concurrency testing

### INGESTION (Manifest)
- **Alias**: `ingestion`
- **Tests**: 99
- **Collection**: Manifest_Based_Ingestion_Osdu_ingest_CI-CD_v2.0
- **Folder**: `29_CICD_Setup_Ingestion`
- **Signal**: Strong
- **Capabilities**: Manifest submission, DAG triggers, Record verification
- **Risks Covered**: Invalid manifests, Workflow failures, Partial ingestion
- **Known Gaps**: Limited retry scenario testing

### CSV INGESTION
- **Alias**: `csv-ingestion`
- **Tests**: 85
- **Collection**: CSVWorkflow_CI-CD_v2.0
- **Folder**: `31_CICD_Setup_CSVIngestion`
- **Signal**: Strong
- **Capabilities**: CSV upload, Column mapping, Validation, Batch records
- **Risks Covered**: Invalid CSV format, Mapping errors, Validation failures
- **Known Gaps**: No large file handling, Limited encoding tests

### INGESTION BY REFERENCE
- **Alias**: `ingestion-ref`
- **Tests**: 69
- **Collection**: Ingestion By Reference CI-CD v3.0
- **Folder**: `47_CICD_IngestionByReference`
- **Signal**: Medium
- **Capabilities**: External reference ingestion for Master, Reference, and WPC data
- **Risks Covered**: Invalid references, Missing external data
- **Known Gaps**: Limited negative scenarios

## P2 - DDMS & Domain

Domain services built on core platform (13 collections, 608 tests).

### WELLBORE DDMS
- **Alias**: `wellbore-ddms` (also `wellbore` for backward compat)
- **Tests**: 82
- **Collection**: Wellbore DDMS CI/CD v3.0
- **Folder**: `28_CICD_Setup_WellboreDDMSAPI`
- **Signal**: Medium
- **Capabilities**: Well/wellbore records, LAS logs, Markers, Trajectories
- **Risks Covered**: Invalid well data, Trajectory errors, Log parsing
- **Known Gaps**: No smoke tests, Limited negative scenarios, No bulk ops

### WELL DELIVERY DDMS
- **Alias**: `well-delivery`
- **Tests**: 46
- **Collection**: WellDelivery DDMS CI-CD v3.1
- **Folder**: `44_CICD_Well_Delivery_DMS`
- **Signal**: Weak
- **Capabilities**: Activity programs, Drilling reports, Operations tracking (UC1-UC5)
- **Risks Covered**: Invalid activity data, Report generation failures
- **Known Gaps**: No smoke tests, No negative scenarios, Limited auth tests

### WELL DATA WORKFLOW
- **Alias**: `well-data`
- **Tests**: 30
- **Collection**: Well R3 CI/CD v1.0
- **Folder**: `32_CICD_R3_WellDataWorkflow`
- **Signal**: Weak
- **Capabilities**: Well record R3 workflow, DAG-based well data processing
- **Risks Covered**: Workflow execution failures, Invalid well records
- **Known Gaps**: Limited coverage, No negative scenarios

### WELLBORE R3 WORKFLOW
- **Alias**: `wellbore-wf`
- **Tests**: 29
- **Collection**: Wellbore R3 CI/CD v1.0
- **Folder**: `33_CICD_R3_WellboreWorkflow`
- **Signal**: Weak
- **Capabilities**: Wellbore R3 workflow, DAG-based wellbore processing
- **Risks Covered**: Workflow execution failures, Invalid wellbore records
- **Known Gaps**: Limited coverage, No negative scenarios

### MARKERS R3 WORKFLOW
- **Alias**: `markers`
- **Tests**: 28
- **Collection**: WellboreMarker R3 CI/CD v1.0
- **Folder**: `34_CICD_R3_MarkersWorkflow`
- **Signal**: Weak
- **Capabilities**: Wellbore marker R3 workflow, DAG-based marker processing
- **Risks Covered**: Workflow execution failures, Invalid marker data
- **Known Gaps**: Limited coverage, No negative scenarios

### WELLLOG R3
- **Alias**: `welllog` (R3, 28 tests), `welllog-las` (LAS ingest, 36 tests)
- **Tests**: 28 (R3) + 36 (LAS)
- **Collection**: WellLog R3 CI/CD v1.0
- **Folder**: `35_CICD_R3_WellLogWorkflow` (2 files)
- **Signal**: Weak
- **Capabilities**: WellLog R3 workflow, LAS file ingestion
- **Risks Covered**: Log parsing failures, Invalid LAS format
- **Known Gaps**: Limited coverage, No negative scenarios

### TRAJECTORY R3 WORKFLOW
- **Alias**: `trajectory`
- **Tests**: 32
- **Collection**: Trajectory R3 CI/CD v1.0
- **Folder**: `38_CICD_R3_TrajectoryWorkflow`
- **Signal**: Weak
- **Capabilities**: Trajectory R3 workflow, DAG-based trajectory processing
- **Risks Covered**: Workflow execution failures, Invalid trajectory data
- **Known Gaps**: Limited coverage, No negative scenarios

### SEISMIC R3
- **Alias**: `seismic`
- **Tests**: 59
- **Collection**: Seismic R3 CI/CD v1.0
- **Folder**: `39_CICD_R3_Seismic`
- **Signal**: Medium
- **Capabilities**: Seismic metadata, Store operations, SeisStore integration
- **Risks Covered**: Invalid seismic data, Storage failures
- **Known Gaps**: No smoke tests, Limited format coverage

### SEGY-ZGY CONVERSION
- **Alias**: `segy-zgy`
- **Tests**: 27
- **Collection**: SegyToZgyConversion Workflow using SeisStore R3 CI-CD v1.0
- **Folder**: `42_CICD_SEGY_ZGY_Conversion`
- **Signal**: Weak
- **Capabilities**: SEGY to ZGY conversion workflow, File collection, DAG process
- **Risks Covered**: Conversion failures, Invalid SEGY format
- **Known Gaps**: No negative scenarios, Limited format coverage

### SEGY-OPENVDS CONVERSION
- **Alias**: `segy-openvds`
- **Tests**: 28
- **Collection**: SegyToOpenVDS conversion using Seisstore CI-CD v1.0
- **Folder**: `46_CICD_SEGY_OpenVDS_Conversion_ManualStorageRecordsCreation`
- **Signal**: Weak
- **Capabilities**: SEGY to OpenVDS conversion, Manual storage record creation
- **Risks Covered**: Conversion failures, Storage record issues
- **Known Gaps**: No negative scenarios, Limited format coverage

### WITSML INGESTION
- **Alias**: `witsml`
- **Tests**: 121
- **Collection**: WITSML Energistics XML Ingest CI-CD v3.0
- **Folder**: `41_CICD_Setup_WITSMLIngestion`
- **Signal**: Medium
- **Capabilities**: WITSML XML parsing, Well/wellbore/welllog/trajectory/markers/tubular extraction
- **Risks Covered**: Invalid XML, Schema mismatches, Incomplete data
- **Known Gaps**: Limited WITSML 2.0 coverage, No streaming scenarios

### ENERGYML CONVERTER
- **Alias**: `energyml`
- **Tests**: 24
- **Collection**: EnergisticsParser
- **Folder**: `49_CICD_EnergymlConverter_And_Delivery`
- **Signal**: Weak
- **Capabilities**: EPC+h5/XML upload, Energyml parsing, Energistics delivery
- **Risks Covered**: Invalid EPC format, Parser failures
- **Known Gaps**: Limited format coverage, No negative scenarios

## Priority Tiers

- **Smoke**: Cross-layer integration check. Always run first.
- **P0**: Core platform, must pass for deployment
- **P1**: Core+ services, should pass for release
- **P2**: DDMS & domain services, extended coverage

## Signal Quality

- **Strong**: Asserts body/schema + negative tests + auth/ACL coverage
- **Medium**: Asserts status + some functional checks, partial neg/ACL
- **Weak**: Mostly happy-path status checks, missing neg/ACL tests
