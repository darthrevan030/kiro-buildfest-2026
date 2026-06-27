"""
Cloud Janitor Dashboard

Streamlit-based UI with 4 panels:
  - Agent Activity Feed (left-top): shows sequential agent execution status
  - Findings Panel (right-top): displays findings with severity tags
  - Diff View (left-bottom): remediation HCL vs rollback HCL side by side
  - Audit Log (right-bottom): append-only audit trail

Usage:
    streamlit run app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from orchestrator import Orchestrator

# ──────────────────────────────────────────────────────────────────────
# Page config
# ──────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Cloud Janitor Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.title("☁️ Cloud Janitor Dashboard")

# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent
FINDINGS_STORE_PATH = PROJECT_ROOT / "findings_store.json"
REMEDIATION_PATH = PROJECT_ROOT / "output" / "remediation.tf"
ROLLBACKS_DIR = PROJECT_ROOT / "rollbacks"
AUDIT_LOG_PATH = PROJECT_ROOT / "audit.log"

# ──────────────────────────────────────────────────────────────────────
# Session state initialization
# ──────────────────────────────────────────────────────────────────────

if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = Orchestrator()

if "audit_result" not in st.session_state:
    st.session_state.audit_result = None

if "agent_status" not in st.session_state:
    st.session_state.agent_status = {
        "finops": "idle",
        "secops": "idle",
        "remediation": "idle",
    }

# ──────────────────────────────────────────────────────────────────────
# Helper functions
# ──────────────────────────────────────────────────────────────────────


def load_findings() -> list[dict]:
    """Load findings from findings_store.json."""
    if not FINDINGS_STORE_PATH.exists():
        return []
    try:
        with open(FINDINGS_STORE_PATH) as f:
            data = json.load(f)
        return data.get("findings", [])
    except (json.JSONDecodeError, IOError):
        return []


def load_remediation_hcl() -> str:
    """Load the generated remediation HCL."""
    if not REMEDIATION_PATH.exists():
        return "No remediation plan generated yet."
    return REMEDIATION_PATH.read_text(encoding="utf-8")


def load_rollback_hcl(resource_id: str) -> str:
    """Load rollback HCL for a specific resource."""
    rollback_path = ROLLBACKS_DIR / f"{resource_id}.tf"
    if not rollback_path.exists():
        return f"No rollback file for {resource_id}."
    return rollback_path.read_text(encoding="utf-8")


def load_audit_log() -> list[str]:
    """Load the append-only audit log lines."""
    if not AUDIT_LOG_PATH.exists():
        return []
    try:
        lines = AUDIT_LOG_PATH.read_text(encoding="utf-8").strip().splitlines()
        return lines
    except IOError:
        return []


def severity_color(severity: str) -> str:
    """Map severity to a color for display."""
    colors = {
        "CRITICAL": "🔴",
        "HIGH": "🟠",
        "MEDIUM": "🟡",
        "LOW": "🟢",
    }
    return colors.get(severity, "⚪")


def agent_status_icon(status: str) -> str:
    """Map agent status to an icon."""
    icons = {
        "idle": "⚪",
        "running": "🔵",
        "success": "🟢",
        "failure": "🔴",
    }
    return icons.get(status, "⚪")


# ──────────────────────────────────────────────────────────────────────
# Execute Audit button
# ──────────────────────────────────────────────────────────────────────

st.divider()

if st.button("🚀 Execute Audit", type="primary", use_container_width=True):
    # Update agent statuses as pipeline runs
    st.session_state.agent_status = {
        "finops": "running",
        "secops": "running",
        "remediation": "running",
    }

    with st.spinner("Running audit pipeline: FinOps → SecOps → Remediation..."):
        result = st.session_state.orchestrator.execute_audit()
        st.session_state.audit_result = result

    if result.success:
        st.session_state.agent_status = {
            "finops": "success",
            "secops": "success",
            "remediation": "success",
        }
        st.success("Audit pipeline completed successfully.")
    else:
        st.session_state.agent_status = {
            "finops": "success",
            "secops": "success",
            "remediation": "failure",
        }
        st.error(f"Audit pipeline failed: {result.error or result.hook_error}")

st.divider()

# ──────────────────────────────────────────────────────────────────────
# 4-Panel Layout
# ──────────────────────────────────────────────────────────────────────

top_left, top_right = st.columns([1, 1])
bottom_left, bottom_right = st.columns([1, 1])

# ──────────────────────────────────────────────────────────────────────
# Panel 1: Agent Activity Feed (top-left)
# ──────────────────────────────────────────────────────────────────────

with top_left:
    st.subheader("🤖 Agent Activity Feed")

    with st.container(border=True):
        agents = [
            ("FinOps Auditor", "finops"),
            ("SecOps Guard", "secops"),
            ("Remediation Architect", "remediation"),
        ]

        for agent_name, agent_key in agents:
            status = st.session_state.agent_status[agent_key]
            icon = agent_status_icon(status)
            st.markdown(f"{icon} **{agent_name}** — _{status}_")

        # Show pipeline arrow
        st.caption("Pipeline: FinOps Auditor → SecOps Guard → Remediation Architect")

# ──────────────────────────────────────────────────────────────────────
# Panel 2: Findings Panel (top-right)
# ──────────────────────────────────────────────────────────────────────

with top_right:
    st.subheader("🔍 Findings")

    with st.container(border=True):
        findings = load_findings()

        if not findings:
            st.info("No findings yet. Click 'Execute Audit' to scan.")
        else:
            for finding in findings:
                severity = finding.get("severity", "UNKNOWN")
                icon = severity_color(severity)
                resource_id = finding.get("resource_id", "unknown")
                title = finding.get("title", "Untitled finding")
                agent = finding.get("agent", "unknown")
                cost = finding.get("cost_estimate_monthly", 0)

                col_sev, col_detail = st.columns([1, 5])
                with col_sev:
                    st.markdown(f"{icon} **{severity}**")
                with col_detail:
                    st.markdown(f"**{title}**")
                    detail_parts = [f"`{resource_id}`", f"Agent: {agent}"]
                    if cost > 0:
                        detail_parts.append(f"${cost:.2f}/mo")
                    st.caption(" · ".join(detail_parts))

            st.divider()
            st.caption(f"Total findings: {len(findings)}")

# ──────────────────────────────────────────────────────────────────────
# Panel 3: Diff View (bottom-left)
# ──────────────────────────────────────────────────────────────────────

with bottom_left:
    st.subheader("📝 Remediation & Rollback HCL")

    with st.container(border=True):
        # Remediation HCL
        remediation_hcl = load_remediation_hcl()

        # Determine available rollback resources
        rollback_files = list(ROLLBACKS_DIR.glob("*.tf"))
        resource_ids = [f.stem for f in rollback_files if f.stem != ".gitkeep"]

        if resource_ids:
            selected_resource = st.selectbox(
                "Select resource for side-by-side view:",
                options=resource_ids,
                key="diff_resource_select",
            )

            diff_left, diff_right = st.columns([1, 1])

            with diff_left:
                st.markdown("**Remediation HCL**")
                st.code(remediation_hcl, language="hcl")

            with diff_right:
                st.markdown("**Rollback HCL**")
                rollback_hcl = load_rollback_hcl(selected_resource)
                st.code(rollback_hcl, language="hcl")
        else:
            st.info("No remediation or rollback plans available yet.")
            st.code(remediation_hcl, language="hcl")

# ──────────────────────────────────────────────────────────────────────
# Panel 4: Audit Log (bottom-right)
# ──────────────────────────────────────────────────────────────────────

with bottom_right:
    st.subheader("📋 Audit Log")

    with st.container(border=True):
        # Show in-memory audit trail from orchestrator
        trail = st.session_state.orchestrator.get_audit_trail()

        if trail:
            for entry in reversed(trail):
                ts = entry.timestamp[:19]  # Trim to readable timestamp
                action = entry.action
                resource = entry.resource_id
                result = entry.result
                details = entry.details

                if result == "success":
                    result_icon = "✅"
                elif result == "failure":
                    result_icon = "❌"
                elif result == "blocked":
                    result_icon = "🚫"
                else:
                    result_icon = "ℹ️"

                st.markdown(
                    f"{result_icon} `{ts}` | **{action}** | `{resource}` — {details}"
                )
        else:
            # Fall back to file-based audit log
            log_lines = load_audit_log()
            if log_lines:
                for line in reversed(log_lines[-50:]):  # Show latest 50 entries
                    st.text(line)
            else:
                st.info("No audit entries yet. Execute an audit to generate trail.")
