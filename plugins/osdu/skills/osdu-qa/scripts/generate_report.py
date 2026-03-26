# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx",
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
OSDU QA Report Generator

Generates reports in multiple formats:
- Markdown (comprehensive, category, executive)
- HTML (interactive dashboard)
- JSON (structured data)
"""

import json
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent directory to path for common imports
sys.path.insert(0, str(Path(__file__).parent))
from common import SKILL_DIR, RESULTS_DIR

TEMPLATES_DIR = SKILL_DIR / "templates"


def load_results(input_path: Optional[Path] = None) -> dict:
    """Load test results from file or find latest."""
    if input_path and input_path.exists():
        return json.loads(input_path.read_text())

    # Find latest results
    results_files = sorted(RESULTS_DIR.glob("*.json"), reverse=True)
    if results_files:
        return json.loads(results_files[0].read_text())

    return {}


def generate_html_dashboard(results: dict, output_dir: Path) -> Path:
    """Generate interactive HTML dashboard."""

    env = results.get("environment", "unknown")
    timestamp = results.get("timestamp", datetime.now().isoformat())
    collections = results.get("collections", [])
    summary = results.get("summary", {})

    # Calculate metrics
    total = len(collections)
    passed = sum(1 for c in collections if c.get("status") == "passed")
    failed = total - passed
    pass_rate = (passed / total * 100) if total > 0 else 0

    # Category breakdown
    categories = {}
    for c in collections:
        cat = c.get("category", "Other")
        if cat not in categories:
            categories[cat] = {"passed": 0, "failed": 0, "assertions": 0}
        if c.get("status") == "passed":
            categories[cat]["passed"] += 1
        else:
            categories[cat]["failed"] += 1
        categories[cat]["assertions"] += c.get("assertions", {}).get("total", 0)

    # Generate category bars
    cat_bars = ""
    colors = {
        "Core": "#3b82f6",
        "Data": "#22c55e",
        "Workflow": "#f59e0b",
        "Well R3": "#8b5cf6",
        "DDMS": "#ec4899",
        "Seismic": "#06b6d4",
        "Other": "#6b7280"
    }
    for cat, data in sorted(categories.items()):
        total_cat = data["passed"] + data["failed"]
        pct = (data["passed"] / total_cat * 100) if total_cat > 0 else 0
        color = colors.get(cat, "#6b7280")
        cat_bars += f'''
        <div class="bar-row">
          <span class="bar-label">{cat}</span>
          <div class="bar-container">
            <div class="bar" style="width:{pct}%;background:{color}"></div>
          </div>
          <span class="bar-value">{data["passed"]}/{total_cat}</span>
        </div>'''

    # Generate collection cards
    collection_cards = ""
    for c in sorted(collections, key=lambda x: (x.get("status") != "passed", x.get("name", ""))):
        status_class = "pass" if c.get("status") == "passed" else "fail"
        assertions = c.get("assertions", {})
        passed_a = assertions.get("passed", 0)
        total_a = assertions.get("total", 0)
        pct = (passed_a / total_a * 100) if total_a > 0 else 0

        collection_cards += f'''
        <div class="collection {status_class}">
          <div class="collection-header">
            <span class="collection-name">{c.get("name", "Unknown")}</span>
            <span class="collection-category">{c.get("category", "Other")}</span>
          </div>
          <div class="collection-stats">
            <div class="stat-row">
              <span>Assertions</span>
              <span class="stat-value">{passed_a}/{total_a}</span>
            </div>
            <div class="progress-bar">
              <div class="progress" style="width:{pct}%"></div>
            </div>
          </div>
        </div>'''

    # Generate failures section
    failures_html = ""
    failed_collections = [c for c in collections if c.get("status") != "passed"]
    if failed_collections:
        failures_html = '<h2>Failures</h2>'
        for c in failed_collections:
            failures_html += f'''
            <div class="failure-card">
              <h3>{c.get("name", "Unknown")}</h3>
              <p>Category: {c.get("category", "Other")}</p>
              <p>Failed Assertions: {c.get("assertions", {}).get("failed", 0)}</p>
            </div>'''

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OSDU QA Dashboard - {env}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #0f172a;
      color: #e2e8f0;
      line-height: 1.6;
    }}
    .container {{ display: flex; min-height: 100vh; }}

    /* Sidebar */
    .sidebar {{
      width: 320px;
      background: #1e293b;
      padding: 24px;
      border-right: 1px solid #334155;
      position: fixed;
      height: 100vh;
      overflow-y: auto;
    }}
    .logo {{ font-size: 24px; font-weight: 700; margin-bottom: 8px; }}
    .env-badge {{
      display: inline-block;
      background: #3b82f6;
      color: white;
      padding: 4px 12px;
      border-radius: 16px;
      font-size: 12px;
      margin-bottom: 24px;
    }}
    .timestamp {{ color: #94a3b8; font-size: 12px; margin-bottom: 24px; }}

    /* Stats */
    .stat-card {{
      background: #334155;
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 16px;
    }}
    .stat-label {{ color: #94a3b8; font-size: 14px; }}
    .stat-number {{ font-size: 36px; font-weight: 700; }}
    .stat-number.passed {{ color: #22c55e; }}
    .stat-number.failed {{ color: #ef4444; }}
    .stat-number.warning {{ color: #f59e0b; }}

    /* Category bars */
    .section-title {{ font-size: 12px; text-transform: uppercase; color: #64748b; margin: 24px 0 12px; }}
    .bar-row {{ display: flex; align-items: center; margin: 8px 0; }}
    .bar-label {{ width: 80px; font-size: 13px; color: #94a3b8; }}
    .bar-container {{ flex: 1; height: 8px; background: #1e293b; border-radius: 4px; margin: 0 12px; }}
    .bar {{ height: 100%; border-radius: 4px; transition: width 0.3s; }}
    .bar-value {{ width: 50px; text-align: right; font-size: 13px; color: #64748b; }}

    /* Main content */
    .main {{
      flex: 1;
      margin-left: 320px;
      padding: 24px;
    }}
    .main h1 {{ font-size: 28px; margin-bottom: 24px; }}
    .main h2 {{ font-size: 20px; margin: 32px 0 16px; color: #94a3b8; }}

    /* Collection grid */
    .collection-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 16px;
    }}
    .collection {{
      background: #1e293b;
      border-radius: 12px;
      padding: 16px;
      border-left: 4px solid;
      transition: transform 0.2s;
    }}
    .collection:hover {{ transform: translateY(-2px); }}
    .collection.pass {{ border-color: #22c55e; }}
    .collection.fail {{ border-color: #ef4444; }}
    .collection-header {{ display: flex; justify-content: space-between; margin-bottom: 12px; }}
    .collection-name {{ font-weight: 600; }}
    .collection-category {{
      font-size: 11px;
      background: #334155;
      padding: 2px 8px;
      border-radius: 10px;
      color: #94a3b8;
    }}
    .stat-row {{ display: flex; justify-content: space-between; font-size: 14px; color: #94a3b8; }}
    .stat-value {{ color: #e2e8f0; font-weight: 600; }}
    .progress-bar {{ height: 4px; background: #334155; border-radius: 2px; margin-top: 8px; }}
    .progress {{ height: 100%; background: #22c55e; border-radius: 2px; }}
    .collection.fail .progress {{ background: #ef4444; }}

    /* Failures */
    .failure-card {{
      background: rgba(239, 68, 68, 0.1);
      border: 1px solid #ef4444;
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 12px;
    }}
    .failure-card h3 {{ color: #ef4444; margin-bottom: 8px; }}
    .failure-card p {{ color: #94a3b8; font-size: 14px; }}

    /* Responsive */
    @media (max-width: 768px) {{
      .sidebar {{ width: 100%; height: auto; position: relative; }}
      .main {{ margin-left: 0; }}
      .container {{ flex-direction: column; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="sidebar">
      <div class="logo">OSDU QA Dashboard</div>
      <span class="env-badge">{env}</span>
      <div class="timestamp">{timestamp[:19].replace('T', ' ')}</div>

      <div class="stat-card">
        <div class="stat-label">Pass Rate</div>
        <div class="stat-number {'passed' if pass_rate >= 90 else 'warning' if pass_rate >= 70 else 'failed'}">{pass_rate:.1f}%</div>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
        <div class="stat-card">
          <div class="stat-label">Passed</div>
          <div class="stat-number passed">{passed}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Failed</div>
          <div class="stat-number failed">{failed}</div>
        </div>
      </div>

      <div class="section-title">By Category</div>
      {cat_bars}
    </div>

    <div class="main">
      <h1>Test Collections</h1>
      <div class="collection-grid">
        {collection_cards}
      </div>
      {failures_html}
    </div>
  </div>
</body>
</html>'''

    # Save file
    output_file = output_dir / f"qa-dashboard-{env.replace('/', '-')}-{datetime.now().strftime('%Y-%m-%d')}.html"
    output_file.write_text(html)
    return output_file


def generate_markdown_report(results: dict, output_dir: Path, report_type: str = "comprehensive") -> Path:
    """Generate Markdown report."""

    env = results.get("environment", "unknown")
    timestamp = results.get("timestamp", datetime.now().isoformat())
    collections = results.get("collections", [])
    summary = results.get("summary", {})

    total = len(collections)
    passed = sum(1 for c in collections if c.get("status") == "passed")
    pass_rate = (passed / total * 100) if total > 0 else 0

    # Determine status
    if pass_rate == 100:
        status = "✅ **PASSED**"
    elif pass_rate >= 90:
        status = "⚠️ **PASSED WITH WARNINGS**"
    else:
        status = "❌ **FAILED**"

    # Build report
    report = f"""# OSDU QA Test Report
## {env.upper()} Environment

| Field | Value |
|-------|-------|
| **Environment** | {env} |
| **Test Date** | {timestamp[:10]} |
| **Overall Status** | {status} |
| **Pass Rate** | {pass_rate:.1f}% |

---

## Executive Summary

| Metric | Value |
|--------|-------|
| **Collections Tested** | {total} |
| **Collections Passed** | {passed} |
| **Collections Failed** | {total - passed} |
| **Total Assertions** | {summary.get('total_assertions_passed', 0) + summary.get('total_assertions_failed', 0)} |
| **Assertions Passed** | {summary.get('total_assertions_passed', 0)} |

---

## Results by Collection

| Collection | Category | Status | Assertions | Pass Rate |
|------------|----------|--------|------------|-----------|
"""

    for c in sorted(collections, key=lambda x: x.get("name", "")):
        status_icon = "✅" if c.get("status") == "passed" else "❌"
        assertions = c.get("assertions", {})
        passed_a = assertions.get("passed", 0)
        total_a = assertions.get("total", 0)
        pct = (passed_a / total_a * 100) if total_a > 0 else 0
        report += f"| {c.get('name', 'Unknown')} | {c.get('category', 'Other')} | {status_icon} | {passed_a}/{total_a} | {pct:.1f}% |\n"

    # Add failures section
    failed_collections = [c for c in collections if c.get("status") != "passed"]
    if failed_collections:
        report += "\n---\n\n## Failures\n\n"
        for c in failed_collections:
            report += f"""### {c.get('name', 'Unknown')}

- **Category:** {c.get('category', 'Other')}
- **Failed Assertions:** {c.get('assertions', {}).get('failed', 0)}
- **Duration:** {c.get('duration_ms', 0)}ms

"""

    report += f"""
---

**Report Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    # Save file
    output_file = output_dir / f"qa-report-{env.replace('/', '-')}-{datetime.now().strftime('%Y-%m-%d')}.md"
    output_file.write_text(report)
    return output_file


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate OSDU QA Reports")
    parser.add_argument("--input", "-i", type=Path, help="Input results JSON file")
    parser.add_argument("--output", "-o", type=Path, default=RESULTS_DIR, help="Output directory")
    parser.add_argument("--format", "-f", choices=["md", "html", "both"], default="both", help="Output format")
    parser.add_argument("--type", "-t", choices=["comprehensive", "executive", "category"], default="comprehensive", help="Report type")
    parser.add_argument("--open", action="store_true", help="Open HTML report in browser")

    args = parser.parse_args()

    # Ensure output directory exists
    args.output.mkdir(parents=True, exist_ok=True)

    # Load results
    results = load_results(args.input)
    if not results:
        print("No results found. Run tests first.")
        sys.exit(1)

    # Generate reports
    if args.format in ("md", "both"):
        md_file = generate_markdown_report(results, args.output, args.type)
        print(f"Markdown report: {md_file}")

    if args.format in ("html", "both"):
        html_file = generate_html_dashboard(results, args.output)
        print(f"HTML dashboard: {html_file}")
        if args.open:
            webbrowser.open(f"file://{html_file.absolute()}")


if __name__ == "__main__":
    main()
