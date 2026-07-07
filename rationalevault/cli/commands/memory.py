import argparse
import sys
import uuid
from pathlib import Path


def register(subparsers: argparse._SubParsersAction) -> None:
    from rationalevault.memory.models import MemoryType
    parser_memory = subparsers.add_parser("memory", help="Manage RationaleVault Memory Bridge")
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

    parser_memory.set_defaults(func=handler)


def handler(args: argparse.Namespace) -> None:
    from rationalevault.memory.factory import get_memory_provider
    from rationalevault.memory.models import MemoryRecord, MemoryType, generate_memory_id
    from rationalevault.memory.compiler import compile_memory_context
    from rationalevault.memory.ranking import compute_retrieval_score
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
            project_id="",
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
        from rationalevault.memory.retrieval import retrieve_ranked_citations
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
        from rationalevault.memory.citation_builder import build_citation
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
            
        print("RationaleVault Memory Bridge Statistics:")
        print("=" * 40)
        print(f"Total Memory Records:          {total_records}")
        print(f"Unique Memories (IDs):        {unique_ids}")
        print(f"Memory Deduplication Rate:    {deduplication_rate:.2%}")
        print(f"Memory With Provenance:       {provenance_pct:.2%}")
        print("\\nMemories by Type:")
        for t, count in sorted(by_type.items()):
            print(f"  {t:<20}: {count}")
        print("=" * 40)

    elif args.mem_command == "consolidate":
        from rationalevault.memory.consolidation import detect_consolidation_candidates, emit_consolidation_candidates
        import yaml
        project_root = Path.cwd()
        project_yaml = project_root / ".rationalevault" / "project.yaml"
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
