"""Tests for verifier module — test command auto-detection and execution."""

import subprocess
from unittest.mock import patch, MagicMock

import pytest

from gh_autoloop import VerifyResult
from gh_autoloop.verifier import Verifier, TEST_COMMANDS, VERIFY_TIMEOUT


@pytest.fixture
def verifier():
    return Verifier()


class TestVerifierVerify:
    """Tests for Verifier.verify()."""

    @patch("gh_autoloop.verifier.subprocess.run")
    @patch("gh_autoloop.verifier.shutil.which")
    def test_pytest_passes(self, mock_which, mock_run, verifier):
        mock_which.return_value = "/usr/bin/pytest"
        mock_run.return_value = MagicMock(returncode=0, stdout="3 passed", stderr="")

        result = verifier.verify("/repo")

        assert result.status == "passed"
        assert result.passed is True
        mock_run.assert_called_once_with(
            ["pytest", "--tb=short", "-q"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd="/repo",
            timeout=VERIFY_TIMEOUT,
        )

    @patch("gh_autoloop.verifier.subprocess.run")
    @patch("gh_autoloop.verifier.shutil.which")
    def test_pytest_fails(self, mock_which, mock_run, verifier):
        mock_which.return_value = "/usr/bin/pytest"
        mock_run.return_value = MagicMock(returncode=1, stdout="1 failed", stderr="ERRORS")

        result = verifier.verify("/repo")

        assert result.status == "failed"
        assert result.passed is False
        assert "1 failed" in result.output

    @patch("gh_autoloop.verifier.shutil.which")
    def test_no_test_tool_returns_skipped(self, mock_which, verifier):
        mock_which.return_value = None  # No tool found

        result = verifier.verify("/repo")

        assert result.status == "skipped"
        assert result.passed is True
        assert "No test command found" in result.output

    @patch("gh_autoloop.verifier.subprocess.run")
    @patch("gh_autoloop.verifier.shutil.which")
    def test_falls_through_to_npm_test(self, mock_which, mock_run, verifier):
        # pytest not found, npm found
        mock_which.side_effect = lambda exe: "/usr/bin/npm" if exe == "npm" else None
        mock_run.return_value = MagicMock(returncode=0, stdout="tests passed", stderr="")

        result = verifier.verify("/repo")

        assert result.status == "passed"
        mock_run.assert_called_once_with(
            ["npm", "test"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd="/repo",
            timeout=VERIFY_TIMEOUT,
        )

    @patch("gh_autoloop.verifier.subprocess.run")
    @patch("gh_autoloop.verifier.shutil.which")
    def test_falls_through_to_make_test(self, mock_which, mock_run, verifier):
        # pytest and npm not found, make found
        mock_which.side_effect = lambda exe: "/usr/bin/make" if exe == "make" else None
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")

        result = verifier.verify("/repo")

        assert result.status == "passed"
        mock_run.assert_called_once_with(
            ["make", "test"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd="/repo",
            timeout=VERIFY_TIMEOUT,
        )

    @patch("gh_autoloop.verifier.subprocess.run")
    @patch("gh_autoloop.verifier.shutil.which")
    def test_test_command_timeout_returns_failed(self, mock_which, mock_run, verifier):
        mock_which.return_value = "/usr/bin/pytest"
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="pytest", timeout=300)

        result = verifier.verify("/repo")

        assert result.status == "failed"
        assert "timed out" in result.output

    @patch("gh_autoloop.verifier.shutil.which")
    def test_test_commands_is_tuples(self, mock_which):
        """Verify TEST_COMMANDS structure is (exe_name, cmd_list) tuples."""
        for entry in TEST_COMMANDS:
            assert isinstance(entry, tuple)
            assert len(entry) == 2
            exe, cmd = entry
            assert isinstance(exe, str)
            assert isinstance(cmd, list)
            assert cmd[0] == exe


class TestVerifyResult:
    """Tests for the VerifyResult dataclass."""

    def test_passed_status_is_passed(self):
        r = VerifyResult(status="passed", output="ok")
        assert r.passed is True

    def test_skipped_status_is_passed(self):
        r = VerifyResult(status="skipped", output="no tests")
        assert r.passed is True

    def test_failed_status_is_not_passed(self):
        r = VerifyResult(status="failed", output="errors")
        assert r.passed is False
