# Session Digest Format

> **Part of:** [brain skill](../SKILL.md)
> **Purpose:** Structured session summary appended to the daily note at session end

---

## Format

```markdown
## Session Digest — HH:MM

### Context
What was being worked on (1-2 sentences)

### Decisions
- Key decisions made during this session

### Facts Learned
- New information discovered during this session

### Open Questions
- Threads to pick up in the next session
```

## Rules

1. **Append to the daily note** — never create a separate file for a digest
2. **Create daily note from template if missing** — use `templates/daily-note.md`
3. **3-5 bullets max per section** — keep it scannable
4. **Use America/Chicago timezone** for the HH:MM timestamp
5. **Multiple digests per day are fine** — each session gets its own H2 heading
6. **Skip empty sections** — if no decisions were made, omit the Decisions section
7. **Use `[[wiki-links]]`** to reference vault notes mentioned during the session

## Example

```markdown
## Session Digest — 14:30

### Context
Investigated failing acceptance tests in storage-service after pipeline regression.

### Decisions
- Switch to CNPG operator v1.24 to resolve connection pooling issue
- Pin Spring Boot to 3.2.3 across all core services

### Facts Learned
- storage-service acceptance tests depend on partition-service being healthy
- CNPG operator <1.24 has a known bug with PgBouncer session mode

### Open Questions
- Should we add a health gate between partition and storage in CI?
- Need to check if seismic-store also uses PgBouncer session mode
```

---

**Back to:** [Main Skill File](../SKILL.md)
