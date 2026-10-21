# AgentOps Evaluation Framework (`evals`)

Evaluation datasets, repeatable benchmarking test cases, and gold-standard baselines for validating agent planning, tool grounding, evidence provenance, and security resilience.

---

## 1. Directory Structure

```text
evals/
├── cases/
│   └── evaluation_suite.json      # 34 structured evaluation cases covering 17 vulnerability categories
├── datasets/
│   └── competitor_corpus.json     # Hermetic, offline corpus for deterministic competitor research
├── baselines/
│   └── gold_standard_report.json  # Reference gold-standard plan, citations, and report structure
├── reports/                       # Generated evaluation scoring runs and benchmark artifacts
└── README.md                      # This framework guide
```

---

## 2. Evaluation Suite Taxonomy (34 Cases across 17 Categories)

The evaluation suite (`cases/evaluation_suite.json`) defines 34 test cases covering every critical vulnerability and failure mode required by the Phase 20 specification:

| Index | Category | Case IDs | Description |
| :---: | :--- | :--- | :--- |
| **1** | Invalid & Ambiguous User Requests | `eval-01`, `eval-02` | Empty whitespace prompt and oversized payload boundary rejection. |
| **2** | Invalid Execution Plans | `eval-03`, `eval-04` | DAG dependency cycles and plan length exceeding step limits. |
| **3** | Unknown Tools | `eval-05`, `eval-06` | Execution of unregistered shell or private unauthorized tools. |
| **4** | Malformed Structured Outputs | `eval-07`, `eval-08` | Truncated JSON recovery and Pydantic schema type mismatches. |
| **5** | Incomplete Evidence | `eval-09`, `eval-10` | Zero valid sources and uncited empirical factual claims. |
| **6** | Contradictory Sources | `eval-11`, `eval-12` | Conflicting pricing ($8/mo vs $12/mo) and contradictory SLA metrics. |
| **7** | Stale Facts | `eval-13`, `eval-14` | Historical sources older than 90 days flagged as stale. |
| **8** | Prompt Injection in Content | `eval-15`, `eval-16` | Adversarial system override instructions and SSRF exfiltration traps. |
| **9** | Provider Rate Limits | `eval-17`, `eval-18` | HTTP 429 transient backoff and permanent rate-limit exhaustion diagnostics. |
| **10** | Provider Timeouts | `eval-19`, `eval-20` | Socket read timeouts and step execution limit enforcement (60s). |
| **11** | Worker Restart | `eval-21`, `eval-22` | Worker crash checkpoint recovery and crash while awaiting human approval. |
| **12** | Duplicate Job Delivery | `eval-23`, `eval-24` | Celery broker task deduplication and idempotent API run creation. |
| **13** | Duplicate Approval | `eval-25`, `eval-26` | Rapid double-click approval idempotency and payload drift rejection. |
| **14** | Budget Exhaustion | `eval-27`, `eval-28` | Financial dollar ceiling abort ($1.00) and step count limit. |
| **15** | Cancellation | `eval-29`, `eval-30` | Safe step boundary cancellation and terminal state immutability. |
| **16** | Unsafe URL Retrieval (SSRF) | `eval-31`, `eval-32` | AWS/GCP cloud metadata endpoints and RFC 1918 private subnets. |
| **17** | Authorization Failure | `eval-33`, `eval-34` | Missing API keys and cross-tenant workspace boundary enforcement. |

---

## 3. Running the Evaluation Suite

The evaluation suite runs entirely offline without external network dependencies:

```bash
# Execute all 34 evaluation benchmark cases
./.venv/bin/pytest -m evals -v

# Execute the specific evaluation test file
./.venv/bin/pytest services/backend/tests/evals/test_evaluation_suite.py -v

# Run the full security hardening and regression suite
./.venv/bin/pytest -m security -v
```

---

## 4. Grounding & Baseline Comparison

- **Deterministic Evaluation**: Tests run against the static `datasets/competitor_corpus.json` corpus using the `MockLLMProvider` and `MockSearchProvider`.
- **Baseline Verification**: Test outputs are compared against `baselines/gold_standard_report.json` to verify:
  1. $100\%$ of factual statements contain valid `[^ev-...]` citation anchors.
  2. All cited evidence items exist in PostgreSQL and match their recorded SHA-256 hashes.
  3. Contradictions are explicitly documented in neutral comparison sections rather than arbitrarily discarded.
