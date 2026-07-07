import argparse
import sys
import uuid
from pathlib import Path


def register(subparsers: argparse._SubParsersAction) -> None:
    parser_knowledge = subparsers.add_parser("knowledge", help="Manage RationaleVault Knowledge Synthesis")
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

    parser_knowledge.set_defaults(func=handler)


def handler(args: argparse.Namespace) -> None:
    import json
    import yaml
    from rationalevault.knowledge.factory import get_knowledge_provider
    from rationalevault.knowledge.synthesizer import synthesize_all
    from rationalevault.knowledge.evaluation import compute_knowledge_metrics

    provider = get_knowledge_provider()

    if args.knowledge_command == "synthesize":
        project_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
        project_yaml = Path.cwd() / ".rationalevault" / "project.yaml"
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
        from rationalevault.memory.factory import get_memory_provider
        mem_provider = get_memory_provider()
        memory_count = len(mem_provider.get_all_records())
        knowledge = provider.get_all_knowledge()

        metrics = compute_knowledge_metrics(
            knowledge, [], memory_count=memory_count
        )

        print("RationaleVault Knowledge Synthesis Metrics:")
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
        from rationalevault.knowledge.evaluator import KnowledgeEvaluator, check_knowledge_gates
        from rationalevault.knowledge.benchmark_schema import KnowledgeBenchmark
        from rationalevault.knowledge.synthesizer import synthesize_all

        # Load benchmarks
        knowledge_cases_dir = Path.cwd() / "rationalevault" / "evaluation" / "knowledge_cases"
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
        project_yaml = Path.cwd() / ".rationalevault" / "project.yaml"
        if project_yaml.exists():
            try:
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

            from rationalevault.evaluation.thresholds import EvaluationThresholds
            thresholds = EvaluationThresholds()
            gate_passed, failures = check_knowledge_gates(result, thresholds)
            status = "[PASS]" if gate_passed else "[FAIL]"

            print(f"\\nBenchmark: {benchmark.benchmark_id} v{benchmark.benchmark_version} {status}")
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
