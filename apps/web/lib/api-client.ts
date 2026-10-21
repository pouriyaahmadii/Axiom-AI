/**
 * Type-Safe API Client for AgentOps FastAPI Backend.
 *
 * Communicates through the secure `/api/proxy/` Route Handler in the browser,
 * preventing any credential leakage while matching the backend's exact OpenAPI contract.
 */

import { type RunStatusType } from "./constants.ts";
export type { RunStatusType };

export interface ApiError {
  code: string;
  message: string;
  details?: unknown;
  correlation_id?: string;
}

export class ApiClientError extends Error {
  public statusCode: number;
  public errorCode: string;
  public correlationId?: string;
  public details?: unknown;

  constructor(statusCode: number, error: ApiError) {
    super(error.message || `API request failed with status ${statusCode}`);
    this.name = "ApiClientError";
    this.statusCode = statusCode;
    this.errorCode = error.code || "UNKNOWN_ERROR";
    this.correlationId = error.correlation_id;
    this.details = error.details;
  }
}

// ==========================================
// API Domain Schemas
// ==========================================

export interface HealthResponse {
  status: string;
  app_name: string;
  environment: string;
  llm_provider: string;
  search_provider: string;
  database?: string;
  redis?: string;
}

export interface SystemInfoResponse {
  app_name: string;
  version: string;
  environment: string;
  limits: {
    max_plan_steps: number;
    max_execution_seconds: number;
    step_timeout_seconds: number;
    max_retries_per_step: number;
    budget_usd_limit: number;
  };
  providers: {
    llm: string;
    search: string;
  };
}

export interface RunSummary {
  run_id: string;
  objective: string;
  domain: string;
  status: RunStatusType;
  created_at: string;
  completed_at: string | null;
}

export interface RunListResponse {
  items: RunSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface StepCompact {
  step_id: string;
  step_index: number;
  step_identifier: string;
  title: string;
  tool_name: string;
  status: string;
  requires_human_approval: boolean;
}

export interface PlanSummary {
  total_steps: number;
  steps: StepCompact[];
}

export interface ApprovalPending {
  approval_id: string;
  step_id?: string | null;
  proposed_action: Record<string, unknown>;
}

export interface RunDetail {
  run_id: string;
  status: RunStatusType;
  objective: string;
  domain: string;
  geography: string | null;
  llm_provider: string;
  search_provider: string;
  budget_usd_limit: number;
  estimated_cost_usd: number;
  attempt_count?: number;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  error_message: string | null;
  plan: PlanSummary | null;
  approval_pending: ApprovalPending | null;
}

export interface CreateRunRequest {
  objective: string;
  domain: string;
  geography?: string | null;
  budget_usd_limit?: number;
  constraints?: Record<string, unknown> | null;
  provider_override?: Record<string, unknown> | null;
  idempotency_key?: string | null;
}

export interface CreateRunResponse {
  run_id: string;
  status: RunStatusType;
  created_at: string;
}

export interface RunCancelResponse {
  run_id: string;
  status: RunStatusType;
  message: string;
}

export interface RunStep {
  step_id: string;
  run_id: string;
  step_index: number;
  step_identifier: string;
  title: string;
  tool_name: string;
  parameters: Record<string, unknown>;
  requires_human_approval: boolean;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "SKIPPED";
  retry_count: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface RunStepListResponse {
  run_id: string;
  items: RunStep[];
  total: number;
}

export interface AuditEvent {
  event_id: string;
  run_id: string | null;
  step_id: string | null;
  correlation_id: string | null;
  event_type: string;
  actor: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface AuditEventListResponse {
  run_id: string;
  items: AuditEvent[];
  total: number;
  limit: number;
  offset: number;
}

export interface CitationItem {
  marker?: string;
  evidence_id?: string;
  source_id?: string;
  source_url?: string;
  url?: string;
  claim?: string;
}

export interface ReportResponse {
  report_id: string;
  run_id: string;
  title: string;
  markdown_content: string;
  executive_summary: string;
  citations: CitationItem[];
  metadata_payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ApprovalActionRequest {
  operator_notes?: string | null;
  expected_payload_hash?: string | null;
}

export interface ApprovalRejectRequest {
  operator_notes?: string | null;
  reason?: string | null;
  abort_run?: boolean;
}

export interface ApprovalResponse {
  approval_id: string;
  run_id: string;
  step_id: string | null;
  action: string;
  payload_hash: string;
  version: number;
  status: "PENDING" | "APPROVED" | "REJECTED" | "EXPIRED";
  proposed_action: Record<string, unknown>;
  operator_notes: string | null;
  resolved_by: string | null;
  expires_at: string | null;
  resolved_at: string | null;
  run_status: RunStatusType;
}

// ==========================================
// Base Fetch Wrapper
// ==========================================

const PROXY_BASE = "/api/proxy";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${PROXY_BASE}/${path.replace(/^\//, "")}`;
  const headers = new Headers(options.headers || {});

  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(url, {
    ...options,
    headers,
  });

  const contentType = res.headers.get("content-type") || "";
  let payload: unknown;

  if (contentType.includes("application/json")) {
    payload = await res.json();
  } else {
    payload = await res.text();
  }

  if (!res.ok) {
    const errorData =
      payload && typeof payload === "object" && "error" in payload
        ? (payload as { error: ApiError }).error
        : { code: `HTTP_${res.status}`, message: res.statusText };

    throw new ApiClientError(res.status, errorData);
  }

  return payload as T;
}

// ==========================================
// Exported Client Methods
// ==========================================

export const apiClient = {
  /**
   * Check operational health of the backend and dependencies.
   */
  async getHealth(): Promise<HealthResponse> {
    return request<HealthResponse>("health");
  },

  /**
   * Get system constraints and runtime boundaries.
   */
  async getSystemInfo(): Promise<SystemInfoResponse> {
    return request<SystemInfoResponse>("info");
  },

  /**
   * Retrieve paginated runs collection with optional status filter.
   */
  async listRuns(
    params: {
      status?: string;
      limit?: number;
      offset?: number;
    } = {},
  ): Promise<RunListResponse> {
    const search = new URLSearchParams();
    if (params.status && params.status !== "ALL")
      search.set("status", params.status);
    if (params.limit) search.set("limit", params.limit.toString());
    if (params.offset !== undefined)
      search.set("offset", params.offset.toString());

    const qs = search.toString();
    return request<RunListResponse>(`runs${qs ? `?${qs}` : ""}`);
  },

  /**
   * Retrieve state and execution plan of an individual run.
   */
  async getRun(runId: string): Promise<RunDetail> {
    return request<RunDetail>(`runs/${runId}`);
  },

  /**
   * Submit a new research analysis run for background execution (202 Accepted).
   */
  async createRun(data: CreateRunRequest): Promise<CreateRunResponse> {
    return request<CreateRunResponse>("runs", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  /**
   * Cancel an ongoing research run.
   */
  async cancelRun(runId: string): Promise<RunCancelResponse> {
    return request<RunCancelResponse>(`runs/${runId}/cancel`, {
      method: "POST",
    });
  },

  /**
   * Retrieve sequential plan steps for a run.
   */
  async getRunSteps(runId: string): Promise<RunStepListResponse> {
    return request<RunStepListResponse>(`runs/${runId}/steps`);
  },

  /**
   * Retrieve audit events for a run.
   */
  async getRunEvents(
    runId: string,
    params: { event_type?: string; limit?: number; offset?: number } = {},
  ): Promise<AuditEventListResponse> {
    const search = new URLSearchParams();
    if (params.event_type && params.event_type !== "ALL") {
      search.set("event_type", params.event_type);
    }
    if (params.limit) search.set("limit", params.limit.toString());
    if (params.offset !== undefined)
      search.set("offset", params.offset.toString());

    const qs = search.toString();
    return request<AuditEventListResponse>(
      `runs/${runId}/events${qs ? `?${qs}` : ""}`,
    );
  },

  /**
   * Retrieve synthesized final report with grounded citations.
   */
  async getRunReport(runId: string): Promise<ReportResponse> {
    return request<ReportResponse>(`runs/${runId}/report`);
  },

  /**
   * Approve a gated execution checkpoint.
   */
  async approveCheckpoint(
    approvalId: string,
    data: ApprovalActionRequest = {},
  ): Promise<ApprovalResponse> {
    return request<ApprovalResponse>(`approvals/${approvalId}/approve`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  /**
   * Reject a gated execution checkpoint with documented rationale.
   */
  async rejectCheckpoint(
    approvalId: string,
    data: ApprovalRejectRequest,
  ): Promise<ApprovalResponse> {
    return request<ApprovalResponse>(`approvals/${approvalId}/reject`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  },
};
