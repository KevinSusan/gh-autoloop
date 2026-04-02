from __future__ import annotations
import json
import subprocess
from typing import Optional
from gh_autoloop import Task


class Planner:
    def get_tasks(
        self, repo_path: str, label: Optional[str] = None, gh_repo: Optional[str] = None
    ) -> list[Task]:
        """Fetch open GitHub Issues via gh CLI."""
        cmd = ["gh", "issue", "list", "--json", "number,title,body", "--state", "open", "--limit", "100"]
        if gh_repo:
            cmd += ["--repo", gh_repo]
        if label:
            cmd += ["--label", label]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                cwd=repo_path, timeout=30,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("gh issue list timed out after 30s")
        if result.returncode != 0:
            raise RuntimeError(f"gh issue list failed: {result.stderr.strip()}")
        raw = result.stdout.strip()
        if not raw:
            return []
        try:
            issues = json.loads(raw)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse gh output: {e}")
        return [Task(number=i["number"], title=i["title"], body=i.get("body") or "") for i in issues]
