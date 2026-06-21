# Sprint C — First Handoff Experiment

## Objective

Run a real multi-agent handoff experiment and measure where continuity breaks.

```
Claude → Relay → ChatGPT → Relay → Hermes
```

Measure all five metrics at each handoff. Let failures define Sprint D.

---

## Prerequisites

1. Docker running: `docker-compose -f docker/postgres/docker-compose.yml up -d`
2. Schema initialized: `python scripts/init_db.py`
3. Dependencies installed: `pip install -e ".[dev]"`
4. `.env` configured (copy from `.env.example`)

---

## Step 1: Establish a Baseline (No Relay)

Before using Relay, measure cold-start performance.

**Goal:** Determine the baseline "Time to Productive Action" without any context.

### Baseline Procedure

1. Open a new Claude conversation.
2. Type only: `"I need you to continue work on the Relay V1 project. What should be done next?"`
3. Record: time until Claude produces a correct next-step action.
4. Note: Does Claude ask clarifying questions? Does it re-derive known decisions?
5. Repeat for ChatGPT and Hermes.

**Record baseline times in a note before proceeding.**

---

## Step 2: Seed the Demo Project

```bash
python scripts/seed_demo.py --project-name "Relay V1"
```

Save the Project ID printed at the end:
```
✅ Done. Project ID: <SAVE THIS UUID>
```

The command also prints the full Claude Context Block — copy it.

---

## Step 3: First Handoff — Claude

### 3.1 Start Claude Session

Open a new Claude conversation. Paste the Relay Context Block at the start.

**Verify Claude:**
- [ ] Identifies the 2 open questions (q_01, q_02)
- [ ] Lists the open Sprint C tasks
- [ ] References the 4 accepted decisions (psycopg3, no ORM, event_sequence ordering, no Alembic)
- [ ] Does NOT re-derive information already in the context
- [ ] Its first action targets the highest-priority open question

### 3.2 Run Handoff Metrics

```bash
python scripts/handoff_metrics.py --project-id <UUID> --agent "Claude"
```

Follow the interactive prompts. Metrics are saved to the Relay ledger.

### 3.3 Claude Work Session

Have Claude resolve one open question (e.g., "Should Sprint C use a real or synthetic scenario?").

When Claude resolves it, record the event manually:
```python
from relay.db.event_store import EventStore
from relay.schema.events import EventMetadata, EventType
import uuid

store = EventStore()
meta = EventMetadata(actor="Claude", source="manual",
                     session_id="<Claude session ID>",
                     correlation_id="sprint_c_experiment")

store.append_event(
    uuid.UUID("<YOUR_PROJECT_ID>"),
    "questions",
    EventType.OPEN_QUESTION_RESOLVED,
    {
        "question_id": "q_01",
        "resolution": "<Claude's resolution here>"
    },
    meta,
)
```

---

## Step 4: Second Handoff — ChatGPT

### 4.1 Compile a Fresh Context Block

After Claude's work session, recompile:

```python
from relay.cognitive_head.compiler import compile_cognitive_head
from relay.compilers.claude import ClaudeCompiler
import uuid

head = compile_cognitive_head(uuid.UUID("<YOUR_PROJECT_ID>"))
compiler = ClaudeCompiler()
print(compiler.compile(head))
```

Note: `ledger_version` should be higher than before.

### 4.2 Start ChatGPT Session

Open a new ChatGPT conversation. Paste the new context block.

**Verify ChatGPT:**
- [ ] Recognizes that q_01 has been resolved
- [ ] Identifies q_02 as the remaining open question
- [ ] Preserves the 4 accepted decisions from Claude's session
- [ ] Does NOT re-propose decisions already accepted

### 4.3 Run Handoff Metrics

```bash
python scripts/handoff_metrics.py --project-id <UUID> --agent "ChatGPT"
```

---

## Step 5: Third Handoff — Hermes

### 5.1 Compile a Fresh Context Block

Same as Step 4.1.

### 5.2 Start Hermes Session

Paste the updated context block.

**Verify Hermes:**
- [ ] Preserves all decisions from both previous agents
- [ ] Recognizes the current project state correctly
- [ ] Time to Productive Action is within 30 seconds of receiving context

### 5.3 Run Handoff Metrics

```bash
python scripts/handoff_metrics.py --project-id <UUID> --agent "Hermes"
```

---

## Step 6: Compare Results

After all three handoffs, retrieve metrics from the ledger:

```python
from relay.db.event_store import EventStore
from relay.schema.events import EventType
import uuid

store = EventStore()
events = store.get_stream(
    uuid.UUID("<YOUR_PROJECT_ID>"),
    "metrics"
)

metric_events = [e for e in events if e.event_type == EventType.FACT_RECORDED]
for e in metric_events:
    m = e.payload.get("metrics", {})
    print(f"\nAgent: {m.get('agent')}")
    print(f"  Context Load Time:         {m.get('context_load_time_s')}s")
    print(f"  Time to Productive Action: {m.get('time_to_productive_action_s')}s")
    print(f"  Task Continuity:           {m.get('task_continuity', 0):.0%}")
    print(f"  Decision Recall:           {m.get('decision_recall', 0):.0%}")
    print(f"  Question Recall:           {m.get('question_recall', 0):.0%}")
    print(f"  Overall Recall:            {m.get('overall_recall', 0):.0%}")
```

---

## Step 7: Identify Failures

After the experiment, answer:

| Question | Finding |
|----------|---------|
| Which agent had the lowest recall? | |
| Which information type was most often lost? | Tasks / Decisions / Questions |
| Did any agent re-derive already-known decisions? | |
| What was the baseline vs. Relay Time to Productive Action? | |
| Where did context continuity break? | |

---

## Step 8: Define Sprint D

Based on failures, choose which of these to build next:

| If this failed | Build this |
|----------------|------------|
| Facts re-derived despite decisions | R3 Knowledge Compiler |
| Context block too large | R4 Context Planner (token budget) |
| Agent didn't trust the context | Provenance Explorer (R6) |
| Handoff took > 30 seconds | Faster compilation (snapshots) |
| Decisions not preserved | Stronger decision framing in compiler |

**Do not build anything that Sprint C did not break.**

---

## Relay's Success Criterion

Relay V1 succeeds if:

```
Any agent can resume work
within 30 seconds
with Task Continuity ≥ 80%
and Decision Recall ≥ 90%
```

If these are achieved, Sprint D can expand to Knowledge Compilation, Context Planning, and Reflection.
If not, diagnose the specific failure first.
