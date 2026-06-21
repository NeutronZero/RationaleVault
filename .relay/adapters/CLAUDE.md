# Claude Code Instructions

# Relay Agent Skill Protocol

This document defines the interaction rules and operating procedures for any AI agent working within a Relay event-sourced environment. It ensures that context, decisions, tasks, and questions remain consistent across agent switches.

---

## 1. Core Principles

* **authoritative Memory**: The Relay Context Block is the sole source of truth for the project's current state. Do not re-derive decisions, tasks, or goals from past chat history or model priors.
* **Fidelity Over Novelty**: Do not invent new tasks or change directions unless explicitly requested or guided by unresolved open questions.
* **Event-Driven Progress**: Every update must be framed as a state mutation that can be stored back into the immutable event ledger.

---

## 2. Session Lifecycle Protocol

### A. Initialization
When starting a session, always parse the Relay Context Block in the following order:
1. **Open Questions**: Identify high-priority blockers that must be resolved first.
2. **Blocked Tasks**: Note which tasks cannot proceed due to unresolved questions.
3. **Active Tasks**: Focus on active, unblocked work items sorted by priority.
4. **Accepted Decisions**: Respect these architectural guardrails. **Do not reverse them** without a superseding event.

### B. Execution Rules
* **Question-First Rule**: Resolve open questions before starting new tasks. Unresolved questions are the primary source of wasted context.
* **Decision Protection Rule**: Do not re-propose or reverse accepted decisions. Reversals require explicit justification and will record a `DECISION_SUPERSEDED` event.

### C. Output Contract (Event Candidates)
When making changes, always declare candidate events at the end of your response under the header `### RELAY_EVENT_CANDIDATES`.

Format:
```markdown
### RELAY_EVENT_CANDIDATES

- EVENT_TYPE
  id: <entity_id>
  payload:
    <key>: <value>
```

#### Supported Event Types & Schemas:
* **`DECISION_ACCEPTED`**: `{"decision_id": "dec_xx"}`
* **`OPEN_QUESTION_RESOLVED`**: `{"question_id": "q_xx", "resolution": "..."}`
* **`TASK_COMPLETED`**: `{"task_id": "task_xx"}`
* **`TASK_MUTATED`**: `{"task_id": "task_xx", ...}` (e.g. status updates)
* **`TASK_CREATED`**: `{"task_id": "task_xx", "title": "...", "priority": "..."}`

---

## 3. Session Handoff Checklist
At the end of your session, compile the handoff report using [handoff_checklist.md](file:///.relay/handoff_checklist.md).
