"""LangGraph agent graph definition, conditional routing, and compilation."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from app.agents.nodes import (
    check_approval_node,
    check_plan_approval_node,
    check_report_approval_node,
    evaluate_evidence_node,
    execute_task_node,
    finalize_run_node,
    generate_plan_node,
    generate_report_node,
    validate_plan_node,
    validate_report_node,
    validate_request_node,
    validate_step_result_node,
)
from app.agents.state import AgentState
from app.repositories.checkpointer import DurableCheckpointSaver


# Conditional routing predicates
def route_after_request_validation(state: AgentState) -> str:
    if state.get("fatal_error"):
        return "finalize_run"
    return "generate_plan"


def route_after_plan_validation(state: AgentState) -> str:
    if state.get("fatal_error"):
        return "finalize_run"
    # If repair attempt triggered and current_step is None, loop back to plan generation
    if state.get("plan_repair_attempts", 0) > 0 and state.get("current_step") is None:
        return "generate_plan"
    return "check_plan_approval"


def route_after_plan_approval(state: AgentState) -> str:
    if state.get("fatal_error") or state.get("status") == "ABORTED_BY_OPERATOR":
        return "finalize_run"
    return "check_approval"


def route_after_approval_check(state: AgentState) -> str:
    if state.get("fatal_error") or state.get("status") == "ABORTED_BY_OPERATOR":
        return "finalize_run"
    return "execute_task"


def route_after_step_execution(state: AgentState) -> str:
    if state.get("fatal_error"):
        return "finalize_run"
    return "validate_step_result"


def route_after_evidence_evaluation(state: AgentState) -> str:
    if state.get("fatal_error"):
        return "finalize_run"
    # If there are more steps remaining in the plan, loop back to approval check for next step
    if state.get("current_step") is not None:
        return "check_approval"
    return "generate_report"


def route_after_report_generation(state: AgentState) -> str:
    if state.get("fatal_error"):
        return "finalize_run"
    return "validate_report"


def route_after_report_validation(state: AgentState) -> str:
    if state.get("fatal_error") or state.get("status") == "ABORTED_BY_OPERATOR":
        return "finalize_run"
    return "check_report_approval"


def build_agent_graph() -> StateGraph:
    """Construct the bounded StateGraph representing the execution stages and HITL approval checkpoints."""
    workflow = StateGraph(AgentState)

    # 1. Register nodes
    workflow.add_node("validate_request", validate_request_node)
    workflow.add_node("generate_plan", generate_plan_node)
    workflow.add_node("validate_plan", validate_plan_node)
    workflow.add_node("check_plan_approval", check_plan_approval_node)
    workflow.add_node("check_approval", check_approval_node)
    workflow.add_node("execute_task", execute_task_node)
    workflow.add_node("validate_step_result", validate_step_result_node)
    workflow.add_node("evaluate_evidence", evaluate_evidence_node)
    workflow.add_node("generate_report", generate_report_node)
    workflow.add_node("validate_report", validate_report_node)
    workflow.add_node("check_report_approval", check_report_approval_node)
    workflow.add_node("finalize_run", finalize_run_node)

    # 2. Add edges and conditional transitions
    workflow.add_edge(START, "validate_request")

    workflow.add_conditional_edges(
        "validate_request",
        route_after_request_validation,
        {
            "generate_plan": "generate_plan",
            "finalize_run": "finalize_run",
        },
    )

    workflow.add_edge("generate_plan", "validate_plan")

    workflow.add_conditional_edges(
        "validate_plan",
        route_after_plan_validation,
        {
            "generate_plan": "generate_plan",  # Repair loop
            "check_plan_approval": "check_plan_approval",
            "finalize_run": "finalize_run",
        },
    )

    workflow.add_conditional_edges(
        "check_plan_approval",
        route_after_plan_approval,
        {
            "check_approval": "check_approval",
            "finalize_run": "finalize_run",
        },
    )

    workflow.add_conditional_edges(
        "check_approval",
        route_after_approval_check,
        {
            "execute_task": "execute_task",
            "finalize_run": "finalize_run",
        },
    )

    workflow.add_conditional_edges(
        "execute_task",
        route_after_step_execution,
        {
            "validate_step_result": "validate_step_result",
            "finalize_run": "finalize_run",
        },
    )

    workflow.add_edge("validate_step_result", "evaluate_evidence")

    workflow.add_conditional_edges(
        "evaluate_evidence",
        route_after_evidence_evaluation,
        {
            "check_approval": "check_approval",  # Next step in loop
            "generate_report": "generate_report",  # All steps finished
            "finalize_run": "finalize_run",
        },
    )

    workflow.add_conditional_edges(
        "generate_report",
        route_after_report_generation,
        {
            "validate_report": "validate_report",
            "finalize_run": "finalize_run",
        },
    )

    workflow.add_conditional_edges(
        "validate_report",
        route_after_report_validation,
        {
            "check_report_approval": "check_report_approval",
            "finalize_run": "finalize_run",
        },
    )

    workflow.add_edge("check_report_approval", "finalize_run")
    workflow.add_edge("finalize_run", END)

    return workflow


def create_agent_graph(checkpointer: BaseCheckpointSaver | None = None) -> Any:
    """Compile the agent StateGraph with a durable checkpoint saver for persistent state and HITL pause/resume."""
    saver = checkpointer or DurableCheckpointSaver()
    workflow = build_agent_graph()
    return workflow.compile(checkpointer=saver)
