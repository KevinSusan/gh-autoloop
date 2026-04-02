# gh-autoloop

> Thin automation tool that reads GitHub Issues, calls local Claude Code CLI to fix them, verifies with tests, then auto-commits and pushes. Loops until done or max iterations reached.

## How It Works

```
读取 GitHub Issues (via gh CLI)
      ↓
  生成任务描述 (prompt)
      ↓
  调用 claude CLI 执行修复
      ↓
  自动验证 (pytest → npm test → make test)
      ↓
  成功 → git commit + push
  失败 → git rollback, 继续下一个
      ↓
  循环直到完成或达到上限
```

## Prerequisites

Before installing gh-autoloop, you need the following tools:

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11+ | [python.org](https://www.python.org/) |
| Claude Code CLI | latest | [claude.ai/code](https://claude.ai/code) |
| GitHub CLI (gh) | latest | [cli.github.com](https://cli.github.com/) |
| git | any | [git-scm.com](https://git-scm.com/) |

Make sure `gh` is authenticated:

```bash
gh auth login
gh auth status  # verify
```

## Installation

```bash
# Using uv (recommended)
uv pip install -e .

# Or using pip (requires pip 21.3+ for PEP 660 editable installs)
pip install -e .
```

## Usage

### Run the auto-loop

```bash
# In your project directory (must be a git repo with GitHub remote)
cd /path/to/your/project
gh-autoloop run

# Limit to at most 5 issues
gh-autoloop run --max-iter 5

# Only process issues with a specific label
gh-autoloop run --label bug

# Specify a different repo path
gh-autoloop run --repo /path/to/other/repo

# Set timeout per task (default: 600 seconds)
gh-autoloop run --timeout 300

# Dry run: list issues that would be processed without executing
gh-autoloop run --dry-run

# Use a specific GitHub repo (useful when local remote differs)
gh-autoloop run --gh-repo owner/repo

# Verbose logging
gh-autoloop run -v
```

### Check results from the last run

```bash
gh-autoloop status
gh-autoloop status --repo /path/to/repo
```

## Output

Each run generates `~/.gh-autoloop/results/<repo-name>.json`:

```json
{
  "summary": {
    "total": 3,
    "success": 2,
    "failed": 1,
    "skipped": 0
  },
  "results": [
    {
      "issue": 42,
      "title": "Fix login bug",
      "status": "success",
      "commit": "abc1234",
      "error": null,
      "elapsed": 47.32,
      "diff": "diff --git a/..."
    },
    {
      "issue": 43,
      "title": "Add dark mode",
      "status": "failed",
      "commit": null,
      "error": "Tests failed:\n1 failed, 2 passed",
      "elapsed": 12.08,
      "diff": null
    }
  ]
}
```

A progress summary table is also printed at the end of each run:

```
=== Run Summary ===
   #  Title                                     Status    Elapsed
--------------------------------------------------------------------
  42  Fix login bug                             success    47.3s
  43  Add dark mode                             failed     12.1s
--------------------------------------------------------------------
Total: 2  Success: 1  Failed: 1  Skipped: 0
```

### Status meanings

| Status | Description |
|--------|-------------|
| `success` | Claude fixed the issue, tests passed, committed and pushed |
| `failed` | Claude execution failed, or tests failed after fix (auto-rollback) |
| `skipped` | Claude ran but made no file changes |

## Architecture

```
cli.py                  # CLI entry point (argparse)
  └── loop.py           # Main loop orchestration
        ├── planner.py  # Fetches GitHub Issues via gh CLI
        ├── executor.py # Calls claude CLI via subprocess
        ├── verifier.py # Auto-detects and runs test command
        └── git_ops.py  # git add/commit/push/rollback
```

**Design constraints:**
- Total source code < 500 lines Python (currently ~471 lines)
- Zero third-party dependencies — only Python stdlib + subprocess
- No AI SDKs (no anthropic/openai packages) — Claude Code CLI is the sole AI executor
- Fail-safe: any task failure triggers automatic rollback, does not affect subsequent tasks

## Error Handling

| Scenario | Behavior |
|----------|----------|
| `gh` or `claude` CLI not installed | Exits with clear error message before processing |
| `gh` not authenticated | Exits with prompt to run `gh auth login` |
| Claude execution timeout | Marks task as failed, rollback, continues |
| Tests fail after fix | Marks task as failed, rollback, continues |
| `git push` fails | Warning logged, commit kept locally, task still marked as success |
| No open issues | Exits cleanly with "No open issues found" |
| Unexpected exception | Caught by catch-all handler, rollback, continues to next task |

## Development

```bash
# Install in development mode
uv pip install -e .

# Run tests
pytest tests/ -v

# Format code
ruff check --fix src/ tests/
ruff format src/ tests/
```

### Windows Compatibility

All `subprocess` calls use `encoding="utf-8", errors="replace"` to avoid `UnicodeDecodeError` on systems with non-UTF-8 default encodings (e.g., GBK on Chinese Windows).

For Python 3.8 / older environments where `encoding=` on `Popen` is not available, the CLI entry point automatically sets:

```python
os.environ.setdefault("PYTHONUTF8", "1")
```

This forces UTF-8 I/O across all subprocesses. Alternatively, you can set the environment variable yourself before running:

```bash
# PowerShell
$env:PYTHONUTF8 = "1"
gh-autoloop run

# CMD
set PYTHONUTF8=1
gh-autoloop run
```

## License

MIT
