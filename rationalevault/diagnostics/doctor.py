"""RationaleVault Diagnostics Doctor — Active and static system health verification."""
from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from rationalevault.evaluation.thresholds import EvaluationThresholds
from rationalevault import __version__ as VERSION


@dataclass
class HealthCheck:
    """Result of a single diagnostic health check."""
    component: str
    status: str  # PASS | WARN | FAIL
    details: str


@dataclass
class HealthReport:
    """Diagnostic health report for the Relay system."""
    rationalevault_version: str
    overall_passed: bool
    generated_at: str
    checks: list[HealthCheck]

    def to_dict(self) -> dict[str, Any]:
        return {
            "rationalevault_version": self.rationalevault_version,
            "overall_passed": self.overall_passed,
            "generated_at": self.generated_at,
            "checks": [
                {
                    "component": c.component,
                    "status": c.status,
                    "details": c.details,
                }
                for c in self.checks
            ],
        }


def run_diagnostics() -> HealthReport:
    """Run all system checks and diagnostics."""
    checks: list[HealthCheck] = []

    # 1. Event Store Health
    try:
        from rationalevault.db.factory import get_event_store
        store = get_event_store()
        # Ping check
        store.get_event_count(uuid.UUID("00000000-0000-0000-0000-000000000000"))
        checks.append(HealthCheck("Event Store", "PASS", f"Connected to {type(store).__name__}"))
    except Exception as e:
        checks.append(HealthCheck("Event Store", "FAIL", f"Failed connection: {str(e)}"))

    # 2. Memory Store Health
    try:
        from rationalevault.memory.factory import get_memory_provider
        mem_prov = get_memory_provider()
        mem_prov.get_all_records()
        checks.append(HealthCheck("Memory Store", "PASS", f"Connected to {type(mem_prov).__name__}"))
    except Exception as e:
        checks.append(HealthCheck("Memory Store", "FAIL", f"Failed lookup: {str(e)}"))

    # 3. Knowledge Store Health
    try:
        from rationalevault.knowledge.factory import get_knowledge_provider
        k_prov = get_knowledge_provider()
        k_prov.get_all_knowledge()
        checks.append(HealthCheck("Knowledge Store", "PASS", f"Connected to {type(k_prov).__name__}"))
    except Exception as e:
        checks.append(HealthCheck("Knowledge Store", "FAIL", f"Failed lookup: {str(e)}"))

    # 4. Evaluation Assets Presence (package-relative, CWD-agnostic)
    try:
        import importlib.resources
        eval_pkg = importlib.resources.files("rationalevault.evaluation")
        # Verify key sub-packages are accessible (works in wheel installs too)
        knowledge_cases = eval_pkg.joinpath("knowledge_cases")
        items = list(knowledge_cases.iterdir())
        bench_exists = len(items) > 0
        bench_desc = f"Package assets verified ({len(items)} knowledge benchmark files)"
    except Exception as e:
        bench_exists = False
        bench_desc = f"Package assets inaccessible: {e}"
    if bench_exists:
        checks.append(HealthCheck("Evaluation Assets", "PASS", bench_desc))
    else:
        checks.append(HealthCheck("Evaluation Assets", "WARN", bench_desc))

    # 5. Thresholds Loaded
    try:
        thresholds = EvaluationThresholds()
        checks.append(HealthCheck("Evaluation Thresholds", "PASS", f"Successfully instanced EvaluationThresholds with {len(vars(thresholds))} parameters"))
    except Exception as e:
        checks.append(HealthCheck("Evaluation Thresholds", "FAIL", f"Failed to load thresholds: {str(e)}"))

    # 6. Graph Projection Engine
    try:
        from rationalevault.knowledge.graph import GraphProjection
        # Try constructing an empty graph
        proj = GraphProjection.build([], [])
        checks.append(HealthCheck("Graph Projection", "PASS", f"Graph engine loaded successfully (ID: {proj.graph_id[:8]}...)"))
    except Exception as e:
        checks.append(HealthCheck("Graph Projection", "FAIL", f"Failed to run graph builder: {str(e)}"))

    # 7. Compiler Registry
    try:
        from rationalevault.compilers.registry import get_context_compiler
        get_context_compiler("claude")
        get_context_compiler("opencode")
        get_context_compiler("cursor")
        checks.append(HealthCheck("Compiler Registry", "PASS", "Successfully registered compilers: claude, opencode, cursor"))
    except Exception as e:
        checks.append(HealthCheck("Compiler Registry", "FAIL", f"Failed to load compiler adapters: {str(e)}"))

    # 8. Active Projection Chain Verification (End-to-End Synthetic Pipe)
    proj_chain_passed = True
    proj_chain_details = "Pipeline fully functional"
    try:
        # Step A: Memory record
        from rationalevault.memory.models import MemoryRecord, MemoryType
        from rationalevault.memory.citation_builder import build_citation
        mem = MemoryRecord(
            id="synth_mem_123",
            version=1,
            title="Synthetic Memory Title",
            content="Synthetic Memory Content describing goal fulfillment.",
            memory_type=MemoryType.DECISION,
            importance="high",
            lifecycle_status="active",
            source_event_ids=["synth_ev_123"],
            source_type="synthetic",
            confidence=1.0,
        )

        # Step B: KnowledgeObject
        from rationalevault.knowledge.models import KnowledgeObject, KnowledgeType, KnowledgeDomain, KnowledgeConfidence, ProvenanceChain, KnowledgeRelation
        k_conf = KnowledgeConfidence(1, 1, 0, 1.0)
        prov = ProvenanceChain(
            knowledge_id="synth_k_123",
            source_memory_ids=["synth_mem_123"],
            source_event_ids=["synth_ev_123"],
            synthesis_event_id="synth_syn_123",
            confidence=k_conf,
            evidence_count=1
        )
        ko = KnowledgeObject(
            id="synth_k_123",
            version=1,
            title="Synthetic Invariant",
            content="Always assert synthetic truth.",
            knowledge_type=KnowledgeType.PROJECT_INVARIANT,
            knowledge_domain=KnowledgeDomain.ARCHITECTURE,
            confidence=k_conf,
            importance="critical",
            provenance=prov,
            tags=["synthetic"],
        )

        # Step C: Graph Build
        from rationalevault.knowledge.graph import GraphProjection
        rel = KnowledgeRelation(source_id="synth_k_123", target_id="synth_k_123", relation_type="RELATED_TO", confidence=1.0)
        GraphProjection.build([ko], [rel])

        # Step D: Context compilation
        from rationalevault.knowledge.context_compiler import ContextPackage
        from rationalevault.knowledge.context_types import ContextCitation
        
        citation = ContextCitation(
            source_type="memory",
            source_id="synth_mem_123",
            title="Synthetic Memory Title",
            content="Synthetic Memory Content describing goal fulfillment.",
            relevance_score=0.9,
            confidence=1.0,
            reasons=["manual"],
            source_event_ids=["synth_ev_123"],
        )
        k_citation = ContextCitation(
            source_type="knowledge",
            source_id="synth_k_123",
            title="Synthetic Invariant",
            content="Always assert synthetic truth.",
            relevance_score=0.9,
            confidence=1.0,
            reasons=["manual"],
            source_event_ids=["synth_ev_123"],
        )

        package = ContextPackage(
            context_id="synth_ctx_123",
            query="test",
            profile="default",
            created_at=datetime.now().isoformat(),
            citations=[citation, k_citation],
            inclusion_reasons=["test reason"],
            source_counts={"memory": 1, "knowledge": 1},
        )

        # Step E: Compiler Rendering
        from rationalevault.compilers.registry import get_context_compiler
        compiler = get_context_compiler("claude")
        compiler.compile(package)

    except Exception as e:
        proj_chain_passed = False
        proj_chain_details = f"Active verification failed: {str(e)}"

    if proj_chain_passed:
        checks.append(HealthCheck("Projection Chain", "PASS", proj_chain_details))
    else:
        checks.append(HealthCheck("Projection Chain", "FAIL", proj_chain_details))

    # Overall outcome
    overall_passed = all(c.status != "FAIL" for c in checks)

    return HealthReport(
        rationalevault_version=VERSION,
        overall_passed=overall_passed,
        generated_at=datetime.now().isoformat(),
        checks=checks,
    )
