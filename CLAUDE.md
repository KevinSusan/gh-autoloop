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
| AI 执行器 | 本地 `claude --print <task>` CLI |
| 验证方式 | 自动检测 pytest → npm test → make test |
| Commit message | `fix: <issue title> (closes #<num>)` |
| 失败处理 | `git checkout -- .` 自动回滚 |
| 推送策略 | 每次成功 commit 后自动 `git push` |

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

# 查看上次运行结果
gh-autoloop status
```

### 输出
- 每次运行生成 `loop_result.json`，记录每个 issue 的处理状态
- 格式：`{issue_num, title, status: success|failed|skipped, commit_sha, error}`

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
- [ ] `planner.py` — 实现 GitHub Issues 读取
- [ ] `executor.py` — 实现 claude CLI 调用
- [ ] `verifier.py` — 实现测试自动检测
- [ ] `git_ops.py` — 实现 git 操作
- [ ] `loop.py` — 实现主循环
- [ ] `cli.py` — 实现 CLI 入口
- [ ] 测试用例
- [ ] README 完善
