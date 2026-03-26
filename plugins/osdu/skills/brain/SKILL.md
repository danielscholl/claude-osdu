---
name: brain
allowed-tools: Bash, Read, Write, Glob, Grep
description: >-
  Use when reading from, writing to, or organizing the OSDU brain Obsidian vault — the
  project's long-term memory and knowledge base. Trigger this skill whenever the user
  mentions the vault, brain, daily notes, daily briefing, reports, knowledge base,
  decision records, incident reports, dependency reports, QA reports, meeting notes,
  architecture notes, or asks to "remember", "store", "log", or "write up" anything
  related to project operations. Also trigger when generating MR summaries, pipeline
  analysis, RCA write-ups, dependency audits, or any content destined for the brain vault.
  Use when the user says "vault", "brain", "daily note", "remember this", "store this",
  "log this", "write up", or references knowledge base operations.
  Not for: ad-hoc chat answers, one-time commands, or information already in git history.
---

# Obsidian Vault — OSDU Brain

## Path Resolution

The vault location is determined by:
- `$OSDU_BRAIN` environment variable (if set)
- Default: `~/.osdu-brain`

All paths below use `$OSDU_BRAIN` to mean the resolved location.

---

The `$OSDU_BRAIN` directory is an Obsidian vault that serves as persistent, human-readable
project memory. The plugin provides the scaffold (directory structure, templates, Obsidian
config); content accumulates per-user over time.

## Quick Start

Check if the vault exists and QMD is indexed:
```bash
ls $OSDU_BRAIN/00-inbox/ 2>/dev/null && echo "vault exists" || echo "vault not found"
```
If the vault exists, use the QMD MCP server (`qmd` collection: `brain`) for all searches
before writing — this prevents duplicate notes and surfaces related content.

If the vault does not exist, run the initialization below.

## Initialization

When the vault does not exist and vault access is needed, or when the user says
"init brain", "setup brain", or "create vault":

1. Create the directory structure:

```
$OSDU_BRAIN/
├── 00-inbox/
├── 01-goals/
├── 02-projects/
├── 03-knowledge/
│   └── decisions/
├── 04-reports/
├── attachments/
└── templates/
```

2. Copy templates from this skill's `scaffold/templates/` into `$OSDU_BRAIN/templates/`
3. Copy Obsidian config from `scaffold/obsidian/` into `$OSDU_BRAIN/.obsidian/`
4. Place `scaffold/Welcome.md` into `$OSDU_BRAIN/00-inbox/Welcome.md`
5. Place `scaffold/.gitignore` into `$OSDU_BRAIN/.gitignore`

After initialization, report what was created and suggest opening in Obsidian.

## When to Use This Skill

- Creating or updating daily briefings
- Writing reports (QA, dependency, incident, architecture)
- Logging decisions (ADRs)
- Storing knowledge notes or research findings
- Summarizing MR activity across repos
- Documenting RCA from pipeline failures or infrastructure debugging
- Any time the user says "put this in the vault", "write that up", "log this", etc.

## Vault Structure

```
$OSDU_BRAIN/
+-- 00-inbox/          # Landing zone — new notes and daily briefings
+-- 01-goals/          # Quarterly objectives and key results
+-- 02-projects/       # Project config notes (one per project/platform)
+-- 03-knowledge/      # Durable reference material, research, patterns
+-- 04-reports/        # Generated reports (QA, dependency, incident, etc.)
+-- attachments/       # Images, diagrams, embedded files
+-- templates/         # Note templates (do NOT modify these)
```

**Key rule:** Notes start in `00-inbox/` unless they clearly belong in a specific folder.
The user curates and moves notes in Obsidian — place them correctly when
the destination is obvious (e.g., reports in `04-reports/`, ADRs in `03-knowledge/`).
Daily briefings always go in `00-inbox/`.

## Writing Notes

### Frontmatter Is Required

Every note MUST have YAML frontmatter. Match the `type` field to the template being used.
Always include `tags` as an array. Use ISO dates (`YYYY-MM-DD`).

```yaml
---
type: qa-report
date: 2026-03-05
tags: [report/qa, storage-service]
---
```

### Use Templates

Templates live in `$OSDU_BRAIN/templates/`. Before creating any note, check if a matching
template exists and follow its structure. When creating notes from templates, adapt the
template's default tags to follow the nested taxonomy (e.g., replace `tags: [osdu, qa]`
with `tags: [report/qa, storage-service]`). The available templates are:

| Template | Use For | Destination |
|----------|---------|-------------|
| `daily-note.md` | Daily briefings with MR summaries | `00-inbox/` |
| `report-note.md` | General reports | `04-reports/` |
| `qa-report.md` | QA/test run results | `04-reports/` |
| `dependency-report.md` | Dependency audits, CVE analysis | `04-reports/` |
| `incident-report.md` | RCA, pipeline failures, outages | `04-reports/` |
| `decision-record.md` | Architecture Decision Records | `03-knowledge/` |
| `decision.md` | Lightweight decisions, agent observations | `03-knowledge/decisions/` |
| `architecture-note.md` | System design, component docs | `03-knowledge/` |
| `meeting-note.md` | Meeting minutes | `00-inbox/` |
| `goal.md` | Quarterly OKRs | `01-goals/` |

**For complete template field reference, see:** [Templates Reference](references/templates.md)

### Obsidian-Flavored Markdown

Write Markdown that renders well in Obsidian:

- **Wiki links:** Use `[[note-name]]` to link between notes, `[[note-name|display text]]` for aliases
- **Tags:** Use `#tag-name` inline or `tags: [a, b]` in frontmatter (prefer frontmatter)
- **Callouts:** Use Obsidian callout syntax for visual structure:
  ```markdown
  > [!warning] Title
  > Content here
  ```
  Available types: `note`, `abstract`, `info`, `tip`, `success`, `question`, `warning`,
  `danger`, `bug`, `example`, `quote`
- **Mermaid diagrams:** Supported natively in fenced code blocks
- **Tables:** Standard Markdown tables, keep columns aligned
- **Checklists:** `- [ ] task` / `- [x] done`

### File Naming

- Daily notes: `YYYY-MM-DD.md` (e.g., `2026-03-05.md`)
- Reports: `YYYY-MM-DD-descriptive-slug.md` (e.g., `2026-03-05-storage-service-qa.md`)
- Knowledge: `descriptive-slug.md` (e.g., `spring-boot-3.2-migration-guide.md`)
- Decisions (ADR): `adr-NNN-descriptive-slug.md` (e.g., `adr-001-use-avm-modules.md`)
- Decisions (lightweight): `descriptive-slug.md` (e.g., `use-cnpg-over-azure-postgres.md`)
- Use lowercase, hyphens between words, no spaces

## Content Patterns

### Daily Briefings

Daily notes follow the `daily-note.md` template. When generating a daily briefing:

1. File goes in `00-inbox/YYYY-MM-DD.md`
2. Populate the MR tables with real data from GitLab APIs
3. Group MRs by project — each project in `02-projects/` gets its own section
4. Use pipeline status indicators: pass, fail, running, pending
5. Summarize key metrics at the bottom of each project section
6. Fill the Delegation section with actionable items for AI agents

### Reports

When writing reports (QA, dependency, incident, etc.):

1. Use the matching template from `templates/`
2. File goes in `04-reports/YYYY-MM-DD-descriptive-slug.md`
3. Fill ALL frontmatter fields — these power Obsidian's search and Dataview queries
4. Include an Executive Summary section at the top
5. Link to related notes using `[[wiki-links]]`
6. For tables with many rows, keep data dense — no extra blank lines between rows

### Decisions

Lightweight captured judgments — things the user or an agent decided that should persist.

**Use `decision.md`** (lightweight) when:
- User says "remember this" or "we decided to..."
- Agent discovers an undocumented convention during analysis
- A root cause is identified and a corrective choice is made
- A tooling or process choice is made that affects future work

**Use `decision-record.md`** (ADR) when:
- The decision requires alternatives analysis and formal sign-off
- Multiple stakeholders need to review the decision
- The decision has significant architectural consequences

**Do NOT create a decision note for:**
- One-time instructions ("run this command")
- Speculative plans not yet decided
- Information already captured in code comments or commit messages

Decision notes go in `03-knowledge/decisions/` using the `decision.md` template.
File naming: `descriptive-slug.md` (e.g., `use-cnpg-over-azure-postgres.md`).

### Knowledge Notes

For durable reference material (architecture patterns, research findings, how-to guides):

1. File goes in `03-knowledge/descriptive-slug.md`
2. Include `type: knowledge` or a more specific type in frontmatter
3. Add relevant tags for discoverability
4. Link to related decisions, incidents, or reports
5. Keep content evergreen — update rather than creating new notes when the topic exists

### Cross-Linking

The vault's power comes from connections between notes. When creating content:

- Link to the relevant project note in `02-projects/` if one exists
- Link incident reports to the services they affect
- Link dependency reports to the service they audit
- Link daily notes to any reports or incidents from that day
- Use tags consistently: service names, report types, severity levels

## Working with Multiple Repos

This vault serves as the central brain for a platform with 50+ service repos. Key patterns:

- **Service identification:** Use the GitLab project/repo name as the canonical service identifier in tags and frontmatter (e.g., `service: storage-service`)
- **MR references:** Link to GitLab MRs using `[!NNN](web_url)` format in tables
- **Cross-repo analysis:** When analyzing patterns across repos (dependency versions, test coverage, pipeline health), create a report in `04-reports/` with findings organized by service
- **Project config notes:** Each major platform or group of services gets a config note in `02-projects/` that serves as a hub linking to relevant reports, decisions, and knowledge

## Agent Write Discipline

Every agent (CIMPL, OSDU) must follow these rules when writing to the vault.
The vault is a curated knowledge graph — not a log dump. Protect its signal-to-noise ratio.

### Write Decision Framework

Before creating a vault note, pass through this filter:

```
 1. Did the user explicitly ask to store this?        → YES → Write it.
 2. Is this durable knowledge (useful in 30+ days)?   → NO  → Keep in chat.
 3. Does a note on this topic already exist?           → YES → Update it, don't duplicate.
 4. Is this raw output (logs, command dumps, traces)?  → YES → Don't write. Summarize instead.
 5. Does this represent a decision, pattern, or root cause? → YES → Write it.
```

**Write** — decisions, patterns, root causes, research findings, incident post-mortems,
architectural insights, recurring problems, cross-repo observations.

**Don't write** — one-off answers, raw CLI output, ephemeral debugging steps, status checks,
information the user didn't ask to preserve, anything already captured in git history or CI logs.

When in doubt: **answer in chat, offer to store.** ("Want me to put this in the vault?")

### Tagging Rules

Tags are the primary way agents navigate the vault. Poor tagging makes notes invisible
to future sessions. Every note must have **at least two tags** from different categories.

**Tag structure: category + specificity.**

```yaml
# GOOD — two categories, one specific
tags: [incident, storage-service, pipeline]

# GOOD — nested tags for hierarchy
tags: [report/qa, storage-service]

# BAD — only one generic tag
tags: [report]

# BAD — too many, dilutes signal
tags: [report, qa, service, storage, pipeline, azure, aks, critical, 2026]
```

**Nested tags** use `/` separator for hierarchy. Obsidian renders these as collapsible
groups in the tag pane:

| Parent | Children | Use For |
|--------|----------|---------|
| `report/` | `report/qa`, `report/dependency`, `report/incident`, `report/rca` | Report subtypes |
| `platform/` | `platform/storage`, `platform/search`, `platform/indexer` | Service-specific platform notes |
| `infra/` | `infra/aks`, `infra/terraform`, `infra/networking` | Infrastructure topics |
| `decision/` | `decision/architecture`, `decision/tooling`, `decision/process` | Decision subtypes |

**Tagging checklist** (apply in order):

1. **Type tag** — what kind of note is this? (`daily`, `incident`, `adr`, `architecture`, or nested `report/*`)
2. **Subject tag** — what service, component, or topic? (`storage-service`, `terraform`, `spring-boot`)
3. **Severity/status tag** — only if applicable (`critical`, `draft`, `resolved`)
4. **Keep it to 2–4 tags.** More than 5 is noise.

### Noise Filter

The vault is not a scratchpad. These do NOT belong:

| Keep out of vault | Why | Where it belongs |
|-------------------|-----|------------------|
| Raw `kubectl` / `terraform` output | Ephemeral, noisy | Chat response or CI logs |
| Single-question answers | No future recall value | Chat response |
| Intermediate debugging steps | Process, not outcome | Chat; write an incident note for the *conclusion* |
| Full MR diffs or code dumps | Already in git | Link to the MR instead |
| Speculative plans not yet decided | Premature, will rot | Chat; write an ADR when *decided* |
| Duplicate of an existing note | Dilutes the graph | Update the existing note |

**Rule of thumb:** If it wouldn't be useful to an agent starting a fresh session next week,
it doesn't belong in the vault.

### Connection Protocol

Before writing a new note, search for related existing notes. The vault's value comes from
its connections, not its volume.

1. **Search first** — use the QMD MCP server (collection: `brain`) to search for existing
   notes on the same topic before creating a new one. Use both lexical (`lex`) and semantic
   (`vec`) search. If a note exists, update it rather than creating a new file. When updating,
   append a new dated section rather than replacing content — this preserves history while
   keeping notes evergreen.
2. **Add backlinks** — every new note should contain at least one `[[wiki-link]]` to a
   related existing note (a project, a prior incident, a relevant ADR).
3. **Anchor to projects** — if the note relates to a specific platform or service group,
   link to its config note in `02-projects/`.
4. **Anchor to goals** — if the work connects to a quarterly objective, link to the
   relevant note in `01-goals/`. Goals are the vault's "north star" — agents should
   reference them when context is ambiguous.
5. **Surface missing connections** — this applies when browsing vault content during any
   task, not just during note creation. When you encounter related notes, suggest backlinks
   the user may have missed. ("This incident looks related to
   `[[adr-003-cnpg-operator-strategy]]` — want me to add a link?")

### Source Attribution

When an agent writes a note based on external data (GitLab API, pipeline logs, CLI output),
include a `source` field in frontmatter so future readers know where the data came from:

```yaml
---
type: qa-report
date: 2026-03-11
tags: [report/qa, storage-service]
source: glab pipeline, storage-service MR !456
---
```

This is not required for user-dictated notes or daily briefings (the source is obvious).

## Session Digests

At the end of a session, capture a structured digest summarizing decisions, facts learned,
and open threads. This creates episodic memory that helps future sessions pick up context.

### Format

Append to the current daily note (`00-inbox/YYYY-MM-DD.md`):

```markdown
## Session Digest — HH:MM

### Context
What was being worked on (1-2 sentences)

### Decisions
- Key decisions made

### Facts Learned
- New information discovered

### Open Questions
- Threads to pick up later
```

### Rules

- Append to the daily note — never create a separate file
- Create the daily note from template if it doesn't exist
- 3-5 bullets max per section — keep it scannable
- Use America/Chicago timezone for the HH:MM timestamp
- Skip empty sections (no decisions? omit the heading)
- Use `[[wiki-links]]` to reference vault notes mentioned in the session

**Full format reference:** [Session Digest Reference](references/session-digest.md)

## Knowledge Decay and Consolidation

Knowledge notes decay over time. The consolidation process flags stale notes and
contradictions to keep the vault accurate.

### Decay Rules

- Notes with `source: human` in frontmatter **never decay** (human-corrected knowledge)
- All other notes are checked against their `last-verified` date (or `git log` fallback)
- Notes not verified in >90 days are flagged as stale

### Frontmatter Fields for Decay

| Field | Type | Purpose |
|-------|------|---------|
| `last-verified` | `YYYY-MM-DD` | When the note was last confirmed accurate |
| `source` | `human` / `agent observation` / free text | `human` = never decays |

When updating a knowledge note, set `last-verified` to today's date to reset its decay timer.
When a human explicitly corrects or confirms a note, set `source: human`.

### Running Consolidation

```bash
uv run skills/consolidate/scripts/consolidate.py --dry-run
```

See the `consolidate` skill for the full consolidation protocol.

## What NOT to Do

- Do not modify files in `templates/` — these are the scaffold
- Do not modify `.obsidian/` config files — the user manages Obsidian settings
- Do not create deeply nested subdirectories — the folder structure is intentionally flat
- Do not duplicate information that exists in another note — link to it instead
- Do not store secrets, credentials, or sensitive connection strings in the vault
- Do not create notes without frontmatter — Obsidian and Dataview depend on it
- Do not use `#heading` tags in frontmatter arrays (use plain strings: `[qa, report]` not `[#qa, #report]`)
