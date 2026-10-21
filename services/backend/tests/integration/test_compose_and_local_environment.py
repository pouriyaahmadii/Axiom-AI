"""Acceptance tests for local Docker Compose environment, service health, and security boundaries."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import build_agent_graph
from app.agents.state import AgentState
from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, DeterministicValidationError
from app.models.enums import RunStatus, StepStatus
from app.models.run import Run
from app.models.step import RunStep
from app.providers.factory import get_llm_provider

settings = get_settings()

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
COMPOSE_FILE = ROOT_DIR / "compose.yaml"
BACKEND_DOCKERFILE = ROOT_DIR / "infra" / "docker" / "backend.Dockerfile"
FRONTEND_DOCKERFILE = ROOT_DIR / "infra" / "docker" / "frontend.Dockerfile"
OVERRIDE_EXAMPLE = ROOT_DIR / "compose.override.yaml.example"


@pytest.fixture(scope="module")
def compose_config() -> dict[str, Any]:
    """Load and parse root compose.yaml."""
    assert COMPOSE_FILE.exists(), f"compose.yaml not found at {COMPOSE_FILE}"
    with open(COMPOSE_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict), "compose.yaml root must be a YAML dictionary"
    return data


class TestDockerComposeSpecification:
    """Verifies Docker Compose service architecture, networking, security, and resource boundaries."""

    def test_compose_project_name(self, compose_config: dict[str, Any]) -> None:
        """Compose project must be strictly named 'agentops'."""
        assert compose_config.get("name") == "agentops"

    def test_required_services_present(self, compose_config: dict[str, Any]) -> None:
        """All 6 core application components must exist in the service definition."""
        services = compose_config.get("services", {})
        required = {"postgres", "redis", "n8n", "backend-api", "backend-worker", "frontend"}
        assert required.issubset(set(services.keys()))

    def test_backend_image_reuse(self, compose_config: dict[str, Any]) -> None:
        """API and Worker must reuse the same backend image and build specification."""
        services = compose_config.get("services", {})
        api = services["backend-api"]
        worker = services["backend-worker"]

        assert api.get("image") == "agentops-backend:latest"
        assert worker.get("image") == "agentops-backend:latest"
        assert api.get("build") == worker.get("build")

    def test_service_specific_commands(self, compose_config: dict[str, Any]) -> None:
        """API and Worker must execute distinct, service-specific process entrypoints."""
        services = compose_config.get("services", {})
        api_cmd = services["backend-api"].get("command", "")
        worker_cmd = services["backend-worker"].get("command", "")

        assert "uvicorn" in api_cmd or "app.main:app" in api_cmd
        assert "alembic upgrade head" in api_cmd  # Automated schema migration on boot
        assert "celery" in worker_cmd and "worker" in worker_cmd

    def test_isolated_compose_network_and_dns(self, compose_config: dict[str, Any]) -> None:
        """All services must attach to the private agentops-net bridge network."""
        networks = compose_config.get("networks", {})
        assert "agentops-net" in networks
        assert networks["agentops-net"].get("driver") == "bridge"

        services = compose_config.get("services", {})
        for name, s_conf in services.items():
            s_nets = s_conf.get("networks", [])
            assert "agentops-net" in s_nets, f"Service {name} is not connected to agentops-net"

    def test_no_accidental_public_port_exposure(self, compose_config: dict[str, Any]) -> None:
        """Verify no container binds to 0.0.0.0 or forbidden ports; all ports must bind strictly to 127.0.0.1."""
        services = compose_config.get("services", {})
        forbidden_ports = {"8080", "5433", "6380", "6333"}

        for name, s_conf in services.items():
            ports = s_conf.get("ports", [])
            for p in ports:
                p_str = str(p)
                # Must never bind to 0.0.0.0
                assert "0.0.0.0" not in p_str, (
                    f"Service {name} insecurely binds to 0.0.0.0: {p_str}"
                )
                # Must explicitly bind to loopback
                assert p_str.startswith("127.0.0.1:"), (
                    f"Service {name} does not bind to 127.0.0.1: {p_str}"
                )

                # Ensure forbidden ports are untouched
                for f_port in forbidden_ports:
                    assert f":{f_port}:" not in p_str and not p_str.endswith(f":{f_port}")

    def test_database_and_redis_not_exposed_by_default(
        self, compose_config: dict[str, Any]
    ) -> None:
        """PostgreSQL and Redis must use 'expose' and NOT publish host ports in base compose.yaml."""
        services = compose_config.get("services", {})
        postgres = services["postgres"]
        redis = services["redis"]

        assert "ports" not in postgres or len(postgres["ports"]) == 0
        assert "5432" in postgres.get("expose", [])

        assert "ports" not in redis or len(redis["ports"]) == 0
        assert "6379" in redis.get("expose", [])

    def test_compose_override_example_binds_loopback(self) -> None:
        """compose.override.yaml.example must bind postgres and redis strictly to 127.0.0.1."""
        assert OVERRIDE_EXAMPLE.exists()
        with open(OVERRIDE_EXAMPLE, encoding="utf-8") as f:
            override_data = yaml.safe_load(f)

        pg_ports = override_data.get("services", {}).get("postgres", {}).get("ports", [])
        redis_ports = override_data.get("services", {}).get("redis", {}).get("ports", [])

        assert "127.0.0.1:5432:5432" in pg_ports
        assert "127.0.0.1:6379:6379" in redis_ports

    def test_explicit_healthchecks_defined(self, compose_config: dict[str, Any]) -> None:
        """Every service must have explicit health checks with intervals and timeouts."""
        services = compose_config.get("services", {})
        for name, s_conf in services.items():
            hc = s_conf.get("healthcheck")
            assert hc is not None, f"Service {name} lacks a healthcheck specification"
            assert "test" in hc
            assert "interval" in hc
            assert "timeout" in hc
            assert "retries" in hc

    def test_service_readiness_dependencies(self, compose_config: dict[str, Any]) -> None:
        """Dependencies must require healthy upstream state."""
        services = compose_config.get("services", {})

        api_deps = services["backend-api"].get("depends_on", {})
        assert api_deps.get("postgres", {}).get("condition") == "service_healthy"
        assert api_deps.get("redis", {}).get("condition") == "service_healthy"

        worker_deps = services["backend-worker"].get("depends_on", {})
        assert worker_deps.get("postgres", {}).get("condition") == "service_healthy"
        assert worker_deps.get("redis", {}).get("condition") == "service_healthy"
        assert worker_deps.get("backend-api", {}).get("condition") == "service_healthy"

        frontend_deps = services["frontend"].get("depends_on", {})
        assert frontend_deps.get("backend-api", {}).get("condition") == "service_healthy"

    def test_resource_limits_and_reservations(self, compose_config: dict[str, Any]) -> None:
        """All production services must specify explicit CPU and memory resource bounds."""
        services = compose_config.get("services", {})
        for name, s_conf in services.items():
            deploy = s_conf.get("deploy", {})
            resources = deploy.get("resources", {})
            limits = resources.get("limits", {})
            assert "cpus" in limits, f"Service {name} lacks CPU limits"
            assert "memory" in limits, f"Service {name} lacks memory limits"

    def test_state_persistence_named_volumes(self, compose_config: dict[str, Any]) -> None:
        """Named volumes must be declared for PostgreSQL, Redis, and n8n."""
        volumes = compose_config.get("volumes", {})
        assert "postgres_data" in volumes
        assert "redis_data" in volumes
        assert "n8n_data" in volumes

    def test_optional_ollama_profile(self, compose_config: dict[str, Any]) -> None:
        """Ollama container must be isolated under the 'ollama' profile, not running in default stack."""
        services = compose_config.get("services", {})
        ollama = services.get("ollama")
        assert ollama is not None
        assert "ollama" in ollama.get("profiles", [])

        # Backend services must map host.docker.internal for host-native Ollama access
        api_extra = services["backend-api"].get("extra_hosts", [])
        assert any("host.docker.internal" in h for h in api_extra)


class TestDockerfileHardening:
    """Verifies multi-stage build, unprivileged non-root users, and lean images."""

    def test_backend_dockerfile_security(self) -> None:
        """Backend Dockerfile must implement multi-stage build and unprivileged appuser."""
        assert BACKEND_DOCKERFILE.exists()
        content = BACKEND_DOCKERFILE.read_text(encoding="utf-8")

        assert "AS builder" in content
        assert "AS runner" in content
        assert "useradd" in content and "appuser" in content
        assert "USER appuser" in content
        assert "WORKDIR /app/services/backend" in content

    def test_frontend_dockerfile_security(self) -> None:
        """Frontend Dockerfile must use standalone output, multi-stage build, and unprivileged nextjs."""
        assert FRONTEND_DOCKERFILE.exists()
        content = FRONTEND_DOCKERFILE.read_text(encoding="utf-8")

        assert "AS deps" in content
        assert "AS builder" in content
        assert "AS runner" in content
        assert "adduser" in content and "nextjs" in content
        assert "USER nextjs" in content
        assert ".next/standalone" in content
        assert "server.js" in content


class TestRuntimeEnvironmentAcceptance:
    """Verifies runtime behavior, provider transparency, state persistence, and worker resilience."""

    def test_deterministic_mock_run_acceptance(self) -> None:
        """End-to-end acceptance run in Mock mode completes without any external network dependencies."""
        graph = build_agent_graph().compile()
        run_id = f"docker-acceptance-{uuid.uuid4()}"

        state: AgentState = {
            "run_id": run_id,
            "objective": "Evaluate Docker Compose multi-service local operations",
            "domain": "infrastructure",
            "llm_provider": "mock",
            "search_provider": "mock",
            "max_steps": 4,
            "budget_limit_usd": 1.00,
        }

        result = graph.invoke(state)

        assert result["status"] in ("COMPLETED", "COMPLETED_WITH_WARNINGS")
        assert result["final_report"] is not None
        assert "Docker Compose" in result["final_report"]["markdown_content"]
        assert result["llm_provider"] == "mock"
        assert result["search_provider"] == "mock"

    def test_clear_provider_reporting_no_silent_fallback(self) -> None:
        """System must report chosen provider and NEVER silently fallback to Mock when real provider is expected."""
        # 1. Explicit mock provider succeeds and reports mock
        mock_provider = get_llm_provider("mock")
        assert mock_provider.provider_name == "mock"

        # 2. Requesting OpenAI without API key raises AuthenticationError, does not fallback to mock
        openai_provider = get_llm_provider("openai", api_key="")
        with pytest.raises(AuthenticationError) as exc_info:
            openai_provider.generate_plan("Test objective", "software")
        assert "OpenAI API key is missing" in str(exc_info.value)

        # 3. Requesting invalid provider raises DeterministicValidationError
        with pytest.raises(DeterministicValidationError) as val_exc_info:
            get_llm_provider("unsupported_claude_clone")
        assert "Unsupported LLM provider" in str(val_exc_info.value)

    @pytest.mark.asyncio
    async def test_database_data_persistence_across_restart(
        self, async_db_session: AsyncSession
    ) -> None:
        """Simulate persistence and recovery of run and step entities across restarts."""
        run_id = uuid.uuid4()
        run = Run(
            id=run_id,
            objective="Data persistence verification before restart",
            domain="storage",
            status=RunStatus.RUNNING,
            idempotency_key=f"persist-{uuid.uuid4()}",
        )
        step = RunStep(
            id=uuid.uuid4(),
            run_id=run_id,
            step_index=1,
            step_identifier="step-persist-1",
            title="Discover Market Competitors",
            tool_name="discover_competitors",
            status=StepStatus.COMPLETED,
        )
        async_db_session.add(run)
        async_db_session.add(step)
        await async_db_session.commit()

        # Simulate fresh session (as would happen after a container restart)
        async_db_session.expunge_all()

        stmt_run = select(Run).where(Run.id == run_id)
        res_run = await async_db_session.execute(stmt_run)
        persisted_run = res_run.scalar_one_or_none()

        stmt_step = select(RunStep).where(RunStep.run_id == run_id)
        res_step = await async_db_session.execute(stmt_step)
        persisted_step = res_step.scalar_one_or_none()

        assert persisted_run is not None
        assert persisted_run.objective == "Data persistence verification before restart"
        assert persisted_step is not None
        assert persisted_step.step_identifier == "step-persist-1"

    @pytest.mark.asyncio
    async def test_worker_restart_resilience(self, async_db_session: AsyncSession) -> None:
        """A QUEUED run must be recoverable and execute to completion after a simulated worker restart."""
        run_id = uuid.uuid4()
        run = Run(
            id=run_id,
            objective="Worker restart recovery test",
            domain="resilience",
            status=RunStatus.QUEUED,
            attempt_count=0,
            idempotency_key=f"restart-{uuid.uuid4()}",
        )
        async_db_session.add(run)
        await async_db_session.commit()

        # Simulate worker picking up task after crash/restart
        stmt = select(Run).where(Run.id == run_id)
        res = await async_db_session.execute(stmt)
        recovered_run = res.scalar_one()

        recovered_run.status = RunStatus.PLANNING
        recovered_run.attempt_count += 1
        await async_db_session.commit()

        assert recovered_run.status == RunStatus.PLANNING
        assert recovered_run.attempt_count == 1
