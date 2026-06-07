# Contributing

欢迎贡献规则、测试和真实团队工作流案例。

## 本地流程

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python -m ai_patch_risk_checker.cli analyze --diff examples/auth-without-tests.diff
```

## Guidelines

- Keep the runtime dependency-free unless a strong reason is documented.
- Add tests for every new rule, parser behavior, or report field.
- Do not commit real diffs containing secrets, private customer names, or internal endpoints.
- Prefer configurable rules over hard-coded organization-specific policy.
