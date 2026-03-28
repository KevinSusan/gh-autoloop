import subprocess
from gh_autoloop import Task


class GitOps:
    def commit_and_push(self, task: Task, repo_path: str) -> str:
        """Stage all changes, commit, push. Returns commit hash."""
        msg = f"fix: {task.title} (closes #{task.number})"
        subprocess.run(["git", "add", "-A"], cwd=repo_path, check=True)
        subprocess.run(["git", "commit", "-m", msg], cwd=repo_path, check=True)
        subprocess.run(["git", "push"], cwd=repo_path, check=True)
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=repo_path, check=True
        )
        return result.stdout.strip()

    def rollback(self, repo_path: str) -> None:
        """Discard all uncommitted changes."""
        subprocess.run(["git", "checkout", "--", "."], cwd=repo_path, check=True)
        subprocess.run(["git", "clean", "-fd"], cwd=repo_path, check=True)

    def has_changes(self, repo_path: str) -> bool:
        """Check if there are any uncommitted changes."""
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=repo_path
        )
        return bool(result.stdout.strip())
