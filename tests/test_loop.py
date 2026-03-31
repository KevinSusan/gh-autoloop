"""Tests for loop module — AutoLoop orchestration."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from gh_autoloop import Task, ExecutionResult, VerifyResult, IterationResult
from gh_autoloop.loop import AutoLoop


@pytest.fixture
def tmp_repo(tmp_path):
    """Create a temporary directory to act as repo_path."""
    return str(tmp_path)


@pytest.fixture
def sample_tasks():
    return [
        Task(number=1, title="Bug A", body="Fix A"),
        Task(number=2, title="Bug B", body="Fix B"),
    ]


class TestAutoLoopRun:
    """Tests for AutoLoop.run()."""

    @patch.object(AutoLoop, "_save_results")
    @patch.object(AutoLoop, "_process_task")
    def test_run_no_issues_returns_empty(self, mock_process, mock_save, tmp_repo):
        loop = AutoLoop(repo_path=tmp_repo)
        with patch.object(loop.planner, "get_tasks", return_value=[]):
            results = loop.run()

        assert results == []
        mock_process.assert_not_called()
        mock_save.assert_not_called()

    @patch.object(AutoLoop, "_save_results")
    @patch.object(AutoLoop, "_process_task")
    def test_run_processes_all_tasks(self, mock_process, mock_save, tmp_repo, sample_tasks):
        loop = AutoLoop(repo_path=tmp_repo)
        mock_process.return_value = IterationResult(
            task=sample_tasks[0], status="success", commit="abc123"
        )
        with patch.object(loop.planner, "get_tasks", return_value=sample_tasks):
            results = loop.run()

        assert len(results) == 2
        assert mock_process.call_count == 2

    @patch.object(AutoLoop, "_save_results")
    @patch.object(AutoLoop, "_process_task")
    def test_max_iter_limits_tasks(self, mock_process, mock_save, tmp_repo, sample_tasks):
        loop = AutoLoop(repo_path=tmp_repo, max_iter=1)
        mock_process.return_value = IterationResult(
            task=sample_tasks[0], status="success", commit="abc"
        )
        with patch.object(loop.planner, "get_tasks", return_value=sample_tasks):
            results = loop.run()

        assert len(results) == 1
        assert mock_process.call_count == 1

    @patch.object(AutoLoop, "_save_results")
    @patch.object(AutoLoop, "_process_task")
    def test_max_iter_zero_means_no_limit(self, mock_process, mock_save, tmp_repo, sample_tasks):
        loop = AutoLoop(repo_path=tmp_repo, max_iter=0)
        mock_process.return_value = IterationResult(
            task=sample_tasks[0], status="success", commit="abc"
        )
        with patch.object(loop.planner, "get_tasks", return_value=sample_tasks):
            results = loop.run()

        assert len(results) == 2


class TestDoProcess:
    """Tests for AutoLoop._do_process() (the core processing logic)."""

    def _make_loop(self, tmp_repo):
        loop = AutoLoop(repo_path=tmp_repo)
        loop.executor = MagicMock()
        loop.verifier = MagicMock()
        loop.git = MagicMock()
        return loop

    def test_executor_failure_rolls_back(self, tmp_repo):
        loop = self._make_loop(tmp_repo)
        task = Task(number=1, title="Bug", body="desc")
        loop.executor.run.return_value = ExecutionResult(
            success=False, output="error", exit_code=1
        )

        result = loop._do_process(task)

        assert result.status == "failed"
        assert "Executor failed" in result.error
        loop.git.rollback.assert_called_once_with(loop.repo_path)

    def test_executor_failure_error_includes_output(self, tmp_repo):
        loop = self._make_loop(tmp_repo)
        task = Task(number=1, title="Bug", body="desc")
        loop.executor.run.return_value = ExecutionResult(
            success=False, output="detailed error info", exit_code=1
        )

        result = loop._do_process(task)

        assert "detailed error info" in result.error

    def test_no_changes_returns_skipped(self, tmp_repo):
        loop = self._make_loop(tmp_repo)
        task = Task(number=1, title="Bug", body="desc")
        loop.executor.run.return_value = ExecutionResult(
            success=True, output="done", exit_code=0
        )
        loop.git.has_changes.return_value = False

        result = loop._do_process(task)

        assert result.status == "skipped"
        assert "No changes" in result.error

    def test_tests_fail_rolls_back(self, tmp_repo):
        loop = self._make_loop(tmp_repo)
        task = Task(number=1, title="Bug", body="desc")
        loop.executor.run.return_value = ExecutionResult(
            success=True, output="done", exit_code=0
        )
        loop.git.has_changes.return_value = True
        loop.verifier.verify.return_value = VerifyResult(status="failed", output="1 failed")

        result = loop._do_process(task)

        assert result.status == "failed"
        assert "Tests failed" in result.error
        loop.git.rollback.assert_called_once()

    def test_success_commits_and_pushes(self, tmp_repo):
        loop = self._make_loop(tmp_repo)
        task = Task(number=1, title="Bug", body="desc")
        loop.executor.run.return_value = ExecutionResult(
            success=True, output="done", exit_code=0
        )
        loop.git.has_changes.return_value = True
        loop.verifier.verify.return_value = VerifyResult(status="passed", output="3 passed")
        loop.git.commit_and_push.return_value = "abc1234"

        result = loop._do_process(task)

        assert result.status == "success"
        assert result.commit == "abc1234"
        loop.git.commit_and_push.assert_called_once_with(task, loop.repo_path)

    def test_skipped_verify_still_commits(self, tmp_repo):
        loop = self._make_loop(tmp_repo)
        task = Task(number=1, title="Bug", body="desc")
        loop.executor.run.return_value = ExecutionResult(
            success=True, output="done", exit_code=0
        )
        loop.git.has_changes.return_value = True
        loop.verifier.verify.return_value = VerifyResult(status="skipped", output="no tests")
        loop.git.commit_and_push.return_value = "def5678"

        result = loop._do_process(task)

        assert result.status == "success"
        assert result.commit == "def5678"


class TestProcessTaskErrorHandling:
    """Tests for AutoLoop._process_task() catch-all error handling."""

    def test_unexpected_exception_returns_failed(self, tmp_repo):
        loop = AutoLoop(repo_path=tmp_repo)
        loop.executor = MagicMock()
        loop.verifier = MagicMock()
        loop.git = MagicMock()
        task = Task(number=1, title="Bug", body="desc")

        loop.executor.run.side_effect = RuntimeError("unexpected boom")

        result = loop._process_task(task)

        assert result.status == "failed"
        assert "unexpected boom" in result.error
        loop.git.rollback.assert_called_once()


class TestSaveResults:
    """Tests for AutoLoop._save_results()."""

    def test_writes_json_file(self, tmp_repo, tmp_path):
        loop = AutoLoop(repo_path=tmp_repo)
        task = Task(number=1, title="Bug A", body="desc")
        results = [
            IterationResult(task=task, status="success", commit="abc123"),
        ]
        loop._save_results(results)

        repo_name = Path(tmp_repo).name
        output_file = Path.home() / ".gh-autoloop" / "results" / f"{repo_name}.json"
        assert output_file.exists()

        data = json.loads(output_file.read_text())
        assert data["summary"]["total"] == 1
        assert data["summary"]["success"] == 1
        assert data["summary"]["failed"] == 0
        assert data["summary"]["skipped"] == 0
        assert data["results"][0]["issue"] == 1
        assert data["results"][0]["commit"] == "abc123"

    def test_mixed_results_summary(self, tmp_repo, tmp_path):
        loop = AutoLoop(repo_path=tmp_repo)
        results = [
            IterationResult(task=Task(1, "A", ""), status="success", commit="abc"),
            IterationResult(task=Task(2, "B", ""), status="failed", error="err"),
            IterationResult(task=Task(3, "C", ""), status="skipped", error="no changes"),
        ]
        loop._save_results(results)

        repo_name = Path(tmp_repo).name
        data = json.loads((Path.home() / ".gh-autoloop" / "results" / f"{repo_name}.json").read_text())
        assert data["summary"]["total"] == 3
        assert data["summary"]["success"] == 1
        assert data["summary"]["failed"] == 1
        assert data["summary"]["skipped"] == 1
