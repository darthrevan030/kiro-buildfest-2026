"""Unit tests for Orchestrator → SavingsTracker wiring.

Validates Requirements 5.1, 5.2, 5.3:
- record_run() is called from approve() with correct arguments after successful execution
- record_run() is NOT called from _run_post_remediation_hook (avoids double-counting)
- Savings tracker errors (FileNotFoundError, OSError) don't block approval
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from agents.remediation_architect import RemediationPlan
from orchestrator import Orchestrator, ApprovalResult


@pytest.fixture
def tmp_project(tmp_path):
    """Set up a temporary project structure for testing."""
    (tmp_path / ".kiro" / "hooks").mkdir(parents=True)
    (tmp_path / "output").mkdir()
    (tmp_path / "rollbacks").mkdir()

    pre_hook = tmp_path / ".kiro" / "hooks" / "pre-remediation.sh"
    pre_hook.write_text("#!/usr/bin/env bash\nexit 0\n")

    post_hook = tmp_path / ".kiro" / "hooks" / "post-remediation.sh"
    post_hook.write_text("#!/usr/bin/env bash\nexit 0\n")

    # Write findings_store.json with both agents
    store = {
        "scan_id": "test-scan-001",
        "started_at": "2025-01-15T10:00:00Z",
        "completed_at": "2025-01-15T10:01:00Z",
        "findings": [
            {
                "id": "f1",
                "resource_id": "vol-abc123",
                "resource_type": "ebs",
                "agent": "finops",
                "category": "waste",
                "severity": "MEDIUM",
                "title": "Unattached EBS volume",
                "description": "Idle for 45 days",
                "cost_estimate_monthly": 12.50,
                "idle_days": 45,
                "metadata": {},
                "detected_at": "2025-01-15T10:00:00Z",
            },
            {
                "id": "f2",
                "resource_id": "sg-web-servers",
                "resource_type": "security_group",
                "agent": "secops",
                "category": "security",
                "severity": "CRITICAL",
                "title": "Open security group",
                "description": "0.0.0.0/0 on Redis port",
                "cost_estimate_monthly": 0.0,
                "idle_days": 0,
                "metadata": {},
                "detected_at": "2025-01-15T10:00:30Z",
            },
        ],
        "summary": {
            "total": 2,
            "by_severity": {"LOW": 0, "MEDIUM": 1, "HIGH": 0, "CRITICAL": 1},
            "by_agent": {"finops": 1, "secops": 1},
            "total_monthly_waste": 12.50,
        },
    }
    (tmp_path / "findings_store.json").write_text(json.dumps(store, indent=2))

    # Write output files for approval
    (tmp_path / "output" / "remediation.tf").write_text(
        'resource "null_resource" "test" {}'
    )
    (tmp_path / "rollbacks" / "vol-abc123.tf").write_text(
        'resource "null_resource" "rollback" {}'
    )

    return tmp_path


@pytest.fixture
def orchestrator_with_plan(tmp_project):
    """Create an orchestrator with a mocked plan ready for approval."""
    orch = Orchestrator(project_root=tmp_project, approver="test-user")

    # Mock agents to skip real scanning
    orch._finops.scan = MagicMock(return_value=[{"id": "f1", "agent": "finops"}])
    orch._secops.scan = MagicMock(return_value=[{"id": "f2", "agent": "secops"}])

    plans = [
        RemediationPlan(
            resource_id="vol-abc123",
            finding={
                "resource_id": "vol-abc123",
                "resource_type": "ebs",
                "category": "waste",
            },
            blocked=False,
            remediation_hcl='resource "null_resource" "test" {}',
            rollback_hcl='resource "null_resource" "rollback" {}',
        ),
    ]
    orch._architect.plan = MagicMock(return_value=plans)

    return orch


# ──────────────────────────────────────────────────────────────────────
# Requirement 5.1: record_run() is called from approve() with correct args
# ──────────────────────────────────────────────────────────────────────


class TestRecordRunCalledFromApprove:
    """Validates Requirement 5.1: record_run is invoked after successful approval."""

    def test_record_run_called_with_correct_resource_id(
        self, orchestrator_with_plan
    ):
        """record_run() receives the approved resource_id in resources_remediated."""
        orch = orchestrator_with_plan
        orch._savings_tracker.record_run = MagicMock(return_value=True)

        with patch("orchestrator.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            orch.execute_audit()
            result = orch.approve("APPROVE vol-abc123")

        assert result.success is True
        orch._savings_tracker.record_run.assert_called_once_with(
            resources_remediated=["vol-abc123"]
        )

    def test_record_run_called_after_post_remediation_hook(
        self, orchestrator_with_plan
    ):
        """record_run() is called AFTER _run_post_remediation_hook completes."""
        orch = orchestrator_with_plan
        call_order = []

        original_post_hook = orch._run_post_remediation_hook

        def track_post_hook(*args, **kwargs):
            call_order.append("post_hook")
            return original_post_hook(*args, **kwargs)

        def track_record_run(*args, **kwargs):
            call_order.append("record_run")
            return True

        orch._run_post_remediation_hook = track_post_hook
        orch._savings_tracker.record_run = track_record_run

        with patch("orchestrator.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            orch.execute_audit()
            orch.approve("APPROVE vol-abc123")

        assert call_order == ["post_hook", "record_run"]

    def test_record_run_not_called_on_failed_approval(
        self, orchestrator_with_plan
    ):
        """record_run() is NOT called when approval command is invalid."""
        orch = orchestrator_with_plan
        orch._savings_tracker.record_run = MagicMock(return_value=True)

        with patch("orchestrator.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            orch.execute_audit()

        # Invalid command — should not trigger savings tracking
        result = orch.approve("approve vol-abc123", resource_id="vol-abc123")
        assert result.success is False
        orch._savings_tracker.record_run.assert_not_called()

    def test_record_run_not_called_on_tflocal_apply_failure(
        self, orchestrator_with_plan
    ):
        """record_run() is NOT called when tflocal apply fails."""
        orch = orchestrator_with_plan
        orch._savings_tracker.record_run = MagicMock(return_value=True)

        call_count = [0]

        def subprocess_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # Pre-remediation hook passes
                return subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                )
            # tflocal apply fails
            return subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="apply error"
            )

        with patch("orchestrator.subprocess.run", side_effect=subprocess_side_effect):
            orch.execute_audit()
            result = orch.approve("APPROVE vol-abc123")

        assert result.success is False
        orch._savings_tracker.record_run.assert_not_called()


# ──────────────────────────────────────────────────────────────────────
# Requirement 5.3: record_run() is NOT called from _run_post_remediation_hook
# ──────────────────────────────────────────────────────────────────────


class TestRecordRunNotInPostHook:
    """Validates Requirement 5.3: record_run is not invoked from _run_post_remediation_hook."""

    def test_post_remediation_hook_does_not_call_record_run(
        self, orchestrator_with_plan
    ):
        """Calling _run_post_remediation_hook directly does NOT trigger record_run."""
        orch = orchestrator_with_plan
        orch._savings_tracker.record_run = MagicMock(return_value=True)

        with patch("orchestrator.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            # Call post-hook directly (simulating what happens inside approve)
            orch._run_post_remediation_hook("vol-abc123", "remediate", "success")

        # record_run should NOT have been called by the post-hook
        orch._savings_tracker.record_run.assert_not_called()

    def test_record_run_only_called_once_per_approval(
        self, orchestrator_with_plan
    ):
        """record_run() is called exactly once per successful approval (no double-counting)."""
        orch = orchestrator_with_plan
        orch._savings_tracker.record_run = MagicMock(return_value=True)

        with patch("orchestrator.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            orch.execute_audit()
            orch.approve("APPROVE vol-abc123")

        # Exactly one call — not doubled by post-hook
        assert orch._savings_tracker.record_run.call_count == 1


# ──────────────────────────────────────────────────────────────────────
# Requirement 5.3: Savings tracker errors don't block approval
# ──────────────────────────────────────────────────────────────────────


class TestSavingsTrackerErrorHandling:
    """Validates Requirement 5.3: savings tracker errors are graceful (non-blocking)."""

    def test_file_not_found_error_does_not_block_approval(
        self, orchestrator_with_plan
    ):
        """FileNotFoundError from record_run() is handled — approval still succeeds."""
        orch = orchestrator_with_plan
        orch._savings_tracker.record_run = MagicMock(
            side_effect=FileNotFoundError("findings_store.json not found")
        )

        with patch("orchestrator.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            orch.execute_audit()
            result = orch.approve("APPROVE vol-abc123")

        assert result.success is True
        assert result.resource_id == "vol-abc123"

    def test_os_error_does_not_block_approval(self, orchestrator_with_plan):
        """OSError from record_run() is handled — approval still succeeds."""
        orch = orchestrator_with_plan
        orch._savings_tracker.record_run = MagicMock(
            side_effect=OSError("disk full")
        )

        with patch("orchestrator.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            orch.execute_audit()
            result = orch.approve("APPROVE vol-abc123")

        assert result.success is True
        assert result.resource_id == "vol-abc123"

    def test_savings_error_is_logged_in_audit_trail(self, orchestrator_with_plan):
        """When savings tracker raises, a warning is logged in the audit trail."""
        orch = orchestrator_with_plan
        orch._savings_tracker.record_run = MagicMock(
            side_effect=OSError("permission denied")
        )

        with patch("orchestrator.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            orch.execute_audit()
            orch.approve("APPROVE vol-abc123")

        trail = orch.get_audit_trail()
        savings_entries = [
            e for e in trail if e.action == "savings" and e.result == "warning"
        ]
        assert len(savings_entries) == 1
        assert "permission denied" in savings_entries[0].details
