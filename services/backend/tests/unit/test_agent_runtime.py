"""Unit and integration tests for the bounded LangGraph agent runtime."""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.agents import (
    ALLOWED_TASK_TYPES,
    AgentState,
    create_agent_graph,
    validate_plan_dag,
)


def test_allowed_task_types_allowlist() -> None:
    """Verify strictly approved task types in agent registry."""
    assert {"web_search", "fetch_document", "extract_metrics"} == ALLOWED_TASK_TYPES


def test_validate_plan_dag_success() -> None:
    """Verify valid linear DAG passes validation."""
    valid_plan = [
        {"step_identifier": "step_1", "tool_name": "web_search", "dependencies": []},
        {"step_identifier": "step_2", "tool_name": "fetch_document", "dependencies": ["step_1"]},
        {"step_identifier": "step_3", "tool_name": "extract_metrics", "dependencies": ["step_2"]},
    ]
    is_valid, err = validate_plan_dag(valid_plan, max_steps=10)
    assert is_valid is True
    assert err is None


def test_validate_plan_dag_detects_cycle() -> None:
    """Verify circular dependencies are detected and rejected."""
    cyclic_plan = [
        {"step_identifier": "step_a", "tool_name": "web_search", "dependencies": ["step_b"]},
        {"step_identifier": "step_b", "tool_name": "fetch_document", "dependencies": ["step_a"]},
    ]
    is_valid, err = validate_plan_dag(cyclic_plan, max_steps=10)
    assert is_valid is False
    assert "cycle detected" in str(err).lower()


def test_validate_plan_dag_detects_self_loop() -> None:
    """Verify self-dependency is rejected."""
    self_loop_plan = [
        {"step_identifier": "step_a", "tool_name": "web_search", "dependencies": ["step_a"]},
    ]
    is_valid, err = validate_plan_dag(self_loop_plan, max_steps=10)
    assert is_valid is False
    assert "cannot depend on itself" in str(err).lower()


def test_validate_plan_dag_rejects_unknown_task_types() -> None:
    """Verify unauthorized arbitrary code or shell execution tools are strictly rejected."""
    dangerous_plan = [
        {"step_identifier": "step_eval", "tool_name": "execute_shell", "dependencies": []},
    ]
    is_valid, err = validate_plan_dag(dangerous_plan, max_steps=10)
    assert is_valid is False
    assert "unapproved task type 'execute_shell'" in str(err)


def test_validate_plan_dag_enforces_max_steps() -> None:
    """Verify plan exceeding max_steps ceiling is rejected."""
    long_plan = [
        {"step_identifier": f"step_{i}", "tool_name": "web_search", "dependencies": []}
        for i in range(12)
    ]
    is_valid, err = validate_plan_dag(long_plan, max_steps=10)
    assert is_valid is False
    assert "maximum allowable step limit" in str(err)


def test_agent_graph_full_execution_with_mock_provider() -> None:
    """Acceptance Criteria: Complete 10-stage execution completes cleanly with MockLLMProvider."""
    checkpointer = MemorySaver()
    graph = create_agent_graph(checkpointer=checkpointer)

    initial_state: AgentState = {
        "run_id": "test-run-001",
        "objective": "Analyze competitor landscape for cloud observability tools in North America",
        "domain": "cloud-observability",
        "geography": "North America",
        "llm_provider": "mock",
        "max_steps": 10,
        "budget_limit_usd": 2.00,
    }

    config = {"configurable": {"thread_id": "thread-mock-test-1"}}
    final_output = graph.invoke(initial_state, config=config)

    assert final_output["status"] == "COMPLETED"
    assert final_output["steps_executed"] == 3
    assert len(final_output["evidence_items"]) == 3
    assert all("content_hash" in ev for ev in final_output["evidence_items"])
    assert final_output["final_report"] is not None
    assert "grounded_findings" in final_output["final_report"]
    assert "strategic_inferences" in final_output["final_report"]
    assert final_output["cost_usd"] >= 0.0


def test_agent_graph_stops_on_request_validation_failure() -> None:
    """Verify invalid short objective halts at Stage 1."""
    checkpointer = MemorySaver()
    graph = create_agent_graph(checkpointer=checkpointer)

    initial_state: AgentState = {
        "run_id": "test-run-invalid",
        "objective": "Too short",  # Less than 10 chars
        "domain": "tech",
        "llm_provider": "mock",
    }

    config = {"configurable": {"thread_id": "thread-invalid-request"}}
    final_output = graph.invoke(initial_state, config=config)

    assert final_output["status"] == "FAILED"
    assert "objective length" in final_output["fatal_error"].lower()


def test_agent_graph_budget_ceiling_exhaustion() -> None:
    """Verify execution halts when budget limit is reached."""
    checkpointer = MemorySaver()
    graph = create_agent_graph(checkpointer=checkpointer)

    initial_state: AgentState = {
        "run_id": "test-run-budget",
        "objective": "Analyze competitor landscape for cloud observability tools",
        "domain": "cloud-observability",
        "llm_provider": "mock",
        "max_steps": 1,  # Set maximum steps to 1 to trigger budget limit before 3 steps finish
    }

    config = {"configurable": {"thread_id": "thread-budget-limit"}}
    final_output = graph.invoke(initial_state, config=config)

    assert final_output["status"] == "FAILED"
    assert "step limit" in final_output["fatal_error"].lower()


def test_agent_graph_hitl_approval_pause_and_resume() -> None:
    """Verify Human-in-the-Loop approval pauses graph at step boundary and resumes upon approval."""
    checkpointer = MemorySaver()
    graph = create_agent_graph(checkpointer=checkpointer)

    # We will inject a step that requires human approval
    initial_state: AgentState = {
        "run_id": "test-run-hitl",
        "objective": "Analyze competitor landscape with sensitive external query",
        "domain": "security",
        "llm_provider": "mock",
        "max_steps": 10,
    }

    config = {"configurable": {"thread_id": "thread-hitl-test"}}

    # Pre-populate state with an approval-required step
    pre_plan = [
        {
            "step_index": 1,
            "step_identifier": "approval_gated_step",
            "title": "Sensitive External Ingress Query",
            "tool_name": "web_search",
            "parameters": {"query": "security audit"},
            "requires_human_approval": True,
            "dependencies": [],
        }
    ]

    # Run up to the interrupt
    graph.update_state(
        config,
        {
            **initial_state,
            "plan": pre_plan,
            "current_step_index": 0,
            "current_step": pre_plan[0],
            "status": "RUNNING",
            "steps_executed": 0,
            "cost_usd": 0.0,
            "budget_limit_usd": 2.0,
            "max_steps": 10,
            "evidence_items": [],
            "step_results": {},
            "errors": [],
        },
        as_node="validate_plan",
    )

    # Invoke from validate_plan -> check_approval triggers interrupt
    res_paused = graph.invoke(None, config=config)
    assert "__interrupt__" in res_paused
    interrupt_payload = res_paused["__interrupt__"][0].value
    assert interrupt_payload["approval_required"] is True
    assert interrupt_payload["step_identifier"] == "approval_gated_step"

    # Verify graph state is waiting at check_approval
    current_snapshot = graph.get_state(config)
    assert "check_approval" in current_snapshot.next

    # Resume with approval decision
    res_resumed = graph.invoke(Command(resume={"verdict": "approved"}), config=config)
    assert res_resumed["status"] in ("COMPLETED", "COMPLETED_WITH_WARNINGS")
    assert res_resumed["steps_executed"] >= 1
