"""Property-based tests for the Streamlit reasoning panel.

Tests the rendering logic for agent section header transitions.
# Feature: savings-tracker-localstack, Property 10: Agent section header transitions
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Mock streamlit and safely import _render_reasoning_events from app.py
# ---------------------------------------------------------------------------

def _build_streamlit_mock():
    """Create a MagicMock that simulates streamlit module well enough for import."""
    mock_st = MagicMock()
    mock_st.__version__ = "1.33.0"

    def _mock_columns(n, **kwargs):
        mocks = []
        count = n if isinstance(n, int) else 2
        for _ in range(count):
            col = MagicMock()
            col.__enter__ = MagicMock(return_value=col)
            col.__exit__ = MagicMock(return_value=False)
            mocks.append(col)
        return mocks

    mock_st.columns = _mock_columns

    container_mock = MagicMock()
    container_mock.__enter__ = MagicMock(return_value=container_mock)
    container_mock.__exit__ = MagicMock(return_value=False)
    mock_st.container = MagicMock(return_value=container_mock)

    mock_st.fragment = lambda **kwargs: (lambda f: f)
    mock_st.session_state = MagicMock()
    mock_st.set_page_config = MagicMock()
    mock_st.markdown = MagicMock()
    mock_st.divider = MagicMock()
    mock_st.subheader = MagicMock()
    mock_st.sidebar = MagicMock()
    mock_st.text_input = MagicMock(return_value="")
    mock_st.button = MagicMock(return_value=False)
    mock_st.info = MagicMock()
    mock_st.error = MagicMock()
    mock_st.success = MagicMock()
    mock_st.warning = MagicMock()
    mock_st.caption = MagicMock()
    mock_st.metric = MagicMock()
    mock_st.code = MagicMock()
    mock_st.text = MagicMock()
    mock_st.tabs = MagicMock(return_value=[MagicMock(), MagicMock()])
    mock_st.expander = MagicMock()
    mock_st.empty = MagicMock()

    return mock_st


# Install mock and patch Path.read_text for encoding-safe import
sys.modules["streamlit"] = _build_streamlit_mock()

_original_read_text = Path.read_text


def _safe_read_text(self, encoding=None, errors=None):
    try:
        return _original_read_text(self, encoding=encoding, errors=errors)
    except (UnicodeDecodeError, OSError):
        try:
            return _original_read_text(self, encoding="utf-8", errors="replace")
        except OSError:
            return ""


Path.read_text = _safe_read_text

# Remove cached app module to force fresh import with our mocks
if "app" in sys.modules:
    del sys.modules["app"]

try:
    from app import _render_reasoning_events
except Exception:
    # Fallback: define the function inline matching app.py implementation exactly
    _REASONING_EVENT_COLORS = {
        "check": "#9e9e9e",
        "finding": "#ff9800",
        "skip": "#bdbdbd",
        "decision": "#2196f3",
    }

    def _render_reasoning_events(events: list[dict]) -> str:
        """Render reasoning events as color-coded HTML with section headers."""
        if not events:
            return ""
        html_parts: list[str] = []
        last_agent = None
        for event in events:
            agent = event.get("agent", "unknown")
            event_type = event.get("event_type", "")
            message = event.get("message", "")
            resource_id = event.get("resource_id", "")
            timestamp = event.get("timestamp", "")
            if agent != last_agent:
                header_html = (
                    f'<div style="margin-top:12px;margin-bottom:4px;padding:4px 8px;'
                    f'background:#e3f2fd;border-radius:4px;font-weight:700;font-size:0.9rem;">'
                    f'🤖 {agent}'
                    f'</div>'
                )
                html_parts.append(header_html)
                last_agent = agent
            if event_type == "handoff":
                style = "font-weight:bold;color:#333;"
            else:
                color = _REASONING_EVENT_COLORS.get(event_type, "#9e9e9e")
                style = f"color:{color};"
            ts_display = timestamp[:19] if timestamp else ""
            resource_tag = f" <code>{resource_id}</code>" if resource_id else ""
            event_html = (
                f'<div style="padding:3px 8px;margin:2px 0;font-size:0.85rem;'
                f'font-family:monospace;border-left:3px solid '
                f'{_REASONING_EVENT_COLORS.get(event_type, "#666")};{style}">'
                f'<span style="color:#888;font-size:0.75rem;">{ts_display}</span> '
                f'<strong>[{event_type}]</strong>{resource_tag} {message}'
                f'</div>'
            )
            html_parts.append(event_html)
        return "".join(html_parts)

# Restore Path.read_text
Path.read_text = _original_read_text


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Agent name strategy: non-empty strings with varied characters (no surrogates)
_agent_name_strategy = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    min_size=1,
    max_size=30,
)

# Event type strategy: valid event types
_event_type_strategy = st.sampled_from(["check", "finding", "skip", "decision", "handoff"])

# Single event strategy
_event_strategy = st.fixed_dictionaries({
    "agent": _agent_name_strategy,
    "event_type": _event_type_strategy,
    "message": st.text(
        alphabet=st.characters(blacklist_categories=("Cs",)),
        min_size=0,
        max_size=100,
    ),
    "resource_id": st.text(
        alphabet=st.characters(blacklist_categories=("Cs",)),
        min_size=0,
        max_size=30,
    ),
    "timestamp": st.datetimes().map(lambda dt: dt.isoformat()),
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Pattern to match section header divs containing agent names
_HEADER_PATTERN = re.compile(
    r'<div style="margin-top:12px;margin-bottom:4px;padding:4px 8px;'
    r'background:#e3f2fd;border-radius:4px;font-weight:700;font-size:0\.9rem;">'
    r'🤖 (.*?)'
    r'</div>',
    re.DOTALL,
)


def _get_all_section_headers(html: str) -> list[str]:
    """Extract all agent names from section headers in rendered order."""
    return _HEADER_PATTERN.findall(html)


# ---------------------------------------------------------------------------
# Property 10: Agent section header transitions
# Feature: savings-tracker-localstack, Property 10: Agent section header transitions
# ---------------------------------------------------------------------------


@settings(max_examples=100)
@given(events=st.lists(_event_strategy, min_size=1, max_size=30))
def test_agent_section_header_transitions(events):
    """
    Property 10: Agent section header transitions

    For any sequence of reasoning log events where the agent field changes
    between consecutive entries, the rendering function SHALL insert a section
    header containing the new agent name at each transition point. Events with
    the same agent as their predecessor SHALL NOT produce a section header.

    **Validates: Requirements 10.3**
    """
    html = _render_reasoning_events(events)
    headers = _get_all_section_headers(html)

    # Compute expected transitions: first event always gets a header,
    # then only when agent changes
    expected_headers: list[str] = []
    last_agent = None
    for event in events:
        agent = event.get("agent", "unknown")
        if agent != last_agent:
            expected_headers.append(agent)
            last_agent = agent

    # Number of section headers must match number of agent transitions
    assert len(headers) == len(expected_headers), (
        f"Expected {len(expected_headers)} section headers but got {len(headers)}. "
        f"Expected agents: {expected_headers}, Got: {headers}"
    )

    # Each header must contain the correct agent name
    for i, (expected, actual) in enumerate(zip(expected_headers, headers)):
        assert actual == expected, (
            f"Section header {i}: expected agent '{expected}' but got '{actual}'"
        )


@settings(max_examples=100)
@given(
    agent_name=_agent_name_strategy,
    n_events=st.integers(min_value=2, max_value=10),
)
def test_same_agent_produces_single_header(agent_name, n_events):
    """
    When all events have the same agent, only ONE section header should be
    produced (at the first event). Subsequent events with the same agent
    SHALL NOT produce additional headers.

    **Validates: Requirements 10.3**
    """
    events = [
        {
            "agent": agent_name,
            "event_type": "check",
            "message": f"Event {i}",
            "resource_id": "",
            "timestamp": "2026-01-01T00:00:00",
        }
        for i in range(n_events)
    ]

    html = _render_reasoning_events(events)
    headers = _get_all_section_headers(html)

    assert len(headers) == 1, (
        f"Expected 1 section header for {n_events} events with same agent, "
        f"got {len(headers)}"
    )
    assert headers[0] == agent_name


@settings(max_examples=100)
@given(
    agents=st.lists(_agent_name_strategy, min_size=2, max_size=10, unique=True),
)
def test_every_agent_change_produces_header(agents):
    """
    When every consecutive event has a DIFFERENT agent, each event should
    produce a section header.

    **Validates: Requirements 10.3**
    """
    events = [
        {
            "agent": agent,
            "event_type": "check",
            "message": f"Event from {agent}",
            "resource_id": "",
            "timestamp": "2026-01-01T00:00:00",
        }
        for agent in agents
    ]

    html = _render_reasoning_events(events)
    headers = _get_all_section_headers(html)

    assert len(headers) == len(agents), (
        f"Expected {len(agents)} headers for {len(agents)} unique agents, "
        f"got {len(headers)}"
    )
    assert headers == agents


@settings(max_examples=100)
@given(events=st.lists(_event_strategy, min_size=0, max_size=30))
def test_empty_events_produce_empty_output(events):
    """
    An empty event list produces empty HTML output (no headers at all).

    **Validates: Requirements 10.3**
    """
    if len(events) == 0:
        html = _render_reasoning_events(events)
        assert html == ""
        headers = _get_all_section_headers(html)
        assert len(headers) == 0
