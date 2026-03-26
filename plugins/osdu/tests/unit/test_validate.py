# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest",
#     "rich",
# ]
# ///
# Copyright 2026, Microsoft
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Structure validation tests for the osdu plugin.

Validates plugin.json, agent files, skill frontmatter, and cross-references.
Run with:

    uv run --with rich --with pytest pytest tests/unit/test_validate.py -v
"""

import json
import re
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).parent.parent.parent


# =============================================================================
# Frontmatter Parser
# =============================================================================

def parse_frontmatter(content: str):
    """Parse YAML frontmatter from markdown content."""
    if not content.startswith("---"):
        return None, content
    end = content.find("\n---", 3)
    if end == -1:
        return None, content
    fm_text = content[4:end]
    body = content[end + 4:].strip()

    fm = {}
    current_key = None
    current_value_lines = []

    for line in fm_text.split("\n"):
        if re.match(r"^[a-z_-]+:", line):
            if current_key:
                fm[current_key] = "\n".join(current_value_lines).strip()
            parts = line.split(":", 1)
            current_key = parts[0].strip()
            val = parts[1].strip() if len(parts) > 1 else ""
            if val in (">-", ">", "|"):
                current_value_lines = []
            else:
                current_value_lines = [val.strip('"').strip("'")]
        elif current_key and line.startswith("  "):
            current_value_lines.append(line.strip())

    if current_key:
        fm[current_key] = "\n".join(current_value_lines).strip()

    return fm, body


# =============================================================================
# Plugin Structure Tests
# =============================================================================

class TestPluginJson:
    def test_exists(self):
        assert (PLUGIN_ROOT / ".claude-plugin" / "plugin.json").exists()

    def test_valid_json(self):
        data = json.loads(
            (PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text()
        )
        assert isinstance(data, dict)

    def test_required_fields(self):
        data = json.loads(
            (PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text()
        )
        assert data.get("name"), "Missing 'name'"
        assert data.get("description"), "Missing 'description'"
        assert data.get("version"), "Missing 'version'"

    def test_version_semver(self):
        data = json.loads(
            (PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text()
        )
        assert re.match(r"^\d+\.\d+\.\d+", data["version"]), (
            f"Version '{data['version']}' is not semver"
        )

    def test_agent_paths_exist(self):
        data = json.loads(
            (PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text()
        )
        for agent_path in data.get("agents", []):
            full_path = PLUGIN_ROOT / agent_path
            assert full_path.exists(), f"Agent not found: {agent_path}"


# =============================================================================
# Agent File Tests
# =============================================================================

class TestAgentFiles:
    @pytest.fixture
    def agent_files(self):
        agents_dir = PLUGIN_ROOT / "agents"
        return sorted(agents_dir.glob("*.md"))

    def test_agents_exist(self, agent_files):
        assert len(agent_files) > 0, "No agent files found"

    def test_all_have_frontmatter(self, agent_files):
        for f in agent_files:
            fm, _ = parse_frontmatter(f.read_text())
            assert fm is not None, f"{f.name} missing frontmatter"

    def test_all_have_name(self, agent_files):
        for f in agent_files:
            fm, _ = parse_frontmatter(f.read_text())
            assert fm.get("name"), f"{f.name} missing 'name' field"

    def test_all_have_description(self, agent_files):
        for f in agent_files:
            fm, _ = parse_frontmatter(f.read_text())
            assert fm.get("description"), f"{f.name} missing 'description' field"

    def test_names_are_lowercase(self, agent_files):
        for f in agent_files:
            fm, _ = parse_frontmatter(f.read_text())
            name = fm.get("name", "")
            assert name == name.lower(), (
                f"{f.name}: name '{name}' must be lowercase"
            )

    def test_names_match_filenames(self, agent_files):
        for f in agent_files:
            fm, _ = parse_frontmatter(f.read_text())
            name = fm.get("name", "")
            expected = f"{name}.md"
            assert f.name == expected, (
                f"Filename '{f.name}' doesn't match name '{name}' "
                f"(expected '{expected}')"
            )

    def test_no_duplicate_names(self, agent_files):
        names = []
        for f in agent_files:
            fm, _ = parse_frontmatter(f.read_text())
            names.append(fm.get("name", ""))
        assert len(names) == len(set(names)), f"Duplicate agent names: {names}"


# =============================================================================
# Skill Tests
# =============================================================================

class TestSkills:
    @pytest.fixture
    def skill_dirs(self):
        skills_dir = PLUGIN_ROOT / "skills"
        return sorted(
            d for d in skills_dir.iterdir()
            if d.is_dir() and (d / "SKILL.md").exists()
        )

    def test_skills_exist(self, skill_dirs):
        assert len(skill_dirs) > 0, "No skills found"

    def test_all_have_frontmatter(self, skill_dirs):
        for d in skill_dirs:
            content = (d / "SKILL.md").read_text()
            fm, _ = parse_frontmatter(content)
            assert fm is not None, f"{d.name}/SKILL.md missing frontmatter"

    def test_all_have_name(self, skill_dirs):
        for d in skill_dirs:
            fm, _ = parse_frontmatter((d / "SKILL.md").read_text())
            assert fm.get("name"), f"{d.name}/SKILL.md missing 'name'"

    def test_all_have_description(self, skill_dirs):
        for d in skill_dirs:
            fm, _ = parse_frontmatter((d / "SKILL.md").read_text())
            assert fm.get("description"), f"{d.name}/SKILL.md missing 'description'"

    def test_names_are_lowercase_kebab(self, skill_dirs):
        for d in skill_dirs:
            fm, _ = parse_frontmatter((d / "SKILL.md").read_text())
            name = fm.get("name", "")
            assert re.match(r"^[a-z][a-z0-9-]*$", name), (
                f"{d.name}: name '{name}' must be lowercase kebab-case"
            )

    def test_names_match_directories(self, skill_dirs):
        for d in skill_dirs:
            fm, _ = parse_frontmatter((d / "SKILL.md").read_text())
            name = fm.get("name", "")
            assert d.name == name, (
                f"Directory '{d.name}' doesn't match skill name '{name}'"
            )

    def test_no_duplicate_names(self, skill_dirs):
        names = []
        for d in skill_dirs:
            fm, _ = parse_frontmatter((d / "SKILL.md").read_text())
            names.append(fm.get("name", ""))
        assert len(names) == len(set(names)), "Duplicate skill names found"

    def test_description_length(self, skill_dirs):
        for d in skill_dirs:
            fm, _ = parse_frontmatter((d / "SKILL.md").read_text())
            desc = fm.get("description", "")
            assert 20 <= len(desc) <= 1024, (
                f"{d.name}: description length {len(desc)} not in 20-1024 range"
            )


# =============================================================================
# Setup Delegation Tests
# =============================================================================

class TestSetupDelegation:
    """Skills with --version pre-flight checks must delegate to setup on failure."""

    def test_version_checks_have_setup_delegation(self):
        skills_dir = PLUGIN_ROOT / "skills"
        missing_delegation = []
        preflight_pattern = re.compile(r"```bash\n\s*\S+\s+--version")
        for skill_dir in sorted(skills_dir.iterdir()):
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            content = skill_md.read_text()
            if skill_dir.name == "setup":
                continue
            if preflight_pattern.search(content):
                if "setup skill" not in content.lower():
                    missing_delegation.append(skill_dir.name)
        assert not missing_delegation, (
            f"Skills with pre-flight --version checks but no setup skill delegation: "
            f"{missing_delegation}"
        )
