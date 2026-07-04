# ADR-012: Promotion Pipeline Pattern

**Date:** 2026-06-26
**Status:** Accepted
**Supersedes:** N/A

## Context

Across RationaleVault, multiple subsystems follow the same lifecycle progression:

1. **Beliefs:** CandidateEvent → Assessment → GateResult → Decision → BEL
2. **Skills:** SkillCandidate → SkillAssessment → GateResult → Decision → SKL
3. **Artifacts:** ArtifactCandidate → ExecutionEvaluation → GateResult → Decision → ART
4. **Reflections:** ReflectionCandidate → RuleEngine assessment → Approval → Reflection
5. **Knowledge Promotion:** PromotionCandidate → PromotionAssessment → PromotionGateResult → Decision → KnowledgeCandidate → KnowledgeObject
6. **Memory:** ConsolidationCandidate → Evidence evaluation → Promotion decision → MTRANS
7. **Workspace:** Workspace → Session → Snapshot → Context → Package

Each applies the same fundamental pattern but with slightly different naming and structure. This creates risk of drift as new subsystems are added (agent onboarding, connector registration, policy approval, workflow publication).

## Decision

Formalize the **Promotion Pipeline Pattern** as an architectural invariant. All lifecycle progressions in RationaleVault must follow this pattern.

### Core Pipeline

```
Candidate
    ↓
Assessment
    ↓
Gate
    ↓
Decision
    ↓
[Materialization]  ← optional stage
    ↓
Materialized Object
    ↓
Event
    ↓
Projection
```

### Stage Definitions

| Stage | Purpose | Immutability | ID Family |
|-------|---------|-------------|-----------|
| **Candidate** | Proposes a potential promotion. Created from raw inputs. | Frozen | CAND-[hash] or subsystem-specific |
| **Assessment** | Evaluates candidate against rules/criteria. Produces scoring, approval/rejection. | Frozen | Subsystem-specific |
| **Gate** | Binary pass/fail decision based on assessment. Enforces quality thresholds. | Frozen | Subsystem-specific |
| **Decision** | Records the promotion decision (approve, reject, defer). Never rewrites assessment. | Frozen | DEC-[hash] or subsystem-specific |
| **Materialization** (optional) | Transforms intermediate candidate into final object. May not exist in simple pipelines. | One-way transformation | Subsystem-specific |
| **Materialized Object** | The durable domain object resulting from promotion. | Frozen | Subsystem-specific (BEL, SKL, ART, KNOW, etc.) |
| **Event** | Immutable event payload emitted to the Event Ledger. The only persistence boundary. | Frozen | Event type-specific |
| **Projection** | Derived read-only state compiled from events. Never feeds back into upstream stages. | Derived (ephemeral) | Projection-specific |

### Invariants

1. **Every stage is immutable.** All inputs and outputs are frozen dataclasses. No stage mutates its inputs.

2. **Each stage has its own stable identifier family.** Every stage that produces a distinct object type gets its own ID prefix in the identifier registry.

3. **Gates never mutate inputs.** Gates receive an assessment and return a pass/fail result. They do not modify the assessment or candidate.

4. **Decisions never rewrite assessments.** A decision records the outcome of evaluation but does not alter the assessment that led to it.

5. **Materialization is one-way.** When a materialization stage exists, it transforms an intermediate candidate into a final object. This transformation is irreversible — you cannot reconstruct the intermediate candidate from the materialized object.

6. **Events are the only persistence boundary.** The Event Ledger is the sole source of truth. All upstream objects (candidates, assessments, gates, decisions) are ephemeral — they exist only during pipeline execution and are reconstructed from events when needed.

7. **Projections never feed back into upstream stages.** Projections are derived, read-only views. They inform but do not drive pipeline execution.

### Pipeline Variants

**Simple Pipeline (no materialization):**
```
Candidate → Assessment → Gate → Decision → Event → Projection
```
Used by: Reflections, Memory Lifecycle

**Materialized Pipeline (with materialization):**
```
Candidate → Assessment → Gate → Decision → Materialization → Materialized Object → Event → Projection
```
Used by: Beliefs, Skills, Artifacts, Knowledge Promotion

**Workspace Pipeline (aggregate lifecycle):**
```
Workspace → Session → Snapshot → Context → Package → Event → Projection
```
Used by: Workspace subsystem (structurally identical, different naming)

### Existing Implementations

| Subsystem | Candidate | Assessment | Gate | Decision | Materialization | Object | Event |
|-----------|-----------|------------|------|----------|-----------------|--------|-------|
| Beliefs | CandidateEvent | BeliefAssessor | GateResult | Decision | — | BEL | BEL_CREATED |
| Skills | SkillCandidate | SkillAssessment | GateResult | Decision | — | SKL | SKL_CREATED |
| Artifacts | ArtifactCandidate | ExecutionEvaluation | GateResult | Decision | ArtifactCompiler | ART | ART_CREATED |
| Reflections | ReflectionCandidate | ReflectionRuleEngine | — | ReflectionStatus | — | REFL | REFL_GENERATED |
| Knowledge | PromotionCandidate | PromotionAssessment | PromotionGateResult | PromotionDecision | Materializer | KNOW | KNOW_PROMOTED |
| Memory | ConsolidationCandidate | Evidence evaluation | — | Promotion decision | — | MTRANS | MTRANS_CREATED |
| Workspace | — | — | — | — | — | WS, WSSNP, WSSSN, WSCTX, WSPKG | WORKSPACE_CREATED |

## Rationale

- **Consistency:** New subsystems follow the same pattern, reducing cognitive load and design drift.
- **Reusability:** Common components (gate logic, event emission, projection compilation) can be shared.
- **Testability:** Each stage has clear inputs/outputs, making unit testing straightforward.
- **Auditability:** Every promotion is traceable through its pipeline stages.
- **Event sourcing alignment:** The pattern naturally fits the Event Ledger model — ephemeral pipeline stages produce durable events.

## Consequences

- All new subsystems must follow this pattern. Deviations require a new ADR.
- Existing subsystems that don't follow the pattern exactly (e.g., Reflections) are grandfathered but should not be used as templates for new work.
- Future infrastructure (Connector SDK, Agent Runtime) can reuse pipeline components for connector registration, agent onboarding, and policy approval.
- The pattern becomes a standard vocabulary for discussing lifecycle management across the platform.

## Related Documents

- `docs/v1.2.0_architecture_freeze.md` — Cognitive pipeline freeze
- `docs/v2.0_cognitive_platform_freeze.md` — Knowledge promotion pipeline
- `docs/v2.1_workspace_freeze.md` — Workspace lifecycle
- `docs/adr/ADR-003-cognitive-pipeline-architecture.md` — Original pipeline architecture
