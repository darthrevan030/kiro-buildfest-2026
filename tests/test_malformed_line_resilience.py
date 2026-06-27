"""Property-based tests for malformed line resilience in reasoning log parsing.

Verifies that the log parser silently skips malformed (non-JSON) lines and
returns exactly the valid JSON lines in order, without raising exceptions.

# Feature: savings-tracker-localstack, Property 11: Malformed line resilience
"""

from __future__ import annotations

import json
from pathlib import Path

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st


# --- Replicate parse_reasoning_events from app.py ---
# (app.py cannot be imported directly in test context due to Streamlit side effects)


def parse_reasoning_events(log_path: Path | None = None) -> list[dict]:
    """Read agent_reasoning.log and return a list of parsed JSON events.

    Silently skips malformed lines (requirement 10.6).
    Returns an empty list if the file does not exist or cannot be read.
    """
    if log_path is None:
        return []
    if not log_path.exists():
        return []
    try:
        text = log_path.read_text(encoding="utf-8")
    except OSError:
        return []

    events: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            events.append(event)
        except (json.JSONDecodeError, ValueError):
            # Skip malformed lines silently (requirement 10.6)
            continue
    return events


# --- Strategies ---

# Arbitrary text that may or may not be valid JSON
arbitrary_text_strategy = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=0,
    max_size=200,
)

# Strategy for generating lines that are guaranteed NOT valid JSON and are single-line.
# We prefix with a non-JSON character to ensure invalidity and exclude line-break chars.
_safe_line_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters=("\n", "\r", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x85"),
)

malformed_line_strategy = st.text(
    alphabet=_safe_line_chars,
    min_size=0,
    max_size=100,
).map(lambda s: f"INVALID>>>{s}")  # Prefix guarantees it's never valid JSON

# Characters safe to use in JSON string values that won't cause splitlines issues
# when serialized. We blacklist surrogates and Unicode line/paragraph separators.
_json_safe_chars = st.characters(
    blacklist_categories=("Cs",),
    blacklist_characters=("\u2028", "\u2029"),
)

# Valid JSON event dicts (mimicking reasoning log events)
valid_event_strategy = st.fixed_dictionaries({
    "timestamp": st.text(
        alphabet=st.characters(whitelist_categories=("Nd", "L", "P")),
        min_size=1,
        max_size=30,
    ),
    "agent": st.text(
        alphabet=_json_safe_chars,
        min_size=1,
        max_size=64,
    ),
    "event_type": st.sampled_from(["check", "finding", "skip", "decision", "handoff"]),
    "resource_id": st.text(
        alphabet=_json_safe_chars,
        min_size=0,
        max_size=40,
    ),
    "message": st.text(
        alphabet=_json_safe_chars,
        min_size=0,
        max_size=100,
    ),
})


# --- Property 11: Malformed line resilience ---
# Feature: savings-tracker-localstack, Property 11: Malformed line resilience


@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    valid_events=st.lists(valid_event_strategy, min_size=1, max_size=10),
    malformed_lines=st.lists(malformed_line_strategy, min_size=1, max_size=10),
    interleave_seed=st.randoms(use_true_random=False),
)
def test_malformed_lines_skipped_valid_preserved(
    valid_events, malformed_lines, interleave_seed, tmp_path
):
    """
    Property 11: Malformed line resilience

    For any sequence of lines read from agent_reasoning.log where some lines
    are valid JSON and others are arbitrary non-JSON strings, the log consumer
    SHALL yield exactly the set of valid JSON lines (in order) and SHALL NOT
    raise an exception or halt processing.

    **Validates: Requirements 10.6**
    """
    # Build a mixed file: interleave valid JSON lines with malformed lines
    valid_json_lines = [json.dumps(e) for e in valid_events]

    # Interleave: place valid and malformed lines in a mixed order
    all_lines: list[str] = []
    valid_idx = 0
    malformed_idx = 0

    # Alternate between valid and malformed using the seeded random
    while valid_idx < len(valid_json_lines) or malformed_idx < len(malformed_lines):
        if valid_idx >= len(valid_json_lines):
            all_lines.append(malformed_lines[malformed_idx])
            malformed_idx += 1
        elif malformed_idx >= len(malformed_lines):
            all_lines.append(valid_json_lines[valid_idx])
            valid_idx += 1
        elif interleave_seed.random() < 0.5:
            all_lines.append(valid_json_lines[valid_idx])
            valid_idx += 1
        else:
            all_lines.append(malformed_lines[malformed_idx])
            malformed_idx += 1

    # Write the mixed content to a temp log file
    log_file = tmp_path / "agent_reasoning.log"
    log_file.write_text("\n".join(all_lines) + "\n", encoding="utf-8")

    # Parse and verify
    result = parse_reasoning_events(log_file)

    # The result must contain exactly the valid events in their original order
    assert len(result) == len(valid_events), (
        f"Expected {len(valid_events)} valid events, got {len(result)}"
    )
    for i, (expected, actual) in enumerate(zip(valid_events, result)):
        assert actual == expected, (
            f"Event {i} mismatch: expected {expected}, got {actual}"
        )


@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    content=st.text(
        alphabet=st.characters(blacklist_categories=("Cs",)),
        min_size=0,
        max_size=500,
    ),
)
def test_arbitrary_content_never_crashes(content, tmp_path):
    """
    Property 11 (corollary): Arbitrary content never causes exceptions.

    For any arbitrary text content written to the log file, the parser
    SHALL NOT raise an exception or halt processing. It may return an
    empty list or a list of any accidentally-valid JSON lines, but it
    must never crash.

    **Validates: Requirements 10.6**
    """
    log_file = tmp_path / "agent_reasoning.log"
    log_file.write_text(content, encoding="utf-8")

    # Must not raise any exception
    result = parse_reasoning_events(log_file)

    # Result must be a list (possibly empty)
    assert isinstance(result, list)

    # Every item in the result must be a valid parsed JSON value
    for item in result:
        # Re-serializing should not fail
        json.dumps(item)


@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    valid_events=st.lists(valid_event_strategy, min_size=1, max_size=15),
)
def test_valid_json_always_returned(valid_events, tmp_path):
    """
    Property 11 (completeness): If all lines are valid JSON, all are returned.

    When every line in the log file is valid JSON, the parser SHALL return
    all of them in their original order.

    **Validates: Requirements 10.6**
    """
    lines = [json.dumps(e) for e in valid_events]
    log_file = tmp_path / "agent_reasoning.log"
    log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = parse_reasoning_events(log_file)

    assert len(result) == len(valid_events), (
        f"Expected {len(valid_events)} events, got {len(result)}"
    )
    for i, (expected, actual) in enumerate(zip(valid_events, result)):
        assert actual == expected, (
            f"Event {i}: expected {expected}, got {actual}"
        )
