"""Approval gate — parses approval/rollback commands with strict validation.

Implements the approval protocol for Cloud Janitor remediation actions.
Commands must match exact format — case-sensitive, no extra whitespace.
"""

from dataclasses import dataclass


MAX_APPROVAL_ATTEMPTS = 3


@dataclass
class ApprovalResult:
    """Result of parsing an approval command."""

    approved: bool
    resource_id: str | None
    error: str | None
    attempts_remaining: int


@dataclass
class RollbackResult:
    """Result of parsing a rollback command."""

    confirmed: bool
    resource_id: str | None
    phase: str  # "initiate" | "confirm"
    error: str | None


class CommandValidationError(Exception):
    """Raised when a command string fails validation."""

    pass


def validate_command(input_str: str) -> tuple[str, str]:
    """Parse and validate a command string into (command_type, resource_id).

    Accepted formats:
        "APPROVE <resource-id>"
        "ROLLBACK <resource-id>"
        "CONFIRM ROLLBACK <resource-id>"

    Raises CommandValidationError for any malformed input.
    """
    if not isinstance(input_str, str) or len(input_str) == 0:
        raise CommandValidationError("Input must be a non-empty string")

    # Check for leading/trailing whitespace
    if input_str != input_str.strip():
        raise CommandValidationError(
            "Input must not have leading or trailing whitespace"
        )

    # Try CONFIRM ROLLBACK first (3-part command)
    if input_str.startswith("CONFIRM ROLLBACK "):
        parts = input_str.split(" ")
        if len(parts) != 3:
            raise CommandValidationError(
                'Invalid format. Expected: "CONFIRM ROLLBACK <resource-id>"'
            )
        resource_id = parts[2]
        if not resource_id:
            raise CommandValidationError("Resource ID must not be empty")
        return ("confirm_rollback", resource_id)

    # Try APPROVE or ROLLBACK (2-part commands)
    parts = input_str.split(" ")

    if len(parts) < 2:
        raise CommandValidationError(
            'Invalid format. Expected: "APPROVE <resource-id>" or '
            '"ROLLBACK <resource-id>" or "CONFIRM ROLLBACK <resource-id>"'
        )

    if len(parts) > 2:
        raise CommandValidationError(
            'Invalid format. Expected: "APPROVE <resource-id>" or '
            '"ROLLBACK <resource-id>" or "CONFIRM ROLLBACK <resource-id>"'
        )

    command, resource_id = parts

    if command == "APPROVE":
        if not resource_id:
            raise CommandValidationError("Resource ID must not be empty")
        return ("approve", resource_id)

    if command == "ROLLBACK":
        if not resource_id:
            raise CommandValidationError("Resource ID must not be empty")
        return ("rollback", resource_id)

    raise CommandValidationError(
        f'Unknown command "{command}". '
        'Expected: "APPROVE", "ROLLBACK", or "CONFIRM ROLLBACK"'
    )


def parse_approval(
    input_str: str, expected_resource_id: str, attempts_remaining: int | None = None
) -> ApprovalResult:
    """Parse an approval command and validate against expected resource ID.

    Args:
        input_str: Raw user input string.
        expected_resource_id: The resource ID that must match.
        attempts_remaining: Current remaining attempts (defaults to MAX_APPROVAL_ATTEMPTS).

    Returns:
        ApprovalResult with approval status and remaining attempts.
    """
    if attempts_remaining is None:
        attempts_remaining = MAX_APPROVAL_ATTEMPTS

    try:
        command_type, resource_id = validate_command(input_str)
    except CommandValidationError as e:
        return ApprovalResult(
            approved=False,
            resource_id=None,
            error=str(e),
            attempts_remaining=attempts_remaining - 1,
        )

    if command_type != "approve":
        return ApprovalResult(
            approved=False,
            resource_id=None,
            error=f'Expected "APPROVE <resource-id>", got "{input_str}"',
            attempts_remaining=attempts_remaining - 1,
        )

    if resource_id != expected_resource_id:
        return ApprovalResult(
            approved=False,
            resource_id=resource_id,
            error=(
                f'Resource ID mismatch. Expected "{expected_resource_id}", '
                f'got "{resource_id}"'
            ),
            attempts_remaining=attempts_remaining - 1,
        )

    return ApprovalResult(
        approved=True,
        resource_id=resource_id,
        error=None,
        attempts_remaining=attempts_remaining,
    )


def parse_rollback(input_str: str, expected_resource_id: str) -> RollbackResult:
    """Parse a rollback command and validate against expected resource ID.

    Args:
        input_str: Raw user input string.
        expected_resource_id: The resource ID that must match.

    Returns:
        RollbackResult with confirmation status and phase.
    """
    try:
        command_type, resource_id = validate_command(input_str)
    except CommandValidationError as e:
        return RollbackResult(
            confirmed=False,
            resource_id=None,
            phase="initiate",
            error=str(e),
        )

    if command_type == "rollback":
        if resource_id != expected_resource_id:
            return RollbackResult(
                confirmed=False,
                resource_id=resource_id,
                phase="initiate",
                error=(
                    f'Resource ID mismatch. Expected "{expected_resource_id}", '
                    f'got "{resource_id}"'
                ),
            )
        return RollbackResult(
            confirmed=False,
            resource_id=resource_id,
            phase="initiate",
            error=None,
        )

    if command_type == "confirm_rollback":
        if resource_id != expected_resource_id:
            return RollbackResult(
                confirmed=False,
                resource_id=resource_id,
                phase="confirm",
                error=(
                    f'Resource ID mismatch. Expected "{expected_resource_id}", '
                    f'got "{resource_id}"'
                ),
            )
        return RollbackResult(
            confirmed=True,
            resource_id=resource_id,
            phase="confirm",
            error=None,
        )

    return RollbackResult(
        confirmed=False,
        resource_id=None,
        phase="initiate",
        error=f'Expected "ROLLBACK <resource-id>" or "CONFIRM ROLLBACK <resource-id>", got "{input_str}"',
    )
