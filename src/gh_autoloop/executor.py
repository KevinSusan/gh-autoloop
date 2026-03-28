import subprocess
from gh_autoloop import Task, ExecutionResult


class Executor:
    def __init__(self, timeout: int = 600):
        self.timeout = timeout

    def run(self, task: Task, repo_path: str) -> ExecutionResult:
        """Execute a task using local Claude Code CLI."""
        prompt = task.to_prompt()
        try:
            result = subprocess.run(
                ["claude", "--print", prompt],
                capture_output=True,
                text=True,
                cwd=repo_path,
                timeout=self.timeout,
            )
            return ExecutionResult(
                success=result.returncode == 0,
                output=result.stdout + result.stderr,
                exit_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(success=False, output="Execution timed out", exit_code=-1)
