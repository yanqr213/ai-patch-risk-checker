"""Unified diff parser."""

from __future__ import annotations

from typing import List

from .models import FileChange


def parse_unified_diff(text: str) -> List[FileChange]:
    """Parse enough unified diff metadata for risk checks."""

    files: List[FileChange] = []
    current: dict | None = None
    old_path = ""
    new_path = ""

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        if line.startswith("diff --git "):
            if current is not None:
                files.append(_finish(current))
            parts = line.split()
            old_path = _strip_prefix(parts[2]) if len(parts) > 2 else ""
            new_path = _strip_prefix(parts[3]) if len(parts) > 3 else old_path
            current = _new_change(old_path, new_path)
            continue

        if current is None:
            if line.startswith("--- "):
                old_path = _strip_prefix(line[4:].strip())
                current = _new_change(old_path, old_path)
            else:
                continue

        if line.startswith("rename from "):
            current["old_path"] = line[len("rename from ") :].strip()
            current["status"] = "renamed"
        elif line.startswith("rename to "):
            current["new_path"] = line[len("rename to ") :].strip()
            current["status"] = "renamed"
        elif line.startswith("new file mode"):
            current["status"] = "added"
        elif line.startswith("deleted file mode"):
            current["status"] = "deleted"
        elif line.startswith("--- "):
            current["old_path"] = _strip_prefix(line[4:].strip())
        elif line.startswith("+++ "):
            current["new_path"] = _strip_prefix(line[4:].strip())
        elif line.startswith("+") and not line.startswith("+++"):
            current["additions"] += 1
            current["added_lines"].append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            current["deletions"] += 1
            current["deleted_lines"].append(line[1:])

    if current is not None:
        files.append(_finish(current))
    return [file for file in files if file.path]


def _new_change(old_path: str, new_path: str) -> dict:
    return {
        "old_path": old_path,
        "new_path": new_path,
        "status": "modified",
        "additions": 0,
        "deletions": 0,
        "added_lines": [],
        "deleted_lines": [],
    }


def _finish(current: dict) -> FileChange:
    old_path = current["old_path"]
    new_path = current["new_path"]
    status = current["status"]
    if old_path == "/dev/null":
        status = "added"
    elif new_path == "/dev/null":
        status = "deleted"
    return FileChange(
        old_path=old_path,
        new_path=new_path,
        status=status,
        additions=current["additions"],
        deletions=current["deletions"],
        added_lines=list(current["added_lines"]),
        deleted_lines=list(current["deleted_lines"]),
    )


def _strip_prefix(path: str) -> str:
    path = path.strip()
    if path in {"/dev/null", "dev/null"}:
        return "/dev/null"
    if path.startswith("a/") or path.startswith("b/"):
        return path[2:]
    return path
