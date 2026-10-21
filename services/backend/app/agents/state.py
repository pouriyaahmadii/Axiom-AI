"""Typed state definitions for the LangGraph AgentOps execution runtime."""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """Complete execution state schema for the bounded LangGraph agent workflow."""

    # 1. Run identifiers
    run_id: str
    correlation_id: str | None

    # 2. Validated user request
    objective: str
    domain: str
    geography: str | None
    constraints: dict[str, Any]

    # 3. Provider selection
    llm_provider: str
    search_provider: str

    # 4. Execution plan
    plan: list[dict[str, Any]]
    plan_rationale: str | None
    total_steps: int

    # 5. Current step execution pointers
    current_step_index: int  # 0-based index into plan
    current_step: dict[str, Any] | None

    # 6. Step inputs and outputs
    step_results: dict[str, Any]  # map of step_identifier -> result payload

    # 7. Evidence references
    evidence_items: list[dict[str, Any]]

    # 8. Budget counters & resource bounds
    steps_executed: int
    max_steps: int
    cost_usd: float
    budget_limit_usd: float
    plan_repair_attempts: int
    max_plan_repairs: int

    # 9. Error summaries
    errors: list[str]
    fatal_error: str | None

    # 10. Approval state (Human-in-the-Loop)
    approval_required: bool
    approval_id: str | None
    approval_status: str | None
    approval_token: str | None
    approval_action: dict[str, Any] | None

    # 11. Final report reference & lifecycle status
    final_report: dict[str, Any] | None
    status: str  # QUEUED, PLANNING, RUNNING, AWAITING_APPROVAL, COMPLETED, COMPLETED_WITH_WARNINGS, FAILED
