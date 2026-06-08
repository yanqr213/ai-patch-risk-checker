"""Command-line interface."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Iterable

from . import __version__
from .baseline import apply_baseline, load_baseline, render_baseline
from .config import default_config_json, load_config
from .diff_parser import parse_unified_diff
from .report import render_csv, render_json, render_markdown, render_sarif
from .remediation import render_remediation_json, render_remediation_markdown
from .rules import analyze_patch, severity_at_least


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "init-config":
        write_text(Path(args.output), default_config_json())
        print(f"Wrote config: {args.output}")
        return 0

    config = load_config(Path(args.config) if args.config else None)
    diff_text = read_diff(args)
    files = parse_unified_diff(diff_text)
    report = analyze_patch(files, config)

    if args.command == "baseline":
        output = render_baseline(report)
        if args.output == "-":
            print(output, end="")
        elif args.output:
            write_text(Path(args.output), output)
            print(f"Wrote baseline: {args.output}")
        else:
            print(output, end="")
        return 0

    if getattr(args, "baseline", None):
        report = apply_baseline(report, load_baseline(Path(args.baseline)))

    if args.command == "inspect":
        print(render_json(report), end="")
        return 0

    output = render_report(report, args.format)
    if args.output:
        write_text(Path(args.output), output)
        print(f"Wrote report: {args.output}")
    else:
        print(output, end="")

    if args.command == "check" and severity_at_least(str(report.summary["risk_level"]), config.fail_on):
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aipatchrisk", description="Review AI-generated patch risk before PRs and CI merges.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("analyze", "check", "inspect"):
        cmd = sub.add_parser(name, help=f"{name} a unified diff.")
        cmd.add_argument("--diff", help="Path to unified diff. Use '-' or omit to read stdin.")
        cmd.add_argument("--git", action="store_true", help="Read diff from `git diff --cached` or `git diff`.")
        cmd.add_argument("--staged", action="store_true", help="When --git is used, read staged diff.")
        cmd.add_argument("--config", help="Optional JSON config file.")
        cmd.add_argument("--baseline", help="Optional baseline JSON. Matching findings are suppressed before reporting and CI exit checks.")
        cmd.add_argument(
            "--format",
            choices=["markdown", "json", "csv", "sarif", "remediation", "remediation-json"],
            default="markdown",
            help="Report format.",
        )
        cmd.add_argument("--output", help="Write report to file.")

    baseline = sub.add_parser("baseline", help="Write a reviewed baseline JSON from current findings.")
    baseline.add_argument("--diff", help="Path to unified diff. Use '-' or omit to read stdin.")
    baseline.add_argument("--git", action="store_true", help="Read diff from `git diff --cached` or `git diff`.")
    baseline.add_argument("--staged", action="store_true", help="When --git is used, read staged diff.")
    baseline.add_argument("--config", help="Optional JSON config file.")
    baseline.add_argument("--output", default="ai-patch-risk-baseline.json", help="Baseline output path. Use '-' to print to stdout.")

    init = sub.add_parser("init-config", help="Write a default JSON config.")
    init.add_argument("--output", default="ai-patch-risk.json", help="Config output path.")
    return parser


def read_diff(args: argparse.Namespace) -> str:
    if args.git:
        command = ["git", "diff", "--cached" if args.staged else ""]
        command = [part for part in command if part]
        return subprocess.check_output(command, text=True, encoding="utf-8", errors="replace")
    if args.diff and args.diff != "-":
        return Path(args.diff).read_text(encoding="utf-8")
    return sys.stdin.read()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def render_report(report, format_name: str) -> str:
    if format_name == "json":
        return render_json(report)
    if format_name == "csv":
        return render_csv(report)
    if format_name == "sarif":
        return render_sarif(report)
    if format_name == "remediation":
        return render_remediation_markdown(report)
    if format_name == "remediation-json":
        return render_remediation_json(report)
    return render_markdown(report)


if __name__ == "__main__":
    raise SystemExit(main())
