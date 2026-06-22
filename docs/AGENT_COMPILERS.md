# RationaleVault Agent Compilers

## Overview

Agent Compilers translate a `CognitiveHead` into a formatted context string optimized for a specific AI agent's reasoning style.

All compilers implement the `AgentCompiler` ABC:

```python
class AgentCompiler(ABC):
    def compile(self, head: CognitiveHead) -> str: ...
    def agent_name(self) -> str: ...
```

**Compilers are output-only.** They do not call any LLM API. RationaleVault is model-agnostic. Context blocks are injected by the user.

---

## ClaudeCompiler (V1 — Implemented)

**File:** `rationalevault/compilers/claude.py`

Optimized for: narrative reasoning, architecture analysis, research, multi-agent handoffs.

### Section Order

Per design freeze (Change 6), Open Questions appear first:

```
1. Header (project name, ledger version, timestamp)
2. ⚠️  Open Questions  ← RESOLVE BEFORE STARTING NEW TASKS
3. 🚫  Blocked Tasks
4. 📋  Active Tasks
5. ✅  Accepted Decisions  ← DO NOT REVERSE WITHOUT STRONG REASON
6. 📌  Project Context (goal + focus)
7. 🚀  Resumption Prompt
```

### Resumption Prompt Logic

```
If open_questions exist:
    → target first (highest-priority) open question

Elif active_tasks exist:
    → target first (highest-priority) unblocked task

Else:
    → suggest reviewing state and proposing next sprint
```

### Usage

```python
from rationalevault.cognitive_head.compiler import compile_cognitive_head
from rationalevault.compilers.claude import ClaudeCompiler

head = compile_cognitive_head(project_id)
compiler = ClaudeCompiler()
context_block = compiler.compile(head)
print(context_block)  # paste into Claude
```

---

## Future Compilers (Sprint D or later)

Build only when Sprint C identifies agent-specific continuity failures.

### CursorCompiler

Optimized for: task execution, code generation, implementation.
- Shorter context blocks
- Task-first ordering (no narrative context needed)
- Code symbol references over prose descriptions
- File path references where relevant

### HermesCompiler

Optimized for: structured reasoning, research synthesis.
- Decision-first ordering (Hermes is most useful for reasoning about choices)
- Explicit option enumeration
- Confidence levels surfaced prominently

### ChatGPTCompiler

Optimized for: broad reasoning, question answering, task continuation.
- Similar to ClaudeCompiler but with simpler markdown
- More explicit role framing in system prompt style

### OpenCodeCompiler

Optimized for: direct code execution.
- Minimal prose
- Task list + decisions only
- Code-first references

---

## Adding a New Compiler

```python
# rationalevault/compilers/my_agent.py

from rationalevault.compilers.base import AgentCompiler
from rationalevault.cognitive_head.compiler import CognitiveHead

class MyAgentCompiler(AgentCompiler):

    @property
    def agent_name(self) -> str:
        return "MyAgent"

    def compile(self, head: CognitiveHead) -> str:
        # Format head into a string for MyAgent
        return f"# Context for {head.project_name}\n..."
```

Then add tests in `tests/unit/test_my_agent_compiler.py` following the pattern in `test_claude_compiler.py`.
