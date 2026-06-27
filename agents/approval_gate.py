"""Approval gate protocol for remediation actions.

Handles strict parsing and validation of approval, rollback, and
confirm-rollback commands. All commands are case-sensitive with
exact-match requirements:

- "APPROVE <resource_id>" — approve a remediation action
- "ROLLBACK <resource_id>" — request a rollback
- "CONFIRM ROLLBACK <resource_id>" — confirm a rollback

Usage:
    from agents.approval_gate import parse_approval, ApprovalGate

    result = parse_approval("APPROVE vol-abc123", "vol-abc123")
    # {"valid": True, "resource_id": "vol-abc123"}

    gate = ApprovalGate(max_attempts=3)
    result = gate.attempt_approval("APPROVE vol-abc123", "vol-abc123")
"""

from __future__ import annotations


def parse_approval(input_str: str, expected_resource_id: str) -> dict:
    """Parse an approval command string.

    Args:
        input_str: The raw input string to parse.
        expected_resource_id: The resource ID that must appear after "APPROVE ".

    Returns:
        {"valid": True, "resource_id": "..."} on exact match.
        {"valid": False, "error": "...", "expected_format": "APPROVE <resource_id>"} otherwise.
    """
    expected_format = f"APPROVE {expected_resource_id}"
    return _parse_command(input_str, "APPROVE", expected_resource_id, expected_format)


def parse_rollback(input_str: str, expected_resource_id: str) -> dict:
    """Parse a rollback command string.

    Args:
        input_str: The raw input string to parse.
        expected_resource_id: The resource ID that must appear after "ROLLBACK ".

    Returns:
        {"valid": True, "resource_id": "..."} on exact match.
        {"valid": False, "error": "...", "expected_format": "ROLLBACK <resource_id>"} otherwise.
    """
    expected_format = f"ROLLBACK {expected_resource_id}"
    return _parse_command(input_str, "ROLLBACK", expected_resource_id, expected_format)


def parse_confirm_rollback(input_str: str, expected_resource_id: str) -> dict:
    """Parse a confirm-rollback command string.

    Args:
        input_str: The raw input string to parse.
        expected_resource_id: The resource ID that must appear after "CONFIRM ROLLBACK ".

    Returns:
        {"valid": True, "resource_id": "..."} on exact match.
        {"valid": False, "error": "...", "expected_format": "CONFIRM ROLLBACK <resource_id>"}
        otherwise.
    """
    expected_format = f"CONFIRM ROLLBACK {expected_resource_id}"
    return _parse_command(
        input_str, "CONFIRM ROLLBACK", expected_resource_id, expected_format
    )


def _parse_command(
    input_str: str,
    command: str,
    expected_resource_id: str,
    expected_format: str,
) -> dict:
    """Internal parser for all command types.

    Validates:
    - No leading/trailing whitespace (strip check)
    - Command prefix is exact (case-sensitive)
    - Single space separator between command and resource_id
    - Resource ID matches exactly
    """
    # Reject if stripping changes the input (leading/trailing whitespace)
    if input_str != input_str.strip():
        return {
            "valid": False,
            "error": "Input contains leading or trailing whitespace",
            "expected_format": expected_format,
        }

    # Check prefix
    prefix = command + " "
    if not input_str.startswith(prefix):
        return {
            "valid": False,
            "error": f"Input must start with '{command} '",
            "expected_format": expected_format,
        }

    # Extract the resource_id part (everything after the prefix)
    resource_id = input_str[len(prefix):]

    # Reject empty resource_id
    if not resource_id:
        return {
            "valid": False,
            "error": "Missing resource ID",
            "expected_format": expected_format,
        }

    # Resource ID must match exactly
    if resource_id != expected_resource_id:
        return {
            "valid": False,
            "error": f"Resource ID mismatch: expected '{expected_resource_id}', got '{resource_id}'",
            "expected_format": expected_format,
        }

    return {"valid": True, "resource_id": resource_id}


class ApprovalGate:
    """Stateful approval gate that tracks failed attempts.

    After max_attempts consecutive failures, the gate locks and
    rejects all further attempts until reset.

    Args:
        max_attempts: Maximum number of failed attempts before locking. Default is 3.
    """

    def __init__(self, max_attempts: int = 3) -> None:
        self.max_attempts = max_attempts
        self._attempts: int = 0
        self._locked: bool = False

    @property
    def attempts(self) -> int:
        """Number of failed attempts so far."""
        return self._attempts

    @property
    def locked(self) -> bool:
        """Whether the gate is locked due to max attempts exceeded."""
        return self._locked

    def attempt_approval(self, input_str: str, resource_id: str) -> dict:
        """Attempt to parse an approval, tracking failures.

        Args:
            input_str: The raw input string to validate.
            resource_id: The expected resource ID.

        Returns:
            On success: {"valid": True, "resource_id": "..."}
            On failure: {"valid": False, "error": "...", "expected_format": "..."}
            When locked: {"valid": False, "error": "Max attempts exceeded", "locked": True}
        """
        if self._locked:
            return {
                "valid": False,
                "error": "Max attempts exceeded",
                "locked": True,
            }

        result = parse_approval(input_str, resource_id)

        if not result["valid"]:
            self._attempts += 1
            if self._attempts >= self.max_attempts:
                self._locked = True
                return {
                    "valid": False,
                    "error": "Max attempts exceeded",
                    "locked": True,
                }
            result["attempts_remaining"] = self.max_attempts - self._attempts

        return result

    def reset(self) -> None:
        """Reset attempt counter and unlock the gate."""
        self._attempts = 0
        self._locked = False


if __name__ == "__main__":
    # Basic self-test assertions
    print("Running approval_gate self-tests...")

    # --- parse_approval tests ---
    assert parse_approval("APPROVE vol-abc123", "vol-abc123") == {
        "valid": True, "resource_id": "vol-abc123"
    }
    assert parse_approval("approve vol-abc123", "vol-abc123")["valid"] is False
    assert parse_approval("APPROVE  vol-abc123", "vol-abc123")["valid"] is False
    assert parse_approval(" APPROVE vol-abc123", "vol-abc123")["valid"] is False
    assert parse_approval("APPROVE vol-abc123 ", "vol-abc123")["valid"] is False
    assert parse_approval("APPROVE vol-wrong", "vol-abc123")["valid"] is False
    assert parse_approval("APPROVE", "vol-abc123")["valid"] is False
    assert parse_approval("", "vol-abc123")["valid"] is False

    # --- parse_rollback tests ---
    assert parse_rollback("ROLLBACK sg-123", "sg-123") == {
        "valid": True, "resource_id": "sg-123"
    }
    assert parse_rollback("rollback sg-123", "sg-123")["valid"] is False
    assert parse_rollback("ROLLBACK sg-wrong", "sg-123")["valid"] is False

    # --- parse_confirm_rollback tests ---
    assert parse_confirm_rollback("CONFIRM ROLLBACK sg-123", "sg-123") == {
        "valid": True, "resource_id": "sg-123"
    }
    assert parse_confirm_rollback("confirm rollback sg-123", "sg-123")["valid"] is False
    assert parse_confirm_rollback("CONFIRM ROLLBACK sg-wrong", "sg-123")["valid"] is False

    # --- ApprovalGate tests ---
    gate = ApprovalGate(max_attempts=3)
    # Successful approval resets nothing
    result = gate.attempt_approval("APPROVE vol-123", "vol-123")
    assert result == {"valid": True, "resource_id": "vol-123"}
    assert gate.attempts == 0

    # Failed attempts count up
    gate2 = ApprovalGate(max_attempts=3)
    r1 = gate2.attempt_approval("bad input", "vol-123")
    assert r1["valid"] is False
    assert r1.get("attempts_remaining") == 2

    r2 = gate2.attempt_approval("bad input", "vol-123")
    assert r2["valid"] is False
    assert r2.get("attempts_remaining") == 1

    # Third failure locks the gate
    r3 = gate2.attempt_approval("bad input", "vol-123")
    assert r3 == {"valid": False, "error": "Max attempts exceeded", "locked": True}

    # Locked gate rejects even valid input
    r4 = gate2.attempt_approval("APPROVE vol-123", "vol-123")
    assert r4 == {"valid": False, "error": "Max attempts exceeded", "locked": True}

    # Reset unlocks
    gate2.reset()
    r5 = gate2.attempt_approval("APPROVE vol-123", "vol-123")
    assert r5 == {"valid": True, "resource_id": "vol-123"}

    print("✓ All approval_gate self-tests passed")
