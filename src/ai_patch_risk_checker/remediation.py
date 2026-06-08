"""Remediation plans for AI patch risk findings."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Dict, List

from .baseline import attach_fingerprints
from .models import Finding, PatchReport


@dataclass(frozen=True)
class RemediationTask:
    task_id: str
    priority: str
    severity: str
    code: str
    title: str
    paths: List[str]
    owner_hint: str
    summary: str
    recommended_action: str
    acceptance_criteria: List[str]
    agent_prompt: str
    fingerprint: str


PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def build_remediation_plan(report: PatchReport) -> List[RemediationTask]:
    """Build prioritized repair tasks from active findings."""

    attach_fingerprints(report)
    tasks = [_task_for_finding(report, finding) for finding in report.findings]
    return sorted(
        tasks,
        key=lambda item: (PRIORITY_ORDER.get(item.priority, 9), item.code, ",".join(item.paths), item.fingerprint),
    )


def render_remediation_json(report: PatchReport) -> str:
    tasks = build_remediation_plan(report)
    payload = {
        "schema": "ai-patch-risk-checker.remediation.v1",
        "summary": {
            "task_count": len(tasks),
            "risk_level": report.summary.get("risk_level", "none"),
            "findings": report.summary.get("finding_count", 0),
            "suppressed": report.summary.get("suppressed_finding_count", 0),
            "priorities": _priority_counts(tasks),
        },
        "tasks": [asdict(task) for task in tasks],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_remediation_markdown(report: PatchReport) -> str:
    tasks = build_remediation_plan(report)
    lines = [
        "# AI Patch Risk Remediation Plan",
        "",
        "- Risk level: `%s`" % report.summary.get("risk_level", "none"),
        "- Tasks: `%s`" % len(tasks),
        "- Findings: `%s`" % report.summary.get("finding_count", 0),
        "- Suppressed by baseline: `%s`" % report.summary.get("suppressed_finding_count", 0),
        "",
    ]
    if not tasks:
        lines.extend(["## Tasks", "", "No active remediation tasks after baseline filtering.", ""])
        return "\n".join(lines)
    for task in tasks:
        paths = ", ".join("`%s`" % path for path in task.paths) if task.paths else "`patch.diff`"
        lines.extend(
            [
                "## %s: %s" % (task.task_id, task.title),
                "",
                "- Priority: `%s`" % task.priority,
                "- Severity: `%s`" % task.severity,
                "- Code: `%s`" % task.code,
                "- Owner hint: `%s`" % task.owner_hint,
                "- Paths: %s" % paths,
                "- Fingerprint: `%s`" % task.fingerprint,
                "",
                "### Summary",
                "",
                task.summary,
                "",
                "### Recommended Action",
                "",
                task.recommended_action,
                "",
                "### Acceptance Criteria",
                "",
            ]
        )
        for criterion in task.acceptance_criteria:
            lines.append("- %s" % criterion)
        lines.extend(["", "### Agent Prompt", "", "```text", task.agent_prompt, "```", ""])
    return "\n".join(lines)


def _task_for_finding(report: PatchReport, finding: Finding) -> RemediationTask:
    priority = _priority(finding)
    owner_hint = _owner_hint(finding)
    action = _recommended_action(finding)
    criteria = _acceptance_criteria(finding)
    task_id = "APR-%s-%s" % (priority, (finding.fingerprint or "pending")[:8])
    title = finding.code.replace("_", " ").replace("-", " ").title()
    summary = "%s: %s" % (title, finding.message)
    return RemediationTask(
        task_id=task_id,
        priority=priority,
        severity=finding.severity,
        code=finding.code,
        title=title,
        paths=list(finding.paths),
        owner_hint=owner_hint,
        summary=summary,
        recommended_action=action,
        acceptance_criteria=criteria,
        agent_prompt=_agent_prompt(report, finding, priority, owner_hint, action, criteria),
        fingerprint=finding.fingerprint,
    )


def _priority(finding: Finding) -> str:
    if finding.severity == "critical" or finding.code == "secret_like_addition":
        return "P0"
    if finding.severity == "high":
        return "P1"
    if finding.severity == "medium":
        return "P2"
    return "P3"


def _owner_hint(finding: Finding) -> str:
    code = finding.code
    if "secret" in code:
        return "security-owner"
    if any(token in code for token in ("auth", "payments", "database")):
        return "domain-owner"
    if "dependencies" in code:
        return "dependency-owner"
    if "ci" in code:
        return "ci-owner"
    if "test" in code or "without_tests" in code:
        return "test-owner"
    if "large" in code:
        return "review-lead"
    return "change-owner"


def _recommended_action(finding: Finding) -> str:
    code = finding.code
    if code == "secret_like_addition":
        return "Remove the secret-like value from the patch, rotate the credential if it was real, and replace it with a managed-secret reference or redacted placeholder."
    if code.endswith("_without_tests") or code == "code_without_tests":
        return "Add focused tests for the changed behavior, or add an explicit reviewer note explaining why existing coverage is sufficient."
    if code == "large_patch":
        return "Split the patch into smaller reviewable commits or add a reviewer checklist that covers each touched subsystem."
    if code == "large_deletion":
        return "Confirm the deletion is intentional, add migration or rollback notes, and ensure removed behavior is covered by tests or release notes."
    if code == "generated_or_lockfile_changed":
        return "Regenerate the file with a documented command and verify that lockfile or build-output changes are reproducible."
    return finding.recommendation or "Resolve the finding and rerun ai-patch-risk-checker before merging."


def _acceptance_criteria(finding: Finding) -> List[str]:
    criteria = [
        "Rerunning ai-patch-risk-checker no longer reports this finding as an active unreviewed risk.",
        "The PR or delivery notes explain the remediation decision in reviewer-auditable language.",
    ]
    if finding.paths:
        criteria.append("All affected paths are either updated, tested, split into smaller changes, or explicitly justified.")
    if finding.code == "secret_like_addition":
        criteria.append("No raw credential-like value remains in the diff, reports, or examples.")
    if finding.code.endswith("_without_tests") or finding.code == "code_without_tests":
        criteria.append("A relevant test path is added or the reviewer note names the existing coverage that applies.")
    return criteria


def _agent_prompt(report: PatchReport, finding: Finding, priority: str, owner_hint: str, action: str, criteria: List[str]) -> str:
    paths = ", ".join(finding.paths) if finding.paths else "patch.diff"
    lines = [
        "You are repairing an ai-patch-risk-checker finding before a PR is merged.",
        "Current patch risk level: %s." % report.summary.get("risk_level", "none"),
        "Priority: %s." % priority,
        "Owner hint: %s." % owner_hint,
        "Finding: [%s] %s." % (finding.severity.upper(), finding.code),
        "Paths: %s." % paths,
        "Message: %s" % finding.message,
        "Recommended action: %s" % action,
        "Acceptance criteria:",
    ]
    lines.extend("- %s" % item for item in criteria)
    lines.append("After the fix, rerun the exact ai-patch-risk-checker command and include the result in the delivery notes.")
    return "\n".join(lines)


def _priority_counts(tasks: List[RemediationTask]) -> Dict[str, int]:
    counts = {key: 0 for key in ("P0", "P1", "P2", "P3")}
    for task in tasks:
        counts[task.priority] = counts.get(task.priority, 0) + 1
    return counts
