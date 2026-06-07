"""Configuration loading."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .models import CheckConfig


DEFAULT_CATEGORIES: Dict[str, List[str]] = {
    "auth": ["auth/*", "*/auth/*", "*security*", "*permission*", "*session*", "*oauth*"],
    "database": ["migrations/*", "*/migrations/*", "*schema*", "*.sql"],
    "payments": ["*billing*", "*payment*", "*checkout*", "*invoice*", "*stripe*"],
    "dependencies": ["requirements*.txt", "pyproject.toml", "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "go.mod", "Cargo.toml"],
    "ci": [".github/workflows/*", ".gitlab-ci.yml", "Jenkinsfile", "Dockerfile", "docker-compose*.yml"],
    "frontend": ["*.js", "*.jsx", "*.ts", "*.tsx", "*.css", "*.html"],
    "tests": ["tests/*", "test/*", "*_test.*", "*.test.*", "*.spec.*"],
}


DEFAULT_CONFIG = CheckConfig(categories=DEFAULT_CATEGORIES)


def load_config(path: Path | None) -> CheckConfig:
    """Load optional JSON config."""

    if path is None:
        return DEFAULT_CONFIG
    data = json.loads(path.read_text(encoding="utf-8"))
    categories = dict(DEFAULT_CATEGORIES)
    categories.update({key: list(value) for key, value in data.get("categories", {}).items()})
    return CheckConfig(
        fail_on=data.get("fail_on", DEFAULT_CONFIG.fail_on),
        large_change_lines=int(data.get("large_change_lines", DEFAULT_CONFIG.large_change_lines)),
        min_test_required_for_code=bool(data.get("min_test_required_for_code", DEFAULT_CONFIG.min_test_required_for_code)),
        require_tests_for_categories=set(data.get("require_tests_for_categories", sorted(DEFAULT_CONFIG.require_tests_for_categories))),
        categories=categories,
    )


def default_config_json() -> str:
    """Return a documented default config."""

    data = {
        "fail_on": "high",
        "large_change_lines": DEFAULT_CONFIG.large_change_lines,
        "min_test_required_for_code": True,
        "require_tests_for_categories": sorted(DEFAULT_CONFIG.require_tests_for_categories),
        "categories": DEFAULT_CATEGORIES,
    }
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
