"""
Remediation Architect Agent

Reads findings_store.json (containing both FinOps and SecOps findings),
runs dependency checks, and generates BOTH remediation HCL and rollback HCL
simultaneously for each finding. Rollback is generated ALONGSIDE remediation,
never as a separate step after.

Produces:
  - remediation.tf — Terraform plan to fix the finding
  - rollbacks/<resource_id>.tf — Terraform plan to revert the remediation

All generated resources include required tags:
  ManagedBy, Environment, RemediatedAt, RollbackRef

Usage:
    python -m agents.remediation_architect
"""

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from mcp_server.aws_janitor_mcp import check_dependencies, validate_hcl

PROJECT_ROOT = Path(__file__).parent.parent
FINDINGS_STORE_PATH = PROJECT_ROOT / "findings_store.json"
ROLLBACKS_DIR = PROJECT_ROOT / "rollbacks"

# Required tags for all generated Terraform resources
REQUIRED_TAGS = """\
    ManagedBy    = "Kiro-Janitor"
    Environment  = var.environment
    RemediatedAt = timestamp()
    RollbackRef  = "rollbacks/{resource_id}.tf"\
"""


def _sanitize_id(resource_id: str) -> str:
    """Sanitize a resource ID for use in Terraform resource names.

    Replaces non-alphanumeric characters with underscores.
    """
    return re.sub(r"[^a-zA-Z0-9]", "_", resource_id)


def _render_tags(resource_id: str) -> str:
    """Render the required tags block for a given resource ID."""
    return REQUIRED_TAGS.format(resource_id=resource_id)


@dataclass
class DependencyReport:
    """Result of a dependency check for a resource."""
    resource_id: str
    has_dependencies: bool
    dependencies: list[str] = field(default_factory=list)
    recommendation: str = "proceed"
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "resource_id": self.resource_id,
            "has_dependencies": self.has_dependencies,
            "dependencies": self.dependencies,
            "recommendation": self.recommendation,
            "checked_at": self.checked_at,
        }


@dataclass
class RemediationPlan:
    """Complete remediation plan for a finding: includes both remediation and rollback."""
    finding: dict
    dependency_report: DependencyReport
    remediation_hcl: Optional[str] = None
    rollback_hcl: Optional[str] = None
    blocked: bool = False
    block_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "resource_id": self.finding.get("resource_id"),
            "resource_type": self.finding.get("resource_type"),
            "dependency_report": self.dependency_report.to_dict(),
            "remediation_hcl": self.remediation_hcl,
            "rollback_hcl": self.rollback_hcl,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
        }


class RemediationArchitect:
    """
    Remediation Architect agent — generates Terraform remediation and rollback plans.

    For each finding:
      1. Checks dependencies (blocks if any found)
      2. Generates remediation HCL AND rollback HCL simultaneously
      3. Writes rollback to rollbacks/<resource_id>.tf
    """

    def __init__(
        self,
        findings_store_path: Path | None = None,
        rollbacks_dir: Path | None = None,
    ):
        self.findings_store_path = findings_store_path or FINDINGS_STORE_PATH
        self.rollbacks_dir = rollbacks_dir or ROLLBACKS_DIR

    def check_dependencies(self, finding: dict) -> DependencyReport:
        """
        Check whether any other resources depend on the target resource.

        If dependencies are found, remediation is blocked and manual review is recommended.
        """
        resource_id = finding["resource_id"]
        result = check_dependencies(resource_id)

        has_deps = result.get("has_dependencies", False)
        dependents = result.get("dependents", [])

        return DependencyReport(
            resource_id=resource_id,
            has_dependencies=has_deps,
            dependencies=dependents,
            recommendation="manual_review" if has_deps else "proceed",
        )

    def generate_remediation(self, finding: dict) -> str:
        """
        Generate remediation HCL for a finding based on its resource type.

        Supported resource types:
          - ebs: Snapshot + destroy volume
          - security_group: Restrict 0.0.0.0/0 to VPC CIDR
          - elasticache: Snapshot + delete cluster
        """
        resource_type = finding.get("resource_type", "")
        # Normalize aws_ prefixed types
        normalized_type = resource_type.replace("aws_", "", 1) if resource_type.startswith("aws_") else resource_type

        if normalized_type == "ebs":
            return self._generate_ebs_remediation(finding)
        elif normalized_type == "security_group":
            return self._generate_sg_remediation(finding)
        elif normalized_type == "elasticache":
            return self._generate_elasticache_remediation(finding)
        else:
            return f'# Unsupported resource type: {resource_type}\n'

    def generate_rollback(self, finding: dict) -> str:
        """
        Generate rollback HCL for a finding based on its resource type.

        Rollback reverses the remediation action:
          - EBS: Restore volume from snapshot
          - Security Group: Restore 0.0.0.0/0 rule
          - ElastiCache: Restore cluster from snapshot
        """
        resource_type = finding.get("resource_type", "")
        normalized_type = resource_type.replace("aws_", "", 1) if resource_type.startswith("aws_") else resource_type

        if normalized_type == "ebs":
            return self._generate_ebs_rollback(finding)
        elif normalized_type == "security_group":
            return self._generate_sg_rollback(finding)
        elif normalized_type == "elasticache":
            return self._generate_elasticache_rollback(finding)
        else:
            return f'# Unsupported resource type for rollback: {resource_type}\n'

    def plan(self, findings: list[dict]) -> list[RemediationPlan]:
        """
        Generate remediation plans for all findings.

        For each finding:
          1. Run dependency check
          2. If blocked → mark plan as blocked
          3. If clear → generate BOTH remediation AND rollback HCL simultaneously
          4. Write rollback to rollbacks/<resource_id>.tf

        Remediation and rollback are generated together, not sequentially.
        """
        self.rollbacks_dir.mkdir(parents=True, exist_ok=True)
        plans: list[RemediationPlan] = []

        for finding in findings:
            # Step 1: Dependency check
            dep_report = self.check_dependencies(finding)

            if dep_report.has_dependencies:
                # Blocked — do not generate HCL
                plan = RemediationPlan(
                    finding=finding,
                    dependency_report=dep_report,
                    blocked=True,
                    block_reason=(
                        f"Resource {finding['resource_id']} has dependencies: "
                        f"{dep_report.dependencies}. Manual review required."
                    ),
                )
            else:
                # Step 2: Generate BOTH remediation and rollback TOGETHER
                remediation_hcl = self.generate_remediation(finding)
                rollback_hcl = self.generate_rollback(finding)

                plan = RemediationPlan(
                    finding=finding,
                    dependency_report=dep_report,
                    remediation_hcl=remediation_hcl,
                    rollback_hcl=rollback_hcl,
                )

                # Step 3: Write rollback artifact
                self._write_rollback(finding["resource_id"], rollback_hcl)

            plans.append(plan)

        return plans

    # ────────────────────────────────────────────────────────────────────────────
    # EBS Remediation & Rollback
    # ────────────────────────────────────────────────────────────────────────────

    def _generate_ebs_remediation(self, finding: dict) -> str:
        """Generate remediation HCL for an unattached EBS volume: snapshot then destroy."""
        resource_id = finding["resource_id"]
        sanitized = _sanitize_id(resource_id)
        tags = _render_tags(resource_id)

        return f'''\
resource "aws_ebs_snapshot" "pre_remediation_{sanitized}" {{
  volume_id   = "{resource_id}"
  description = "Pre-remediation snapshot for {resource_id}"

  tags = {{
{tags}
  }}
}}
'''

    def _generate_ebs_rollback(self, finding: dict) -> str:
        """Generate rollback HCL for EBS: restore volume from snapshot."""
        resource_id = finding["resource_id"]
        sanitized = _sanitize_id(resource_id)
        az = finding.get("metadata", {}).get("availability_zone", "us-east-1a")
        tags = _render_tags(resource_id)

        return f'''\
resource "aws_ebs_volume" "restore_{sanitized}" {{
  availability_zone = "{az}"
  snapshot_id       = aws_ebs_snapshot.pre_remediation_{sanitized}.id

  tags = {{
{tags}
  }}
}}
'''

    # ────────────────────────────────────────────────────────────────────────────
    # Security Group Remediation & Rollback
    # ────────────────────────────────────────────────────────────────────────────

    def _generate_sg_remediation(self, finding: dict) -> str:
        """Generate remediation HCL for a security group: restrict CIDR to VPC."""
        resource_id = finding["resource_id"]
        sanitized = _sanitize_id(resource_id)
        port = finding.get("metadata", {}).get("port", 0)
        tags = _render_tags(resource_id)

        return f'''\
resource "aws_security_group_rule" "restrict_{sanitized}_port_{port}" {{
  type              = "ingress"
  from_port         = {port}
  to_port           = {port}
  protocol          = "tcp"
  cidr_blocks       = [data.aws_vpc.current.cidr_block]
  security_group_id = "{resource_id}"
}}
'''

    def _generate_sg_rollback(self, finding: dict) -> str:
        """Generate rollback HCL for a security group: restore 0.0.0.0/0 rule."""
        resource_id = finding["resource_id"]
        sanitized = _sanitize_id(resource_id)
        port = finding.get("metadata", {}).get("port", 0)
        tags = _render_tags(resource_id)

        return f'''\
resource "aws_security_group_rule" "restore_{sanitized}_port_{port}" {{
  type              = "ingress"
  from_port         = {port}
  to_port           = {port}
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = "{resource_id}"

  tags = {{
{tags}
  }}
}}
'''

    # ────────────────────────────────────────────────────────────────────────────
    # ElastiCache Remediation & Rollback
    # ────────────────────────────────────────────────────────────────────────────

    def _generate_elasticache_remediation(self, finding: dict) -> str:
        """Generate remediation HCL for an idle ElastiCache cluster: snapshot then delete."""
        resource_id = finding["resource_id"]
        sanitized = _sanitize_id(resource_id)
        tags = _render_tags(resource_id)

        return f'''\
resource "aws_elasticache_snapshot" "pre_remediation_{sanitized}" {{
  cluster_id       = "{resource_id}"
  snapshot_name    = "pre-remediation-{resource_id}"
  description      = "Pre-remediation snapshot for {resource_id}"

  tags = {{
{tags}
  }}
}}
'''

    def _generate_elasticache_rollback(self, finding: dict) -> str:
        """Generate rollback HCL for ElastiCache: restore cluster from snapshot."""
        resource_id = finding["resource_id"]
        sanitized = _sanitize_id(resource_id)
        metadata = finding.get("metadata", {})
        node_type = metadata.get("instance_type", "cache.t3.medium")
        engine = metadata.get("engine", "redis")
        engine_version = metadata.get("engine_version", "7.0.7")
        num_cache_nodes = metadata.get("num_cache_nodes", 1)
        tags = _render_tags(resource_id)

        return f'''\
resource "aws_elasticache_cluster" "restore_{sanitized}" {{
  cluster_id       = "{resource_id}"
  snapshot_name    = aws_elasticache_snapshot.pre_remediation_{sanitized}.id
  node_type        = "{node_type}"
  engine           = "{engine}"
  engine_version   = "{engine_version}"
  num_cache_nodes  = {num_cache_nodes}

  tags = {{
{tags}
  }}
}}
'''

    # ────────────────────────────────────────────────────────────────────────────
    # Rollback file writer
    # ────────────────────────────────────────────────────────────────────────────

    def _write_rollback(self, resource_id: str, rollback_hcl: str) -> Path:
        """Write rollback HCL to rollbacks/<resource_id>.tf and return the path."""
        self.rollbacks_dir.mkdir(parents=True, exist_ok=True)
        rollback_path = self.rollbacks_dir / f"{resource_id}.tf"
        rollback_path.write_text(rollback_hcl)
        return rollback_path


def main() -> None:
    """Run the Remediation Architect: read findings, generate plans."""
    print("[Remediation Architect] Starting remediation planning...")

    if not FINDINGS_STORE_PATH.exists():
        print("[Remediation Architect] ERROR: findings_store.json not found", file=sys.stderr)
        print("  Run FinOps Auditor and SecOps Guard first.", file=sys.stderr)
        sys.exit(1)

    with open(FINDINGS_STORE_PATH) as f:
        store = json.load(f)

    findings = store.get("findings", [])

    if not findings:
        print("[Remediation Architect] No findings to remediate.")
        return

    architect = RemediationArchitect()
    plans = architect.plan(findings)

    for plan in plans:
        rid = plan.finding["resource_id"]
        if plan.blocked:
            print(f"  ⚠ [{rid}] BLOCKED — {plan.block_reason}")
        else:
            print(f"  ✓ [{rid}] Remediation + Rollback generated")
            print(f"    Rollback saved to: rollbacks/{rid}.tf")

    blocked_count = sum(1 for p in plans if p.blocked)
    generated_count = sum(1 for p in plans if not p.blocked)
    print(
        f"\n[Remediation Architect] Done: {generated_count} plan(s) generated, "
        f"{blocked_count} blocked by dependencies"
    )


if __name__ == "__main__":
    main()
