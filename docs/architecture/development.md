# Development Guidelines & Policies

When contributing to RationaleVault, adhere to the following architectural policies to maintain the integrity and stability of the system.

## 1. Exception Handling Policy

Broad exceptions represent a massive risk to diagnostic clarity and system stability. 
- **Never use bare `except:`**.
- **Never use `except Exception: pass` in application logic.** If an exception must be ignored, log it at the `DEBUG` level or use `contextlib.suppress(SpecificExpectedError)`.
- **Reserve `except Exception:` exclusively for absolute system boundaries:**
  - The CLI Dispatcher (to prevent ugly stack traces for users).
  - The MCP Tool execution wrappers (to prevent a failing tool from crashing the server).
  - The Skill Platform Sandbox (to prevent host crashes).

When catching expected operational errors (e.g., file locking failures, missing databases), always catch the specific exception (e.g., `sqlite3.OperationalError` or `FileNotFoundError`).

## 2. Dependency Management

RationaleVault is an infrastructure component. It must remain lightweight.
- Core operations (CLI, Event Store, Projections) must rely only on the standard library + explicitly approved minimal dependencies (e.g., `filelock`, `psycopg`).
- Generative components (e.g., `sentence-transformers`, `faiss`) must be sequestered behind Optional Extras `[embed]`.
- Do not introduce new third-party orchestration libraries or runtime frameworks without going through the Architecture Review Gate.

## 3. Architecture Review Gate

Before introducing any new major abstraction (especially across Runtime modules), the following criteria must be evaluated and approved:
- **Measurable Duplication**: Does the new abstraction eliminate at least 3 instances of identical duplicated logic?
- **Coupling Reduction**: Does the abstraction reduce the blast radius of changes?
- **Testability**: Does the abstraction allow easier unit testing via mocks or dependency injection?
- **Boundary Preservation**: Does the abstraction strictly preserve the one-way data flow from the Event Store into the Projections?

## 4. Testing Philosophy

- **Equivalence Testing**: Every reducer must be accompanied by a replay equivalence test. This test verifies that feeding an array of raw events into a fresh reducer instance results in the exact same state as the current projection state.
- **Fixture Isolation**: Ensure that `tests/integration/` uses the `temp_project` fixture exclusively to prevent polluting the local developer's `.rationalevault` store.
- **Marker Discipline**: Use `@pytest.mark.db` and `@pytest.mark.snapshot` to isolate tests that require heavy I/O from fast unit tests.
