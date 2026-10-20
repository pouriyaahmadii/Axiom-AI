# Success Metrics and Evaluation Framework: AgentOps

## 1. Principles of Measurement

To maintain strict engineering integrity, AgentOps adheres to the following measurement standards:
- **No Fabricated Benchmarks**: The project never presents simulated or invented benchmark figures as measured reality.
- **Targets vs. Results**: All metrics in this document are defined as **Target Specifications** for the platform architecture. Measured results are only recorded after automated testing harnesses, load profiles, or empirical runs have been formally conducted.
- **Reproducibility**: Any metric reported in future phases must specify the exact test script, environment specification, deterministic seed, and command used to obtain it.

---

## 2. Target Metric Categories

### 2.1 Functional & Orchestration Reliability Targets

| Metric | Target Specification | Validation Method | Current Status |
| :--- | :--- | :--- | :--- |
| **Plan Validation Rate** | 100% of generated execution plans must pass deterministic schema and tool allowlist validation before execution begins. | Unit and property tests (`test_planning.py`) | *Target Defined (Unmeasured)* |
| **State Checkpoint Integrity** | 100% of state transitions must be serialized to PostgreSQL; a crashed or restarted worker must be able to resume without data loss. | Fault injection and worker termination test | *Target Defined (Unmeasured)* |
| **Bounded Execution Enforcement** | 0% of runs may exceed `MAX_PLAN_STEPS` or `MAX_EXECUTION_SECONDS`. | Boundary stress test with adversarial loops | *Target Defined (Unmeasured)* |
| **Deterministic Mock Replay** | Identical inputs in Mock mode with the same seed must produce bit-for-bit identical plan DAGs and step sequences. | Deterministic replay test suite | *Target Defined (Unmeasured)* |

---

### 2.2 Security & Safety Boundary Targets

| Metric | Target Specification | Validation Method | Current Status |
| :--- | :--- | :--- | :--- |
| **SSRF Request Interception** | 100% of outbound tool requests directed at loopback (`127.0.0.0/8`), private subnets (`10.0.0.0/8`, `192.168.0.0/16`, `172.16.0.0/12`), or cloud metadata (`169.254.169.254`) must be rejected. | Automated SSRF test suite (`test_security.py`) | **100% Passed (12/12 Baseline Tests)** |
| **Arbitrary Code Interception** | Zero arbitrary shell execution, SQL generation, or runtime `eval` calls allowed within tool execution pathways. | Static security analysis (`bandit`) & code review | *Target Defined (Audited in Architecture)* |
| **HITL Gate Compliance** | 100% of plan steps marked with `requires_human_approval = True` must halt execution until explicit cryptographic token approval is recorded. | Integration test (`test_approval_flow.py`) | *Target Defined (Unmeasured)* |

---

### 2.3 Citation Grounding & Report Quality Targets

| Metric | Target Specification | Validation Method | Current Status |
| :--- | :--- | :--- | :--- |
| **Factual Citation Coverage** | 100% of material factual claims (product names, published prices, launch dates) in the final report must link to a valid `evidence_id`. | Citation auditor script parsing report AST | *Target Defined (Unmeasured)* |
| **Evidence Hash Verification** | 100% of cited snippets must match the SHA-256 hash stored in the immutable `EvidenceRecord` table. | Cryptographic integrity validation pass | *Target Defined (Unmeasured)* |
| **Evidence vs. Inference Separation** | Final report must contain structurally distinct sections for empirical evidence vs. analytical synthesis. | Markdown structure parser validation | *Target Defined (Unmeasured)* |

---

### 2.4 Performance & Operational Targets

| Metric | Target Specification | Validation Method | Current Status |
| :--- | :--- | :--- | :--- |
| **End-to-End Mock Run Latency** | A full 5-step mock research cycle must complete in under 5.0 seconds locally. | Automated timing test (`pytest -k test_mock_flow`) | *Target Defined (Unmeasured)* |
| **API Response Latency (P95)** | Health and run inspection endpoints (`GET /api/v1/runs/{id}`) must respond in < 50ms under normal local load. | Local benchmark suite (`httpx` benchmark) | *Target Defined (Unmeasured)* |
| **Resource Footprint** | Local Docker Compose stack (FastAPI, Redis, PostgreSQL, Celery, Next.js) must idle at < 1.5 GB total RAM. | Docker stats inspection | *Target Defined (Unmeasured)* |

---

### 2.5 Developer & Evaluation Experience Targets

| Metric | Target Specification | Validation Method | Current Status |
| :--- | :--- | :--- | :--- |
| **Zero-Key Quickstart Time** | A new developer should be able to clone the repository, run tests, and spin up the complete mock demonstration in < 5 minutes. | First-time installation walkthrough | *Target Defined (In Progress)* |
| **Automated Test Coverage** | Backend unit and integration test coverage target: ≥ 85% branch coverage. | `pytest --cov=app --cov-report=term` | *Target Defined (Baseline Active)* |
| **Lint & Type Conformance** | 0 warnings or errors under `ruff check` and strict Pydantic v2 validation. | Continuous Integration lint check | **Active (0 errors, clean passing)** |
