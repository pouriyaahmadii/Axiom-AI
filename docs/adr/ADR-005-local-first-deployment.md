# ADR-005: Local-First Deployment Strategy via Docker Compose

## Status
Accepted

## Context
A major challenge with evaluating modern AI platforms is complex, expensive infrastructure provisioning. Deployments requiring cloud accounts, Terraform scripts, managed Kubernetes clusters, or multi-cloud service dependencies prevent straightforward code evaluation and create substantial maintenance overhead for an engineering portfolio.
At the same time, running disparate services (PostgreSQL, Redis, Celery, FastAPI, Next.js, n8n) directly on a developer's host machine creates version conflicts and "works on my machine" failures.

## Decision
We adopt a **Local-First, Single-Host Containerized Deployment Model** using **Docker Compose**:
- All six core services (Next.js frontend, FastAPI backend, Celery worker, PostgreSQL 16, Redis 7.2, n8n Community) are defined in a unified `docker-compose.yml`.
- All published host ports bind strictly to the loopback interface (`127.0.0.1`), ensuring zero external network exposure by default.
- Persistent state is isolated to named Docker volumes (`postgres_data`, `redis_data`, `n8n_data`).
- A developer or reviewer can boot the entire platform with a single command: `docker compose up -d`.

## Alternatives Considered
1. **Cloud-First Kubernetes (EKS / GKE / Helm)**:
   - *Pros*: Production-grade horizontal pod autoscaling and rolling deployments.
   - *Cons*: Expensive to run; requires cloud credentials and cluster management; completely inappropriate for immediate local portfolio review.
2. **Serverless Deployment (AWS Lambda / Cloud Run / Supabase)**:
   - *Pros*: Zero idle cost, managed scaling.
   - *Cons*: Severe cold start latency; 15-minute execution limits disrupt long-running research agents; difficult to run hermetically offline.
3. **Bare-Metal Local Installation (Manual Services)**:
   - *Pros*: Zero container overhead.
   - *Cons*: Requires reviewers to install and configure PostgreSQL, Redis, Node, and Python on their host operating systems, leading to high failure rates.

## Consequences
- **Positive**:
  - Consistent, identical runtime environment across macOS, Linux, and Windows (via WSL2).
  - Single-command lifecycle: start, stop, rebuild, and teardown.
  - Complete network isolation via internal Docker bridge network (`agentops-net`).
- **Negative / Trade-offs**:
  - Higher local memory consumption compared to running bare-metal binaries.
  - Multi-container stack requires Docker Desktop or Colima installed on the host.

## Rejected Options
- **Multi-Cloud Distributed Mesh**: Rejected as speculative complexity violating Engineering Principle 16.
- **Exposing Services to Public Interfaces (`0.0.0.0`) by Default**: Rejected due to critical security risks.

## Conditions for Revisiting
- If the project transitions from a self-hosted evaluation utility to an enterprise multi-tenant cloud service requiring multi-node auto-scaling and managed database clusters.
