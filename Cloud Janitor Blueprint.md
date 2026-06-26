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

| Feature                 | Legacy Tools          | Kiro Autonomous Cloud Janitor                                               |
| ----------------------- | --------------------- | --------------------------------------------------------------------------- |
| **Logic Engine**        | Hardcoded YAML rules  | Dynamic sequential-thinking AI agents                                       |
| **Context Awareness**   | No business awareness | Guided by `.kiro/` steering files                                           |
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

* Current infrastructure
* Generated Terraform remediation
* Rollback plan

## 4. Safe Deployment

Only after explicit user confirmation:

* Execute the generated Terraform.
* Record all actions.
* Preserve rollback artifacts.
* Ensure every action is traceable and reversible.
