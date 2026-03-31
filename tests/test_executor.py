"""Tests for executor module — Claude CLI invocation via subprocess."""

import subprocess
from unittest.mock import patch, MagicMock
from io import StringIO

import pytest

from gh_autoloop import Task, ExecutionResult
from gh_autoloop.executor import Executor


@pytest.fixture
def task():
    return Task(number=42, title="Fix the bug", body="Something is broken.")


@pytest.fixture
def executor():
    return Executor(timeout=60)


def make_popen_mock(returncode=0, stdout_text="ok\n"):
    """Create a mock Popen object with streaming stdout."""
    mock_proc = MagicMock()
    mock_proc.stdout = StringIO(stdout_text)
    mock_proc.returncode = returncode
    mock_proc.wait.return_value = returncode
    mock_proc.kill.return_value = None
    return mock_proc


class TestExecutorRun:
    """Tests for Executor.run()."""

    @patch("gh_autoloop.executor.subprocess.Popen")
    def test_successful_execution(self, mock_popen, executor, task):
        mock_popen.return_value = make_popen_mock(returncode=0, stdout_text="Fixed the bug\n")
        result = executor.run(task, "/repo")

        assert result.success is True
        assert result.exit_code == 0
        assert "Fixed the bug" in result.output

    @patch("gh_autoloop.executor.subprocess.Popen")
    def test_failed_execution(self, mock_popen, executor, task):
        mock_popen.return_value = make_popen_mock(returncode=1, stdout_text="Error occurred\n")
        result = executor.run(task, "/repo")

        assert result.success is False
        assert result.exit_code == 1
        assert "Error occurred" in result.output

    @patch("gh_autoloop.executor.subprocess.Popen")
    def test_timeout_returns_failure(self, mock_popen, executor, task):
        mock_proc = MagicMock()
        mock_proc.stdout = StringIO("partial\n")
        mock_proc.returncode = None
        mock_proc.kill.return_value = None

        # First call (with timeout=) raises TimeoutExpired; second call (after kill) returns normally
        mock_proc.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="claude", timeout=60),
            None,
        ]
        mock_popen.return_value = mock_proc

        result = executor.run(task, "/repo")

        assert result.success is False
        assert result.exit_code == -1
        assert "timed out" in result.output.lower()
        mock_proc.kill.assert_called_once()

    @patch("gh_autoloop.executor.subprocess.Popen")
    def test_oserror_returns_failure(self, mock_popen, executor, task):
        mock_popen.side_effect = OSError("No such file or directory")
        result = executor.run(task, "/repo")

        assert result.success is False
        assert result.exit_code == -1
        assert "Failed to launch claude" in result.output

    @patch("gh_autoloop.executor.subprocess.Popen")
    def test_dangerously_skip_permissions_included(self, mock_popen, task):
        executor = Executor(timeout=30)
        mock_popen.return_value = make_popen_mock()
        executor.run(task, "/repo")

        cmd = mock_popen.call_args[0][0]
        assert "--dangerously-skip-permissions" in cmd

    @patch("gh_autoloop.executor.subprocess.Popen")
    def test_command_includes_print_flag(self, mock_popen, executor, task):
        mock_popen.return_value = make_popen_mock()
        executor.run(task, "/repo")

        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == "claude"
        assert "--print" in cmd

    @patch("gh_autoloop.executor.subprocess.Popen")
    def test_prompt_passed_as_last_arg(self, mock_popen, executor, task):
        mock_popen.return_value = make_popen_mock()
        executor.run(task, "/repo")

        cmd = mock_popen.call_args[0][0]
        assert cmd[-1] == task.to_prompt()

    @patch("gh_autoloop.executor.subprocess.Popen")
    def test_cwd_is_repo_path(self, mock_popen, executor, task):
        mock_popen.return_value = make_popen_mock()
        executor.run(task, "/my/project")

        kwargs = mock_popen.call_args[1]
        assert kwargs["cwd"] == "/my/project"

    @patch("gh_autoloop.executor.subprocess.Popen")
    def test_multiline_output_captured(self, mock_popen, executor, task):
        mock_popen.return_value = make_popen_mock(
            stdout_text="line 1\nline 2\nline 3\n"
        )
        result = executor.run(task, "/repo")
        assert result.output == "line 1\nline 2\nline 3\n"

    @patch("gh_autoloop.executor.subprocess.Popen")
    def test_default_timeout_is_600(self, mock_popen, task):
        executor = Executor()
        assert executor.timeout == 600
