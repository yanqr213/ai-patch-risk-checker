"""Report renderers."""

from __future__ import annotations

import csv
import io
import json
from typing import Dict

from .models import FileChange, Finding, PatchReport


def render_json(report: PatchReport) -> str:
    """Render report as JSON."""

    return json.dumps(to_dict(report), indent=2, ensure_ascii=False) + "\n"


def render_markdown(report: PatchReport) -> str:
    """Render report as Markdown."""

    lines = [
        "# AI Patch Risk Report",
        "",
        "## Summary",
        "",
        f"- Files changed: {report.summary['files_changed']}",
        f"- Additions: {report.summary['additions']}",
        f"- Deletions: {report.summary['deletions']}",
        f"- Risk level: {report.summary['risk_level']}",
        f"- Findings: {report.summary['finding_count']}",
        "",
        "## Findings",
        "",
    ]
    if report.findings:
        lines.extend(["| Severity | Code | Message | Paths | Recommendation |", "| --- | --- | --- | --- | --- |"])
        for finding in report.findings:
            lines.append(
                f"| {finding.severity} | `{finding.code}` | {escape_pipe(finding.message)} | {escape_pipe(', '.join(finding.paths))} | {escape_pipe(finding.recommendation)} |"
            )
    else:
        lines.append("_No findings._")

    lines.extend(["", "## Changed Files", "", "| Path | Status | + | - |", "| --- | --- | ---: | ---: |"])
    for file in report.files:
        lines.append(f"| `{escape_pipe(file.path)}` | {file.status} | {file.additions} | {file.deletions} |")

    if report.touched_categories:
        lines.extend(["", "## Touched Categories", ""])
        for category, paths in sorted(report.touched_categories.items()):
            lines.append(f"- **{category}**: {', '.join(f'`{path}`' for path in paths)}")

    return "\n".join(lines) + "\n"


def render_csv(report: PatchReport) -> str:
    """Render findings as CSV."""

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["severity", "code", "message", "paths", "recommendation"])
    for finding in report.findings:
        writer.writerow([finding.severity, finding.code, finding.message, "|".join(finding.paths), finding.recommendation])
    return buffer.getvalue()


def render_sarif(report: PatchReport) -> str:
    """Render findings as SARIF 2.1.0 for GitHub code scanning."""

    rules = {}
    for finding in report.findings:
        if finding.code in rules:
            continue
        rules[finding.code] = {
            "id": finding.code,
            "name": finding.code.replace("_", " ").title(),
            "shortDescription": {"text": finding.message},
            "fullDescription": {"text": finding.recommendation or finding.message},
            "help": {"text": finding.recommendation or finding.message},
            "properties": {
                "problem.severity": _sarif_severity(finding.severity),
                "security-severity": _security_severity(finding.severity),
                "tags": ["ai-patch-risk", finding.severity],
            },
        }

    results = []
    for finding in report.findings:
        paths = finding.paths or ["."]
        for path in paths:
            results.append(
                {
                    "ruleId": finding.code,
                    "level": _sarif_level(finding.severity),
                    "message": {"text": f"{finding.message} Recommendation: {finding.recommendation}".strip()},
                    "locations": [
                        {
                            "physicalLocation": {
                                "artifactLocation": {"uri": _sarif_uri(path)},
                                "region": {"startLine": 1},
                            }
                        }
                    ],
                    "properties": {"severity": finding.severity},
                }
            )

    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "ai-patch-risk-checker",
                        "informationUri": "https://github.com/yanqr213/ai-patch-risk-checker",
                        "rules": [rules[key] for key in sorted(rules)],
                    }
                },
                "results": results,
                "properties": {
                    "summary": report.summary,
                    "touched_categories": report.touched_categories,
                    "test_paths": report.test_paths,
                },
            }
        ],
    }
    return json.dumps(sarif, indent=2, ensure_ascii=False) + "\n"


def to_dict(report: PatchReport) -> Dict[str, object]:
    """Convert report to serializable dict."""

    return {
        "summary": report.summary,
        "findings": [finding_to_dict(finding) for finding in report.findings],
        "files": [file_to_dict(file) for file in report.files],
        "touched_categories": report.touched_categories,
        "test_paths": report.test_paths,
    }


def finding_to_dict(finding: Finding) -> Dict[str, object]:
    return {
        "code": finding.code,
        "severity": finding.severity,
        "message": finding.message,
        "paths": finding.paths,
        "recommendation": finding.recommendation,
    }


def file_to_dict(file: FileChange) -> Dict[str, object]:
    return {
        "old_path": file.old_path,
        "new_path": file.new_path,
        "path": file.path,
        "status": file.status,
        "additions": file.additions,
        "deletions": file.deletions,
        "extension": file.extension,
    }


def escape_pipe(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _sarif_uri(path: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized.startswith("a/") or normalized.startswith("b/"):
        normalized = normalized[2:]
    return normalized


def _sarif_level(severity: str) -> str:
    if severity in {"critical", "high"}:
        return "error"
    if severity == "medium":
        return "warning"
    return "note"


def _sarif_severity(severity: str) -> str:
    if severity == "critical":
        return "error"
    if severity == "high":
        return "warning"
    if severity == "medium":
        return "recommendation"
    return "note"


def _security_severity(severity: str) -> str:
    return {"critical": "9.0", "high": "7.0", "medium": "5.0", "low": "3.0"}.get(severity, "0.0")
