# OSDU Quality — Troubleshooting

For common issues (authentication, installation, output, rate limiting), see the
[shared CLI reference](../../../reference/osdu-cli-reference.md).

This file covers **quality-specific** issues only.

---

## No Pipelines Found

**Symptom:** `Warning: No pipelines found for project X`

**Causes:** Project has no recent pipeline activity, or filters are too restrictive.

**Fix:** Remove `--provider`/`--stage` filters and try again, or increase `--pipelines 50`.
Verify the project has pipelines: `glab api "projects/osdu%2Fplatform%2Fsystem%2Fpartition/pipelines?per_page=5"`

---

## Inconsistent Pass Rates

**Symptom:** Pass rates vary significantly between analysis runs.

**Causes:** Flaky tests, pipeline timing variations, or provider-specific infrastructure issues.

**Fix:** Increase sample size (`--pipelines 30`) to smooth out variance. Compare providers
to isolate whether flakiness is environment-specific:

```bash
osdu-quality analyze --project partition --provider azure --output markdown
osdu-quality analyze --project partition --provider aws --output markdown
```

---

## Missing Test Results for a Stage

**Symptom:** Some stages (unit/integration/acceptance) show no data.

**Cause:** Not all projects run all test stages. Some only have unit tests. Some providers
skip certain stages.

**Fix:** Check what stages exist with `osdu-quality status --project <name> --output markdown`.
This is expected behavior — not all projects have acceptance tests.

---

## Getting Help

```bash
osdu-quality --help
osdu-quality analyze --help
osdu-quality status --help
osdu-quality tests --help
```

Report issues: https://community.opengroup.org/osdu/ui/ai-devops-agent/osdu-quality/-/issues
