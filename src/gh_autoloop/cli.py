import argparse
import json
import logging
import os
import sys
from pathlib import Path
from gh_autoloop import PrerequisiteError, check_prerequisites
from gh_autoloop.loop import AutoLoop

# Force UTF-8 for all subprocess I/O on Windows (avoids GBK decode errors in Python 3.8)
os.environ.setdefault("PYTHONUTF8", "1")


def main():
    parser = argparse.ArgumentParser(
        prog="gh-autoloop",
        description="Auto-iterate GitHub Issues using local Claude Code CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # run command
    run_parser = sub.add_parser("run", help="Start the auto-iteration loop")
    run_parser.add_argument("--repo", default=".", help="Path to the target git repo (default: .)")
    run_parser.add_argument("--max-iter", type=int, default=0, help="Max issues to process (0 = no limit)")
    run_parser.add_argument("--label", default=None, help="Only process issues with this label")
    run_parser.add_argument("--timeout", type=int, default=600, help="Seconds per task (default: 600)")
    run_parser.add_argument("--dry-run", action="store_true", help="List issues without executing")
    run_parser.add_argument("--gh-repo", default=None, metavar="OWNER/REPO", help="GitHub repo (e.g. owner/repo); defaults to remote of --repo")
    run_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")

    # status command
    status_parser = sub.add_parser("status", help="Show results from last run")
    status_parser.add_argument("--repo", default=".", help="Path to the target git repo (default: .)")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "verbose", False) else logging.INFO,
        format="%(message)s",
    )

    if args.command == "run":
        try:
            check_prerequisites()
        except PrerequisiteError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        try:
            loop = AutoLoop(
                repo_path=args.repo,
                max_iter=args.max_iter,
                label=args.label,
                timeout=args.timeout,
                dry_run=args.dry_run,
                gh_repo=args.gh_repo,
            )
            results = loop.run()
        except Exception as e:
            print(f"Fatal error: {e}", file=sys.stderr)
            sys.exit(1)
        total = len(results)
        success = sum(1 for r in results if r.status == "success")
        print(f"\nDone: {success}/{total} issues resolved.")
        sys.exit(0 if success > 0 or total == 0 else 1)

    elif args.command == "status":
        repo_name = Path(args.repo).resolve().name
        result_file = Path.home() / ".gh-autoloop" / "results" / f"{repo_name}.json"
        if not result_file.exists():
            print(f"No results found for '{repo_name}'. Run 'gh-autoloop run' first.")
            sys.exit(1)
        try:
            data = json.loads(result_file.read_text())
        except (json.JSONDecodeError, OSError) as e:
            print(f"Error reading results: {e}", file=sys.stderr)
            sys.exit(1)
        s = data["summary"]
        print(f"Last run: {s['total']} total, {s['success']} success, {s['failed']} failed, {s['skipped']} skipped")
        for r in data["results"]:
            icon = "✓" if r["status"] == "success" else "✗"
            commit = f" [{r['commit']}]" if r.get("commit") else ""
            print(f"  [{icon}] #{r['issue']} {r['title']}{commit}")


if __name__ == "__main__":
    main()
