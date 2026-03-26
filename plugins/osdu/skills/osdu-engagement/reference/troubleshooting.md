# OSDU Engagement — Troubleshooting

For common issues (authentication, installation, output, rate limiting), see the
[shared CLI reference](../../../reference/osdu-cli-reference.md).

This file covers **engagement-specific** issues only.

---

## No Contributors Found

**Symptom:** `No contributions found in the specified period`

**Cause:** Time period too short, or project had no activity in the window.

**Fix:** Expand the time range (`--days 90` or `--days 180`) and remove the project filter
to confirm data exists across the platform.

---

## Contribution Counts Seem Low

**Symptom:** Numbers don't match expectations.

**Cause:** The CLI counts merged MRs. Open MRs (not yet merged) aren't included in
contribution totals.

**Fix:** Verify the time period covers expected activity. Check if MRs are still open
(use `osdu-activity mr` to see open MRs). Compare with GitLab web interface.

---

## Missing Contributors

**Symptom:** Known contributors don't appear in results.

**Causes:** No activity in the analyzed time period, activity in a different project, or
contributor uses a different GitLab account.

**Fix:** Expand time range (`--days 180`), remove the project filter, and verify the
contributor's GitLab username.

---

## No ADRs Found

**Symptom:** `osdu-engagement decision` returns empty results.

**Causes:** Project doesn't use ADR issues, ADRs are labeled differently, or filter too
restrictive.

**Fix:** Try without filters first (`osdu-engagement decision --output markdown`), then
narrow. Check for recent ADR activity with `--days 90`. Verify ADR labeling in GitLab.

---

## ADR Status Not Updating

**Symptom:** ADR shows stale status.

**Cause:** Status reflects labels/state in GitLab. The CLI mirrors what's in GitLab — it
doesn't cache independently.

**Fix:** Verify the ADR's status in the GitLab web interface.

---

## Getting Help

```bash
osdu-engagement --help
osdu-engagement contribution --help
osdu-engagement decision --help
```

Report issues: https://community.opengroup.org/osdu/ui/ai-devops-agent/osdu-engagement/-/issues
