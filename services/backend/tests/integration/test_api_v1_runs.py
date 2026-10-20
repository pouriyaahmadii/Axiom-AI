"""Integration tests for research run management API endpoints (/api/v1/runs)."""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.models import Report, Run, RunStep


@pytest.mark.integration
async def test_create_run_accepted(async_client: AsyncClient):
    """Verify POST /api/v1/runs returns 202 Accepted, creates run, and attaches correlation ID."""
    payload = {
        "objective": "Analyze top 3 AI developer tooling vendors in North America",
        "domain": "devtools",
        "geography": "North America",
    }
    response = await async_client.post("/api/v1/runs", json=payload)
    assert response.status_code == 202

    data = response.json()
    assert "run_id" in data
    assert data["status"] == "QUEUED"
    assert "created_at" in data
    assert "X-Correlation-ID" in response.headers


@pytest.mark.integration
async def test_create_run_idempotency(async_client: AsyncClient):
    """Verify idempotency key prevents duplicate run creation and rejects conflicting objectives."""
    idempotency_key = f"idem-{uuid.uuid4()}"
    payload = {
        "objective": "Analyze vector database market share",
        "domain": "database",
        "idempotency_key": idempotency_key,
    }

    # 1. First submission
    res1 = await async_client.post("/api/v1/runs", json=payload)
    assert res1.status_code == 202
    run_id_1 = res1.json()["run_id"]

    # 2. Second submission with identical payload should replay identical run_id
    res2 = await async_client.post("/api/v1/runs", json=payload)
    assert res2.status_code == 202
    run_id_2 = res2.json()["run_id"]
    assert run_id_1 == run_id_2

    # 3. Third submission with same idempotency key but different objective should fail with 409 Conflict
    conflict_payload = {
        "objective": "Conflicting objective using same idempotency key",
        "domain": "database",
        "idempotency_key": idempotency_key,
    }
    res3 = await async_client.post("/api/v1/runs", json=conflict_payload)
    assert res3.status_code == 409
    assert res3.json()["error"]["code"] == "CONFLICT"


@pytest.mark.integration
async def test_create_run_validation_errors(async_client: AsyncClient):
    """Verify input size bounds and schema validation enforcement."""
    # Objective too short (< 10 chars)
    res_short = await async_client.post(
        "/api/v1/runs", json={"objective": "Short", "domain": "tech"}
    )
    assert res_short.status_code == 422
    assert res_short.json()["error"]["code"] == "VALIDATION_ERROR"

    # Missing domain
    res_missing = await async_client.post(
        "/api/v1/runs", json={"objective": "Valid long objective exceeding ten characters"}
    )
    assert res_missing.status_code == 422

    # Forbidden extra field
    res_extra = await async_client.post(
        "/api/v1/runs",
        json={
            "objective": "Valid long objective exceeding ten characters",
            "domain": "tech",
            "unexpected_field": "disallowed",
        },
    )
    assert res_extra.status_code == 422


@pytest.mark.integration
async def test_get_run_detail(async_client: AsyncClient):
    """Verify GET /api/v1/runs/{id} returns full state and returns 404 for unknown run."""
    # 1. Unknown UUID
    unknown_id = str(uuid.uuid4())
    res_404 = await async_client.get(f"/api/v1/runs/{unknown_id}")
    assert res_404.status_code == 404
    assert res_404.json()["error"]["code"] == "NOT_FOUND"

    # 2. Create and retrieve valid run
    create_res = await async_client.post(
        "/api/v1/runs",
        json={
            "objective": "Detailed state inspection run",
            "domain": "security",
        },
    )
    run_id = create_res.json()["run_id"]

    detail_res = await async_client.get(f"/api/v1/runs/{run_id}")
    assert detail_res.status_code == 200
    data = detail_res.json()
    assert data["run_id"] == run_id
    assert data["objective"] == "Detailed state inspection run"
    assert data["domain"] == "security"
    assert data["status"] == "QUEUED"
    assert data["llm_provider"] == "mock"
    assert Decimal(str(data["budget_usd_limit"])) == Decimal("1.0000")


@pytest.mark.integration
async def test_list_runs_pagination_and_filters(async_client: AsyncClient):
    """Verify paginated run listing and status filtering."""
    for i in range(3):
        await async_client.post(
            "/api/v1/runs",
            json={"objective": f"Pagination test run number {i + 1}", "domain": "fintech"},
        )

    # List with limit 2
    res_page = await async_client.get("/api/v1/runs?limit=2&offset=0")
    assert res_page.status_code == 200
    page_data = res_page.json()
    assert len(page_data["items"]) == 2
    assert page_data["total"] >= 3
    assert page_data["limit"] == 2
    assert page_data["offset"] == 0

    # Filter by status
    res_filtered = await async_client.get("/api/v1/runs?status=QUEUED")
    assert res_filtered.status_code == 200
    for item in res_filtered.json()["items"]:
        assert item["status"] == "QUEUED"


@pytest.mark.integration
async def test_get_run_steps(async_client: AsyncClient, async_db_session):
    """Verify retrieving sequential execution plan steps for a run."""
    # Create run and add steps directly in DB
    run = Run(objective="Steps inspection run", domain="qa")
    async_db_session.add(run)
    await async_db_session.commit()

    step1 = RunStep(
        run_id=run.id,
        step_index=0,
        step_identifier="step_search",
        title="Search Market Leaders",
        tool_name="web_search",
        parameters={"query": "agent ops platforms"},
    )
    step2 = RunStep(
        run_id=run.id,
        step_index=1,
        step_identifier="step_extract",
        title="Extract Metrics",
        tool_name="fetch_document",
        parameters={"url": "https://example.com"},
    )
    async_db_session.add_all([step1, step2])
    await async_db_session.commit()

    response = await async_client.get(f"/api/v1/runs/{run.id}/steps")
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == str(run.id)
    assert len(data["items"]) == 2
    assert data["items"][0]["step_identifier"] == "step_search"
    assert data["items"][1]["step_identifier"] == "step_extract"


@pytest.mark.integration
async def test_get_run_events(async_client: AsyncClient):
    """Verify retrieving audit events for a run."""
    create_res = await async_client.post(
        "/api/v1/runs",
        json={"objective": "Audit events inspection run", "domain": "compliance"},
    )
    run_id = create_res.json()["run_id"]

    response = await async_client.get(f"/api/v1/runs/{run_id}/events")
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == run_id
    assert len(data["items"]) >= 1
    assert data["items"][0]["event_type"] == "RUN_QUEUED"


@pytest.mark.integration
async def test_cancel_run_and_state_transitions(async_client: AsyncClient):
    """Verify cancelling an active run and rejecting cancellation of already terminal runs."""
    create_res = await async_client.post(
        "/api/v1/runs",
        json={"objective": "Cancellation test run", "domain": "testing"},
    )
    run_id = create_res.json()["run_id"]

    # 1. Cancel active run
    cancel_res = await async_client.post(f"/api/v1/runs/{run_id}/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"

    # 2. Attempt to cancel already cancelled run should fail with 409 Conflict
    re_cancel_res = await async_client.post(f"/api/v1/runs/{run_id}/cancel")
    assert re_cancel_res.status_code == 409
    assert re_cancel_res.json()["error"]["code"] == "INVALID_STATE_TRANSITION"


@pytest.mark.integration
async def test_get_run_report(async_client: AsyncClient, async_db_session):
    """Verify retrieving synthesized report and 404 when report has not been generated."""
    run = Run(objective="Report retrieval run", domain="analytics")
    async_db_session.add(run)
    await async_db_session.commit()

    # 1. Report not yet created -> 404
    res_404 = await async_client.get(f"/api/v1/runs/{run.id}/report")
    assert res_404.status_code == 404
    assert res_404.json()["error"]["code"] == "NOT_FOUND"

    # 2. Add report to database
    report = Report(
        run_id=run.id,
        title="Final Research Report",
        markdown_content="# Report\n\nContent with citations.",
        executive_summary="Summary of research.",
        citations=[{"marker": "[^1]", "evidence_id": "ev-01"}],
    )
    async_db_session.add(report)
    await async_db_session.commit()

    # 3. Retrieve report -> 200
    res_200 = await async_client.get(f"/api/v1/runs/{run.id}/report")
    assert res_200.status_code == 200
    report_data = res_200.json()
    assert report_data["title"] == "Final Research Report"
    assert report_data["citations"][0]["marker"] == "[^1]"
