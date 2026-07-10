# Projection Checklist

Use this checklist to architecturally validate any new Projection before submitting a pull request.

- [ ] **Reducer is pure:** Does the reducer modify state directly without external I/O?
- [ ] **Replay deterministic:** Will this projection build the exact same state if replayed from the same event stream 100 times?
- [ ] **No runtime dependencies during replay:** Did you verify there are no hidden network requests, database lookups, or random number generators used during reduction?
- [ ] **Snapshot serialization deterministic:** Is the `State` object composed entirely of JSON-serializable dataclasses, primitives, dicts, and lists?
- [ ] **State equality implemented:** Does the State object correctly implement equality (`__eq__`) so the system can verify when state actually changes?
- [ ] **Conformance passes:** Did you run the projection conformance suite against your projection class? (`pytest tests/unit/conformance/`)
- [ ] **Architecture documented:** If this projection introduces a new semantic pattern, is it documented?
- [ ] **Benchmarks added:** Did you add a performance benchmark to track the events-per-second replay speed?
- [ ] **CLI optional:** Can the core capabilities of your projection be used perfectly *without* the CLI adapter?
- [ ] **MCP optional:** Can the core capabilities of your projection be used perfectly *without* the MCP adapter?
