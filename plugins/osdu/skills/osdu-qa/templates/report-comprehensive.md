# OSDU QA Comprehensive Test Report
## ${ENVIRONMENT} Environment

| Field | Value |
|-------|-------|
| **Environment** | ${ENVIRONMENT} |
| **Host** | ${HOST} |
| **Partition** | ${PARTITION} |
| **Test Date** | ${DATE} |
| **Platform Version** | ${VERSION} |
| **Authentication** | ${AUTH_TYPE} |

---

## Executive Summary

| Metric | Value |
|--------|-------|
| **Overall Status** | ${STATUS} |
| **Collections Tested** | ${TOTAL_COLLECTIONS} |
| **Collections Passed** | ${PASSED_COLLECTIONS} (${PASS_RATE}%) |
| **Collections Failed** | ${FAILED_COLLECTIONS} |
| **Total Assertions** | ${TOTAL_ASSERTIONS} |
| **Assertions Passed** | ${PASSED_ASSERTIONS} (${ASSERTION_RATE}%) |

### Key Findings

1. ${FINDING_1}
2. ${FINDING_2}
3. ${FINDING_3}

### Recommendation

${RECOMMENDATION}

---

## Results by Category

### Core Services

| Service | Status | Assertions | Pass Rate |
|---------|--------|------------|-----------|
${CORE_SERVICES_TABLE}

### Data Management Services

| Service | Status | Assertions | Pass Rate |
|---------|--------|------------|-----------|
${DATA_SERVICES_TABLE}

### Workflow & Ingestion Services

| Service | Status | Assertions | Pass Rate |
|---------|--------|------------|-----------|
${WORKFLOW_SERVICES_TABLE}

### Well R3 Workflows

| Service | Status | Assertions | Pass Rate |
|---------|--------|------------|-----------|
${WELL_SERVICES_TABLE}

### DDMS Services

| Service | Status | Assertions | Pass Rate |
|---------|--------|------------|-----------|
${DDMS_SERVICES_TABLE}

---

## Failures

${FAILURES_SECTION}

---

## Issue Classification

### Critical (P0)

${P0_ISSUES}

### High Priority (P1)

${P1_ISSUES}

### Medium Priority (P2)

${P2_ISSUES}

---

## Recommendations

### Immediate Actions

${IMMEDIATE_ACTIONS}

### Short-term Actions

${SHORT_TERM_ACTIONS}

### Medium-term Actions

${MEDIUM_TERM_ACTIONS}

---

## Appendix: Full Results Matrix

${FULL_RESULTS_TABLE}

---

**Report Generated:** ${GENERATED_AT}
**QA Team:** OSDU Azure QA
