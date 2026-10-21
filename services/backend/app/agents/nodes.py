"""LangGraph workflow node implementations for all 10 bounded execution stages."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

import structlog
from langgraph.types import interrupt

from app.agents.planner import ALLOWED_TASK_TYPES, validate_plan_dag
from app.agents.state import AgentState
from app.core.config import get_settings
from app.providers import get_llm_provider
from app.tools.citation_auditor import CitationAuditor
from app.tools.evidence import EvidenceService
from app.tools.registry import get_tool_registry

logger = structlog.get_logger(__name__)
settings = get_settings()


def observable_node(
    name: str,
) -> Callable[[Callable[[AgentState], dict[str, Any]]], Callable[[AgentState], dict[str, Any]]]:
    """Decorator wrapping LangGraph nodes with correlation context and OpenTelemetry spans."""

    def decorator(
        fn: Callable[[AgentState], dict[str, Any]],
    ) -> Callable[[AgentState], dict[str, Any]]:
        @functools.wraps(fn)
        def wrapper(state: AgentState) -> dict[str, Any]:
            run_id = str(state.get("run_id")) if state.get("run_id") else None
            correlation_id = (
                str(state.get("correlation_id")) if state.get("correlation_id") else None
            )
            from app.observability import correlation_context, trace_span

            with (
                correlation_context(run_id=run_id, correlation_id=correlation_id, node_name=name),
                trace_span(f"langgraph.node.{name}", {"agentops.node_name": name}),
            ):
                return fn(state)

        return wrapper

    return decorator


# Stage 1: Validate request
@observable_node("validate_request")
def validate_request_node(state: AgentState) -> dict[str, Any]:
    """Validate user research request bounds and initialize execution counters."""
    objective = (state.get("objective") or "").strip()
    domain = (state.get("domain") or "").strip()

    if len(objective) < 10 or len(objective) > 2000:
        return {
            "fatal_error": f"Request objective length ({len(objective)}) must be between 10 and 2000 characters.",
            "status": "FAILED",
        }

    if not domain:
        return {
            "fatal_error": "Domain must be a non-empty string.",
            "status": "FAILED",
        }

    max_steps = state.get("max_steps") or settings.MAX_PLAN_STEPS
    budget_limit = state.get("budget_limit_usd") or settings.BUDGET_USD_LIMIT
    max_tokens = state.get("max_tokens") or settings.MAX_TOKENS_PER_RUN
    max_search_requests = state.get("max_search_requests") or settings.MAX_SEARCH_REQUESTS_PER_RUN
    max_fetched_bytes = state.get("max_fetched_bytes") or settings.MAX_FETCHED_BYTES_PER_RUN
    max_evidence_records = (
        state.get("max_evidence_records") or settings.MAX_EVIDENCE_RECORDS_PER_RUN
    )

    logger.info("request_validated", objective=objective[:50], domain=domain, max_steps=max_steps)
    return {
        "objective": objective,
        "domain": domain,
        "steps_executed": 0,
        "max_steps": max_steps,
        "cost_usd": 0.0,
        "budget_limit_usd": float(budget_limit),
        "tokens_consumed": 0,
        "max_tokens": max_tokens,
        "search_requests_count": 0,
        "max_search_requests": max_search_requests,
        "bytes_fetched": 0,
        "max_fetched_bytes": max_fetched_bytes,
        "evidence_records_count": 0,
        "max_evidence_records": max_evidence_records,
        "plan_repair_attempts": 0,
        "max_plan_repairs": 2,
        "step_results": {},
        "evidence_items": [],
        "errors": [],
        "fatal_error": None,
        "status": "PLANNING",
    }


# Stage 2: Generate structured plan
@observable_node("generate_plan")
def generate_plan_node(state: AgentState) -> dict[str, Any]:
    """Invoke LLM provider to synthesize a bounded execution plan."""
    if state.get("fatal_error"):
        return {"status": "FAILED"}

    llm = get_llm_provider(state.get("llm_provider"))
    constraints = dict(state.get("constraints") or {})

    # If this is a repair attempt, pass repair guidance in constraints
    repair_count = state.get("plan_repair_attempts", 0)
    if repair_count > 0:
        constraints["repair_attempt"] = repair_count
        constraints["previous_errors"] = state.get("errors", [])

    try:
        res = llm.generate_plan(
            objective=state["objective"],
            domain=state["domain"],
            geography=state.get("geography"),
            constraints=constraints,
        )
    except Exception as exc:
        logger.error("plan_generation_failed", error=str(exc))
        return {
            "fatal_error": f"LLM plan generation failed: {exc}",
            "status": "FAILED",
        }

    plan_steps = [s.model_dump() for s in res.data.steps]
    new_cost = state.get("cost_usd", 0.0) + float(res.usage.cost_usd)
    new_tokens = state.get("tokens_consumed", 0) + res.usage.total_tokens

    logger.info(
        "plan_generated",
        total_steps=len(plan_steps),
        provider=res.provider,
        cost_usd=new_cost,
        tokens=new_tokens,
    )
    return {
        "plan": plan_steps,
        "plan_rationale": res.data.rationale,
        "total_steps": len(plan_steps),
        "cost_usd": new_cost,
        "tokens_consumed": new_tokens,
    }


# Stage 3: Validate the plan
@observable_node("validate_plan")
def validate_plan_node(state: AgentState) -> dict[str, Any]:
    """Validate that plan forms a valid DAG with allowed task types and bounded length."""
    if state.get("fatal_error"):
        return {"status": "FAILED"}

    plan = state.get("plan", [])
    max_steps = state.get("max_steps", settings.MAX_PLAN_STEPS)

    is_valid, error_msg = validate_plan_dag(plan, max_steps=max_steps)

    if not is_valid:
        current_repairs = state.get("plan_repair_attempts", 0) + 1
        max_repairs = state.get("max_plan_repairs", 2)
        err = error_msg or "Unknown plan validation error"
        errors = list(state.get("errors", [])) + [err]

        if current_repairs <= max_repairs:
            logger.warning(
                "plan_invalid_triggering_repair",
                attempt=current_repairs,
                max_repairs=max_repairs,
                error=err,
            )
            return {
                "plan_repair_attempts": current_repairs,
                "errors": errors,
            }

        logger.error("plan_validation_repair_exhausted", error=err)
        return {
            "fatal_error": f"Plan validation failed after {max_repairs} repair attempts: {err}",
            "errors": errors,
            "status": "FAILED",
        }

    logger.info("plan_validated_successfully", step_count=len(plan))
    first_step = plan[0] if plan else None
    return {
        "current_step_index": 0,
        "current_step": first_step,
        "status": "RUNNING",
    }


# Stage 3b: Review execution plan when required (HITL Checkpoint)
@observable_node("check_plan_approval")
def check_plan_approval_node(state: AgentState) -> dict[str, Any]:
    """Check if synthesized execution plan requires operator approval before execution."""
    if state.get("fatal_error") or state.get("status") == "ABORTED_BY_OPERATOR":
        return {}

    constraints = dict(state.get("constraints") or {})
    requires_approval = bool(
        state.get("requires_plan_approval")
        or constraints.get("requires_plan_approval")
        or settings.REQUIRE_PLAN_APPROVAL
    )

    if not requires_approval or state.get("plan_approved", False):
        return {"plan_approved": True}

    plan = state.get("plan", [])
    verdict = interrupt(
        {
            "approval_required": True,
            "action": "plan_review",
            "total_steps": len(plan),
            "plan": plan,
            "rationale": state.get("plan_rationale"),
        }
    )

    decision = (
        verdict
        if isinstance(verdict, str)
        else (verdict.get("verdict") if isinstance(verdict, dict) else "approved")
    )
    decision_str = str(decision or "approved").lower()
    notes = verdict.get("operator_notes") if isinstance(verdict, dict) else None

    if decision_str not in ("approved", "yes", "true"):
        logger.warning("plan_approval_rejected", verdict=decision_str, notes=notes)
        return {
            "fatal_error": f"Operator rejected execution plan: {notes or 'No reason provided'}",
            "status": "ABORTED_BY_OPERATOR",
        }

    logger.info("plan_approval_granted")
    return {"plan_approved": True}


# Stage 4: Wait for approval when required (Human-in-the-Loop)
@observable_node("check_approval")
def check_approval_node(state: AgentState) -> dict[str, Any]:
    """Check if current step requires operator approval and pause execution via interrupt."""
    if state.get("fatal_error") or state.get("status") == "ABORTED_BY_OPERATOR":
        return {}

    step = state.get("current_step")
    if not step:
        return {}

    if step.get("requires_human_approval", False):
        step_id = step.get("step_identifier", "unknown")
        # Trigger LangGraph interrupt primitive
        verdict = interrupt(
            {
                "approval_required": True,
                "action": "step_execution",
                "step_identifier": step_id,
                "title": step.get("title"),
                "tool_name": step.get("tool_name"),
                "parameters": step.get("parameters"),
            }
        )

        # Process resume payload
        decision = (
            verdict
            if isinstance(verdict, str)
            else (verdict.get("verdict") if isinstance(verdict, dict) else "approved")
        )
        decision_str = str(decision or "approved").lower()
        notes = verdict.get("operator_notes") if isinstance(verdict, dict) else None

        if decision_str not in ("approved", "yes", "true"):
            logger.warning(
                "step_approval_rejected", step_id=step_id, verdict=decision_str, notes=notes
            )
            return {
                "fatal_error": f"Operator rejected execution of step '{step_id}': {notes or 'No reason provided'}",
                "status": "ABORTED_BY_OPERATOR",
            }

        logger.info("step_approval_granted", step_id=step_id)
        return {
            "approval_required": False,
            "approval_status": "APPROVED",
        }

    return {"approval_required": False}


# Stage 5: Execute approved task types (Guarded Tool Sandbox)
@observable_node("execute_task")
def execute_task_node(state: AgentState) -> dict[str, Any]:
    """Execute allowlisted task type within safety bounds. Never permits arbitrary code execution."""
    if state.get("fatal_error") or state.get("status") == "ABORTED_BY_OPERATOR":
        return {}

    steps_executed = state.get("steps_executed", 0)
    max_steps = state.get("max_steps", settings.MAX_PLAN_STEPS)
    cost_usd = state.get("cost_usd", 0.0)
    budget_limit = state.get("budget_limit_usd", settings.BUDGET_USD_LIMIT)
    tokens_consumed = state.get("tokens_consumed", 0)
    max_tokens = state.get("max_tokens", settings.MAX_TOKENS_PER_RUN)

    # Budget & step boundary checks
    if steps_executed >= max_steps:
        return {
            "fatal_error": f"Execution halted: step limit ({max_steps}) exceeded.",
            "status": "FAILED",
        }
    if cost_usd >= budget_limit:
        return {
            "fatal_error": f"Execution halted: financial budget limit (${budget_limit:.2f}) exceeded.",
            "status": "FAILED",
        }
    if tokens_consumed >= max_tokens:
        return {
            "fatal_error": f"Execution halted: token consumption budget ({max_tokens} tokens) exceeded.",
            "status": "FAILED",
        }

    step = state.get("current_step")
    if not step:
        return {"fatal_error": "No active step to execute.", "status": "FAILED"}

    tool_name = step.get("tool_name")
    step_id = str(step.get("step_identifier") or "")
    if not step_id:
        return {"fatal_error": "Active step missing step_identifier.", "status": "FAILED"}
    params = step.get("parameters", {})

    # Enforce tool allowlist
    if tool_name not in ALLOWED_TASK_TYPES:
        return {
            "fatal_error": f"Security violation: unauthorized tool '{tool_name}' requested in step '{step_id}'.",
            "status": "FAILED",
        }

    logger.info("executing_step_task", step_id=step_id, tool_name=tool_name)
    step_results = dict(state.get("step_results", {}))

    try:
        registry = get_tool_registry()
        tool_params = {
            **params,
            "run_id": str(state.get("run_id", "run-default")),
            "step_identifier": step_id,
            "domain": str(state.get("domain", "general")),
            "llm_provider": state.get("llm_provider"),
            "query": params.get("query", state.get("objective")),
        }
        tool_result = registry.execute(tool_name, tool_params)

        if not tool_result.success:
            return {
                "fatal_error": tool_result.error
                or f"Step '{step_id}' failed during tool execution.",
                "status": "FAILED",
            }

        result = dict(tool_result.data)
        if tool_result.evidence_records:
            result["evidence_records"] = tool_result.evidence_records
        if tool_result.content_hash:
            result["content_hash"] = tool_result.content_hash

        search_requests = state.get("search_requests_count", 0)
        max_searches = state.get("max_search_requests", settings.MAX_SEARCH_REQUESTS_PER_RUN)
        if tool_name in ("search_public_web", "web_search"):
            if search_requests >= max_searches:
                return {
                    "fatal_error": f"Execution halted: search request budget ({max_searches}) exceeded.",
                    "status": "FAILED",
                }
            search_requests += 1

        bytes_fetched = state.get("bytes_fetched", 0)
        max_bytes = state.get("max_fetched_bytes", settings.MAX_FETCHED_BYTES_PER_RUN)
        if tool_name in ("fetch_approved_public_page", "fetch_document"):
            added_bytes = int(result.get("byte_count", 0))
            if (bytes_fetched + added_bytes) > max_bytes:
                return {
                    "fatal_error": f"Execution halted: cumulative fetch bandwidth budget ({max_bytes} bytes) exceeded.",
                    "status": "FAILED",
                }
            bytes_fetched += added_bytes

        # Track token costs if extract_metrics or LLM was invoked
        if tool_name == "extract_metrics" and "cost_usd" in result:
            cost_usd += float(result.get("cost_usd", 0.0))

        step_results[step_id] = result
        return {
            "steps_executed": steps_executed + 1,
            "step_results": step_results,
            "cost_usd": cost_usd,
            "search_requests_count": search_requests,
            "bytes_fetched": bytes_fetched,
        }

    except Exception as exc:
        logger.error("step_execution_failed", step_id=step_id, error=str(exc))
        return {
            "fatal_error": f"Step '{step_id}' failed: {exc}",
            "status": "FAILED",
        }


# Stage 6: Validate step results and capture evidence
@observable_node("validate_step_result")
def validate_step_result_node(state: AgentState) -> dict[str, Any]:
    """Validate step outputs and record evidence with cryptographic SHA-256 hashes."""
    if state.get("fatal_error"):
        return {}

    step = state.get("current_step")
    if not step:
        return {}

    step_id = str(step.get("step_identifier") or "")
    result = state.get("step_results", {}).get(step_id)
    if not result:
        return {"fatal_error": f"Missing result for step '{step_id}'.", "status": "FAILED"}

    evidence_items = list(state.get("evidence_items", []))

    # Incorporate tool-generated evidence records if available
    tool_ev_records = result.get("evidence_records") if isinstance(result, dict) else None
    if tool_ev_records and isinstance(tool_ev_records, list):
        for ev in tool_ev_records:
            evidence_items.append(ev)
    else:
        # Construct verifiable evidence snippet using canonical EvidenceService
        snippet = str(result.get("content") or result.get("hits") or result)
        url = str(
            result.get("url")
            or (
                result.get("hits", [{}])[0].get("url")
                if isinstance(result.get("hits"), list) and result.get("hits")
                else "https://example.com/source"
            )
        )
        ev_record = EvidenceService.create_evidence_record(
            run_id=str(state.get("run_id", "run-default")),
            step_identifier=step_id,
            tool_name=str(step.get("tool_name", "unknown")),
            source_url=url,
            snippet=snippet[:400],
        )
        evidence_items.append(ev_record)

    logger.info("step_result_validated", step_id=step_id, total_evidence=len(evidence_items))
    return {"evidence_items": evidence_items}


# Stage 7: Evaluate evidence completeness and step progression
@observable_node("evaluate_evidence")
def evaluate_evidence_node(state: AgentState) -> dict[str, Any]:
    """Check if all planned steps have executed or advance to the next step."""
    if state.get("fatal_error"):
        return {}

    next_idx = state.get("current_step_index", 0) + 1
    plan = state.get("plan", [])

    if next_idx < len(plan):
        next_step = plan[next_idx]
        logger.info(
            "advancing_to_next_step", next_index=next_idx, step_id=next_step.get("step_identifier")
        )
        return {
            "current_step_index": next_idx,
            "current_step": next_step,
        }

    logger.info("all_plan_steps_completed", total_executed=len(plan))
    return {
        "current_step": None,
    }


# Stage 8: Generate report draft
@observable_node("generate_report")
def generate_report_node(state: AgentState) -> dict[str, Any]:
    """Invoke LLM to synthesize final structured report from evidence records."""
    if state.get("fatal_error"):
        return {}

    llm = get_llm_provider(state.get("llm_provider"))
    analysis_data = {"domain": state["domain"], "results": state.get("step_results", {})}
    evidence = state.get("evidence_items", [])

    try:
        report_res = llm.draft_report(
            objective=state["objective"],
            analysis=analysis_data,
            evidence_records=evidence,
        )
    except Exception as exc:
        logger.error("report_generation_failed", error=str(exc))
        return {
            "fatal_error": f"Report draft generation failed: {exc}",
            "status": "FAILED",
        }

    new_cost = state.get("cost_usd", 0.0) + float(report_res.usage.cost_usd)
    logger.info("report_draft_generated", title=report_res.data.title, cost_usd=new_cost)

    return {
        "final_report": report_res.data.model_dump(),
        "cost_usd": new_cost,
    }


# Stage 9: Validate report structure
@observable_node("validate_report")
def validate_report_node(state: AgentState) -> dict[str, Any]:
    """Validate report structure: ensure presence of empirical findings and strategic inferences."""
    if state.get("fatal_error"):
        return {}

    report = state.get("final_report")
    if not report:
        return {"fatal_error": "Final report was not generated.", "status": "FAILED"}

    grounded = report.get("grounded_findings", "")
    inferences = report.get("strategic_inferences", "")
    markdown = report.get("markdown_content", "")

    # Hard payload size check (Phase 21: Payload Bounds)
    max_payload_bytes: int = int(
        state.get("max_report_payload_bytes") or settings.MAX_REPORT_PAYLOAD_BYTES
    )
    if len(markdown.encode("utf-8")) > max_payload_bytes:
        logger.error(
            "report_payload_size_exceeded",
            size_bytes=len(markdown.encode("utf-8")),
            limit_bytes=max_payload_bytes,
        )
        return {
            "fatal_error": f"Report validation failed: markdown payload size ({len(markdown.encode('utf-8'))} bytes) exceeds maximum limit of {max_payload_bytes} bytes.",
            "status": "FAILED",
        }

    errors = list(state.get("errors", []))
    if not grounded or len(grounded.strip()) < 20:
        errors.append("Report lacks substantive grounded empirical findings section.")
    if not inferences or len(inferences.strip()) < 20:
        errors.append("Report lacks substantive strategic inferences section.")
    if not markdown or len(markdown.strip()) < 50:
        errors.append("Report markdown content is truncated or missing required headings.")

    # Audit empirical citation grounding
    evidence = state.get("evidence_items", [])
    audit_res = CitationAuditor.audit_report_grounding(report, evidence)
    if not audit_res.is_grounded:
        for hall in audit_res.hallucinated_citations:
            errors.append(f"Grounding audit warning: ungrounded citation [{hall}] detected.")

    if errors:
        logger.warning("report_structure_warnings", error_count=len(errors))
        return {"errors": errors}

    logger.info("report_structure_validated_cleanly")
    return {}


# Stage 9b: Review completed report when required (HITL Checkpoint)
@observable_node("check_report_approval")
def check_report_approval_node(state: AgentState) -> dict[str, Any]:
    """Check if completed report requires operator review before finalization."""
    if state.get("fatal_error") or state.get("status") == "ABORTED_BY_OPERATOR":
        return {}

    constraints = dict(state.get("constraints") or {})
    requires_approval = bool(
        state.get("requires_report_approval")
        or constraints.get("requires_report_approval")
        or settings.REQUIRE_REPORT_APPROVAL
    )

    if not requires_approval or state.get("report_approved", False):
        return {"report_approved": True}

    report = state.get("final_report", {})
    verdict = interrupt(
        {
            "approval_required": True,
            "action": "report_review",
            "title": report.get("title") if report else "Report Draft",
            "executive_summary": report.get("executive_summary") if report else "",
            "report": report,
        }
    )

    decision = (
        verdict
        if isinstance(verdict, str)
        else (verdict.get("verdict") if isinstance(verdict, dict) else "approved")
    )
    decision_str = str(decision or "approved").lower()
    notes = verdict.get("operator_notes") if isinstance(verdict, dict) else None

    if decision_str not in ("approved", "yes", "true"):
        logger.warning("report_approval_rejected", verdict=decision_str, notes=notes)
        return {
            "fatal_error": f"Operator rejected completed report: {notes or 'No reason provided'}",
            "status": "ABORTED_BY_OPERATOR",
        }

    logger.info("report_approval_granted")
    return {"report_approved": True}


# Stage 10: Finalize the run
@observable_node("finalize_run")
def finalize_run_node(state: AgentState) -> dict[str, Any]:
    """Determine terminal status and finalize run state."""
    if state.get("status") == "ABORTED_BY_OPERATOR":
        return {"status": "ABORTED_BY_OPERATOR"}

    if state.get("fatal_error"):
        return {"status": "FAILED"}

    if state.get("errors"):
        return {"status": "COMPLETED_WITH_WARNINGS"}

    return {"status": "COMPLETED"}
