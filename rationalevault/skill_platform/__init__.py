"""
RationaleVault Skill Platform — Epic C.

The execution layer that consumes DecisionSet from the cognitive pipeline
and produces deterministic, replayable execution results.

Key invariants:
  - The runtime never knows how events are persisted.
  - Every execution produces a SkillResult, even on failure.
  - Skills never write to the Event Ledger directly.
  - The feedback loop operates through the Event Ledger, never direct calls.
"""
from rationalevault.skill_platform.manifest import SkillManifest, SkillManifestRegistry
from rationalevault.skill_platform.permissions import (
    CAPABILITY_KEYS,
    CapabilityModel,
    PermissionChecker,
    PermissionDecision,
)
from rationalevault.skill_platform.context import ExecutionContext
from rationalevault.skill_platform.provenance import Provenance, compute_snapshot_hash
from rationalevault.skill_platform.result import SkillResult, SkillResultStatus
from rationalevault.skill_platform.bridge import DecisionSkillBridge, SkillCandidate
from rationalevault.skill_platform.runtime import (
    SkillRuntime,
    SkillExecutionRecord,
    SkillState,
    SandboxViolation,
)
from rationalevault.skill_platform.execution_state import (
    ExecutionState,
    ExecutionEntry,
    ExecutionStateProjection,
)
from rationalevault.skill_platform.skill_input import SkillInput, ProjectionSnapshot
from rationalevault.skill_platform.skill_output import SkillOutput
from rationalevault.skill_platform.validator import OutputValidator, ValidationResult
from rationalevault.skill_platform.input_builder import SkillInputBuilder
from rationalevault.skill_platform.sandbox import SkillSandbox, SandboxConfig
from rationalevault.skill_platform.resolver import SkillResolver, SkillDescriptor, ActivationTarget
from rationalevault.skill_platform.activator import SkillActivator, SkillActivationError
from rationalevault.skill_platform.skill_event import SkillExecutionEvent
from rationalevault.skill_platform.event_emitter import SkillEventEmitter, ExecutionSummary
from rationalevault.skill_platform.execution_plan import ExecutionPlan
from rationalevault.skill_platform.execution_report import ExecutionReport
from rationalevault.skill_platform.executor import SkillExecutor, ExecutionStep

__all__ = [
    # C1 (stable)
    "ExecutionContext",
    "SkillManifest",
    "SkillManifestRegistry",
    "CAPABILITY_KEYS",
    "CapabilityModel",
    "PermissionChecker",
    "PermissionDecision",
    "Provenance",
    "compute_snapshot_hash",
    "SkillResult",
    "SkillResultStatus",
    "DecisionSkillBridge",
    "SkillCandidate",
    "SkillRuntime",
    "SkillExecutionRecord",
    "SkillState",
    "SandboxViolation",
    "ExecutionState",
    "ExecutionEntry",
    "ExecutionStateProjection",
    # C2 (new)
    "SkillInput",
    "ProjectionSnapshot",
    "SkillOutput",
    "OutputValidator",
    "ValidationResult",
    "SkillInputBuilder",
    "SkillSandbox",
    "SandboxConfig",
    "SkillResolver",
    "SkillDescriptor",
    "ActivationTarget",
    "SkillActivator",
    "SkillActivationError",
    "SkillExecutionEvent",
    "SkillEventEmitter",
    "ExecutionSummary",
    "ExecutionPlan",
    "ExecutionReport",
    "SkillExecutor",
    "ExecutionStep",
]
