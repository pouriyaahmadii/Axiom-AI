# Dependency Management & Governance Policy: AgentOps

## 1. Purpose & Core Principles

This policy governs dependency selection, pinning standards, update cadences, and license compliance across the AgentOps platform. As an auditable, production-grade system, AgentOps enforces strict dependency discipline:

1. **Determinism**: Builds must be bit-for-bit reproducible across developer machines, Docker environments, and CI runners.
2. **Zero Floating Tags**: Container images must specify exact patch/minor version tags; floating tags (`:latest`, `:alpine`, `:bookworm`) are strictly prohibited in deployment manifests.
3. **Single Tooling Authority**: Exactly one package management system is authorized per runtime tier (Python: `pip` + `pyproject.toml`; Frontend: `npm` + `package-lock.json`). Competing or mixed tools (e.g., mixing `pip` with `poetry`, or `npm` with `yarn`/`pnpm`) are forbidden.
4. **Permissive Licensing Only**: All direct dependencies must use permissive open-source licenses. Copyleft licenses (GPL, AGPL) are prohibited in application runtime graphs.
5. **Least Dependency Principle**: No external package may be added if the capability is readily achieved using standard library primitives with low maintenance overhead.

---

## 2. Package Management Governance

### 2.1 Python Service Tier (`services/backend`)
- **Specification**: Dependencies are declared in [`pyproject.toml`](file:///Users/macbook/Downloads/Github_repo/agentops/pyproject.toml) using PEP 621 metadata standards.
- **Pinning Strategy**:
  - Core runtime libraries specify semantic compatibility bounds: `package>=X.Y.Z,<(X+1).0.0` to permit non-breaking security patches while locking against major breaking changes.
  - Development tools (`pytest`, `ruff`, `mypy`) specify pinned minor bounds.
- **Lockfile Enforcement**: Production and CI container builds install via a verified lockfile (`requirements.lock` generated via `pip-compile` / `pip freeze`).
- **Standard Toolchain**: Standard virtual environment (`.venv`) managed via Python's built-in `venv` module and standard `pip`.

### 2.2 Frontend Application Tier (`apps/web`)
- **Specification**: Declared in `apps/web/package.json`.
- **Lockfile Enforcement**: Dependencies are locked via `package-lock.json` and installed exclusively via `npm ci` in Docker and CI environments.
- **Package Manager Choice**: Standard `npm` (v10+). Yarn and pnpm are excluded to eliminate multiple lockfile formats in the repository.

---

## 3. Container Image Pinning Standards

All base images in Dockerfiles and all service images in [`compose.yaml`](file:///Users/macbook/Downloads/Github_repo/agentops/compose.yaml) must adhere to exact tag pinning:

| Service / Layer | Image Reference | Pinning Policy | Justification |
| :--- | :--- | :--- | :--- |
| **PostgreSQL Database** | `postgres:16.4-alpine` | Exact Minor + OS Tag | Prevents unexpected major PostgreSQL migrations or breaking storage format updates. |
| **Redis Broker** | `redis:7.2.6-alpine` | Exact Patch + OS Tag | Guarantees stable eviction, pub/sub, and protocol behavior. |
| **n8n Community** | `n8nio/n8n:1.70.0` | Exact Release Tag | Eliminates automated schema or workflow node deprecations. |
| **Backend Base Image** | `python:3.10.15-slim-bookworm` | Exact Patch + Distro | Ensures reproducible C-libraries (`libc`, `libpq`) and OpenSSL versions. |
| **Frontend Base Image** | `node:20.18.0-alpine3.20` | Exact Patch + Alpine | Ensures stable V8 engine and node runtime behavior. |

---

## 4. License Compliance Policy

AgentOps enforces strict license scanning to safeguard against proprietary contamination or restrictive viral copyleft obligations:

### 4.1 Permitted License Categories
- **MIT License**
- **Apache License 2.0**
- **BSD 2-Clause & 3-Clause**
- **ISC License**
- **Python Software Foundation (PSF) License**

### 4.2 Prohibited License Categories
- **GNU General Public License (GPL v2 / GPL v3)**
- **GNU Affero General Public License (AGPL v3)**
- **Server Side Public License (SSPL)**
- **Commons Clause / Non-Commercial Restrictions**

### 4.3 Automated Verification
- Automated scans using `pip-licenses` verify that 100% of transitive Python runtime dependencies fall under permitted licenses prior to release.

---

## 5. Security Vulnerability Scanning & Update Cadence

1. **Static Dependency Audit**: Weekly automated scans via GitHub Dependabot and local `pip-audit`.
2. **Patch Cadence**:
   - *Critical / High CVEs*: Patched within 72 hours of upstream release.
   - *Medium / Low CVEs*: Evaluated and integrated during bi-weekly maintenance windows.
3. **Container Image Scanning**: `trivy` or `docker scout` scans on base images to ensure zero unpatched OS-level vulnerabilities.
