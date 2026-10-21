import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  cn,
  formatTimestamp,
  formatUSD,
  truncateIdentifier,
} from "../lib/utils.ts";
import {
  RUN_STATUS_META,
  MAIN_NAVIGATION,
  type RunStatusType,
} from "../lib/constants.ts";
import {
  DEMO_APPROVALS,
  DEMO_AUDIT_EVENTS,
  DEMO_EVIDENCE,
  DEMO_REPORT,
  DEMO_RUNS,
  DEMO_STEPS,
} from "../lib/mock-data.ts";

describe("AgentOps Design System - Utilities", () => {
  it("merges Tailwind classes correctly with clsx and tailwind-merge", () => {
    const result = cn("p-4", "p-2", {
      "text-red-500": true,
      "bg-blue-500": false,
    });
    assert.equal(result, "p-2 text-red-500");
  });

  it("formats USD currency values accurately", () => {
    assert.equal(formatUSD(1.5), "$1.50");
    assert.equal(formatUSD(0.42), "$0.42");
    assert.equal(formatUSD(0), "$0.00");
  });

  it("truncates identifiers with start and end characters preserved", () => {
    const uuid = "9f8a2b10-c3d4-4e5f-a6b7-c8d9e0f1a2b3";
    const truncated = truncateIdentifier(uuid, 8, 4);
    assert.equal(truncated, "9f8a2b10...a2b3");
  });

  it("formats ISO timestamps cleanly", () => {
    const formatted = formatTimestamp("2026-10-21T18:30:00Z");
    assert.notEqual(formatted, "-");
    assert.equal(typeof formatted, "string");
  });
});

describe("AgentOps Design System - Semantic Status & Accessibility", () => {
  const ALL_STATUSES: RunStatusType[] = [
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

  it("defines explicit dual-encoding (icon + label) for all 9 backend run statuses", () => {
    for (const status of ALL_STATUSES) {
      const meta = RUN_STATUS_META[status];
      assert.ok(meta, `Status meta for ${status} must exist`);
      assert.ok(meta.label, `Label for ${status} must be non-empty`);
      assert.ok(meta.icon, `Icon for ${status} must exist`);
      assert.ok(
        ["neutral", "info", "success", "warning", "danger"].includes(
          meta.variant,
        ),
        `Variant for ${status} must be semantic`,
      );
      assert.ok(
        meta.description,
        `Description for ${status} must be non-empty`,
      );
    }
  });

  it("provides complete navigation catalog with valid paths", () => {
    assert.ok(MAIN_NAVIGATION.length >= 6);
    for (const nav of MAIN_NAVIGATION) {
      assert.ok(nav.name);
      assert.ok(nav.href.startsWith("/"));
    }
  });
});

describe("AgentOps Design System - Seed Data Integrity", () => {
  it("ensures all demo data records are strictly flagged with isDemoSeed: true", () => {
    for (const run of DEMO_RUNS) {
      assert.equal(run.isDemoSeed, true);
      assert.ok(run.id);
      assert.ok(run.budget_usd_limit > 0);
    }

    for (const step of DEMO_STEPS) {
      assert.equal(step.isDemoSeed, true);
      assert.ok(step.tool_name);
    }

    for (const ev of DEMO_EVIDENCE) {
      assert.equal(ev.isDemoSeed, true);
      assert.equal(ev.content_hash.length, 64); // SHA-256
      assert.equal(ev.validation_status, "VERIFIED");
    }

    assert.equal(DEMO_REPORT.isDemoSeed, true);
    assert.ok(DEMO_REPORT.citations.length > 0);

    for (const appr of DEMO_APPROVALS) {
      assert.equal(appr.isDemoSeed, true);
      assert.equal(appr.payload_hash.length, 64);
    }

    for (const evt of DEMO_AUDIT_EVENTS) {
      assert.equal(evt.isDemoSeed, true);
      assert.ok(evt.correlation_id);
    }
  });
});
