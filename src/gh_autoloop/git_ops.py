import logging
import subprocess
from gh_autoloop import Task

logger = logging.getLogger(__name__)


class GitOps:
    def close_issue(self, number: int, repo_path: str) -> None:
        """Close the GitHub issue via gh CLI. Errors are logged but not raised."""
        try:
            result = subprocess.run(
                ["gh", "issue", "close", str(number)],
                capture_output=True, text=True, cwd=repo_path, timeout=30,
            )
            if result.returncode != 0:
                logger.warning(f"Failed to close issue #{number}: {result.stderr.strip()}")
            else:
                logger.info(f"  Closed issue #{number}")
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.warning(f"Failed to close issue #{number}: {e}")

    def commit_and_push(self, task: Task, repo_path: str) -> str:
        """Stage all changes, commit, push. Returns commit hash.

        If push fails, the commit is kept locally and a warning is logged.
        """
        msg = f"fix: {task.title} (closes #{task.number})"
        subprocess.run(["git", "add", "-A"], cwd=repo_path, check=True)
        subprocess.run(["git", "commit", "-m", msg], cwd=repo_path, check=True)
        push = subprocess.run(
            ["git", "push"], capture_output=True, text=True, cwd=repo_path, timeout=60
        )
        if push.returncode != 0:
            logger.warning(f"git push failed (commit kept locally): {push.stderr.strip()}")
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=repo_path, check=True,
        )
        return result.stdout.strip()

    def rollback(self, repo_path: str) -> None:
        """Discard all uncommitted changes. Errors are logged but not raised."""
        try:
            subprocess.run(["git", "checkout", "--", "."], cwd=repo_path, check=True)
            subprocess.run(["git", "clean", "-fd"], cwd=repo_path, check=True)
        except subprocess.CalledProcessError as e:
            logger.warning(f"Rollback incomplete: {e}")

    def has_changes(self, repo_path: str) -> bool:
        """Check if there are any uncommitted changes."""
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=repo_path,
        )
        return bool(result.stdout.strip())
