---
name: learn
allowed-tools: Bash, Read, Write, Glob, Grep, WebFetch
description: >-
  Use when Agent is asked to study, learn, or absorb knowledge from external sources
  (GitLab wikis, documentation pages, URLs, or pasted content) and produce curated
  knowledge notes in the vault.
  Use when the user says "learn about", "study", "absorb", "index", "pull in docs for",
  or wants to populate the vault with reference material from an external source.
  Not for: quick one-off lookups or answers that don't need to be persisted in the vault.
---

# Learn — Knowledge Acquisition Skill

Agent can study external sources and produce curated knowledge notes in the vault.
This skill defines the protocol for acquiring, distilling, and storing reference material
so it is indexed by the RAG server and available to all agents.

**This is NOT a bulk scraper.** The goal is curated, tagged, connected knowledge notes —
not raw dumps.

## When to Use

- User asks Agent to "learn about OSDU", "study the wiki", "pull in docs for X"
- Populating the vault with reference material from GitLab wikis
- Ingesting documentation from URLs or pasted content
- Refreshing stale knowledge notes with updated source material

## Prerequisites

- Load the **brain** skill (`skills/brain/SKILL.md`) — all vault writes follow
  its Agent Write Discipline rules
- `glab` CLI authenticated for GitLab wiki access
- For URLs: WebFetch tool available

## Sources

### GitLab Wikis (via glab API)

The primary source for OSDU knowledge. Use the GitLab wiki API:

```bash
# List pages in a project wiki
glab api "projects/<url-encoded-path>/wikis?per_page=100" --hostname community.opengroup.org

# List pages in a group wiki
glab api "groups/<url-encoded-path>/wikis?per_page=100" --hostname community.opengroup.org

# Fetch a single page
glab api "groups/<url-encoded-path>/wikis/<slug>" --hostname community.opengroup.org
```

**Known OSDU wiki sources:**

| Source | API path | Content |
|--------|----------|---------|
| Platform group wiki | `groups/osdu%2Fplatform/wikis` | Core services, APIs, architecture |
| PMC wiki | `projects/osdu%2Fgovernance%2Fproject-management-committee/wikis` | Governance, releases, strategy |
| Documentation wiki | `projects/osdu%2Fdocumentation/wikis` | Mostly redirects to platform group wiki |

### URLs

When given a URL, use WebFetch to retrieve content, then distill into a knowledge note.

### Pasted Content

When the user pastes content directly, treat it as the source material and distill.

## Protocol

### Step 1: Discover

List available pages from the source. Filter out noise:

**Include** — pages about architecture, services, APIs, governance, strategy, processes,
standards, patterns, and the most recent release notes (latest 1-2 milestones only).

**Exclude** — upload/attachment pages, sidebar navigation, historical release/tagging notes
(keep only the latest), duplicate or redirect pages.

Present the filtered list to the user and confirm which pages to ingest.

### Step 2: Fetch & Assess

For each selected page:

1. Fetch the raw content via API
2. Assess whether it has enough substance for a knowledge note (skip stubs, redirect pages,
   pages that say "moved to X")
3. If the content is thin, note it and skip

### Step 3: Distill

Transform raw wiki content into a vault knowledge note. This is the critical step — do NOT
copy-paste raw wiki markdown. Instead:

1. **Extract durable concepts** — strip navigation boilerplate, redundant headers, and
   formatting artifacts (GitLab-specific syntax like `[[_TOC_]]`)
2. **Summarize where appropriate** — tables of services/APIs can be preserved as-is, but
   long prose sections should be condensed to the key points
3. **Preserve links** — keep URLs to GitLab repos, API docs, and external references.
   Convert GitLab wiki internal links to their full URLs
4. **Add context** — include a one-line summary at the top explaining what this knowledge
   is and why it matters
5. **Split or consolidate** — one note per topic when content is substantial (~500+ words
   of real content). Consolidate thin related pages into a single concept note when they
   don't stand alone. Too coarse = every RAG search returns an omnibus doc. Too fine =
   related context scattered across dozens of files.

### Step 4: Write

Create the knowledge note following brain skill conventions:

**Frontmatter:**
```yaml
---
type: knowledge
created: YYYY-MM-DD
tags: [platform/<topic>, osdu]
source: glab wiki, <source-path>/<page-slug>
milestone: "0.29"   # OSDU milestone version the content reflects (omit if not version-specific)
---
```

The `milestone` field enables staleness detection — a briefing or automated check can flag
notes written against an older milestone when a new one ships.

**File location:** `$OSDU_BRAIN/03-knowledge/osdu/<descriptive-slug>.md`

**File naming:**
- Use descriptive slugs: `core-services-overview.md`, `release-strategy.md`,
  `governance-charter.md`
- Do NOT use dates in filenames for reference material (it's evergreen, not temporal)

**Tagging — use nested tags:**

| Content type | Tags |
|-------------|------|
| Service architecture | `platform/architecture`, `osdu` |
| Individual service docs | `platform/<service-name>`, `osdu` |
| Governance / process | `platform/governance`, `osdu` |
| Release management | `platform/releases`, `osdu` |
| API documentation | `platform/api`, `osdu` |
| Security / compliance | `platform/security`, `osdu` |

**Connection requirements (mandatory):**
- Every note MUST include a `## Related Notes` section at the bottom with `[[wiki-links]]`
- Link to `[[osdu-platform]]` project config in `02-projects/` if it exists
- Cross-link between related knowledge notes (e.g., `[[core-services-overview]]` from
  a release note, `[[release-strategy]]` from a services note)
- If no related note exists yet, link to the project config as the minimum connection

### Step 5: Report

After ingestion, present a summary:

```
Learned X pages from [source]:
  - core-services-overview.md — 15 services catalogued
  - release-strategy.md — versioning model + milestone dates
  - [skipped] Feature-Flag — stub page, no content

Vault now has N OSDU knowledge notes in 03-knowledge/osdu/.
```

## Refreshing Knowledge

When re-learning from a source that already has vault notes:

1. **Search first** — check `$OSDU_BRAIN/03-knowledge/osdu/` for existing notes on the topic
2. **Update, don't duplicate** — if a note exists, append a dated update section:
   ```markdown
   ## Update — 2026-03-11

   [New information from source refresh]
   ```
3. **Update the `created` date** only if the note is being substantially rewritten

## Live Fallback

If vault notes are absent or stale and the question is urgent, agents may fetch the relevant
wiki page via `glab api` as a one-shot answer in chat. The write guard is critical:

- **Raw API output stays in chat** — do not write it to the vault
- **If the content is worth keeping**, run the full learn protocol (distill → write → connect)
- This prevents a hard stop in sessions where the vault hasn't been populated yet

## What NOT to Do

- Do not dump raw wiki pages into the vault without distilling
- Do not ingest all pages from a wiki — curate based on value
- Do not ingest historical release/tagging notes (150+ pages of noise)
- Do not create one massive "OSDU overview" note — split by topic for granular RAG retrieval
- Do not ingest content that duplicates what's already in `reference/osdu-cli-reference.md`
- Do not proceed without confirming the page list with the user
