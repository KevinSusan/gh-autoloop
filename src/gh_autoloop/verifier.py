import shutil
import subprocess
from gh_autoloop import VerifyResult

# (executable_name, test_command_args)
TEST_COMMANDS = [
    ("pytest", ["pytest", "--tb=short", "-q"]),
    ("npm", ["npm", "test"]),
    ("make", ["make", "test"]),
]

VERIFY_TIMEOUT = 300  # 5 minutes


class Verifier:
    def verify(self, repo_path: str) -> VerifyResult:
        """Auto-detect and run test command."""
        for exe, cmd in TEST_COMMANDS:
            if not shutil.which(exe):
                continue
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, cwd=repo_path, timeout=VERIFY_TIMEOUT
                )
            except subprocess.TimeoutExpired:
                return VerifyResult(status="failed", output=f"Test command '{cmd[0]}' timed out")
            status = "passed" if result.returncode == 0 else "failed"
            return VerifyResult(status=status, output=result.stdout + result.stderr)
        return VerifyResult(status="skipped", output="No test command found")
