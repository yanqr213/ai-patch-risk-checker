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
