"""RationaleVault Unified Evaluator — Pipeline to evaluate the quality and health of the entire cognitive platform."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from rationalevault.evaluation.thresholds import EvaluationThresholds
from rationalevault import __version__ as VERSION, SCHEMA_VERSION


@dataclass
class EvaluationResult:
    """Consolidated evaluation results."""
    rationalevault_version: str
    schema_version: str
    memory_passed: bool
    knowledge_passed: bool
    context_passed: bool
    compiler_passed: bool
    continuity_passed: bool
    graph_passed: bool
    graph_projection_passed: bool
    examples_passed: bool
    overall_passed: bool
    report_path: str
    metrics: dict[str, Any] = field(default_factory=dict)


def run_full_evaluation() -> EvaluationResult:
    """Run all evaluation suites across memory, knowledge, context, compilers, continuity, graph, and examples."""
    metrics: dict[str, Any] = {}
    thresholds = EvaluationThresholds()

    # ── Insert Mock Evaluation Data ───────────────────────────────────────
    import uuid
    from rationalevault.memory.models import MemoryRecord, MemoryType
    from rationalevault.schema.events import EventMetadata, EventType
    from rationalevault.db.factory import get_event_store
    from rationalevault.memory.factory import get_memory_provider
    from rationalevault.knowledge.factory import get_knowledge_provider
    from rationalevault.knowledge.models import KnowledgeObject, KnowledgeType, KnowledgeDomain, KnowledgeConfidence, ProvenanceChain

    project_uuid = uuid.UUID("00000000-0000-0000-0000-000000000000")
    
    mem_prov = get_memory_provider()
    k_prov = get_knowledge_provider()
    event_store = get_event_store()

    # Clear residual records to prevent graph pollution from test suites
    # 1. Clear Markdown files
    for filename in ("knowledge.md", "memory.md"):
        path = Path.cwd() / ".rationalevault" / filename
        if path.exists():
            try:
                path.unlink()
            except Exception:
                pass

    # 2. Clear SQLite databases
    if hasattr(k_prov, "_get_conn"):
        try:
            conn = k_prov._get_conn()
            conn.execute("DELETE FROM rationalevault_knowledge")
            conn.commit()
            conn.close()
        except Exception:
            pass
    if hasattr(mem_prov, "_get_conn"):
        try:
            conn = mem_prov._get_conn()
            conn.execute("DELETE FROM rationalevault_memories")
            conn.commit()
            conn.close()
        except Exception:
            pass

    # Create mock memories
    mock_m1 = MemoryRecord(
        id="eval_temp_mem_1",
        version=1,
        title="Test Memory One",
        content="This is a test memory record containing the term test query.",
        memory_type=MemoryType.DECISION,
        importance="high",
        lifecycle_status="active",
        source_event_ids=["eval_temp_ev_1"],
        source_type="event",
        confidence=1.0,
        project_id=str(project_uuid),
    )
    mock_m2 = MemoryRecord(
        id="eval_temp_mem_2",
        version=1,
        title="Test Memory Two",
        content="This is another test memory record containing query keywords.",
        memory_type=MemoryType.IMPLEMENTATION_NOTE,
        importance="medium",
        lifecycle_status="active",
        source_event_ids=["eval_temp_ev_2"],
        source_type="event",
        confidence=1.0,
        project_id=str(project_uuid),
    )

    # Create mock knowledge
    k_conf = KnowledgeConfidence(1, 1, 0, 1.0)
    prov1 = ProvenanceChain(
        knowledge_id="eval_temp_k_1",
        source_memory_ids=["eval_temp_mem_1"],
        source_event_ids=["eval_temp_ev_1"],
        synthesis_event_id="eval_temp_syn_1",
        confidence=k_conf,
        evidence_count=1
    )
    mock_ko1 = KnowledgeObject(
        id="eval_temp_k_1",
        version=1,
        title="Test Knowledge One",
        content="Test query principle for system diagnostics.",
        knowledge_type=KnowledgeType.ARCHITECTURE_PRINCIPLE,
        knowledge_domain=KnowledgeDomain.ARCHITECTURE,
        confidence=k_conf,
        importance="critical",
        provenance=prov1,
        tags=["test"],
        project_id=str(project_uuid),
        lifecycle_status="ACTIVE",
    )
    prov2 = ProvenanceChain(
        knowledge_id="eval_temp_k_2",
        source_memory_ids=["eval_temp_mem_2"],
        source_event_ids=["eval_temp_ev_2"],
        synthesis_event_id="eval_temp_syn_2",
        confidence=k_conf,
        evidence_count=1
    )
    mock_ko2 = KnowledgeObject(
        id="eval_temp_k_2",
        version=1,
        title="Test Knowledge Two",
        content="Test query principle for system diagnostics.",
        knowledge_type=KnowledgeType.ARCHITECTURE_PRINCIPLE,
        knowledge_domain=KnowledgeDomain.ARCHITECTURE,
        confidence=k_conf,
        importance="critical",
        provenance=prov2,
        tags=["test"],
        project_id=str(project_uuid),
        lifecycle_status="ACTIVE",
    )

    # State variables for evaluation
    memory_passed = True
    knowledge_passed = True
    context_passed = True
    compiler_passed = True
    continuity_passed = True
    graph_passed = True
    graph_projection_passed = True
    examples_passed = True

    try:
        # Seeding
        metadata = EventMetadata(actor="evaluator", source="evaluator", session_id="eval-session-1")
        event_store.append_event(
            project_id=project_uuid,
            stream_id="main",
            event_type=EventType.PROJECT_CREATED,
            payload={"name": "Test Project"},
            metadata=metadata,
        )
        event_store.append_event(
            project_id=project_uuid,
            stream_id="main",
            event_type=EventType.PROJECT_GOAL_SET,
            payload={"goal": "Test query goal set"},
            metadata=metadata,
        )
        event_store.append_event(
            project_id=project_uuid,
            stream_id="main",
            event_type=EventType.PROJECT_FOCUS_CHANGED,
            payload={"focus": "Test focus"},
            metadata=metadata,
        )
        event_store.append_event(
            project_id=project_uuid,
            stream_id="main",
            event_type=EventType.DECISION_PROPOSED,
            payload={
                "decision_id": "d1",
                "title": "Test query decision accepted",
                "rationale": "",
                "description": "Test description",
            },
            metadata=metadata,
        )
        event_store.append_event(
            project_id=project_uuid,
            stream_id="main",
            event_type=EventType.DECISION_ACCEPTED,
            payload={"decision_id": "d1"},
            metadata=metadata,
        )
        event_store.append_event(
            project_id=project_uuid,
            stream_id="tasks",
            event_type=EventType.TASK_CREATED,
            payload={
                "task_id": "t1",
                "priority": "high",
                "details": {
                    "summary": "Test task",
                    "body": "Test description",
                }
            },
            metadata=metadata,
        )
        event_store.append_event(
            project_id=project_uuid,
            stream_id="tasks",
            event_type=EventType.TASK_MUTATED,
            payload={"task_id": "t1", "status": "in_progress"},
            metadata=metadata,
        )
        event_store.append_event(
            project_id=project_uuid,
            stream_id="tasks",
            event_type=EventType.TASK_PROGRESS_NOTED,
            payload={"task_id": "t1", "note": "Progress note"},
            metadata=metadata,
        )
        event_store.append_event(
            project_id=project_uuid,
            stream_id="questions",
            event_type=EventType.OPEN_QUESTION_RAISED,
            payload={"question_id": "q1", "title": "Open question", "priority": "normal"},
            metadata=metadata,
        )
        event_store.append_event(
            project_id=project_uuid,
            stream_id="main",
            event_type=EventType.CONTEXT_SNAPSHOT_RECORDED,
            payload={
                "summary": "Test query goal set summary",
                "blocked_on": "something block",
                "next_action": "Do next things"
            },
            metadata=metadata,
        )

        mem_prov.add_record(mock_m1)
        mem_prov.add_record(mock_m2)

        k_prov.add_knowledge(mock_ko1)
        k_prov.add_knowledge(mock_ko2)

        # 1. Memory Evaluation
        records = mem_prov.get_all_records()
        total_records = len(records)
        unique_ids = len({r.id for r in records})
        deduplication_rate = unique_ids / total_records if total_records > 0 else 1.0
        with_provenance = sum(1 for r in records if r.source_event_ids)
        provenance_pct = (with_provenance / total_records) if total_records > 0 else 1.0

        metrics["memory"] = {
            "total_records": total_records,
            "deduplication_rate": deduplication_rate,
            "provenance_pct": provenance_pct,
        }
        if deduplication_rate < thresholds.MIN_MEMORY_DEDUPLICATION_RATE:
            memory_passed = False
        if provenance_pct < thresholds.MIN_MEMORY_PROVENANCE_PCT:
            memory_passed = False

        # 2. Knowledge Evaluation
        from rationalevault.knowledge.evaluation import compute_knowledge_metrics
        k_list = k_prov.get_all_knowledge()
        k_metrics = compute_knowledge_metrics(k_list, [], memory_count=len(records))
        passed, failures = k_metrics.passes_exit_gates()
        metrics["knowledge"] = k_metrics.to_dict()
        if not passed:
            knowledge_passed = False

        # 3. Context & Compiler Evaluation
        from rationalevault.knowledge.context_compiler import compile_context
        package = compile_context("test query", project_uuid, total_slices=10)
        
        from rationalevault.knowledge.evaluation_i5 import compute_context_metrics
        ctx_metrics = compute_context_metrics(package, keywords=["test"])
        passed, failures = ctx_metrics.passes_exit_gates()
        metrics["context"] = ctx_metrics.to_dict()
        if not passed:
            context_passed = False

        from rationalevault.compilers.registry import get_context_compiler
        compiler = get_context_compiler("claude")
        output = compiler.compile(package)
        
        compiler_passed = output.rendered_content is not None
        metrics["compiler"] = {
            "claude_compiled_len": len(output.rendered_content) if output.rendered_content else 0,
        }

        # 4. Continuity Validation
        from rationalevault.knowledge.context_compiler import compile_context, ContextMode
        from rationalevault.compilers.claude_context import ClaudeContextCompiler
        from rationalevault.evaluation.continuation_evaluator import ContinuationEvaluator

        cont_package = compile_context("continue", project_uuid, mode=ContextMode.CONTINUATION)
        compiler = ClaudeContextCompiler()
        cont_output = compiler.compile(cont_package)
        
        if cont_package.continuation_state:
            cont_evaluator = ContinuationEvaluator()
            cont_result = cont_evaluator.evaluate(cont_package.continuation_state, cont_output.rendered_content)
            gate_passed, failures = cont_result.passes_exit_gate()
            continuity_passed = gate_passed
            metrics["continuity"] = cont_result.to_dict()
        else:
            continuity_passed = False
            metrics["continuity"] = {"error": "No continuation state compiled"}


        # 5. Graph Evaluation
        from rationalevault.knowledge.relations import detect_relations
        from rationalevault.knowledge.graph import GraphProjection
        from rationalevault.knowledge.graph_evaluation import evaluate_graph_projection, check_graph_gates

        knowledge_objs = k_prov.get_all_knowledge()
        relations = detect_relations(knowledge_objs)
        projection = GraphProjection.build(knowledge_objs, relations)
        projection2 = GraphProjection.build(knowledge_objs, relations)

        eval_result = evaluate_graph_projection(projection, knowledge_objs, relations, previous_projection=projection2)
        passed, failures = check_graph_gates(eval_result)
        metrics["graph"] = eval_result.to_dict()
        if not passed:
            graph_passed = False

        # 5b. Graph Projection Evaluation (new GraphState evaluator)
        from rationalevault.projections.knowledge import KnowledgeProjection as NewKnowledgeProjection
        from rationalevault.projections.graph import GraphProjection as NewGraphProjection
        from rationalevault.evaluation.graph_projection_evaluator import (
            GraphProjectionEvaluator,
            check_graph_projection_gates,
        )

        try:
            ks = NewKnowledgeProjection.project(str(project_uuid))
            gs = NewGraphProjection.project(ks)
            gs2 = NewGraphProjection.project(ks)

            gp_evaluator = GraphProjectionEvaluator()
            gp_result = gp_evaluator.evaluate(gs, previous_state=gs2)
            gp_passed, gp_failures = check_graph_projection_gates(gp_result)
            metrics["graph_projection"] = gp_result.to_dict()
            if not gp_passed:
                graph_projection_passed = False
        except Exception as ex:
            graph_projection_passed = False
            metrics["graph_projection"] = {"error": f"Graph projection evaluation failed: {str(ex)}"}

    except Exception as e:
        # Any exception in pipeline means failure
        memory_passed = False
        knowledge_passed = False
        context_passed = False
        compiler_passed = False
        graph_passed = False
        graph_projection_passed = False
        metrics["error"] = str(e)
    finally:
        # Clean up mock database records
        # 1. Clean memories
        if hasattr(mem_prov, "_get_conn"):
            conn = mem_prov._get_conn()
            try:
                conn.execute("DELETE FROM rationalevault_memories WHERE id LIKE 'eval_temp_%'")
                conn.commit()
            except Exception:
                pass
            finally:
                conn.close()

        # 2. Clean knowledge
        if hasattr(k_prov, "_get_conn"):
            conn = k_prov._get_conn()
            try:
                conn.execute("DELETE FROM rationalevault_knowledge WHERE id LIKE 'eval_temp_%'")
                conn.commit()
            except Exception:
                pass
            finally:
                conn.close()

        # 3. Clean events
        if hasattr(event_store, "_store") and hasattr(event_store._store, "_get_conn"):
            conn = event_store._store._get_conn()
            try:
                conn.execute("DELETE FROM rationalevault_events WHERE project_id = ?", (str(project_uuid),))
                conn.commit()
            except Exception:
                pass
            finally:
                conn.close()
        elif hasattr(event_store, "_get_conn"):
            conn = event_store._get_conn()
            try:
                conn.execute("DELETE FROM rationalevault_events WHERE project_id = ?", (str(project_uuid),))
                conn.commit()
            except Exception:
                pass
            finally:
                conn.close()

    # 6. Examples Verification — use package-bundled copies (CWD-agnostic)
    examples_status = {}
    try:
        from rationalevault.examples.basic_memory import main as run_basic_memory
        print("\n[EVAL] Executing: basic_memory example")
        run_basic_memory()
        examples_status["basic_memory"] = "PASS"
    except Exception as e:
        examples_passed = False
        examples_status["basic_memory"] = f"FAIL: {str(e)}"

    try:
        from rationalevault.examples.knowledge_synthesis import main as run_knowledge_synthesis
        print("[EVAL] Executing: knowledge_synthesis example")
        run_knowledge_synthesis()
        examples_status["knowledge_synthesis"] = "PASS"
    except Exception as e:
        examples_passed = False
        examples_status["knowledge_synthesis"] = f"FAIL: {str(e)}"

    try:
        from rationalevault.examples.multi_agent_handoff import main as run_multi_agent_handoff
        print("[EVAL] Executing: multi_agent_handoff example")
        run_multi_agent_handoff()
        examples_status["multi_agent_handoff"] = "PASS"
    except Exception as e:
        examples_passed = False
        examples_status["multi_agent_handoff"] = f"FAIL: {str(e)}"

    metrics["examples"] = examples_status

    # Overall Gate
    overall_passed = all([
        memory_passed,
        knowledge_passed,
        context_passed,
        compiler_passed,
        continuity_passed,
        graph_passed,
        graph_projection_passed,
        examples_passed,
    ])

    # Cognitive Continuity Score (CCS)
    from rationalevault.evaluation.thresholds import CCS_WEIGHTS

    continuation_rate = metrics.get("continuity", {}).get("continuation_success_rate", 0.0)
    knowledge_rate = metrics.get("knowledge", {}).get("knowledge_projection_success_rate", 0.0)
    gp_rate = metrics.get("graph_projection", {}).get("graph_projection_success_rate", 0.0)

    ccs = (
        CCS_WEIGHTS["continuation"] * continuation_rate
        + CCS_WEIGHTS["knowledge"] * knowledge_rate
        + CCS_WEIGHTS["graph"] * gp_rate
    )

    if ccs >= 0.95:
        ccs_grade = "EXCELLENT"
    elif ccs >= 0.85:
        ccs_grade = "GOOD"
    elif ccs >= 0.70:
        ccs_grade = "FAIR"
    else:
        ccs_grade = "POOR"

    metrics["ccs"] = {
        "score": round(ccs, 4),
        "grade": ccs_grade,
        "weights": CCS_WEIGHTS,
        "components": {
            "continuation": continuation_rate,
            "knowledge": knowledge_rate,
            "graph": gp_rate,
        },
    }

    # Output Reports Directory (use .rationalevault/ to match renamed package)
    reports_dir = Path.cwd() / ".rationalevault" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = reports_dir / "release_manifest.json"

    # Write Manifest
    manifest_data = {
        "rationalevault_version": VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().isoformat(),
        "evaluations": {
            "memory": "PASS" if memory_passed else "FAIL",
            "knowledge": "PASS" if knowledge_passed else "FAIL",
            "context": "PASS" if context_passed else "FAIL",
            "compiler": "PASS" if compiler_passed else "FAIL",
            "continuity": "PASS" if continuity_passed else "FAIL",
            "graph": "PASS" if graph_passed else "FAIL",
            "graph_projection": "PASS" if graph_projection_passed else "FAIL",
        },
        "ccs": metrics.get("ccs", {}),
        "examples": examples_status,
        "metrics": metrics,
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    # Write Markdown Summary Report
    md_report_path = reports_dir / "report.md"
    with open(md_report_path, "w", encoding="utf-8") as f:
        f.write(f"# RationaleVault Platform Evaluation Summary (v{VERSION})\n\n")
        f.write(f"Generated at: {datetime.now().isoformat()}\n")
        f.write(f"Overall Pass Verdict: {'**PASS**' if overall_passed else '**FAIL**'}\n\n")
        f.write("## Subsystem Verification\n\n")
        f.write(f"- **Memory**: {'PASS' if memory_passed else 'FAIL'}\n")
        f.write(f"- **Knowledge**: {'PASS' if knowledge_passed else 'FAIL'}\n")
        f.write(f"- **Context**: {'PASS' if context_passed else 'FAIL'}\n")
        f.write(f"- **Compiler**: {'PASS' if compiler_passed else 'FAIL'}\n")
        f.write(f"- **Continuity**: {'PASS' if continuity_passed else 'FAIL'}\n")
        f.write(f"- **Graph Projection**: {'PASS' if graph_passed else 'FAIL'}\n")
        f.write(f"- **Graph Projection (new)**: {'PASS' if graph_projection_passed else 'FAIL'}\n")
        f.write(f"- **Examples execution**: {'PASS' if examples_passed else 'FAIL'}\n\n")
        f.write(f"## Cognitive Continuity Score\n\n")
        ccs_data = metrics.get("ccs", {})
        f.write(f"- **Score:** {ccs_data.get('score', 'N/A')}\n")
        f.write(f"- **Grade:** {ccs_data.get('grade', 'N/A')}\n")
        f.write(f"- **Components:** continuation={ccs_data.get('components', {}).get('continuation', 0):.2f}, "
                f"knowledge={ccs_data.get('components', {}).get('knowledge', 0):.2f}, "
                f"graph={ccs_data.get('components', {}).get('graph', 0):.2f}\n\n")
        f.write("## Example Runs Status\n\n")
        for ex_name, ex_verdict in examples_status.items():
            f.write(f"- `{ex_name}`: {ex_verdict}\n")

    return EvaluationResult(
        rationalevault_version=VERSION,
        schema_version=SCHEMA_VERSION,
        memory_passed=memory_passed,
        knowledge_passed=knowledge_passed,
        context_passed=context_passed,
        compiler_passed=compiler_passed,
        continuity_passed=continuity_passed,
        graph_passed=graph_passed,
        graph_projection_passed=graph_projection_passed,
        examples_passed=examples_passed,
        overall_passed=overall_passed,
        report_path=str(manifest_path),
        metrics=metrics,
    )
