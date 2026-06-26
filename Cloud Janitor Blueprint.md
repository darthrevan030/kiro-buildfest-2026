# Kiro Autonomous Cloud Janitor — Blueprint v2

**AWS Kiro BuildFest 2026 Singapore**

---

## The One-Sentence Pitch

> An AI that *thinks before it touches* — discovering AWS waste and security gaps, reasoning about dependencies, and generating production-ready Terraform with rollback before a human ever approves a change.

This is what separates us from Cloud Custodian and every Bash script ever written: **reasoning, not rules.**

---

## What Changed From v1 (Council Improvements)

| Area             | v1                          | v2                                                      |
| ---------------- | --------------------------- | ------------------------------------------------------- |
| Demo scope       | Vague "Streamlit dashboard" | One locked scenario, bulletproof end-to-end             |
| Demo moment      | Happy path only             | Includes rollback demo — safety story made visceral    |
| Agent visibility | Static architecture diagram | Live agent progress feed in UI                          |
| Pitch hook       | Buried in comparison table  | 30-second verbal hook defined upfront                   |
| MCP honesty      | Implied live AWS            | Explicit simulated infra — architecture legible anyway |

---

## The Demo Scenario (Locked — Build Exactly This)

Do not generalize. Build one flow that is cinematically perfect.

**Scenario: "The Ghost Cluster"**

```
Discovered:  ElastiCache cluster (cache-prod-legacy) — unattached 34 days
             Security Group (sg-0a3f...) — port 6379 open to 0.0.0.0/0

FinOps finds:   $847/month waste, 34-day idle confirmed
SecOps finds:   Redis exposed to internet, no auth, encryption disabled
Remediation:    Snapshot → delete cluster → narrow SG to VPC CIDR only
Rollback:       Restore from snapshot + re-open SG if needed
```

This scenario hits **all three agents**, produces a **Terraform diff the judges can read**, and lets you demo the rollback in 60 seconds.

---

## Competitive Edge

| Feature             | Cloud Custodian / Bash | Kiro Cloud Janitor                                |
| ------------------- | ---------------------- | ------------------------------------------------- |
| Logic engine        | Hardcoded YAML rules   | Sequential-reasoning AI agents                    |
| Context awareness   | None                   | Guided by`.kiro/` steering files                |
| Safety model        | Blind execution        | Spec → plan → human approval → execute         |
| Dependency handling | Fails or ignores       | Agent discovers and resolves before acting        |
| Rollback            | Manual                 | Auto-generated HCL rollback block, pre-approved   |
| Audit trail         | Logs (if lucky)        | Every action tagged`ManagedBy = "Kiro-Janitor"` |

**The line that wins the room:** *"Cloud Custodian runs rules. This runs reasoning."*

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User / Developer                      │
│              "Execute Cloud Audit"                       │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│                  Kiro Spec Engine                        │
│         Validates .kiro/AGENTS.md + rules.md            │
│         Loads task spec before any agent fires          │
└──────┬──────────────────┬───────────────────┬───────────┘
       │                  │                   │
       ▼                  ▼                   ▼
┌────────────┐   ┌───────────────┐   ┌──────────────────┐
│   FinOps   │   │    SecOps     │   │  Remediation     │
│  Auditor   │──▶│    Guard      │──▶│  Architect       │
│            │   │               │   │                  │
│ Finds waste│   │ Finds vulns   │   │ Generates HCL    │
│ Tags idle  │   │ Flags SGs     │   │ + rollback block │
│ resources  │   │ Checks S3     │   │ Requires approval│
└────────────┘   └───────────────┘   └──────────────────┘
       │                  │                   │
       └──────────────────┴───────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              MODEL CONTEXT PROTOCOL LAYER               │
├─────────────────┬──────────────────┬────────────────────┤
│  AWS Cost MCP   │  AWS Security MCP│   Terraform MCP    │
│  Cost Explorer  │  Inspector/Config│   HCL Validation   │
│  (simulated)    │  (simulated)     │   (real output)    │
└─────────────────┴──────────────────┴────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│            Target AWS Infrastructure (Simulated)        │
│  • cache-prod-legacy  ElastiCache  — 34 days idle       │
│  • sg-0a3f...         Security Group — 0.0.0.0/0:6379   │
└─────────────────────────────────────────────────────────┘
```

**Why simulated infra is fine to say out loud:** Judges at a hackathon care about architecture, reasoning quality, and Kiro's spec-driven workflow. You will explicitly state "we're running against a simulated AWS environment" in the demo opening. The MCP integration *architecture* is real — backing data is seeded. This is standard practice and judges will respect the honesty.

---

## `.kiro/` Directory (Commit Everything — Judges Will Read It)

```
.kiro/
├── AGENTS.md
├── rules.md
└── tasks/
    ├── 001_initial_scan_spec.md
    ├── 002_remediation_spec.md        ← NEW
    └── 003_rollback_spec.md           ← NEW
```

### `.kiro/AGENTS.md`

```markdown
# Cloud Janitor Agent Steering

## Agent Roles

### FinOps Auditor
- Detects financial waste: unattached EBS, idle EC2, orphaned ElastiCache
- Confirms idle duration before flagging (minimum 7 days; flag at 30+)
- Estimates monthly cost of each waste item
- Tags findings with severity: LOW / MEDIUM / HIGH

### SecOps Guard
- Flags Security Groups with 0.0.0.0/0 ingress on sensitive ports
- Checks S3 bucket public access settings
- Audits EBS/RDS/ElastiCache encryption at rest
- Tags findings with CVE references where applicable

### Remediation Architect
- Receives structured findings from FinOps + SecOps
- Investigates resource dependencies before generating any HCL
- Produces: remediation spec → Terraform block → rollback block
- Never generates code without a prior spec
- All generated resources tagged ManagedBy = "Kiro-Janitor"

## Hard Boundaries (Never Violate)
- Never generate AWS access keys or secrets
- Never expose plaintext credentials in HCL output
- Never modify infrastructure without explicit user approval
- Always generate rollback before asking for approval
- Rollback must be tested (plan only) before approval prompt
```

### `.kiro/rules.md`

```markdown
# Infrastructure Remediation Standards

## Terraform Tag Requirements
Every generated resource block must include:
  ManagedBy   = "Kiro-Janitor"
  Environment = var.environment   # "dev" | "staging" | "prod"
  RemediatedAt = timestamp()

## EBS Volume Rules
- Unattached > 7 days: FLAG
- Unattached > 30 days: REMEDIATE
  1. aws_ebs_snapshot_copy (snapshot first)
  2. aws_volume_attachment destroy
  3. aws_ebs_volume destroy
  4. Rollback: restore from snapshot ARN

## Security Group Rules
- Never delete a Security Group — always narrow CIDR
- Replace 0.0.0.0/0 ingress with VPC CIDR block (data.aws_vpc.current.cidr_block)
- Sensitive ports requiring VPC-only: 22, 3306, 5432, 6379, 27017

## ElastiCache Rules
- Idle > 30 days: snapshot → delete
- Require encryption_at_rest = true on all new clusters
- auth_token required if reachable from public subnet

## Approval Gate
- Display full Terraform plan output before asking for approval
- Display rollback plan alongside remediation plan
- Require typed confirmation: "APPROVE <resource-id>"
```

### `.kiro/tasks/001_initial_scan_spec.md`

```markdown
# Task 001 — MCP Ingestion & Baseline Discovery

## Objective
Implement a secure integration layer using MCP to ingest AWS infrastructure metrics
and produce a structured findings report.

## Inputs
- Simulated AWS Cost Explorer data (JSON fixture)
- Simulated AWS Config/Inspector data (JSON fixture)

## Success Criteria
- [ ] Identifies at least 3 distinct waste/security categories
- [ ] Produces findings.json with: resource_id, type, severity, estimated_cost, idle_days
- [ ] Generates findings.md human-readable report
- [ ] Zero infrastructure modification during discovery phase

## Output Schema
{
  "findings": [
    {
      "resource_id": "string",
      "resource_type": "elasticache|ebs|ec2|sg|s3",
      "finding_type": "waste|security",
      "severity": "low|medium|high|critical",
      "estimated_monthly_cost": number,
      "idle_days": number | null,
      "details": "string"
    }
  ]
}
```

### `.kiro/tasks/002_remediation_spec.md` *(New)*

```markdown
# Task 002 — Remediation Planning

## Objective
For each HIGH/CRITICAL finding from Task 001, produce a complete remediation plan
before any infrastructure action.

## Steps (in order — no skipping)
1. Dependency check: query all resources referencing target resource
2. Impact assessment: document what breaks if resource is removed
3. Generate remediation Terraform HCL
4. Generate rollback Terraform HCL
5. Run terraform plan (dry-run) on both
6. Present diff to user for approval

## Approval Format
Display to user:
  REMEDIATION PLAN: <resource_id>
  Estimated savings: $X/month
  Risk: LOW | MEDIUM | HIGH
  Dependencies affected: [list]

  [Terraform diff block]
  [Rollback block]

  Type "APPROVE <resource_id>" to proceed.

## Success Criteria
- [ ] Rollback generated before remediation presented
- [ ] Dependency list accurate
- [ ] No resource modified before APPROVE received
```

### `.kiro/tasks/003_rollback_spec.md` *(New)*

```markdown
# Task 003 — Rollback Execution

## Trigger
User types "ROLLBACK <resource_id>" within 24h of remediation.

## Steps
1. Locate rollback artifact for resource_id in ./rollbacks/
2. Validate rollback HCL (terraform validate)
3. Run terraform plan -target=<resource>
4. Display plan to user
5. Require confirmation: "CONFIRM ROLLBACK <resource_id>"
6. Execute. Record to audit log.

## Success Criteria
- [ ] Resource restored to pre-remediation state
- [ ] Audit log entry written
- [ ] Rollback artifact marked consumed
```

---

## Demo Flow (6 Minutes)

### 0:00–0:30 — The Hook

Say this verbatim (or close):

> *"Every cloud team has waste they know about and vulnerabilities they don't. The existing tools either run rigid rules that miss context, or require engineers to write scripts for every scenario. We built something different: an AI that reasons about your infrastructure the way a senior DevOps engineer would — checking dependencies, generating rollback before touching anything, and requiring your approval at every step."*

### 0:30–2:00 — Scan

- Dashboard loads. Click **Execute Cloud Audit.**
- **Show the agent progress feed** — "FinOps Auditor scanning… found 2 findings" then "SecOps Guard scanning… found 1 critical."
- Findings appear: `cache-prod-legacy` ($847/mo, 34 days idle) + `sg-0a3f` (0.0.0.0/0 on 6379).
- Point at the `.kiro/AGENTS.md` panel: *"The agents are guided by steering files — business rules the team can edit without touching code."*

### 2:00–3:30 — Remediation Plan

- Click **Generate Remediation Plan** on `cache-prod-legacy`.
- **Show the dependency check running** — agent queries what references this cluster. Result: nothing live depends on it.
- Side-by-side diff appears: current state (cluster running) vs. proposed (snapshot → delete).
- Rollback block shown alongside: *"The rollback is generated before we ask for approval — not after."*
- Point at the Terraform tags: `ManagedBy = "Kiro-Janitor"`. Every action is traceable.

### 3:30–4:30 — Approval + Execution

- Type `APPROVE cache-prod-legacy` into the approval field.
- Terraform executes. Progress feed shows each step.
- Audit log entry written. Savings counter updates: **+$847/month.**

### 4:30–5:30 — Rollback Demo *(The moment that wins)*

- Say: *"Now watch what happens if we made a mistake."*
- Type `ROLLBACK cache-prod-legacy`.
- Rollback plan appears. Confirm. Cluster restored from snapshot.
- Say: *"This is what makes autonomous cloud tooling safe enough to actually use."*

### 5:30–6:00 — .kiro/ Close

- Show the `.kiro/` directory in the repo.
- Say: *"Everything the agents know — their roles, their rules, their task specs — lives here. Reviewable, versionable, auditable. This is Kiro's spec-driven build in practice."*

---

## UI: What the Dashboard Must Show

**Do not build a generic dashboard. Build exactly these panels:**

```
┌─────────────────────────────────────────────────┐
│  🔍 Cloud Audit                    [Execute Audit]│
├──────────────────────┬──────────────────────────┤
│  AGENT ACTIVITY      │  FINDINGS                │
│                      │                          │
│  ● FinOps Auditor    │  ⚠ cache-prod-legacy     │
│    Scanning Cost     │    $847/mo | 34d idle    │
│    Explorer...       │    HIGH                  │
│                      │                          │
│  ● SecOps Guard      │  🔴 sg-0a3f...           │
│    Checking SGs...   │    0.0.0.0/0:6379        │
│                      │    CRITICAL              │
│  ✓ Remediation Arch  │                          │
│    Plan ready        │  [Generate Plan ▶]       │
├──────────────────────┴──────────────────────────┤
│  REMEDIATION DIFF          ROLLBACK PLAN        │
│  [current terraform]  vs   [rollback terraform] │
│                                                  │
│  Approval: [APPROVE cache-prod-legacy    ] [OK] │
├─────────────────────────────────────────────────┤
│  AUDIT LOG                                       │
│  14:23:01  Scan complete. 2 findings.            │
│  14:24:15  Plan generated. Awaiting approval.    │
│  14:24:44  APPROVED. Executing...               │
│  14:24:58  Done. Savings: $847/mo.              │
└─────────────────────────────────────────────────┘
```

**Agent Activity feed is the most important UI element.** It makes the multi-agent architecture *visible* and saves you from having to explain the architecture diagram. Judges see it working.

---

## Generated Terraform Samples

### Remediation HCL — ElastiCache Delete

```hcl
# Generated by Kiro Cloud Janitor — Task 002
# Resource: cache-prod-legacy
# Estimated savings: $847/month
# Approved by: <user> at <timestamp>

resource "aws_elasticache_snapshot" "cache_prod_legacy_pre_delete" {
  cluster_id             = "cache-prod-legacy"
  snapshot_name          = "kiro-janitor-pre-delete-${formatdate("YYYYMMDD", timestamp())}"

  tags = {
    ManagedBy    = "Kiro-Janitor"
    Environment  = var.environment
    RemediatedAt = timestamp()
    RollbackRef  = "rollbacks/cache-prod-legacy.tf"
  }
}

resource "null_resource" "cache_prod_legacy_delete" {
  depends_on = [aws_elasticache_snapshot.cache_prod_legacy_pre_delete]

  provisioner "local-exec" {
    command = "aws elasticache delete-cache-cluster --cache-cluster-id cache-prod-legacy"
  }
}
```

### Rollback HCL — ElastiCache Restore

```hcl
# ROLLBACK PLAN — cache-prod-legacy
# Generated alongside remediation. Do not modify.
# Trigger: ROLLBACK cache-prod-legacy

resource "aws_elasticache_cluster" "cache_prod_legacy_restored" {
  cluster_id           = "cache-prod-legacy"
  engine               = "redis"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  snapshot_name        = "kiro-janitor-pre-delete-${var.snapshot_date}"
  security_group_ids   = [var.original_sg_id]

  tags = {
    ManagedBy   = "Kiro-Janitor"
    RestoredAt  = timestamp()
    RestoredBy  = "rollback"
  }
}
```

### Remediation HCL — Security Group Narrow

```hcl
# Generated by Kiro Cloud Janitor — Task 002
# Resource: sg-0a3f... (port 6379 exposure)
# Action: narrow CIDR from 0.0.0.0/0 to VPC CIDR only

data "aws_vpc" "current" {
  default = true
}

resource "aws_security_group_rule" "redis_ingress_vpc_only" {
  type              = "ingress"
  from_port         = 6379
  to_port           = 6379
  protocol          = "tcp"
  cidr_blocks       = [data.aws_vpc.current.cidr_block]
  security_group_id = "sg-0a3f..."
  description       = "Kiro-Janitor: narrowed from 0.0.0.0/0 — ${timestamp()}"
}

resource "aws_security_group_rule" "redis_ingress_public_remove" {
  type              = "ingress"
  from_port         = 6379
  to_port           = 6379
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = "sg-0a3f..."
  lifecycle {
    prevent_destroy = false
  }
}
```

---

## Tech Stack

| Layer       | Choice                                        | Reason                                |
| ----------- | --------------------------------------------- | ------------------------------------- |
| UI          | Streamlit                                     | Fast to build, judges can run locally |
| Agents      | Python + Kiro orchestration                   | Native Kiro integration               |
| MCP servers | AWS Cost MCP, AWS Security MCP, Terraform MCP | Required for Kiro Power User award    |
| Infra data  | JSON fixtures (simulated)                     | No live AWS creds needed for demo     |
| HCL output  | Generated strings + terraform validate        | Real Terraform, fake target           |
| Audit log   | Local SQLite or flat file                     | Simple, demoable, no infra dependency |

---

## Build Order (Hackathon Sequencing)

Build in this exact order. Each step is demoable on its own if time runs out.

```
Day 1 Morning   — .kiro/ directory + steering files (commit immediately)
Day 1 Afternoon — JSON fixtures for simulated AWS infra
Day 1 Evening   — FinOps agent: scan fixtures, produce findings.json

Day 2 Morning   — SecOps agent: scan fixtures, add findings
Day 2 Midday    — Remediation Architect: generate HCL from findings
Day 2 Afternoon — Approval gate + rollback generation
Day 2 Evening   — Streamlit UI: agent feed + diff panel + approval input

Day 3 Morning   — Rollback execution flow
Day 3 Midday    — Polish demo scenario end-to-end
Day 3 Afternoon — Rehearse 6-minute demo 3x. Cut anything that wobbles.
```

**If short on time, cut in this order:** rollback execution (keep rollback *display*), SecOps agent (keep FinOps only), Streamlit (use terminal output). Never cut the `.kiro/` files — judges look there first.

---

## Judging Criteria Map

| Award                  | What Judges Look For                                 | Where It's In This Build                  |
| ---------------------- | ---------------------------------------------------- | ----------------------------------------- |
| Best Spec-Driven Build | `.kiro/` directory quality, agents guided by specs | AGENTS.md, rules.md, 3 task specs         |
| Best Kiro Power User   | MCP integration depth, multi-agent orchestration     | 3 MCP servers, 3 specialist agents        |
| Most Practical         | Real-world applicability, production readiness       | Terraform tags, rollback, approval gate   |
| Best Demo              | Judges could see it in their org                     | "Ghost Cluster" scenario, rollback moment |

---

## What Not to Build

- **General-purpose rule engine** — scope creep, won't finish
- **Live AWS integration** — security risk, demo dependency, not needed
- **Beautiful UI beyond the 4 panels above** — judges care about the agents, not the CSS
- **More than 3 finding types** — depth beats breadth in a hackathon demo
- **CLI tool** — Streamlit dashboard is more demoable to a non-technical jud

# 🚀 Project Blueprint: Kiro Autonomous Cloud Janitor (FinOps & DevSecOps)

**Target Event:** AWS Kiro Buildfest 2026 Singapore

**Core Objective:** Win by maximizing Kiro's Spec-Driven AI capabilities, Model Context Protocol (MCP) servers, and agent orchestration.

---

# 💡 The Core Concept

The **Kiro Autonomous Cloud Janitor** is an enterprise-grade, multi-agent AI system that continuously audits, plans, and remediates AWS cloud waste and security vulnerabilities.

Unlike traditional, rigid automation tools that blindly run deletion scripts and break production, this system acts like an elite human DevOps engineer. Guided by Kiro steering files, it investigates resource dependencies, generates structural design plans, and writes production-ready Terraform (HCL) remediation and rollback blocks before touching live infrastructure.

---

# ⚡ Competitive Edge (Why This Wins)

When pitching to AWS Solutions Architecture judges, we'll directly compare our project against legacy automation tools such as Cloud Custodian and custom Bash scripts.

| Feature                       | Legacy Tools          | Kiro Autonomous Cloud Janitor                                               |
| ----------------------------- | --------------------- | --------------------------------------------------------------------------- |
| **Logic Engine**        | Hardcoded YAML rules  | Dynamic sequential-thinking AI agents                                       |
| **Context Awareness**   | No business awareness | Guided by`.kiro/` steering files                                          |
| **Safety**              | Blind deletions       | Spec-driven planning with rollback generation before execution              |
| **Dependency Handling** | Fails on dependencies | Automatically discovers and safely resolves dependencies before remediation |

---

# 🗺️ System Architecture

```text
                    +---------------------------------------+
                    |           User / Developer            |
                    +-------------------+-------------------+
                                        |
                               Prompt / UI Action
                                        |
                                        v
                    +-------------------+-------------------+
                    |          Kiro Spec Engine             |
                    |  Validates AGENTS.md & RULES.md       |
                    +-------------------+-------------------+
                                        |
          +-----------------------------+-----------------------------+
          |                             |                             |
          v                             v                             v
+----------------------+     +----------------------+     +----------------------+
| FinOps Scanner       |     | SecOps Auditor       |     | Remediation          |
| (Orchestrator)       |     | (Orchestrator)       |     | Architect            |
+----------------------+     +----------------------+     +----------------------+
          \                     |                     /
           \                    |                    /
            +-------------------+-------------------+
                                |
                                v
+--------------------------------------------------------------------------+
|                 MODEL CONTEXT PROTOCOL (MCP) LAYER                        |
|                                                                          |
|  AWS Security MCP  |  AWS Cost MCP  |  Terraform MCP                     |
|  Inspector/Config  | Cost Explorer  | HCL Validation                     |
+--------------------------------------------------------------------------+
                                |
                                v
                 +---------------------------------------+
                 |      Target AWS Infrastructure        |
                 |---------------------------------------|
                 | • Unattached EBS Volumes              |
                 | • Orphaned ElastiCache Clusters       |
                 | • Open Security Groups                |
                 +---------------------------------------+
```

---

# 📂 Required `.kiro/` Directory Structure

> **Critical Hackathon Rule**
>
> Commit the entire `.kiro/` directory into GitHub. Judges will inspect it for the **Best Spec-Driven Build** and **Best Kiro Power User** awards.

```
.kiro/
├── AGENTS.md
├── rules.md
└── tasks/
    └── 001_initial_scan_spec.md
```

---

# `.kiro/AGENTS.md`

```markdown
# Kiro Cloud Janitor Agent Steering Rules

## Agent Roles

### FinOps Auditor

- Detects financial waste
- Finds unattached EBS volumes
- Detects idle EC2 instances
- Detects abandoned ElastiCache clusters

### SecOps Guard

- Detects security vulnerabilities
- Flags open Security Groups (0.0.0.0/0)
- Checks storage encryption
- Reviews S3 security posture

### Remediation Architect

- Receives findings from auditors
- Produces remediation specifications
- Generates production-ready Terraform (HCL)

## Boundary Rules

- Never generate AWS credentials.
- Never expose plaintext secrets.
- Always generate a remediation specification before code.
- Require explicit user approval before modifying infrastructure.
```

---

# `.kiro/rules.md`

```markdown
# Infrastructure Remediation Standards

- Every Terraform change must include:

  ManagedBy = "Kiro-Janitor"
  Environment = "Dev" | "Prod"

- If an EBS volume has been unattached for more than 30 days:

  1. Generate a snapshot.
  2. Generate the deletion block.

- Security Group remediation must narrow CIDR ranges to internal VPC subnets instead of deleting Security Groups.
```

---

# `.kiro/tasks/001_initial_scan_spec.md`

```markdown
# Task 001 — MCP Ingestion & Baseline Discovery

## Objective

Implement a secure integration layer using the Model Context Protocol (MCP) to ingest active AWS infrastructure metrics.

## Success Metrics

- Parse simulated AWS infrastructure via MCP servers.
- Identify at least three categories of cloud waste or security issues.
- Generate a Markdown report locally.
- Never modify production infrastructure during discovery.
```

---

# 🛠️ Step-by-Step Demo Plan

## 1. User Interface

Build a lightweight **Streamlit** dashboard displaying current AWS resource health and optimization opportunities.

## 2. Execute Audit

Clicking **Execute Cloud Audit** launches the MCP orchestration pipeline.

## 3. Spec-Driven Showcase

Display a side-by-side Git diff comparing:

- Current infrastructure
- Generated Terraform remediation
- Rollback plan

## 4. Safe Deployment

Only after explicit user confirmation:

- Execute the generated Terraform.
- Record all actions.
- Preserve rollback artifacts.
- Ensure every action is traceable and reversible.
