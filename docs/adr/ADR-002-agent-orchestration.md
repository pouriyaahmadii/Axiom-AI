# ADR-002: Agent Orchestration Engine Selection (LangGraph)

## Status
Accepted

## Context
AgentOps requires an orchestration framework to coordinate the analytical research workflow:
1. Deconstruct objectives into discrete, bounded execution steps.
2. Manage explicit state transitions and maintain an auditable state dictionary.
3. Support Human-in-the-Loop (HITL) gates, where execution halts at consequential nodes, persists its exact execution state to PostgreSQL, and resumes seamlessly upon operator approval.
4. Enforce strict bounded execution loops without non-deterministic conversational drift.

## Decision
We select **LangGraph** (Python) as the primary agent orchestration framework.
The workflow is implemented as a **Single Coordinator StateGraph** with explicit nodes:
- `PlannerNode`: Generates and validates the step DAG.
- `ToolExecutionNode`: Sequentially executes allowlisted tools under SSRF protection.
- `ApprovalCheckpointNode`: Interrupts the graph and awaits external approval.
- `SynthesizerNode`: Aggregates evidence and authors the final citation-grounded report.

## Alternatives Considered
1. **CrewAI**:
   - *Pros*: Quick prototyping of role-based agents.
   - *Cons*: Highly opinionated around multi-agent chat swarms; lacks first-class interrupt/resume checkpointing; non-deterministic message looping.
2. **AutoGen (Microsoft)**:
   - *Pros*: Flexible multi-agent conversational patterns.
   - *Cons*: Heavy focus on conversational emergence; difficult to enforce strict step budgets and deterministic state persistence.
3. **Custom Hand-Rolled State Machine in Pure Python**:
   - *Pros*: Zero third-party framework overhead.
   - *Cons*: Requires rebuilding state checkpoint serialization, graph visualization, interrupt protocols, and retry logic from scratch.

## Consequences
- **Positive**:
  - Native support for durable checkpoints in PostgreSQL via `langgraph.checkpoint.postgres`.
  - Built-in `interrupt()` primitives allowing clean suspension and resumption for human-in-the-loop approvals.
  - Cyclic and acyclic directed graph modeling provides complete determinism over task transitions.
- **Negative / Trade-offs**:
  - LangGraph's API evolved rapidly between versions 0.1 and 0.2; we must pin dependencies and adhere strictly to current stable patterns.

## Rejected Options
- **Multi-Agent Conversational Swarm**: Rejected because unconstrained agent-to-agent debate creates non-deterministic token consumption, hallucinations, and unobservable failure modes.
- **Prompt Chaining without State Graph**: Rejected because linear prompt chains cannot handle dynamic retries, branching tool calls, or human approval interruptions.

## Conditions for Revisiting
- If LangGraph introduces breaking architectural shifts or proprietary licensing restrictions, or if a lightweight custom state machine proves significantly simpler to maintain.
