# gh-autoloop — Claude Code 工作指南

## 项目定位

**gh-autoloop** 是一个薄薄的自动迭代工作流工具。它读取 GitHub Issues，调用本地 Claude Code CLI 逐一修复，验证后自动 commit + push，循环直到完成或达到上限。

**核心设计原则**：
- 整个系统 < 500 行 Python
- Claude Code CLI 是唯一的 AI 执行器（通过 `subprocess` 调用 `claude` 命令）
- 不引入 LLM SDK，不调用远程 AI API
- 失败安全：任何任务失败都自动回滚，不影响下一个任务

---

## 架构

```
gh-autoloop/
├── src/gh_autoloop/
│   ├── __init__.py
│   ├── cli.py          # 入口：gh-autoloop run --repo . --max-iter 10
│   ├── loop.py         # 主循环：AutoLoop.run()
│   ├── planner.py      # 任务来源：GitHub Issues via gh CLI
│   ├── executor.py     # 调用 claude CLI 执行任务
│   ├── verifier.py     # 验证：自动检测 pytest/npm test/make test
│   └── git_ops.py      # git 操作：commit、push、rollback
├── specs/
│   └── architecture.md # 详细架构设计
├── tests/
├── CLAUDE.md           # 本文件
├── README.md
└── pyproject.toml
```

---

## 关键决策（已定）

| 问题 | 决策 |
|------|------|
| Issues 来源 | `gh issue list --json` (本地 gh CLI) |
| AI 执行器 | 本地 `claude --dangerously-skip-permissions --print <task>` CLI（Popen 流式输出）|
| 验证方式 | 自动检测 pytest → npm test → make test |
| Commit message | `fix: <issue title> (closes #<num>)` |
| 失��处理 | `git checkout -- .` 自动回滚 |
| 推送策略 | 每次成功 commit 后自动 `git push`，并关闭对应 Issue |
| 结果存储 | `~/.gh-autoloop/results/<repo-name>.json`（含 elapsed、diff 字段）|
| Windows 兼容 | 所有 subprocess 调用统一 `encoding="utf-8", errors="replace"`；cli.py 设置 `PYTHONUTF8=1` |

---

## 主要接口

### CLI
```bash
# 基本用法
gh-autoloop run --repo /path/to/repo

# 限制最大迭代次数
gh-autoloop run --repo . --max-iter 5

# 指定 issue 标签过滤
gh-autoloop run --repo . --label bug

# 试运行：只列出将处理的 issues，不执行
gh-autoloop run --repo . --dry-run

# 指定 GitHub 仓库（跨仓库处理）
gh-autoloop run --repo . --gh-repo owner/repo

# 查看上次运行结果
gh-autoloop status
```

### 输出
- 每次运行生成 `~/.gh-autoloop/results/<repo-name>.json`，记录每个 issue 的处理状态
- 格式：`{issue_num, title, status: success|failed|skipped, commit_sha, error, elapsed, diff}`
- 运行结束后自动打印进度摘要表（含每条耗时）

---

## 开发规范

- Python 3.11+
- 使用 `uv` 管理依赖（`uv pip install -e .`）
- 测试用 `pytest`
- 代码格式用 `ruff`
- **不要**引入 anthropic SDK、openai SDK 等 AI 库
- **不要**过度工程化，保持极简

---

## 外部依赖要求

用户环境需要：
1. `claude` CLI 已安装（Claude Code）
2. `gh` CLI 已安装并完成 `gh auth login`
3. Python 3.11+
4. `uv`（推荐）或 `pip`

---

## 当前状态

- [x] 项目创建，架构设计完成
- [x] `planner.py` — 实现 GitHub Issues 读取（含超时、JSON 解析错误处理；支持 `--gh-repo` 参数）
- [x] `executor.py` — 实现 claude CLI 调用（Popen 流式输出；`encoding="utf-8", errors="replace"` Windows 兼容修复）
- [x] `verifier.py` — 实现测试自动检测（使用 `shutil.which`、含超时处理；encoding 修复）
- [x] `git_ops.py` — 实现 git 操作（push 失败不抛异常、rollback 错误吞没并记录；新增 `close_issue()`、`get_diff()`；所有调用 encoding 修复）
- [x] `loop.py` — 实现主循环（含 catch-all 异常处理；4 步进度提示；运行后摘要表；elapsed 计时；diff 快照记录；dry-run 支持；结果写入 `~/.gh-autoloop/results/`）
- [x] `cli.py` — 实现 CLI 入口（含前置依赖检查；`--dry-run`、`--gh-repo` 新参数；`PYTHONUTF8=1` Windows 修复）
- [x] `__init__.py` — 数据类 + `check_prerequisites()` 前置检查（encoding 修复）
- [x] 测试用例（74 个测试，6 个测试文件：单元测试 + 集成测试）
- [x] README 完善（含 Windows 兼容性说明）
