"""Tests for executor module — Claude CLI invocation via subprocess."""

import subprocess
from unittest.mock import patch, MagicMock

import pytest

from gh_autoloop import Task, ExecutionResult
from gh_autoloop.executor import Executor


@pytest.fixture
def task():
    return Task(number=42, title="Fix the bug", body="Something is broken.")


@pytest.fixture
def executor():
    return Executor(timeout=60)


class TestExecutorRun:
    """Tests for Executor.run()."""

    @patch("gh_autoloop.executor.subprocess.run")
    def test_successful_execution(self, mock_run, executor, task):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Fixed the bug",
            stderr="",
        )
        result = executor.run(task, "/repo")

        assert result.success is True
        assert result.exit_code == 0
        assert "Fixed the bug" in result.output

    @patch("gh_autoloop.executor.subprocess.run")
    def test_failed_execution(self, mock_run, executor, task):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error occurred",
        )
        result = executor.run(task, "/repo")

        assert result.success is False
        assert result.exit_code == 1
        assert "Error occurred" in result.output

    @patch("gh_autoloop.executor.subprocess.run")
    def test_timeout_returns_failure(self, mock_run, executor, task):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=60)
        result = executor.run(task, "/repo")

        assert result.success is False
        assert result.exit_code == -1
        assert "timed out" in result.output.lower()

    @patch("gh_autoloop.executor.subprocess.run")
    def test_oserror_returns_failure(self, mock_run, executor, task):
        mock_run.side_effect = OSError("No such file or directory")
        result = executor.run(task, "/repo")

        assert result.success is False
        assert result.exit_code == -1
        assert "Failed to launch claude" in result.output

    @patch("gh_autoloop.executor.subprocess.run")
    def test_skip_permissions_flag_included(self, mock_run, task):
        executor = Executor(timeout=30, skip_permissions=True)
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        executor.run(task, "/repo")

        cmd = mock_run.call_args[0][0]
        assert "--dangerously-skip-permissions" in cmd

    @patch("gh_autoloop.executor.subprocess.run")
    def test_skip_permissions_false_omits_flag(self, mock_run, task):
        executor = Executor(timeout=30, skip_permissions=False)
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        executor.run(task, "/repo")

        cmd = mock_run.call_args[0][0]
        assert "--dangerously-skip-permissions" not in cmd

    @patch("gh_autoloop.executor.subprocess.run")
    def test_command_includes_print_and_output_format(self, mock_run, executor, task):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        executor.run(task, "/repo")

        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "claude"
        assert "--print" in cmd
        assert "--output-format" in cmd
        assert "text" in cmd

    @patch("gh_autoloop.executor.subprocess.run")
    def test_prompt_passed_as_last_arg(self, mock_run, executor, task):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        executor.run(task, "/repo")

        cmd = mock_run.call_args[0][0]
        assert cmd[-1] == task.to_prompt()

    @patch("gh_autoloop.executor.subprocess.run")
    def test_cwd_is_repo_path(self, mock_run, executor, task):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        executor.run(task, "/my/project")

        kwargs = mock_run.call_args[1]
        assert kwargs["cwd"] == "/my/project"

    @patch("gh_autoloop.executor.subprocess.run")
    def test_timeout_passed_to_subprocess(self, mock_run, task):
        executor = Executor(timeout=120)
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        executor.run(task, "/repo")

        kwargs = mock_run.call_args[1]
        assert kwargs["timeout"] == 120

    @patch("gh_autoloop.executor.subprocess.run")
    def test_output_combines_stdout_and_stderr(self, mock_run, executor, task):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="stdout content",
            stderr="stderr content",
        )
        result = executor.run(task, "/repo")
        assert result.output == "stdout contentstderr content"

    @patch("gh_autoloop.executor.subprocess.run")
    def test_default_skip_permissions_is_true(self, mock_run, task):
        executor = Executor()
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        executor.run(task, "/repo")

        cmd = mock_run.call_args[0][0]
        assert "--dangerously-skip-permissions" in cmd
