# ai-patch-risk-checker

`ai-patch-risk-checker` 是一个离线 Python CLI，用来在 AI 生成补丁进入 PR 或 CI 合并前做风险预检。

它面向使用 Codex、Claude Code、Cursor、ChatGPT 等 AI 编程工具的开发者和团队：当 agent 一次性改了鉴权、数据库迁移、依赖、CI、支付、前端状态或大量代码时，你需要一个本地、可审计、可 CI 化的工具先把风险点列出来，而不是完全依赖人工从巨大 diff 里临场发现问题。

## 真实场景

- Codex 或 Claude Code 生成了一组改动，你想在提交 PR 前快速知道是否缺测试、是否碰到高风险路径。
- 团队希望 AI 生成的补丁在 CI 中自动生成风险报告，帮助 reviewer 决定审查重点。
- 维护者接收外部贡献，希望统一检查依赖、迁移、鉴权、CI、锁文件和大删改。
- SRE 或安全同学想把“改了 auth/database/payments 必须有测试或说明”变成可执行门禁。
- 独立开发者在深夜合并 AI 补丁前，需要一个不会联网、不会上传代码的本地提醒器。

## 功能

- 读取 unified diff 文件、stdin 或 `git diff` / `git diff --cached`。
- 解析每个文件的状态、加行、删行、扩展名和路径。
- 按路径识别 `auth`、`database`、`payments`、`dependencies`、`ci`、`frontend`、`tests` 等类别。
- 检测疑似密钥新增，包括 `github_pat_`、`ghp_`、`sk-`、AWS key、private key 和常见 key/value 形态。
- 检查代码变更缺少测试、高风险类别缺少测试、大补丁、大删改、锁文件或生成物变更。
- 输出 Markdown、JSON、CSV、SARIF 报告。
- SARIF 可直接上传到 GitHub Code Scanning，让 AI 补丁风险出现在仓库安全/代码扫描视图里。
- `check` 模式可按严重度阈值返回非零退出码，用于 CI。
- baseline 文件可记录团队已审阅的历史风险，CI 只拦截 AI 补丁引入的新风险。
- JSON 配置可覆盖阈值、类别路径和需要测试的类别。
- 仅使用 Python 标准库，无需网络。

## 安装

需要 Python 3.9 或更新版本。

```bash
python -m pip install -e .
```

安装后：

```bash
aipatchrisk --help
```

不安装也可从源码运行：

```bash
python -m ai_patch_risk_checker.cli --help
```

## 快速开始

分析一个 diff 文件：

```bash
aipatchrisk analyze --diff examples/auth-without-tests.diff
```

输出 JSON：

```bash
aipatchrisk analyze --diff examples/auth-without-tests.diff --format json --output report.json
```

输出 SARIF，供 GitHub Code Scanning 或其他安全平台读取：

```bash
aipatchrisk check --diff examples/auth-without-tests.diff --format sarif --output patch-risk.sarif
```

检查当前工作区未暂存改动：

```bash
aipatchrisk check --git
```

检查 staged diff：

```bash
aipatchrisk check --git --staged
```

从 stdin 读取：

```bash
git diff --cached | aipatchrisk check --format markdown
```

生成并使用已知风险 baseline：

```bash
aipatchrisk baseline --diff examples/auth-without-tests.diff --output ai-patch-risk-baseline.json
aipatchrisk check --diff examples/auth-without-tests.diff --baseline ai-patch-risk-baseline.json
```

## 配置

生成默认配置：

```bash
aipatchrisk init-config --output ai-patch-risk.json
```

示例：

```json
{
  "fail_on": "high",
  "large_change_lines": 500,
  "min_test_required_for_code": true,
  "require_tests_for_categories": ["auth", "database", "payments", "dependencies", "ci"],
  "categories": {
    "auth": ["auth/*", "*/auth/*", "*session*", "*oauth*"],
    "database": ["migrations/*", "*/migrations/*", "*.sql"],
    "dependencies": ["pyproject.toml", "package.json", "package-lock.json"]
  }
}
```

使用配置：

```bash
aipatchrisk check --git --config ai-patch-risk.json
```

## Baseline 工作流

baseline 是一个可审阅、可提交的 JSON 文件，用来记录团队已经接受或排期处理的既有 finding。它不会关闭规则，只会按稳定 fingerprint 压制已知项，让 CI 专注拦截新增风险。

```bash
aipatchrisk baseline --git --staged --output ai-patch-risk-baseline.json
aipatchrisk check --git --staged --baseline ai-patch-risk-baseline.json --format json --output patch-risk.json
```

建议流程：

1. 首次接入时生成 `ai-patch-risk-baseline.json`。
2. 人工审阅 baseline 中的 `code`、`severity`、`paths` 和 `fingerprint`。
3. 把 baseline 文件提交到仓库。
4. CI 中使用 `--baseline ai-patch-risk-baseline.json`，只让新增风险导致失败。

过滤后的 JSON、Markdown、CSV 和 SARIF 仍会保留 suppressed 信息，例如 `suppressed_finding_count` 或 `suppressed_findings`，方便后续逐步清理技术债。

## 风险规则

| Code | Severity | 说明 |
| --- | --- | --- |
| `secret_like_addition` | critical | 新增内容疑似包含凭证或私钥 |
| `auth_without_tests` | high | 鉴权相关路径变更但没有测试变更 |
| `database_without_tests` | high | 数据库/迁移相关路径变更但没有测试变更 |
| `payments_without_tests` | high | 支付/账单相关路径变更但没有测试变更 |
| `dependencies_without_tests` | high | 依赖文件变更但没有测试变更 |
| `ci_without_tests` | high | CI / Docker 等构建路径变更但没有测试变更 |
| `code_without_tests` | medium | 代码变更但没有测试变更 |
| `large_patch` | medium | 补丁总行数超过阈值 |
| `large_deletion` | medium | 大量删除且替换很少 |
| `generated_or_lockfile_changed` | low | 锁文件、构建输出或生成物发生变化 |

严重度是 review 线索，不代表 bug 一定存在。工具目的是把 AI 补丁的审查重点提前暴露出来。

每条 finding 都会带一个稳定 `fingerprint`，由规则 code 和归一化路径生成。它可用于 baseline、审计表格或外部质量平台去重。

## 输出

Markdown 报告适合贴到 PR：

```bash
aipatchrisk analyze --diff patch.diff --format markdown
```

JSON 报告适合自动化处理：

```bash
aipatchrisk inspect --diff patch.diff
```

CSV 报告适合导入表格或审计台账：

```bash
aipatchrisk analyze --diff patch.diff --format csv --output findings.csv
```

SARIF 报告适合接入 GitHub Code Scanning：

```bash
aipatchrisk check --diff patch.diff --format sarif --output patch-risk.sarif
```

baseline 过滤后的 JSON 会保留压制摘要：

```json
{
  "summary": {
    "finding_count": 0,
    "suppressed_finding_count": 2,
    "risk_level": "none"
  }
}
```

## CI 用法

GitHub Actions 示例：

```yaml
- name: Check AI patch risk
  run: |
    git diff origin/main...HEAD > patch.diff
    python -m ai_patch_risk_checker.cli check --diff patch.diff --baseline ai-patch-risk-baseline.json --format markdown --output patch-risk.md
```

如果风险级别达到配置中的 `fail_on`，`check` 会返回非零退出码。

上传 SARIF 到 GitHub Code Scanning：

```yaml
permissions:
  contents: read
  security-events: write

steps:
  - uses: actions/checkout@v4
    with:
      fetch-depth: 0
  - uses: actions/setup-python@v5
    with:
      python-version: "3.12"
  - run: python -m pip install git+https://github.com/yanqr213/ai-patch-risk-checker.git
  - name: Build patch risk SARIF
    run: |
      git diff origin/main...HEAD > patch.diff
      aipatchrisk check --diff patch.diff --format sarif --output patch-risk.sarif
  - uses: github/codeql-action/upload-sarif@v3
    if: always()
    with:
      sarif_file: patch-risk.sarif
```

如果你只想把报告上传但暂不阻断合并，可以在 `ai-patch-risk.json` 中把 `fail_on` 设为 `critical`，或把 `check` 换成 `analyze`。

CI 中消费已提交 baseline：

```yaml
- name: Fail only on new AI patch risks
  run: aipatchrisk check --diff patch.diff --baseline ai-patch-risk-baseline.json --format json --output patch-risk.json
```

不要在同一个阻断型 CI run 里现生成 baseline 再过滤当前 diff；baseline 应该在接入或风险复核后由维护者提交。

## 隐私与安全

- 工具只读取本地 diff，不联网，不上传代码。
- 工具不会读取、请求或推送 GitHub token。
- 密钥检测是启发式，不替代专门的 secret scanner。
- baseline 是审计文件，不是忽略规则；请像维护测试快照一样审阅它。
- 如果报告进入 PR 或工单，请确认其中没有业务敏感上下文。
- 如果检测到真实凭证，请删除补丁里的凭证并轮换。

## 本地开发

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python -m ai_patch_risk_checker.cli analyze --diff examples/auth-without-tests.diff
```

## English

`ai-patch-risk-checker` is an offline Python CLI for reviewing AI-generated patch risk before a PR or CI merge.

It helps teams using Codex, Claude Code, Cursor, ChatGPT, and similar coding agents detect review hot spots in a unified diff: auth changes without tests, database or migration changes without tests, dependency and CI changes, secret-like additions, large patches, large deletions, and generated or lockfile updates.

### Features

- Reads unified diff files, stdin, `git diff`, or `git diff --cached`.
- Parses changed files, statuses, additions, deletions, and added/deleted lines.
- Categorizes touched paths such as auth, database, payments, dependencies, CI, frontend, and tests.
- Detects secret-like additions including GitHub PAT shapes, `ghp_`, `sk-`, AWS access keys, private keys, and common key/value assignments.
- Emits Markdown, JSON, CSV, and SARIF reports.
- Uploads SARIF to GitHub Code Scanning so AI patch risks show up where maintainers already review security and quality alerts.
- Provides a `check` mode with severity-based exit codes for CI.
- Supports reviewed baseline files so teams can fail CI only on newly introduced AI patch risks.
- Uses only the Python standard library and does not require network access.

### Quick Start

```bash
python -m pip install -e .
aipatchrisk analyze --diff examples/auth-without-tests.diff
```

Check staged changes:

```bash
aipatchrisk check --git --staged
```

Create a config:

```bash
aipatchrisk init-config --output ai-patch-risk.json
```

Write SARIF for code scanning:

```bash
aipatchrisk check --diff examples/auth-without-tests.diff --format sarif --output patch-risk.sarif
```

Create and use a baseline:

```bash
aipatchrisk baseline --diff examples/auth-without-tests.diff --output ai-patch-risk-baseline.json
aipatchrisk check --diff examples/auth-without-tests.diff --baseline ai-patch-risk-baseline.json
```

### Baselines

Baselines are reviewed JSON files containing known finding fingerprints. They are useful when a team wants to adopt the checker on an existing repository without failing CI for every previously accepted risk.

```bash
aipatchrisk baseline --git --staged --output ai-patch-risk-baseline.json
aipatchrisk check --git --staged --baseline ai-patch-risk-baseline.json --format json --output patch-risk.json
```

A practical rollout is:

1. Generate `ai-patch-risk-baseline.json` for the current diff or staged change.
2. Review the finding codes, severities, paths, and fingerprints.
3. Commit the baseline file.
4. Run CI with `--baseline ai-patch-risk-baseline.json` so only new findings fail the build.

JSON, CSV, Markdown, and SARIF outputs include finding fingerprints. Filtered reports also keep suppressed finding metadata through `suppressed_finding_count` and `suppressed_findings`.

### CI

```bash
git diff origin/main...HEAD > patch.diff
python -m ai_patch_risk_checker.cli check --diff patch.diff --baseline ai-patch-risk-baseline.json --format json --output patch-risk.json
```

`check` returns a non-zero exit code when the highest finding severity is at or above `fail_on`.

GitHub Code Scanning example:

```yaml
permissions:
  contents: read
  security-events: write

steps:
  - uses: actions/checkout@v4
    with:
      fetch-depth: 0
  - uses: actions/setup-python@v5
    with:
      python-version: "3.12"
  - run: python -m pip install git+https://github.com/yanqr213/ai-patch-risk-checker.git
  - name: Build patch risk SARIF
    run: |
      git diff origin/main...HEAD > patch.diff
      aipatchrisk check --diff patch.diff --format sarif --output patch-risk.sarif
  - uses: github/codeql-action/upload-sarif@v3
    if: always()
    with:
      sarif_file: patch-risk.sarif
```

### Security Notes

The tool runs locally and does not upload code. Secret detection is heuristic and should complement, not replace, a dedicated secret scanner. Reports can still contain sensitive business context, so treat them as development artifacts.

## License

MIT
