import argparse
import json
import logging
import sys
from pathlib import Path
from gh_autoloop.loop import AutoLoop


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
        loop = AutoLoop(
            repo_path=args.repo,
            max_iter=args.max_iter,
            label=args.label,
            timeout=args.timeout,
        )
        results = loop.run()
        total = len(results)
        success = sum(1 for r in results if r.status == "success")
        print(f"\nDone: {success}/{total} issues resolved.")
        sys.exit(0 if success > 0 or total == 0 else 1)

    elif args.command == "status":
        result_file = Path(args.repo) / "loop_result.json"
        if not result_file.exists():
            print("No loop_result.json found. Run 'gh-autoloop run' first.")
            sys.exit(1)
        data = json.loads(result_file.read_text())
        s = data["summary"]
        print(f"Last run: {s['total']} total, {s['success']} success, {s['failed']} failed, {s['skipped']} skipped")
        for r in data["results"]:
            icon = "v" if r["status"] == "success" else "x"
            commit = f" [{r['commit']}]" if r.get("commit") else ""
            print(f"  [{icon}] #{r['issue']} {r['title']}{commit}")


if __name__ == "__main__":
    main()
