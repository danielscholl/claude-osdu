# OSDU ${CATEGORY} Services QA Report
## ${ENVIRONMENT} Environment

| Field | Value |
|-------|-------|
| **Environment** | ${ENVIRONMENT} |
| **Test Date** | ${DATE} |
| **Category** | ${CATEGORY} |

---

## Executive Summary

| Metric | Value |
|--------|-------|
| **Category Status** | ${STATUS} |
| **Services Tested** | ${TOTAL_SERVICES} |
| **Services Passed** | ${PASSED_SERVICES} (${PASS_RATE}%) |
| **Services Failed** | ${FAILED_SERVICES} |
| **Total Assertions** | ${TOTAL_ASSERTIONS} |
| **Assertions Passed** | ${PASSED_ASSERTIONS} |

---

## Service Results

${SERVICE_DETAILS}

---

## Summary by Service

| Service | Requests | Assertions | Pass Rate | Status |
|---------|----------|------------|-----------|--------|
${SUMMARY_TABLE}

---

## Recommendations

${RECOMMENDATIONS}

---

**Report Generated:** ${GENERATED_AT}
**Category:** ${CATEGORY}
