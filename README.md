# gh-autoloop

> 用本地 Claude Code CLI 自动处理 GitHub Issues，实现项目自我迭代循环。

## 工作原理

```
读取 GitHub Issues
      ↓
  生成任务描述
      ↓
  调用 claude CLI 执行
      ↓
  自动验证（pytest/npm test...）
      ↓
  成功 → git commit + push
  失败 → git rollback，继续下一个
      ↓
  循环直到完成或达到上限
```

## 安装

```bash
# 前提：已安装 Claude Code 和 gh CLI
claude --version
gh --version

# 安装 gh-autoloop
uv pip install -e .
```

## 使用

```bash
# 在你的项目目录下运行
cd /path/to/your/project
gh-autoloop run

# 限制最多处理 5 个 issues
gh-autoloop run --max-iter 5

# 只处理带 bug 标签的 issues
gh-autoloop run --label bug

# 查看上次运行结果
gh-autoloop status
```

## 依赖

- Python 3.11+
- [Claude Code CLI](https://claude.ai/code)
- [GitHub CLI (gh)](https://cli.github.com/)
- git

## 输出

运行结束后生成 `loop_result.json`：

```json
{
  "summary": {"total": 3, "success": 2, "failed": 1},
  "results": [
    {"issue": 42, "title": "Fix login bug", "status": "success", "commit": "abc1234"},
    {"issue": 43, "title": "Add dark mode", "status": "failed", "error": "tests failed"}
  ]
}
```
