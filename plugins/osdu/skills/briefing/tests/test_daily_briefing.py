# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pytest",
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
Unit tests for daily-briefing.py — SPI integration and rendering functions.

Tests cover:
- SPI workflow label mapping
- SPI alert extraction from fork status data
- SPI section rendering (healthy, alerts, error, empty)
- SPI integration into recommendations, risks, and delegation
- Brain context SPI keyword injection

Run with:
    uv run --with pytest pytest plugins/osdu/skills/briefing/tests/test_daily_briefing.py -v
"""

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

# Add the scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

# Import the functions under test from daily-briefing.py
# The module has a hyphen so we use importlib
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "daily_briefing",
    Path(__file__).parent.parent / "scripts" / "daily-briefing.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# Pull out the functions we need to test
_spi_workflow_label = _mod._spi_workflow_label
build_spi_alerts = _mod.build_spi_alerts
render_spi_section = _mod.render_spi_section
render_recommendations = _mod.render_recommendations
render_risks = _mod.render_risks
render_delegation = _mod.render_delegation
render_footer = _mod.render_footer

TIMEZONE = ZoneInfo("America/Chicago")


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def healthy_spi_status():
    """SPI status with all repos healthy, no alerts."""
    return {
        "org": "azure",
        "services": {
            "partition": {
                "issues_open": 0, "prs_open": 1, "sync_prs": 0,
                "template_sync_prs": 0, "workflow_conclusion": "success",
                "human_required": 0, "cascade_blocked": 0,
            },
            "entitlements": {
                "issues_open": 0, "prs_open": 0, "sync_prs": 0,
                "template_sync_prs": 0, "workflow_conclusion": "success",
                "human_required": 0, "cascade_blocked": 0,
            },
            "legal": {
                "issues_open": 0, "prs_open": 0, "sync_prs": 0,
                "template_sync_prs": 0, "workflow_conclusion": "success",
                "human_required": 0, "cascade_blocked": 0,
            },
        },
        "extra_repos": {
            "osdu-spi": {"issues_open": 0, "prs_open": 0},
            "osdu-spi-infra": {"issues_open": 0, "prs_open": 0},
        },
        "error": None,
    }


@pytest.fixture
def alerting_spi_status():
    """SPI status with multiple alert types."""
    return {
        "org": "azure",
        "services": {
            "partition": {
                "issues_open": 0, "prs_open": 2, "sync_prs": 1,
                "template_sync_prs": 0, "workflow_conclusion": "success",
                "human_required": 0, "cascade_blocked": 0,
            },
            "entitlements": {
                "issues_open": 2, "prs_open": 1, "sync_prs": 0,
                "template_sync_prs": 0, "workflow_conclusion": "failure",
                "human_required": 1, "cascade_blocked": 0,
            },
            "storage": {
                "issues_open": 1, "prs_open": 0, "sync_prs": 0,
                "template_sync_prs": 0, "workflow_conclusion": "success",
                "human_required": 0, "cascade_blocked": 1,
            },
        },
        "extra_repos": {
            "osdu-spi": {"issues_open": 0, "prs_open": 1},
            "osdu-spi-infra": {"issues_open": 2, "prs_open": 0},
        },
        "error": None,
    }


@pytest.fixture
def error_spi_status():
    """SPI status when gh auth fails."""
    return {
        "org": "azure",
        "services": {},
        "extra_repos": {},
        "error": "gh not available or not authenticated",
    }


@pytest.fixture
def now():
    return datetime(2026, 3, 31, 8, 0, 0, tzinfo=TIMEZONE)


# =============================================================================
# Test: _spi_workflow_label
# =============================================================================

class TestSpiWorkflowLabel:
    def test_success(self):
        assert _spi_workflow_label("success") == "✅"

    def test_failure(self):
        assert _spi_workflow_label("failure") == "❌"

    def test_cancelled(self):
        assert _spi_workflow_label("cancelled") == "⊘"

    def test_skipped(self):
        assert _spi_workflow_label("skipped") == "⊘"

    def test_none(self):
        assert _spi_workflow_label("none") == "⬜"

    def test_question_mark(self):
        assert _spi_workflow_label("?") == "⬜"

    def test_unknown_value(self):
        result = _spi_workflow_label("something_else")
        assert "❓" in result


# =============================================================================
# Test: build_spi_alerts
# =============================================================================

class TestBuildSpiAlerts:
    def test_no_alerts_for_healthy_status(self, healthy_spi_status):
        alerts = build_spi_alerts(healthy_spi_status)
        assert len(alerts) == 0

    def test_extracts_human_required(self, alerting_spi_status):
        alerts = build_spi_alerts(alerting_spi_status)
        human = [a for a in alerts if a["type"] == "human-required"]
        assert len(human) == 1
        assert human[0]["service"] == "entitlements"
        assert human[0]["severity"] == "high"
        assert human[0]["count"] == 1

    def test_extracts_cascade_blocked(self, alerting_spi_status):
        alerts = build_spi_alerts(alerting_spi_status)
        blocked = [a for a in alerts if a["type"] == "cascade-blocked"]
        assert len(blocked) == 1
        assert blocked[0]["service"] == "storage"
        assert blocked[0]["severity"] == "high"

    def test_extracts_workflow_failure(self, alerting_spi_status):
        alerts = build_spi_alerts(alerting_spi_status)
        failures = [a for a in alerts if a["type"] == "workflow-failure"]
        assert len(failures) == 1
        assert failures[0]["service"] == "entitlements"
        assert failures[0]["severity"] == "medium"

    def test_extracts_sync_pr_pending(self, alerting_spi_status):
        alerts = build_spi_alerts(alerting_spi_status)
        sync = [a for a in alerts if a["type"] == "sync-pr-pending"]
        assert len(sync) == 1
        assert sync[0]["service"] == "partition"
        assert sync[0]["severity"] == "low"

    def test_empty_services(self):
        alerts = build_spi_alerts({"services": {}})
        assert alerts == []

    def test_missing_services_key(self):
        alerts = build_spi_alerts({})
        assert alerts == []


# =============================================================================
# Test: render_spi_section
# =============================================================================

class TestRenderSpiSection:
    def test_error_shows_warning(self, error_spi_status):
        output = render_spi_section(error_spi_status)
        assert "SPI fork health unavailable" in output
        assert "gh auth login" in output
        assert "[!warning]" in output

    def test_healthy_shows_success_callout(self, healthy_spi_status):
        output = render_spi_section(healthy_spi_status)
        assert "[!success]" in output
        assert "no alerts" in output.lower()
        assert "partition" in output
        assert "entitlements" in output
        assert "legal" in output

    def test_healthy_has_summary_line(self, healthy_spi_status):
        output = render_spi_section(healthy_spi_status)
        assert "**Summary:**" in output
        assert "3 repos" in output

    def test_alerts_show_info_callout(self, alerting_spi_status):
        output = render_spi_section(alerting_spi_status)
        assert "[!info]" in output
        assert "need attention" in output.lower()

    def test_alerts_show_danger_callout(self, alerting_spi_status):
        output = render_spi_section(alerting_spi_status)
        assert "[!danger]" in output
        assert "SPI Alerts" in output

    def test_alerts_list_human_required(self, alerting_spi_status):
        output = render_spi_section(alerting_spi_status)
        assert "human-required" in output
        assert "entitlements" in output
        assert "conflict resolution" in output

    def test_alerts_list_cascade_blocked(self, alerting_spi_status):
        output = render_spi_section(alerting_spi_status)
        assert "cascade blocked" in output
        assert "storage" in output

    def test_alerts_list_workflow_failure(self, alerting_spi_status):
        output = render_spi_section(alerting_spi_status)
        assert "workflow failing" in output

    def test_has_table_header(self, healthy_spi_status):
        output = render_spi_section(healthy_spi_status)
        assert "Service" in output
        assert "Issues" in output
        assert "PRs" in output
        assert "Sync" in output
        assert "Workflow" in output
        assert "Alerts" in output

    def test_extra_repos_shown(self, alerting_spi_status):
        output = render_spi_section(alerting_spi_status)
        assert "Template/Infra" in output
        assert "osdu-spi" in output
        assert "osdu-spi-infra" in output

    def test_extra_repos_hidden_when_empty(self, healthy_spi_status):
        output = render_spi_section(healthy_spi_status)
        assert "Template/Infra" not in output

    def test_empty_services(self):
        output = render_spi_section({"services": {}, "extra_repos": {}, "error": None})
        assert "No SPI fork data" in output

    def test_section_header(self, healthy_spi_status):
        output = render_spi_section(healthy_spi_status)
        assert "## SPI Forks · GitHub" in output


# =============================================================================
# Test: SPI alerts in recommendations
# =============================================================================

class TestRecommendationsWithSpi:
    def test_no_spi_alerts_no_spi_recommendations(self, now):
        output = render_recommendations([], [], [], now, spi_alerts=[])
        assert "SPI" not in output

    def test_high_severity_alerts_generate_recommendation(self, now):
        alerts = [
            {"service": "entitlements", "type": "human-required", "count": 1, "severity": "high"},
            {"service": "storage", "type": "cascade-blocked", "count": 1, "severity": "high"},
        ]
        output = render_recommendations([], [], [], now, spi_alerts=alerts)
        assert "Resolve SPI fork alerts" in output
        assert "entitlements" in output
        assert "storage" in output

    def test_workflow_failures_generate_recommendation(self, now):
        alerts = [
            {"service": "indexer", "type": "workflow-failure", "count": 1, "severity": "medium"},
        ]
        output = render_recommendations([], [], [], now, spi_alerts=alerts)
        assert "Fix SPI build failures" in output
        assert "indexer" in output

    def test_none_spi_alerts_is_safe(self, now):
        # Backwards compatibility: spi_alerts=None should work
        output = render_recommendations([], [], [], now, spi_alerts=None)
        assert "SPI" not in output


# =============================================================================
# Test: SPI alerts in risks
# =============================================================================

class TestRisksWithSpi:
    def test_cascade_blocked_generates_risk(self, now):
        alerts = [
            {"service": "storage", "type": "cascade-blocked", "count": 1, "severity": "high"},
        ]
        output = render_risks([], [], 0, 0, now, spi_alerts=alerts)
        assert "cascade blocked" in output.lower()
        assert "storage" in output

    def test_multiple_human_required_generates_systemic_risk(self, now):
        alerts = [
            {"service": "partition", "type": "human-required", "count": 1, "severity": "high"},
            {"service": "entitlements", "type": "human-required", "count": 1, "severity": "high"},
            {"service": "legal", "type": "human-required", "count": 1, "severity": "high"},
        ]
        output = render_risks([], [], 0, 0, now, spi_alerts=alerts)
        assert "3 SPI forks" in output
        assert "systemic" in output.lower()

    def test_two_human_required_no_systemic_risk(self, now):
        alerts = [
            {"service": "partition", "type": "human-required", "count": 1, "severity": "high"},
            {"service": "entitlements", "type": "human-required", "count": 1, "severity": "high"},
        ]
        output = render_risks([], [], 0, 0, now, spi_alerts=alerts)
        assert "systemic" not in output.lower()

    def test_none_spi_alerts_is_safe(self, now):
        output = render_risks([], [], 0, 0, now, spi_alerts=None)
        assert "SPI" not in output


# =============================================================================
# Test: SPI alerts in delegation
# =============================================================================

class TestDelegationWithSpi:
    def test_workflow_failure_routes_to_spi_agent(self, now):
        alerts = [
            {"service": "indexer", "type": "workflow-failure", "count": 1, "severity": "medium"},
        ]
        output = render_delegation([], [], [], now, spi_alerts=alerts)
        assert "@spi agent" in output
        assert "osdu-spi-indexer" in output
        assert "workflow" in output.lower()

    def test_human_required_routes_to_spi_agent(self, now):
        alerts = [
            {"service": "entitlements", "type": "human-required", "count": 1, "severity": "high"},
        ]
        output = render_delegation([], [], [], now, spi_alerts=alerts)
        assert "@spi agent" in output
        assert "conflict resolution" in output

    def test_cascade_blocked_routes_to_spi_agent(self, now):
        alerts = [
            {"service": "storage", "type": "cascade-blocked", "count": 1, "severity": "high"},
        ]
        output = render_delegation([], [], [], now, spi_alerts=alerts)
        assert "@spi agent" in output
        assert "Unblock cascade" in output

    def test_sync_pr_not_delegated(self, now):
        alerts = [
            {"service": "partition", "type": "sync-pr-pending", "count": 1, "severity": "low"},
        ]
        output = render_delegation([], [], [], now, spi_alerts=alerts)
        assert "@spi agent" not in output

    def test_none_spi_alerts_is_safe(self, now):
        output = render_delegation([], [], [], now, spi_alerts=None)
        assert "@spi" not in output


# =============================================================================
# Test: render_footer passes through spi_alerts
# =============================================================================

class TestFooterWithSpi:
    def test_footer_surfaces_spi_alerts(self, now):
        alerts = [
            {"service": "entitlements", "type": "human-required", "count": 1, "severity": "high"},
            {"service": "storage", "type": "workflow-failure", "count": 1, "severity": "medium"},
        ]
        output = render_footer([], [], [], 0, 0, now, spi_alerts=alerts)
        assert "SPI" in output
        assert "@spi agent" in output

    def test_footer_without_spi(self, now):
        output = render_footer([], [], [], 0, 0, now)
        assert "@spi" not in output
