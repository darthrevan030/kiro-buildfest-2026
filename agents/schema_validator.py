"""Schema validation for findings_store.json.

Validates the findings store against the expected schema, checking:
- Required top-level fields (scan_id, started_at, findings, summary)
- Each finding has all required fields with valid values
- Severity, resource_type, and agent enums are correct
- Summary counts match actual findings data

Usage:
    # As a module
    from agents.schema_validator import validate_findings_store
    result = validate_findings_store("findings_store.json")

    # Standalone
    python -m agents.schema_validator [path_to_findings_store.json]
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

VALID_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
VALID_RESOURCE_TYPES = {"elasticache", "ebs", "security_group"}
VALID_AGENTS = {"finops", "secops"}
VALID_CATEGORIES = {"waste", "security"}


@dataclass
class ValidationResult:
    """Result of schema validation."""

    valid: bool
    errors: list[str] = field(default_factory=list)

    def add_error(self, error: str) -> None:
        self.errors.append(error)
        self.valid = False


def _is_iso8601(value: str) -> bool:
    """Check if a string is a valid ISO-8601 timestamp."""
    try:
        datetime.fromisoformat(value)
        return True
    except (ValueError, TypeError):
        return False


def _validate_top_level(data: dict, result: ValidationResult) -> None:
    """Validate required top-level fields."""
    required_fields = ["scan_id", "started_at", "findings", "summary"]
    for field_name in required_fields:
        if field_name not in data:
            result.add_error(f"Missing required top-level field: '{field_name}'")

    if "scan_id" in data and not isinstance(data["scan_id"], str):
        result.add_error("'scan_id' must be a string")

    if "started_at" in data:
        if not isinstance(data["started_at"], str) or not _is_iso8601(data["started_at"]):
            result.add_error("'started_at' must be a valid ISO-8601 timestamp")

    if "completed_at" in data and data["completed_at"] is not None:
        if not isinstance(data["completed_at"], str) or not _is_iso8601(data["completed_at"]):
            result.add_error("'completed_at' must be a valid ISO-8601 timestamp or null")

    if "findings" in data and not isinstance(data["findings"], list):
        result.add_error("'findings' must be a list")

    if "summary" in data and not isinstance(data["summary"], dict):
        result.add_error("'summary' must be a dict")


def _validate_finding(finding: dict, index: int, result: ValidationResult) -> None:
    """Validate a single finding entry."""
    required_fields = [
        "id", "resource_id", "resource_type", "agent", "category",
        "severity", "title", "description", "metadata", "detected_at",
    ]

    for field_name in required_fields:
        if field_name not in finding:
            result.add_error(f"Finding[{index}]: missing required field '{field_name}'")

    # Validate enum fields
    if "severity" in finding:
        if finding["severity"] not in VALID_SEVERITIES:
            result.add_error(
                f"Finding[{index}]: 'severity' must be one of {sorted(VALID_SEVERITIES)}, "
                f"got '{finding['severity']}'"
            )

    if "resource_type" in finding:
        if finding["resource_type"] not in VALID_RESOURCE_TYPES:
            result.add_error(
                f"Finding[{index}]: 'resource_type' must be one of {sorted(VALID_RESOURCE_TYPES)}, "
                f"got '{finding['resource_type']}'"
            )

    if "agent" in finding:
        if finding["agent"] not in VALID_AGENTS:
            result.add_error(
                f"Finding[{index}]: 'agent' must be one of {sorted(VALID_AGENTS)}, "
                f"got '{finding['agent']}'"
            )

    if "category" in finding:
        if finding["category"] not in VALID_CATEGORIES:
            result.add_error(
                f"Finding[{index}]: 'category' must be one of {sorted(VALID_CATEGORIES)}, "
                f"got '{finding['category']}'"
            )

    if "detected_at" in finding:
        if not isinstance(finding["detected_at"], str) or not _is_iso8601(finding["detected_at"]):
            result.add_error(
                f"Finding[{index}]: 'detected_at' must be a valid ISO-8601 timestamp"
            )

    if "metadata" in finding and not isinstance(finding["metadata"], dict):
        result.add_error(f"Finding[{index}]: 'metadata' must be a dict")

    # cost_estimate_monthly is required for finops findings
    if finding.get("agent") == "finops" and "cost_estimate_monthly" not in finding:
        result.add_error(
            f"Finding[{index}]: 'cost_estimate_monthly' is required for finops findings"
        )

    if "cost_estimate_monthly" in finding:
        if not isinstance(finding["cost_estimate_monthly"], (int, float)):
            result.add_error(
                f"Finding[{index}]: 'cost_estimate_monthly' must be a number"
            )

    if "idle_days" in finding and finding["idle_days"] is not None:
        if not isinstance(finding["idle_days"], int):
            result.add_error(f"Finding[{index}]: 'idle_days' must be an int or null")


def _validate_summary(summary: dict, findings: list[dict], result: ValidationResult) -> None:
    """Validate summary matches actual findings data."""
    # Validate total count
    if "total" in summary:
        if summary["total"] != len(findings):
            result.add_error(
                f"summary.total ({summary['total']}) does not match "
                f"len(findings) ({len(findings)})"
            )
    else:
        result.add_error("summary: missing required field 'total'")

    # Validate by_severity counts
    if "by_severity" in summary:
        actual_by_severity = {s: 0 for s in VALID_SEVERITIES}
        for finding in findings:
            sev = finding.get("severity")
            if sev in VALID_SEVERITIES:
                actual_by_severity[sev] += 1

        for severity in VALID_SEVERITIES:
            expected = actual_by_severity[severity]
            actual = summary["by_severity"].get(severity, 0)
            if actual != expected:
                result.add_error(
                    f"summary.by_severity.{severity}: expected {expected}, got {actual}"
                )
    else:
        result.add_error("summary: missing required field 'by_severity'")

    # Validate by_agent counts
    if "by_agent" in summary:
        actual_by_agent = {a: 0 for a in VALID_AGENTS}
        for finding in findings:
            agent = finding.get("agent")
            if agent in VALID_AGENTS:
                actual_by_agent[agent] += 1

        for agent in VALID_AGENTS:
            expected = actual_by_agent[agent]
            actual = summary["by_agent"].get(agent, 0)
            if actual != expected:
                result.add_error(
                    f"summary.by_agent.{agent}: expected {expected}, got {actual}"
                )
    else:
        result.add_error("summary: missing required field 'by_agent'")

    # Validate total_monthly_waste
    if "total_monthly_waste" not in summary:
        result.add_error("summary: missing required field 'total_monthly_waste'")
    elif not isinstance(summary["total_monthly_waste"], (int, float)):
        result.add_error("summary.total_monthly_waste must be a number")


def validate_findings_store(path: str | Path) -> ValidationResult:
    """Validate a findings_store.json file against the expected schema.

    Args:
        path: Path to the findings_store.json file.

    Returns:
        ValidationResult with valid=True if schema is correct,
        or valid=False with a list of error messages.
    """
    result = ValidationResult(valid=True)
    path = Path(path)

    # Check file exists
    if not path.exists():
        result.add_error(f"File not found: {path}")
        return result

    # Parse JSON
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        result.add_error(f"Invalid JSON: {e}")
        return result

    if not isinstance(data, dict):
        result.add_error("Root element must be a JSON object")
        return result

    # Validate top-level fields
    _validate_top_level(data, result)

    # Validate findings
    findings = data.get("findings", [])
    if isinstance(findings, list):
        for i, finding in enumerate(findings):
            if not isinstance(finding, dict):
                result.add_error(f"Finding[{i}]: must be a JSON object")
            else:
                _validate_finding(finding, i, result)

    # Validate summary
    summary = data.get("summary")
    if isinstance(summary, dict) and isinstance(findings, list):
        _validate_summary(summary, findings, result)

    return result


def main() -> None:
    """CLI entry point — validate findings_store.json and print results."""
    path = sys.argv[1] if len(sys.argv) > 1 else "findings_store.json"
    result = validate_findings_store(path)

    if result.valid:
        print(f"✓ {path} is valid")
    else:
        print(f"✗ {path} has {len(result.errors)} validation error(s):")
        for error in result.errors:
            print(f"  - {error}")

    sys.exit(0 if result.valid else 1)


if __name__ == "__main__":
    main()
