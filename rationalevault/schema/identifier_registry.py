"""
RationaleVault Identifier Registry — Canonical prefix definitions and generation rules.

Every identifier family in RationaleVault is registered here. This registry is the
authoritative source for:
  - Allowed prefixes
  - Hash input templates
  - Collision guarantees
  - Reserved ranges

Design rules:
  - Never remove or rename existing prefixes (breaks historical references).
  - New prefixes must be added here BEFORE use in code.
  - All IDs are SHA-256 derived, truncated to 8 hex characters (uppercased).
  - Format: PREFIX-{8-char-hex}
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class IdentifierPrefix(str, Enum):
    """All registered identifier prefixes in RationaleVault."""

    # ── Cognitive Head (Epic B) ──────────────────────────────────────
    BEL = "BEL"          # Beliefs
    SYN = "SYN"          # Synthesis items
    DEC = "DEC"          # Decisions

    # ── Skill Platform (Epic C) ──────────────────────────────────────
    SKE = "SKE"          # Skill executions
    SRT = "SRT"          # Skill results
    ART = "ART"          # Artifacts (promoted)
    ACAND = "ACAND"      # Artifact candidates (ephemeral)
    SKL = "SKL"          # Skill manifests

    # ── Execution Intelligence (Epic C5) ─────────────────────────────
    LEARN = "LEARN"      # Learning records

    # ── Reflection (Program F, Phase 1) ──────────────────────────────
    RCAND = "RCAND"      # Reflection candidates (ephemeral)
    REFL = "REFL"        # Reflections
    RREP = "RREP"        # Reflection reports
    RTRC = "RTRC"        # Reflection traces

    # ── Knowledge Promotion (Program F, Phase 2) ─────────────────────
    PROMO = "PROMO"      # Promotion candidates
    PASSMT = "PASSMT"    # Promotion assessments
    PGATE = "PGATE"      # Promotion gate results
    PD = "PD"            # Promotion decisions
    PREP = "PREP"        # Promotion reports
    KCAN = "KCAN"        # Knowledge candidates (ephemeral)
    KNOW = "KNOW"        # Knowledge objects (promoted)

    # ── Knowledge Validation (Program F, Phase 3) ────────────────────
    KVAL = "KVAL"        # Knowledge validation reports

    # ── AI Advisory (Program F, Phase 4) ─────────────────────────────
    ADVC = "ADVC"        # Advisory reports (not ledger events)

    # ── Planner Evolution (Program F, Phase 5) ───────────────────────
    PADJ = "PADJ"        # Planner adjustments
    PPOL = "PPOL"        # Planner policy versions (append-only)

    # ── Memory Lifecycle (Program F, Phase 6) ────────────────────────
    MTRANS = "MTRANS"    # Memory transitions

    # ── Scheduled Cognition (Program F, Phase 7) ─────────────────────
    CJOB = "CJOB"        # Cognitive jobs
    CEXEC = "CEXEC"      # Cognitive execution history

    # ── Workspace (Epic G) ───────────────────────────────────────────
    WS = "WS"            # Workspaces
    WSSNP = "WSSNP"      # Workspace snapshots
    WSSSN = "WSSSN"      # Workspace sessions
    WSCTX = "WSCTX"      # Workspace contexts
    WSPKG = "WSPKG"      # Workspace packages

    # ── Agent Runtime (Epic H) ───────────────────────────────────────
    AGNT = "AGNT"        # Agent profiles
    AGS = "AGS"          # Agent sessions
    AGCAP = "AGCAP"      # Agent capabilities
    RTC = "RTC"          # Runtime contexts
    WSB = "WSB"          # Workspace bindings
    SSSN = "SSSN"        # Session snapshots
    AGPRF = "AGPRF"      # Agent profiles (alternate)

    # ── Transport SDK (Epic H) ──────────────────────────────────────
    TMNF = "TMNF"        # Transport manifests
    TNAG = "TNAG"        # Transport negotiations
    TSSN = "TSSN"        # Transport sessions

    # ── Vendor SDK (Epic H) ─────────────────────────────────────────
    VMNF = "VMNF"        # Vendor manifests

    # ── MCP Server v2 (Epic H) ──────────────────────────────────────
    MCPT = "MCPT"        # MCP tool definitions
    MCPB = "MCPB"        # MCP tool bindings
    MCPM = "MCPM"        # MCP server manifest

    # ── Memory Integration (Epic H) ─────────────────────────────────
    MQRY = "MQRY"        # Memory queries
    MRES = "MRES"        # Memory results
    MCTX = "MCTX"        # Memory contexts
    MWRT = "MWRT"        # Memory write requests
    MWRS = "MWRS"        # Memory write results

    # ── Memory Policy Engine (Epic H) ───────────────────────────────
    MPOL = "MPOL"        # Memory policies (composite)

    # ── Adaptive Policy Engine (Epic H) ─────────────────────────────
    TELE = "TELE"        # Telemetry data points
    ARUL = "ARUL"        # Adjustment rules
    APOL = "APOL"        # Adaptive policies

    # ── Policy Simulator (Epic H) ───────────────────────────────────
    PSIM = "PSIM"        # Simulation reports and results

    # ── Remote Sessions (Epic H) ────────────────────────────────────
    RSES = "RSES"        # Remote sessions and distributed cognition


@dataclass(frozen=True)
class IdentifierSpec:
    """Specification for an identifier prefix."""
    prefix: str
    hash_input_template: str
    description: str
    ephemeral: bool = False  # True = not persisted to ledger


# Registry: prefix -> spec
IDENTIFIER_REGISTRY: dict[str, IdentifierSpec] = {
    # Cognitive Head
    IdentifierPrefix.BEL.value: IdentifierSpec(
        prefix="BEL",
        hash_input_template="belief:{title}:{content}",
        description="Beliefs constructed from evidence assessments",
    ),
    IdentifierPrefix.SYN.value: IdentifierSpec(
        prefix="SYN",
        hash_input_template="synthesis:{candidate_id}:{config_version}",
        description="Synthesis items generated from beliefs",
    ),
    IdentifierPrefix.DEC.value: IdentifierSpec(
        prefix="DEC",
        hash_input_template="decision:{policy_version}:{synthesis_id}",
        description="Decisions produced by the decision gate",
    ),

    # Skill Platform
    IdentifierPrefix.SKE.value: IdentifierSpec(
        prefix="SKE",
        hash_input_template="execution:{skill_id}:{decision_id}:{input_hash}",
        description="Skill execution records",
    ),
    IdentifierPrefix.SRT.value: IdentifierSpec(
        prefix="SRT",
        hash_input_template="result:{execution_id}:{output_hash}",
        description="Skill execution results",
    ),
    IdentifierPrefix.ART.value: IdentifierSpec(
        prefix="ART",
        hash_input_template="artifact:{skill_id}:{execution_id}:{content_hash}",
        description="Promoted artifacts",
    ),
    IdentifierPrefix.ACAND.value: IdentifierSpec(
        prefix="ACAND",
        hash_input_template="artifact_candidate:{skill_id}:{execution_id}:{content_hash}",
        description="Ephemeral artifact candidates",
        ephemeral=True,
    ),
    IdentifierPrefix.SKL.value: IdentifierSpec(
        prefix="SKL",
        hash_input_template="skill:{name}:{version}",
        description="Skill manifest identifiers",
    ),

    # Execution Intelligence
    IdentifierPrefix.LEARN.value: IdentifierSpec(
        prefix="LEARN",
        hash_input_template="learn:{planner_id}:{evaluation_version}:{assessment_hash}",
        description="Execution learning records",
    ),

    # Reflection
    IdentifierPrefix.RCAND.value: IdentifierSpec(
        prefix="RCAND",
        hash_input_template="candidate_reflection:{source_artifact_id}:{reason}:{config_version}",
        description="Reflection candidates (ephemeral)",
        ephemeral=True,
    ),
    IdentifierPrefix.REFL.value: IdentifierSpec(
        prefix="REFL",
        hash_input_template="reflection:{candidate_id}:{created_at}",
        description="Reflections",
    ),
    IdentifierPrefix.RREP.value: IdentifierSpec(
        prefix="RREP",
        hash_input_template="report:{sorted_reflection_ids}:{created_at}",
        description="Reflection reports",
    ),
    IdentifierPrefix.RTRC.value: IdentifierSpec(
        prefix="RTRC",
        hash_input_template="trace:{reflection_id}:{candidate_id}:{created_at}",
        description="Reflection traces",
    ),

    # Knowledge Promotion
    IdentifierPrefix.PROMO.value: IdentifierSpec(
        prefix="PROMO",
        hash_input_template="promotion:{source_reflection_ids}:{knowledge_type}:{created_at}",
        description="Promotion candidates",
    ),
    IdentifierPrefix.PASSMT.value: IdentifierSpec(
        prefix="PASSMT",
        hash_input_template="promotion_assessment:{candidate_id}:{created_at}",
        description="Promotion assessments",
    ),
    IdentifierPrefix.PGATE.value: IdentifierSpec(
        prefix="PGATE",
        hash_input_template="promotion_gate:{assessment_id}:{decision}:{created_at}",
        description="Promotion gate results",
    ),
    IdentifierPrefix.PD.value: IdentifierSpec(
        prefix="PD",
        hash_input_template="promotion_decision:{candidate_id}:{gate_result_id}:{created_at}",
        description="Promotion decisions",
    ),
    IdentifierPrefix.PREP.value: IdentifierSpec(
        prefix="PREP",
        hash_input_template="promotion_report:{sorted_decision_ids}:{created_at}",
        description="Promotion reports",
    ),
    IdentifierPrefix.KCAN.value: IdentifierSpec(
        prefix="KCAN",
        hash_input_template="knowledge_candidate:{source_promotion_decision_id}:{knowledge_type}:{created_at}",
        description="Knowledge candidates (ephemeral)",
        ephemeral=True,
    ),
    IdentifierPrefix.KNOW.value: IdentifierSpec(
        prefix="KNOW",
        hash_input_template="knowledge:{knowledge_type}:{title}:{content_hash}",
        description="Promoted knowledge objects",
    ),

    # Knowledge Validation
    IdentifierPrefix.KVAL.value: IdentifierSpec(
        prefix="KVAL",
        hash_input_template="knowledge_validation:{knowledge_id}:{created_at}",
        description="Knowledge validation reports",
    ),

    # AI Advisory
    IdentifierPrefix.ADVC.value: IdentifierSpec(
        prefix="ADVC",
        hash_input_template="advisory:{advisory_type}:{source_ids}:{created_at}",
        description="Advisory reports (not ledger events, cacheable/disposable)",
    ),

    # Planner Evolution
    IdentifierPrefix.PADJ.value: IdentifierSpec(
        prefix="PADJ",
        hash_input_template="planner_adjustment:{adjustment_type}:{target}:{created_at}",
        description="Planner adjustment records",
    ),
    IdentifierPrefix.PPOL.value: IdentifierSpec(
        prefix="PPOL",
        hash_input_template="planner_policy:{version}:{created_at}",
        description="Planner policy versions (append-only, never overwrite)",
    ),

    # Memory Lifecycle
    IdentifierPrefix.MTRANS.value: IdentifierSpec(
        prefix="MTRANS",
        hash_input_template="memory_transition:{memory_id}:{from_status}:{to_status}:{created_at}",
        description="Memory lifecycle transitions",
    ),

    # Scheduled Cognition
    IdentifierPrefix.CJOB.value: IdentifierSpec(
        prefix="CJOB",
        hash_input_template="cognitive_job:{job_type}:{priority}:{created_at}",
        description="Cognitive job records",
    ),
    IdentifierPrefix.CEXEC.value: IdentifierSpec(
        prefix="CEXEC",
        hash_input_template="cognitive_execution:{job_id}:{status}:{created_at}",
        description="Cognitive execution history records",
    ),

    # Workspace
    IdentifierPrefix.WS.value: IdentifierSpec(
        prefix="WS",
        hash_input_template="workspace:{name}:{created_at}",
        description="Workspace identifiers",
    ),
    IdentifierPrefix.WSSNP.value: IdentifierSpec(
        prefix="WSSNP",
        hash_input_template="workspace_snapshot:{workspace_id}:{created_at}",
        description="Workspace snapshots (point-in-time state)",
    ),
    IdentifierPrefix.WSSSN.value: IdentifierSpec(
        prefix="WSSSN",
        hash_input_template="workspace_session:{workspace_id}:{agent_id}:{created_at}",
        description="Workspace sessions (agent interaction instances)",
    ),
    IdentifierPrefix.WSCTX.value: IdentifierSpec(
        prefix="WSCTX",
        hash_input_template="workspace_context:{session_id}:{created_at}",
        description="Workspace contexts (compiled context packages)",
    ),
    IdentifierPrefix.WSPKG.value: IdentifierSpec(
        prefix="WSPKG",
        hash_input_template="workspace_package:{workspace_id}:{created_at}",
        description="Workspace packages (resumable continuation envelopes)",
    ),
    # ── Agent Runtime (Epic H) ───────────────────────────────────────
    IdentifierPrefix.AGNT.value: IdentifierSpec(
        prefix="AGNT",
        hash_input_template="agent_profile:{name}:{vendor}:{created_at}",
        description="Agent profiles (identity, separate from session)",
    ),
    IdentifierPrefix.AGS.value: IdentifierSpec(
        prefix="AGS",
        hash_input_template="agent_session:{profile_id}:{workspace_id}:{created_at}",
        description="Agent sessions (running instances in workspaces)",
    ),
    IdentifierPrefix.AGCAP.value: IdentifierSpec(
        prefix="AGCAP",
        hash_input_template="agent_capabilities:{profile_id}:{resolved_at}",
        description="Agent capability sets (composable permission flags)",
    ),
    IdentifierPrefix.RTC.value: IdentifierSpec(
        prefix="RTC",
        hash_input_template="runtime_context:{session_id}:{created_at}",
        description="Runtime contexts (compiled agent context)",
    ),
    IdentifierPrefix.WSB.value: IdentifierSpec(
        prefix="WSB",
        hash_input_template="workspace_binding:{session_id}:{workspace_id}",
        description="Workspace bindings (session-workspace attachment)",
    ),
    IdentifierPrefix.SSSN.value: IdentifierSpec(
        prefix="SSSN",
        hash_input_template="session_snapshot:{session_id}:{created_at}",
        description="Session snapshots (point-in-time session state)",
    ),
    IdentifierPrefix.AGPRF.value: IdentifierSpec(
        prefix="AGPRF",
        hash_input_template="agent_profile_alt:{name}:{vendor}:{created_at}",
        description="Agent profiles (alternate prefix)",
    ),
    # ── Transport SDK (Epic H) ──────────────────────────────────────
    IdentifierPrefix.TMNF.value: IdentifierSpec(
        prefix="TMNF",
        hash_input_template="transport_manifest:{name}:{transport_type}:{version}",
        description="Transport manifests (transport identity)",
    ),
    IdentifierPrefix.TNAG.value: IdentifierSpec(
        prefix="TNAG",
        hash_input_template="transport_negotiation:{manifest_id}:{runtime_version}:{negotiated_at}",
        description="Transport negotiations (version/capability handshake)",
    ),
    IdentifierPrefix.TSSN.value: IdentifierSpec(
        prefix="TSSN",
        hash_input_template="transport_session:{manifest_id}:{agent_session_id}:{created_at}",
        description="Transport sessions (active connections)",
    ),
    # ── Vendor SDK (Epic H) ─────────────────────────────────────────
    IdentifierPrefix.VMNF.value: IdentifierSpec(
        prefix="VMNF",
        hash_input_template="vendor_manifest:{name}:{vendor_id}:{version}",
        description="Vendor manifests (vendor identity)",
    ),
    # ── MCP Server v2 (Epic H) ──────────────────────────────────────
    IdentifierPrefix.MCPT.value: IdentifierSpec(
        prefix="MCPT",
        hash_input_template="mcp_tool:{name}:{category}",
        description="MCP tool definitions",
    ),
    IdentifierPrefix.MCPB.value: IdentifierSpec(
        prefix="MCPB",
        hash_input_template="mcp_binding:{tool_id}:{workspace_id}",
        description="MCP tool bindings",
    ),
    IdentifierPrefix.MCPM.value: IdentifierSpec(
        prefix="MCPM",
        hash_input_template="mcp_manifest:{server_name}:{version}",
        description="MCP server manifest",
    ),
    # ── Memory Integration (Epic H) ─────────────────────────────────
    IdentifierPrefix.MQRY.value: IdentifierSpec(
        prefix="MQRY",
        hash_input_template="memory_query:{query_type}:{text}:{project_id}",
        description="Memory queries",
    ),
    IdentifierPrefix.MRES.value: IdentifierSpec(
        prefix="MRES",
        hash_input_template="memory_result:{memory_id}:{query_id}",
        description="Memory results",
    ),
    IdentifierPrefix.MCTX.value: IdentifierSpec(
        prefix="MCTX",
        hash_input_template="memory_context:{query_id}",
        description="Memory contexts",
    ),
    IdentifierPrefix.MWRT.value: IdentifierSpec(
        prefix="MWRT",
        hash_input_template="memory_write:{title}:{content}:{project_id}",
        description="Memory write requests",
    ),
    IdentifierPrefix.MWRS.value: IdentifierSpec(
        prefix="MWRS",
        hash_input_template="memory_write_result:{memory_id}:{request_id}",
        description="Memory write results",
    ),
    # ── Memory Policy Engine (Epic H) ───────────────────────────────
    IdentifierPrefix.MPOL.value: IdentifierSpec(
        prefix="MPOL",
        hash_input_template="memory_policy:{name}",
        description="Memory policies (composite)",
    ),
    # ── Adaptive Policy Engine (Epic H) ─────────────────────────────
    IdentifierPrefix.TELE.value: IdentifierSpec(
        prefix="TELE",
        hash_input_template="telemetry:{metric_type}:{value}:{timestamp}",
        description="Telemetry data points",
    ),
    IdentifierPrefix.ARUL.value: IdentifierSpec(
        prefix="ARUL",
        hash_input_template="adjustment_rule:{metric_type}:{dimension}",
        description="Adjustment rules",
    ),
    IdentifierPrefix.APOL.value: IdentifierSpec(
        prefix="APOL",
        hash_input_template="adaptive_policy:{name}",
        description="Adaptive policies",
    ),
    # ── Policy Simulator (Epic H) ───────────────────────────────────
    IdentifierPrefix.PSIM.value: IdentifierSpec(
        prefix="PSIM",
        hash_input_template="simulation_report:{scenario_id}",
        description="Simulation reports and results",
    ),
    # ── Remote Sessions (Epic H) ────────────────────────────────────
    IdentifierPrefix.RSES.value: IdentifierSpec(
        prefix="RSES",
        hash_input_template="remote_session:{node_id}:{session_id}",
        description="Remote sessions and distributed cognition",
    ),
}


def get_spec(prefix: str) -> IdentifierSpec:
    """Get the specification for a given prefix."""
    if prefix not in IDENTIFIER_REGISTRY:
        raise ValueError(f"Unknown identifier prefix: {prefix}. Must be registered in IDENTIFIER_REGISTRY.")
    return IDENTIFIER_REGISTRY[prefix]


def list_prefixes() -> list[str]:
    """Return all registered prefixes."""
    return list(IDENTIFIER_REGISTRY.keys())
