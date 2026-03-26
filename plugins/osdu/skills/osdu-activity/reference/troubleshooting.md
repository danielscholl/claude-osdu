# OSDU Activity — Troubleshooting

For common issues (authentication, installation, output, rate limiting), see the
[shared CLI reference](../../../reference/osdu-cli-reference.md).

This file covers **activity-specific** issues only.

---

## No MRs Found

**Symptom:** `No open merge requests found`

**Causes:** Project has no open MRs (healthy state), or only draft MRs exist (excluded by
default).

**Fix:** Include drafts with `--include-draft`. If still empty, the project may genuinely
have no open MRs — this is not an error.

---

## Failed Jobs Not Showing

**Symptom:** Know there are failures but the output doesn't show them.

**Cause:** Default table style shows summary counts, not individual job details.

**Fix:** Use list style with job details:
```bash
osdu-activity mr --style list --show-jobs --output markdown
```

---

## Missing Pipeline Status on MRs

**Symptom:** MRs show no pipeline status.

**Causes:** Pipeline hasn't started yet, MR was just created, or CI isn't configured for
that branch.

**Fix:** Check pipeline directly with `osdu-activity pipeline --project <name> --output markdown`.
Verify in GitLab web interface.

---

## Provider Filter Not Working as Expected

**Symptom:** Getting results from all providers despite using `--provider`.

**Cause:** Provider filter applies to **job names** within pipelines. Not all projects have
provider-specific jobs. For MRs, it filters the pipeline jobs associated with the MR, not
the MR itself.

**Fix:** Provider filtering works best with `osdu-activity pipeline` and `osdu-quality analyze`.
For MRs, use it to see which provider's jobs are failing, not to filter MRs by provider.

---

## No ADR Issues Found

**Symptom:** `osdu-activity issue --adr` returns empty results.

**Cause:** ADR issues are identified by labels or title patterns. Not all projects use them.

**Fix:** List all issues first (`osdu-activity issue --project <name> --style list --output markdown`)
and look for ADR-related titles or labels.

---

## Getting Help

```bash
osdu-activity --help
osdu-activity mr --help
osdu-activity pipeline --help
osdu-activity issue --help
```

Report issues: https://community.opengroup.org/osdu/ui/ai-devops-agent/osdu-activity/-/issues
