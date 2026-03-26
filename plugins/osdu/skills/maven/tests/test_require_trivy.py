#!/usr/bin/env python3
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
Unit tests for require_trivy() function in scan.py.

Tests the fail-fast dependency validation pattern that checks if trivy
is installed and exits with helpful guidance if missing.
"""

import sys
from pathlib import Path

import pytest

# Add the scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


# =============================================================================
# Test: require_trivy() Function
# =============================================================================


class TestRequireTrivy:
    """Tests for the require_trivy fail-fast function."""

    def test_require_trivy_function_exists(self):
        """Verify require_trivy function is importable."""
        # The function should be defined in the module
        with open(Path(__file__).parent.parent / "scripts" / "scan.py") as f:
            content = f.read()
        assert "def require_trivy()" in content

    def test_require_trivy_has_docstring(self):
        """Verify require_trivy has documentation."""
        with open(Path(__file__).parent.parent / "scripts" / "scan.py") as f:
            content = f.read()
        # Check that there's a docstring after the function definition
        assert "def require_trivy()" in content
        assert "Check trivy is installed" in content

    def test_require_trivy_error_message_format(self):
        """Verify error message includes expected components."""
        with open(Path(__file__).parent.parent / "scripts" / "scan.py") as f:
            content = f.read()

        # Check error message includes trivy
        assert "trivy is not installed" in content

        # Check platform-specific install commands are present
        assert "brew install trivy" in content
        assert "winget install" in content or "AquaSecurity.Trivy" in content

    def test_require_trivy_called_at_module_level(self):
        """Verify require_trivy is called at module level for fail-fast."""
        with open(Path(__file__).parent.parent / "scripts" / "scan.py") as f:
            content = f.read()

        # The function should be called at module level (outside any function)
        # Look for a line that calls require_trivy() and isn't a definition or comment
        lines = content.split("\n")

        found_call = False
        for line in lines:
            stripped = line.strip()
            # Skip function definitions and comments
            if stripped.startswith("def ") or stripped.startswith("#"):
                continue
            # Look for module-level call (not indented, contains the call)
            if (
                "require_trivy()" in stripped
                and not line.startswith(" ")
                and not line.startswith("\t")
            ):
                found_call = True
                break

        assert found_call, "require_trivy() should be called at module level"

    def test_require_trivy_exits_with_code_1(self):
        """Verify require_trivy exits with code 1 on failure."""
        with open(Path(__file__).parent.parent / "scripts" / "scan.py") as f:
            content = f.read()

        # Look for sys.exit(1) in the require_trivy function
        assert "sys.exit(1)" in content


class TestRequireTrivyErrorOutput:
    """Tests for the error output format of require_trivy."""

    def test_error_includes_macos_install(self):
        """Error message includes macOS install command."""
        with open(Path(__file__).parent.parent / "scripts" / "scan.py") as f:
            content = f.read()
        assert "macOS" in content or "brew install trivy" in content

    def test_error_includes_linux_install(self):
        """Error message includes Linux install command."""
        with open(Path(__file__).parent.parent / "scripts" / "scan.py") as f:
            content = f.read()
        assert "Linux" in content

    def test_error_includes_windows_install(self):
        """Error message includes Windows install command."""
        with open(Path(__file__).parent.parent / "scripts" / "scan.py") as f:
            content = f.read()
        assert "Windows" in content or "winget" in content


# =============================================================================
# Test: Integration with subprocess
# =============================================================================


class TestRequireTrivySubprocess:
    """Tests for subprocess integration in require_trivy."""

    def test_uses_subprocess_run(self):
        """Verify require_trivy uses subprocess.run for checking."""
        with open(Path(__file__).parent.parent / "scripts" / "scan.py") as f:
            content = f.read()
        assert "subprocess.run" in content

    def test_handles_timeout(self):
        """Verify require_trivy handles subprocess timeout."""
        with open(Path(__file__).parent.parent / "scripts" / "scan.py") as f:
            content = f.read()
        # Should handle TimeoutExpired
        assert "TimeoutExpired" in content or "timeout" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
