"""Plan validation, DAG cycle detection, and plan repair heuristics."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

ALLOWED_TASK_TYPES = {
    "web_search",
    "fetch_document",
    "extract_metrics",
}


def validate_plan_dag(
    plan: list[dict[str, Any]],
    max_steps: int = 10,
) -> tuple[bool, str | None]:
    """Validate that an execution plan forms a valid, bounded Directed Acyclic Graph (DAG).

    Rules:
    1. Plan length must be between 1 and max_steps.
    2. Each step must have a unique, non-empty step_identifier.
    3. Task type (tool_name) must be in the approved allowlist.
    4. All dependencies must reference valid step_identifiers within the plan.
    5. No step may depend on itself.
    6. The graph must be strictly acyclic (Kahn's topological sort verification).

    Returns:
        (is_valid, error_message): Tuple indicating validity and failure reason.
    """
    if not plan:
        return False, "Plan is empty. At least one step is required."

    if len(plan) > max_steps:
        return False, f"Plan exceeds maximum allowable step limit ({len(plan)} > {max_steps})."

    step_ids: set[str] = set()
    for idx, step in enumerate(plan):
        step_id = step.get("step_identifier")
        if not step_id or not isinstance(step_id, str):
            return False, f"Step at index {idx} lacks a valid 'step_identifier'."

        if step_id in step_ids:
            return False, f"Duplicate step_identifier '{step_id}' found in plan."
        step_ids.add(step_id)

        tool_name = step.get("tool_name")
        if tool_name not in ALLOWED_TASK_TYPES:
            allowed_str = ", ".join(sorted(ALLOWED_TASK_TYPES))
            return (
                False,
                f"Step '{step_id}' requests unapproved task type '{tool_name}'. Allowed task types: {allowed_str}.",
            )

    # Validate dependencies and build adjacency
    in_degree: dict[str, int] = dict.fromkeys(step_ids, 0)
    adj: dict[str, list[str]] = defaultdict(list)

    for step in plan:
        step_id = step["step_identifier"]
        dependencies = step.get("dependencies", [])
        if not isinstance(dependencies, list):
            return False, f"Dependencies for step '{step_id}' must be a list."

        for dep in dependencies:
            if dep not in step_ids:
                return False, f"Step '{step_id}' references non-existent dependency '{dep}'."
            if dep == step_id:
                return False, f"Step '{step_id}' cannot depend on itself (self-loop cycle)."

            # Edge from dep -> step_id (dep must execute before step_id)
            adj[dep].append(step_id)
            in_degree[step_id] += 1

    # Kahn's algorithm for cycle detection
    queue: deque[str] = deque([node for node, deg in in_degree.items() if deg == 0])
    visited_count = 0

    while queue:
        node = queue.popleft()
        visited_count += 1
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited_count != len(step_ids):
        cyclic_nodes = [node for node, deg in in_degree.items() if deg > 0]
        return False, f"Dependency cycle detected in plan involving steps: {cyclic_nodes}."

    return True, None
