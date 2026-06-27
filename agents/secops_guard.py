"""
SecOps Guard Agent

Detects security vulnerabilities: open security groups on sensitive ports and
unencrypted storage (ElastiCache, EBS). Calls the MCP server's get_security_data()
to retrieve findings from fixtures, classifies severity, and APPENDS findings
to the existing findings_store.json (which should already contain FinOps findings).

Must run AFTER FinOps Auditor — reads existing findings_store.json and appends to it.

Usage:
    python -m agents.secops_guard
"""

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Import MCP tool directly (no network transport needed for demo)
sys.path.insert(0, str(Path(__file__).parent.parent))
from mcp_server.aws_janitor_mcp import get_security_data


# Sensitive ports that must be VPC-only (never open to 0.0.0.0/0)
SENSITIVE_PORTS = {22, 3306, 5432, 6379, 27017}

# Database/cache ports — open on these = CRITICAL
DATABASE_CACHE_PORTS = {3306, 5432, 6379, 27017}

# SSH port — open = HIGH
SSH_PORTS = {22}

# Project root for output files
PROJECT_ROOT = Path(__file__).parent.parent
FINDINGS_STORE_PATH = PROJECT_ROOT / "findings_store.json"


def classify_severity(finding: dict) -> str:
    """
    Classify finding severity based on check type and specifics.

    Rules (from steering/AGENTS.md and requirements):
      - Open SG on database/cache ports (3306, 5432, 6379, 27017) = CRITICAL
      - Open SG on SSH (22) = HIGH
      - Unencrypted ElastiCache = HIGH
      - Unencrypted EBS = MEDIUM
    """
    check_type = finding.get("check_type", "")

    if check_type == "security_group":
        port = finding.get("port", 0)
        if port in DATABASE_CACHE_PORTS:
            return "CRITICAL"
        elif port in SSH_PORTS:
            return "HIGH"
        else:
            return "HIGH"

    elif check_type == "encryption":
        # Determine resource type from resource_id naming convention
        resource_id = finding.get("resource_id", "")
        if resource_id.startswith("cache-") or "cache" in resource_id.lower():
            return "HIGH"
        elif resource_id.startswith("vol-") or "ebs" in resource_id.lower():
            return "MEDIUM"
        else:
            return "HIGH"

    return "HIGH"


def determine_resource_type(finding: dict) -> str:
    """Determine the resource_type field from the raw finding data."""
    check_type = finding.get("check_type", "")

    if check_type == "security_group":
        return "security_group"
    elif check_type == "encryption":
        resource_id = finding.get("resource_id", "")
        if resource_id.startswith("cache-") or "cache" in resource_id.lower():
            return "elasticache"
        elif resource_id.startswith("vol-") or "ebs" in resource_id.lower():
            return "ebs"
    return "unknown"


def build_finding(raw_finding: dict) -> dict:
    """
    Build a Finding object from a raw security finding record.

    Schema matches design.md Finding specification.
    """
    resource_id = raw_finding["resource_id"]
    resource_type = determine_resource_type(raw_finding)
    severity = classify_severity(raw_finding)
    check_type = raw_finding.get("check_type", "")

    title = raw_finding.get("title", f"Security issue on {resource_id}")
    description = raw_finding.get("description", f"Security finding for {resource_id}")

    # Build metadata based on check type
    metadata: dict = {}
    if check_type == "security_group":
        metadata["port"] = raw_finding.get("port")
        metadata["cidr"] = raw_finding.get("cidr", "0.0.0.0/0")
        metadata["current_state"] = raw_finding.get("current_state", "open_to_world")
        metadata["required_state"] = raw_finding.get("required_state", "vpc_only")
    elif check_type == "encryption":
        metadata["encryption_at_rest"] = raw_finding.get("encryption_at_rest", False)
        metadata["current_state"] = raw_finding.get("current_state", "unencrypted")
        metadata["required_state"] = raw_finding.get("required_state", "encrypted")

    return {
        "id": str(uuid.uuid4()),
        "resource_id": resource_id,
        "resource_type": resource_type,
        "agent": "secops",
        "category": "security",
        "severity": severity,
        "title": title,
        "description": description,
        "cost_estimate_monthly": 0.0,
        "idle_days": None,
        "metadata": metadata,
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }


def check_security_groups() -> list[dict]:
    """
    Check for security groups with 0.0.0.0/0 ingress on sensitive ports.

    Returns findings for any SG open to the world on ports:
    22, 3306, 5432, 6379, 27017
    """
    data = get_security_data(check_type="security_group")

    if "error" in data:
        print(f"[SecOps Guard] ERROR: {data['error']}", file=sys.stderr)
        return []

    raw_findings = data.get("findings", [])
    findings = []

    for raw in raw_findings:
        port = raw.get("port", 0)
        cidr = raw.get("cidr", "")

        # Only flag if open to 0.0.0.0/0 on a sensitive port
        if cidr == "0.0.0.0/0" and port in SENSITIVE_PORTS:
            findings.append(build_finding(raw))

    return findings


def check_encryption() -> list[dict]:
    """
    Check for unencrypted storage (ElastiCache and EBS).

    Returns findings for any resource lacking encryption at rest.
    """
    data = get_security_data(check_type="encryption")

    if "error" in data:
        print(f"[SecOps Guard] ERROR: {data['error']}", file=sys.stderr)
        return []

    raw_findings = data.get("findings", [])
    findings = []

    for raw in raw_findings:
        encryption_at_rest = raw.get("encryption_at_rest", True)

        # Only flag if encryption is not enabled
        if not encryption_at_rest:
            findings.append(build_finding(raw))

    return findings


def run_audit() -> list[dict]:
    """
    Execute the SecOps audit:
      1. Check security groups for open sensitive ports
      2. Check encryption at rest for ElastiCache and EBS
      3. Classify severity and build Finding objects

    Returns:
        List of Finding dicts for detected security issues.
    """
    findings = []

    # Check security groups
    sg_findings = check_security_groups()
    findings.extend(sg_findings)

    # Check encryption
    enc_findings = check_encryption()
    findings.extend(enc_findings)

    return findings


def load_existing_findings_store() -> dict:
    """
    Load the existing findings_store.json (should contain FinOps findings).

    Returns a valid store dict, or a fresh empty store if the file doesn't exist.
    """
    if FINDINGS_STORE_PATH.exists():
        try:
            with open(FINDINGS_STORE_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[SecOps Guard] WARNING: Could not read existing findings_store.json: {e}", file=sys.stderr)

    # Return empty store if file doesn't exist or is unreadable
    return {
        "scan_id": str(uuid.uuid4()),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "findings": [],
        "summary": {
            "total": 0,
            "by_severity": {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0},
            "by_agent": {"finops": 0, "secops": 0},
            "total_monthly_waste": 0.0,
        },
    }


def append_findings_to_store(new_findings: list[dict]) -> dict:
    """
    Append SecOps findings to the existing findings_store.json and update summary.

    Reads the current store (expected to contain FinOps findings already),
    appends SecOps findings, recalculates summary, and writes back.

    Returns:
        The updated findings store dict.
    """
    store = load_existing_findings_store()

    # Append new findings
    existing_findings = store.get("findings", [])
    existing_findings.extend(new_findings)
    store["findings"] = existing_findings

    # Update completed_at timestamp
    store["completed_at"] = datetime.now(timezone.utc).isoformat()

    # Recalculate summary across ALL findings (FinOps + SecOps)
    all_findings = store["findings"]
    by_severity = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    by_agent: dict[str, int] = {"finops": 0, "secops": 0}
    total_monthly_waste = 0.0

    for f in all_findings:
        sev = f.get("severity", "LOW")
        if sev in by_severity:
            by_severity[sev] += 1

        agent = f.get("agent", "unknown")
        by_agent[agent] = by_agent.get(agent, 0) + 1

        total_monthly_waste += f.get("cost_estimate_monthly", 0.0)

    store["summary"] = {
        "total": len(all_findings),
        "by_severity": by_severity,
        "by_agent": by_agent,
        "total_monthly_waste": round(total_monthly_waste, 2),
    }

    # Write updated store
    FINDINGS_STORE_PATH.write_text(json.dumps(store, indent=2))
    return store


def main() -> None:
    """Run the SecOps Guard and append findings to findings_store.json."""
    print("[SecOps Guard] Starting security audit...")

    findings = run_audit()

    print(f"[SecOps Guard] Found {len(findings)} security finding(s)")
    for f in findings:
        port_info = f" (port {f['metadata'].get('port')})" if f['metadata'].get('port') else ""
        print(f"  • [{f['severity']}] {f['title']}{port_info}")

    store = append_findings_to_store(findings)
    print(f"[SecOps Guard] Updated findings_store.json (scan_id={store['scan_id']})")
    print(f"[SecOps Guard] Summary: {store['summary']}")


if __name__ == "__main__":
    main()
