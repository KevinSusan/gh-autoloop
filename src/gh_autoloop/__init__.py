from dataclasses import dataclass


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
    commit: str | None = None
    error: str | None = None
