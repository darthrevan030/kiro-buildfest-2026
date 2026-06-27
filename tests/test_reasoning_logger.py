"""Unit tests and property tests for agents.reasoning_logger.ReasoningLogger."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from agents.reasoning_logger import ReasoningLogger


class TestReasoningLoggerInit:
    """Tests for ReasoningLogger initialization."""

    def test_default_log_path(self):
        logger = ReasoningLogger()
        assert logger.log_path == Path("agent_reasoning.log")

    def test_custom_log_path(self, tmp_path: Path):
        custom = tmp_path / "custom.log"
        logger = ReasoningLogger(log_path=custom)
        assert logger.log_path == custom


class TestReasoningLoggerTruncate:
    """Tests for truncate() method."""

    def test_truncate_clears_file(self, tmp_path: Path):
        log_file = tmp_path / "reasoning.log"
        log_file.write_text("existing content\n")
        logger = ReasoningLogger(log_path=log_file)
        logger.truncate()
        assert log_file.read_text() == ""

    def test_truncate_creates_file_if_missing(self, tmp_path: Path):
        log_file = tmp_path / "new.log"
        logger = ReasoningLogger(log_path=log_file)
        logger.truncate()
        assert log_file.exists()
        assert log_file.read_text() == ""

    def test_truncate_on_permission_error_prints_stderr(self, tmp_path: Path, capsys):
        # Use an invalid path to trigger an OSError
        bad_path = tmp_path / "nonexistent_dir" / "sub" / "reasoning.log"
        logger = ReasoningLogger(log_path=bad_path)
        logger.truncate()
        captured = capsys.readouterr()
        assert "ReasoningLogger: failed to truncate" in captured.err


class TestReasoningLoggerEmit:
    """Tests for emit() method."""

    def test_emit_appends_valid_json_line(self, tmp_path: Path):
        log_file = tmp_path / "reasoning.log"
        logger = ReasoningLogger(log_path=log_file)
        logger.emit("finops_auditor", "check", "cache-01", "Checking idle duration")

        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["agent"] == "finops_auditor"
        assert entry["event_type"] == "check"
        assert entry["resource_id"] == "cache-01"
        assert entry["message"] == "Checking idle duration"
        assert "timestamp" in entry

    def test_emit_timestamp_is_utc_iso8601(self, tmp_path: Path):
        log_file = tmp_path / "reasoning.log"
        logger = ReasoningLogger(log_path=log_file)
        logger.emit("agent", "finding", "res-1", "msg")

        entry = json.loads(log_file.read_text().strip())
        ts = entry["timestamp"]
        # Should end with +00:00 (UTC)
        assert "+00:00" in ts

    def test_emit_truncates_agent_to_64_chars(self, tmp_path: Path):
        log_file = tmp_path / "reasoning.log"
        logger = ReasoningLogger(log_path=log_file)
        long_agent = "a" * 100
        logger.emit(long_agent, "check", "", "msg")

        entry = json.loads(log_file.read_text().strip())
        assert len(entry["agent"]) == 64

    def test_emit_truncates_message_to_500_chars(self, tmp_path: Path):
        log_file = tmp_path / "reasoning.log"
        logger = ReasoningLogger(log_path=log_file)
        long_msg = "x" * 1000
        logger.emit("agent", "decision", "", long_msg)

        entry = json.loads(log_file.read_text().strip())
        assert len(entry["message"]) == 500

    def test_emit_invalid_event_type_uses_unknown(self, tmp_path: Path):
        log_file = tmp_path / "reasoning.log"
        logger = ReasoningLogger(log_path=log_file)
        logger.emit("agent", "invalid_type", "res", "msg")

        entry = json.loads(log_file.read_text().strip())
        assert entry["event_type"] == "unknown"

    def test_emit_all_valid_event_types(self, tmp_path: Path):
        log_file = tmp_path / "reasoning.log"
        logger = ReasoningLogger(log_path=log_file)
        for et in ReasoningLogger.VALID_EVENT_TYPES:
            logger.emit("agent", et, "", "msg")

        lines = log_file.read_text().strip().splitlines()
        event_types = {json.loads(line)["event_type"] for line in lines}
        assert event_types == ReasoningLogger.VALID_EVENT_TYPES

    def test_emit_sequential_append(self, tmp_path: Path):
        log_file = tmp_path / "reasoning.log"
        logger = ReasoningLogger(log_path=log_file)
        logger.emit("agent1", "check", "r1", "first")
        logger.emit("agent2", "finding", "r2", "second")
        logger.emit("agent3", "handoff", "r3", "third")

        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 3
        assert json.loads(lines[0])["message"] == "first"
        assert json.loads(lines[1])["message"] == "second"
        assert json.loads(lines[2])["message"] == "third"

    def test_emit_on_filesystem_error_prints_stderr(self, tmp_path: Path, capsys):
        bad_path = tmp_path / "no_dir" / "sub" / "reasoning.log"
        logger = ReasoningLogger(log_path=bad_path)
        logger.emit("agent", "check", "", "msg")
        captured = capsys.readouterr()
        assert "ReasoningLogger: failed to write" in captured.err

    def test_emit_does_not_raise_on_filesystem_error(self, tmp_path: Path):
        bad_path = tmp_path / "no_dir" / "sub" / "reasoning.log"
        logger = ReasoningLogger(log_path=bad_path)
        # Should not raise
        logger.emit("agent", "check", "", "msg")

    def test_emit_empty_resource_id(self, tmp_path: Path):
        log_file = tmp_path / "reasoning.log"
        logger = ReasoningLogger(log_path=log_file)
        logger.emit("agent", "skip", "", "No resource")

        entry = json.loads(log_file.read_text().strip())
        assert entry["resource_id"] == ""


# --- Property-based tests ---
# Feature: savings-tracker-localstack, Property 8: Reasoning logger emits valid structured JSON

import tempfile
from hypothesis import given, settings
from hypothesis import strategies as st

from agents.reasoning_logger import ReasoningLogger


# Strategy for generating unicode text covering quotes, backslashes, and unicode chars
# Uses blacklist_categories=('Cs',) to exclude surrogate code points only
unicode_text_strategy = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
)


@settings(max_examples=100)
@given(
    agent=unicode_text_strategy,
    event_type=st.sampled_from(["check", "finding", "skip", "decision", "handoff"]),
    resource_id=unicode_text_strategy,
    message=unicode_text_strategy,
)
def test_reasoning_logger_emits_valid_structured_json(agent, event_type, resource_id, message):
    """
    Property 8: Reasoning logger emits valid structured JSON

    For any combination of agent name (string, 0-64 chars), event_type in
    {check, finding, skip, decision, handoff}, resource_id (string), and
    message (string, 0-500 chars), calling emit() SHALL append exactly one
    line to the log file that passes json.loads() and contains all required
    keys: timestamp, agent, event_type, resource_id, message.

    **Validates: Requirements 9.4, 9.9**
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        log_file = Path(tmp_dir) / "reasoning.log"
        logger = ReasoningLogger(log_path=log_file)

        # Emit one event
        logger.emit(agent, event_type, resource_id, message)

        # Read back the file
        content = log_file.read_text(encoding="utf-8")
        lines = content.splitlines()

        # Exactly one line should have been written
        assert len(lines) == 1, f"Expected 1 line, got {len(lines)}"

        # The line must be valid JSON
        entry = json.loads(lines[0])

        # All required keys must be present
        required_keys = {"timestamp", "agent", "event_type", "resource_id", "message"}
        assert required_keys.issubset(entry.keys()), (
            f"Missing keys: {required_keys - set(entry.keys())}"
        )

        # Verify field constraints
        assert len(entry["agent"]) <= 64, f"Agent too long: {len(entry['agent'])}"
        assert len(entry["message"]) <= 500, f"Message too long: {len(entry['message'])}"
        assert entry["event_type"] == event_type
        assert entry["resource_id"] == resource_id

        # Verify agent truncation is applied correctly
        assert entry["agent"] == agent[:64]
        # Verify message truncation is applied correctly
        assert entry["message"] == message[:500]

        # Verify timestamp is present and non-empty
        assert entry["timestamp"], "Timestamp should be non-empty"


# --- Property-Based Tests ---

# Strategy for generating valid emit event tuples
_event_type_strategy = st.sampled_from(sorted(ReasoningLogger.VALID_EVENT_TYPES))
_agent_strategy = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=1,
    max_size=64,
)
_resource_id_strategy = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=0,
    max_size=50,
)
_message_strategy = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=0,
    max_size=500,
)

_emit_event_strategy = st.tuples(
    _agent_strategy,
    _event_type_strategy,
    _resource_id_strategy,
    _message_strategy,
)


class TestReasoningLoggerSequentialAppendProperty:
    """Property 9: Reasoning logger sequential append.

    **Validates: Requirements 9.6**

    For any sequence of N calls to emit() within a single run (after a single
    truncate() call), the log file SHALL contain exactly N lines, and reading
    them back in order SHALL yield the same sequence of (agent, event_type,
    resource_id, message) tuples as the input sequence.
    """

    # Feature: savings-tracker-localstack, Property 9: Reasoning logger sequential append

    @given(events=st.lists(_emit_event_strategy, min_size=1, max_size=50))
    @settings(max_examples=100)
    def test_sequential_append_preserves_count_and_order(self, events):
        """N emit() calls produce exactly N lines in preserved order."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_file = Path(tmp_dir) / "reasoning.log"
            logger = ReasoningLogger(log_path=log_file)
            logger.truncate()

            # Emit all events
            for agent, event_type, resource_id, message in events:
                logger.emit(agent, event_type, resource_id, message)

            # Read back all lines
            lines = log_file.read_text(encoding="utf-8").strip().splitlines()

            # Exactly N lines
            assert len(lines) == len(events), (
                f"Expected {len(events)} lines but got {len(lines)}"
            )

            # Order is preserved — line N corresponds to the Nth emit call
            for i, (agent, event_type, resource_id, message) in enumerate(events):
                entry = json.loads(lines[i])
                # Agent is truncated to 64 chars
                assert entry["agent"] == agent[:64]
                # Event type should match (all are valid per strategy)
                assert entry["event_type"] == event_type
                # Resource ID preserved as-is
                assert entry["resource_id"] == resource_id
                # Message truncated to 500 chars
                assert entry["message"] == message[:500]
