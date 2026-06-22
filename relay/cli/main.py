"""
Relay Command Line Interface (CLI) Entry Point.
"""
from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from relay.db.connection import get_connection


def cmd_init(args: argparse.Namespace) -> None:
    project_root = Path.cwd()
    relay_dir = project_root / ".relay"
    relay_dir.mkdir(parents=True, exist_ok=True)

    protocol_file = relay_dir / "relay_protocol.yaml"
    skill_file = relay_dir / "RELAY_SKILL.md"
    checklist_file = relay_dir / "handoff_checklist.md"
    project_config = relay_dir / "project.yaml"

    # Default Protocol YAML
    if not protocol_file.exists():
        protocol_file.write_text("""name: "Relay Project"
version: "1.0"
description: "Rules for agent behavior in this repository."
execution_priority:
  - "OPEN_QUESTION"
  - "BLOCKER"
  - "TASK"
  - "DECISION"
rules:
  - id: "resolve_questions_first"
    description: "Always address open questions blocking active tasks before starting new work."
    severity: "error"
  - id: "respect_accepted_decisions"
    description: "Do not reverse accepted decisions without a DECISION_SUPERSEDED event."
    severity: "error"
""", encoding="utf-8")

    # Default Skill MD
    if not skill_file.exists():
        skill_file.write_text("""# Relay Agent Skill Protocol
* **Authoritative Memory**: Rely only on the Relay Context Block.
* **Question-First**: Resolve open questions before starting new tasks.
* **Decision Protection**: Do not reverse accepted decisions.
""", encoding="utf-8")

    # Default Handoff Checklist
    if not checklist_file.exists():
        checklist_file.write_text("""# Relay Handoff Checklist
- What changed?
- What decisions were made?
- What questions were resolved?
- What tasks were completed?
- What should happen next?
""", encoding="utf-8")

    # Project UUID Config & Storage Setup
    if not project_config.exists():
        pid = uuid.uuid4()
        project_config.write_text(f"""project_id: {pid}
protocol_version: 1
storage:
  backend: sqlite
  database: .relay/relay.db
""", encoding="utf-8")

    # Force creation of sqlite schema if not present
    from relay.db.sqlite_store import SQLiteEventStore
    SQLiteEventStore(db_path=str(relay_dir / "relay.db"))

    print(f"[SUCCESS] Bootstrapped Relay configuration in: {relay_dir.relative_to(project_root)}")


def cmd_install(args: argparse.Namespace) -> None:
    project_root = Path.cwd()
    relay_dir = project_root / ".relay"
    
    if not relay_dir.exists():
        print("Error: Relay has not been initialized. Run 'relay init' first.")
        sys.exit(1)

    platform = args.platform.lower()
    skill_file = relay_dir / "RELAY_SKILL.md"
    skill_text = skill_file.read_text(encoding="utf-8") if skill_file.exists() else "Default Relay Skill"

    if platform == "claude":
        target = project_root / "CLAUDE.md"
        target.write_text(f"# Claude Code Rules\n\n{skill_text}", encoding="utf-8")
        print(f"[SUCCESS] Installed Claude Code adapter in: {target.relative_to(project_root)}")
    elif platform == "cursor":
        rules_dir = project_root / ".cursor" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        target = rules_dir / "relay.mdc"
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
        print(f"Error: Unknown platform '{args.platform}'. Supported: claude, cursor, opencode, copilot.")
        sys.exit(1)


def cmd_uninstall(args: argparse.Namespace) -> None:
    project_root = Path.cwd()
    relay_dir = project_root / ".relay"

    # Remove rule files in root
    for file_name in ["CLAUDE.md", "AGENTS.md", "copilot-instructions.md"]:
        p = project_root / file_name
        if p.exists():
            p.unlink()
            print(f"Removed {file_name}")

    # Remove cursor rules
    cursor_rules = project_root / ".cursor" / "rules" / "relay.mdc"
    if cursor_rules.exists():
        cursor_rules.unlink()
        print("Removed .cursor/rules/relay.mdc")

    # Remove .relay dir
    if relay_dir.exists():
        import shutil
        shutil.rmtree(relay_dir)
        print("Removed .relay/ configuration directory.")

    print("[SUCCESS] Relay has been uninstalled from this project.")


def cmd_doctor(args: argparse.Namespace) -> None:
    from relay.diagnostics.doctor import run_diagnostics
    report = run_diagnostics()
    
    print("\n=== Relay Doctor ===")
    print(f"Relay version: {report.relay_version}")
    print(f"Generated at:  {report.generated_at}\n")
    for check in report.checks:
        status_symbol = f"[{check.status}]"
        print(f"  {check.component:<22} {status_symbol:<8} : {check.details}")
    print("-" * 65)
    print(f"Overall Result: {'PASS' if report.overall_passed else 'FAIL'}")
    if not report.overall_passed:
        sys.exit(1)


def cmd_generate_adapters(args: argparse.Namespace) -> None:
    project_root = Path.cwd()
    relay_dir = project_root / ".relay"
    
    if not relay_dir.exists():
        print("Error: Relay has not been initialized. Run 'relay init' first.")
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
    from relay.db.sqlite_store import SQLiteEventStore
    from relay.db.postgres_store import PostgresEventStore
    import yaml

    project_root = Path.cwd()
    project_yaml_path = project_root / ".relay" / "project.yaml"
    if not project_yaml_path.exists():
        print("Error: project.yaml not found. Run 'relay init' first.")
        sys.exit(1)

    try:
        with open(project_yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except Exception as ex:
        print(f"Error reading project.yaml: {ex}")
        sys.exit(1)

    pid_str = config.get("project_id")
    if not pid_str:
        print("Error: project_id not found in project.yaml")
        sys.exit(1)
    
    pid = uuid.UUID(pid_str)

    src_type = args.frm.lower()
    tgt_type = args.to.lower()

    if src_type == tgt_type:
        print("Error: Source and target backends must be different.")
        sys.exit(1)

    # Resolve source store
    if src_type == "sqlite":
        storage_config = config.get("storage", {})
        db_path = storage_config.get("database", ".relay/relay.db")
        src_store = SQLiteEventStore(db_path=db_path)
    elif src_type == "postgres":
        src_store = PostgresEventStore()
    else:
        print(f"Error: Unknown source backend '{src_type}'")
        sys.exit(1)

    # Resolve target store
    if tgt_type == "sqlite":
        tgt_store = SQLiteEventStore(db_path=".relay/relay.db")
    elif tgt_type == "postgres":
        tgt_store = PostgresEventStore()
    else:
        print(f"Error: Unknown target backend '{tgt_type}'")
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


def cmd_memory(args: argparse.Namespace) -> None:
    from relay.memory.factory import get_memory_provider
    from relay.memory.models import MemoryRecord, MemoryType, generate_memory_id
    from relay.memory.compiler import compile_memory_context
    from relay.memory.retrieval import retrieve_ranked_memories
    from relay.memory.ranking import compute_retrieval_score
    import json

    provider = get_memory_provider()

    if args.mem_command == "add":
        tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
        m_type = MemoryType(args.type)
        m_id = generate_memory_id(m_type.value, args.title, args.content)
        
        record = MemoryRecord(
            id=m_id,
            version=1,
            title=args.title,
            content=args.content,
            memory_type=m_type,
            importance="medium",
            lifecycle_status="active",
            source_event_ids=[],
            source_type="manual",
            tags=tags,
            confidence=1.0,
        )
        provider.add_record(record)
        print(f"[SUCCESS] Recorded memory: {record.title} (ID: {record.id})")

    elif args.mem_command == "list":
        records = provider.get_all_records()
        if not records:
            print("No memories recorded yet.")
            return
        print(f"Total memories: {len(records)}")
        print(f"{'ID':<10} | {'Type':<18} | {'Version':<7} | {'Title'}")
        print("-" * 80)
        for r in records:
            print(f"{r.id[:8]:<10} | {r.memory_type.value:<18} | {r.version:<7} | {r.title}")

    elif args.mem_command == "search":
        from relay.memory.retrieval import retrieve_ranked_citations
        citations, execution = retrieve_ranked_citations(args.query, limit=10)
        if not citations:
            print("No matching memories found.")
            return
            
        print("Retrieval Execution Summary:")
        print(f"  Profile:          {execution.profile.value}")
        print(f"  Sources:          {', '.join(execution.planner_sources)}")
        print(f"  Candidates Cnt:   {execution.candidate_count}")
        print(f"  Execution Time:   {execution.execution_ms:.2f} ms")
        print("=" * 90)
        print(f"{'ID':<10} | {'Total Score':<12} | {'Reasons':<35} | {'Title'}")
        print("-" * 90)
        
        # Load records to display titles
        records = provider.get_all_records()
        for c in citations:
            r = next((rec for rec in records if rec.id == c.memory_id), None)
            if r:
                reasons_str = ", ".join(c.reasons)
                if len(reasons_str) > 33:
                    reasons_str = reasons_str[:30] + "..."
                print(f"{r.id[:8]:<10} | {c.score.total:<12.2f} | {reasons_str:<35} | {r.title}")
        print("=" * 90)

    elif args.mem_command == "show":
        records = provider.get_all_records()
        record = next((r for r in records if r.id.startswith(args.id) or r.id == args.id), None)
        if not record:
            print(f"Error: Memory with ID/Prefix '{args.id}' not found.")
            sys.exit(1)
        
        score = compute_retrieval_score(record)
        
        print(f"Memory Record {record.id} (v{record.version})")
        print("=" * 80)
        print(f"Title:        {record.title}")
        print(f"Type:         {record.memory_type.value}")
        print(f"Importance:   {record.importance}")
        print(f"Confidence:   {record.confidence:.2f}")
        print(f"Priority:     {record.retrieval_priority:.1f}")
        print(f"Status:       {record.lifecycle_status}")
        print(f"Source Type:  {record.source_type}")
        print(f"Source Event: {', '.join(record.source_event_ids)}")
        print(f"Tags:         {', '.join(record.tags)}")
        print(f"Created At:   {record.created_at}")
        print(f"Reference Cnt:{record.reference_count} (Last: {record.last_referenced_at or 'Never'})")
        from relay.memory.citation_builder import build_citation
        citation = build_citation(record, "", ["manual_show"])
        
        print("-" * 80)
        print(f"Retrieval Score Breakdown:")
        print(f"  Total Score:       {score.total:.2f}")
        print(f"  Priority:          {score.priority:.2f}")
        print(f"  Recency:           {score.recency:.2f}")
        print(f"  References:        {score.references:.2f}")
        print(f"  Confidence:        {score.confidence:.2f}")
        print(f"  Lifecycle Penalty: {score.lifecycle_penalty:.2f}")
        print(f"Citations Metadata:")
        print(f"  Reasons:           {', '.join(citation.reasons)}")
        print(f"  Default Path:      {', '.join(citation.retrieval_path)}")
        print("-" * 80)
        print(record.content.strip())
        print("=" * 80)

    elif args.mem_command == "compile":
        context = compile_memory_context(args.query)
        serializable_context = {}
        for k, v in context.items():
            serializable_context[k] = [
                {
                    "record": r.to_dict(),
                    "score": score.to_dict()
                } for r, score in v
            ]
        print(json.dumps(serializable_context, indent=2))

    elif args.mem_command == "stats":
        records = provider.get_all_records()
        total_records = len(records)
        unique_ids = len({r.id for r in records})
        
        deduplication_rate = unique_ids / total_records if total_records > 0 else 1.0
        
        with_provenance = sum(1 for r in records if r.source_event_ids)
        provenance_pct = (with_provenance / total_records) if total_records > 0 else 1.0
        
        by_type = {}
        for r in records:
            by_type[r.memory_type.value] = by_type.get(r.memory_type.value, 0) + 1
            
        print("Relay Memory Bridge Statistics:")
        print("=" * 40)
        print(f"Total Memory Records:          {total_records}")
        print(f"Unique Memories (IDs):        {unique_ids}")
        print(f"Memory Deduplication Rate:    {deduplication_rate:.2%}")
        print(f"Memory With Provenance:       {provenance_pct:.2%}")
        print("\nMemories by Type:")
        for t, count in sorted(by_type.items()):
            print(f"  {t:<20}: {count}")
        print("=" * 40)

    elif args.mem_command == "consolidate":
        from relay.memory.consolidation import detect_consolidation_candidates, emit_consolidation_candidates
        import yaml
        project_root = Path.cwd()
        project_yaml = project_root / ".relay" / "project.yaml"
        project_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
        if project_yaml.exists():
            try:
                with open(project_yaml, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                project_id = uuid.UUID(config.get("project_id"))
            except Exception:
                pass
        
        candidates = detect_consolidation_candidates()
        num_emitted = emit_consolidation_candidates(project_id)
        
        print("Consolidation Candidate Detection:")
        print("=" * 50)
        print(f"Found duplicate clusters: {len(candidates)}")
        print(f"Emitted events to ledger: {num_emitted}")
        print("-" * 50)
        for cand in candidates:
            print(f"Cluster Candidate: {cand.candidate_id[:8]}...")
            print(f"  Similarity Score:  {cand.similarity_score:.2f}")
            print(f"  Cluster Size:      {cand.cluster_size}")
            print(f"  Member Memory IDs: {', '.join([mid[:8] for mid in cand.memory_ids])}")
        print("=" * 50)


def cmd_knowledge(args: argparse.Namespace) -> None:
    """Manage Relay Knowledge Synthesis."""
    import json
    import yaml
    from relay.knowledge.factory import get_knowledge_provider
    from relay.knowledge.synthesizer import synthesize_all
    from relay.knowledge.evaluation import compute_knowledge_metrics

    provider = get_knowledge_provider()

    if args.knowledge_command == "synthesize":
        project_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
        project_yaml = Path.cwd() / ".relay" / "project.yaml"
        if project_yaml.exists():
            try:
                with open(project_yaml, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                project_id = uuid.UUID(config.get("project_id", str(project_id)))
            except Exception:
                pass

        # Load existing knowledge for STALE detection
        existing = provider.get_all_knowledge()

        # Synthesize
        knowledge = synthesize_all(project_id, existing)

        # Persist to store
        for k in knowledge:
            provider.add_knowledge(k)

        print(f"Synthesized {len(knowledge)} knowledge objects.")
        print(f"Types: {', '.join(k.knowledge_type.value for k in knowledge)}")

    elif args.knowledge_command == "list":
        knowledge = provider.get_all_knowledge()
        if not knowledge:
            print("No knowledge objects synthesized yet.")
            return
        print(f"Total knowledge: {len(knowledge)}")
        print(f"{'ID':<10} | {'Type':<25} | {'Domain':<15} | {'Conf':<6} | {'Title'}")
        print("-" * 90)
        for k in knowledge:
            print(f"{k.id[:8]:<10} | {k.knowledge_type.value:<25} | {k.knowledge_domain.value:<15} | {k.confidence.score:<6.2f} | {k.title}")

    elif args.knowledge_command == "stats":
        from relay.memory.factory import get_memory_provider
        mem_provider = get_memory_provider()
        memory_count = len(mem_provider.get_all_records())
        knowledge = provider.get_all_knowledge()

        metrics = compute_knowledge_metrics(
            knowledge, [], memory_count=memory_count
        )

        print("Relay Knowledge Synthesis Metrics:")
        print("=" * 40)
        print(f"Knowledge Count:            {metrics.knowledge_count}")
        print(f"Knowledge Density:          {metrics.knowledge_density:.4f}")
        print(f"Knowledge Coverage:         {metrics.knowledge_coverage:.2%}")
        print(f"Knowledge Provenance:       {metrics.knowledge_provenance_pct:.2%}")
        print(f"Freshness:                  {metrics.freshness_score:.2%}")
        print(f"Stability:                  {metrics.stability_score:.2%}")
        print(f"Determinism:                {metrics.determinism_score:.2%}")
        print(f"Contradictions Detected:    {metrics.contradictions_detected}")

        passed, failures = metrics.passes_exit_gates()
        if passed:
            print("\n[PASS] All sprint exit gates passed.")
        else:
            print(f"\n[FAIL] Sprint exit gates failed: {', '.join(failures)}")

    elif args.knowledge_command == "show":
        knowledge = provider.get_all_knowledge()
        k = next((k for k in knowledge if k.id.startswith(args.id) or k.id == args.id), None)
        if not k:
            print(f"Error: Knowledge with ID/Prefix '{args.id}' not found.")
            sys.exit(1)

        print(f"Knowledge Object {k.id} (v{k.version})")
        print("=" * 80)
        print(f"Title:            {k.title}")
        print(f"Type:             {k.knowledge_type.value}")
        print(f"Domain:           {k.knowledge_domain.value}")
        print(f"Importance:       {k.importance}")
        print(f"Confidence:       {k.confidence.score:.2f}")
        print(f"Status:           {k.lifecycle_status}")
        print(f"Tags:             {', '.join(k.tags)}")
        print(f"Created At:       {k.created_at}")
        print(f"Updated At:       {k.updated_at}")
        print("-" * 80)
        print(f"Provenance:")
        print(f"  Source Memories: {', '.join(k.provenance.source_memory_ids)}")
        print(f"  Source Events:   {', '.join(k.provenance.source_event_ids)}")
        print(f"  Evidence Count:  {k.provenance.evidence_count}")
        print("-" * 80)
        print(f"Confidence Breakdown:")
        print(f"  Memory Count:           {k.confidence.memory_count}")
        print(f"  Source Event Count:     {k.confidence.source_event_count}")
        print(f"  Contradiction Count:    {k.confidence.contradiction_count}")
        print(f"  Avg Memory Confidence:  {k.confidence.average_memory_confidence:.2f}")
        print("-" * 80)
        print(k.content.strip())
        print("=" * 80)

    elif args.knowledge_command == "search":
        results = provider.search_knowledge(args.query, limit=10)
        if not results:
            print("No matching knowledge found.")
            return
        print(f"Found {len(results)} knowledge objects:")
        for k in results:
            print(f"  [{k.knowledge_type.value}] {k.title} (conf: {k.confidence.score:.2f})")

    elif args.knowledge_command == "evaluate":
        from relay.knowledge.evaluator import KnowledgeEvaluator, KnowledgeEvalResult, check_knowledge_gates
        from relay.knowledge.benchmark_schema import KnowledgeBenchmark
        from relay.knowledge.synthesizer import synthesize_all

        # Load benchmarks
        knowledge_cases_dir = Path.cwd() / "relay" / "evaluation" / "knowledge_cases"
        benchmarks = []
        if knowledge_cases_dir.exists():
            for p in knowledge_cases_dir.glob("**/*.json"):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        benchmarks.append(KnowledgeBenchmark.from_dict(json.load(f)))
                except Exception:
                    pass

        if not benchmarks:
            print("No knowledge benchmarks found.")
            return

        # Get project ID
        project_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
        project_yaml = Path.cwd() / ".relay" / "project.yaml"
        if project_yaml.exists():
            try:
                import yaml
                with open(project_yaml, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                project_id = uuid.UUID(config.get("project_id", str(project_id)))
            except Exception:
                pass

        # Synthesize knowledge
        existing = provider.get_all_knowledge()
        synthesized = synthesize_all(project_id, existing)

        # Run synthesis again for determinism check
        synthesized_run2 = synthesize_all(project_id, existing)

        # Evaluate each benchmark
        print("Knowledge Synthesis Evaluation:")
        print("=" * 60)

        for benchmark in benchmarks:
            evaluator = KnowledgeEvaluator(benchmark)
            result = evaluator.evaluate(synthesized, previous_synthesis=synthesized_run2)

            from relay.evaluation.thresholds import EvaluationThresholds
            thresholds = EvaluationThresholds()
            gate_passed, failures = check_knowledge_gates(result, thresholds)
            status = "[PASS]" if gate_passed else "[FAIL]"

            print(f"\nBenchmark: {benchmark.benchmark_id} v{benchmark.benchmark_version} {status}")
            print(f"  Expected: {result.expected_count} | Synthesized: {result.synthesized_count}")
            print(f"  Precision:        {result.precision * 100:.1f}%")
            print(f"  Semantic Recall:  {result.semantic_recall * 100:.1f}%")
            print(f"  Identity Recall:  {result.identity_recall * 100:.1f}%")
            print(f"  F1:               {result.f1_score * 100:.1f}%")
            print(f"  Determinism:      {result.determinism_score * 100:.1f}%")
            print(f"  Provenance:       {result.provenance_pct * 100:.1f}%")
            print(f"  Provenance Depth: {result.average_provenance_depth:.1f}")
            print(f"  Type Coverage:    {result.type_coverage * 100:.1f}%")

            if not gate_passed:
                print(f"  Gate Failures: {', '.join(failures)}")


def cmd_context(args: argparse.Namespace) -> None:
    """Compile and display unified context from events, memories, and knowledge."""
    import json
    from relay.knowledge.context_compiler import compile_context
    from relay.knowledge.evaluation_i5 import compute_context_metrics

    # Resolve project ID
    project_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
    project_yaml = Path.cwd() / ".relay" / "project.yaml"
    if project_yaml.exists():
        try:
            import yaml
            with open(project_yaml, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            project_id = uuid.UUID(config.get("project_id", str(project_id)))
        except Exception:
            pass

    package = compile_context(
        query=args.query,
        project_id=project_id,
        total_slices=args.limit,
    )

    # Agent-specific compilation
    if args.agent:
        import sys, io
        from relay.compilers.registry import get_context_compiler
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
        from relay.knowledge.evaluation_i5 import extract_keywords_from_query
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
        from relay.evaluation.context_benchmark_schema import ContextBenchmark
        from relay.evaluation.context_evaluator import ContextEvaluator, check_context_gates
        benchmark_dir = Path.cwd() / "relay" / "evaluation" / "context_benchmarks"
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
    from relay.knowledge.factory import get_knowledge_provider
    from relay.knowledge.relations import detect_relations
    from relay.knowledge.graph import GraphProjection
    from relay.knowledge.graph_evaluation import evaluate_graph_projection, check_graph_gates
    import json
    
    project_root = Path.cwd()
    graph_file = project_root / ".relay" / "graph.json"
    
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
            print("Error: Graph has not been built yet. Run 'relay graph build' first.")
            sys.exit(1)
            
        with open(graph_file, "r", encoding="utf-8") as f:
            projection = GraphProjection.from_dict(json.load(f))
            
        stats = projection.stats()
        provider = get_knowledge_provider()
        knowledge = provider.get_all_knowledge()
        relations = detect_relations(knowledge)
        eval_result = evaluate_graph_projection(projection, knowledge, relations, previous_projection=projection)
        
        print("Relay Knowledge Graph Statistics:")
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
            print("Error: Graph has not been built yet. Run 'relay graph build' first.")
            sys.exit(1)
            
        with open(graph_file, "r", encoding="utf-8") as f:
            projection = GraphProjection.from_dict(json.load(f))
            
        node = projection.query_node(args.node_id)
        if not node:
            print(f"Error: Node with ID/Prefix '{args.node_id}' not found.")
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
                print(f"  {e.source[:8]} -->|{e.relation_type}| {e.target[:8]} (conf: {e.confidence:.2f})")

    elif args.graph_command == "query-path":
        if not graph_file.exists():
            print("Error: Graph has not been built yet. Run 'relay graph build' first.")
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
            print(f"Error: Unknown format '{args.format}'")
            sys.exit(1)
            
        if args.output:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"[SUCCESS] Exported graph to {out_path} in {fmt} format.")
        else:
            print(output)


def cmd_evaluate(args: argparse.Namespace) -> None:
    from relay.evaluation.evaluator import run_full_evaluation
    result = run_full_evaluation()
    
    print("\n=== Relay Evaluation ===")
    print(f"Relay version:  {result.relay_version}")
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Relay Multi-Agent Memory Layer CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    subparsers.add_parser("init", help="Initialize Relay in the current project directory")

    # install
    parser_install = subparsers.add_parser("install", help="Install platform adapters")
    parser_install.add_argument("--platform", required=True, help="Target platform (claude, cursor, opencode, copilot)")

    # uninstall
    subparsers.add_parser("uninstall", help="Uninstall Relay adapters and configs from current project")

    # doctor
    subparsers.add_parser("doctor", help="Check diagnostics and system status")

    # generate-adapters
    subparsers.add_parser("generate-adapters", help="Recompile adapter templates")

    # migrate-storage
    parser_migrate = subparsers.add_parser("migrate-storage", help="Migrate event stream between storage backends")
    parser_migrate.add_argument("--from", dest="frm", required=True, choices=["sqlite", "postgres"], help="Source backend")
    parser_migrate.add_argument("--to", required=True, choices=["sqlite", "postgres"], help="Target backend")

    # memory
    from relay.memory.models import MemoryType
    parser_memory = subparsers.add_parser("memory", help="Manage Relay Memory Bridge")
    mem_subparsers = parser_memory.add_subparsers(dest="mem_command", required=True)

    # memory add
    parser_mem_add = mem_subparsers.add_parser("add", help="Manually record a memory")
    parser_mem_add.add_argument("--title", required=True, help="Title of the memory")
    parser_mem_add.add_argument("--content", required=True, help="Detailed body of the memory")
    parser_mem_add.add_argument("--type", required=True, choices=[t.value for t in MemoryType], help="Type of memory")
    parser_mem_add.add_argument("--tags", help="Comma-separated list of tags")

    # memory search
    parser_mem_search = mem_subparsers.add_parser("search", help="Search memories by query string")
    parser_mem_search.add_argument("--query", required=True, help="Query string")

    # memory compile
    parser_mem_compile = mem_subparsers.add_parser("compile", help="Compile structured context grouped by MemoryType")
    parser_mem_compile.add_argument("--query", required=True, help="Query string to filter intent")

    # memory list
    mem_subparsers.add_parser("list", help="List all stored memories")

    # memory stats
    mem_subparsers.add_parser("stats", help="Show baseline memory quality/deduplication metrics")

    # memory show
    parser_mem_show = mem_subparsers.add_parser("show", help="Show details of a specific memory record by ID")
    parser_mem_show.add_argument("id", help="Memory record ID")

    # memory consolidate
    mem_subparsers.add_parser("consolidate", help="Detect duplicate clusters and emit candidates to the ledger")

    # knowledge
    from relay.knowledge.models import KnowledgeType, KnowledgeDomain
    parser_knowledge = subparsers.add_parser("knowledge", help="Manage Relay Knowledge Synthesis")
    knowledge_subparsers = parser_knowledge.add_subparsers(dest="knowledge_command", required=True)

    # knowledge synthesize
    knowledge_subparsers.add_parser("synthesize", help="Synthesize knowledge from memories")

    # knowledge list
    knowledge_subparsers.add_parser("list", help="List all synthesized knowledge objects")

    # knowledge stats
    knowledge_subparsers.add_parser("stats", help="Show knowledge synthesis metrics")

    # knowledge show
    parser_knowledge_show = knowledge_subparsers.add_parser("show", help="Show details of a specific knowledge object by ID")
    parser_knowledge_show.add_argument("id", help="Knowledge object ID")

    # knowledge search
    parser_knowledge_search = knowledge_subparsers.add_parser("search", help="Search knowledge by query string")
    parser_knowledge_search.add_argument("--query", required=True, help="Query string")

    # knowledge evaluate
    knowledge_subparsers.add_parser("evaluate", help="Evaluate knowledge against benchmarks")

    # context
    parser_context = subparsers.add_parser("context", help="Compile unified context from events, memories, and knowledge")
    parser_context.add_argument("--query", required=True, help="Query string")
    parser_context.add_argument("--limit", type=int, default=30, help="Max total citations (default: 30)")
    parser_context.add_argument("--output", choices=["json", "summary", "evaluate"], default="summary", help="Output format")
    parser_context.add_argument("--agent", choices=["claude", "opencode", "cursor"], default=None, help="Compile for specific agent (overrides --output)")

    # graph
    parser_graph = subparsers.add_parser("graph", help="Manage Relay Knowledge Graph Projection")
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

    # evaluate
    subparsers.add_parser("evaluate", help="Run the unified evaluation suite across all subsystems")

    args = parser.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "install":
        cmd_install(args)
    elif args.command == "uninstall":
        cmd_uninstall(args)
    elif args.command == "doctor":
        cmd_doctor(args)
    elif args.command == "generate-adapters":
        cmd_generate_adapters(args)
    elif args.command == "migrate-storage":
        cmd_migrate_storage(args)
    elif args.command == "memory":
        cmd_memory(args)
    elif args.command == "knowledge":
        cmd_knowledge(args)
    elif args.command == "context":
        cmd_context(args)
    elif args.command == "graph":
        cmd_graph(args)
    elif args.command == "evaluate":
        cmd_evaluate(args)


if __name__ == "__main__":
    main()
