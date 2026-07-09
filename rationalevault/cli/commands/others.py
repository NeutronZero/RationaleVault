"""
RationaleVault Command Line Interface (CLI) Entry Point.
"""
from __future__ import annotations
from rationalevault.logging import get_logger

logger = get_logger(__name__)



import argparse
import sys
import uuid
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


from rationalevault.cli.utils.project import _resolve_project_id


def cmd_install(args: argparse.Namespace) -> None:
    project_root = Path.cwd()
    relay_dir = project_root / ".rationalevault"
    
    if not relay_dir.exists():
        logger.error("Relay has not been initialized. Run 'rationalevault init' first.")
        sys.exit(1)

    platform = args.platform.lower()
    skill_file = relay_dir / "RELAY_SKILL.md"
    skill_text = skill_file.read_text(encoding="utf-8") if skill_file.exists() else "Default RationaleVault Skill"

    if platform == "claude":
        target = project_root / "CLAUDE.md"
        target.write_text(f"# Claude Code Rules\n\n{skill_text}", encoding="utf-8")
        print(f"[SUCCESS] Installed Claude Code adapter in: {target.relative_to(project_root)}")
    elif platform == "cursor":
        rules_dir = project_root / ".cursor" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        target = rules_dir / "rationalevault.mdc"
        target.write_text(f"# Cursor Custom Rules\n\n{skill_text}", encoding="utf-8")
        print(f"[SUCCESS] Installed Cursor adapter in: {target.relative_to(project_root)}")
    elif platform == "opencode":
        target = project_root / "AGENTS.md"
        target.write_text(f"# OpenCode Rules\n\n{skill_text}", encoding="utf-8")
        print(f"[SUCCESS] Installed OpenCode adapter in: {target.relative_to(project_root)}")
    elif platform == "copilot":
        target = project_root / "copilot-instructions.md"
        target.write_text(f"# Copilot Instructions\n\n{skill_text}", encoding="utf-8")
        print(f"[SUCCESS] Installed Copilot adapter in: {target.relative_to(project_root)}")
    else:
        logger.error(f"Unknown platform '{args.platform}'. Supported: claude, cursor, opencode, copilot.")
        sys.exit(1)


def cmd_uninstall(args: argparse.Namespace) -> None:
    project_root = Path.cwd()
    relay_dir = project_root / ".rationalevault"

    # Remove rule files in root
    for file_name in ["CLAUDE.md", "AGENTS.md", "copilot-instructions.md"]:
        p = project_root / file_name
        if p.exists():
            p.unlink()
            print(f"Removed {file_name}")

    # Remove cursor rules
    cursor_rules = project_root / ".cursor" / "rules" / "rationalevault.mdc"
    if cursor_rules.exists():
        cursor_rules.unlink()
        print("Removed .cursor/rules/relay.mdc")

    # Remove .relay dir
    if relay_dir.exists():
        import shutil
        shutil.rmtree(relay_dir)
        print("Removed .rationalevault/ configuration directory.")

    print("[SUCCESS] RationaleVault has been uninstalled from this project.")


def cmd_generate_adapters(args: argparse.Namespace) -> None:
    project_root = Path.cwd()
    relay_dir = project_root / ".rationalevault"
    
    if not relay_dir.exists():
        logger.error("Relay has not been initialized. Run 'rationalevault init' first.")
        sys.exit(1)

    skill_file = relay_dir / "RELAY_SKILL.md"
    skill_text = skill_file.read_text(encoding="utf-8") if skill_file.exists() else ""

    adapters_dir = relay_dir / "adapters"
    adapters_dir.mkdir(parents=True, exist_ok=True)

    # Compile Claude Adapter
    (adapters_dir / "CLAUDE.md").write_text(f"# Claude Code Instructions\n\n{skill_text}", encoding="utf-8")
    # Compile Cursor Adapter
    (adapters_dir / "cursor_rules.md").write_text(f"# Cursor Instructions\n\n{skill_text}", encoding="utf-8")
    # Compile Copilot Adapter
    (adapters_dir / "copilot-instructions.md").write_text(f"# Copilot Instructions\n\n{skill_text}", encoding="utf-8")
    # Compile OpenCode Adapter
    (adapters_dir / "opencode_instructions.md").write_text(f"# OpenCode Instructions\n\n{skill_text}", encoding="utf-8")

    print(f"[SUCCESS] Compiled adapters in: {adapters_dir.relative_to(project_root)}")


def cmd_migrate_storage(args: argparse.Namespace) -> None:
    from rationalevault.db.sqlite_store import SQLiteEventStore
    from rationalevault.db.postgres_store import PostgresEventStore
    import yaml

    project_root = Path.cwd()
    project_yaml_path = project_root / ".rationalevault" / "project.yaml"
    if not project_yaml_path.exists():
        logger.error("project.yaml not found. Run 'rationalevault init' first.")
        sys.exit(1)

    try:
        with open(project_yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except Exception as ex:
        print(f"Error reading project.yaml: {ex}")
        sys.exit(1)

    pid_str = config.get("project_id")
    if not pid_str:
        logger.error("project_id not found in project.yaml")
        sys.exit(1)
    
    pid = uuid.UUID(pid_str)

    src_type = args.frm.lower()
    tgt_type = args.to.lower()

    if src_type == tgt_type:
        logger.error("Source and target backends must be different.")
        sys.exit(1)

    # Resolve source store
    if src_type == "sqlite":
        storage_config = config.get("storage", {})
        db_path = storage_config.get("database", ".relay/relay.db")
        src_store = SQLiteEventStore(db_path=db_path)
    elif src_type == "postgres":
        src_store = PostgresEventStore()
    else:
        logger.error(f"Unknown source backend '{src_type}'")
        sys.exit(1)

    # Resolve target store
    if tgt_type == "sqlite":
        tgt_store = SQLiteEventStore(db_path=".relay/relay.db")
    elif tgt_type == "postgres":
        tgt_store = PostgresEventStore()
    else:
        logger.error(f"Unknown target backend '{tgt_type}'")
        sys.exit(1)

    print(f"Migrating events for project {pid} from {src_type} to {tgt_type}...")

    try:
        events = src_store.get_project_stream(pid)
        print(f"Found {len(events)} events in source store.")
    except Exception as ex:
        print(f"Error reading from source store: {ex}")
        sys.exit(1)

    migrated_count = 0
    for ev in events:
        try:
            tgt_store.append_event(
                project_id=ev.project_id,
                stream_id=ev.stream_id,
                event_type=ev.event_type,
                payload=ev.payload,
                metadata=ev.metadata,
                parent_id=ev.parent_id
            )
            migrated_count += 1
        except Exception as ex:
            print(f"Error appending event {ev.id} to target store: {ex}")
            sys.exit(1)

    # Update project.yaml config with new default
    config["storage"] = {
        "backend": tgt_type,
        "database": ".relay/relay.db" if tgt_type == "sqlite" else None
    }
    try:
        with open(project_yaml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f)
        print(f"Updated project.yaml to use '{tgt_type}' as default backend.")
    except Exception as ex:
        print(f"Warning: Failed to update project.yaml: {ex}")

    print(f"[SUCCESS] Migrated {migrated_count} of {len(events)} events.")


def cmd_context(args: argparse.Namespace) -> None:
    """Compile and display unified context from events, memories, and knowledge."""
    import json
    from rationalevault.knowledge.context_compiler import compile_context, ContextMode
    from rationalevault.knowledge.evaluation_i5 import compute_context_metrics
    from rationalevault.memory.query_analyzer import RetrievalProfile

    # Resolve project ID
    project_id = _resolve_project_id()

    mode_val = ContextMode(args.mode) if getattr(args, "mode", None) else ContextMode.STANDARD
    profile_val = RetrievalProfile(args.profile) if getattr(args, "profile", None) else None

    package = compile_context(
        query=args.query,
        project_id=project_id,
        mode=mode_val,
        profile=profile_val,
        total_slices=args.limit,
    )

    # Agent-specific compilation
    if args.agent:
        import sys, io
        from rationalevault.compilers.registry import get_context_compiler
        compiler = get_context_compiler(args.agent)
        output = compiler.compile(package)

        if args.output == "json":
            print(json.dumps(output.to_dict(), indent=2))
        else:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
            print(output.rendered_content)
        return

    if args.output == "json":
        print(json.dumps(package.to_dict(), indent=2))
    elif args.output == "summary":
        print("Context Package Summary:")
        print("=" * 60)
        print(f"Context ID: {package.context_id}")
        print(f"Query:      {package.query}")
        print(f"Profile:    {package.profile}")
        print(f"Created:    {package.created_at}")
        print(f"Sources:    {package.source_counts}")
        print("-" * 60)
        for i, c in enumerate(package.citations[:20], 1):
            print(f"  {i:2d}. [{c.source_type:<10}] score={c.relevance_score:.2f} | {c.title[:50]}")
        print("-" * 60)
        print("Inclusion Reasons:")
        for reason in package.inclusion_reasons:
            print(f"  - {reason}")
        print("-" * 60)
        print(f"Timing: {json.dumps(package.timing, indent=2)}")
    elif args.output == "evaluate":
        from rationalevault.knowledge.evaluation_i5 import extract_keywords_from_query
        keywords = extract_keywords_from_query(args.query)
        metrics = compute_context_metrics(package, keywords=keywords)
        print("Context Construction Metrics:")
        print("=" * 60)
        print(f"Context Completeness:   {metrics.context_completeness:.2%}")
        print(f"Source Traceability:    {metrics.source_traceability:.2%}")
        print(f"Source Balance:         {metrics.source_balance:.2%}")
        print(f"Context Precision:      {metrics.context_precision:.2%}")
        print(f"Context Redundancy:     {metrics.context_redundancy:.2%}")
        print(f"Avg Provenance Depth:   {metrics.citations_with_trace}/{metrics.total_citations}")
        print(f"Determinism:            {metrics.blending_determinism:.2%}")
        print(f"Timing Budget:          {'PASS' if metrics.within_timing_budget else 'FAIL'} ({metrics.total_ms:.1f}ms)")
        passed, failures = metrics.passes_exit_gates()
        if passed:
            print("\n[PASS] All Sprint I5 exit gates passed.")
        else:
            print(f"\n[FAIL] Exit gates failed: {', '.join(failures)}")

        # Run benchmark evaluation if available
        from rationalevault.evaluation.context_benchmark_schema import ContextBenchmark
        from rationalevault.evaluation.context_evaluator import ContextEvaluator, check_context_gates
        benchmark_dir = Path.cwd() / "rationalevault" / "evaluation" / "context_benchmarks"
        if benchmark_dir.exists():
            benchmarks = []
            for p in benchmark_dir.glob("**/*.json"):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        benchmarks.append(ContextBenchmark.from_dict(json.load(f)))
                except Exception:
                    pass
            if benchmarks:
                print("\n--- Context Benchmark Evaluation ---")
                for benchmark in benchmarks:
                    evaluator = ContextEvaluator(benchmark)
                    result = evaluator.evaluate(package)
                    gate_passed, gate_failures = check_context_gates(result)
                    status = "[PASS]" if gate_passed else "[FAIL]"
                    print(f"\nBenchmark: {benchmark.benchmark_id} v{benchmark.benchmark_version} {status}")
                    print(f"  Completeness:  {result.completeness:.2%}")
                    print(f"  Precision:     {result.precision:.2%}")
                    print(f"  Keyword Recall: {result.keyword_recall:.2%}")
                    print(f"  F1:            {result.f1_score:.2%}")
                    print(f"  Redundancy:    {result.redundancy:.2%}")
                    print(f"  Source Balance: {result.source_balance:.2%}")
                    print(f"  Determinism:   {result.determinism_score:.2%}")
                    print(f"  Profile Match: {'Yes' if result.profile_correct else 'No'}")
                    if not gate_passed:
                        print(f"  Gate Failures: {', '.join(gate_failures)}")


def cmd_graph(args: argparse.Namespace) -> None:
    from rationalevault.knowledge.factory import get_knowledge_provider
    from rationalevault.knowledge.relations import detect_relations
    from rationalevault.knowledge.graph import GraphProjection
    from rationalevault.knowledge.graph_evaluation import evaluate_graph_projection, check_graph_gates
    import json
    
    project_root = Path.cwd()
    graph_file = project_root / ".rationalevault" / "graph.json"
    
    if args.graph_command == "build":
        provider = get_knowledge_provider()
        knowledge = provider.get_all_knowledge()
        relations = detect_relations(knowledge)
        
        # Build projection
        projection = GraphProjection.build(knowledge, relations)
        
        # Evaluate
        projection2 = GraphProjection.build(knowledge, relations)
        eval_result = evaluate_graph_projection(projection, knowledge, relations, previous_projection=projection2)
        
        # Save to disk
        graph_file.parent.mkdir(parents=True, exist_ok=True)
        with open(graph_file, "w", encoding="utf-8") as f:
            f.write(projection.export_json())
            
        print(f"[SUCCESS] Projected knowledge graph built and saved to {graph_file.relative_to(project_root)}")
        print(f"Nodes:                  {projection.node_count}")
        print(f"Edges:                  {projection.edge_count}")
        print(f"Graph ID:               {projection.graph_id}")
        print("-" * 50)
        print("Graph Projection Metrics:")
        print(f"  Node Coverage:        {eval_result.node_coverage:.2%}")
        print(f"  Edge Coverage:        {eval_result.edge_coverage:.2%}")
        print(f"  Referential Integrity: {eval_result.referential_integrity:.2%}")
        print(f"  Determinism Score:    {eval_result.determinism_score:.2%}")
        print(f"  Graph Density:        {eval_result.density:.4f}")
        print(f"  Connected Components:  {eval_result.connected_components}")
        print(f"  Orphan Node Pct:      {eval_result.orphan_pct:.2%} ({eval_result.orphan_count} nodes)")
        print(f"  Largest Component Pct:{eval_result.largest_component_pct:.2%}")
        
        passed, failures = check_graph_gates(eval_result)
        if passed:
            print("\n[PASS] All Sprint I7.5 Exit Gates passed.")
        else:
            print(f"\n[FAIL] Exit gates failed: {', '.join(failures)}")

    elif args.graph_command == "stats":
        if not graph_file.exists():
            logger.error("Graph has not been built yet. Run 'rationalevault graph build' first.")
            sys.exit(1)
            
        with open(graph_file, "r", encoding="utf-8") as f:
            projection = GraphProjection.from_dict(json.load(f))
            
        stats = projection.stats()
        provider = get_knowledge_provider()
        knowledge = provider.get_all_knowledge()
        relations = detect_relations(knowledge)
        eval_result = evaluate_graph_projection(projection, knowledge, relations, previous_projection=projection)
        
        print("RationaleVault Knowledge Graph Statistics:")
        print("=" * 45)
        print(f"Graph ID:               {projection.graph_id}")
        print(f"Nodes Count:            {projection.node_count}")
        print(f"Edges Count:            {projection.edge_count}")
        print(f"Graph Density:          {stats['density']:.4f}")
        print(f"Connected Components:   {stats['connected_components']}")
        print(f"Orphan Node Count:      {stats['orphan_count']}")
        print(f"Orphan Node Pct:        {stats['orphan_pct']:.2%}")
        print(f"Largest Component Pct:  {stats['largest_component_pct']:.2%}")
        print("-" * 45)
        
        passed, failures = check_graph_gates(eval_result)
        if passed:
            print("[PASS] All Sprint I7.5 Exit Gates passed.")
        else:
            print(f"[FAIL] Exit gates failed: {', '.join(failures)}")

    elif args.graph_command == "query":
        if not graph_file.exists():
            logger.error("Graph has not been built yet. Run 'rationalevault graph build' first.")
            sys.exit(1)
            
        with open(graph_file, "r", encoding="utf-8") as f:
            projection = GraphProjection.from_dict(json.load(f))
            
        node = projection.query_node(args.node_id)
        if not node:
            logger.error(f"Node with ID/Prefix '{args.node_id}' not found.")
            sys.exit(1)
            
        print(f"Knowledge Node {node.id}")
        print("=" * 60)
        print(f"Title:            {node.title}")
        print(f"Type:             {node.type}")
        print(f"Domain:           {node.domain}")
        print(f"Importance:       {node.importance}")
        print(f"Confidence:       {node.confidence:.2f}")
        print(f"Evidence Count:   {node.evidence_count}")
        print(f"Source Events:    {node.source_event_count}")
        print(f"Tags:             {', '.join(node.tags)}")
        print(f"Original ID:      {node.metadata.get('original_id')}")
        print("=" * 60)
        
        if args.depth > 0:
            sub = projection.neighbors(node.id, depth=args.depth)
            print(f"\nNeighbors up to depth {args.depth}:")
            print(f"  Nodes: {sub.node_count} | Edges: {sub.edge_count}")
            print("-" * 60)
            for n in sub.nodes:
                if n.id != node.id:
                    print(f"  - [{n.type}] {n.title} (ID: {n.id[:8]})")
            print("-" * 60)
            for e in sub.edges:
                print(f"  {e.source[:8]} -->|{e.relation_type.value}| {e.target[:8]} (conf: {e.confidence:.2f})")

    elif args.graph_command == "query-path":
        if not graph_file.exists():
            logger.error("Graph has not been built yet. Run 'rationalevault graph build' first.")
            sys.exit(1)
            
        with open(graph_file, "r", encoding="utf-8") as f:
            projection = GraphProjection.from_dict(json.load(f))
            
        path = projection.shortest_path(args.source, args.target)
        if not path:
            print(f"No path found between '{args.source}' and '{args.target}'.")
            return
            
        print(f"Shortest Path ({len(path) - 1} hops):")
        print("=" * 60)
        for idx, nid in enumerate(path):
            n = projection.query_node(nid)
            node_label = f"[{n.type}] {n.title}" if n else "Unknown Node"
            if idx == 0:
                print(f"  [START] {nid[:8]} : {node_label}")
            elif idx == len(path) - 1:
                print(f"  [END]   {nid[:8]} : {node_label}")
            else:
                print(f"   -->    {nid[:8]} : {node_label}")
        print("=" * 60)

    elif args.graph_command == "export":
        if not graph_file.exists():
            provider = get_knowledge_provider()
            knowledge = provider.get_all_knowledge()
            relations = detect_relations(knowledge)
            projection = GraphProjection.build(knowledge, relations)
        else:
            with open(graph_file, "r", encoding="utf-8") as f:
                projection = GraphProjection.from_dict(json.load(f))
                
        fmt = args.format.lower()
        if fmt == "json":
            output = projection.export_json()
        elif fmt == "graphml":
            output = projection.export_graphml()
        elif fmt == "mermaid":
            output = projection.export_mermaid()
        elif fmt == "networkx":
            output = json.dumps(projection.export_networkx(), indent=2)
        else:
            logger.error(f"Unknown format '{args.format}'")
            sys.exit(1)
            
        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"[SUCCESS] Exported graph to {out_path} in {fmt} format.")
        else:
            print(output)

    elif args.graph_command in ("traverse", "impact", "path"):
        # Build fresh GraphState from knowledge
        from rationalevault.knowledge.relation_types import RelationType
        from rationalevault.projections.knowledge import KnowledgeProjection
        from rationalevault.projections.graph import GraphProjection as GraphProjectionNew

        provider = get_knowledge_provider()
        knowledge = provider.get_all_knowledge()
        if not knowledge:
            logger.error("No knowledge found. Run 'rationalevault knowledge synthesize' first.")
            sys.exit(1)

        ks = KnowledgeProjection.project(knowledge)
        gs = GraphProjectionNew.project(ks)

        if args.graph_command == "traverse":
            edge_types = None
            if args.edge_types:
                edge_types = [RelationType.from_str(et) for et in args.edge_types]

            result = gs.filtered_traversal(
                node_id=args.node_id,
                edge_types=edge_types,
                min_confidence=args.min_confidence,
                direction=args.direction,
                max_depth=args.max_depth,
            )

            print(f"Filtered Traversal from '{args.node_id}'")
            print(f"  Direction:     {args.direction}")
            print(f"  Max depth:     {args.max_depth}")
            print(f"  Min confidence:{args.min_confidence}")
            if edge_types:
                print(f"  Edge types:    {[et.value for et in edge_types]}")
            print(f"  Nodes found:   {result.node_count}")
            print(f"  Edges found:   {result.edge_count}")
            print("-" * 50)
            for nid, node in sorted(result.nodes.items()):
                print(f"  [{node.knowledge_type}] {node.title} (conf: {node.confidence:.2f})")
            if result.edges:
                print("-" * 50)
                for e in result.edges:
                    print(f"  {e.source[:8]} -->|{e.relation_type.value}| {e.target[:8]} (conf: {e.confidence:.2f})")

        elif args.graph_command == "impact":
            relation_types = None
            if args.relation_types:
                relation_types = [RelationType.from_str(rt) for rt in args.relation_types]

            result = gs.impact_analysis(
                node_id=args.node_id,
                depth=args.depth,
                relation_types=relation_types,
            )

            print(f"Impact Analysis for '{args.node_id}'")
            print(f"  Depth: {args.depth}")
            print("-" * 50)
            print(f"  Upstream ({len(result['upstream'])}):")
            for nid in result["upstream"]:
                node = gs.nodes.get(nid)
                label = node.title if node else nid
                print(f"    - {label}")
            print(f"  Downstream ({len(result['downstream'])}):")
            for nid in result["downstream"]:
                node = gs.nodes.get(nid)
                label = node.title if node else nid
                print(f"    - {label}")
            print(f"  Affected by contradiction ({len(result['affected_by_contradiction'])}):")
            for nid in result["affected_by_contradiction"]:
                node = gs.nodes.get(nid)
                label = node.title if node else nid
                print(f"    - {label}")

        elif args.graph_command == "path":
            paths = gs.all_paths(
                source=args.source,
                target=args.target,
                max_depth=args.max_depth,
            )

            print(f"All Paths from '{args.source}' to '{args.target}'")
            print(f"  Max depth: {args.max_depth}")
            print(f"  Paths found: {len(paths)}")
            print("-" * 50)
            for i, path in enumerate(paths, 1):
                labels = []
                for nid in path:
                    node = gs.nodes.get(nid)
                    labels.append(node.title if node else nid[:8])
                print(f"  Path {i}: {' -> '.join(labels)}")


def cmd_project(args: argparse.Namespace) -> None:
    from rationalevault.knowledge.project_registry import ProjectRegistry

    registry = ProjectRegistry.load()

    if args.project_command == "list":
        projects = registry.list_projects()
        if not projects:
            print("No projects registered. Use 'rationalevault project register <path>' to add one.")
            return
        print(f"Registered Projects ({len(projects)}):")
        print("-" * 60)
        for p in projects:
            tags_str = f" [{', '.join(p.tags)}]" if p.tags else ""
            print(f"  {p.id:20s} {p.name}{tags_str}")
            print(f"  {'':20s} {p.path}")

    elif args.project_command == "register":
        try:
            entry = registry.register(args.path)
            print(f"[SUCCESS] Registered project '{entry.id}'")
            print(f"  Name: {entry.name}")
            print(f"  Path: {entry.path}")
        except ValueError as e:
            logger.error(f"{e}")
            sys.exit(1)

    elif args.project_command == "unregister":
        if registry.unregister(args.project_id):
            print(f"[SUCCESS] Unregistered project '{args.project_id}'")
        else:
            logger.error(f"Project '{args.project_id}' not found.")
            sys.exit(1)

    elif args.project_command == "info":
        project_root = Path.cwd()
        project_yaml = project_root / ".rationalevault" / "project.yaml"
        if project_yaml.exists():
            import yaml
            with open(project_yaml, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            pid = config.get("project_id", "unknown")
            print(f"Current Project: {project_root.name}")
            print(f"  Project ID: {pid}")
            print(f"  Path: {project_root}")
        else:
            print(f"No project found at {project_root}")
            print("Run 'rationalevault init' to initialize a project.")

    elif args.project_command == "search":
        import yaml
        from rationalevault.knowledge.project_registry import ProjectRegistry
        from rationalevault.knowledge.factory import get_knowledge_provider
        from rationalevault.projections.cross_project import CrossProjectProjection

        registry = ProjectRegistry.load()
        projects = registry.list_projects()
        if not projects:
            print("No registered projects. Use 'rationalevault project register <path>' first.")
            return

        # Resolve current project
        current_id = ""
        project_yaml = Path.cwd() / ".rationalevault" / "project.yaml"
        if project_yaml.exists():
            try:
                with open(project_yaml, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
                current_id = config.get("project_id", "")
            except Exception:
                pass

        # Load current project's knowledge
        provider = get_knowledge_provider()
        current_knowledge = provider.get_all_knowledge()

        # Load knowledge from registered projects
        target_knowledge: dict[str, list] = {}
        for entry in projects:
            if entry.id == current_id:
                continue
            try:
                from rationalevault.knowledge.store import SQLiteKnowledgeProvider
                target_store = SQLiteKnowledgeProvider(db_path=str(Path(entry.path) / ".rationalevault" / "knowledge.db"))
                target_knowledge[entry.id] = target_store.get_all_knowledge()
            except Exception:
                target_knowledge[entry.id] = []

        state = CrossProjectProjection.project(
            current_project_id=current_id,
            current_knowledge=current_knowledge,
            target_knowledge=target_knowledge,
            query=args.query,
        )

        print(f"Cross-Project Knowledge Search: '{args.query}'")
        print(f"  Projects searched: {len(state.source_projects)}")
        print(f"  Transferable knowledge: {len(state.transferable_knowledge)}")
        print("=" * 70)
        if not state.transferable_knowledge:
            print("  No transferable knowledge found.")
        else:
            for k in sorted(state.transferable_knowledge, key=lambda x: x.relevance_score, reverse=True):
                tags = f" [{', '.join(k.matched_terms)}]" if k.matched_terms else ""
                print(f"  [{k.transferability:<15}] {k.title}{tags}")
                print(f"    Source: {k.source_project_id[:20]}  Conf: {k.confidence:.2f}  Rel: {k.relevance_score:.2f}")
                print(f"    Reasons: {', '.join(k.reasons)}")
        print("=" * 70)
        if state.health:
            print(f"  Coverage: {state.health.coverage:.0%} ({state.health.total_transferable}/{state.health.total_transferable + (state.health.total_projects - state.health.total_transferable)})")
            print(f"  Reusable: {state.health.reusable_count} | Organizational: {state.health.organizational_count}")


def cmd_evaluate(args: argparse.Namespace) -> None:
    from rationalevault.evaluation.evaluator import run_full_evaluation
    result = run_full_evaluation()
    
    print("\n=== RationaleVault Evaluation ===")
    print(f"RationaleVault version:  {result.rationalevault_version}")
    print(f"Schema version: {result.schema_version}")
    print(f"Report path:    {result.report_path}\n")
    print(f"  Memory:      {'PASS' if result.memory_passed else 'FAIL'}")
    print(f"  Knowledge:   {'PASS' if result.knowledge_passed else 'FAIL'}")
    print(f"  Context:     {'PASS' if result.context_passed else 'FAIL'}")
    print(f"  Compiler:    {'PASS' if result.compiler_passed else 'FAIL'}")
    print(f"  Continuity:  {'PASS' if result.continuity_passed else 'FAIL'}")
    print(f"  Graph:       {'PASS' if result.graph_passed else 'FAIL'}")
    print(f"  Examples:    {'PASS' if result.examples_passed else 'FAIL'}")
    print("-" * 35)
    print(f"Overall Result: {'PASS' if result.overall_passed else 'FAIL'}")
    if not result.overall_passed:
        sys.exit(1)


def cmd_organization(args: argparse.Namespace) -> None:
    """Manage organizational knowledge visibility."""
    import yaml
    from rationalevault.knowledge.project_registry import ProjectRegistry
    from rationalevault.knowledge.factory import get_knowledge_provider
    from rationalevault.projections.cross_project import CrossProjectProjection
    from rationalevault.organization.projection import OrganizationProjection

    if args.org_command == "stats":
        registry = ProjectRegistry.load()
        projects = registry.list_projects()
        if not projects:
            print("No registered projects. Use 'rationalevault project register <path>' first.")
            return

        # Resolve current project
        current_id = ""
        project_yaml = Path.cwd() / ".rationalevault" / "project.yaml"
        if project_yaml.exists():
            try:
                with open(project_yaml, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
                current_id = config.get("project_id", "")
            except Exception:
                pass

        provider = get_knowledge_provider()
        current_knowledge = provider.get_all_knowledge()

        # Build CrossProjectState per project
        cross_states: dict = {}
        knowledge_by_project: dict = {}
        for entry in projects:
            try:
                from rationalevault.knowledge.store import SQLiteKnowledgeProvider
                store = SQLiteKnowledgeProvider(db_path=str(Path(entry.path) / ".rationalevault" / "knowledge.db"))
                klist = store.get_all_knowledge()
                knowledge_by_project[entry.id] = klist
            except Exception:
                knowledge_by_project[entry.id] = []

        for entry in projects:
            if entry.id == current_id:
                continue
            targets = {pid: klist for pid, klist in knowledge_by_project.items() if pid != entry.id}
            cross_states[entry.id] = CrossProjectProjection.project(
                current_project_id=entry.id,
                current_knowledge=knowledge_by_project.get(entry.id, []),
                target_knowledge=targets,
            )

        state = OrganizationProjection.project(
            registry=registry,
            cross_project_states=cross_states,
            knowledge_by_project=knowledge_by_project,
        )

        h = state.health
        t = state.transferability_telemetry
        print("RationaleVault Organization State")
        print("=" * 55)
        print(f"Projects:               {h.total_projects}")
        print(f"Total Knowledge:        {h.total_knowledge}")
        print(f"Transferable:           {h.transferable_knowledge}")
        print(f"Shared Knowledge:       {h.shared_knowledge_count}")
        print(f"Knowledge Adoption:     {h.knowledge_adoption_rate:.0%}")
        print(f"Cross-Project Conflicts:{h.cross_project_conflicts}")
        print(f"Invariants Spanning:    {h.invariant_count}")
        print(f"Avg Lineage Depth:      {h.lineage_depth_avg:.1f}")
        print(f"Overall Health:         {h.overall:.2f}")
        print("-" * 55)
        print("Transferability Distribution:")
        print(f"  LOCAL_ONLY:    {t.local_only_count}")
        print(f"  REUSABLE:      {t.reusable_count}")
        print(f"  ORGANIZATIONAL:{t.organizational_count}")
        print(f"  Acceptance:    {t.acceptance_rate:.0%}")
        if state.project_clusters:
            print("-" * 55)
            print("Project Clusters:")
            for i, cluster in enumerate(state.project_clusters, 1):
                print(f"  {i}: {', '.join(cluster)}")
        if state.cross_project_conflicts:
            print("-" * 55)
            print("Cross-Project Conflicts:")
            for c in state.cross_project_conflicts[:5]:
                print(f"  [{c.conflict_id[:8]}] {c.knowledge_a_title} ({c.project_a} vs {c.project_b})")
                print(f"    Reasons: {', '.join(c.reasons)}")
        print("=" * 55)

    elif args.org_command == "lineage":
        registry = ProjectRegistry.load()
        projects = registry.list_projects()
        if not projects:
            print("No registered projects.")
            return

        knowledge_by_project: dict = {}
        for entry in projects:
            try:
                from rationalevault.knowledge.store import SQLiteKnowledgeProvider
                store = SQLiteKnowledgeProvider(db_path=str(Path(entry.path) / ".rationalevault" / "knowledge.db"))
                knowledge_by_project[entry.id] = store.get_all_knowledge()
            except Exception:
                knowledge_by_project[entry.id] = []

        cross_states: dict = {}
        for entry in projects:
            targets = {pid: klist for pid, klist in knowledge_by_project.items() if pid != entry.id}
            cross_states[entry.id] = CrossProjectProjection.project(
                current_project_id=entry.id,
                current_knowledge=knowledge_by_project.get(entry.id, []),
                target_knowledge=targets,
            )

        state = OrganizationProjection.project(
            registry=registry,
            cross_project_states=cross_states,
            knowledge_by_project=knowledge_by_project,
        )

        lineage = state.active_lineages.get(args.knowledge_id)
        if not lineage:
            # Search by prefix
            for kid, l in state.active_lineages.items():
                if kid.startswith(args.knowledge_id):
                    lineage = l
                    break
        if not lineage:
            print(f"Lineage for '{args.knowledge_id}' not found.")
            print("Available lineages:")
            for kid in sorted(state.active_lineages.keys()):
                l = state.active_lineages[kid]
                print(f"  {kid}: {l.origin_project} → {', '.join(l.current_projects)} (depth {l.depth})")
            return

        print(f"Knowledge Lineage: {lineage.knowledge_id}")
        print("=" * 50)
        print(f"Origin Project:    {lineage.origin_project}")
        print(f"Current Projects:  {', '.join(lineage.current_projects)}")
        print(f"Transfer Path:     {' → '.join(lineage.transfer_path)}")
        print(f"Depth:             {lineage.depth}")
        print("=" * 50)

    elif args.org_command == "graph":
        cmd_organization_graph(args)

    elif args.org_command == "activity":
        cmd_organization_activity(args)

    elif args.org_command == "continuation":
        cmd_organization_continuation(args)


def cmd_organization_activity(args: argparse.Namespace) -> None:
    """Organization activity state commands."""
    import json
    from rationalevault.organization.activity import OrganizationActivityProjection

    state, registry = _build_org_state_from_registry()
    if state is None:
        print("No registered projects.")
        return

    window_hours = getattr(args, "window_hours", 72)

    # Build activity from temporal signals (project-level calls)
    from rationalevault.knowledge.factory import get_knowledge_provider

    project_ids = state.project_ids
    recent_events_by_project: dict[str, list] = {}
    recent_knowledge_by_project: dict[str, list] = {}
    recent_memories_by_project: dict[str, list] = {}

    provider = get_knowledge_provider()
    all_knowledge = provider.get_all_knowledge()

    for pid in project_ids:
        # Knowledge from current provider
        pid_knowledge = [k for k in all_knowledge if getattr(k, "project_id", "") == pid]
        recent_knowledge_by_project[pid] = pid_knowledge[:10]

    activity = OrganizationActivityProjection.project(
        project_ids=project_ids,
        recent_events_by_project=recent_events_by_project,
        recent_knowledge_by_project=recent_knowledge_by_project,
        recent_memories_by_project=recent_memories_by_project,
        org_state=state,
        activity_window_hours=window_hours,
    )

    if hasattr(args, "org_activity_command") and args.org_activity_command == "evaluate":
        from rationalevault.evaluation.organization_continuation_evaluator import (
            OrganizationContinuationEvaluator,
        )
        from rationalevault.organization.graph import OrganizationGraphProjection
        from rationalevault.organization.continuation import OrganizationContinuationProjection

        graph = OrganizationGraphProjection.project(state)
        cont = OrganizationContinuationProjection.project(state, graph, activity)
        eval_ = OrganizationContinuationEvaluator()
        result = eval_.evaluate(state, graph, activity, cont)
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(json.dumps(activity.to_dict(), indent=2))


def cmd_organization_continuation(args: argparse.Namespace) -> None:
    """Organization continuation state commands."""
    import json
    from rationalevault.organization.activity import OrganizationActivityProjection
    from rationalevault.organization.continuation import OrganizationContinuationProjection
    from rationalevault.organization.graph import OrganizationGraphProjection

    state, registry = _build_org_state_from_registry()
    if state is None:
        print("No registered projects.")
        return

    window_hours = getattr(args, "window_hours", 72)

    from rationalevault.knowledge.factory import get_knowledge_provider
    provider = get_knowledge_provider()
    all_knowledge = provider.get_all_knowledge()

    recent_knowledge_by_project: dict[str, list] = {}
    for pid in state.project_ids:
        pid_knowledge = [k for k in all_knowledge if getattr(k, "project_id", "") == pid]
        recent_knowledge_by_project[pid] = pid_knowledge[:10]

    activity = OrganizationActivityProjection.project(
        project_ids=state.project_ids,
        recent_events_by_project={},
        recent_knowledge_by_project=recent_knowledge_by_project,
        recent_memories_by_project={},
        org_state=state,
        activity_window_hours=window_hours,
    )
    graph = OrganizationGraphProjection.project(state)
    cont = OrganizationContinuationProjection.project(state, graph, activity)

    if hasattr(args, "org_cont_command") and args.org_cont_command == "evaluate":
        from rationalevault.evaluation.organization_continuation_evaluator import (
            OrganizationContinuationEvaluator,
        )
        eval_ = OrganizationContinuationEvaluator()
        result = eval_.evaluate(state, graph, activity, cont)
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(json.dumps(cont.to_dict(), indent=2))


def _build_org_state_from_registry() -> tuple:
    """Build OrganizationState from the project registry.

    Delegates to organization.service for shared domain logic.
    """
    from rationalevault.organization.service import build_org_state_from_registry
    return build_org_state_from_registry()


def cmd_organization_graph(args: argparse.Namespace) -> None:
    """Organization graph projection commands."""
    import json
    from rationalevault.organization.graph import OrganizationGraphProjection

    state, registry = _build_org_state_from_registry()
    if state is None:
        print("No registered projects.")
        return

    if args.org_graph_command == "stats":
        graph = OrganizationGraphProjection.project(state)
        h = graph.health
        print("Organization Graph State")
        print("=" * 55)
        print(f"Projects:             {len(graph.nodes)}")
        print(f"Edges:                {len(graph.edges)}")
        print(f"Density:              {h.density:.4f}")
        print(f"Connectivity:         {h.connectivity:.2%}")
        print(f"Conflict Density:     {h.conflict_density:.2%}")
        print(f"Cluster Cohesion:     {h.cluster_cohesion:.2%}")
        print(f"Producer/Consumer:    {h.producer_consumer_balance:.4f}")
        print(f"Overall Health:       {h.overall:.4f}")
        print("-" * 55)
        if graph.knowledge_producers:
            print("Knowledge Producers:")
            for pid, score in graph.knowledge_producers[:5]:
                print(f"  {pid}: +{score:.0f}")
        if graph.knowledge_consumers:
            print("Knowledge Consumers:")
            for pid, score in graph.knowledge_consumers[:5]:
                print(f"  {pid}: -{score:.0f}")
        if graph.contradiction_hotspots:
            print("Contradiction Hotspots:")
            for pid, score in graph.contradiction_hotspots[:5]:
                print(f"  {pid}: {score:.0f} conflicts")
        print("=" * 55)

    elif args.org_graph_command == "query":
        graph = OrganizationGraphProjection.project(state)
        pid = args.project_id
        if pid not in graph.nodes:
            # Prefix search
            matches = [n for n in graph.nodes if n.startswith(pid)]
            if len(matches) == 1:
                pid = matches[0]
            else:
                print(f"Project '{pid}' not found. Available: {', '.join(sorted(graph.nodes))}")
                return
        node = graph.nodes[pid]
        print(f"Project: {node.project_id}")
        print(f"  Knowledge Count:    {node.knowledge_count}")
        print(f"  Transferable:       {node.transferable_count}")
        print(f"  Shared:             {node.shared_count}")
        print(f"  Conflicts:          {node.conflict_count}")
        print(f"  Cluster Center:     {node.is_cluster_center}")
        out_edges = graph.adjacency.get(pid, [])
        in_edges = graph.reverse_adjacency.get(pid, [])
        if out_edges:
            print("  Outgoing Edges:")
            for e in out_edges:
                print(f"    → {e.target} [{e.relation_type.value}] w={e.weight:.0f} c={e.confidence:.2f}")
        if in_edges:
            print("  Incoming Edges:")
            for e in in_edges:
                print(f"    ← {e.source} [{e.relation_type.value}] w={e.weight:.0f} c={e.confidence:.2f}")

    elif args.org_graph_command == "traverse":
        graph = OrganizationGraphProjection.project(state)
        from rationalevault.organization.relation_types import OrganizationRelationType
        rel_types = None
        if hasattr(args, "relation_types") and args.relation_types:
            rel_types = {OrganizationRelationType.from_str(r) for r in args.relation_types}
        visited = OrganizationGraphProjection.filtered_traversal(
            graph, args.start, relation_types=rel_types,
        )
        print(f"Traversal from {args.start}: {' → '.join(visited)}")

    elif args.org_graph_command == "shortest-path":
        graph = OrganizationGraphProjection.project(state)
        path = OrganizationGraphProjection.shortest_transfer_path(graph, args.source, args.target)
        if path:
            print(f"Shortest transfer path: {' → '.join(path)}")
        else:
            print(f"No transfer path from '{args.source}' to '{args.target}'")

    elif args.org_graph_command == "flow-balance":
        graph = OrganizationGraphProjection.project(state)
        print("Knowledge Flow Balance")
        print("=" * 40)
        for pid, balance in sorted(graph.knowledge_flow_balance.items(), key=lambda x: -x[1]):
            if balance > 0:
                label = f"+{balance} (producer)"
            elif balance < 0:
                label = f"{balance} (consumer)"
            else:
                label = "0 (balanced)"
            print(f"  {pid}: {label}")
        print("=" * 40)

    elif args.org_graph_command == "export":
        graph = OrganizationGraphProjection.project(state)
        print(json.dumps(graph.to_dict(), indent=2))

    elif args.org_graph_command == "evaluate":
        from rationalevault.evaluation.organization_graph_evaluator import OrganizationGraphEvaluator
        graph = OrganizationGraphProjection.project(state)
        eval_ = OrganizationGraphEvaluator()
        result = eval_.evaluate(graph, state)
        d = result.to_dict()
        print(json.dumps(d, indent=2))


def cmd_recommend(args: argparse.Namespace) -> None:
    """Recommendation engine commands."""
    import json

    from rationalevault.organization.activity import OrganizationActivityProjection
    from rationalevault.organization.continuation import OrganizationContinuationProjection
    from rationalevault.organization.graph import OrganizationGraphProjection
    from rationalevault.organization.recommendations.engine import RecommendationEngine

    from rationalevault.cli.main import _build_org_state_from_registry

    if args.recommend_command == "evaluate":
        from rationalevault.evaluation.recommendation_evaluator import RecommendationEvaluator
        eval_ = RecommendationEvaluator()
        result = eval_.evaluate()
        d = result.to_dict()
        print(json.dumps(d, indent=2))
        return

    # Generate recommendations
    org_state, _ = _build_org_state_from_registry()
    if org_state is None:
        print(json.dumps({"error": "No registered projects", "recommendations": [], "recommendation_count": 0}))
        return

    from rationalevault.knowledge.factory import get_knowledge_provider
    provider = get_knowledge_provider()
    all_knowledge = provider.get_all_knowledge()
    recent_knowledge_by_project: dict[str, list] = {}
    for pid in org_state.project_ids:
        pid_knowledge = [k for k in all_knowledge if getattr(k, "project_id", "") == pid]
        recent_knowledge_by_project[pid] = pid_knowledge[:10]

    activity = OrganizationActivityProjection.project(
        project_ids=org_state.project_ids,
        recent_events_by_project={},
        recent_knowledge_by_project=recent_knowledge_by_project,
        recent_memories_by_project={},
        org_state=org_state,
        activity_window_hours=72,
    )
    graph = OrganizationGraphProjection.project(org_state)
    cont = OrganizationContinuationProjection.project(org_state, graph, activity)

    result = RecommendationEngine.generate(
        org_state=org_state,
        graph_state=graph,
        activity_state=activity,
    )

    d = result.to_dict()

    # Filter by project if specified
    if args.project:
        d["recommendations"] = [
            r for r in d["recommendations"]
            if args.project in r.get("affected_projects", [])
        ]
        d["recommendation_count"] = len(d["recommendations"])

    print(json.dumps(d, indent=2))


def cmd_retrieval(args: argparse.Namespace) -> None:
    """Hybrid retrieval orchestrator commands."""
    import json
    from rationalevault.retrieval.orchestrator import RetrievalOrchestrator

    if args.retrieval_command == "plan":
        orch = RetrievalOrchestrator()
        plan = orch.build_plan(
            args.query,
            available_projections=None,
        )
        d = plan.to_dict()
        print(json.dumps(d, indent=2))

    elif args.retrieval_command == "evaluate":
        from rationalevault.evaluation.retrieval_evaluator import RetrievalEvaluator
        eval_ = RetrievalEvaluator()
        result = eval_.evaluate()
        d = result.to_dict()
        print(json.dumps(d, indent=2))


def cmd_serve(args: argparse.Namespace) -> None:
    """Run the RationaleVault MCP server."""
    try:
        import mcp
    except ImportError:
        logger.error("The 'mcp' package is not installed.")
        print("Please install it with: pip install RationaleVault[mcp]")
        sys.exit(1)

    from rationalevault.mcp.server import run as run_mcp_server
    run_mcp_server(transport=args.transport, port=args.port)


def cmd_retrieval_dashboard(args: argparse.Namespace) -> None:
    """Display retrieval telemetry dashboard."""
    from rationalevault.telemetry.metrics import get_collector

    snap = get_collector().snapshot()

    print("Retrieval Dashboard")
    print("=" * 40)

    if snap.total_requests == 0:
        print("No requests recorded yet.")
        return

    print(f"Total requests:        {snap.total_requests}")
    print()
    print("Latency (ms)")
    print(f"  Average:             {snap.avg_total_ms:.1f}")
    print(f"  P50:                 {snap.p50_total_ms:.1f}")
    print(f"  P95:                 {snap.p95_total_ms:.1f}")
    print(f"  P99:                 {snap.p99_total_ms:.1f}")
    print()
    print(f"Provider latency (ms): {snap.avg_provider_latency_ms:.1f}")
    print(f"Avg candidates:        {snap.avg_candidate_count:.0f}")
    print(f"Avg final citations:   {snap.avg_retrieved_count:.0f}")
    print()
    print("Profile distribution")
    for profile, count in sorted(snap.profile_distribution.items(), key=lambda x: -x[1]):
        print(f"  {profile:<25} {count}")

    if snap.stage_averages:
        print()
        print("Stage averages (ms)")
        for stage, avg in snap.stage_averages.items():
            print(f"  {stage:<30} {avg:.1f}")


import argparse

def register(subparsers: argparse._SubParsersAction) -> None:


    # install
    parser_install = subparsers.add_parser("install", help="Install platform adapters")
    parser_install.add_argument("--platform", required=True, help="Target platform (claude, cursor, opencode, copilot)")

    # uninstall
    subparsers.add_parser("uninstall", help="Uninstall RationaleVault adapters and configs from current project")


    # generate-adapters
    subparsers.add_parser("generate-adapters", help="Recompile adapter templates")

    # migrate-storage
    parser_migrate = subparsers.add_parser("migrate-storage", help="Migrate event stream between storage backends")
    parser_migrate.add_argument("--from", dest="frm", required=True, choices=["sqlite", "postgres"], help="Source backend")
    parser_migrate.add_argument("--to", required=True, choices=["sqlite", "postgres"], help="Target backend")
















    parser_context = subparsers.add_parser("context", help="Compile unified context from events, memories, and knowledge")
    parser_context.add_argument("--query", required=True, help="Query string")
    parser_context.add_argument("--limit", type=int, default=30, help="Max total citations (default: 30)")
    parser_context.add_argument("--output", choices=["json", "summary", "evaluate"], default="summary", help="Output format")
    parser_context.add_argument("--agent", choices=["claude", "opencode", "cursor"], default=None, help="Compile for specific agent (overrides --output)")
    parser_context.add_argument("--mode", choices=["standard", "continuation"], default="standard", help="Context compilation mode")
    parser_context.add_argument("--profile", help="Override auto-detected retrieval profile")
    parser_context.add_argument("--knowledge", action="store_true", help="Include knowledge projection in output")

    # project
    parser_project = subparsers.add_parser("project", help="Manage cross-project registry")
    project_subparsers = parser_project.add_subparsers(dest="project_command", required=True)

    # project list
    project_subparsers.add_parser("list", help="List all registered projects")

    # project register
    parser_project_register = project_subparsers.add_parser("register", help="Register a project by path")
    parser_project_register.add_argument("path", help="Path to project root")

    # project unregister
    parser_project_unregister = project_subparsers.add_parser("unregister", help="Remove a project from registry")
    parser_project_unregister.add_argument("project_id", help="Project ID to remove")

    # project info
    project_subparsers.add_parser("info", help="Show current project info")

    # project search
    parser_project_search = project_subparsers.add_parser("search", help="Search transferable knowledge across registered projects")
    parser_project_search.add_argument("--query", required=True, help="Query string to search for")


    # graph
    parser_graph = subparsers.add_parser("graph", help="Manage RationaleVault Knowledge Graph Projection")
    graph_subparsers = parser_graph.add_subparsers(dest="graph_command", required=True)
    
    # graph build
    graph_subparsers.add_parser("build", help="Build the deterministic knowledge graph projection from store")
    
    # graph stats
    graph_subparsers.add_parser("stats", help="Show knowledge graph projection statistics and exit gates status")
    
    # graph query
    parser_graph_query = graph_subparsers.add_parser("query", help="Query a node and optionally show neighbors")
    parser_graph_query.add_argument("--node-id", required=True, help="Knowledge node ID (prefix or full)")
    parser_graph_query.add_argument("--depth", type=int, default=0, help="Depth of neighbors to fetch (default: 0)")
    
    # graph query-path
    parser_graph_path = graph_subparsers.add_parser("query-path", help="Find the shortest path between two nodes")
    parser_graph_path.add_argument("--source", required=True, help="Source node ID")
    parser_graph_path.add_argument("--target", required=True, help="Target node ID")
    
    # graph export
    parser_graph_export = graph_subparsers.add_parser("export", help="Export the knowledge graph projection")
    parser_graph_export.add_argument("--format", required=True, choices=["json", "graphml", "mermaid", "networkx"], help="Format of the export")
    parser_graph_export.add_argument("--output", help="Optional output filepath to write the export to")

    # graph traverse
    parser_graph_traverse = graph_subparsers.add_parser("traverse", help="BFS traversal with edge-type and confidence filters")
    parser_graph_traverse.add_argument("--node-id", required=True, help="Starting node ID")
    parser_graph_traverse.add_argument("--edge-types", nargs="*", help="Filter by edge types (SUPPORTS, CONTRADICTS, DERIVED_FROM, RELATED_TO)")
    parser_graph_traverse.add_argument("--min-confidence", type=float, default=0.0, help="Minimum edge confidence (default: 0.0)")
    parser_graph_traverse.add_argument("--direction", choices=["forward", "backward", "both"], default="both", help="Traversal direction (default: both)")
    parser_graph_traverse.add_argument("--max-depth", type=int, default=10, help="Maximum traversal depth (default: 10)")

    # graph impact
    parser_graph_impact = graph_subparsers.add_parser("impact", help="Upstream/downstream impact analysis")
    parser_graph_impact.add_argument("--node-id", required=True, help="Node to analyze")
    parser_graph_impact.add_argument("--depth", type=int, default=3, help="Impact depth (default: 3)")
    parser_graph_impact.add_argument("--relation-types", nargs="*", help="Filter by relation types")

    # graph path
    parser_graph_path_all = graph_subparsers.add_parser("path", help="Find all paths between two nodes")
    parser_graph_path_all.add_argument("--source", required=True, help="Source node ID")
    parser_graph_path_all.add_argument("--target", required=True, help="Target node ID")
    parser_graph_path_all.add_argument("--max-depth", type=int, default=10, help="Maximum path depth (default: 10)")

    # evaluate
    subparsers.add_parser("evaluate", help="Run the unified evaluation suite across all subsystems")

    # organization
    parser_org = subparsers.add_parser("organization", help="Organizational knowledge visibility")
    org_subparsers = parser_org.add_subparsers(dest="org_command", required=True)

    # organization stats
    org_subparsers.add_parser("stats", help="Show organizational knowledge statistics")

    # organization lineage
    parser_org_lineage = org_subparsers.add_parser("lineage", help="Show lineage for a knowledge object")
    parser_org_lineage.add_argument("--knowledge-id", required=True, help="Knowledge object ID (prefix or full)")

    # organization graph
    org_graph_subparsers = org_subparsers.add_parser("graph", help="Organization graph projection")
    org_graph_sub = org_graph_subparsers.add_subparsers(dest="org_graph_command", required=True)
    org_graph_sub.add_parser("stats", help="Show organization graph statistics")
    parser_og_query = org_graph_sub.add_parser("query", help="Query a project node")
    parser_og_query.add_argument("--project-id", required=True, help="Project ID (prefix or full)")
    parser_og_traverse = org_graph_sub.add_parser("traverse", help="BFS traversal from a project")
    parser_og_traverse.add_argument("--start", required=True, help="Starting project ID")
    parser_og_traverse.add_argument("--relation-types", nargs="*", help="Filter by relation types")
    parser_og_path = org_graph_sub.add_parser("shortest-path", help="Shortest transfer path between projects")
    parser_og_path.add_argument("--source", required=True, help="Source project ID")
    parser_og_path.add_argument("--target", required=True, help="Target project ID")
    org_graph_sub.add_parser("flow-balance", help="Show knowledge flow balance")
    org_graph_sub.add_parser("export", help="Export organization graph as JSON")
    org_graph_sub.add_parser("evaluate", help="Evaluate organization graph projection")

    # organization activity
    parser_org_activity = org_subparsers.add_parser("activity", help="Organization activity state")
    parser_org_activity.add_argument("--window-hours", type=int, default=72, help="Activity window in hours")
    org_activity_sub = parser_org_activity.add_subparsers(dest="org_activity_command")
    org_activity_sub.add_parser("evaluate", help="Evaluate organization activity")

    # organization continuation
    parser_org_cont = org_subparsers.add_parser("continuation", help="Organization continuation state")
    parser_org_cont.add_argument("--window-hours", type=int, default=72, help="Activity window in hours")
    org_cont_sub = parser_org_cont.add_subparsers(dest="org_cont_command")
    org_cont_sub.add_parser("evaluate", help="Evaluate organization continuation")

    parser_recommend = subparsers.add_parser("recommend", help="Recommendation engine")
    parser_recommend.add_argument("--project", help="Filter recommendations to a specific project")
    recommend_sub = parser_recommend.add_subparsers(dest="recommend_command")
    recommend_sub.add_parser("evaluate", help="Evaluate recommendation engine quality")

    # retrieval
    parser_retrieval = subparsers.add_parser("retrieval", help="Hybrid retrieval orchestrator")
    retrieval_subparsers = parser_retrieval.add_subparsers(dest="retrieval_command", help="Retrieval commands")
    parser_retrieval_plan = retrieval_subparsers.add_parser("plan", help="Build a retrieval plan for a query")
    parser_retrieval_plan.add_argument("--query", required=True, help="Query string")
    retrieval_subparsers.add_parser("evaluate", help="Evaluate retrieval orchestrator quality")





    # serve
    parser_serve = subparsers.add_parser("serve", help="Run the RationaleVault MCP server")
    parser_serve.add_argument("--transport", choices=["stdio", "sse"], default="stdio", help="MCP server transport type (default: stdio)")
    parser_serve.add_argument("--port", type=int, default=8080, help="Port to run SSE server on (default: 8080)")

    # retrieval-dashboard
    subparsers.add_parser(
        "retrieval-dashboard",
        help="Display retrieval telemetry dashboard",
    )


    parser_install.set_defaults(func=cmd_install)
    subparsers.choices['uninstall'].set_defaults(func=cmd_uninstall)
    subparsers.choices['generate-adapters'].set_defaults(func=cmd_generate_adapters)
    parser_migrate.set_defaults(func=cmd_migrate_storage)
    parser_context.set_defaults(func=cmd_context)
    parser_project.set_defaults(func=cmd_project)
    parser_graph.set_defaults(func=cmd_graph)
    subparsers.choices['evaluate'].set_defaults(func=cmd_evaluate)
    parser_org.set_defaults(func=cmd_organization)
    parser_retrieval.set_defaults(func=cmd_retrieval)
    parser_recommend.set_defaults(func=cmd_recommend)
    parser_serve.set_defaults(func=cmd_serve)
    subparsers.choices['retrieval-dashboard'].set_defaults(func=cmd_retrieval_dashboard)
