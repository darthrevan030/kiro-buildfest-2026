"""
FinOps Auditor Agent

Detects financial waste: idle ElastiCache clusters and unattached EBS volumes.
Calls the MCP server's get_cost_data() to retrieve resource data from fixtures,
filters for resources idle > 30 days, classifies severity, estimates monthly cost,
and writes findings to findings_store.json.

Usage:
    python -m agents.finops_auditor
"""

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Import MCP tool directly (no network transport needed for demo)
sys.path.insert(0, str(Path(__file__).parent.parent))
from mcp_server.aws_janitor_mcp import get_cost_data


# Minimum idle days threshold for remediation flagging
MIN_IDLE_DAYS_FOR_REMEDIATION = 30

# Project root for output files
PROJECT_ROOT = Path(__file__).parent.parent
FINDINGS_STORE_PATH = PROJECT_ROOT / "findings_store.json"


def classify_severity(resource: dict) -> str:
    """
    Classify finding severity based on resource type and idle duration.

    Rules (from steering/AGENTS.md and requirements):
      - ElastiCache idle > 30d = HIGH
      - Unattached EBS > 30d = MEDIUM
    """
    resource_type = resource.get("type", "")
    idle_days = resource.get("idle_days", 0)

    if resource_type == "elasticache" and idle_days > 30:
        return "HIGH"
    elif resource_type == "ebs" and idle_days > 30:
        return "MEDIUM"
    else:
        return "LOW"


def build_finding(resource: dict) -> dict:
    """
    Build a Finding object from a raw resource record.

    Schema matches design.md Finding specification.
    """
    resource_type = resource["type"]
    resource_id = resource["id"]
    severity = classify_severity(resource)
    idle_days = resource["idle_days"]
    monthly_cost = resource["monthly_cost"]

    # Build a human-readable title based on resource type
    if resource_type == "elasticache":
        title = f"Idle ElastiCache cluster ({resource_id}) — {idle_days} days unused"
    elif resource_type == "ebs":
        title = f"Unattached EBS volume ({resource_id}) — {idle_days} days detached"
    else:
        title = f"Idle {resource_type} resource ({resource_id}) — {idle_days} days"

    # Build detailed description
    description = resource.get("description", f"Resource {resource_id} idle for {idle_days} days")

    # Metadata carries extra resource details for downstream agents
    metadata = {
        k: v
        for k, v in resource.items()
        if k not in ("id", "type", "idle_days", "monthly_cost", "description")
    }

    return {
        "id": str(uuid.uuid4()),
        "resource_id": resource_id,
        "resource_type": resource_type,
        "agent": "finops",
        "category": "waste",
        "severity": severity,
        "title": title,
        "description": description,
        "cost_estimate_monthly": monthly_cost,
        "idle_days": idle_days,
        "metadata": metadata,
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }


def run_audit(min_idle_days: int = MIN_IDLE_DAYS_FOR_REMEDIATION) -> list[dict]:
    """
    Execute the FinOps audit:
      1. Call MCP get_cost_data() to retrieve all resources idle >= 7 days
      2. Filter to resources idle > 30 days for remediation flagging
      3. Classify severity per resource type
      4. Build Finding objects

    Returns:
        List of Finding dicts for resources exceeding the idle threshold.
    """
    # Call MCP tool — retrieves from fixture, no live AWS needed
    cost_data = get_cost_data(resource_type=None, min_idle_days=7)

    if "error" in cost_data:
        print(f"[FinOps Auditor] ERROR: {cost_data['error']}", file=sys.stderr)
        return []

    resources = cost_data.get("resources", [])

    # Filter: only flag resources idle > 30 days for remediation
    flaggable = [r for r in resources if r.get("idle_days", 0) > min_idle_days]

    findings = [build_finding(r) for r in flaggable]
    return findings


def write_findings_store(findings: list[dict]) -> dict:
    """
    Write (or initialize) findings_store.json with FinOps findings.

    The store follows the top-level schema from design.md:
      scan_id, started_at, completed_at, findings[], summary{}

    Returns:
        The complete findings store dict that was written.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Calculate summary
    by_severity: dict[str, int] = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    for f in findings:
        sev = f.get("severity", "LOW")
        if sev in by_severity:
            by_severity[sev] += 1

    total_monthly_waste = round(sum(f.get("cost_estimate_monthly", 0) for f in findings), 2)

    store = {
        "scan_id": str(uuid.uuid4()),
        "started_at": now,
        "completed_at": now,
        "findings": findings,
        "summary": {
            "total": len(findings),
            "by_severity": by_severity,
            "by_agent": {"finops": len(findings), "secops": 0},
            "total_monthly_waste": total_monthly_waste,
        },
    }

    FINDINGS_STORE_PATH.write_text(json.dumps(store, indent=2))
    return store


def main() -> None:
    """Run the FinOps Auditor and write findings_store.json."""
    print("[FinOps Auditor] Starting audit...")

    findings = run_audit()

    print(f"[FinOps Auditor] Found {len(findings)} finding(s) exceeding {MIN_IDLE_DAYS_FOR_REMEDIATION}-day threshold")
    for f in findings:
        print(f"  • [{f['severity']}] {f['title']} — ${f['cost_estimate_monthly']}/mo")

    store = write_findings_store(findings)
    print(f"[FinOps Auditor] Wrote findings_store.json (scan_id={store['scan_id']})")
    print(f"[FinOps Auditor] Summary: {store['summary']}")


if __name__ == "__main__":
    main()
