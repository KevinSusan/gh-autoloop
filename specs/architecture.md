# gh-autoloop 架构设计

## 整体流程

```
AutoLoop.run()
  ├── Planner.get_tasks()        # 从 GitHub Issues 获取待办任务
  └── for task in tasks:
        ├── Executor.run(task)   # 调用 claude CLI 执行
        ├── Verifier.verify()    # 运行测试验证
        ├── 成功 → GitOps.commit_and_push(task)
        └── 失败 → GitOps.rollback()
```

---

## 模块设计

### `planner.py` — 任务来源

```python
class Planner:
    def get_tasks(self, repo: str, label: str | None) -> list[Task]
    # 调用: gh issue list --repo <repo> --json number,title,body --state open
    # 返回: Task(number, title, body) 列表，按 issue number 升序
```

**Task 数据结构**：
```python
@dataclass
class Task:
    number: int      # issue number
    title: str       # issue 标题
    body: str        # issue 描述（作为 claude 的任务输入）
```

---

### `executor.py` — Claude Code 执行器

```python
class Executor:
    def run(self, task: Task, repo_path: str) -> ExecutionResult
    # 调用: claude --print "<task prompt>" 在 repo_path 目录下
    # 超时: 默认 10 分钟
    # 返回: ExecutionResult(success, output, exit_code)
```

**任务 prompt 模板**：
```
Fix GitHub Issue #{number}: {title}

{body}

Please analyze the codebase, implement the fix, and make sure existing tests pass.
```

---

### `verifier.py` — 测试验证

```python
class Verifier:
    def verify(self, repo_path: str) -> VerifyResult
    # 按优先级检测并运行：
    #   1. pytest（检测 tests/ 目录或 pytest.ini）
    #   2. npm test（检测 package.json）
    #   3. make test（检测 Makefile）
    #   4. 均不存在 → 返回 skipped
    # 返回: VerifyResult(status: passed|failed|skipped, output)
```

---

### `git_ops.py` — Git 操作

```python
class GitOps:
    def commit_and_push(self, task: Task) -> str  # 返回 commit sha
    # git add -A
    # git commit -m "fix: {title} (closes #{number})"
    # git push

    def rollback(self) -> None
    # git checkout -- .
    # git clean -fd  (清理新增的未跟踪文件)

    def has_changes(self) -> bool
    # git diff --quiet && git diff --cached --quiet
```

---

### `loop.py` — 主循环

```python
@dataclass
class LoopConfig:
    repo_path: str
    max_iterations: int = 10
    label: str | None = None
    output_path: str = "loop_result.json"

class AutoLoop:
    def run(self, config: LoopConfig) -> LoopResult
```

**循环逻辑**：
```
1. tasks = planner.get_tasks()
2. for i, task in enumerate(tasks):
     if i >= max_iterations: break
     executor.run(task)
     if not git_ops.has_changes():
         record skipped
         continue
     verify_result = verifier.verify()
     if verify_result.passed:
         sha = git_ops.commit_and_push(task)
         record success(sha)
     else:
         git_ops.rollback()
         record failed(error)
3. save loop_result.json
```

---

### `cli.py` — 命令行入口

```
gh-autoloop run [--repo PATH] [--max-iter N] [--label LABEL]
gh-autoloop status [--result loop_result.json]
```

---

## 依赖关系图

```
cli.py
  └── loop.py
        ├── planner.py   (gh CLI)
        ├── executor.py  (claude CLI)
        ├── verifier.py  (pytest/npm/make)
        └── git_ops.py   (git)
```

所有模块只依赖 Python 标准库 + subprocess，无第三方 AI SDK。

---

## 错误处理策略

| 场景 | 处理方式 |
|------|----------|
| `gh` CLI 未安装 | 启动时检查，给出安装提示后退出 |
| `claude` CLI 未安装 | 启动时检查，给出安装提示后退出 |
| claude 执行超时 | 标记 failed，rollback，继续下一个 |
| git push 失败 | 记录警告，commit 保留本地，继续 |
| 无 open issues | 正常退出，输出提示 |
| 无网络/gh 认证失败 | 报错退出，提示 `gh auth login` |
