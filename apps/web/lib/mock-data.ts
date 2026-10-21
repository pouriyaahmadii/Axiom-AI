/**
 * Realistic Seed Demo Data for AgentOps.
 *
 * STRICT CONSTRAINT: This data is explicitly flagged with `isDemoSeed: true`
 * and represents an authentic competitor research scenario (AI Agent Observability).
 * It enables offline demonstration and UI validation without fabricating synthetic claims.
 */

export interface DemoRun {
  isDemoSeed: true;
  id: string;
  objective: string;
  domain: string;
  geography: string;
  status:
    | "QUEUED"
    | "PLANNING"
    | "RUNNING"
    | "AWAITING_APPROVAL"
    | "COMPLETED"
    | "COMPLETED_WITH_WARNINGS"
    | "FAILED"
    | "CANCELLED"
    | "ABORTED_BY_OPERATOR";
  created_at: string;
  completed_at: string | null;
  budget_usd_limit: number;
  estimated_cost_usd: number;
  steps_total: number;
  steps_completed: number;
  current_step_title?: string;
  error_message?: string;
}

export interface DemoStep {
  isDemoSeed: true;
  id: string;
  step_index: number;
  step_identifier: string;
  title: string;
  tool_name: string;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "SKIPPED";
  requires_human_approval: boolean;
  started_at: string | null;
  completed_at: string | null;
  parameters: Record<string, unknown>;
  output_summary?: string;
}

export interface DemoEvidence {
  isDemoSeed: true;
  id: string;
  source_id: string;
  url: string;
  title: string;
  domain: string;
  passage: string;
  related_entity: string;
  related_claim: string;
  retrieved_at: string;
  validation_status: "VERIFIED" | "CONTRADICTED" | "PENDING_VALIDATION";
  content_hash: string;
}

export interface DemoApproval {
  isDemoSeed: true;
  id: string;
  run_id: string;
  action: "PLAN_REVIEW" | "STEP_EXECUTION" | "REPORT_REVIEW";
  status: "PENDING" | "APPROVED" | "REJECTED" | "EXPIRED";
  proposed_action: Record<string, unknown>;
  payload_hash: string;
  expires_at: string;
  created_at: string;
  operator_notes?: string;
  resolved_by?: string;
}

export interface DemoReport {
  isDemoSeed: true;
  id: string;
  run_id: string;
  title: string;
  executive_summary: string;
  markdown_content: string;
  citations: Array<{
    citation_id: string;
    source_id: string;
    url: string;
    claim: string;
  }>;
  created_at: string;
}

export interface DemoAuditEvent {
  isDemoSeed: true;
  id: string;
  run_id: string;
  correlation_id: string;
  event_type: string;
  actor: string;
  timestamp: string;
  payload: Record<string, unknown>;
}

export const DEMO_RUNS: DemoRun[] = [
  {
    isDemoSeed: true,
    id: "9f8a2b10-c3d4-4e5f-a6b7-c8d9e0f1a2b3",
    objective:
      "Competitive landscape analysis of AI agent observability and evaluation frameworks in Q4 2026",
    domain: "ai-observability",
    geography: "Global",
    status: "AWAITING_APPROVAL",
    created_at: "2026-10-21T18:30:00Z",
    completed_at: null,
    budget_usd_limit: 2.0,
    estimated_cost_usd: 0.42,
    steps_total: 6,
    steps_completed: 2,
    current_step_title:
      "Review synthesized competitive research plan (Checkpoint)",
  },
  {
    isDemoSeed: true,
    id: "3e4f5a6b-7c8d-9e0f-1a2b-3c4d5e6f7a8b",
    objective:
      "Benchmark Langfuse, LangSmith, and Arize Phoenix feature matrix, self-hosting models, and pricing",
    domain: "ai-observability",
    geography: "North America",
    status: "COMPLETED",
    created_at: "2026-10-21T17:15:00Z",
    completed_at: "2026-10-21T17:22:15Z",
    budget_usd_limit: 1.5,
    estimated_cost_usd: 0.88,
    steps_total: 5,
    steps_completed: 5,
  },
  {
    isDemoSeed: true,
    id: "7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d",
    objective:
      "Deep-dive security review of public metadata endpoints and agent runtime sandboxing policies",
    domain: "security-auditing",
    geography: "Global",
    status: "RUNNING",
    created_at: "2026-10-21T19:00:00Z",
    completed_at: null,
    budget_usd_limit: 1.0,
    estimated_cost_usd: 0.28,
    steps_total: 4,
    steps_completed: 1,
    current_step_title:
      "Fetch and verify public documentation for SSRF guardrails",
  },
  {
    isDemoSeed: true,
    id: "1c2d3e4f-5a6b-7c8d-9e0f-1a2b3c4d5e6f",
    objective:
      "Scan open-source vector store integrations with LangGraph multi-agent runtimes",
    domain: "data-infrastructure",
    geography: "Global",
    status: "FAILED",
    created_at: "2026-10-21T16:00:00Z",
    completed_at: "2026-10-21T16:04:12Z",
    budget_usd_limit: 0.5,
    estimated_cost_usd: 0.5,
    steps_total: 4,
    steps_completed: 1,
    error_message:
      "BudgetExceededError: Estimated execution cost exceeded $0.50 ceiling limit",
  },
];

export const DEMO_STEPS: DemoStep[] = [
  {
    isDemoSeed: true,
    id: "step-1-discover",
    step_index: 0,
    step_identifier: "discover_vendors",
    title: "Discover leading AI observability platforms",
    tool_name: "discover_competitors",
    status: "COMPLETED",
    requires_human_approval: false,
    started_at: "2026-10-21T18:30:10Z",
    completed_at: "2026-10-21T18:30:45Z",
    parameters: { domain: "ai-observability", max_results: 5 },
    output_summary:
      "Discovered 3 target platforms: Langfuse, LangSmith, Arize Phoenix",
  },
  {
    isDemoSeed: true,
    id: "step-2-fetch-docs",
    step_index: 1,
    step_identifier: "fetch_specifications",
    title: "Extract deployment models and hosting capabilities",
    tool_name: "fetch_approved_public_page",
    status: "COMPLETED",
    requires_human_approval: false,
    started_at: "2026-10-21T18:31:00Z",
    completed_at: "2026-10-21T18:31:40Z",
    parameters: { target_urls: ["https://example.com/docs/self-hosting"] },
    output_summary:
      "Captured 4 primary source excerpts with SHA-256 hashes verified",
  },
  {
    isDemoSeed: true,
    id: "step-3-approval-gate",
    step_index: 2,
    step_identifier: "plan_approval_gate",
    title: "Review synthesized competitive research plan (Checkpoint)",
    tool_name: "human_approval_gate",
    status: "RUNNING",
    requires_human_approval: true,
    started_at: "2026-10-21T18:32:00Z",
    completed_at: null,
    parameters: {
      action: "PLAN_REVIEW",
      payload_hash:
        "7d9e4a2b1c8f3e5d0a6b4c2e1f9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a",
      timeout_seconds: 86400,
    },
    output_summary:
      "Suspended waiting for operator verdict. Checkpoint persisted in PostgreSQL.",
  },
  {
    isDemoSeed: true,
    id: "step-4-compare",
    step_index: 3,
    step_identifier: "compare_pricing_models",
    title: "Synthesize quantitative pricing and token consumption matrices",
    tool_name: "compare_entities",
    status: "PENDING",
    requires_human_approval: false,
    started_at: null,
    completed_at: null,
    parameters: {
      entities: ["Langfuse", "LangSmith", "Arize Phoenix"],
      dimension: "pricing",
    },
  },
  {
    isDemoSeed: true,
    id: "step-5-report",
    step_index: 4,
    step_identifier: "draft_report",
    title: "Generate grounded comparative research report with citations",
    tool_name: "generate_report_draft",
    status: "PENDING",
    requires_human_approval: false,
    started_at: null,
    completed_at: null,
    parameters: { format: "markdown", require_grounding: true },
  },
];

export const DEMO_EVIDENCE: DemoEvidence[] = [
  {
    isDemoSeed: true,
    id: "ev-01",
    source_id: "src-01",
    url: "https://langfuse.com/docs/deployment/self-host",
    title: "Langfuse Self-Hosting Documentation",
    domain: "langfuse.com",
    passage:
      "Langfuse is fully open-source under MIT and can be deployed on Docker Compose or Kubernetes using PostgreSQL and ClickHouse.",
    related_entity: "Langfuse",
    related_claim:
      "Langfuse provides MIT-licensed self-hostable Docker Compose and Kubernetes deployments.",
    retrieved_at: "2026-10-21T17:16:30Z",
    validation_status: "VERIFIED",
    content_hash:
      "a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef",
  },
  {
    isDemoSeed: true,
    id: "ev-02",
    source_id: "src-02",
    url: "https://docs.smith.langchain.com/pricing",
    title: "LangSmith Pricing and Tiers",
    domain: "smith.langchain.com",
    passage:
      "LangSmith Developer tier includes 5,000 free trace units per month; Enterprise tier offers dedicated VPC and on-premise installation.",
    related_entity: "LangSmith",
    related_claim:
      "LangSmith offers SaaS tiers with 5,000 free trace units and an enterprise self-hosted option.",
    retrieved_at: "2026-10-21T17:17:10Z",
    validation_status: "VERIFIED",
    content_hash:
      "b2c3d4e5f6a178901234567890abcdef1234567890abcdef1234567890abcdef",
  },
  {
    isDemoSeed: true,
    id: "ev-03",
    source_id: "src-03",
    url: "https://docs.arize.com/phoenix/deployment",
    title: "Arize Phoenix Open Source Deployment",
    domain: "arize.com",
    passage:
      "Arize Phoenix is lightweight and can run locally as a standalone Python process or container with SQLite or PostgreSQL backends.",
    related_entity: "Arize Phoenix",
    related_claim:
      "Arize Phoenix supports local in-process Python execution alongside containerized deployment.",
    retrieved_at: "2026-10-21T17:18:05Z",
    validation_status: "VERIFIED",
    content_hash:
      "c3d4e5f6a1b278901234567890abcdef1234567890abcdef1234567890abcdef",
  },
];

export const DEMO_APPROVALS: DemoApproval[] = [
  {
    isDemoSeed: true,
    id: "appr-8888-9999-aaaa-bbbb",
    run_id: "9f8a2b10-c3d4-4e5f-a6b7-c8d9e0f1a2b3",
    action: "PLAN_REVIEW",
    status: "PENDING",
    proposed_action: {
      plan_steps: 6,
      target_entities: ["Langfuse", "LangSmith", "Arize Phoenix"],
      estimated_tokens: 12500,
      estimated_cost_usd: 0.42,
    },
    payload_hash:
      "7d9e4a2b1c8f3e5d0a6b4c2e1f9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a",
    expires_at: "2026-10-22T18:32:00Z",
    created_at: "2026-10-21T18:32:00Z",
  },
];

export const DEMO_REPORT: DemoReport = {
  isDemoSeed: true,
  id: "rep-001",
  run_id: "3e4f5a6b-7c8d-9e0f-1a2b-3c4d5e6f7a8b",
  title:
    "Competitive Analysis: Open-Source vs Managed AI Observability Platforms",
  executive_summary:
    "The AI agent observability market demonstrates bifurcated adoption: developer-led teams prioritize open-source self-hostable tools (Langfuse, Arize Phoenix) for data privacy, while enterprise teams choose managed SaaS suites (LangSmith) for turnkey evaluations.",
  markdown_content: `# Executive Summary

The AI agent observability market demonstrates bifurcated adoption: developer-led teams prioritize open-source self-hostable tools (Langfuse, Arize Phoenix) for data privacy, while enterprise teams choose managed SaaS suites (LangSmith) for turnkey evaluations.

## 1. Architectural & Deployment Comparison

- **Langfuse**: Fully open-source (MIT) web application backed by PostgreSQL and ClickHouse [1]. It provides SDK instrumentation for Python, TypeScript, and LangChain/LlamaIndex frameworks.
- **LangSmith**: Proprietary SaaS evaluation and prompt engineering suite from LangChain [2]. On-premise deployment is reserved for Enterprise tier agreements.
- **Arize Phoenix**: Open-source evaluation platform with direct Jupyter notebook embedding and OTEL-compliant trace exports [3].

## 2. Key Findings & Strategic Recommendations

1. **Self-Hosting Viability**: For air-gapped or HIPAA/SOC2 sensitive workloads, Langfuse and Arize Phoenix represent the only zero-data-leakage architectures.
2. **Evaluation & Grounding**: Automated LLM evaluation pipelines benefit significantly from LangGraph checkpointing and deterministic replay guarantees.`,
  citations: [
    {
      citation_id: "cite-1",
      source_id: "src-01",
      url: "https://langfuse.com/docs/deployment/self-host",
      claim:
        "Langfuse is fully open-source (MIT) backed by PostgreSQL and ClickHouse.",
    },
    {
      citation_id: "cite-2",
      source_id: "src-02",
      url: "https://docs.smith.langchain.com/pricing",
      claim:
        "LangSmith provides SaaS tiers with on-premise installation reserved for enterprise agreements.",
    },
    {
      citation_id: "cite-3",
      source_id: "src-03",
      url: "https://docs.arize.com/phoenix/deployment",
      claim:
        "Arize Phoenix supports direct in-process Jupyter execution and OTEL exports.",
    },
  ],
  created_at: "2026-10-21T17:22:15Z",
};

export const DEMO_AUDIT_EVENTS: DemoAuditEvent[] = [
  {
    isDemoSeed: true,
    id: "evt-01",
    run_id: "9f8a2b10-c3d4-4e5f-a6b7-c8d9e0f1a2b3",
    correlation_id: "corr-8410a91e-01",
    event_type: "RUN_QUEUED",
    actor: "operator-web",
    timestamp: "2026-10-21T18:30:00Z",
    payload: { objective_length: 96, domain: "ai-observability" },
  },
  {
    isDemoSeed: true,
    id: "evt-02",
    run_id: "9f8a2b10-c3d4-4e5f-a6b7-c8d9e0f1a2b3",
    correlation_id: "corr-8410a91e-01",
    event_type: "PLAN_SYNTHESIZED",
    actor: "langgraph-planner",
    timestamp: "2026-10-21T18:30:15Z",
    payload: { total_steps: 6, estimated_cost_usd: 0.42 },
  },
  {
    isDemoSeed: true,
    id: "evt-03",
    run_id: "9f8a2b10-c3d4-4e5f-a6b7-c8d9e0f1a2b3",
    correlation_id: "corr-8410a91e-01",
    event_type: "TOOL_CALLED",
    actor: "celery-worker-01",
    timestamp: "2026-10-21T18:30:45Z",
    payload: {
      tool: "discover_competitors",
      status: "SUCCESS",
      duration_ms: 350,
    },
  },
  {
    isDemoSeed: true,
    id: "evt-04",
    run_id: "9f8a2b10-c3d4-4e5f-a6b7-c8d9e0f1a2b3",
    correlation_id: "corr-8410a91e-01",
    event_type: "APPROVAL_REQUESTED",
    actor: "hitl-checkpoint-manager",
    timestamp: "2026-10-21T18:32:00Z",
    payload: { action: "PLAN_REVIEW", approval_id: "appr-8888-9999-aaaa-bbbb" },
  },
];
