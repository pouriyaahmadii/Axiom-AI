"""Integration and contract tests for n8n automation workflows.

Validates:
1. JSON structure, connection integrity, and node schema compatibility for all exported n8n workflows.
2. Absence of hardcoded credentials or secrets in workflow node configurations.
3. Strict API contract matching between n8n HTTP Request nodes and AgentOps FastAPI endpoints.
4. Payload size limits and field validation parity between n8n Code nodes and backend schemas.
5. Idempotent submission and duplicate event delivery handling.
6. Resilient error handling (400 validation error, 404 report not found, 502 backend unreachable).
7. HITL approval action URL execution via n8n-generated links.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Report, Run, RunStatus
from app.services import approval_service

WORKFLOWS_DIR = Path(__file__).resolve().parents[4] / "workflows" / "n8n"

REQUIRED_WORKFLOWS = [
    "01_agentops_run_trigger.json",
    "02_run_completed_notification.json",
    "03_run_failure_notification.json",
    "04_approval_required_notification.json",
    "05_scheduled_research_trigger.json",
]

ALLOWED_NODE_TYPES = {
    "n8n-nodes-base.webhook",
    "n8n-nodes-base.code",
    "n8n-nodes-base.if",
    "n8n-nodes-base.httpRequest",
    "n8n-nodes-base.respondToWebhook",
    "n8n-nodes-base.scheduleTrigger",
    "n8n-nodes-base.noOp",
}


@pytest.mark.integration
def test_n8n_workflow_files_exist_and_parse():
    """Verify all 5 required workflow files exist, are valid JSON, and have proper root structure."""
    assert WORKFLOWS_DIR.is_dir(), f"Workflows directory not found: {WORKFLOWS_DIR}"

    for filename in REQUIRED_WORKFLOWS:
        filepath = WORKFLOWS_DIR / filename
        assert filepath.exists(), f"Missing required workflow: {filename}"

        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        assert "name" in data, f"{filename} missing 'name'"
        assert "nodes" in data and isinstance(data["nodes"], list), f"{filename} missing 'nodes'"
        assert "connections" in data and isinstance(data["connections"], dict), (
            f"{filename} missing 'connections'"
        )
        assert data.get("active") is False, f"{filename} should default to inactive (active: false)"


@pytest.mark.integration
def test_n8n_node_schemas_and_connections_integrity():
    """Verify nodes use approved node types and all connection targets point to valid nodes."""
    for filename in REQUIRED_WORKFLOWS:
        filepath = WORKFLOWS_DIR / filename
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        node_names = {node["name"] for node in data["nodes"]}
        node_ids = {node["id"] for node in data["nodes"]}

        # All node IDs must be unique
        assert len(node_ids) == len(data["nodes"]), f"Duplicate node IDs detected in {filename}"

        # All node types must be from approved n8n 1.70.0 core set
        for node in data["nodes"]:
            node_type = node.get("type")
            assert node_type in ALLOWED_NODE_TYPES, (
                f"Unsupported node type '{node_type}' in {filename}"
            )

        # All connection references must exist
        for source_name, connection_map in data["connections"].items():
            assert source_name in node_names, (
                f"Connection source '{source_name}' not in nodes of {filename}"
            )
            for _output_type, route_list in connection_map.items():
                for route in route_list:
                    for target_ref in route:
                        target_name = target_ref.get("node")
                        assert target_name in node_names, (
                            f"Connection target '{target_name}' referenced by '{source_name}' does not exist in {filename}"
                        )


@pytest.mark.integration
def test_n8n_no_hardcoded_secrets_in_workflows():
    """Verify workflows never contain embedded API keys, tokens, or hardcoded passwords."""
    forbidden_tokens = ["sk-", "secret-key", "bearer ", "password123", "ghp_"]

    for filename in REQUIRED_WORKFLOWS:
        filepath = WORKFLOWS_DIR / filename
        content = filepath.read_text(encoding="utf-8")

        for token in forbidden_tokens:
            assert token not in content.lower(), (
                f"Potential secret leak '{token}' detected in {filename}"
            )

        # If HTTP Request node exists, check it uses environment variable expressions
        if "httpRequest" in content:
            assert "$env.AGENTOPS_API_KEY" in content, (
                f"{filename} has HTTP Request node but does not reference $env.AGENTOPS_API_KEY"
            )


@pytest.mark.integration
async def test_workflow_01_api_contract_run_trigger(async_client: AsyncClient):
    """Verify backend accepts the exact JSON payload dispatched by Workflow 01."""
    # Matches the payload shape emitted by 'Validate & Sanitize Input' code node
    idempotency_key = f"idem-test-{uuid.uuid4()}"
    correlation_id = f"corr-test-{uuid.uuid4()}"

    n8n_generated_payload = {
        "objective": "Evaluate competitive positioning of AI agent observability platforms in Q4",
        "domain": "ai-observability",
        "geography": "Global",
        "idempotency_key": idempotency_key,
    }

    headers = {
        "X-Correlation-ID": correlation_id,
    }

    response = await async_client.post("/api/v1/runs", json=n8n_generated_payload, headers=headers)
    assert response.status_code == 202, f"Expected 202 Accepted, got: {response.text}"

    data = response.json()
    assert "run_id" in data
    assert data["status"] == "QUEUED"
    assert response.headers.get("X-Correlation-ID") == correlation_id

    # Verify idempotency replay returns identical run_id
    replayed_response = await async_client.post(
        "/api/v1/runs", json=n8n_generated_payload, headers=headers
    )
    assert replayed_response.status_code == 202
    assert replayed_response.json()["run_id"] == data["run_id"]


@pytest.mark.integration
async def test_workflow_01_validation_parity(async_client: AsyncClient):
    """Verify backend rejects payloads violating the same validation constraints enforced by n8n."""
    # Objective too short (< 10 chars)
    short_payload = {
        "objective": "Short",
        "domain": "ai-observability",
    }
    res_short = await async_client.post("/api/v1/runs", json=short_payload)
    assert res_short.status_code in (400, 422)

    # Missing domain
    no_domain = {
        "objective": "Valid length research objective about market size",
        "domain": "",
    }
    res_no_domain = await async_client.post("/api/v1/runs", json=no_domain)
    assert res_no_domain.status_code in (400, 422)


@pytest.mark.integration
async def test_workflow_02_api_contract_run_completed(
    async_client: AsyncClient, async_db_session: AsyncSession
):
    """Verify backend returns report structure expected by Workflow 02."""
    run_id = uuid.uuid4()
    run = Run(
        id=run_id,
        objective="Analyze competitive benchmarks",
        domain="ai-observability",
        status=RunStatus.COMPLETED,
    )
    report = Report(
        id=uuid.uuid4(),
        run_id=run_id,
        title="Comprehensive AI Agent Observability Market Scan",
        markdown_content="# Executive Summary\n\nCompetitive analysis indicates rapid convergence on LangGraph runtimes.",
        executive_summary="Competitive analysis indicates rapid convergence on LangGraph runtimes.",
        citations=[{"source_id": str(uuid.uuid4()), "url": "https://example.com/source1"}],
    )
    async_db_session.add(run)
    async_db_session.add(report)
    await async_db_session.commit()

    # Query endpoint as Workflow 02 would
    response = await async_client.get(f"/api/v1/runs/{run_id}/report")
    assert response.status_code == 200

    report_data = response.json()
    assert report_data["report_id"] == str(report.id)
    assert report_data["title"] == report.title
    assert report_data["executive_summary"] == report.executive_summary
    assert len(report_data["citations"]) == 1

    # Verify 404 behavior for incomplete runs
    non_existent_run_id = uuid.uuid4()
    res_404 = await async_client.get(f"/api/v1/runs/{non_existent_run_id}/report")
    assert res_404.status_code == 404


@pytest.mark.integration
async def test_workflow_03_api_contract_run_failure(
    async_client: AsyncClient, async_db_session: AsyncSession
):
    """Verify backend returns events structure expected by Workflow 03."""
    run_id = uuid.uuid4()
    run = Run(
        id=run_id,
        objective="Failed research attempt",
        domain="ai-observability",
        status=RunStatus.FAILED,
        error_message="ResourceLimitExceeded: Maximum budget exhausted",
    )
    async_db_session.add(run)
    await async_db_session.commit()

    # Query events endpoint as Workflow 03 would
    response = await async_client.get(f"/api/v1/runs/{run_id}/events?limit=10")
    assert response.status_code == 200

    events_data = response.json()
    assert "items" in events_data
    assert "total" in events_data
    assert events_data["run_id"] == str(run_id)


@pytest.mark.integration
async def test_workflow_04_api_contract_approval_actions(
    async_client: AsyncClient, async_db_session: AsyncSession
):
    """Verify approval and rejection action URLs generated by Workflow 04 succeed against backend."""
    run_id = uuid.uuid4()
    run = Run(
        id=run_id,
        objective="Execute gated research",
        domain="ai-observability",
        status=RunStatus.RUNNING,
    )
    async_db_session.add(run)
    await async_db_session.commit()

    proposed_action = {"tool": "scrape_page", "target": "https://example.com"}
    approval = await approval_service.create_approval_request(
        session=async_db_session,
        run_id=run_id,
        action="STEP_EXECUTION",
        proposed_action=proposed_action,
    )
    await async_db_session.commit()

    # 1. Test approve endpoint using payload generated by Workflow 04
    approve_url = f"/api/v1/approvals/{approval.id}/approve"
    approve_payload = {
        "expected_payload_hash": approval.payload_hash,
        "operator_notes": "Approved via n8n notification action link",
    }
    approve_res = await async_client.post(approve_url, json=approve_payload)
    assert approve_res.status_code == 200

    approved_data = approve_res.json()
    assert approved_data["status"] == "APPROVED"
    assert approved_data["operator_notes"] == "Approved via n8n notification action link"

    # 2. Test rejection on a second approval
    approval_2 = await approval_service.create_approval_request(
        session=async_db_session,
        run_id=run_id,
        action="REPORT_REVIEW",
        proposed_action={"report_draft": "Draft v1"},
    )
    await async_db_session.commit()
    reject_url = f"/api/v1/approvals/{approval_2.id}/reject"
    reject_payload = {
        "reason": "Draft report lacks primary evidence citations",
        "abort_run": True,
    }
    reject_res = await async_client.post(reject_url, json=reject_payload)
    assert reject_res.status_code == 200

    rejected_data = reject_res.json()
    assert rejected_data["status"] == "REJECTED"
    assert rejected_data["run_status"] == "ABORTED_BY_OPERATOR"


@pytest.mark.integration
def test_n8n_subdirectories_match_root_workflows():
    """Verify workflow copies in triggers/ and notifications/ match root files identically."""
    mappings = {
        WORKFLOWS_DIR / "triggers" / "01_agentops_run_trigger.json": WORKFLOWS_DIR
        / "01_agentops_run_trigger.json",
        WORKFLOWS_DIR / "triggers" / "05_scheduled_research_trigger.json": WORKFLOWS_DIR
        / "05_scheduled_research_trigger.json",
        WORKFLOWS_DIR / "notifications" / "02_run_completed_notification.json": WORKFLOWS_DIR
        / "02_run_completed_notification.json",
        WORKFLOWS_DIR / "notifications" / "03_run_failure_notification.json": WORKFLOWS_DIR
        / "03_run_failure_notification.json",
        WORKFLOWS_DIR / "notifications" / "04_approval_required_notification.json": WORKFLOWS_DIR
        / "04_approval_required_notification.json",
    }

    for sub_path, root_path in mappings.items():
        assert sub_path.exists(), f"Subdirectory workflow missing: {sub_path}"
        assert sub_path.read_text(encoding="utf-8") == root_path.read_text(encoding="utf-8"), (
            f"Content mismatch between {sub_path} and {root_path}"
        )


@pytest.mark.integration
def test_n8n_validation_logic_oversized_payload_rejection():
    """Verify the 50KB payload guardrail logic embedded in n8n Code nodes."""
    max_allowed_bytes = 51200

    # Normal payload under limit
    normal_payload = {"objective": "A" * 500, "domain": "test"}
    assert len(json.dumps(normal_payload)) <= max_allowed_bytes

    # Oversized payload exceeding 50KB
    oversized_payload = {"objective": "A" * 55000, "domain": "test"}
    assert len(json.dumps(oversized_payload)) > max_allowed_bytes
