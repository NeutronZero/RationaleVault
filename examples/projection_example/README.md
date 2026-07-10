# Projection Example (Task Tracker)

This directory contains a complete, working reference implementation of a Projection in RationaleVault. It demonstrates the entire engineering workflow for extending the platform with a new capability.

## What it does
The `TaskTrackerProjection` consumes `TaskCreatedEvent` and `TaskCompletedEvent` facts from the event stream and materializes a queryable `TaskTrackerState`.

## Reading Guide

Read the files in this exact order to trace the flow of architecture:

1. **`events.py`**: Defines the immutable facts that enter the system.
2. **`state.py`**: Defines the deterministic data structure we will build.
3. **`projection.py`**: The pure reducers that apply events to the state.
4. **`runtime.py`**: The stateless service that answers queries using the projection.
5. **`test_projection.py`**: Standard unit tests for business logic.
6. **`test_conformance.py`**: Architectural validation to ensure determinism and idempotency.
7. **`benchmark.py`**: Performance gating to ensure O(1) replay speeds.

## Decision Records
Throughout these files, you will find comments formatted as:
```python
# Decision:
# ...
# Why:
# ...
```
These explicitly explain *why* the code is structured the way it is, reinforcing the core architectural laws of RationaleVault.
