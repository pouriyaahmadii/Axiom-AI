# AgentOps

> Maintainable, secure-by-default, observable, self-hostable AI Agent Operations Platform.

AgentOps accepts research and analysis requests, constructs validated execution plans, executes allowlisted tools, preserves durable state, records evidence and events, enforces human-in-the-loop (HITL) approvals, and produces traceable final reports.

---

## Key Features

- **LangGraph Single-Coordinator Orchestration**: Deterministic workflow state machine with explicit transitions and interrupts.
- **Deterministic Mock Mode**: 100% offline-verifiable operation without paid API keys.
- **Security-First Architecture**:
  - SSRF protection against private IP spaces, cloud metadata (169.254.169.254), and loopback.
  - Strict Pydantic v2 schemas around every model and tool boundary.
  - No arbitrary shell, SQL, or code execution.
- **Durable Run State**: Persistent checkpoints, event log, and evidence records stored in PostgreSQL.
- **Human-in-the-Loop (HITL)**: Consequential operations pause until explicitly reviewed and approved.
- **Traceable Reports**: Final markdown output with grounded citation evidence and execution audit trails.
- **Open Observability**: Structured JSON logging and OpenTelemetry tracing support.

---

## Quickstart (Local Development)

### 1. Prerequisites
- Python 3.10+
- Node.js 18+ (for frontend)
- Docker & Docker Compose (optional for full containerized stack)

### 2. Environment Setup

Clone the repository and prepare your virtual environment:

```bash
git clone https://github.com/your-username/agentops.git
cd agentops

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
```

### 3. Run Verification Tests & Linter

```bash
# Run test suite
pytest backend/tests

# Run ruff linter
ruff check .
```

### 4. Run Development API Server

```bash
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

Visit the interactive OpenAPI documentation at:
- `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/api/v1/health`

---

## Repository Structure

```
agentops/
├── backend/
│   ├── app/
│   │   ├── api/             # FastAPI routes & v1 router
│   │   ├── core/            # Configuration, logging, SSRF security
│   │   ├── domain/          # Pydantic schemas & data models
│   │   ├── orchestration/   # LangGraph coordinators & tools
│   │   ├── adapters/        # LLM & Search provider adapters (Mock/Live)
│   │   ├── db/              # Database models, sessions & migrations
│   │   ├── tasks/           # Celery background workers
│   │   └── main.py          # FastAPI application factory
│   └── tests/               # Unit and integration test suites
├── docs/                    # Architecture, security & specifications
├── frontend/                # Next.js web application (React, TypeScript)
├── docker/                  # Dockerfiles & container compose configs
├── .env.example             # Safe loopback configuration template
├── pyproject.toml           # Python package specifications & tool configs
└── README.md
```

---

## License

Apache-2.0
