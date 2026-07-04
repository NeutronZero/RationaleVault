# RationaleVault Custom Subagent Governance Workflow

To maintain absolute architectural integrity, RationaleVault employs a decentralized agentic governance model. Specialist subagents are orchestrated by the lead architect in a gated workflow to validate and audit every proposed change against the platform's constitutional laws and theorems.

---

## The Six-Agent Specialist Team

1. **`architecture_reviewer`**
   - *Question:* "Is this a good design?"
   - *Checks:* ADR alignment, dependency direction, layering boundaries, and abstraction quality.

2. **`theorem_guardian`**
   - *Question:* "Is the design constitutionally valid?"
   - *Checks:* Compliance with the 13 Architectural Theorems, Invariants, and Monotonic Understanding. Acts as both the initial semantic gate and the final validation gate before code merges.

3. **`implementation_engineer`**
   - *Action:* Writes clean, minimal code changes with complete test coverage according to the approved ADR. Never invents new abstractions.

4. **`validation_engineer`**
   - *Action:* Runs the unit/integration tests sequentially, checks dependency graph compliance (`check_dependencies.py`), and executes AST guards (`test_architecture_guards.py`).

5. **`performance_engineer`**
   - *Action:* Runs replay performance benchmarks (`benchmark_replay.py`) to measure latency and throughput changes, ensuring compliance with the Optimization Neutrality Theorem.

6. **`documentation_engineer`**
   - *Action:* Synchronizes ADRs, freeze checklists, health reports, task logs, and rules with the completed implementation.

---

## Standardized Review Template
Every subagent must output its report using this uniform format:

```text
Decision:
PASS | PASS WITH CHANGES | FAIL

Scope:
(components, files, or packages audited)

Checks Performed:
- ...

Risks:
- ...

Recommendations:
- ...

Confidence:
High / Medium / Low
```

---

## The Constitutional Gate Workflow

```
                  Feature Request
                        │
                        ▼
            [1. Architecture Reviewer]
               (Design & Layering)
                        │
                        ▼
              [2. Theorem Guardian]
               (Initial Theorem Gate)
                        │
               APPROVED DESIGN
                        │
                        ▼
          [3. Implementation Engineer]
                        │
                        ▼
            [4. Validation Engineer]
              (Tests, Guards, Audits)
                        │
                        ▼
             [5. Performance Engineer]
                        │
                        ▼
           [6. Documentation Engineer]
                        │
                        ▼
              [2. Theorem Guardian]
                (Final Sign-off)
                        │
                        ▼
                  Merge / Freeze
```

---

*See also:*
* [`docs/contributing/ARCHITECTURE_RULES.md`](file:///c:/Projects/Relay/docs/contributing/ARCHITECTURE_RULES.md) — The operational developer rules.
* `architectural_theorems.md` — The core theorems.
