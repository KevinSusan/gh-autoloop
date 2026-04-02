from __future__ import annotations
import json
import logging
import time
from pathlib import Path
from typing import Optional
from gh_autoloop import IterationResult
from gh_autoloop.planner import Planner
from gh_autoloop.executor import Executor
from gh_autoloop.verifier import Verifier
from gh_autoloop.git_ops import GitOps

logger = logging.getLogger(__name__)


class AutoLoop:
    def __init__(
        self,
        repo_path: str,
        max_iter: int = 0,
        label: Optional[str] = None,
        timeout: int = 600,
        dry_run: bool = False,
        gh_repo: Optional[str] = None,
    ):
        self.repo_path = str(Path(repo_path).resolve())
        self.max_iter = max_iter
        self.label = label
        self.dry_run = dry_run
        self.gh_repo = gh_repo
        self.planner = Planner()
        self.executor = Executor(timeout=timeout)
        self.verifier = Verifier()
        self.git = GitOps()

    def run(self) -> list[IterationResult]:
        tasks = self.planner.get_tasks(self.repo_path, self.label, gh_repo=self.gh_repo)
        if not tasks:
            logger.info("No open issues found.")
            return []

        if self.max_iter and len(tasks) > self.max_iter:
            tasks = tasks[: self.max_iter]

        if self.dry_run:
            logger.info(f"Dry run — {len(tasks)} issue(s) would be processed:")
            for i, t in enumerate(tasks, 1):
                logger.info(f"  [{i}] #{t.number}: {t.title}")
            return [IterationResult(task=t, status="skipped", error="dry-run") for t in tasks]

        results: list[IterationResult] = []
        for i, task in enumerate(tasks, 1):
            logger.info(f"[{i}/{len(tasks)}] Processing issue #{task.number}: {task.title}")
            result = self._process_task(task)
            results.append(result)
            icon = "✓" if result.status == "success" else "✗"
            detail = f" → {result.commit}" if result.commit else ""
            logger.info(f"  [{icon}] {result.status}{detail}")

        self._print_summary(results)
        self._save_results(results)
        return results

    def _print_summary(self, results: list[IterationResult]) -> None:
        """Print a formatted summary table after all iterations complete."""
        logger.info("\n=== Run Summary ===")
        logger.info(f"{'#':>4}  {'Title':<40}  {'Status':<8}  {'Elapsed':>8}")
        logger.info("-" * 68)
        for r in results:
            elapsed_str = f"{r.elapsed:.1f}s" if r.elapsed is not None else "-"
            title = r.task.title[:40]
            logger.info(f"#{r.task.number:>3}  {title:<40}  {r.status:<8}  {elapsed_str:>8}")
        logger.info("-" * 68)
        success = sum(1 for r in results if r.status == "success")
        failed = sum(1 for r in results if r.status == "failed")
        skipped = sum(1 for r in results if r.status == "skipped")
        logger.info(f"Total: {len(results)}  Success: {success}  Failed: {failed}  Skipped: {skipped}")

    def _process_task(self, task) -> IterationResult:
        start = time.monotonic()
        try:
            result = self._do_process(task)
        except Exception as e:
            logger.error(f"  Unexpected error: {e}")
            self.git.rollback(self.repo_path)
            result = IterationResult(task=task, status="failed", error=str(e))
        result.elapsed = time.monotonic() - start
        return result

    def _do_process(self, task) -> IterationResult:
        logger.info(f"  → [1/4] Executing claude on issue #{task.number}...")
        exec_result = self.executor.run(task, self.repo_path)
        if not exec_result.success:
            self.git.rollback(self.repo_path)
            return IterationResult(
                task=task, status="failed",
                error=f"Executor failed (exit {exec_result.exit_code}): {exec_result.output[:200]}",
            )

        logger.info(f"  → [2/4] Checking for file changes...")
        if not self.git.has_changes(self.repo_path):
            return IterationResult(task=task, status="skipped", error="No changes made")

        logger.info(f"  → [3/4] Running tests...")
        verify = self.verifier.verify(self.repo_path)
        if not verify.passed:
            self.git.rollback(self.repo_path)
            return IterationResult(
                task=task, status="failed", error=f"Tests failed:\n{verify.output[:500]}"
            )

        logger.info(f"  → [4/4] Committing and pushing...")
        diff_snapshot = self.git.get_diff(self.repo_path)
        commit_hash = self.git.commit_and_push(task, self.repo_path)
        self.git.close_issue(task.number, self.repo_path)
        return IterationResult(task=task, status="success", commit=commit_hash, diff=diff_snapshot)

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
                    "elapsed": round(r.elapsed, 2) if r.elapsed is not None else None,
                    "diff": r.diff,
                }
                for r in results
            ],
        }
        results_dir = Path.home() / ".gh-autoloop" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        repo_name = Path(self.repo_path).name
        output = results_dir / f"{repo_name}.json"
        output.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        logger.info(f"Results saved to {output}")
