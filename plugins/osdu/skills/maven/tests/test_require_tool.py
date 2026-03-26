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
Unit tests for require_tool() function in check.py.

Tests the generic tool requirement checking pattern that can be reused
for any external CLI dependency.
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add the scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from check import require_tool  # noqa: E402

# =============================================================================
# Test: require_tool() Function Signature
# =============================================================================


class TestRequireToolSignature:
    """Tests for require_tool function signature and interface."""

    def test_require_tool_function_exists(self):
        """Verify require_tool function is importable."""
        assert callable(require_tool)

    def test_require_tool_accepts_three_arguments(self):
        """Verify require_tool accepts name, check_cmd, and install_hints."""
        import inspect

        sig = inspect.signature(require_tool)
        params = list(sig.parameters.keys())
        assert "name" in params
        assert "check_cmd" in params
        assert "install_hints" in params

    def test_require_tool_has_docstring(self):
        """Verify require_tool has documentation."""
        assert require_tool.__doc__ is not None
        assert "tool" in require_tool.__doc__.lower()


# =============================================================================
# Test: require_tool() Success Cases
# =============================================================================


class TestRequireToolSuccess:
    """Tests for require_tool when tool is available."""

    @patch("check.subprocess.run")
    def test_require_tool_succeeds_when_tool_available(self, mock_run):
        """require_tool completes without error when tool is found."""
        mock_run.return_value = MagicMock(returncode=0)

        # Should not raise or exit
        require_tool("test-tool", ["test-tool", "--version"], {"macOS": "brew install test-tool"})

        mock_run.assert_called_once()

    @patch("check.subprocess.run")
    def test_require_tool_checks_return_code(self, mock_run):
        """require_tool verifies subprocess return code is 0."""
        mock_run.return_value = MagicMock(returncode=0)

        require_tool("git", ["git", "--version"], {"macOS": "brew install git"})

        # Verify the call was made with the check command
        call_args = mock_run.call_args
        assert call_args[0][0] == ["git", "--version"]


# =============================================================================
# Test: require_tool() Failure Cases
# =============================================================================


class TestRequireToolFailure:
    """Tests for require_tool when tool is not available."""

    @patch("check.subprocess.run")
    def test_require_tool_exits_on_file_not_found(self, mock_run):
        """require_tool exits when tool command not found."""
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(SystemExit) as exc_info:
            require_tool(
                "missing-tool",
                ["missing-tool", "--version"],
                {"macOS": "brew install missing-tool"},
            )

        assert exc_info.value.code == 1

    @patch("check.subprocess.run")
    def test_require_tool_exits_on_nonzero_return(self, mock_run):
        """require_tool exits when tool returns non-zero."""
        mock_run.return_value = MagicMock(returncode=1)

        with pytest.raises(SystemExit) as exc_info:
            require_tool(
                "broken-tool", ["broken-tool", "--version"], {"macOS": "brew install broken-tool"}
            )

        assert exc_info.value.code == 1

    @patch("check.subprocess.run")
    def test_require_tool_exits_on_timeout(self, mock_run):
        """require_tool exits when tool command times out."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=5)

        with pytest.raises(SystemExit) as exc_info:
            require_tool(
                "slow-tool", ["slow-tool", "--version"], {"macOS": "brew install slow-tool"}
            )

        assert exc_info.value.code == 1


# =============================================================================
# Test: require_tool() Error Messages
# =============================================================================


class TestRequireToolErrorMessages:
    """Tests for require_tool error message formatting."""

    @patch("check.subprocess.run")
    def test_error_includes_tool_name(self, mock_run, capsys):
        """Error message includes the tool name."""
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(SystemExit):
            require_tool(
                "my-special-tool",
                ["my-special-tool", "--version"],
                {"macOS": "brew install my-special-tool"},
            )

        captured = capsys.readouterr()
        assert "my-special-tool" in captured.err

    @patch("check.subprocess.run")
    def test_error_includes_install_hints(self, mock_run, capsys):
        """Error message includes platform-specific install hints."""
        mock_run.side_effect = FileNotFoundError()

        install_hints = {
            "macOS": "brew install test-tool",
            "Linux": "apt install test-tool",
            "Windows": "winget install test-tool",
        }

        with pytest.raises(SystemExit):
            require_tool("test-tool", ["test-tool", "--version"], install_hints)

        captured = capsys.readouterr()
        assert "brew install test-tool" in captured.err
        assert "apt install test-tool" in captured.err
        assert "winget install test-tool" in captured.err

    @patch("check.subprocess.run")
    def test_error_mentions_rerun(self, mock_run, capsys):
        """Error message tells user to re-run command."""
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(SystemExit):
            require_tool("test-tool", ["test-tool", "--version"], {"macOS": "brew install"})

        captured = capsys.readouterr()
        assert "re-run" in captured.err.lower()


# =============================================================================
# Test: require_tool() subprocess Configuration
# =============================================================================


class TestRequireToolSubprocessConfig:
    """Tests for subprocess configuration in require_tool."""

    @patch("check.subprocess.run")
    def test_uses_capture_output(self, mock_run):
        """require_tool captures subprocess output."""
        mock_run.return_value = MagicMock(returncode=0)

        require_tool("git", ["git", "--version"], {"macOS": "brew install git"})

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs.get("capture_output") is True

    @patch("check.subprocess.run")
    def test_uses_timeout(self, mock_run):
        """require_tool uses a timeout for subprocess."""
        mock_run.return_value = MagicMock(returncode=0)

        require_tool("git", ["git", "--version"], {"macOS": "brew install git"})

        call_kwargs = mock_run.call_args[1]
        assert "timeout" in call_kwargs
        assert isinstance(call_kwargs["timeout"], int | float)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
