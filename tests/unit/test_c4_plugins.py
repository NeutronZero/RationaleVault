"""
RationaleVault Unit Tests — Phase C4 Plugins.
"""
import json
import sys
import pytest
from pathlib import Path
from rationalevault.skill_platform.resolver import ActivationTarget, SkillResolver
from rationalevault.skill_platform.manifest import SkillManifest
from rationalevault.skill_platform.permissions import CapabilityModel
from rationalevault.skill_platform.plugin import (
    PluginScanner,
    PluginValidator,
    PluginLoader,
    PluginRegistry,
    PluginDescriptor,
    PluginCapabilities,
    BasePlugin,
)
from rationalevault.skill_platform.activator import SkillActivator
from rationalevault.skills.base import BaseSkill
from rationalevault.skill_platform.skill_input import SkillInput
from rationalevault.skill_platform.skill_output import SkillOutput
from rationalevault.skill_platform.executor import SkillExecutor
from rationalevault.skill_platform.execution_plan import ExecutionPlan
from rationalevault.skill_platform.context import ExecutionContext
from rationalevault.cognitive_head.decision import DecisionItem
from rationalevault.cognitive_head.synthesis import SynthesisCategory, SynthesisPriority
from rationalevault.skill_platform.bridge import DecisionSkillBridge
from rationalevault.skill_platform.manifest import SkillManifestRegistry


class DummySkill(BaseSkill):
    deterministic = True
    side_effect_free = True
    idempotent = True
    requires_network = False

    def manifest(self) -> SkillManifest:
        return SkillManifest(
            skill_id="SKL-DUMMY",
            name="dummy-skill",
            version="1.0.0",
            description="dummy",
            input_schema={},
            output_schema={},
            required_permissions=["projection:memory"],
            accepted_categories=["AFFIRM"],
            timeout_seconds=5,
            idempotent=True,
        )

    def __call__(self, skill_input: SkillInput) -> SkillOutput:
        return SkillOutput(
            status="completed",
            confirmed_items=[skill_input.belief_title],
            summary="Dummy executed",
            metrics={"dummy_score": 1.0},
        )


class DummyPlugin(BasePlugin):
    sdk_version = "1.0"

    def manifests(self) -> list[SkillManifest]:
        return [
            SkillManifest(
                skill_id="SKL-DUMMY",
                name="dummy-skill",
                version="1.0.0",
                description="dummy",
                input_schema={},
                output_schema={},
                required_permissions=["projection:memory"],
                accepted_categories=["AFFIRM"],
                timeout_seconds=5,
                idempotent=True,
            )
        ]

    def create(self, skill_id: str, context) -> BaseSkill:
        if skill_id == "dummy-skill":
            return DummySkill()
        raise ValueError(f"Unknown skill: {skill_id}")


def test_scanner_and_validation(tmp_path: Path):
    # Setup mock plugin folder structure
    plugin_dir = tmp_path / "mock_plugin"
    plugin_dir.mkdir()
    
    descriptor_data = {
        "plugin_id": "mock-plugin-id",
        "name": "Mock Plugin",
        "version": "1.0.0",
        "author": "Tester",
        "sdk_version": "1.0",
        "entrypoint": {
            "kind": "python",
            "module_path": "mock_plugin_module",
            "class_name": "MockPluginClass"
        },
        "capabilities": {
            "requires_network": False,
            "requires_filesystem": True,
            "requires_subprocess": False,
            "experimental": False
        }
    }
    
    with open(plugin_dir / "plugin.json", "w", encoding="utf-8") as f:
        json.dump(descriptor_data, f)
        
    # Scan
    descriptors = PluginScanner.scan(str(tmp_path))
    assert len(descriptors) == 1
    desc = descriptors[0]
    assert desc.plugin_id == "mock-plugin-id"
    assert desc.name == "Mock Plugin"
    assert desc.capabilities.requires_filesystem is True
    
    # Validate successful
    valid, errors = PluginValidator.validate(desc, [])
    assert valid is True
    assert len(errors) == 0

    # Validate duplicate ID check
    valid_dup, errors_dup = PluginValidator.validate(desc, [desc])
    assert valid_dup is False
    assert any("Duplicate plugin ID" in e for e in errors_dup)

    # Validate invalid semver version
    invalid_desc = PluginDescriptor(
        plugin_id="bad-semver",
        name="Bad",
        version="1.0",
        author="Tester",
        sdk_version="1.0",
        entrypoint=desc.entrypoint,
        capabilities=desc.capabilities,
    )
    valid_ver, errors_ver = PluginValidator.validate(invalid_desc, [])
    assert valid_ver is False
    assert any("Invalid semver" in e for e in errors_ver)


def test_plugin_loading_and_activation(tmp_path: Path):
    # Write plugin module python file
    plugin_dir = tmp_path / "test_plugin"
    plugin_dir.mkdir()
    
    # Write Python file
    plugin_code = """
from rationalevault.skill_platform.plugin import BasePlugin
from rationalevault.skill_platform.manifest import SkillManifest
from rationalevault.skills.base import BaseSkill
from rationalevault.skill_platform.skill_input import SkillInput
from rationalevault.skill_platform.skill_output import SkillOutput

class TestSkill(BaseSkill):
    def manifest(self) -> SkillManifest:
        return SkillManifest(
            skill_id="SKL-TEST",
            name="test-skill",
            version="1.0.0",
            description="test",
            input_schema={},
            output_schema={},
            required_permissions=["projection:memory"],
            accepted_categories=["AFFIRM"],
            timeout_seconds=5,
            idempotent=True,
        )
    def __call__(self, skill_input: SkillInput) -> SkillOutput:
        return SkillOutput(
            status="completed",
            confirmed_items=[skill_input.belief_title],
            summary="test skill run summary",
            metrics={"test_metric": 42}
        )

class TestPluginClass(BasePlugin):
    sdk_version = "1.0"
    def manifests(self) -> list[SkillManifest]:
        return [
            SkillManifest(
                skill_id="SKL-TEST",
                name="test-skill",
                version="1.0.0",
                description="test",
                input_schema={},
                output_schema={},
                required_permissions=["projection:memory"],
                accepted_categories=["AFFIRM"],
                timeout_seconds=5,
                idempotent=True,
            )
        ]
    def create(self, skill_id: str, context) -> BaseSkill:
        if skill_id == "test-skill":
            return TestSkill()
        raise ValueError("Unknown skill")
"""
    with open(plugin_dir / "test_plugin_module.py", "w", encoding="utf-8") as f:
        f.write(plugin_code)
        
    descriptor_data = {
        "plugin_id": "test-plugin-id",
        "name": "Test Plugin",
        "version": "1.0.0",
        "author": "Tester",
        "sdk_version": "1.0",
        "entrypoint": {
            "kind": "python",
            "module_path": "test_plugin_module",
            "class_name": "TestPluginClass"
        },
        "capabilities": {
            "requires_network": False,
            "requires_filesystem": False,
            "requires_subprocess": False,
            "experimental": False
        }
    }
    
    with open(plugin_dir / "plugin.json", "w", encoding="utf-8") as f:
        json.dump(descriptor_data, f)
        
    # Load and register plugin
    PluginRegistry.clear()
    desc = PluginScanner.scan(str(tmp_path))[0]
    plugin_instance = PluginLoader.load(desc, str(plugin_dir))
    assert isinstance(plugin_instance, BasePlugin)
    
    PluginRegistry.register(desc, plugin_instance)
    assert PluginRegistry.get_instance("test-plugin-id") == plugin_instance
    
    # Resolve
    manifests = plugin_instance.manifests()
    assert len(manifests) == 1
    manifest = manifests[0]
    
    # Register dynamic skill in resolver
    target = ActivationTarget(
        kind="python",
        module_path="",
        class_name="",
        metadata={"plugin_id": "test-plugin-id", "skill_id": "test-skill"}
    )
    SkillResolver.register_external("test-skill", target)
    
    descriptor = SkillResolver.resolve(manifest)
    assert descriptor.activation_target.metadata.get("plugin_id") == "test-plugin-id"
    
    # Lazy activate
    callable_fn = SkillActivator.activate(descriptor)
    assert callable(callable_fn)
    
    # Invoke callable_fn directly with dict inputs
    inputs = {
        "belief_title": "Plugin Belief",
        "belief_content": "Plugin Content",
        "confidence": 0.95,
        "category": "AFFIRM",
        "projections": {}
    }
    outputs = callable_fn(inputs)
    assert outputs["status"] == "completed"
    assert outputs["summary"] == "test skill run summary"
    assert outputs["metrics"]["test_metric"] == 42
    
    # Cleanup sys.path modification
    if str(plugin_dir.resolve()) in sys.path:
        sys.path.remove(str(plugin_dir.resolve()))


def test_executor_with_plugin_skill():
    # Setup registry with our preloaded DummyPlugin
    PluginRegistry.clear()
    plugin_desc = PluginDescriptor(
        plugin_id="dummy-plugin-id",
        name="Dummy Plugin",
        version="1.0.0",
        author="Tester",
        sdk_version="1.0",
        entrypoint=ActivationTarget("python", "", ""),
        capabilities=PluginCapabilities(),
    )
    plugin_instance = DummyPlugin()
    PluginRegistry.register(plugin_desc, plugin_instance)

    # Register in resolver
    target = ActivationTarget(
        kind="python",
        module_path="",
        class_name="",
        metadata={"plugin_id": "dummy-plugin-id", "skill_id": "dummy-skill"}
    )
    SkillResolver.register_external("dummy-skill", target)

    # Make execution plan
    manifest = plugin_instance.manifests()[0]
    decision = DecisionItem(
        decision_id="DEC-P1",
        synthesis_id="SYN-P1",
        belief_id="BEL-P1",
        category=SynthesisCategory.AFFIRM,
        priority=SynthesisPriority.NORMAL,
        confidence=0.9,
        impact=0.5,
        contradiction_ids=[],
        belief_title="Plugin Title",
        belief_content="Plugin Content",
        gate_policy_version="1.0",
    )
    
    # Mock registry for DecisionSkillBridge
    mock_reg = type("R", (), {"find_by_category": lambda self, c: [manifest]})()
    candidate = DecisionSkillBridge.map_decision(decision, mock_reg)
    capabilities = CapabilityModel(["projection:memory", "ledger:read"])
    
    from rationalevault.skill_platform.provenance import Provenance
    provenance = Provenance(
        execution_id="",
        decision_id="DEC-P1",
        synthesis_id="SYN-P1",
        belief_id="BEL-P1",
        source_event_ids=[],
        skill_version="1.0.0",
        gate_policy_version="1.0",
        input_snapshot_hash="",
        timestamp="",
    )
    
    context = ExecutionContext(
        decision_id="DEC-P1",
        synthesis_id="SYN-P1",
        belief_id="BEL-P1",
        source_event_ids=[],
        manifest=manifest,
        candidate=candidate,
        input_snapshot={"query": "test"},
        provenance=provenance,
        capabilities=capabilities,
        gate_policy_version="1.0",
    )
    
    plan = ExecutionPlan(
        candidate=candidate,
        context=context,
        timeout_seconds=5,
    )
    
    # Execute through SkillExecutor
    result, event, steps = SkillExecutor.execute(plan)
    
    assert result.status.value == "COMPLETED"
    assert result.error is None
    assert result.outputs["summary"] == "Dummy executed"
    assert "dummy_score" in result.metrics
    assert any(s.step == "activate" and s.status == "ok" for s in steps)
