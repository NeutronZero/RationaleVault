# ADR-028: Certification Platform Freeze and Ecosystem Governance

**Date**: 2026-07-10
**Status**: Accepted

## Context

RationaleVault has reached a point of architectural maturity where internal capabilities—such as the Projection Platform, Snapshots, and Replay Engine—are stabilized and governed by explicit code contracts (e.g., AST guards, performance regression thresholds). 

To transition RationaleVault into an externally consumable ecosystem, we have introduced the **Framework Certification Suite** (`rationalevault certify`). This suite enforces the same architectural laws and governance checks on third-party plugins, projections, skills, and extensions as we do on the internal codebase.

As the certification engine scales to support the ecosystem, there is a risk that the engine itself becomes a sprawling, monolithic orchestrator containing domain-specific logic for every possible new extension type. We need a clear governance policy to prevent this, ensuring the certification suite remains small, stable, and highly extensible.

## Decision

We will explicitly **freeze the Certification Engine** (`CertificationEngine`) and define **Rule Packs as the sole extension mechanism** for the certification subsystem.

### 1. Engine Freeze
- The orchestration pipeline (`Discovery → Static → Compatibility → Runtime → Reporting`) is **frozen**.
- The `CertificationEngine` class, stage interfaces (`CertificationStage`), and `CertificationContext` are frozen for all but backwards-compatible bug fixes and strictly additive telemetry metadata.

### 2. Rule Catalog Versioning
- The core engine, report schema, and the "Rule Catalog" (the collection of rules enforced by the system) will be versioned independently.
- Certification reports will explicitly declare the versions used (e.g., Engine v1.0, Rule Catalog v1, Schema v1).

### 3. Rule Packs as the Extension Mechanism
All future evolution of the certification subsystem must happen **around** the engine, not **inside** it. This follows a strict hierarchy:

```text
Engine (Frozen)
    ↓
ArtifactType (e.g., PROJECTION, SKILL, STORAGE_BACKEND)
    ↓
RulePack (e.g., ProjectionPack, DocumentationPack)
    ↓
CertificationRule (e.g., "Reducer Purity")
    ↓
CertificationCheck (e.g., "CheckNoDatetime", "CheckNoInternalImports")
```

To support a new type of ecosystem extension, developers will simply register a new `ArtifactType` and bind it to a custom `RulePack` containing relevant `CertificationCheck`s. The engine orchestrator requires zero modifications to support this.

### 4. Certification Determinism
The certification pipeline guarantees absolute determinism. Given an identical input extension, framework version, and rule catalog, the `CertificationEngine` will produce an identical set of findings and scores. Only inherently variable metadata (such as timestamps, elapsed runtime, or environment specs) may change between identical runs.

### 5. Semantics of Findings
We explicitly preserve the distinction between diagnostic severities to build trust with downstream developers:
- **INFO**: Informational observations.
- **WARNING**: Quality issues and best-practice deviations (e.g., missing docstrings) that do *not* block certification.
- **ERROR**: Architectural violations (e.g., impure reducers) that *block* certification.

### 6. RV Codes as Public API
The stable finding codes (e.g., `RV010`, `RV011`) are officially part of RationaleVault's public API contract.
- Codes will never be reused.
- The semantic meaning of an existing code will not change.
- Obsolete rules will be formally deprecated rather than redefined.

## Consequences

**Positive**:
- The `CertificationEngine` avoids the "god class" anti-pattern and remains easily testable.
- External developers can write and register their own `RulePack`s to enforce internal company policies alongside RationaleVault defaults.
- The stable output schema, deterministic results, and immutable RV codes allow enterprises to confidently integrate `rationalevault certify` into strict CI/CD pipelines.

**Negative**:
- Structural changes to how extensions are evaluated require creating entirely new `CertificationStage`s or bypassing the engine entirely, imposing a high barrier to radical changes in the certification flow.
