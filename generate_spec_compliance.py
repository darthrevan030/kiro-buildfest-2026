#!/usr/bin/env python3
"""SPEC_COMPLIANCE.md generator script.

Reads .kiro/specs/tasks.md, parses task checkboxes, verifies artifact
existence using a keyword-to-file mapping, and outputs a compliance
report as a 4-column Markdown table.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5
"""

import glob
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


# Keyword-to-file mapping table (Requirement 8.3)
KEYWORD_MAPPING = [
    (["requirements"], ".kiro/specs/requirements.md"),
    (["design"], ".kiro/specs/design.md"),
    (["fixture"], "fixtures/"),
    (["mcp", "MCP"], "mcp_server/aws_janitor_mcp.py"),
    (["FinOps", "finops"], "agents/finops_auditor.py"),
    (["SecOps", "secops"], "agents/secops_guard.py"),
    (["Remediation", "remediation"], "agents/remediation_architect.py"),
    (["rollback"], "rollbacks/"),
    (["findings_store"], "findings_store.json"),
    (["pre-remediation"], ".kiro/hooks/pre-remediation.sh"),
    (["post-remediation"], ".kiro/hooks/post-remediation.sh"),
    (["approval"], "__APPROVE_STRING_CHECK__"),
    (["audit log"], "__AUDIT_LOG_CHECK__"),
    (["Streamlit", "UI", "app.py"], "app.py"),
    (["savings"], "savings.py"),
]


def find_tasks_md(project_root: Path) -> Path | None:
    """Find tasks.md, trying the literal path first then subdirectories."""
    # Try literal path from requirement
    literal = project_root / ".kiro" / "specs" / "tasks.md"
    if literal.exists():
        return literal

    # Search subdirectories of .kiro/specs/
    specs_dir = project_root / ".kiro" / "specs"
    if specs_dir.exists():
        for tasks_file in sorted(specs_dir.rglob("tasks.md")):
            return tasks_file

    return None


def parse_tasks(content: str) -> list[dict]:
    """Parse checkbox lines from tasks.md content.

    Returns a list of dicts with keys: text, status
    where status is 'done', 'pending', or 'partial'.
    """
    tasks = []
    # Match top-level task lines (not sub-tasks indented with spaces)
    # Pattern: lines starting with "- [x]", "- [ ]", or "- [-]"
    pattern = re.compile(r"^- \[([ x\-])\]\s+(.+)$", re.MULTILINE)

    for match in pattern.finditer(content):
        marker = match.group(1)
        text = match.group(2).strip()

        if marker == "x":
            status = "done"
        elif marker == "-":
            status = "partial"
        else:
            status = "pending"

        tasks.append({"text": text, "status": status})

    return tasks


def check_approve_string(project_root: Path) -> bool:
    """Check if 'APPROVE' string exists in agents/ files or orchestrator.py."""
    # Check orchestrator.py
    orchestrator = project_root / "orchestrator.py"
    if orchestrator.exists():
        content = orchestrator.read_text(encoding="utf-8", errors="ignore")
        if "APPROVE" in content:
            return True

    # Check agents/ directory
    agents_dir = project_root / "agents"
    if agents_dir.exists():
        for py_file in agents_dir.glob("*.py"):
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            if "APPROVE" in content:
                return True

    return False


def check_audit_log(project_root: Path) -> bool:
    """Check if audit.log exists or an audit log writer is in the codebase."""
    # Check audit.log file
    if (project_root / "audit.log").exists():
        return True

    # Check for audit log writer in codebase (agents/ directory)
    agents_dir = project_root / "agents"
    if agents_dir.exists():
        for py_file in agents_dir.glob("*.py"):
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            if "audit" in content.lower() and ("log" in content.lower() or "logger" in content.lower()):
                return True

    # Check orchestrator.py
    orchestrator = project_root / "orchestrator.py"
    if orchestrator.exists():
        content = orchestrator.read_text(encoding="utf-8", errors="ignore")
        if "audit" in content.lower() and ("log" in content.lower() or "logger" in content.lower()):
            return True

    return False


def verify_artifact(task_text: str, project_root: Path) -> str:
    """Verify artifact existence for a task based on keyword mapping.

    Returns a description of the verification result.
    """
    for keywords, target in KEYWORD_MAPPING:
        matched_keyword = None
        for kw in keywords:
            if kw in task_text:
                matched_keyword = kw
                break

        if matched_keyword is None:
            continue

        # Special checks
        if target == "__APPROVE_STRING_CHECK__":
            if check_approve_string(project_root):
                return '"APPROVE" found in codebase'
            else:
                return '"APPROVE" not found in codebase'

        if target == "__AUDIT_LOG_CHECK__":
            if check_audit_log(project_root):
                return "audit log writer found"
            else:
                return "audit log not found"

        # File or directory check
        artifact_path = project_root / target
        if artifact_path.exists():
            if artifact_path.is_dir():
                return f"{target} exists"
            else:
                return f"{target} exists"
        else:
            return f"{target} missing"

    return "no mapping"


def generate_report(tasks: list[dict], project_root: Path) -> str:
    """Generate the SPEC_COMPLIANCE.md content."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    lines = [
        "# Spec Compliance Report",
        "",
        f"Generated: {now}",
        "",
        "| # | Task | Status | Artifact Verified |",
        "|---|------|--------|-------------------|",
    ]

    for i, task in enumerate(tasks, start=1):
        task_text = task["text"]
        status = task["status"]

        if status == "done":
            artifact_info = verify_artifact(task_text, project_root)
            status_display = "✅ Done"
        elif status == "partial":
            artifact_info = verify_artifact(task_text, project_root)
            status_display = "⏳ Partial"
        else:
            status_display = "❌ Pending"
            artifact_info = "—"

        # Clean task text for table display (remove trailing requirement refs)
        display_text = task_text.rstrip()

        lines.append(f"| {i} | {display_text} | {status_display} | {artifact_info} |")

    lines.append("")
    return "\n".join(lines)


def main():
    project_root = Path(__file__).resolve().parent

    # Find tasks.md
    tasks_md_path = find_tasks_md(project_root)
    if tasks_md_path is None:
        print("ERROR: tasks.md not found in .kiro/specs/", file=sys.stderr)
        sys.exit(1)

    # Read and parse
    content = tasks_md_path.read_text(encoding="utf-8")
    tasks = parse_tasks(content)

    if not tasks:
        print("WARNING: No task checkboxes found in tasks.md", file=sys.stderr)

    # Generate report
    report = generate_report(tasks, project_root)

    # Write output
    output_path = project_root / "SPEC_COMPLIANCE.md"
    output_path.write_text(report, encoding="utf-8")

    print(f"Generated {output_path} ({len(tasks)} tasks)")


if __name__ == "__main__":
    main()
