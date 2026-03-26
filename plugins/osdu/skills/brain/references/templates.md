# Template Field Reference

> **Part of:** [brain skill](../SKILL.md)
> **Purpose:** Complete frontmatter schemas and field guidance for each vault template

---

## Table of Contents

1. [Daily Note](#daily-note)
2. [Report Note](#report-note)
3. [QA Report](#qa-report)
4. [Dependency Report](#dependency-report)
5. [Incident Report](#incident-report)
6. [Decision Record](#decision-record)
7. [Decision (Lightweight)](#decision-lightweight)
8. [Architecture Note](#architecture-note)
9. [Meeting Note](#meeting-note)
10. [Goal](#goal)
11. [Frontmatter Conventions](#frontmatter-conventions)

---

## Daily Note

**Template:** `templates/daily-note.md`
**Destination:** `00-inbox/YYYY-MM-DD.md`

### Frontmatter

```yaml
---
date: 2026-03-05
type: daily
tags: [daily, briefing]
---
```

### Structure

The daily note has these sections, each using Obsidian callout syntax:

1. **Quote block** — Rotate between inspirational quotes, jokes, or fun facts
2. **Per-project MR sections** — One section per project in `02-projects/`, each containing:
   - `[!danger]` — Your MRs (where the user is author, assignee, or reviewer)
   - `[!example]` — Recent MRs from the last 14 days
   - `[!warning]` — Tasks and action items
3. **Goals** — `[!abstract]` callout with quarterly progress table
4. **Delegation** — `[!tip]` callout listing work to assign to AI agents
5. **Notes** — Freeform section for the day

### MR Table Format

```markdown
| MR | Service | Role | Pipeline | Age |
|----|---------|------|----------|-----|
| [!123](https://gitlab.example.com/group/repo/-/merge_requests/123) | storage-service | Author | pass | 3d |
```

Pipeline status values: `pass`, `fail`, `running`, `pending`, `skipped`
Role values: `Author`, `Reviewer`, `Assignee`

---

## Report Note

**Template:** `templates/report-note.md`
**Destination:** `04-reports/YYYY-MM-DD-slug.md`

### Frontmatter

```yaml
---
created: 2026-03-05
type: report
tags: [report/general, topic-tag]
---
```

### Structure

Generic three-section report: Summary, Details, References. Use this when no specialized
template (QA, dependency, incident) fits.

---

## QA Report

**Template:** `templates/qa-report.md`
**Destination:** `04-reports/YYYY-MM-DD-service-qa.md`

### Frontmatter

```yaml
---
type: qa-report
environment: dev | staging | production
date: 2026-03-05
pass_rate: 94.5
total_tests: 200
passed: 189
failed: 11
status: draft | reviewed | final
tags: [report/qa, storage-service]
---
```

All numeric fields (`pass_rate`, `total_tests`, `passed`, `failed`) should be actual
numbers, not strings. These power Dataview queries for trend analysis.

### Structure

1. **Executive Summary** — Table with Total/Passed/Failed/Rate
2. **Environment Status** — Cross-environment comparison table
3. **Test Results by Category** — Breakdown by test suite or category
4. **Failures** — One subsection per failure with Test, Error, Root Cause fields
5. **Recommendations** — Numbered action items
6. **References** — Links to pipeline runs, related incidents

---

## Dependency Report

**Template:** `templates/dependency-report.md`
**Destination:** `04-reports/YYYY-MM-DD-service-dependencies.md`

### Frontmatter

```yaml
---
type: dependency-report
service: storage-service
version: 1.2.3
generated: 2026-03-05
risk_level: critical | high | medium | low
cve_critical: 0
cve_high: 2
cve_medium: 5
cve_low: 12
status: draft | reviewed | remediated
tags: [report/dependency, storage-service]
---
```

CVE counts must be integers. `risk_level` is the overall assessment, not the highest
individual CVE — a single medium CVE in a critical path is high risk.

### Structure

1. **Summary** — Brief overview of dependency health
2. **Critical Vulnerabilities** — Table or detailed entries for critical CVEs
3. **High Vulnerabilities** — Same format for high-severity
4. **Remediation Plan** — Ordered steps with version bump targets
5. **References** — Links to CVE databases, upstream advisories

### Spring Boot / Maven Specific

When reporting on Spring Boot services, include:

```markdown
## Dependency Tree

| Group ID | Artifact ID | Current | Target | CVE |
|----------|-------------|---------|--------|-----|
| org.springframework.boot | spring-boot-starter-web | 3.1.5 | 3.2.3 | CVE-2024-XXXX |
```

Link parent POM changes that cascade across multiple services.

---

## Incident Report

**Template:** `templates/incident-report.md`
**Destination:** `04-reports/YYYY-MM-DD-incident-slug.md`

### Frontmatter

```yaml
---
type: incident
service: storage-service
severity: critical | high | medium | low
status: investigating | mitigated | resolved | post-mortem
date: 2026-03-05
pipeline: https://gitlab.example.com/...
resolved_date: 2026-03-06
tags: [incident, service-name]
---
```

### Structure

1. **Summary** — One paragraph describing the incident
2. **Timeline** — Chronological entries (Detected, Acknowledged, Resolved) with timestamps
3. **Impact** — What broke, who was affected, blast radius
4. **Root Cause** — Technical explanation of why it happened
5. **Resolution** — What was done to fix it
6. **Action Items** — Checklist of follow-up tasks
7. **Lessons Learned** — What to change to prevent recurrence

### Linking to Infrastructure Debugging

When an incident comes from an infrastructure debugging session, link to the relevant
evidence and reference the debugging methodology:

```markdown
## Root Cause

Investigation followed [[iac-debug]] methodology.

Evidence gathered:
- Terraform plan output showed drift in [[storage-service]] NSG rules
- `kubectl get constraints` revealed 3 safeguard violations
```

---

## Decision Record

**Template:** `templates/decision-record.md`
**Destination:** `03-knowledge/adr-NNN-slug.md`

### Frontmatter

```yaml
---
type: adr
status: proposed | accepted | deprecated | superseded
date: 2026-03-05
deciders: [person-a, person-b]
tags: [adr, decision/architecture]
---
```

### Structure

1. **Status** — Current status (matches frontmatter)
2. **Context** — Why this decision is needed
3. **Decision** — What was decided
4. **Consequences** — Positive, Negative, Risks subsections
5. **Alternatives Considered** — What else was evaluated
6. **References** — Supporting links

Number ADRs sequentially: `adr-001-`, `adr-002-`, etc.

---

## Decision (Lightweight)

**Template:** `templates/decision.md`
**Destination:** `03-knowledge/decisions/descriptive-slug.md`

### Frontmatter

```yaml
---
type: decision
date: 2026-03-05
status: active | superseded | revoked
scope: platform | infra | tooling | process
tags: [decision, decision/architecture]
source: agent observation | user instruction
---
```

| Field | Values | Notes |
|-------|--------|-------|
| `status` | `active`, `superseded`, `revoked` | Default `active`. Set `superseded` when a newer decision replaces this one. |
| `scope` | `platform`, `infra`, `tooling`, `process` | Domain the decision applies to. |
| `source` | free text | Optional. Attribution — who or what prompted this decision. |

### Structure

Two sections only — Context and Decision. No alternatives, no consequences. Keep it tight.

1. **Context** — Why this came up (1–3 sentences)
2. **Decision** — What was decided (1–3 sentences)

> [!tip] For formal architecture decisions with alternatives analysis, use the [Decision Record (ADR)](#decision-record) template instead.

---

## Architecture Note

**Template:** `templates/architecture-note.md`
**Destination:** `03-knowledge/descriptive-slug.md`

### Frontmatter

```yaml
---
type: architecture
service: storage-service     # or "platform" for cross-cutting
scope: component | service | platform
created: 2026-03-05
status: draft | current | deprecated
tags: [architecture, platform/storage]
---
```

### Structure

1. **Context** — What problem this architecture addresses
2. **Decision** — The chosen approach
3. **Rationale** — Why this approach over alternatives
4. **Consequences** — Trade-offs
5. **Diagram** — Mermaid diagram (use `graph TD`, `sequenceDiagram`, or `C4Context`)
6. **References** — Links to ADRs, external docs

---

## Meeting Note

**Template:** `templates/meeting-note.md`
**Destination:** `00-inbox/YYYY-MM-DD-meeting-slug.md`

### Frontmatter

```yaml
---
date: 2026-03-05
type: meeting
attendees: [person-a, person-b]
tags: [meeting, platform/storage]
---
```

### Structure

1. **Agenda** — What was planned
2. **Notes** — What was discussed
3. **Decisions** — What was decided
4. **Action Items** — Checklist with assignees
5. **Follow-up** — Next steps or next meeting date

---

## Goal

**Template:** `templates/goal.md`
**Destination:** `01-goals/YYYY-QN-objectives.md`

### Frontmatter

```yaml
---
quarter: 2026-Q1
last_updated: 2026-03-05
type: goals
tags: [goals]
---
```

### Structure

Each goal is a numbered H2 section containing:
- **Priority** and **Status** (`on_track`, `at_risk`, `behind`, `complete`)
- **Progress** as percentage
- **Target** description
- **Key Results** as checklist items
- **Notes** for context

---

## Frontmatter Conventions

### Required Fields

Every note must have at minimum:

```yaml
---
type: <template-type>
date: YYYY-MM-DD        # or "created:" or "generated:" depending on template
tags: [tag1, tag2]
---
```

### Tag Taxonomy

Use consistent tags across the vault. Every note needs **at least two tags** from
different categories. Use nested tags (`parent/child`) for hierarchy — Obsidian
renders these as collapsible groups in the tag pane.

| Category | Flat tags | Nested tags |
|----------|-----------|-------------|
| Note type | `daily`, `meeting`, `goals` | `report/qa`, `report/dependency`, `report/incident`, `report/rca` |
| Decision | `adr` | `decision/architecture`, `decision/tooling`, `decision/process` |
| Architecture | `architecture` | — |
| Service | Use GitLab repo name | `platform/storage`, `platform/search`, `platform/indexer` |
| Infrastructure | — | `infra/aks`, `infra/terraform`, `infra/networking` |
| Severity | `critical`, `high`, `medium`, `low` | — |
| Status | `draft`, `reviewed`, `final`, `resolved` | — |
| Topic | `dependencies`, `cve`, `pipeline`, `migration` | — |

**Rules:**
- Minimum 2 tags, maximum 5 — more than 5 dilutes signal
- Always include one **type** tag and one **subject** tag
- Prefer nested tags over flat when a natural hierarchy exists
- Do not prefix tags with `#` in frontmatter arrays (`[qa]` not `[#qa]`)

### Optional Fields

These fields are not required by templates but should be added when applicable:

| Field | Type | When to use |
|-------|------|-------------|
| `source` | string | Attribution — who or what prompted this note. Use `human` for user-corrected notes (never decay). Use `agent observation` or free text for agent-generated notes based on external data (e.g., `glab pipeline, storage-service MR !456`). Not needed for daily briefings. |
| `last-verified` | `YYYY-MM-DD` | When the note was last confirmed accurate. Used by the consolidation script to detect stale notes. Set to today's date when updating a knowledge note. |
| `milestone` | string | OSDU milestone version the content reflects (e.g., `"0.29"`). Used for staleness detection. Omit for non-version-specific notes. |

### Date Formats

- Frontmatter: `YYYY-MM-DD` (ISO 8601)
- Filenames: `YYYY-MM-DD` prefix
- Inline text: Use whatever is readable, but prefer ISO format in tables

---

**Back to:** [Main Skill File](../SKILL.md)
