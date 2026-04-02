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

    def test_elapsed_field_saved_in_json(self, tmp_repo):
        """elapsed time should be rounded and saved in the JSON output."""
        loop = AutoLoop(repo_path=tmp_repo)
        task = Task(number=5, title="Slow fix", body="desc")
        result = IterationResult(task=task, status="success", commit="abc", elapsed=12.3456)
        loop._save_results([result])

        repo_name = Path(tmp_repo).name
        data = json.loads((Path.home() / ".gh-autoloop" / "results" / f"{repo_name}.json").read_text())
        assert data["results"][0]["elapsed"] == 12.35

    def test_diff_field_saved_in_json(self, tmp_repo):
        """diff snapshot should be stored in the JSON output."""
        loop = AutoLoop(repo_path=tmp_repo)
        task = Task(number=6, title="Diff fix", body="desc")
        diff_text = "+added line\n-removed line\n"
        result = IterationResult(task=task, status="success", commit="def", diff=diff_text)
        loop._save_results([result])

        repo_name = Path(tmp_repo).name
        data = json.loads((Path.home() / ".gh-autoloop" / "results" / f"{repo_name}.json").read_text())
        assert data["results"][0]["diff"] == diff_text

    def test_elapsed_none_saved_as_null(self, tmp_repo):
        """elapsed=None should serialize as JSON null."""
        loop = AutoLoop(repo_path=tmp_repo)
        task = Task(number=7, title="Quick fix", body="")
        result = IterationResult(task=task, status="skipped", error="no changes")
        loop._save_results([result])

        repo_name = Path(tmp_repo).name
        data = json.loads((Path.home() / ".gh-autoloop" / "results" / f"{repo_name}.json").read_text())
        assert data["results"][0]["elapsed"] is None


class TestProcessTaskElapsed:
    """Tests for elapsed timing in AutoLoop._process_task()."""

    def test_elapsed_is_set_on_success(self, tmp_repo):
        """elapsed field must be a positive float after a successful task."""
        loop = AutoLoop(repo_path=tmp_repo)
        loop.executor = MagicMock()
        loop.verifier = MagicMock()
        loop.git = MagicMock()
        task = Task(number=1, title="Bug", body="desc")
        loop.executor.run.return_value = ExecutionResult(success=True, output="ok", exit_code=0)
        loop.git.has_changes.return_value = True
        loop.verifier.verify.return_value = VerifyResult(status="passed", output="")
        loop.git.commit_and_push.return_value = "abc"

        result = loop._process_task(task)

        assert result.elapsed is not None
        assert result.elapsed >= 0.0

    def test_elapsed_is_set_on_failure(self, tmp_repo):
        """elapsed field is set even when the task fails."""
        loop = AutoLoop(repo_path=tmp_repo)
        loop.executor = MagicMock()
        loop.verifier = MagicMock()
        loop.git = MagicMock()
        task = Task(number=1, title="Bug", body="desc")
        loop.executor.run.return_value = ExecutionResult(success=False, output="err", exit_code=1)

        result = loop._process_task(task)

        assert result.elapsed is not None
        assert result.elapsed >= 0.0


class TestDoProcessDiffCapture:
    """Tests that diff snapshot is captured on success."""

    def _make_loop(self, tmp_repo):
        loop = AutoLoop(repo_path=tmp_repo)
        loop.executor = MagicMock()
        loop.verifier = MagicMock()
        loop.git = MagicMock()
        return loop

    def test_diff_captured_on_success(self, tmp_repo):
        """get_diff() is called and its result stored in IterationResult.diff."""
        loop = self._make_loop(tmp_repo)
        task = Task(number=1, title="Bug", body="desc")
        loop.executor.run.return_value = ExecutionResult(success=True, output="ok", exit_code=0)
        loop.git.has_changes.return_value = True
        loop.verifier.verify.return_value = VerifyResult(status="passed", output="")
        loop.git.commit_and_push.return_value = "abc"
        loop.git.get_diff.return_value = "+some change\n"

        result = loop._do_process(task)

        assert result.diff == "+some change\n"
        loop.git.get_diff.assert_called_once_with(loop.repo_path)

    def test_diff_not_captured_on_failure(self, tmp_repo):
        """get_diff() should NOT be called if execution fails."""
        loop = self._make_loop(tmp_repo)
        task = Task(number=1, title="Bug", body="desc")
        loop.executor.run.return_value = ExecutionResult(success=False, output="err", exit_code=1)

        loop._do_process(task)

        loop.git.get_diff.assert_not_called()


class TestPhaseLogging:
    """Verify that _do_process emits the four stage INFO log messages."""

    def _make_loop(self, tmp_repo):
        loop = AutoLoop(repo_path=tmp_repo)
        loop.executor = MagicMock()
        loop.verifier = MagicMock()
        loop.git = MagicMock()
        return loop

    def test_phase1_always_logged(self, tmp_repo, caplog):
        """[1/4] must appear even when execution fails."""
        import logging
        loop = self._make_loop(tmp_repo)
        task = Task(number=1, title="Bug", body="")
        loop.executor.run.return_value = ExecutionResult(
            success=False, output="err", exit_code=1
        )
        with caplog.at_level(logging.INFO, logger="gh_autoloop.loop"):
            loop._do_process(task)
        assert any("[1/4]" in m for m in caplog.messages)

    def test_phase2_logged_after_exec_success(self, tmp_repo, caplog):
        """[2/4] must appear once executor succeeds."""
        import logging
        loop = self._make_loop(tmp_repo)
        task = Task(number=1, title="Bug", body="")
        loop.executor.run.return_value = ExecutionResult(
            success=True, output="ok", exit_code=0
        )
        loop.git.has_changes.return_value = False  # early exit after phase 2
        with caplog.at_level(logging.INFO, logger="gh_autoloop.loop"):
            loop._do_process(task)
        assert any("[2/4]" in m for m in caplog.messages)

    def test_phase3_logged_when_changes_present(self, tmp_repo, caplog):
        """[3/4] must appear when there are changes to verify."""
        import logging
        loop = self._make_loop(tmp_repo)
        task = Task(number=1, title="Bug", body="")
        loop.executor.run.return_value = ExecutionResult(
            success=True, output="ok", exit_code=0
        )
        loop.git.has_changes.return_value = True
        loop.verifier.verify.return_value = VerifyResult(status="failed", output="err")
        with caplog.at_level(logging.INFO, logger="gh_autoloop.loop"):
            loop._do_process(task)
        assert any("[3/4]" in m for m in caplog.messages)

    def test_phase4_logged_on_success_path(self, tmp_repo, caplog):
        """[4/4] must appear on the full success path."""
        import logging
        loop = self._make_loop(tmp_repo)
        task = Task(number=1, title="Bug", body="")
        loop.executor.run.return_value = ExecutionResult(
            success=True, output="ok", exit_code=0
        )
        loop.git.has_changes.return_value = True
        loop.verifier.verify.return_value = VerifyResult(status="passed", output="ok")
        loop.git.get_diff.return_value = "+line"
        loop.git.commit_and_push.return_value = "abc1234"
        with caplog.at_level(logging.INFO, logger="gh_autoloop.loop"):
            loop._do_process(task)
        assert any("[4/4]" in m for m in caplog.messages)

    def test_all_four_phases_logged_on_full_success(self, tmp_repo, caplog):
        """All four phase markers must appear on the happy path."""
        import logging
        loop = self._make_loop(tmp_repo)
        task = Task(number=1, title="Bug", body="")
        loop.executor.run.return_value = ExecutionResult(
            success=True, output="ok", exit_code=0
        )
        loop.git.has_changes.return_value = True
        loop.verifier.verify.return_value = VerifyResult(status="passed", output="ok")
        loop.git.get_diff.return_value = "+line"
        loop.git.commit_and_push.return_value = "abc1234"
        with caplog.at_level(logging.INFO, logger="gh_autoloop.loop"):
            loop._do_process(task)
        for phase in ("[1/4]", "[2/4]", "[3/4]", "[4/4]"):
            assert any(phase in m for m in caplog.messages), f"Phase log missing: {phase}"
