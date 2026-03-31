"""Integration tests — end-to-end flow with all components mocked at subprocess level."""

import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from gh_autoloop.loop import AutoLoop


MOCK_ISSUES = [
    {"number": 10, "title": "Fix typo", "body": "Typo in README"},
    {"number": 11, "title": "Add feature", "body": "New feature needed"},
]


def make_subprocess_run_mock(
    issues=None,
    test_fails=False,
    push_fails=False,
):
    """Create a subprocess.run mock for planner, verifier, git_ops."""
    if issues is None:
        issues = MOCK_ISSUES

    def side_effect(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""

        if not isinstance(cmd, list):
            return result

        if cmd[0] == "gh" and "issue" in cmd:
            result.stdout = json.dumps(issues)
            return result

        if cmd[0] == "pytest":
            if test_fails:
                result.returncode = 1
                result.stdout = "1 failed"
                result.stderr = "ERRORS"
            else:
                result.stdout = "2 passed"
            return result

        if cmd[:2] == ["git", "status"]:
            result.stdout = " M some_file.py\n"
            return result

        if cmd[:2] == ["git", "add"]:
            return result

        if cmd[:2] == ["git", "commit"]:
            return result

        if cmd[:2] == ["git", "push"]:
            if push_fails:
                result.returncode = 1
                result.stderr = "remote rejected"
            return result

        if cmd[:2] == ["git", "rev-parse"]:
            result.stdout = "abc1234\n"
            return result

        if cmd[:2] == ["git", "checkout"]:
            return result

        if cmd[:2] == ["git", "clean"]:
            return result

        return result

    return side_effect


def make_popen_mock(executor_fails=None):
    """Create a subprocess.Popen mock for the executor."""
    if executor_fails is None:
        executor_fails = set()

    def side_effect(cmd, **kwargs):
        mock_proc = MagicMock()
        mock_proc.kill.return_value = None

        prompt = cmd[-1]
        for num in executor_fails:
            if f"#{num}" in prompt:
                mock_proc.stdout = StringIO("Claude failed\n")
                mock_proc.returncode = 1
                mock_proc.wait.return_value = 1
                return mock_proc

        mock_proc.stdout = StringIO("Applied fix successfully\n")
        mock_proc.returncode = 0
        mock_proc.wait.return_value = 0
        return mock_proc

    return side_effect


def make_which_mock(pytest_found=True):
    """Create a shutil.which mock."""
    def side_effect(exe):
        if exe == "pytest" and pytest_found:
            return "/usr/bin/pytest"
        return None
    return side_effect


class TestIntegrationAllSuccess:
    """Full run where every issue is fixed successfully."""

    @patch("gh_autoloop.verifier.shutil.which")
    @patch("gh_autoloop.executor.subprocess.Popen")
    @patch("subprocess.run")
    def test_all_issues_succeed(self, mock_run, mock_popen, mock_which, tmp_path):
        mock_run.side_effect = make_subprocess_run_mock()
        mock_popen.side_effect = make_popen_mock()
        mock_which.side_effect = make_which_mock()

        loop = AutoLoop(repo_path=str(tmp_path))
        results = loop.run()

        assert len(results) == 2
        assert all(r.status == "success" for r in results)
        assert all(r.commit == "abc1234" for r in results)

        repo_name = tmp_path.name
        result_file = Path.home() / ".gh-autoloop" / "results" / f"{repo_name}.json"
        assert result_file.exists()
        data = json.loads(result_file.read_text())
        assert data["summary"]["success"] == 2
        assert data["summary"]["failed"] == 0


class TestIntegrationExecutorFailure:
    """Run where executor fails on first issue, second succeeds."""

    @patch("gh_autoloop.verifier.shutil.which")
    @patch("gh_autoloop.executor.subprocess.Popen")
    @patch("subprocess.run")
    def test_first_fails_second_succeeds(self, mock_run, mock_popen, mock_which, tmp_path):
        mock_run.side_effect = make_subprocess_run_mock()
        mock_popen.side_effect = make_popen_mock(executor_fails={10})
        mock_which.side_effect = make_which_mock()

        loop = AutoLoop(repo_path=str(tmp_path))
        results = loop.run()

        assert len(results) == 2
        assert results[0].status == "failed"
        assert results[1].status == "success"
        assert results[1].commit == "abc1234"


class TestIntegrationTestFailure:
    """Run where tests fail after executor succeeds."""

    @patch("gh_autoloop.verifier.shutil.which")
    @patch("gh_autoloop.executor.subprocess.Popen")
    @patch("subprocess.run")
    def test_test_failure_triggers_rollback(self, mock_run, mock_popen, mock_which, tmp_path):
        mock_run.side_effect = make_subprocess_run_mock(
            issues=[MOCK_ISSUES[0]], test_fails=True
        )
        mock_popen.side_effect = make_popen_mock()
        mock_which.side_effect = make_which_mock()

        loop = AutoLoop(repo_path=str(tmp_path))
        results = loop.run()

        assert len(results) == 1
        assert results[0].status == "failed"
        assert "Tests failed" in results[0].error


class TestIntegrationNoIssues:
    """Run with no open issues."""

    @patch("gh_autoloop.verifier.shutil.which")
    @patch("gh_autoloop.executor.subprocess.Popen")
    @patch("subprocess.run")
    def test_no_issues_returns_empty(self, mock_run, mock_popen, mock_which, tmp_path):
        mock_run.side_effect = make_subprocess_run_mock(issues=[])
        mock_popen.side_effect = make_popen_mock()
        mock_which.side_effect = make_which_mock()

        loop = AutoLoop(repo_path=str(tmp_path))
        results = loop.run()

        assert results == []


class TestIntegrationMaxIter:
    """Run with max_iter limiting processed issues."""

    @patch("gh_autoloop.verifier.shutil.which")
    @patch("gh_autoloop.executor.subprocess.Popen")
    @patch("subprocess.run")
    def test_max_iter_limits_processing(self, mock_run, mock_popen, mock_which, tmp_path):
        mock_run.side_effect = make_subprocess_run_mock()
        mock_popen.side_effect = make_popen_mock()
        mock_which.side_effect = make_which_mock()

        loop = AutoLoop(repo_path=str(tmp_path), max_iter=1)
        results = loop.run()

        assert len(results) == 1
        assert results[0].status == "success"


class TestIntegrationPushFailure:
    """Run where push fails but commit is kept."""

    @patch("gh_autoloop.verifier.shutil.which")
    @patch("gh_autoloop.executor.subprocess.Popen")
    @patch("subprocess.run")
    def test_push_failure_still_succeeds(self, mock_run, mock_popen, mock_which, tmp_path):
        mock_run.side_effect = make_subprocess_run_mock(
            issues=[MOCK_ISSUES[0]], push_fails=True
        )
        mock_popen.side_effect = make_popen_mock()
        mock_which.side_effect = make_which_mock()

        loop = AutoLoop(repo_path=str(tmp_path))
        results = loop.run()

        assert len(results) == 1
        assert results[0].status == "success"
        assert results[0].commit == "abc1234"


class TestIntegrationNoTestTool:
    """Run where no test tool is found — should still succeed (tests skipped)."""

    @patch("gh_autoloop.verifier.shutil.which")
    @patch("gh_autoloop.executor.subprocess.Popen")
    @patch("subprocess.run")
    def test_no_test_tool_skips_verification(self, mock_run, mock_popen, mock_which, tmp_path):
        mock_run.side_effect = make_subprocess_run_mock()
        mock_popen.side_effect = make_popen_mock()
        mock_which.return_value = None  # No test tool found

        loop = AutoLoop(repo_path=str(tmp_path))
        results = loop.run()

        assert len(results) == 2
        assert all(r.status == "success" for r in results)
