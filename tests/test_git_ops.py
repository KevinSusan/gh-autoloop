"""Tests for git_ops module — git commit, push, rollback operations."""

import subprocess
from unittest.mock import patch, MagicMock, call

import pytest

from gh_autoloop import Task
from gh_autoloop.git_ops import GitOps


@pytest.fixture
def git_ops():
    return GitOps()


@pytest.fixture
def task():
    return Task(number=7, title="Fix memory leak", body="OOM in production.")


class TestCommitAndPush:
    """Tests for GitOps.commit_and_push()."""

    @patch("gh_autoloop.git_ops.subprocess.run")
    def test_stages_commits_pushes_returns_hash(self, mock_run, git_ops, task):
        mock_run.return_value = MagicMock(returncode=0, stdout="abc1234\n", stderr="")

        result = git_ops.commit_and_push(task, "/repo")

        assert result == "abc1234"
        calls = mock_run.call_args_list
        assert len(calls) == 4
        # git add -A
        assert calls[0][0][0] == ["git", "add", "-A"]
        # git commit -m "..."
        assert calls[1][0][0][0:2] == ["git", "commit"]
        assert "closes #7" in calls[1][0][0][3]
        # git push
        assert calls[2][0][0] == ["git", "push"]
        # git rev-parse
        assert calls[3][0][0] == ["git", "rev-parse", "--short", "HEAD"]

    @patch("gh_autoloop.git_ops.subprocess.run")
    def test_commit_message_format(self, mock_run, git_ops, task):
        mock_run.return_value = MagicMock(returncode=0, stdout="abc\n", stderr="")
        git_ops.commit_and_push(task, "/repo")

        commit_call = mock_run.call_args_list[1]
        msg = commit_call[0][0][3]
        assert msg == "fix: Fix memory leak (closes #7)"

    @patch("gh_autoloop.git_ops.subprocess.run")
    def test_push_failure_is_warning_not_error(self, mock_run, git_ops, task):
        """Push failure should NOT raise — commit is kept locally."""
        call_count = [0]

        def side_effect(cmd, **kwargs):
            call_count[0] += 1
            result = MagicMock()
            result.stdout = ""
            result.stderr = ""
            result.returncode = 0
            if cmd == ["git", "push"]:
                result.returncode = 1
                result.stderr = "remote rejected"
            if cmd == ["git", "rev-parse", "--short", "HEAD"]:
                result.stdout = "def5678\n"
            return result

        mock_run.side_effect = side_effect
        result = git_ops.commit_and_push(task, "/repo")

        # Should still return the commit hash despite push failure
        assert result == "def5678"

    @patch("gh_autoloop.git_ops.subprocess.run")
    def test_cwd_is_repo_path(self, mock_run, git_ops, task):
        mock_run.return_value = MagicMock(returncode=0, stdout="abc\n", stderr="")
        git_ops.commit_and_push(task, "/my/project")

        for c in mock_run.call_args_list:
            assert c[1]["cwd"] == "/my/project"


class TestRollback:
    """Tests for GitOps.rollback()."""

    @patch("gh_autoloop.git_ops.subprocess.run")
    def test_rollback_runs_checkout_and_clean(self, mock_run, git_ops):
        mock_run.return_value = MagicMock(returncode=0)
        git_ops.rollback("/repo")

        calls = mock_run.call_args_list
        assert len(calls) == 2
        assert calls[0][0][0] == ["git", "checkout", "--", "."]
        assert calls[1][0][0] == ["git", "clean", "-fd"]

    @patch("gh_autoloop.git_ops.subprocess.run")
    def test_rollback_error_is_swallowed(self, mock_run, git_ops):
        """Rollback errors should be logged but not raised."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "git checkout")
        # Should NOT raise
        git_ops.rollback("/repo")


class TestHasChanges:
    """Tests for GitOps.has_changes()."""

    @patch("gh_autoloop.git_ops.subprocess.run")
    def test_has_changes_true(self, mock_run, git_ops):
        mock_run.return_value = MagicMock(returncode=0, stdout=" M file.py\n")
        assert git_ops.has_changes("/repo") is True

    @patch("gh_autoloop.git_ops.subprocess.run")
    def test_has_changes_false(self, mock_run, git_ops):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        assert git_ops.has_changes("/repo") is False

    @patch("gh_autoloop.git_ops.subprocess.run")
    def test_has_changes_whitespace_only_is_false(self, mock_run, git_ops):
        mock_run.return_value = MagicMock(returncode=0, stdout="   \n  \n")
        assert git_ops.has_changes("/repo") is False

    @patch("gh_autoloop.git_ops.subprocess.run")
    def test_uses_porcelain_flag(self, mock_run, git_ops):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        git_ops.has_changes("/repo")
        mock_run.assert_called_once_with(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd="/repo",
        )


class TestGetDiff:
    """Tests for GitOps.get_diff()."""

    @patch("gh_autoloop.git_ops.subprocess.run")
    def test_returns_diff_output(self, mock_run, git_ops):
        mock_run.return_value = MagicMock(returncode=0, stdout="+added line\n-removed line\n")
        result = git_ops.get_diff("/repo")
        assert result == "+added line\n-removed line\n"

    @patch("gh_autoloop.git_ops.subprocess.run")
    def test_truncates_to_max_chars(self, mock_run, git_ops):
        long_diff = "x" * 5000
        mock_run.return_value = MagicMock(returncode=0, stdout=long_diff)
        result = git_ops.get_diff("/repo", max_chars=100)
        assert len(result) == 100
        assert result == "x" * 100

    @patch("gh_autoloop.git_ops.subprocess.run")
    def test_calls_git_diff_with_correct_args(self, mock_run, git_ops):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        git_ops.get_diff("/my/repo")
        mock_run.assert_called_once_with(
            ["git", "diff"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd="/my/repo",
        )

    @patch("gh_autoloop.git_ops.subprocess.run")
    def test_empty_diff_returns_empty_string(self, mock_run, git_ops):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        result = git_ops.get_diff("/repo")
        assert result == ""
