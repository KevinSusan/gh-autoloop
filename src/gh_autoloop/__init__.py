import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional


class PrerequisiteError(RuntimeError):
    """Raised when a required external tool is missing or not authenticated."""


def check_prerequisites() -> None:
    """Verify that required external tools (gh, claude) are available."""
    for tool in ("gh", "claude"):
        if not shutil.which(tool):
            raise PrerequisiteError(
                f"'{tool}' CLI not found. Please install it and ensure it's on your PATH."
            )
    # Verify gh is authenticated
    r = subprocess.run(
        ["gh", "auth", "status"], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=10,
    )
    if r.returncode != 0:
        raise PrerequisiteError(
            f"GitHub CLI not authenticated. Run 'gh auth login' first.\n{r.stderr}"
        )


@dataclass
class Task:
    number: int
    title: str
    body: str

    def to_prompt(self) -> str:
        return (
            f"Fix GitHub Issue #{self.number}: {self.title}\n\n"
            f"{self.body}\n\n"
            "Please analyze the codebase, implement the fix, and make sure existing tests pass."
        )


@dataclass
class ExecutionResult:
    success: bool
    output: str
    exit_code: int


@dataclass
class VerifyResult:
    status: str  # "passed" | "failed" | "skipped"
    output: str

    @property
    def passed(self) -> bool:
        return self.status in ("passed", "skipped")


@dataclass
class IterationResult:
    task: Task
    status: str  # "success" | "failed" | "skipped"
    commit: Optional[str] = None
    error: Optional[str] = None
