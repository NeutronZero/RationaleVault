# Projection Lifecycle

In RationaleVault, a projection is a strictly deterministic derived view of the event store. The lifecycle of a projection dictates how events are transformed into state, how that state is cached, and when it is invalidated.

## 1. The Event Stream
Every action in the system is stored as an immutable event with a strictly monotonically increasing sequence ID.

## 2. Compilation and Bootstrapping
When a projection is requested (e.g., the `GovernanceProjection` or the `CognitiveHead`), the Projection Manager initiates the compiler.
1. The compiler checks if a cached Snapshot exists for this projection signature.
2. If a valid Snapshot exists, the projection's internal state is hydrated directly from the cache, fast-forwarding the sequence pointer.
3. If no Snapshot exists or it has been invalidated, the compiler starts from Sequence ID 0.

## 3. Reduction
The projection subscribes to the event store starting from its last known sequence ID.
For every new event:
- The event is routed to the projection's registered **Reducer**.
- The Reducer MUST be a pure function. It accepts the `CurrentState` and the `Event`, and returns the `NextState`.
- Any external I/O, network calls, or non-deterministic logic (like `datetime.now()`) inside a Reducer is considered an architectural violation and will break replay equivalence.

## 4. Snapshotting (Caching)
To avoid replaying hundreds of thousands of events on every boot, projections are snapshotted.
- **Snapshot Frequency**: Controlled by the `SnapshotPolicy` (e.g., every 1000 events or every hour).
- **Snapshot Structure**: A snapshot contains the Projection Name, the Last Sequence ID processed, and the serialized internal state payload.
- **Hash Verification**: A hash of the payload and reducer version is used to verify integrity.

## 5. Invalidation
Snapshots are automatically invalidated and discarded if:
- The underlying Reducer code changes (detectable via versioning or schema changes).
- The Event Store detects a sequence anomaly or a storage migration that alters history.
- The user manually clears the cache using diagnostic commands.

When invalidated, the projection gracefully degrades to rebuilding from Sequence 0. This rebuild is entirely transparent to the runtime consuming the projection.
