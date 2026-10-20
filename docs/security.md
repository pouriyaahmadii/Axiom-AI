# AgentOps: Security Architecture & Trust Boundaries

## 1. Security Philosophy

AgentOps operates under an explicit **Zero-Trust Model** for all inputs originating outside verified internal system controls. Specifically:
- User prompts may contain injection attempts, malicious instructions, or jailbreaks.
- Web content, API responses, and search results retrieved from third parties are treated as untrusted and potentially malicious (indirect prompt injection, SSRF targets).
- Model completions (LLM output) are treated as untrusted suggestions until passed through deterministic Pydantic schema validation.
- Tool invocation is strictly allowlisted; execution of arbitrary shell commands, raw SQL, or Python `eval` is forbidden by design.

## 2. Threat Modeling & Defenses

| Threat Vector | Mitigation Strategy | Implementation |
| :--- | :--- | :--- |
| **Server-Side Request Forgery (SSRF)** | Domain and IP validation; rejection of loopback, RFC 1918 private subnets, link-local metadata (169.254.169.254). | `app.core.security.is_safe_url` & `validate_url_for_request` |
| **Prompt & Indirect Injection** | Schema boundary isolation; strict Pydantic parsing; separating instructions from raw untrusted context. | Structured output parsing with bounded fields. |
| **Unbounded Resource Consumption** | Hard caps on plan steps, per-step execution timeouts, overall run duration limits, and USD budget constraints. | Configurable limits in `Settings` (`MAX_PLAN_STEPS`, `MAX_EXECUTION_SECONDS`, `BUDGET_USD_LIMIT`). |
| **Unauthorized Consequential Actions** | Human-in-the-Loop (HITL) gate with approval tokens; execution pause and resume mechanics. | LangGraph checkpoint interrupts + PostgreSQL approval tokens. |
| **Data Leakage & Secret Exposure** | `.gitignore` rules, `.env.example` templates with zero hardcoded credentials, loopback interface bindings. | Default `127.0.0.1` binding and mock provider fallback. |
| **Webhook Spoofing** | Constant-time HMAC SHA-256 signature verification for external webhooks (e.g. n8n). | `app.core.security.verify_hmac_signature` |

## 3. Network & Service Isolation

- **API & Worker**: Bind exclusively to `127.0.0.1` in development.
- **Database & Cache**: PostgreSQL and Redis are isolated within internal Docker bridge networks and are never exposed publicly.
- **Mock Mode**: Fully self-contained local testing with zero outbound network calls.
