# Conventional Commit Prompt

This is the reference for generating commit messages from staged diffs.

## Prompt

Generate a conventional commit message from the staged diff.

Rules:
- Format: `type(scope): description`
- Types: feat fix docs refactor chore ci style test build perf
- Scopes: infra platform scripts docs (omit scope if change spans multiple areas)
- Use imperative mood (add, implement, fix — not adds, added, adding)
- Lowercase first letter of description
- No trailing period
- First line under 72 characters

Multi-line rules:
- Simple changes (1-5 files, single purpose): one line only
- Substantial changes (6-15 files or multiple concerns): add 1 detail line
- Large changes (15+ files or multiple features): add 1-2 detail lines
- Additional lines under 80 characters each
- Max 3 lines total

Analysis strategy:
1. Examine new functions, classes, methods, imports in the diff
2. Identify the primary purpose of the change
3. For multi-feature changes, summarize the overall scope
4. Extract scope from directory names or functional areas

Output ONLY the commit message lines. No quotes, no explanation, no markdown fences, no preamble.
