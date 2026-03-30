import subprocess
from gh_autoloop import Task, ExecutionResult


class Executor:
    def __init__(self, timeout: int = 600, skip_permissions: bool = True):
        self.timeout = timeout
        self.skip_permissions = skip_permissions

    def run(self, task: Task, repo_path: str) -> ExecutionResult:
        """Execute a task using local Claude Code CLI."""
        prompt = task.to_prompt()
        cmd = ["claude", "--print", "--output-format", "text", prompt]
        if self.skip_permissions:
            cmd.insert(1, "--dangerously-skip-permissions")
        try:
            result = subprocess.run(
                cmd,
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
        except OSError as e:
            return ExecutionResult(success=False, output=f"Failed to launch claude: {e}", exit_code=-1)
