# Product Vision: AgentOps

## 1. Executive Summary

**AgentOps** is a self-hosted, observable, and secure-by-default AI Agent Operations Platform. It accepts complex research and analysis objectives, validates incoming requests against strict operational bounds, generates a verifiable execution plan, invokes allowlisted tools, captures durable evidence, manages failures with bounded retries, enforces human-in-the-loop (HITL) approval gates for consequential actions, and synthesizes traceable final reports.

The project demonstrates production-grade AI systems engineering, deterministic state management, secure tool sandboxing, API design, and end-to-end observability without relying on speculative autonomous swarms or unconstrained code execution.

---

## 2. Problem Statement

Modern autonomous AI agents frequently suffer from structural operational defects when evaluated for real-world engineering and analytical utility:

1. **Non-Deterministic "Black Box" Execution**: LLM workflows often operate without durable state machines, making failures irreproducible and debugging impossible.
2. **Hallucination & Ungrounded Assertions**: Traditional agents blend factual evidence with generative assumptions, citing non-existent sources or presenting model speculation as fact.
3. **Unbounded Cost & Resource Runaways**: Agents without strict budgets, iteration caps, or timeout ceilings can trigger runaway loops, exhausting token budgets and external API quotas.
4. **Security Vulnerabilities & Unrestricted Tool Invocation**: Granting agents arbitrary shell execution, unrestricted HTTP scraping, or direct database query generation introduces critical security risks (SSRF, data exfiltration, system compromise).
5. **Vendor Lock-in & Fragile Demonstrations**: Most platforms depend strictly on paid external APIs (e.g., proprietary LLMs and search engines), preventing reproducible offline evaluation and automated CI/CD testing.

---

## 3. Product Vision & Mission

AgentOps addresses these challenges by separating **declarative orchestration** from **tool execution** and enforcing strict validation boundaries around every AI interaction:

- **Predictable & Verifiable**: Every research request is deconstructed into a validated, bounded execution plan before any external tools are invoked.
- **Traceable & Evidence-Grounded**: Every factual claim in the final report must trace back to an immutable, content-hashed evidence snippet. The system explicitly distinguishes between primary evidence and model inference.
- **Controllable & Safe**: Consequential external operations require explicit human approval. Tools run within strict parameter schemas with active SSRF defense and resource budgets.
- **Self-Hostable & Offline-First**: AgentOps features a fully deterministic local Mock mode that requires zero external API keys, enabling deterministic tests, CI passes, and reliable technical evaluation.

---

## 4. Primary Demonstration Case: Industry Competitor Analysis

To prove the platform's reliability and analytical rigor, AgentOps implements a structured demonstration workflow:

> **Demonstration Objective**: Conduct a rigorous competitor analysis in a designated industry and geography using public, permitted sources. The agent must compare competitor products, market positioning, available pricing structures, target customer segments, and recent public announcements.

### Key Output Requirements
- **Factual Grounding**: Every material factual assertion (e.g., pricing figures, launch dates, feature matrices) must cite an identified evidence record with URL, retrieval timestamp, and exact text snippet.
- **Evidence vs. Inference Separation**: The report must clearly separate extracted empirical data from analytical deductions and market commentary.
- **Human Approval Checkpoint**: Any consequential external interaction or export step requires human sign-off before proceeding.

---

## 5. Architectural Principles

1. **Python Owns Core Orchestration**: All planning, state transitions, validation, and domain logic reside in Python (LangGraph, FastAPI, Pydantic). The system avoids hiding operational logic inside proprietary workflow canvases.
2. **Deterministic Mock Mode as Baseline**: The platform is fully functional in a hermetic local environment using mock adapters. Paid LLM and search APIs (e.g., OpenAI, Tavily) are optional enhancements.
3. **Bounded Resources & Idempotency**: Strict limits govern plan length, step execution time, total run duration, retries, and dollar budgets.
4. **Separation of Automation Concerns**: Self-hosted n8n is utilized strictly for ingress webhooks, scheduled triggers, and downstream notification dispatching; it does not replace core state management.
5. **Zero Trust at Trust Boundaries**: All external content (web pages, search snippets, model completions) is treated as untrusted input and subjected to schema validation and sanitization.

---

## 6. Target Audience

- **Technical Evaluators & Engineering Leads**: Reviewing the codebase to assess systems engineering, AI safety practices, API architecture, and testing maturity.
- **Individual Researchers & Analysts**: Requiring structured, reproducible, and verifiable research reports without manual data aggregation.
- **Platform & AI Engineers**: Seeking an open, extensible, self-hosted operational foundation for agentic workflows with durable state persistence.

---

## 7. Business & Technical Value

- **Auditability**: Complete execution history, step outputs, and evidence records preserved in PostgreSQL.
- **Reliability**: Deterministic replay and automated failure recovery via Celery tasks and LangGraph checkpoints.
- **Cost Predictability**: Hard budget caps prevent unintended billing spikes.
- **Portfolio Demonstration**: Showcases senior-level software engineering rigor, security mindfulness, modern TypeScript/Next.js frontend development, and resilient Python distributed systems design.
