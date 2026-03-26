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
Structure validation tests for the cimpl plugin.

Run with:

    uv run --with rich --with pytest pytest tests/unit/test_validate.py -v
"""

import json
import re
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).parent.parent.parent


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

    def test_agent_paths_exist(self):
        data = json.loads(
            (PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text()
        )
        for agent_path in data.get("agents", []):
            full_path = PLUGIN_ROOT / agent_path
            assert full_path.exists(), f"Agent not found: {agent_path}"


class TestAgentFiles:
    @pytest.fixture
    def agent_files(self):
        return sorted((PLUGIN_ROOT / "agents").glob("*.md"))

    def test_agents_exist(self, agent_files):
        assert len(agent_files) > 0

    def test_all_have_frontmatter(self, agent_files):
        for f in agent_files:
            fm, _ = parse_frontmatter(f.read_text())
            assert fm is not None, f"{f.name} missing frontmatter"

    def test_all_have_name_and_description(self, agent_files):
        for f in agent_files:
            fm, _ = parse_frontmatter(f.read_text())
            assert fm.get("name"), f"{f.name} missing 'name'"
            assert fm.get("description"), f"{f.name} missing 'description'"


class TestSkills:
    @pytest.fixture
    def skill_dirs(self):
        return sorted(
            d for d in (PLUGIN_ROOT / "skills").iterdir()
            if d.is_dir() and (d / "SKILL.md").exists()
        )

    def test_skills_exist(self, skill_dirs):
        assert len(skill_dirs) > 0

    def test_all_have_frontmatter(self, skill_dirs):
        for d in skill_dirs:
            fm, _ = parse_frontmatter((d / "SKILL.md").read_text())
            assert fm is not None, f"{d.name}/SKILL.md missing frontmatter"

    def test_names_match_directories(self, skill_dirs):
        for d in skill_dirs:
            fm, _ = parse_frontmatter((d / "SKILL.md").read_text())
            assert d.name == fm.get("name", ""), (
                f"Directory '{d.name}' doesn't match skill name"
            )
