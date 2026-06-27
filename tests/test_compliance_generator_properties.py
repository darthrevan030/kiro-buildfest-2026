# Feature: savings-tracker-localstack, Property 6: Compliance generator parsing and mapping
"""Property-based tests for the SPEC_COMPLIANCE.md generator.

Uses Hypothesis to validate that the compliance generator correctly parses
checkbox states and maps task keywords to artifact paths.
"""

import re
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Add project root to path so we can import generate_spec_compliance
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from generate_spec_compliance import parse_tasks, KEYWORD_MAPPING, verify_artifact


# --- Keyword-to-artifact mapping table (canonical truth from requirements 8.3) ---
# Each tuple: (keyword_to_include_in_task_text, expected_artifact_path)
KEYWORD_ARTIFACT_PAIRS = [
    ("requirements", ".kiro/specs/requirements.md"),
    ("design", ".kiro/specs/design.md"),
    ("fixture", "fixtures/"),
    ("mcp", "mcp_server/aws_janitor_mcp.py"),
    ("MCP", "mcp_server/aws_janitor_mcp.py"),
    ("FinOps", "agents/finops_auditor.py"),
    ("finops", "agents/finops_auditor.py"),
    ("SecOps", "agents/secops_guard.py"),
    ("secops", "agents/secops_guard.py"),
    ("pre-remediation", ".kiro/hooks/pre-remediation.sh"),
    ("post-remediation", ".kiro/hooks/post-remediation.sh"),
    ("Remediation", "agents/remediation_architect.py"),
    ("remediation", "agents/remediation_architect.py"),
    ("rollback", "rollbacks/"),
    ("findings_store", "findings_store.json"),
    ("approval", "__approval_check__"),
    ("audit log", "__audit_log_check__"),
    ("Streamlit", "app.py"),
    ("UI", "app.py"),
    ("app.py", "app.py"),
    ("savings", "savings.py"),
]

# --- Strategies ---

# Checkbox states: 'x' (done), ' ' (pending), '-' (partial), '~' (partial)
checkbox_char_strategy = st.sampled_from(["x", " ", "-", "~"])

# Generate task description text that does NOT accidentally contain any keywords
# (used as filler/padding around intentional keywords)
_all_keywords = [kw for kw, _ in KEYWORD_ARTIFACT_PAIRS]


def _safe_filler():
    """Generate filler text that won't accidentally match keyword patterns."""
    return st.from_regex(r"[A-Z][a-z]{3,10}", fullmatch=True).filter(
        lambda s: not any(kw.lower() in s.lower() for kw in _all_keywords)
    )


# Strategy for a single keyword-artifact pair
keyword_pair_strategy = st.sampled_from(KEYWORD_ARTIFACT_PAIRS)


# --- Property 6: Compliance generator parsing and mapping ---


@settings(max_examples=100)
@given(
    checkbox_char=checkbox_char_strategy,
    keyword_pair=keyword_pair_strategy,
    prefix=_safe_filler(),
    suffix=_safe_filler(),
    indent=st.integers(min_value=0, max_value=4),
)
def test_compliance_generator_parsing_and_mapping(
    checkbox_char, keyword_pair, prefix, suffix, indent
):
    """
    Property 6: Compliance generator parsing and mapping

    For any tasks.md file containing lines with - [x], - [ ], or - [-]
    checkbox markers and task descriptions containing any of the defined
    keywords, the compliance generator SHALL correctly identify the checkbox
    state AND map the task to the correct artifact path according to the
    keyword-to-file mapping table.

    **Validates: Requirements 8.2, 8.3**
    """
    keyword, expected_artifact = keyword_pair

    # Build a task line with the given checkbox char and keyword embedded
    task_text = f"{prefix} {keyword} {suffix}"
    line = " " * indent + f"- [{checkbox_char}] {task_text}"

    # Build a minimal tasks.md content
    content = f"# Tasks\n\n{line}\n"

    # --- Test 1: parse_tasks correctly identifies checkbox state ---
    parsed = parse_tasks(content)

    assert len(parsed) == 1, f"Expected 1 task, got {len(parsed)}"
    task = parsed[0]

    # Verify the checkbox state is correctly identified
    assert task["status_char"] == checkbox_char, (
        f"Expected status_char='{checkbox_char}', got '{task['status_char']}'"
    )

    # Verify status_display is correct based on checkbox char
    if checkbox_char == "x":
        assert task["status_display"] == "✅ Done"
    elif checkbox_char == " ":
        assert task["status_display"] == "❌ Pending"
    elif checkbox_char in ("-", "~"):
        assert task["status_display"] == "⚠️ Partial"

    # Verify the task text is captured correctly
    assert task["task"] == task_text.strip()

    # --- Test 2: verify_artifact maps keyword to correct artifact ---
    # We test the keyword matching logic by checking that the mapping
    # returns the expected artifact path (existence check is separate concern)
    matched_artifact = _find_matching_artifact(task["task"])

    assert matched_artifact is not None, (
        f"No keyword mapping matched for task text: '{task['task']}' "
        f"(expected keyword '{keyword}' to match)"
    )
    assert matched_artifact == expected_artifact, (
        f"Expected artifact '{expected_artifact}' for keyword '{keyword}', "
        f"got '{matched_artifact}'"
    )


def _find_matching_artifact(task_text: str) -> str | None:
    """Find the first matching artifact path for a task text using KEYWORD_MAPPING.

    This mirrors the logic in generate_spec_compliance.py's verify_artifact()
    but returns just the artifact path without checking file existence.
    """
    for keyword_pattern, artifact_path in KEYWORD_MAPPING:
        if re.search(keyword_pattern, task_text):
            return artifact_path
    return None


@settings(max_examples=100)
@given(
    num_tasks=st.integers(min_value=1, max_value=10),
    data=st.data(),
)
def test_compliance_generator_multi_task_parsing(num_tasks, data):
    """
    Property 6 (extended): Multiple checkbox lines are all parsed correctly.

    For any tasks.md file with multiple checkbox lines, each line's checkbox
    state is correctly identified and each keyword maps to the correct artifact.

    **Validates: Requirements 8.2, 8.3**
    """
    lines = []
    expected_states = []
    expected_artifacts = []

    for _ in range(num_tasks):
        checkbox_char = data.draw(checkbox_char_strategy)
        keyword, artifact = data.draw(keyword_pair_strategy)
        prefix = data.draw(_safe_filler())
        suffix = data.draw(_safe_filler())

        task_text = f"{prefix} {keyword} {suffix}"
        line = f"- [{checkbox_char}] {task_text}"
        lines.append(line)
        expected_states.append(checkbox_char)
        expected_artifacts.append(artifact)

    content = "# Tasks\n\n" + "\n".join(lines) + "\n"

    # Parse the content
    parsed = parse_tasks(content)

    # Verify we got the expected number of tasks
    assert len(parsed) == num_tasks, (
        f"Expected {num_tasks} tasks, got {len(parsed)}"
    )

    # Verify each task's checkbox state
    for i, (task, expected_char) in enumerate(zip(parsed, expected_states)):
        assert task["status_char"] == expected_char, (
            f"Task {i}: Expected status_char='{expected_char}', "
            f"got '{task['status_char']}'"
        )

    # Verify each task's keyword mapping
    for i, (task, expected_art) in enumerate(zip(parsed, expected_artifacts)):
        matched = _find_matching_artifact(task["task"])
        assert matched is not None, (
            f"Task {i}: No keyword mapping matched for '{task['task']}'"
        )
        assert matched == expected_art, (
            f"Task {i}: Expected artifact '{expected_art}', got '{matched}'"
        )
