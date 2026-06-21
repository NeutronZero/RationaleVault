# Relay Agent Handoff Checklist

Every agent completing a session must answer the following questions to verify context preservation and cleanly document status:

## 1. What Changed?
*Provide a high-level summary of code edits, schema changes, or files generated during the session.*

## 2. What Decisions Were Made?
*List any new architectural or design decisions accepted.*
* **Decision ID**: `dec_xx`
* **Title**: 
* **Rationale**: 

## 3. What Questions Were Resolved?
*List any open questions that were closed during this session.*
* **Question ID**: `q_xx`
* **Resolution**: 

## 4. What Tasks Were Completed?
*Identify completed work items.*
* **Task ID**: `task_xx`
* **Title**: 

## 5. What Should Happen Next?
*Explicitly state the next immediate action for the next agent session.*
* **Target Task / Question**: 
* **Action Details**: 

---

### Candidate Event Generation Template
Include this at the bottom of the handoff response:
```markdown
### RELAY_EVENT_CANDIDATES

- <EVENT_TYPE>
  id: <entity_id>
  payload:
    <key>: <value>
```
