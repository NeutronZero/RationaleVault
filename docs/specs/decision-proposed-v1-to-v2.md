# Migration Specification: DECISION_PROPOSED v1 → v2

## Identity
- **Migration ID:** DECISION_PROPOSED:v1→v2
- **Status:** Approved
- **Event Type:** DECISION_PROPOSED
- **Current Version:** 1
- **Target Version:** 2
- **Effective Sequence:** 1
- **Supersedes:** None
- **Superseded By:** —

## Structural Changes

| v1 Field     | v2 Field  | Required | Default     |
|--------------|-----------|----------|-------------|
| decision_id  | decision_id | Yes    | —           |
| title        | title     | Yes      | —           |
| description  | description | No    | ""          |
| rationale    | rationale | No       | ""          |
| —            | context   | No       | ""          |
| —            | category  | No       | "general"   |

## Compatibility

| Property                     | Value                                           |
|------------------------------|-------------------------------------------------|
| Native v1 ↔ v2 compatibility | No                                              |
| Replay compatibility         | Yes (via SchemaPolicy + ReplayResolver)         |
| Backward Read                | No                                              |
| Forward Read                 | No                                              |
| Backward Write               | No                                              |
| Mixed Replay                 | Supported via upcaster                          |

## Properties

- **Lossless:** Yes (no data lost in v1→v2)
- **Rollback:** Supported (v2→v1 via reverse mapping)
- **Canonical Schema:** v2

## Migration Chain

```
v1
  │
  ▼
decision_proposed_v1_to_v2
  │
  ▼
v2 (canonical)
```

## Upcaster Contract

```
decision_proposed_v1_to_v2

Input:
    schema_version == 1

Output:
    schema_version == 2

Guarantees:
    - preserves all existing fields
    - adds context=""
    - adds category="general"
    - deterministic
    - idempotent
```

## Independence Invariant

Migration paths are owned per event type.

```
TASK_CREATED:
    1 → 2

DECISION_PROPOSED:
    1 → 2
```

No migration edge may reference another event type.

## Architectural Invariants

- Canonical projection input is schema v2.
- Reducers MUST NOT inspect schema versions.
- SchemaPolicy is the sole authority for canonical version selection.
