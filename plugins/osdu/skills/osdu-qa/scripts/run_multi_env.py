# /// script
# requires-python = ">=3.11"
# dependencies = [
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
OSDU QA Multi-Environment Test Runner

Execute the same test collection across multiple environments in parallel.
"""

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

SKILL_DIR = Path(__file__).parent.parent
RESULTS_DIR = SKILL_DIR / "results"

console = Console()


def run_tests_on_environment(environment: str, collection: str) -> dict:
    """Run tests on a specific environment.

    Args:
        environment: Environment target (e.g., 'cimpl/temp')
        collection: Collection ID to run

    Returns:
        Result dictionary with status and metrics
    """
    result = {
        "environment": environment,
        "collection": collection,
        "status": "pending",
        "start_time": datetime.now().isoformat(),
        "error": None
    }

    try:
        # Switch environment
        switch_cmd = [
            "uv", "run",
            str(SKILL_DIR / "scripts" / "env_manager.py"),
            "use", environment
        ]
        subprocess.run(switch_cmd, check=True, capture_output=True, text=True)

        # Run test
        test_cmd = [
            "uv", "run",
            str(SKILL_DIR / "scripts" / "osdu_test.py"),
            "run", collection
        ]
        test_result = subprocess.run(test_cmd, capture_output=True, text=True)

        # Parse output
        output = test_result.stdout + test_result.stderr

        # Extract metrics from output
        if "PASSED" in output:
            result["status"] = "passed"
        elif "FAILED" in output:
            result["status"] = "failed"
        else:
            result["status"] = "unknown"

        # Try to extract assertion counts
        import re
        assertions_match = re.search(r'Assertions\s+(\d+)/(\d+)', output)
        if assertions_match:
            result["assertions_passed"] = int(assertions_match.group(1))
            result["assertions_total"] = int(assertions_match.group(2))

        requests_match = re.search(r'Requests\s+(\d+)/(\d+)', output)
        if requests_match:
            result["requests_passed"] = int(requests_match.group(1))
            result["requests_total"] = int(requests_match.group(2))

        result["output"] = output

    except subprocess.CalledProcessError as e:
        result["status"] = "error"
        result["error"] = str(e)
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    result["end_time"] = datetime.now().isoformat()
    return result


def run_multi_environment(
    environments: list[str],
    collection: str,
    parallel: bool = True,
    max_workers: int = 3
) -> list[dict]:
    """Run tests across multiple environments.

    Args:
        environments: List of environment targets
        collection: Collection ID to run
        parallel: Whether to run in parallel
        max_workers: Maximum concurrent workers

    Returns:
        List of results for each environment
    """
    results = []

    console.print(Panel.fit(
        f"[bold]Multi-Environment Test Run[/bold]\n\n"
        f"Collection: {collection}\n"
        f"Environments: {', '.join(environments)}\n"
        f"Parallel: {parallel}"
    ))

    if parallel:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(run_tests_on_environment, env, collection): env
                for env in environments
            }

            for future in as_completed(futures):
                env = futures[future]
                try:
                    result = future.result()
                    results.append(result)

                    # Display result
                    status_color = "green" if result["status"] == "passed" else "red"
                    console.print(
                        f"[{status_color}]{result['status'].upper()}[/{status_color}] "
                        f"{env}: {result.get('assertions_passed', '?')}/{result.get('assertions_total', '?')}"
                    )
                except Exception as e:
                    console.print(f"[red]ERROR[/red] {env}: {e}")
    else:
        for env in environments:
            result = run_tests_on_environment(env, collection)
            results.append(result)

            status_color = "green" if result["status"] == "passed" else "red"
            console.print(
                f"[{status_color}]{result['status'].upper()}[/{status_color}] "
                f"{env}: {result.get('assertions_passed', '?')}/{result.get('assertions_total', '?')}"
            )

    return results


def generate_comparison(results: list[dict]) -> None:
    """Generate comparison table from results."""
    table = Table(title="Environment Comparison")
    table.add_column("Environment", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Assertions", justify="right")
    table.add_column("Pass Rate", justify="right")

    for result in results:
        status_style = "green" if result["status"] == "passed" else "red"
        passed = result.get("assertions_passed", 0)
        total = result.get("assertions_total", 0)
        rate = (passed / total * 100) if total > 0 else 0

        table.add_row(
            result["environment"],
            f"[{status_style}]{result['status'].upper()}[/{status_style}]",
            f"{passed}/{total}",
            f"{rate:.1f}%"
        )

    console.print()
    console.print(table)


def save_results(results: list[dict], collection: str) -> Path:
    """Save multi-environment results."""
    RESULTS_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_multi_{collection}.json"
    filepath = RESULTS_DIR / filename

    output = {
        "type": "multi_environment",
        "collection": collection,
        "timestamp": datetime.now().isoformat(),
        "results": results
    }

    filepath.write_text(json.dumps(output, indent=2))
    console.print(f"\n[green]Results saved:[/green] {filepath}")
    return filepath


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="OSDU QA Multi-Environment Runner")
    parser.add_argument("collection", help="Collection ID to run")
    parser.add_argument(
        "-e", "--environments",
        nargs="+",
        default=None,
        help="Environments to test (default: all configured environments)"
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Run sequentially instead of parallel"
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=3,
        help="Maximum parallel workers"
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save results to file"
    )

    args = parser.parse_args()

    # Resolve default environments from config if none specified
    if args.environments is None:
        sys.path.insert(0, str(Path(__file__).parent))
        from common import load_environments
        env_config = load_environments()
        envs = []
        for platform_name, platform in env_config.get("platforms", {}).items():
            for env_name in platform.get("environments", {}).keys():
                envs.append(f"{platform_name}/{env_name}")
        if not envs:
            console.print("[red]No environments configured.[/red]")
            console.print("Add environments with: [cyan]env add <platform>/<name> --host ... --partition ... --auth-type ...[/cyan]")
            sys.exit(1)
        args.environments = envs

    # Run tests
    results = run_multi_environment(
        environments=args.environments,
        collection=args.collection,
        parallel=not args.sequential,
        max_workers=args.workers
    )

    # Generate comparison
    generate_comparison(results)

    # Save results
    if not args.no_save:
        save_results(results, args.collection)


if __name__ == "__main__":
    main()
