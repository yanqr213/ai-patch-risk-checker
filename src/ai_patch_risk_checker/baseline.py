"""Baseline support for known AI patch risk findings."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, Iterable, List, Set

from . import __version__
from .models import Finding, PatchReport


def fingerprint_finding(finding: Finding) -> str:
    """Return a stable fingerprint for a finding."""

    paths = sorted(_normalize_path(path) for path in finding.paths)
    payload = {
        "code": finding.code,
        "paths": paths,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]


def attach_fingerprints(report: PatchReport) -> PatchReport:
    """Fill missing finding fingerprints in-place and return the report."""

    for finding in report.findings:
        if not finding.fingerprint:
            object.__setattr__(finding, "fingerprint", fingerprint_finding(finding))
    for finding in report.suppressed_findings:
        if not finding.fingerprint:
            object.__setattr__(finding, "fingerprint", fingerprint_finding(finding))
    return report


def load_baseline(path: Path) -> Set[str]:
    """Load a baseline JSON file and return known finding fingerprints."""

    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        entries = data.get("findings", [])
    else:
        raise ValueError("Baseline must be a JSON object or list.")

    fingerprints = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        fingerprint = entry.get("fingerprint")
        if isinstance(fingerprint, str) and fingerprint:
            fingerprints.add(fingerprint)
    return fingerprints


def apply_baseline(report: PatchReport, fingerprints: Iterable[str]) -> PatchReport:
    """Suppress findings that already exist in the baseline."""

    known = set(fingerprints)
    attach_fingerprints(report)
    kept: List[Finding] = []
    suppressed: List[Finding] = []
    for finding in report.findings:
        if finding.fingerprint in known:
            suppressed.append(finding)
        else:
            kept.append(finding)
    report.findings = kept
    report.suppressed_findings = suppressed
    _refresh_summary(report)
    return report


def render_baseline(report: PatchReport) -> str:
    """Render all current findings as a baseline JSON document."""

    attach_fingerprints(report)
    data = {
        "schema_version": 1,
        "generated_by": "ai-patch-risk-checker",
        "tool_version": __version__,
        "description": "Known AI patch risk findings. Keep this file reviewed; CI can use it to fail only on new findings.",
        "findings": [
            {
                "fingerprint": finding.fingerprint,
                "code": finding.code,
                "severity": finding.severity,
                "paths": sorted(_normalize_path(path) for path in finding.paths),
                "message": finding.message,
                "recommendation": finding.recommendation,
            }
            for finding in sorted(report.findings, key=lambda item: (item.code, item.severity, item.fingerprint))
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def write_baseline(report: PatchReport, path: Path) -> None:
    """Write a baseline JSON file."""

    path.write_text(render_baseline(report), encoding="utf-8")


def _refresh_summary(report: PatchReport) -> None:
    report.summary["risk_level"] = _max_severity(report.findings)
    report.summary["finding_count"] = len(report.findings)
    report.summary["high_or_above"] = sum(1 for finding in report.findings if _severity_at_least(finding.severity, "high"))
    report.summary["suppressed_finding_count"] = len(report.suppressed_findings)


def _normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized.startswith("a/") or normalized.startswith("b/"):
        normalized = normalized[2:]
    return normalized


def _max_severity(findings: List[Finding]) -> str:
    if not findings:
        return "none"
    return max((finding.severity for finding in findings), key=lambda value: _severity_rank(value))


def _severity_at_least(actual: str, threshold: str) -> bool:
    return _severity_rank(actual) >= _severity_rank(threshold)


def _severity_rank(severity: str) -> int:
    return {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}.get(severity, 0)
