"""Property-based tests for Compliance Generator output format.

Uses Hypothesis to validate that the compliance generator always produces
a valid 4-column Markdown table regardless of input task combinations.
"""

# Feature: savings-tracker-localstack, Property 7: Compliance generator output format

import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Add project root to path so we can import generate_spec_compliance
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from generate_spec_compliance import generate_compliance_report


# --- Strategies ---

# Generate a status character (x = done, space = pending, - = partial, ~ = partial)
status_char_strategy = st.sampled_from(["x", " ", "-", "~"])

# Generate task text (non-empty text, avoid pipe characters and newlines for simplicity)
task_text_strategy = st.text(
    min_size=1,
    max_size=100,
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        blacklist_characters=("\n", "\r", "\x00"),
    ),
)

# Generate a single parsed task dict (as returned by parse_tasks())
def task_strategy():
    """Generate a task dict matching the output format of parse_tasks()."""
    return st.fixed_dictionaries({
        "number": st.integers(min_value=1, max_value=9999),
        "task": task_text_strategy,
        "status_char": status_char_strategy,
        "status_display": st.sampled_from(["✅ Done", "❌ Pending", "⚠️ Partial"]),
    })


# Generate a list of parsed tasks (1 to 50 tasks)
tasks_strategy = st.lists(task_strategy(), min_size=1, max_size=50)


# --- Property 7: Compliance generator output format ---

@settings(max_examples=100)
@given(tasks=tasks_strategy)
def test_compliance_output_is_valid_markdown_table(tasks):
    """
    Property 7: Compliance generator output format

    For any set of parsed tasks (with varying checkbox states and artifact
    existence results), the compliance generator output SHALL be a valid
    Markdown table containing columns for task number, task description,
    status indicator, and artifact verification result.

    **Validates: Requirements 8.4**
    """
    # Mock verify_artifact to return a predictable result (since we're testing
    # the output FORMAT, not the artifact verification logic)
    with patch("generate_spec_compliance.verify_artifact", return_value="mocked artifact check"):
        report = generate_compliance_report(tasks)

    # The report must be a non-empty string
    assert isinstance(report, str)
    assert len(report) > 0

    # Split into lines
    lines = report.strip().split("\n")

    # Must have the title line
    assert lines[0] == "# Spec Compliance Report"

    # Must have the Generated timestamp line (after a blank line)
    assert lines[1] == ""
    assert lines[2].startswith("Generated: ")
    # Timestamp should be ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)
    timestamp_str = lines[2].replace("Generated: ", "")
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", timestamp_str), (
        f"Timestamp not in expected format: {timestamp_str}"
    )

    # After the timestamp there's a blank line, then the table header
    assert lines[3] == ""

    # Table header line (4th line after start, index 4)
    header_line = lines[4]
    assert header_line.startswith("|")
    assert header_line.endswith("|")

    # Parse header columns
    header_cols = [col.strip() for col in header_line.split("|")[1:-1]]
    assert len(header_cols) == 4, f"Expected 4 columns, got {len(header_cols)}: {header_cols}"
    assert header_cols[0] == "#"
    assert header_cols[1] == "Task"
    assert header_cols[2] == "Status"
    assert header_cols[3] == "Artifact Verified"

    # Separator line (index 5)
    separator_line = lines[5]
    assert separator_line.startswith("|")
    assert separator_line.endswith("|")
    # Separator should contain dashes and pipes
    sep_cols = [col.strip() for col in separator_line.split("|")[1:-1]]
    assert len(sep_cols) == 4, f"Separator should have 4 columns, got {len(sep_cols)}"
    for col in sep_cols:
        # Each separator column should be all dashes (possibly with colons for alignment)
        assert re.match(r"^:?-+:?$", col), f"Invalid separator column: '{col}'"

    # Data rows (starting from index 6)
    data_lines = lines[6:]
    assert len(data_lines) == len(tasks), (
        f"Expected {len(tasks)} data rows, got {len(data_lines)}"
    )

    for i, data_line in enumerate(data_lines):
        # Each data row must start and end with pipe
        assert data_line.startswith("|"), f"Row {i} doesn't start with '|': {data_line}"
        assert data_line.endswith("|"), f"Row {i} doesn't end with '|': {data_line}"

        # Each data row must have exactly 4 columns
        row_cols = [col.strip() for col in data_line.split("|")[1:-1]]
        assert len(row_cols) == 4, (
            f"Row {i} has {len(row_cols)} columns instead of 4: {row_cols}"
        )

        # First column should be the task number (a digit)
        assert row_cols[0].isdigit() or row_cols[0].replace(" ", "").isdigit(), (
            f"Row {i} first column is not a number: '{row_cols[0]}'"
        )

        # Third column should be a status indicator (✅ Done, ❌ Pending, or ⚠️ Partial)
        status = row_cols[2]
        assert status in ("✅ Done", "❌ Pending", "⚠️ Partial"), (
            f"Row {i} has invalid status: '{status}'"
        )

        # Fourth column should be non-empty (artifact verification result)
        assert len(row_cols[3]) > 0, f"Row {i} has empty artifact column"


@settings(max_examples=100)
@given(tasks=tasks_strategy)
def test_compliance_output_table_row_count_matches_tasks(tasks):
    """
    Supplementary check: The number of table data rows SHALL equal the number
    of input tasks.

    **Validates: Requirements 8.4**
    """
    with patch("generate_spec_compliance.verify_artifact", return_value="—"):
        report = generate_compliance_report(tasks)

    lines = report.strip().split("\n")

    # Find the separator line (contains |---|)
    sep_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^\|[-:|]+\|$", line.replace(" ", "")):
            sep_idx = i
            break

    assert sep_idx is not None, "Could not find separator line in output"

    # Data rows follow the separator
    data_rows = [l for l in lines[sep_idx + 1:] if l.strip()]
    assert len(data_rows) == len(tasks), (
        f"Expected {len(tasks)} data rows, got {len(data_rows)}"
    )
