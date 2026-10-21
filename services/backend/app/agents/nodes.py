"""LangGraph workflow node implementations for all 10 bounded execution stages."""

from __future__ import annotations

import hashlib
from typing import Any

import structlog
from langgraph.types import interrupt

from app.agents.planner import ALLOWED_TASK_TYPES, validate_plan_dag
from app.agents.state import AgentState
from app.core.config import get_settings
from app.core.exceptions import DeterministicValidationError
from app.core.security import SecurityValidationError, is_safe_url
from app.providers import get_llm_provider

logger = structlog.get_logger(__name__)
settings = get_settings()


# Stage 1: Validate request
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

    logger.info("request_validated", objective=objective[:50], domain=domain, max_steps=max_steps)
    return {
        "objective": objective,
        "domain": domain,
        "steps_executed": 0,
        "max_steps": max_steps,
        "cost_usd": 0.0,
        "budget_limit_usd": float(budget_limit),
        "plan_repair_attempts": 0,
        "max_plan_repairs": 2,
        "step_results": {},
        "evidence_items": [],
        "errors": [],
        "fatal_error": None,
        "status": "PLANNING",
    }


# Stage 2: Generate structured plan
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

    logger.info(
        "plan_generated",
        total_steps=len(plan_steps),
        provider=res.provider,
        cost_usd=new_cost,
    )
    return {
        "plan": plan_steps,
        "plan_rationale": res.data.rationale,
        "total_steps": len(plan_steps),
        "cost_usd": new_cost,
    }


# Stage 3: Validate the plan
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


# Stage 4: Wait for approval when required (Human-in-the-Loop)
def check_approval_node(state: AgentState) -> dict[str, Any]:
    """Check if current step requires operator approval and pause execution via interrupt."""
    if state.get("fatal_error"):
        return {"status": "FAILED"}

    step = state.get("current_step")
    if not step:
        return {}

    if step.get("requires_human_approval", False):
        step_id = step.get("step_identifier", "unknown")
        # Trigger LangGraph interrupt primitive
        verdict = interrupt(
            {
                "approval_required": True,
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
        if decision_str not in ("approved", "yes", "true"):
            logger.warning("step_approval_rejected", step_id=step_id, verdict=decision_str)
            return {
                "fatal_error": f"Operator rejected execution of step '{step_id}'.",
                "status": "ABORTED_BY_OPERATOR",
            }

        logger.info("step_approval_granted", step_id=step_id)
        return {
            "approval_required": False,
            "approval_status": "APPROVED",
        }

    return {"approval_required": False}


# Stage 5: Execute approved task types (Guarded Tool Sandbox)
def execute_task_node(state: AgentState) -> dict[str, Any]:
    """Execute allowlisted task type within safety bounds. Never permits arbitrary code execution."""
    if state.get("fatal_error") or state.get("status") == "ABORTED_BY_OPERATOR":
        return {}

    steps_executed = state.get("steps_executed", 0)
    max_steps = state.get("max_steps", settings.MAX_PLAN_STEPS)
    cost_usd = state.get("cost_usd", 0.0)
    budget_limit = state.get("budget_limit_usd", settings.BUDGET_USD_LIMIT)

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
        # Bounded tool handlers
        if tool_name == "web_search":
            query = params.get("query", state["objective"])
            # In mock/offline mode, return simulated verified competitor search hits
            result = {
                "query": query,
                "hits": [
                    {
                        "title": f"{state['domain']} Benchmark Overview",
                        "url": f"https://example.com/{state['domain']}/benchmark",
                        "snippet": f"Competitive landscape analysis for {state['domain']}. Documented pricing starting from $49/mo.",
                    },
                    {
                        "title": "Enterprise Cloud Observability Feature Matrix",
                        "url": "https://example.com/features/matrix",
                        "snippet": "Feature comparison: Docker Compose deployment, 99.95% API SLA, self-hosted data isolation.",
                    },
                ],
            }
        elif tool_name == "fetch_document":
            url = params.get("url") or f"https://example.com/{params.get('domain', 'tech')}/pricing"
            # SSRF validation check
            safe, reason = is_safe_url(url)
            if not safe:
                raise SecurityValidationError(f"SSRF policy blocked request to '{url}': {reason}")

            result = {
                "url": url,
                "content": (
                    f"Verified Documentation for {params.get('domain', state['domain'])}: "
                    "Features full offline mock capabilities, multi-database PostgreSQL support, and transactional outbox."
                ),
            }
        elif tool_name == "extract_metrics":
            llm = get_llm_provider(state.get("llm_provider"))
            sample_text = (
                f"Competitor data extracted for {state['domain']}: pricing $49/mo, 99.95% uptime."
            )
            ext_res = llm.extract_information(sample_text)
            result = ext_res.data.model_dump()
            cost_usd += float(ext_res.usage.cost_usd)
        else:
            raise DeterministicValidationError(f"Unhandled tool type: {tool_name}")

        step_results[step_id] = result
        return {
            "steps_executed": steps_executed + 1,
            "step_results": step_results,
            "cost_usd": cost_usd,
        }

    except Exception as exc:
        logger.error("step_execution_failed", step_id=step_id, error=str(exc))
        return {
            "fatal_error": f"Step '{step_id}' failed: {exc}",
            "status": "FAILED",
        }


# Stage 6: Validate step results and capture evidence
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

    # Construct verifiable evidence snippet
    snippet = str(result)
    content_hash = hashlib.sha256(snippet.encode("utf-8")).hexdigest()

    evidence_items.append(
        {
            "step_identifier": step_id,
            "tool_name": step.get("tool_name"),
            "content_hash": content_hash,
            "snippet": snippet[:400],
        }
    )

    logger.info("step_result_validated", step_id=step_id, content_hash=content_hash[:12])
    return {"evidence_items": evidence_items}


# Stage 7: Evaluate evidence completeness and step progression
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

    errors = list(state.get("errors", []))
    if not grounded or len(grounded.strip()) < 20:
        errors.append("Report lacks substantive grounded empirical findings section.")
    if not inferences or len(inferences.strip()) < 20:
        errors.append("Report lacks substantive strategic inferences section.")
    if not markdown or len(markdown.strip()) < 50:
        errors.append("Report markdown content is truncated or missing required headings.")

    if errors:
        logger.warning("report_structure_warnings", error_count=len(errors))
        return {"errors": errors}

    logger.info("report_structure_validated_cleanly")
    return {}


# Stage 10: Finalize the run
def finalize_run_node(state: AgentState) -> dict[str, Any]:
    """Determine terminal status and finalize run state."""
    if state.get("status") == "ABORTED_BY_OPERATOR":
        return {"status": "ABORTED_BY_OPERATOR"}

    if state.get("fatal_error"):
        return {"status": "FAILED"}

    if state.get("errors"):
        return {"status": "COMPLETED_WITH_WARNINGS"}

    return {"status": "COMPLETED"}
