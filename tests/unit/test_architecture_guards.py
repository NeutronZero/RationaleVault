from __future__ import annotations
import ast
from pathlib import Path
import pytest
def _get_ast_tree(path: Path) -> ast.AST:
    with open(path, "r", encoding="utf-8") as f:
        return ast.parse(f.read(), filename=str(path))

class TestProjectionLaws:
    def test_projection_layer_imports_guard(self) -> None:
            """
            Asserts that base projections remain completely decoupled from replay pipeline
            internals, upcasting registries, database engines, and governance parameters.
            """
            project_root = Path(__file__).resolve().parent.parent.parent
            projections_dir = project_root / "rationalevault" / "projections"
            assert projections_dir.exists()

            forbidden_replay_imports = {
                "ReplayResolver",
                "SchemaResolver",
                "UpcasterRegistry",
                "ReplayPipeline",
            }

            forbidden_store_imports = {
                "EventStore",
                "SQLiteEventStore",
                "PostgresEventStore",
                "get_event_store",
            }

            orchestration_files = {"pipeline.py", "service.py", "context.py", "continuation.py"}

            violations = []

            for path in projections_dir.glob("*.py"):
                if path.name == "__init__.py":
                    continue

                tree = _get_ast_tree(path)

                for node in ast.walk(tree):
                    # Check direct imports
                    if isinstance(node, ast.Import):
                        for name in node.names:
                            imported_name = name.name.split(".")[-1]
                            # Core projections check
                            if path.name not in orchestration_files:
                                if imported_name in forbidden_replay_imports:
                                    violations.append(f"Forbidden replay import '{imported_name}' in {path.name}")
                                if imported_name in forbidden_store_imports:
                                    violations.append(f"Forbidden store import '{imported_name}' in {path.name}")

                    # Check from-imports
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            for name in node.names:
                                imported_name = name.name
                                if path.name not in orchestration_files:
                                    if imported_name in forbidden_replay_imports:
                                        violations.append(f"Forbidden replay import '{imported_name}' in {path.name}")
                                    if imported_name in forbidden_store_imports:
                                        violations.append(f"Forbidden store import '{imported_name}' in {path.name}")
                                    if imported_name == "ReplayService":
                                        violations.append(f"Forbidden core ReplayService import in base projection {path.name}")

            assert not violations, "Architectural boundary violations found:\n" + "\n".join(violations)



    def test_t14_projection_canonical_boundary_guard(self) -> None:
            """T14: Reducers must not reference schema_version or branch on payload version."""
            project_root = Path(__file__).resolve().parent.parent.parent
            reducers_path = project_root / "rationalevault" / "cognitive_head" / "reducers.py"
            source = reducers_path.read_text(encoding="utf-8")
            tree = ast.parse(source)

            violations = []
            for node in ast.walk(tree):
                # Ban event.schema_version references in reducers
                if isinstance(node, ast.Attribute):
                    if isinstance(node.value, ast.Name) and node.value.id == "event":
                        if node.attr == "schema_version":
                            violations.append(
                                f"Line {node.lineno}: event.schema_version reference"
                            )
                # Ban integer-literal comparisons that look like version branching
                if isinstance(node, ast.Compare):
                    for comparator in node.comparators:
                        if isinstance(comparator, ast.Constant) and isinstance(
                            comparator.value, int
                        ):
                            if comparator.value in (1, 2, 3):
                                violations.append(
                                    f"Line {node.lineno}: possible schema version branch"
                                )

            assert not violations, f"T14 Projection(E) violations: {violations}"



    def test_event_type_local_migration(self) -> None:
            """Migration graphs are local to each event type (T3 + T15).

            Each event type owns an independent migration graph.
            No migration graph may depend upon another event type's graph.
            """
            import ast
            from pathlib import Path

            from rationalevault.schema.events import EventType

            project_root = Path(__file__).resolve().parent.parent.parent
            upcaster_path = project_root / "rationalevault" / "schema" / "upcaster.py"
            if not upcaster_path.exists():
                return

            source = upcaster_path.read_text(encoding="utf-8")
            tree = ast.parse(source)

            # Find all upcaster functions (name contains "v1_to_v2" or similar pattern)
            upcaster_funcs = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and "_to_" in node.name:
                    upcaster_funcs.append(node)

            # Get all event type names
            event_type_names = [et.value for et in EventType]

            for func in upcaster_funcs:
                func_source = ast.get_source_segment(source, func) or ""
                func_name = func.name

                # Determine which event type this upcaster belongs to
                owning_type = None
                for et_name in event_type_names:
                    if et_name.lower() in func_name:
                        owning_type = et_name
                        break

                if owning_type is None:
                    continue  # Can't determine ownership, skip

                # Check that no other event type is referenced
                for et_name in event_type_names:
                    if et_name == owning_type:
                        continue
                    assert et_name not in func_source, (
                        f"Upcaster {func_name} (owns {owning_type}) references "
                        f"another event type: {et_name}"
                    )

            # Verify each migration function has exactly one owning event type
            for func in upcaster_funcs:
                if "_to_" not in func.name:
                    continue
                owning_types = [
                    et_name for et_name in event_type_names
                    if et_name.lower() in func.name
                ]
                assert len(owning_types) == 1, (
                    f"Migration function {func.name} has {len(owning_types)} owning types: "
                    f"{owning_types}. Expected exactly 1."
                )

            # Verify upcasters never import reducers or projections
            # (migration code must remain below the projection layer)
            reducer_imports = ["reducers", "Reducer", "cognitive_head"]
            projection_imports = ["projections", "pipeline", "ReplayPipeline"]
            for func in upcaster_funcs:
                func_source = ast.get_source_segment(source, func) or ""
                for import_name in reducer_imports + projection_imports:
                    assert import_name not in func_source, (
                        f"Upcaster {func.name} references layer above migration: {import_name}"
                    )


class TestDeterminismLaws:
    def test_reducer_purity_ast_guard(self) -> None:
            """
            Asserts that state reducers do not invoke non-pure environment properties
            such as os.environ, datetime.now, time.time, or sys.argv.
            """
            project_root = Path(__file__).resolve().parent.parent.parent
            reducers_path = project_root / "rationalevault" / "cognitive_head" / "reducers.py"

            if not reducers_path.exists():
                return

            tree = _get_ast_tree(reducers_path)
            violations = []

            for node in ast.walk(tree):
                # Prevent calling datetime.now() or datetime.utcnow() directly in reducers
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr in {"now", "utcnow", "environ", "argv"}:
                        violations.append(f"Reducer purity violation: Call to '{node.func.attr}' on line {node.lineno}")

            assert not violations, "Reducers must remain pure functions:\n" + "\n".join(violations)


        # ── T14 Architecture Guards ──────────────────────────────────────────────────



    def test_replay_context_purity(self) -> None:
            """ReplayContext is a pure data structure — frozen, no resolver, no schema logic."""
            from rationalevault.projections.context import ReplayContext
            from rationalevault.schema.policy import SchemaPolicy

            ctx = ReplayContext()

            # Frozen: cannot mutate fields
            try:
                ctx.max_sequence = 999
                assert False, "ReplayContext should be frozen"
            except AttributeError:
                pass

            ctx_with_policy = ReplayContext(
                schema_policy=SchemaPolicy(_schemas={}),
            )
            try:
                ctx_with_policy.schema_policy = SchemaPolicy(_schemas={})
                assert False, "ReplayContext.schema_policy should be frozen"
            except AttributeError:
                pass

            # No resolver attribute
            assert not hasattr(ctx, "resolver"), "ReplayContext must not contain a resolver"
            assert not hasattr(
                ctx_with_policy, "resolver"
            ), "ReplayContext must not contain a resolver"

            # No target_schema_version attribute
            assert not hasattr(
                ctx, "target_schema_version"
            ), "ReplayContext must not contain target_schema_version"
            assert not hasattr(
                ctx_with_policy, "target_schema_version"
            ), "ReplayContext must not contain target_schema_version"


        # ── T15 Architectural Guards ────────────────────────────────────────────────



    def test_reducers_have_zero_schema_knowledge(self) -> None:
            """Reducers MUST NOT reference schema evolution infrastructure (T2)."""
            project_root = Path(__file__).resolve().parent.parent.parent
            reducer_files = [
                project_root / "rationalevault" / "cognitive_head" / "reducers.py",
            ]

            forbidden_names = {
                "schema_version", "SchemaPolicy", "MigrationPath",
                "ReplayResolver", "UpcasterRegistry", "ReplayContext",
            }

            for filepath in reducer_files:
                if not filepath.exists():
                    continue
                tree = ast.parse(filepath.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Name) and node.id in forbidden_names:
                        pytest.fail(
                            f"{filepath}:{node.lineno} references forbidden name '{node.id}'"
                        )
                    if isinstance(node, ast.Attribute) and node.attr in forbidden_names:
                        pytest.fail(
                            f"{filepath}:{node.lineno} references forbidden attribute '{node.attr}'"
                        )



    def test_projection_reducer_purity_guard(self) -> None:
            """
            Executable Projection Laws:
            Reducers must be pure. They cannot import I/O modules, and they cannot 
            call nondeterministic APIs.
            """
            project_root = Path(__file__).resolve().parent.parent.parent

            forbidden_modules = {
                "os", "sys", "pathlib", "shutil", "io", # filesystem
                "requests", "urllib", "http", "socket", "asyncio", # networking
                "sqlite3", "psycopg2", "sqlalchemy", # database
                "subprocess", "threading", "multiprocessing", "concurrent", # threading/subprocess
                "time", "datetime", "random", # time/random
            }

            forbidden_calls = {
                "datetime.now", "datetime.utcnow", "datetime.today",
                "time.time", "time.perf_counter", "time.monotonic",
                "uuid.uuid4", "uuid.uuid1", "uuid4", "uuid1",
                "random.random", "random.randint", "random.choice", "random.shuffle"
            }

            violations = []

            def check_reducer(func_node: ast.FunctionDef, filepath: Path) -> None:
                for node in ast.walk(func_node):
                    if isinstance(node, ast.Import):
                        for name in node.names:
                            base_mod = name.name.split(".")[0]
                            if base_mod in forbidden_modules:
                                violations.append(f"Purity violation: {filepath.name} reduce() imports {base_mod}")
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            base_mod = node.module.split(".")[0]
                            if base_mod in forbidden_modules:
                                violations.append(f"Purity violation: {filepath.name} reduce() imports {base_mod}")
                    elif isinstance(node, ast.Call):
                        try:
                            call_str = ast.unparse(node.func)
                            if call_str in forbidden_calls or any(call_str.endswith("." + fc.split(".")[-1]) for fc in forbidden_calls):
                                violations.append(f"Determinism violation: {filepath.name} reduce() calls {call_str}")
                        except Exception:
                            pass

            # Check all files in rationalevault and examples
            dirs_to_check = [
                project_root / "rationalevault",
                project_root / "examples"
            ]

            for check_dir in dirs_to_check:
                for path in check_dir.glob("**/*.py"):
                    try:
                        tree = _get_ast_tree(path)
                    except Exception:
                        continue

                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            # Check if it inherits from Projection or has a reduce method
                            for item in node.body:
                                if isinstance(item, ast.FunctionDef) and item.name == "reduce":
                                    check_reducer(item, path)

            assert not violations, "Executable Projection Laws Violations:\n" + "\n".join(violations)

class TestLayeringLaws:
    def test_macro_architecture_layer_guard(self) -> None:
            """
            Enforces the layer boundaries:
            - Platform/Persistence must not depend on Presentation
            - Persistence must not depend on Runtime
            - Foundation must not depend on higher layers
            """
            project_root = Path(__file__).resolve().parent.parent.parent
            rv_dir = project_root / "rationalevault"

            layers = {
                "presentation": {"cli", "mcp", "diagnostics", "vendor"},
                "runtime": {"runtime", "governance", "recommendation", "recommendations", "timeline", "extraction"},
                "platform": {"projection_platform", "cognitive_head", "skill_platform", "memory", "knowledge", "embedding", "skills", "projections", "schema", "evaluation"},
                "persistence": {"db", "transport", "workspace"},
                "foundation": {"telemetry"}
            }

            forbidden_imports = {
                "platform": {"cli", "mcp", "diagnostics", "vendor"},
                "persistence": {"cli", "mcp", "diagnostics", "vendor", "runtime", "governance", "recommendation", "timeline", "extraction"},
                "foundation": {"cli", "mcp", "diagnostics", "vendor", "runtime", "governance", "recommendation", "timeline", "extraction", "projection_platform", "cognitive_head", "skill_platform", "memory", "knowledge", "embedding", "skills", "projections", "evaluation", "schema", "db", "workspace"}
            }

            pkg_to_layer = {}
            for layer, pkgs in layers.items():
                for pkg in pkgs:
                    pkg_to_layer[pkg] = layer

            violations = []

            for path in rv_dir.glob("**/*.py"):
                rel_parts = path.relative_to(rv_dir).parts
                if not rel_parts:
                    continue

                pkg = rel_parts[0]
                if pkg not in pkg_to_layer:
                    continue

                layer = pkg_to_layer[pkg]
                forbidden = forbidden_imports.get(layer, set())

                try:
                    tree = _get_ast_tree(path)
                except Exception:
                    continue

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for name in node.names:
                            if name.name.startswith("rationalevault."):
                                target_pkg = name.name.split(".")[1]
                                if target_pkg in forbidden:
                                    violations.append(f"Layer violation: {pkg} ({layer}) imported {target_pkg} in {path.name}")

                    elif isinstance(node, ast.ImportFrom):
                        if node.module and node.module.startswith("rationalevault."):
                            target_pkg = node.module.split(".")[1]
                            if target_pkg in forbidden:
                                violations.append(f"Layer violation: {pkg} ({layer}) imported {target_pkg} in {path.name}")

            assert not violations, "Macro Layer Violations:\n" + "\n".join(violations)


class TestAPILaws:
    def test_replay_canonical_gateway_guard(self) -> None:
            """
            Asserts that compilers and query paths ONLY query event streams via ReplayService.
            No direct imports of ReplayPipeline or ReplayResolver are permitted outside projections.
            """
            project_root = Path(__file__).resolve().parent.parent.parent
            check_paths = [
                project_root / "rationalevault" / "cognitive_head",
                project_root / "rationalevault" / "knowledge",
            ]

            forbidden_replay_internals = {
                "ReplayPipeline",
                "ReplayResolver",
                "SchemaResolver",
                "UpcasterRegistry",
            }

            violations = []

            for base_path in check_paths:
                for path in base_path.glob("**/*.py"):
                    tree = _get_ast_tree(path)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for name in node.names:
                                imported_name = name.name.split(".")[-1]
                                if imported_name in forbidden_replay_internals:
                                    violations.append(f"Forbidden replay internal '{imported_name}' in {path.relative_to(project_root)}")
                        elif isinstance(node, ast.ImportFrom):
                            for name in node.names:
                                imported_name = name.name
                                if imported_name in forbidden_replay_internals:
                                    violations.append(f"Forbidden replay internal '{imported_name}' in {path.relative_to(project_root)}")

            assert not violations, "Compilers must only use ReplayService for replay operations:\n" + "\n".join(violations)



    def test_t14_reducer_imports_no_schema_version(self) -> None:
            """T14: Reducers must not import SchemaPolicy or SchemaVersion types."""
            project_root = Path(__file__).resolve().parent.parent.parent
            reducers_path = project_root / "rationalevault" / "cognitive_head" / "reducers.py"
            tree = _get_ast_tree(reducers_path)

            forbidden = {"SchemaPolicy", "SchemaPolicyFactory", "SchemaVersion"}
            violations = []

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        if name.name.split(".")[-1] in forbidden:
                            violations.append(
                                f"Line {node.lineno}: forbidden import '{name.name}'"
                            )
                elif isinstance(node, ast.ImportFrom):
                    for name in node.names:
                        if name.name in forbidden:
                            violations.append(
                                f"Line {node.lineno}: forbidden from-import '{name.name}'"
                            )

            assert not violations, f"T14 reducer import violations: {violations}"



    def test_schema_policy_immutability(self) -> None:
            """SchemaPolicy is an immutable value object — frozen dataclass."""
            from rationalevault.schema.policy import SchemaPolicy, EventSchema, MigrationPath

            policy = SchemaPolicy(_schemas={})
            try:
                policy._schemas = {}
                assert False, "SchemaPolicy._schemas should be frozen"
            except AttributeError:
                pass

            event_schema = EventSchema(
                event_type=__import__(
                    "rationalevault.schema.events", fromlist=["EventType"]
                ).EventType.TASK_CREATED,
                latest_version=1,
                migration_path=MigrationPath(),
            )
            try:
                event_schema.latest_version = 2
                assert False, "EventSchema should be frozen"
            except AttributeError:
                pass

            step = __import__(
                "rationalevault.schema.policy", fromlist=["MigrationStep"]
            ).MigrationStep(from_version=1, to_version=2)
            try:
                step.from_version = 3
                assert False, "MigrationStep should be frozen"
            except AttributeError:
                pass

            path = MigrationPath()
            try:
                path.steps = ()
                assert False, "MigrationPath should be frozen"
            except AttributeError:
                pass



    def test_reducers_never_implement_compatibility_logic(self) -> None:
            """Reducers MUST NOT branch on payload shape (T14).

            Detects semantic patterns, not field names.
            """
            project_root = Path(__file__).resolve().parent.parent.parent
            reducer_files = [
                project_root / "rationalevault" / "cognitive_head" / "reducers.py",
            ]

            for filepath in reducer_files:
                if not filepath.exists():
                    continue
                source = filepath.read_text(encoding="utf-8")
                tree = ast.parse(source)

                for node in ast.walk(tree):
                    # Detect "key" in dict conditionals (compatibility branching)
                    if isinstance(node, ast.Compare):
                        for op in node.ops:
                            if isinstance(op, ast.In):
                                # "key" in payload pattern
                                pytest.fail(
                                    f"{filepath}:{node.lineno} branches on payload structure"
                                )



    def test_resolver_is_policy_driven(self) -> None:
            """ReplayResolver MUST execute policy, not define it (T15).

            Detects semantic patterns, not event type names.
            """
            project_root = Path(__file__).resolve().parent.parent.parent
            resolver_path = project_root / "rationalevault" / "schema" / "resolver.py"

            if not resolver_path.exists():
                pytest.skip("resolver.py not found")

            source = resolver_path.read_text(encoding="utf-8")
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if node.value.endswith("_CREATED") or node.value.endswith("_RECORDED"):
                        pytest.fail(
                            f"{resolver_path}:{node.lineno} hardcodes event type '{node.value}'"
                        )

                if isinstance(node, ast.Name) and node.id == "EVOLVED_EVENT_TYPES":
                    pytest.fail(
                        f"{resolver_path}:{node.lineno} references EVOLVED_EVENT_TYPES"
                    )

                if isinstance(node, ast.Dict):
                    keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
                    if all(isinstance(k, int) for k in keys) and len(keys) > 1:
                        pytest.fail(
                            f"{resolver_path}:{node.lineno} contains hardcoded version table"
                        )



    def test_schema_policy_is_sole_authority(self) -> None:
            """SchemaPolicy MUST be the only source of latest-version decisions (T15)."""
            project_root = Path(__file__).resolve().parent.parent.parent

            resolver_path = project_root / "rationalevault" / "schema" / "resolver.py"
            if resolver_path.exists():
                resolver_source = resolver_path.read_text(encoding="utf-8")
                assert "SchemaPolicy" in resolver_source, (
                    "ReplayResolver must depend on SchemaPolicy"
                )

            pipeline_path = project_root / "rationalevault" / "projections" / "pipeline.py"
            if pipeline_path.exists():
                pipeline_source = pipeline_path.read_text(encoding="utf-8")
                assert "schema_policy" in pipeline_source, (
                    "ReplayPipeline must construct resolver from schema_policy"
                )

            factory_path = project_root / "rationalevault" / "schema" / "factory.py"
            if factory_path.exists():
                factory_source = factory_path.read_text(encoding="utf-8")
                assert "schema_versions" in factory_source, (
                    "SchemaPolicyFactory must read schema_versions from GovernanceState"
                )



    def test_schema_policy_is_immutable(self) -> None:
            """SchemaPolicy is a snapshot, never a mutable session object (T1)."""
            from rationalevault.schema.policy import SchemaPolicy, EventSchema, MigrationPath
            from rationalevault.schema.events import EventType

            assert hasattr(SchemaPolicy, "__dataclass_params__")
            assert SchemaPolicy.__dataclass_params__.frozen is True

            policy = SchemaPolicy(_schemas={
                EventType.TASK_CREATED: EventSchema(
                    event_type=EventType.TASK_CREATED,
                    latest_version=2,
                    migration_path=MigrationPath(steps=()),
                )
            })

            with pytest.raises(AttributeError):
                policy._schemas = {}

            assert hasattr(EventSchema, "__dataclass_params__")
            assert EventSchema.__dataclass_params__.frozen is True

            assert hasattr(MigrationPath, "__dataclass_params__")
            assert MigrationPath.__dataclass_params__.frozen is True


        # ── T3+T15 Architectural Guards ──────────────────────────────────────────────



    def test_examples_import_strictness_guard(self) -> None:
            """
            Examples must only import from the public API roots.
            """
            project_root = Path(__file__).resolve().parent.parent.parent
            examples_dir = project_root / "examples"

            allowed_roots = {
                "rationalevault.projection_platform",
                "rationalevault.schema",
                "rationalevault.skills",
                "rationalevault.memory"
            }

            violations = []

            for path in examples_dir.glob("**/*.py"):
                try:
                    tree = _get_ast_tree(path)
                except Exception:
                    continue

                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for name in node.names:
                            if name.name.startswith("rationalevault."):
                                if name.name not in allowed_roots:
                                    violations.append(f"Example {path.relative_to(project_root)} imported non-root module: {name.name}")
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and node.module.startswith("rationalevault."):
                            if node.module not in allowed_roots:
                                violations.append(f"Example {path.relative_to(project_root)} imported non-root module: {node.module}")

            assert not violations, "Example Import Strictness Violations:\n" + "\n".join(violations)

