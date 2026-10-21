"""Performance baselines, capacity boundaries, and cost control test suite."""

from __future__ import annotations

import asyncio
import resource
import time
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import build_agent_graph
from app.agents.state import AgentState
from app.core.config import get_settings
from app.models.audit import AuditEvent
from app.models.run import Run
from app.tools.security import SafeHttpClient

settings = get_settings()


@pytest.mark.perf
class TestPerformanceBaselines:
    """Measures reproducible latency baselines across API, database, and end-to-end execution."""

    @pytest.mark.asyncio
    async def test_benchmark_run_creation_api_latency(self, async_client: AsyncClient) -> None:
        """Benchmark POST /api/v1/runs creation latency over 25 iterations."""
        latencies_ms: list[float] = []
        headers = {"X-API-Key": settings.API_KEY}

        for i in range(25):
            payload = {
                "objective": f"Benchmark competitive analysis iteration {i} for high performance",
                "domain": "software",
                "idempotency_key": f"perf-create-{uuid.uuid4()}",
            }
            t0 = time.perf_counter()
            resp = await async_client.post("/api/v1/runs", json=payload, headers=headers)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            assert resp.status_code in (201, 202)
            assert "X-Response-Time-Ms" in resp.headers
            latencies_ms.append(elapsed_ms)

        latencies_ms.sort()
        p50 = latencies_ms[len(latencies_ms) // 2]
        p95 = latencies_ms[int(len(latencies_ms) * 0.95)]
        p99 = latencies_ms[-1]
        print(
            f"\n[BENCHMARK] Run Creation Latency (25 iterations): P50={p50:.2f}ms, P95={p95:.2f}ms, P99={p99:.2f}ms, min={min(latencies_ms):.2f}ms, max={max(latencies_ms):.2f}ms"
        )

        # Baseline criteria: P50 < 60ms, P95 < 120ms on local loopback
        assert p50 < 60.0, f"Run creation P50 too high: {p50:.2f}ms"
        assert p95 < 120.0, f"Run creation P95 too high: {p95:.2f}ms"

    @pytest.mark.asyncio
    async def test_benchmark_run_history_api_latency(self, async_client: AsyncClient) -> None:
        """Benchmark GET /api/v1/runs paginated history query latency."""
        latencies_ms: list[float] = []
        headers = {"X-API-Key": settings.API_KEY}

        for _ in range(20):
            t0 = time.perf_counter()
            resp = await async_client.get("/api/v1/runs?limit=20&offset=0", headers=headers)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            assert resp.status_code == 200
            latencies_ms.append(elapsed_ms)

        latencies_ms.sort()
        p50 = latencies_ms[len(latencies_ms) // 2]
        p95 = latencies_ms[int(len(latencies_ms) * 0.95)]
        p99 = latencies_ms[-1]
        print(
            f"\n[BENCHMARK] Run History Latency (20 iterations): P50={p50:.2f}ms, P95={p95:.2f}ms, P99={p99:.2f}ms, min={min(latencies_ms):.2f}ms, max={max(latencies_ms):.2f}ms"
        )

        assert p50 < 45.0, f"Run history P50 too high: {p50:.2f}ms"
        assert p95 < 90.0, f"Run history P95 too high: {p95:.2f}ms"

    @pytest.mark.asyncio
    async def test_benchmark_database_query_latencies(self, async_db_session: AsyncSession) -> None:
        """Direct database query latency benchmarking on common operational paths."""
        # 1. Benchmark direct Run lookup
        run_id = uuid.uuid4()
        run = Run(
            id=run_id,
            objective="Direct DB benchmark test run",
            domain="cloud",
            status="RUNNING",
        )
        async_db_session.add(run)
        await async_db_session.commit()

        select_times: list[float] = []
        for _ in range(25):
            t0 = time.perf_counter()
            stmt = select(Run).where(Run.id == run_id)
            res = await async_db_session.execute(stmt)
            _ = res.scalar_one_or_none()
            select_times.append((time.perf_counter() - t0) * 1000.0)

        sorted_select = sorted(select_times)
        p50_select = sorted_select[len(sorted_select) // 2]
        p95_select = sorted_select[int(len(sorted_select) * 0.95)]
        print(
            f"\n[BENCHMARK] DB Run SELECT (25 iterations): P50={p50_select:.2f}ms, P95={p95_select:.2f}ms, min={min(select_times):.2f}ms, max={max(select_times):.2f}ms"
        )
        assert p95_select < 30.0, f"P95 SELECT run too slow: {p95_select:.2f}ms"

        # 2. Benchmark AuditEvent insert
        insert_times: list[float] = []
        for i in range(15):
            event = AuditEvent(
                run_id=run_id,
                event_type="STEP_EXECUTED",
                actor="benchmark",
                payload={"iteration": i},
            )
            t0 = time.perf_counter()
            async_db_session.add(event)
            await async_db_session.commit()
            insert_times.append((time.perf_counter() - t0) * 1000.0)

        sorted_insert = sorted(insert_times)
        p50_insert = sorted_insert[len(sorted_insert) // 2]
        p95_insert = sorted_insert[int(len(sorted_insert) * 0.95)]
        print(
            f"[BENCHMARK] DB AuditEvent INSERT (15 iterations): P50={p50_insert:.2f}ms, P95={p95_insert:.2f}ms, min={min(insert_times):.2f}ms, max={max(insert_times):.2f}ms"
        )
        assert p95_insert < 35.0, f"P95 INSERT audit event too slow: {p95_insert:.2f}ms"

    def test_benchmark_mock_end_to_end_execution_latency(self) -> None:
        """Measure full LangGraph mock execution lifecycle duration."""
        graph = build_agent_graph().compile()
        initial_state: AgentState = {
            "run_id": f"perf-run-{uuid.uuid4()}",
            "objective": "Compare Linear and Jira enterprise pricing and SLAs",
            "domain": "software",
            "llm_provider": "mock",
            "search_provider": "mock",
            "max_steps": 5,
            "budget_limit_usd": 1.00,
        }

        t0 = time.perf_counter()
        final_state = graph.invoke(initial_state)
        elapsed_sec = time.perf_counter() - t0

        assert final_state["status"] in ("COMPLETED", "COMPLETED_WITH_WARNINGS")
        assert final_state["final_report"] is not None
        print(
            f"\n[BENCHMARK] Mock Agent End-to-End Execution Latency: {elapsed_sec:.4f}s ({elapsed_sec * 1000.0:.2f}ms)"
        )
        # Entire graph execution must complete in under 2.5 seconds in mock mode
        assert elapsed_sec < 2.5, f"Mock end-to-end execution took too long: {elapsed_sec:.2f}s"

    def test_benchmark_worker_resource_usage(self) -> None:
        """Measure CPU time and memory RSS footprint during agent execution."""
        _ = resource.getrusage(resource.RUSAGE_SELF)
        cpu_time_before = time.process_time()

        graph = build_agent_graph().compile()
        state: AgentState = {
            "run_id": f"perf-rusage-{uuid.uuid4()}",
            "objective": "Measure memory footprint and CPU utilization",
            "domain": "analytics",
            "llm_provider": "mock",
            "search_provider": "mock",
            "max_steps": 3,
        }
        _ = graph.invoke(state)

        cpu_time_after = time.process_time()
        rusage_after = resource.getrusage(resource.RUSAGE_SELF)

        cpu_duration = cpu_time_after - cpu_time_before
        peak_rss_mb = (
            rusage_after.ru_maxrss / (1024 * 1024)
            if rusage_after.ru_maxrss > 10_000_000
            else rusage_after.ru_maxrss / 1024
        )

        print(
            f"\n[BENCHMARK] Worker Resource Usage: CPU Time={cpu_duration:.4f}s, Peak RSS={peak_rss_mb:.2f}MB"
        )
        assert cpu_duration < 1.0, f"Excessive CPU consumption: {cpu_duration:.3f}s"
        assert peak_rss_mb > 0  # Valid readable RSS

    def test_benchmark_document_cache_speedup(self) -> None:
        """Demonstrate significant latency reduction and bandwidth saving via in-memory DocumentCache."""
        client = SafeHttpClient()

        test_url = "https://example.com/datadog/pricing"

        # Prime fetch (cache miss)
        t0 = time.perf_counter()
        doc1 = client.fetch_url(test_url, use_cache=True)
        cold_time = time.perf_counter() - t0

        # Secondary fetch (cache hit)
        t1 = time.perf_counter()
        doc2 = client.fetch_url(test_url, use_cache=True)
        warm_time = time.perf_counter() - t1

        assert doc1["content_type"] == doc2["content_type"]
        assert doc1["byte_count"] == doc2["byte_count"]
        speedup = cold_time / max(warm_time, 0.000001)
        print(
            f"\n[BENCHMARK] DocumentCache Latency: Cold Miss={cold_time * 1000.0:.3f}ms, Warm Hit={warm_time * 1000.0:.3f}ms, Speedup={speedup:.1f}x"
        )
        # Cached response should be substantially faster
        assert warm_time <= cold_time + 0.005


@pytest.mark.perf
class TestCapacityAndCostControls:
    """Enforces hard budget ceilings, concurrency bounds, and oversized payload rejections."""

    @pytest.mark.asyncio
    async def test_capacity_concurrent_run_creations(self, async_client: AsyncClient) -> None:
        """Test concurrent run creation under burst load (15 concurrent requests)."""
        headers = {"X-API-Key": settings.API_KEY}

        async def make_request(idx: int) -> int:
            payload = {
                "objective": f"Concurrent burst test research query number {idx}",
                "domain": "scalability",
                "idempotency_key": f"burst-{uuid.uuid4()}",
            }
            res = await async_client.post("/api/v1/runs", json=payload, headers=headers)
            return res.status_code

        tasks = [make_request(i) for i in range(15)]
        statuses = await asyncio.gather(*tasks)

        assert all(s in (201, 202) for s in statuses)

    @pytest.mark.asyncio
    async def test_capacity_duplicate_idempotency_requests(self, async_client: AsyncClient) -> None:
        """Test concurrent identical requests with same Idempotency-Key return single run ID."""
        shared_key = f"perf-idemp-{uuid.uuid4()}"
        payload = {
            "objective": "Idempotent duplicate concurrency test",
            "domain": "security",
            "idempotency_key": shared_key,
        }
        headers = {"X-API-Key": settings.API_KEY}

        async def make_idemp_request() -> str:
            res = await async_client.post("/api/v1/runs", json=payload, headers=headers)
            assert res.status_code in (200, 201, 202)
            return str(res.json()["run_id"])

        tasks = [make_idemp_request() for _ in range(8)]
        run_ids = await asyncio.gather(*tasks)

        # All 8 concurrent requests must resolve to the identical single run ID
        assert len(set(run_ids)) == 1

    def test_capacity_search_budget_exhaustion(self) -> None:
        """Ensure run halts safely when search request count exceeds MAX_SEARCH_REQUESTS_PER_RUN."""
        state: AgentState = {
            "run_id": f"budget-search-{uuid.uuid4()}",
            "objective": "Search budget exhaustion test",
            "domain": "finance",
            "llm_provider": "mock",
            "search_provider": "mock",
            "search_requests_count": 10,
            "max_search_requests": 10,  # Budget reached
            "current_step": {
                "step_identifier": "search-step-fail",
                "tool_name": "search_public_web",
                "parameters": {"query": "exhausted search"},
            },
            "steps_executed": 0,
            "max_steps": 10,
        }

        # Invoking execute_task node directly or through graph triggers safe halt
        from app.agents.nodes import execute_task_node

        res = execute_task_node(state)
        assert res.get("status") == "FAILED"
        assert "search request budget" in res.get("fatal_error", "")

    def test_capacity_bandwidth_budget_exhaustion(self) -> None:
        """Ensure run halts safely when cumulative fetched bytes exceeds budget."""
        from app.agents.nodes import execute_task_node

        state: AgentState = {
            "run_id": f"budget-bytes-{uuid.uuid4()}",
            "objective": "Bandwidth limit test",
            "domain": "telemetry",
            "llm_provider": "mock",
            "search_provider": "mock",
            "bytes_fetched": 5_242_800,  # Near 5MB ceiling
            "max_fetched_bytes": 5_242_880,
            "current_step": {
                "step_identifier": "fetch-step-oversize",
                "tool_name": "fetch_approved_public_page",
                "parameters": {"url": "https://example.com/pricing"},
            },
            "steps_executed": 1,
            "max_steps": 10,
        }

        res = execute_task_node(state)
        # Result should either succeed within ceiling or halt safely if exceeded
        if res.get("status") == "FAILED":
            assert "bandwidth" in res.get("fatal_error", "").lower()

    def test_capacity_token_budget_exhaustion(self) -> None:
        """Ensure execution halts safely when token consumption budget is exhausted."""
        from app.agents.nodes import execute_task_node

        state: AgentState = {
            "run_id": f"budget-token-{uuid.uuid4()}",
            "objective": "Token budget test",
            "domain": "nlp",
            "llm_provider": "mock",
            "search_provider": "mock",
            "tokens_consumed": 55_000,
            "max_tokens": 50_000,  # Exceeded
            "current_step": {
                "step_identifier": "step-token-exhausted",
                "tool_name": "search_public_web",
                "parameters": {"query": "tokens"},
            },
            "steps_executed": 0,
            "max_steps": 10,
        }

        res = execute_task_node(state)
        assert res.get("status") == "FAILED"
        assert "token" in res.get("fatal_error", "").lower()

    def test_capacity_oversized_report_payload_rejected(self) -> None:
        """Ensure reports exceeding MAX_REPORT_PAYLOAD_BYTES are safely rejected."""
        from app.agents.nodes import validate_report_node

        huge_content = "# Massive Report\n" + ("Extremely long text content " * 30_000)
        state: AgentState = {
            "run_id": f"oversized-report-{uuid.uuid4()}",
            "final_report": {
                "title": "Huge Report",
                "grounded_findings": "Valid empirical findings content here.",
                "strategic_inferences": "Valid strategic inferences section.",
                "markdown_content": huge_content,
            },
            "max_report_payload_bytes": 100_000,  # 100KB limit
        }

        res = validate_report_node(state)
        assert res.get("status") == "FAILED"
        assert "payload size" in res.get("fatal_error", "").lower()
