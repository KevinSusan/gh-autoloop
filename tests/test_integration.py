"""Integration tests — end-to-end flow with all components mocked at subprocess level."""

import json
from unittest.mock import patch, MagicMock

import pytest

from gh_autoloop.loop import AutoLoop


MOCK_ISSUES = [
    {"number": 10, "title": "Fix typo", "body": "Typo in README"},
    {"number": 11, "title": "Add feature", "body": "New feature needed"},
]


def make_subprocess_mock(
    issues=None,
    executor_fails=None,
    test_fails=False,
    push_fails=False,
    pytest_found=True,
):
    """Create a subprocess.run mock that routes calls based on command.

    Args:
        issues: list of issue dicts to return from gh CLI
        executor_fails: set of issue numbers where executor should fail
        test_fails: whether pytest should fail
        push_fails: whether git push should fail
        pytest_found: whether pytest is on PATH
    """
    if issues is None:
        issues = MOCK_ISSUES
    if executor_fails is None:
        executor_fails = set()

    def side_effect(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""

        if not isinstance(cmd, list):
            return result

        # gh issue list
        if cmd[0] == "gh" and "issue" in cmd:
            result.stdout = json.dumps(issues)
            return result

        # claude CLI
        if cmd[0] == "claude":
            prompt = cmd[-1]
            for num in executor_fails:
                if f"#{num}" in prompt:
                    result.returncode = 1
                    result.stderr = "Claude failed"
                    return result
            result.stdout = "Applied fix successfully"
            return result

        # pytest
        if cmd[0] == "pytest":
            if test_fails:
                result.returncode = 1
                result.stdout = "1 failed"
                result.stderr = "ERRORS"
            else:
                result.stdout = "2 passed"
            return result

        # git status --porcelain
        if cmd[:2] == ["git", "status"]:
            result.stdout = " M some_file.py\n"
            return result

        # git add
        if cmd[:2] == ["git", "add"]:
            return result

        # git commit
        if cmd[:2] == ["git", "commit"]:
            return result

        # git push
        if cmd[:2] == ["git", "push"]:
            if push_fails:
                result.returncode = 1
                result.stderr = "remote rejected"
            return result

        # git rev-parse
        if cmd[:2] == ["git", "rev-parse"]:
            result.stdout = "abc1234\n"
            return result

        # git checkout (rollback)
        if cmd[:2] == ["git", "checkout"]:
            return result

        # git clean (rollback)
        if cmd[:2] == ["git", "clean"]:
            return result

        return result

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
    @patch("subprocess.run")
    def test_all_issues_succeed(self, mock_run, mock_which, tmp_path):
        mock_run.side_effect = make_subprocess_mock()
        mock_which.side_effect = make_which_mock()

        loop = AutoLoop(repo_path=str(tmp_path))
        results = loop.run()

        assert len(results) == 2
        assert all(r.status == "success" for r in results)
        assert all(r.commit == "abc1234" for r in results)

        # Check result file was written
        result_file = tmp_path / "loop_result.json"
        assert result_file.exists()
        data = json.loads(result_file.read_text())
        assert data["summary"]["success"] == 2
        assert data["summary"]["failed"] == 0


class TestIntegrationExecutorFailure:
    """Run where executor fails on first issue, second succeeds."""

    @patch("gh_autoloop.verifier.shutil.which")
    @patch("subprocess.run")
    def test_first_fails_second_succeeds(self, mock_run, mock_which, tmp_path):
        mock_run.side_effect = make_subprocess_mock(executor_fails={10})
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
    @patch("subprocess.run")
    def test_test_failure_triggers_rollback(self, mock_run, mock_which, tmp_path):
        mock_run.side_effect = make_subprocess_mock(
            issues=[MOCK_ISSUES[0]], test_fails=True
        )
        mock_which.side_effect = make_which_mock()

        loop = AutoLoop(repo_path=str(tmp_path))
        results = loop.run()

        assert len(results) == 1
        assert results[0].status == "failed"
        assert "Tests failed" in results[0].error


class TestIntegrationNoIssues:
    """Run with no open issues."""

    @patch("gh_autoloop.verifier.shutil.which")
    @patch("subprocess.run")
    def test_no_issues_returns_empty(self, mock_run, mock_which, tmp_path):
        mock_run.side_effect = make_subprocess_mock(issues=[])
        mock_which.side_effect = make_which_mock()

        loop = AutoLoop(repo_path=str(tmp_path))
        results = loop.run()

        assert results == []
        assert not (tmp_path / "loop_result.json").exists()


class TestIntegrationMaxIter:
    """Run with max_iter limiting processed issues."""

    @patch("gh_autoloop.verifier.shutil.which")
    @patch("subprocess.run")
    def test_max_iter_limits_processing(self, mock_run, mock_which, tmp_path):
        mock_run.side_effect = make_subprocess_mock()
        mock_which.side_effect = make_which_mock()

        loop = AutoLoop(repo_path=str(tmp_path), max_iter=1)
        results = loop.run()

        assert len(results) == 1
        assert results[0].status == "success"


class TestIntegrationPushFailure:
    """Run where push fails but commit is kept."""

    @patch("gh_autoloop.verifier.shutil.which")
    @patch("subprocess.run")
    def test_push_failure_still_succeeds(self, mock_run, mock_which, tmp_path):
        mock_run.side_effect = make_subprocess_mock(
            issues=[MOCK_ISSUES[0]], push_fails=True
        )
        mock_which.side_effect = make_which_mock()

        loop = AutoLoop(repo_path=str(tmp_path))
        results = loop.run()

        assert len(results) == 1
        assert results[0].status == "success"
        assert results[0].commit == "abc1234"


class TestIntegrationNoTestTool:
    """Run where no test tool is found — should still succeed (tests skipped)."""

    @patch("gh_autoloop.verifier.shutil.which")
    @patch("subprocess.run")
    def test_no_test_tool_skips_verification(self, mock_run, mock_which, tmp_path):
        mock_run.side_effect = make_subprocess_mock()
        mock_which.return_value = None  # No test tool found

        loop = AutoLoop(repo_path=str(tmp_path))
        results = loop.run()

        assert len(results) == 2
        assert all(r.status == "success" for r in results)
