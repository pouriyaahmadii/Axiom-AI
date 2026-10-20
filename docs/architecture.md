# AgentOps: Architecture & Design Specification

## Overview

AgentOps is an enterprise-grade, self-hostable AI Agent Operations Platform. It orchestrates automated research, analysis, and execution tasks using a deterministic directed cyclic graph (LangGraph), while guaranteeing verifiable execution boundaries, auditability, bounded resources, and secure human-in-the-loop (HITL) approval gates.

## System Topology

```
                       +----------------------------------+
                       |       Next.js Web Frontend       |
                       |    (React, TypeScript, Tailwind) |
                       +-----------------+----------------+
                                         | REST / SSE
                                         v
                       +----------------------------------+
                       |        FastAPI Backend API       |
                       | (Auth, Validation, Submissions)  |
                       +--------+----------------+--------+
                                |                |
                  State / Audit |                | Job Enqueue
                                v                v
                     +----------------+    +--------------+
                     |   PostgreSQL   |    |    Redis     |
                     |  (Durable Run  |    | (Broker and  |
                     |   Store/Events)|    | Result Cache)|
                     +----------------+    +-------+------+
                                                   |
                                                   v
                                        +--------------------+
                                        |   Celery Workers   |
                                        +----------+---------+
                                                   |
                                                   v
                                     +---------------------------+
                                     |    LangGraph Coordinator  |
                                     +-------------+-------------+
                                                   |
                   +-------------------------------+-------------------------------+
                   |                               |                               |
                   v                               v                               v
         +-------------------+           +-------------------+           +-------------------+
         | Plan / Validate   |           | Guarded Tools     |           | Report Synthesis  |
         | & State Engine    |           | (SSRF Guarded)    |           | & Citation Audit  |
         +-------------------+           +-------------------+           +-------------------+
                   |                               |
                   v                               v
         +-------------------+           +-------------------+
         | Deterministic     |           | Deterministic     |
         | Mock LLM Adapter  |           | Mock Search Engine|
         +-------------------+           +-------------------+
```

## Architectural Principles

1. **Deterministic Single-Coordinator Orchestration**:
   - The coordinator manages the flow through an explicit LangGraph state machine.
   - Microservices and dynamic swarm routing are avoided in favor of explicit, bounded tasks.
2. **Deterministic Mock Mode as First-Class Citizen**:
   - The platform functions out-of-the-box without paid third-party API keys.
   - Mock LLM and Mock Search adapters provide reproducible test fixtures and verification.
3. **Defense in Depth & Zero-Trust External Data**:
   - Every input (user prompt, search results, web pages, LLM responses) is untrusted and validated against Pydantic v2 schemas.
   - SSRF defenses block access to loopback, RFC 1918 private subnets, and cloud metadata services.
4. **Durable Run State & Human-in-the-Loop (HITL)**:
   - State checkpoints, step logs, and evidence citations are stored transactionally in PostgreSQL.
   - Consequential actions pause execution until an authorized human grants approval.
5. **Bounded Execution**:
   - Strict maximum steps, per-step timeouts, retry caps, and dollar budget limits prevent runaways.
