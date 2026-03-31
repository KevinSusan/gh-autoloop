import logging
import subprocess
from gh_autoloop import Task, ExecutionResult

logger = logging.getLogger(__name__)


class Executor:
    def __init__(self, timeout: int = 600):
        self.timeout = timeout

    def run(self, task: Task, repo_path: str) -> ExecutionResult:
        """Execute a task using local Claude Code CLI with streaming output."""
        prompt = task.to_prompt()
        cmd = ["claude", "--dangerously-skip-permissions", "--print", prompt]
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, cwd=repo_path,
            )
        except OSError as e:
            return ExecutionResult(success=False, output=f"Failed to launch claude: {e}", exit_code=-1)

        output_lines: list = []
        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                output_lines.append(line)
                logger.debug(line.rstrip())
            proc.wait(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            return ExecutionResult(success=False, output="Execution timed out", exit_code=-1)

        output = "".join(output_lines)
        return ExecutionResult(
            success=proc.returncode == 0,
            output=output,
            exit_code=proc.returncode or 0,
        )
