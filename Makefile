# Plugin Test Runner
# =================
# Cross-plugin test runner using the skilltest framework scripts.
#
# Usage:
#   make test                    Fast tests: lint + unit across all plugins
#   make test P=osdu             Fast tests for one plugin only
#   make lint                    L1: Structure validation (all plugins)
#   make unit                    L2: Trigger eval dry-run (all plugins)
#   make integration             L3: Session tests (all plugins)
#   make benchmark P=osdu S=brain   L4: Skill value comparison
#   make report                  Test inventory across all plugins
#   make test-skill P=osdu S=brain  All layers for one skill
#
# Options:
#   P=plugin-name    Target a specific plugin (osdu, cimpl)
#   S=skill-name     Target a specific skill within the plugin
#   DEBUG=1          Show response captures in L3 integration tests

SCRIPTS := ../claude-sdlc/plugins/skilltest/skills/test-framework/scripts
DEBUG_FLAG := $(if $(DEBUG),--debug,)

# Auto-discover plugins that have tests/evals directories
PLUGINS := $(sort $(patsubst plugins/%/tests/,%,$(wildcard plugins/*/tests/)))

.PHONY: test lint unit integration benchmark report test-skill help pytest

help: ## Show this help
	@echo "Plugin Test Runner"
	@echo "=================="
	@echo ""
	@echo "Quick start:"
	@echo "  make test                    Lint + unit across all plugins (fast)"
	@echo "  make test P=osdu             Lint + unit for one plugin"
	@echo "  make pytest                  Run all pytest suites"
	@echo ""
	@echo "Individual layers:"
	@echo "  make lint                    L1: Structure validation"
	@echo "  make unit                    L2: Trigger eval dry-run (validates eval sets)"
	@echo "  make integration             L3: Multi-turn session tests"
	@echo "  make benchmark P=X S=Y       L4: Skill value comparison"
	@echo ""
	@echo "Targeting:"
	@echo "  make report                  Test inventory for all plugins"
	@echo "  make test-skill P=X S=Y      All layers for one skill in one plugin"
	@echo ""
	@echo "Options:"
	@echo "  P=plugin-name    Target plugin ($(PLUGINS))"
	@echo "  S=skill-name     Target skill within the plugin"
	@echo "  DEBUG=1          Show response captures in L3 tests"
	@echo ""
	@echo "Detected plugins: $(PLUGINS)"

# =============================================================================
# Fast tests (run after every change)
# =============================================================================

test: lint unit pytest

# =============================================================================
# L1: Structure validation
# =============================================================================

lint:
ifdef P
	@echo ""
	@echo "=== L1: Structure — $(P) ==="
	@uv run $(SCRIPTS)/validate.py --root plugins/$(P)
else
	@for plugin in $(PLUGINS); do \
		echo ""; \
		echo "=== L1: Structure — $$plugin ==="; \
		uv run $(SCRIPTS)/validate.py --root plugins/$$plugin || true; \
	done
endif

# =============================================================================
# L2: Trigger eval dry-run (validates eval set balance and format)
# =============================================================================

unit:
ifdef P
	@echo ""
	@echo "=== L2: Trigger Evals — $(P) ==="
	@for evalfile in $$(ls plugins/$(P)/tests/evals/triggers/*.json 2>/dev/null); do \
		skill=$$(basename $$evalfile .json); \
		printf "  %-25s " "$$skill"; \
		eval_rel="tests/evals/triggers/$$skill.json"; \
		skill_path=""; \
		if [ -d "plugins/$(P)/skills/$$skill" ]; then \
			skill_path="skills/$$skill"; \
		elif [ -d "plugins/$(P)/agents" ] && [ -f "plugins/$(P)/agents/$$skill.md" ]; then \
			skill_path="agents/$$skill.md"; \
		fi; \
		if [ -n "$$skill_path" ]; then \
			uv run $(SCRIPTS)/run_trigger_eval.py \
				--eval-set $$eval_rel \
				--skill-path $$skill_path \
				--root plugins/$(P) \
				--dry-run 2>&1 | grep -o '[0-9]* positive.*' || echo "error"; \
		else \
			echo "skill not found (checked skills/$$skill and agents/$$skill.md)"; \
		fi; \
	done
	@echo ""
else
	@for plugin in $(PLUGINS); do \
		has_evals=$$(ls plugins/$$plugin/tests/evals/triggers/*.json 2>/dev/null | head -1); \
		if [ -n "$$has_evals" ]; then \
			echo ""; \
			echo "=== L2: Trigger Evals — $$plugin ==="; \
			for evalfile in plugins/$$plugin/tests/evals/triggers/*.json; do \
				skill=$$(basename $$evalfile .json); \
				printf "  %-25s " "$$skill"; \
				eval_rel="tests/evals/triggers/$$skill.json"; \
				skill_path=""; \
				if [ -d "plugins/$$plugin/skills/$$skill" ]; then \
					skill_path="skills/$$skill"; \
				elif [ -d "plugins/$$plugin/agents" ] && [ -f "plugins/$$plugin/agents/$$skill.md" ]; then \
					skill_path="agents/$$skill.md"; \
				fi; \
				if [ -n "$$skill_path" ]; then \
					uv run $(SCRIPTS)/run_trigger_eval.py \
						--eval-set $$eval_rel \
						--skill-path $$skill_path \
						--root plugins/$$plugin \
						--dry-run 2>&1 | grep -o '[0-9]* positive.*' || echo "error"; \
				else \
					echo "skill not found"; \
				fi; \
			done; \
		fi; \
	done
	@echo ""
endif

# =============================================================================
# L3: Integration / Session tests
# =============================================================================

integration:
ifdef P
ifdef S
	@echo "=== L3: Session — $(P)/$(S) ==="
	@uv run $(SCRIPTS)/session_test.py \
		--scenario $$(ls plugins/$(P)/tests/evals/scenarios/*$(S)*.json 2>/dev/null | head -1) \
		--root plugins/$(P) --verbose $(DEBUG_FLAG)
else
	@echo "=== L3: Sessions — $(P) ==="
	@for scenario in $$(ls plugins/$(P)/tests/evals/scenarios/*.json 2>/dev/null); do \
		name=$$(basename $$scenario .json); \
		echo ""; \
		echo "--- $$name ---"; \
		uv run $(SCRIPTS)/session_test.py \
			--scenario $$scenario \
			--root plugins/$(P) --verbose $(DEBUG_FLAG) 2>&1 | tail -15; \
	done
endif
else
	@for plugin in $(PLUGINS); do \
		has_scenarios=$$(ls plugins/$$plugin/tests/evals/scenarios/*.json 2>/dev/null | head -1); \
		if [ -n "$$has_scenarios" ]; then \
			echo ""; \
			echo "=== L3: Sessions — $$plugin ==="; \
			for scenario in plugins/$$plugin/tests/evals/scenarios/*.json; do \
				name=$$(basename $$scenario .json); \
				echo ""; \
				echo "--- $$name ---"; \
				uv run $(SCRIPTS)/session_test.py \
					--scenario $$scenario \
					--root plugins/$$plugin --verbose $(DEBUG_FLAG) 2>&1 | tail -15; \
			done; \
		fi; \
	done
endif

# =============================================================================
# L4: Skill value comparison (benchmark)
# =============================================================================

benchmark:
ifndef P
	@echo "Usage: make benchmark P=plugin-name S=skill-name"
	@echo "Example: make benchmark P=osdu S=brain"
	@exit 1
endif
ifndef S
	@echo "Usage: make benchmark P=$(P) S=skill-name"
	@exit 1
endif
	@mkdir -p plugins/$(P)/tests/benchmarks
	@uv run $(SCRIPTS)/compare_skill.py \
		--skill $(S) \
		--scenario $$(ls plugins/$(P)/tests/evals/scenarios/*$(S)*.json 2>/dev/null | head -1) \
		--root plugins/$(P) --verbose \
		--save-to plugins/$(P)/tests/benchmarks/

# =============================================================================
# All layers for one skill
# =============================================================================

test-skill:
ifndef P
	@echo "Usage: make test-skill P=plugin-name S=skill-name"
	@echo "Example: make test-skill P=osdu S=brain"
	@exit 1
endif
ifndef S
	@echo "Usage: make test-skill P=$(P) S=skill-name"
	@exit 1
endif
	@uv run $(SCRIPTS)/test_skill.py $(S) --root plugins/$(P)

# =============================================================================
# Test inventory / report
# =============================================================================

report:
ifdef P
	@echo "=== Inventory — $(P) ==="
	@uv run $(SCRIPTS)/test_skill.py --inventory --root plugins/$(P)
else
	@for plugin in $(PLUGINS); do \
		echo ""; \
		echo "=== Inventory — $$plugin ==="; \
		uv run $(SCRIPTS)/test_skill.py --inventory --root plugins/$$plugin 2>&1; \
	done
endif

# =============================================================================
# Pytest: unit tests for plugin scripts
# =============================================================================

pytest:
	@echo ""
	@echo "=== Pytest: Unit Tests ==="
	@failed=0; \
	for plugin in $(PLUGINS); do \
		if [ -d "plugins/$$plugin/tests/unit" ] && [ "$$(ls plugins/$$plugin/tests/unit/test_*.py 2>/dev/null)" ]; then \
			echo ""; \
			echo "--- $$plugin ---"; \
			(cd plugins/$$plugin && uv run --with rich --with pytest pytest tests/unit/ -v --tb=short) || failed=1; \
		fi; \
	done; \
	if [ $$failed -eq 1 ]; then exit 1; fi
