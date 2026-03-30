"""Tests for planner module — GitHub Issues fetching via gh CLI."""

import json
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from gh_autoloop import Task
from gh_autoloop.planner import Planner


@pytest.fixture
def planner():
    return Planner()


SAMPLE_ISSUES = [
    {"number": 1, "title": "Fix login bug", "body": "Users cannot log in."},
    {"number": 2, "title": "Update README", "body": "Add install section."},
    {"number": 3, "title": "No body issue", "body": None},
]


class TestPlannerGetTasks:
    """Tests for Planner.get_tasks()."""

    @patch("gh_autoloop.planner.subprocess.run")
    def test_returns_tasks_from_issues(self, mock_run, planner):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(SAMPLE_ISSUES),
            stderr="",
        )
        tasks = planner.get_tasks("/fake/repo")

        assert len(tasks) == 3
        assert tasks[0] == Task(number=1, title="Fix login bug", body="Users cannot log in.")
        assert tasks[1] == Task(number=2, title="Update README", body="Add install section.")
        assert tasks[2] == Task(number=3, title="No body issue", body="")

    @patch("gh_autoloop.planner.subprocess.run")
    def test_calls_gh_cli_with_correct_args(self, mock_run, planner):
        mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
        planner.get_tasks("/my/repo")

        mock_run.assert_called_once_with(
            ["gh", "issue", "list", "--json", "number,title,body", "--state", "open", "--limit", "100"],
            capture_output=True,
            text=True,
            cwd="/my/repo",
            timeout=30,
        )

    @patch("gh_autoloop.planner.subprocess.run")
    def test_label_filter_adds_label_flag(self, mock_run, planner):
        mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
        planner.get_tasks("/repo", label="bug")

        cmd = mock_run.call_args[0][0]
        assert "--label" in cmd
        assert "bug" in cmd

    @patch("gh_autoloop.planner.subprocess.run")
    def test_gh_failure_raises_runtime_error(self, mock_run, planner):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="auth required",
        )
        with pytest.raises(RuntimeError, match="gh issue list failed"):
            planner.get_tasks("/repo")

    @patch("gh_autoloop.planner.subprocess.run")
    def test_empty_issues_returns_empty_list(self, mock_run, planner):
        mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
        tasks = planner.get_tasks("/repo")
        assert tasks == []

    @patch("gh_autoloop.planner.subprocess.run")
    def test_null_body_becomes_empty_string(self, mock_run, planner):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps([{"number": 5, "title": "Test", "body": None}]),
            stderr="",
        )
        tasks = planner.get_tasks("/repo")
        assert tasks[0].body == ""

    @patch("gh_autoloop.planner.subprocess.run")
    def test_timeout_raises_runtime_error(self, mock_run, planner):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="gh", timeout=30)
        with pytest.raises(RuntimeError, match="timed out"):
            planner.get_tasks("/repo")

    @patch("gh_autoloop.planner.subprocess.run")
    def test_empty_stdout_returns_empty_list(self, mock_run, planner):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        tasks = planner.get_tasks("/repo")
        assert tasks == []

    @patch("gh_autoloop.planner.subprocess.run")
    def test_whitespace_stdout_returns_empty_list(self, mock_run, planner):
        mock_run.return_value = MagicMock(returncode=0, stdout="  \n  ", stderr="")
        tasks = planner.get_tasks("/repo")
        assert tasks == []

    @patch("gh_autoloop.planner.subprocess.run")
    def test_invalid_json_raises_runtime_error(self, mock_run, planner):
        mock_run.return_value = MagicMock(returncode=0, stdout="not json", stderr="")
        with pytest.raises(RuntimeError, match="Failed to parse gh output"):
            planner.get_tasks("/repo")
