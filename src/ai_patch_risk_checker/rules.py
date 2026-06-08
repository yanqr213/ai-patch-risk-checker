"""Risk rules for AI-generated patches."""

from __future__ import annotations

import re
from fnmatch import fnmatchcase
from typing import Dict, Iterable, List, Sequence

from .baseline import attach_fingerprints
from .models import CheckConfig, FileChange, Finding, PatchReport

SEVERITY_ORDER = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}

SECRET_PATTERNS = [
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd|private[_-]?key)\b\s*[:=]\s*['\"]?[A-Za-z0-9_+/=-]{8,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
]

CODE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".rb", ".php", ".cs", ".sql"}
TEST_HINTS = ("test/", "tests/", "__tests__/", ".test.", ".spec.", "_test.")


def analyze_patch(files: Sequence[FileChange], config: CheckConfig) -> PatchReport:
    """Run all risk rules and return a report."""

    touched = categorize_files(files, config)
    test_paths = [file.path for file in files if is_test_path(file.path)]
    findings: List[Finding] = []

    findings.extend(_secret_findings(files))
    findings.extend(_large_change_findings(files, config))
    findings.extend(_category_findings(touched, test_paths, config))
    findings.extend(_missing_test_findings(files, test_paths, config))
    findings.extend(_deletion_findings(files))
    findings.extend(_generated_file_findings(files))

    summary = {
        "files_changed": len(files),
        "additions": sum(file.additions for file in files),
        "deletions": sum(file.deletions for file in files),
        "risk_level": max_severity(findings),
        "finding_count": len(findings),
        "high_or_above": sum(1 for finding in findings if severity_at_least(finding.severity, "high")),
        "suppressed_finding_count": 0,
    }
    return attach_fingerprints(PatchReport(files=list(files), findings=findings, touched_categories=touched, test_paths=test_paths, summary=summary))


def categorize_files(files: Iterable[FileChange], config: CheckConfig) -> Dict[str, List[str]]:
    """Map configured categories to changed paths."""

    touched: Dict[str, List[str]] = {}
    for file in files:
        path = file.path
        for category, patterns in config.categories.items():
            if any(_path_matches(path, pattern) for pattern in patterns):
                touched.setdefault(category, []).append(path)
    return {key: sorted(set(value)) for key, value in touched.items()}


def is_test_path(path: str) -> bool:
    """Return whether a path looks like a test."""

    lowered = path.lower().replace("\\", "/")
    return any(hint in lowered for hint in TEST_HINTS)


def max_severity(findings: Sequence[Finding]) -> str:
    """Return the highest severity in findings."""

    if not findings:
        return "none"
    return max((finding.severity for finding in findings), key=lambda value: SEVERITY_ORDER[value])


def severity_at_least(actual: str, threshold: str) -> bool:
    """Compare severity labels."""

    return SEVERITY_ORDER[actual] >= SEVERITY_ORDER[threshold]


def _secret_findings(files: Sequence[FileChange]) -> List[Finding]:
    findings = []
    for file in files:
        added_text = "\n".join(file.added_lines)
        if any(pattern.search(added_text) for pattern in SECRET_PATTERNS):
            findings.append(
                Finding(
                    code="secret_like_addition",
                    severity="critical",
                    message="Patch adds text that looks like a credential or private key.",
                    paths=[file.path],
                    recommendation="Remove the value, rotate it if real, and keep secrets in a managed store.",
                )
            )
    return findings


def _large_change_findings(files: Sequence[FileChange], config: CheckConfig) -> List[Finding]:
    total = sum(file.additions + file.deletions for file in files)
    if total <= config.large_change_lines:
        return []
    return [
        Finding(
            code="large_patch",
            severity="medium",
            message=f"Patch changes {total} lines, above configured threshold {config.large_change_lines}.",
            paths=[file.path for file in files],
            recommendation="Split the AI-generated patch or add a human review checklist for broad changes.",
        )
    ]


def _category_findings(touched: Dict[str, List[str]], test_paths: Sequence[str], config: CheckConfig) -> List[Finding]:
    findings = []
    for category in sorted(config.require_tests_for_categories):
        paths = touched.get(category, [])
        if paths and not test_paths:
            severity = "high" if category in {"auth", "database", "payments", "dependencies", "ci"} else "medium"
            findings.append(
                Finding(
                    code=f"{category}_without_tests",
                    severity=severity,
                    message=f"Patch touches {category} files but no test file was changed.",
                    paths=paths,
                    recommendation="Add or update focused tests, or document why existing coverage is sufficient.",
                )
            )
    return findings


def _missing_test_findings(files: Sequence[FileChange], test_paths: Sequence[str], config: CheckConfig) -> List[Finding]:
    if not config.min_test_required_for_code or test_paths:
        return []
    code_paths = [file.path for file in files if file.extension in CODE_EXTENSIONS and not is_test_path(file.path)]
    if not code_paths:
        return []
    return [
        Finding(
            code="code_without_tests",
            severity="medium",
            message="Patch changes code but does not change tests.",
            paths=code_paths,
            recommendation="Add tests or include a reviewer note explaining why tests were not changed.",
        )
    ]


def _deletion_findings(files: Sequence[FileChange]) -> List[Finding]:
    findings = []
    for file in files:
        if file.deletions >= 200 and file.deletions > file.additions * 3:
            findings.append(
                Finding(
                    code="large_deletion",
                    severity="medium",
                    message="Patch deletes a large amount of code with little replacement.",
                    paths=[file.path],
                    recommendation="Confirm this is intentional and that deleted behavior has coverage or migration notes.",
                )
            )
    return findings


def _generated_file_findings(files: Sequence[FileChange]) -> List[Finding]:
    generated = [file.path for file in files if _looks_generated(file.path)]
    if not generated:
        return []
    return [
        Finding(
            code="generated_or_lockfile_changed",
            severity="low",
            message="Patch changes generated, lock, or build output files.",
            paths=generated,
            recommendation="Confirm generated files were intentionally refreshed and are reproducible.",
        )
    ]


def _looks_generated(path: str) -> bool:
    lowered = path.lower()
    return any(part in lowered for part in ("dist/", "build/", "coverage/", ".min.js", "package-lock.json", "pnpm-lock.yaml", "yarn.lock"))


def _path_matches(path: str, pattern: str) -> bool:
    normalized = path.replace("\\", "/")
    pattern = pattern.replace("\\", "/")
    return fnmatchcase(normalized, pattern) or fnmatchcase(normalized.rsplit("/", 1)[-1], pattern)
