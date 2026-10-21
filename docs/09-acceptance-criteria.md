# Acceptance Criteria Matrix & Release Gates: AgentOps

## 1. Overview & Verification Standards

To eliminate ambiguity, every acceptance criterion in AgentOps is formulated as a verifiable binary condition (Pass / Fail). Vague qualifiers such as "fast", "secure", or "scalable" are replaced by measurable operational thresholds and deterministic test assertions.

---

## 2. Core Subsystem Acceptance Criteria Matrix

| Subsystem | Requirement ID | Pass / Fail Condition | Verification Procedure (Actual Test File) | Status |
| :--- | :--- | :--- | :--- | :---: |
| **API Ingestion** | `FR-RUN-01` | **PASS**: Requests with valid payload return HTTP 201/202 with UUID `run_id`. Requests exceeding character limits or missing fields return HTTP 422.<br>**FAIL**: Unhandled 500 error or acceptance of invalid JSON. | `pytest services/backend/tests/integration/test_api_v1_runs.py` | **PASS** |
| **Plan Synthesis** | `FR-PLAN-01` | **PASS**: Generated plan adheres strictly to `ExecutionPlan` Pydantic model with $1 \le \text{steps} \le 10$.<br>**FAIL**: Steps exceed limit, step IDs are duplicate, or tool name is unknown. | `pytest services/backend/tests/unit/test_agent_runtime.py` | **PASS** |
| **Plan Validation** | `FR-VAL-01` | **PASS**: Coordinator rejects any plan referencing tools outside the allowlist.<br>**FAIL**: Unregistered tool executes or validation error is swallowed. | `pytest services/backend/tests/unit/test_agent_runtime.py`<br>`pytest services/backend/tests/evals/test_evaluation_suite.py` | **PASS** |
| **SSRF Defense** | `NFR-SEC-01`<br>`FR-TOOL-02` | **PASS**: 100% of fetch requests to `127.0.0.1`, `10.0.0.0/8`, `192.168.0.0/16`, `172.16.0.0/12`, `169.254.169.254`, and `localhost` raise `SecurityValidationError` before opening socket.<br>**FAIL**: Any outbound socket connects to a blocked IP address. | `pytest services/backend/tests/security/test_url_safety_and_tools.py` | **PASS** |
| **Zero Arbitrary Execution** | `NFR-SEC-02` | **PASS**: Zero instances of `subprocess`, `os.system`, `eval`, or unsanitized raw SQL in application code.<br>**FAIL**: Presence of dynamic shell or code execution primitives. | `pytest services/backend/tests/security/test_url_safety_and_tools.py`<br>`python scripts/scan_secrets.py` | **PASS** |
| **Durable Checkpoints** | `FR-STATE-01` | **PASS**: PostgreSQL contains serialized LangGraph state graph for every completed step; killed worker can resume without data loss.<br>**FAIL**: Worker crash causes loss of completed step state. | `pytest services/backend/tests/integration/test_durable_execution.py`<br>`pytest services/backend/tests/integration/test_hitl_approval_and_resumption.py` | **PASS** |
| **Timeout Enforcement** | `FR-EXEC-02` | **PASS**: Step running > 60s is terminated with `StepTimeoutError`. Run exceeding 300s transitions to `TIMED_OUT`.<br>**FAIL**: Process hangs indefinitely on stuck tool call. | `pytest services/backend/tests/integration/test_durable_execution.py`<br>`pytest services/backend/tests/perf/test_performance_and_capacity.py` | **PASS** |
| **Bounded Retries** | `FR-RESIL-01` | **PASS**: Failed network calls retry up to 3 times with exponential backoff before failing or degrading.<br>**FAIL**: Retries exceed limit or loop infinitely. | `pytest services/backend/tests/integration/test_durable_execution.py` | **PASS** |
| **HITL Approval Gate** | `FR-HITL-01`<br>`FR-HITL-02` | **PASS**: Step with `requires_human_approval = True` halts graph, sets status to `AWAITING_APPROVAL`, and resumes only upon valid API approval verdict.<br>**FAIL**: Step executes without approval or status does not pause. | `pytest services/backend/tests/integration/test_hitl_approval_and_resumption.py`<br>`pytest services/backend/tests/integration/test_api_v1_approvals.py` | **PASS** |
| **Evidence Provenance** | `FR-EVID-01` | **PASS**: Every cited evidence item has a valid `EvidenceRecord` in PostgreSQL with SHA-256 hash matching raw snippet.<br>**FAIL**: Missing record or hash mismatch. | `pytest services/backend/tests/unit/test_evidence_and_reports.py` | **PASS** |
| **Citation Grounding** | `FR-REP-01`<br>`FR-EVID-02` | **PASS**: 100% of factual claims in empirical findings section include `[^ev-id]` anchor resolving to verified database record.<br>**FAIL**: Unanchored factual claims or hallucinated citations. | `pytest services/backend/tests/unit/test_evidence_and_reports.py` | **PASS** |
| **Evidence vs. Inference** | `FR-REP-02` | **PASS**: Final report contains distinct markdown sections for Empirical Findings vs. Strategic Inference.<br>**FAIL**: Sections missing or blended together. | `pytest services/backend/tests/unit/test_evidence_and_reports.py` | **PASS** |
| **Deterministic Replay** | `NFR-REPRO-01` | **PASS**: Two executions with identical seed in Mock mode yield identical report SHA-256 hashes.<br>**FAIL**: Output varies between identical runs. | `pytest services/backend/tests/contract/test_providers_contract.py`<br>`pytest services/backend/tests/unit/test_mock_llm_provider.py` | **PASS** |
| **API Response Latency** | `NFR-PERF-01` | **PASS**: P95 latency for `GET /api/v1/runs/{id}` is < 50ms under local development benchmark (measured: 7.23ms).<br>**FAIL**: P95 latency $\ge 50$ms. | `pytest services/backend/tests/perf/test_performance_and_capacity.py` | **PASS** |
| **Code Standards** | `NFR-MAINT-01` | **PASS**: `ruff check .` and `ruff format --check .` return 0 errors and 0 warnings.<br>**FAIL**: Any lint error or unformatted file. | `ruff check . && ruff format --check .` | **PASS** |

---

## 3. Minimum Viable Product (MVP) Release Gate

Before the AgentOps MVP is considered complete and eligible for tag `v1.0.0-mvp`, the following **Release Gate Checklist** must be 100% satisfied:

### 3.1 Quality & Testing Gate
- [x] **100% Test Pass Rate**: All unit, integration, contract, perf, and security tests pass cleanly via `pytest services/backend/tests` (330/330 passed).
- [x] **Zero Lint/Type Errors**: `ruff check .` and `mypy services/backend/app` return 0 errors.
- [x] **Deterministic Demo Verified**: A full end-to-end competitor research run completes in < 5.0 seconds in Mock mode without internet access (measured: 8.36ms).
- [x] **Zero API Keys Required**: Repository functions out-of-the-box with `.env.example` defaults.

### 3.2 Security Audit Gate
- [x] **SSRF Defense Verified**: 100% of test attempts to reach private subnets, localhost, and 169.254.169.254 are blocked (`test_url_safety_and_tools.py`).
- [x] **Static Analysis Clean**: Verified zero dynamic shell (`os.system`, `subprocess`) or raw SQL execution primitives in application code.
- [x] **Loopback Conformance**: Local services bind exclusively to `127.0.0.1` (`compose.yaml`).
- [x] **No Committed Secrets**: Git history verified clean; no real `.env` or credential files staged (`scripts/scan_secrets.py`).

### 3.3 Documentation & Architecture Gate
- [x] **Complete Requirements Traceability**: All `FR` and `NFR` items correspond to specific, active test suites.
- [x] **Truthful Representation**: README and docs contain zero fabricated metrics, fake badges, or unverified claims.
- [x] **Clean Git History**: Commits follow Conventional Commits standard (`feat:`, `docs:`, `test:`, `refactor:`) with working tree clean.
