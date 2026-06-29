# Migration Specification: TASK_CREATED v1 → v2

## Identity
- **Migration ID:** TASK_CREATED:v1→v2
- **Status:** Approved
- **Event Type:** TASK_CREATED
- **Current Version:** 1
- **Target Version:** 2
- **Effective Sequence:** 1
  - This migration is active from the first governance snapshot.
  - Historical replay prior to any future governance change also resolves
    TASK_CREATED to schema v2.
- **Supersedes:** None
- **Superseded By:** —

## Structural Changes

| v1 Field       | v2 Field        | Required | Default |
|----------------|-----------------|----------|---------|
| title          | details.summary | Yes      | —       |
| description    | details.body    | No       | ""      |

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
task_created_v1_to_v2
  │
  ▼
v2 (canonical)
```

## Architectural Invariants

- Canonical projection input is schema v2.
- Reducers MUST NOT inspect schema versions.
- ReplayResolver is solely responsible for schema normalization.
- SchemaPolicy is the only authority for canonical version selection.

## Required Verification

✓ Mixed replay
✓ Projection equivalence
✓ Policy Authority (T15)
✓ Migration graph safety
✓ Deterministic replay
✓ Performance baseline
✓ Canonical idempotence
