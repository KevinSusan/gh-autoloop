import subprocess
from pathlib import Path
from gh_autoloop import VerifyResult


TEST_COMMANDS = [
    ["pytest", "--tb=short", "-q"],
    ["npm", "test"],
    ["make", "test"],
]


class Verifier:
    def verify(self, repo_path: str) -> VerifyResult:
        """Auto-detect and run test command."""
        for cmd in TEST_COMMANDS:
            if self._command_exists(cmd[0], repo_path):
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_path)
                status = "passed" if result.returncode == 0 else "failed"
                return VerifyResult(status=status, output=result.stdout + result.stderr)
        return VerifyResult(status="skipped", output="No test command found")

    def _command_exists(self, cmd: str, cwd: str) -> bool:
        try:
            subprocess.run([cmd, "--version"], capture_output=True, cwd=cwd, timeout=5)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
