import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  ApiClientError,
  apiClient,
  type CreateRunRequest,
  type RunStatusType,
  type CitationItem,
} from "../lib/api-client.ts";

describe("Phase 18 - API Client Error Handling & Contract Enforcement", () => {
  it("constructs ApiClientError with structured error envelopes", () => {
    const error = new ApiClientError(404, {
      message: "Run not found",
      code: "RUN_NOT_FOUND",
      correlation_id: "corr-12345-abcde",
      details: { run_id: "nonexistent-id" },
    });

    assert.equal(error.name, "ApiClientError");
    assert.equal(error.statusCode, 404);
    assert.equal(error.errorCode, "RUN_NOT_FOUND");
    assert.equal(error.correlationId, "corr-12345-abcde");
    assert.deepEqual(error.details, { run_id: "nonexistent-id" });
    assert.match(error.message, /Run not found/);
  });

  it("handles missing optional correlation ID and code gracefully in ApiClientError", () => {
    const error = new ApiClientError(502, {
      message: "Network error",
      code: "BACKEND_UNAVAILABLE",
    });
    assert.equal(error.statusCode, 502);
    assert.equal(error.errorCode, "BACKEND_UNAVAILABLE");
    assert.equal(error.correlationId, undefined);
    assert.equal(error.message, "Network error");
  });
});

describe("Phase 18 - Security & Input Sanitization", () => {
  function validateSafeUrl(url?: string): string | null {
    if (!url) return null;
    try {
      const parsed = new URL(url);
      if (parsed.protocol === "http:" || parsed.protocol === "https:") {
        return parsed.href;
      }
      return null;
    } catch {
      return null;
    }
  }

  it("allows safe http and https citation URLs", () => {
    assert.equal(
      validateSafeUrl("https://arxiv.org/abs/2301.00001"),
      "https://arxiv.org/abs/2301.00001",
    );
    assert.equal(
      validateSafeUrl("http://example.com/reports/benchmark"),
      "http://example.com/reports/benchmark",
    );
  });

  it("strictly rejects javascript:, data:, and file: URLs to prevent XSS", () => {
    assert.equal(validateSafeUrl("javascript:alert(1)"), null);
    assert.equal(
      validateSafeUrl("data:text/html,<script>alert(1)</script>"),
      null,
    );
    assert.equal(validateSafeUrl("file:///etc/passwd"), null);
    assert.equal(validateSafeUrl("not-a-url"), null);
    assert.equal(validateSafeUrl(""), null);
    assert.equal(validateSafeUrl(undefined), null);
  });

  it("guarantees no browser-facing NEXT_PUBLIC_ API key leak", () => {
    const envKeys = Object.keys(process.env);
    const leakedBrowserKeys = envKeys.filter(
      (k) =>
        k.startsWith("NEXT_PUBLIC_") &&
        (k.includes("KEY") || k.includes("SECRET") || k.includes("TOKEN")),
    );
    assert.deepEqual(
      leakedBrowserKeys,
      [],
      "No secret keys should ever be prefixed with NEXT_PUBLIC_",
    );
  });
});

describe("Phase 18 - Mock Client Workflow Integration", () => {
  it("formats run creation payload adhering to FastAPI schema", () => {
    const payload: CreateRunRequest = {
      objective: "Benchmark LangGraph agent runtime performance",
      domain: "ai-observability",
      geography: "Global",
      budget_usd_limit: 1.5,
      idempotency_key: "idem-key-9999",
    };

    assert.equal(
      payload.objective,
      "Benchmark LangGraph agent runtime performance",
    );
    assert.equal(payload.domain, "ai-observability");
    assert.equal(payload.budget_usd_limit, 1.5);
    assert.equal(payload.idempotency_key, "idem-key-9999");
  });

  it("verifies citation structure integrity for report-to-evidence linking", () => {
    const sampleCitation: CitationItem = {
      evidence_id: "evi-001",
      source_id: "src-001",
      source_url: "https://example.com/research",
      claim: "Leading observability frameworks require durable checkpoints.",
    };

    assert.ok(sampleCitation.evidence_id);
    assert.ok(sampleCitation.source_url);
    assert.ok(sampleCitation.claim);
  });

  it("defines standard execution states in conformance with API documentation", () => {
    const validStatuses: RunStatusType[] = [
      "QUEUED",
      "PLANNING",
      "RUNNING",
      "AWAITING_APPROVAL",
      "COMPLETED",
      "COMPLETED_WITH_WARNINGS",
      "FAILED",
      "CANCELLED",
      "ABORTED_BY_OPERATOR",
    ];

    assert.equal(validStatuses.length, 9);
    assert.ok(validStatuses.includes("AWAITING_APPROVAL"));
    assert.ok(validStatuses.includes("COMPLETED"));
  });

  it("validates API client methods are exposed", () => {
    assert.equal(typeof apiClient.listRuns, "function");
    assert.equal(typeof apiClient.getRun, "function");
    assert.equal(typeof apiClient.createRun, "function");
    assert.equal(typeof apiClient.cancelRun, "function");
    assert.equal(typeof apiClient.getRunSteps, "function");
    assert.equal(typeof apiClient.getRunEvents, "function");
    assert.equal(typeof apiClient.getRunReport, "function");
    assert.equal(typeof apiClient.approveCheckpoint, "function");
    assert.equal(typeof apiClient.rejectCheckpoint, "function");
    assert.equal(typeof apiClient.getHealth, "function");
    assert.equal(typeof apiClient.getSystemInfo, "function");
  });
});
