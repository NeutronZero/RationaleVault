# Skill Example (Write File)

This directory contains a complete, working reference implementation of a Skill in RationaleVault. 

## What it does
The `write_file_skill` performs actual file I/O. It accepts a filepath and content, writes it to disk, and returns a structured dictionary detailing the success or failure of the operation.

## Reading Guide

Read the files in this order:

1. **`skill.py`**: The skill implementation itself. Notice how it is purely a function wrapped in a decorator that declares permissions.
2. **`tests.py`**: Unit tests verifying the skill logic.

## Why this is different from a Projection
Projections **never** perform I/O. They must be perfectly deterministic for time-travel replay.
Skills are the *only* place where non-deterministic actions (like writing files, reading databases, making network calls) are permitted. When the agent invokes a skill, the framework records the invocation and the result as an immutable event in the ledger.

## Decision Records
Throughout these files, you will find comments formatted as:
```python
# Decision:
# ...
# Why:
# ...
```
These explicitly explain *why* the code is structured the way it is, reinforcing the core architectural laws of RationaleVault.
