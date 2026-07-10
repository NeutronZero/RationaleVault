# Architecture Anti-Patterns

This document catalogues common mistakes made when extending RationaleVault. Teaching what **not** to do is often as valuable as showing the happy path. 

If you find yourself writing code that resembles an anti-pattern below, stop and reconsider your design.

---

## ❌ Reading another projection during `reduce()`

**Example:**
```python
@reducer(MyEvent)
def apply_event(self, state: MyState, event: MyEvent) -> MyState:
    # BAD: Querying the WorkspaceProjection inside a reducer
    workspace_state = self.workspace_projection.get_state()
    state.computed_value = workspace_state.id + event.payload.value
    return state
```

**Why it's wrong:**
Projections must be completely deterministic. If a projection queries another projection during replay, the result will depend on the *current state* of the queried projection, which breaks time-travel debugging and historical replay determinism.

**Correct alternative:**
Embed the necessary information inside the event payload when the event is emitted. The event should contain all facts necessary for the reducer to do its job.

---

## ❌ Performing network I/O in reducers

**Example:**
```python
@reducer(MyEvent)
def apply_event(self, state: MyState, event: MyEvent) -> MyState:
    # BAD: Making an HTTP request during replay
    response = requests.get(f"https://api.example.com/data/{event.payload.id}")
    state.external_data = response.json()
    return state
```

**Why it's wrong:**
Reducers are invoked every time the projection rebuilds from the event log (e.g., during startup, recovery, or branch switching). Network calls during replay would cause massive latency, DDoS external APIs, and destroy determinism (the API might return different data or be offline tomorrow).

**Correct alternative:**
Perform network I/O inside a **Skill** or **Runtime**. If the external data represents a historical fact, the Skill should fetch the data and emit it as an Event. The reducer then reads the static data from the Event payload.

---

## ❌ Using runtime state in snapshots

**Example:**
```python
@dataclass
class MyState:
    item_count: int = 0
    # BAD: Storing a live database connection or threading lock in state
    _db_connection: Any = field(default=None)
```

**Why it's wrong:**
Snapshot stores serialize the state object to disk periodically. Runtime abstractions like thread locks, database connections, open file handles, or network sockets cannot be serialized to JSON/Protobuf, and their state is meaningless across application restarts.

**Correct alternative:**
State objects must only contain pure data (primitives, lists, dicts, dataclasses). If you need a connection pool or lock, store it in the projection class itself (the infrastructure layer), *not* in the State object.

---

## ❌ Putting business logic in CLI / MCP adapters

**Example:**
```python
@cli.command()
def recommend(query: str):
    # BAD: Embedding domain logic directly in the CLI
    projections = get_projections()
    results = [p for p in projections if query in p.name]
    results.sort(key=lambda x: x.score)
    print(results)
```

**Why it's wrong:**
Adapters should be stateless translators. If business logic lives in the CLI, it cannot be reused by the MCP server, unit tests, or web interfaces.

**Correct alternative:**
Move the business logic into a **Runtime** (e.g., `RecommendationRuntime.search()`). The CLI should parse arguments, call the Runtime, and format the output.
