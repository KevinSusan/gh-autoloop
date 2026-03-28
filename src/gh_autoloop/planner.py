import json
import subprocess
from gh_autoloop import Task


class Planner:
    def get_tasks(self, repo_path: str, label: str | None = None) -> list[Task]:
        """Fetch open GitHub Issues via gh CLI."""
        cmd = ["gh", "issue", "list", "--json", "number,title,body", "--state", "open", "--limit", "100"]
        if label:
            cmd += ["--label", label]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_path)
        if result.returncode != 0:
            raise RuntimeError(f"gh issue list failed: {result.stderr}")
        issues = json.loads(result.stdout)
        return [Task(number=i["number"], title=i["title"], body=i.get("body") or "") for i in issues]
