"""Shared data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set


@dataclass(frozen=True)
class FileChange:
    """One file touched by a unified diff."""

    old_path: str
    new_path: str
    status: str
    additions: int = 0
    deletions: int = 0
    added_lines: List[str] = field(default_factory=list)
    deleted_lines: List[str] = field(default_factory=list)

    @property
    def path(self) -> str:
        return self.new_path if self.new_path != "/dev/null" else self.old_path

    @property
    def extension(self) -> str:
        name = self.path.rsplit("/", 1)[-1]
        return "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""


@dataclass(frozen=True)
class Finding:
    """Risk finding emitted by the checker."""

    code: str
    severity: str
    message: str
    paths: List[str] = field(default_factory=list)
    recommendation: str = ""


@dataclass
class PatchReport:
    """Complete risk report."""

    files: List[FileChange]
    findings: List[Finding]
    touched_categories: Dict[str, List[str]]
    test_paths: List[str]
    summary: Dict[str, object]


@dataclass(frozen=True)
class CheckConfig:
    """Configurable risk thresholds and path categories."""

    fail_on: str = "high"
    large_change_lines: int = 600
    min_test_required_for_code: bool = True
    require_tests_for_categories: Set[str] = field(default_factory=lambda: {"auth", "database", "payments", "dependencies", "ci"})
    categories: Dict[str, List[str]] = field(default_factory=dict)
