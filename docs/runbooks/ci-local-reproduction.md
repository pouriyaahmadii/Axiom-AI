# CI Local Reproduction Runbook (`docs/runbooks/ci-local-reproduction.md`)

This runbook documents the configuration, security controls, and exact commands required to reproduce every job and verification check executed in the AgentOps GitHub Actions CI pipeline (`.github/workflows/ci.yml`).

---

## 1. CI Pipeline Architecture & Security Controls

The AgentOps continuous integration pipeline adheres to strict software supply-chain security standards (OpenSSF and GitHub Security Best Practices):

| Control | Implementation | Verification |
| :--- | :--- | :--- |
| **Least Privilege Tokens** | Workflow-level `permissions: contents: read` | No write, administrative, or deployment permissions granted. |
| **Pinned Action Dependencies**| Immutable 40-character commit SHAs for third-party actions | Prevents tag-mutation and supply-chain tampering attacks. |
| **Zero Real Credentials** | 100% deterministic mock mode (`LLM_PROVIDER=mock`, `SEARCH_PROVIDER=mock`) | No paid API keys or external secrets stored or required in CI. |
| **Zero Network Flakiness** | Database integration tests run against in-process SQLite memory engines | Zero external database or network dependency. |
| **No Deployments or Pushes** | Strictly non-mutating validation and build verification | No container image pushes or external deployments. |
| **Preserved Failure Visibility**| Zero masked errors or `\|\| true` bypasses | Actionable failure output with exact line numbers and traces. |
| **Concurrency Control** | `concurrency: cancel-in-progress: true` | Automatically aborts redundant CI runs on new pushes. |

---

## 2. CI Jobs & Local Reproduction Matrix

Every check in the CI workflow maps directly to a reproducible local command:

| CI Job | Scope | Local CLI Command | Expected Result |
| :--- | :--- | :--- | :--- |
| **1. Python Lint & Format** | Backend code style & PEP 8 rules | `ruff format --check . && ruff check .` | 0 formatting diffs, 0 lint warnings |
| **2. Python Type Checking** | Static type checking (Mypy strict) | `mypy services/backend/app services/backend/tests` | Success: no issues found |
| **3. Python Unit Tests** | Isolated domain, schema, and logic tests | `pytest services/backend/tests/unit -v` | 110 passed |
| **4. Integration & Security**| Relational database, outbox, and SSRF tests | `pytest services/backend/tests/integration services/backend/tests/contract services/backend/tests/security -v` | 171 passed |
| **5. Frontend Lint & Types** | Next.js 14 ESLint & TypeScript compilation | `npm --prefix apps/web run lint && npm --prefix apps/web run type-check` | No ESLint errors, no type errors |
| **6. Frontend Tests & Build**| React component tests & standalone build | `npm --prefix apps/web test && npm --prefix apps/web run build` | 20 passed, standalone server.js |
| **7. n8n JSON Validation** | Schema integrity & credential leakage scan | `python scripts/validate_n8n_workflows.py` | 10 workflow files valid |
| **8. Docker Compose Check** | Compose manifest, port bounds, healthchecks | `docker compose -p agentops config && docker compose -p agentops --profile ollama config` | Valid YAML, loopback bindings |
| **9. Dependency Audit** | Permissive license compliance & CVE audit | `python scripts/audit_dependencies.py` | 100% compliant with permissive policy |
| **10. Secret Scanning** | High-entropy token & private key detector | `python scripts/scan_secrets.py` | 0 hardcoded secrets detected |
| **11. Agent Evaluations** | 36 deterministic mock evaluation scenarios | `pytest services/backend/tests/evals -v && pytest services/backend/tests/perf -v` | 48 passed |

---

## 3. Step-by-Step Local Reproduction Guide

### Prerequisites
Ensure your local Python virtual environment and frontend node modules are installed:
```bash
# Backend virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Frontend dependencies
npm --prefix apps/web ci
```

---

### Job 1: Python Linting and Formatting
Runs Ruff linter and formatter:
```bash
# Verify formatting
ruff format --check .

# Run linter
ruff check .

# (Optional) Auto-fix safe lint and format issues
ruff format .
ruff check --fix .
```

---

### Job 2: Python Static Type Checking
Executes Mypy across application services and tests:
```bash
mypy services/backend/app services/backend/tests
```

---

### Job 3 & 4: Python Unit, Integration, and Security Tests
Executes Pytest with in-memory database isolation:
```bash
# Run unit tests only
pytest services/backend/tests/unit -v

# Run database integration tests
pytest services/backend/tests/integration -v

# Run contract tests
pytest services/backend/tests/contract -v

# Run security hardening tests
pytest services/backend/tests/security -v
```

---

### Job 5 & 6: Frontend Linting, Type Checking, Tests, and Build
Validates the Next.js 14 web application:
```bash
# Run ESLint
npm --prefix apps/web run lint

# Run TypeScript type check
npm --prefix apps/web run type-check

# Run unit and design system tests
npm --prefix apps/web test

# Validate Next.js production standalone build
npm --prefix apps/web run build
```

---

### Job 7: n8n Workflow JSON Validation
Validates that all n8n workflows conform to the schema and contain no real API keys:
```bash
python scripts/validate_n8n_workflows.py
```

---

### Job 8: Docker Compose Validation
Verifies syntax, resource limits, and loopback port bindings without starting containers:
```bash
# Validate core 6-service topology
docker compose -p agentops config

# Validate optional Ollama container profile
docker compose -p agentops --profile ollama config
```

---

### Job 9: Dependency License and Vulnerability Audit
Audits Python package licenses against the Permissive License Policy (`docs/17-dependency-policy.md`):
```bash
python scripts/audit_dependencies.py

# (Optional) Run pip-audit if installed
pip-audit --desc
```

---

### Job 10: Secret Scanning
Scans the entire repository tree for private keys, AWS tokens, GitHub tokens, and hardcoded API keys:
```bash
python scripts/scan_secrets.py
```

---

### Job 11: Deterministic Agent Evaluations
Executes the comprehensive 36-case evaluation suite and performance benchmarks in offline Mock mode:
```bash
# Run evaluation test suite
pytest services/backend/tests/evals -v

# Run performance and budget ceiling tests
pytest services/backend/tests/perf -v
```

---

## 4. One-Command Master Quality Gate

To run the complete suite of local checks in a single command before pushing to Git:

```bash
make validate-all
```

Or using shell directly:
```bash
ruff format --check . && \
ruff check . && \
mypy services/backend/app services/backend/tests && \
pytest services/backend/tests -q && \
npm --prefix apps/web run lint && \
npm --prefix apps/web run type-check && \
npm --prefix apps/web test && \
python scripts/validate_n8n_workflows.py && \
python scripts/scan_secrets.py && \
python scripts/audit_dependencies.py && \
docker compose -p agentops config > /dev/null && \
echo "==> All 11 CI checks PASSED cleanly."
```
