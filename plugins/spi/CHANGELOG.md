# Changelog

## [0.2.0] - 2026-03-31

### Added
- **status skill** — Cross-repository aggregation of issues, PRs, and workflows
  across all SPI fork repos. Dashboard view, focused queries (blocked cascades,
  human-required issues, sync PRs, failing workflows), branch divergence checks.
- **fork-init.md reference** — Complete fork initialization guide using clone+push
  approach (avoids enterprise SSO issues with `--template` flag). Includes
  upstream URL mapping, workflow polling, branch-based testing, bulk init.
- **SPI_ORG configuration** — All fork and status operations support configurable
  GitHub org via `SPI_ORG` env var (defaults to `azure`, override with personal
  org like `danielscholl-osdu` for testing).

### Changed
- **forks skill** — Extended with "Fork Initialization (CLI)" section replacing
  the manual "Use this template" approach. Documents clone+push as primary path.
- **agent routing** — Added status skill to routing signals table. Health skill
  now also appears in routing signals.

### Technical Notes
- The `gh repo create --template` flag fails with SAML SSO enforcement on the
  `azure` org (Microsoft enterprise). The clone+push approach works universally
  for both enterprise and personal orgs.
- Fork init lifecycle verified end-to-end: ~90 seconds total (15s init fork +
  30s init complete + overhead).

## [0.1.0] - 2026-03-30

### Added
- Initial SPI plugin with 4 skills: iac, forks, health, setup
- Single agent (spi) with routing for all skills
- 8 reference docs (4 iac + 4 forks)
- Trigger evals and scenario evals for all skills
- Structural validation tests (10/10 passing)
