import json
import logging
from pathlib import Path
from gh_autoloop import IterationResult
from gh_autoloop.planner import Planner
from gh_autoloop.executor import Executor
from gh_autoloop.verifier import Verifier
from gh_autoloop.git_ops import GitOps

logger = logging.getLogger(__name__)


class AutoLoop:
    def __init__(self, repo_path: str, max_iter: int = 0, label: str | None = None, timeout: int = 600):
        self.repo_path = str(Path(repo_path).resolve())
        self.max_iter = max_iter
        self.label = label
        self.planner = Planner()
        self.executor = Executor(timeout=timeout)
        self.verifier = Verifier()
        self.git = GitOps()

    def run(self) -> list[IterationResult]:
        tasks = self.planner.get_tasks(self.repo_path, self.label)
        if not tasks:
            logger.info("No open issues found.")
            return []

        if self.max_iter and len(tasks) > self.max_iter:
            tasks = tasks[: self.max_iter]

        results: list[IterationResult] = []
        for i, task in enumerate(tasks, 1):
            logger.info(f"[{i}/{len(tasks)}] Processing issue #{task.number}: {task.title}")
            result = self._process_task(task)
            results.append(result)
            icon = "✓" if result.status == "success" else "✗"
            detail = f" → {result.commit}" if result.commit else ""
            logger.info(f"  [{icon}] {result.status}{detail}")

        self._save_results(results)
        return results

    def _process_task(self, task) -> IterationResult:
        try:
            return self._do_process(task)
        except Exception as e:
            logger.error(f"  Unexpected error: {e}")
            self.git.rollback(self.repo_path)
            return IterationResult(task=task, status="failed", error=str(e))

    def _do_process(self, task) -> IterationResult:
        exec_result = self.executor.run(task, self.repo_path)
        if not exec_result.success:
            self.git.rollback(self.repo_path)
            return IterationResult(
                task=task, status="failed",
                error=f"Executor failed (exit {exec_result.exit_code}): {exec_result.output[:200]}",
            )

        if not self.git.has_changes(self.repo_path):
            return IterationResult(task=task, status="skipped", error="No changes made")

        verify = self.verifier.verify(self.repo_path)
        if not verify.passed:
            self.git.rollback(self.repo_path)
            return IterationResult(
                task=task, status="failed", error=f"Tests failed:\n{verify.output[:500]}"
            )

        commit_hash = self.git.commit_and_push(task, self.repo_path)
        return IterationResult(task=task, status="success", commit=commit_hash)

    def _save_results(self, results: list[IterationResult]) -> None:
        summary = {
            "total": len(results),
            "success": sum(1 for r in results if r.status == "success"),
            "failed": sum(1 for r in results if r.status == "failed"),
            "skipped": sum(1 for r in results if r.status == "skipped"),
        }
        data = {
            "summary": summary,
            "results": [
                {
                    "issue": r.task.number,
                    "title": r.task.title,
                    "status": r.status,
                    "commit": r.commit,
                    "error": r.error,
                }
                for r in results
            ],
        }
        output = Path(self.repo_path) / "loop_result.json"
        output.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        logger.info(f"Results saved to {output}")
