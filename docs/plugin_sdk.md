# RationaleVault Plugin SDK

The RationaleVault Plugin SDK provides a versioned, secure, and extensible interface for third-party developers to package and register custom skills. It is the platform's first public extension API.

## Core Architectural Invariants

### 1. Separation of Concerns
Dynamic skill execution is split into clear, decoupled phases:
* **Scanning**: `PluginScanner` reads plugin descriptors (`plugin.json`) to extract metadata *without* importing third-party code.
* **Validation**: `PluginValidator` validates SDK version support, parses semver format, checks capability requests, and prevents duplicate plugin IDs.
* **Loading**: `PluginLoader` imports the code of validated plugins and instantiates `BasePlugin` subclasses.
* **Registration**: `PluginRegistry` records descriptors and loaded plugin instances.
* **Resolution**: `SkillResolver` maps a `SkillManifest` to a target `SkillDescriptor`.
* **Activation**: `SkillActivator` uses the `PluginRegistry` to lazy-instantiate the plugin and the requested `BaseSkill` only upon execution.
* **Execution**: `SkillRuntime` runs the skill within a sandbox.

### 2. Strict Trust Boundary
To ensure the platform's safety, plugins operate as **output producers only**.
* **Allowed**: Plugins return `SkillOutput` and declare list of `ArtifactCandidate` entries.
* **Forbidden**: Plugins cannot access internal runtime components (`SkillRuntime`, `ExecutionContext`, `SkillExecutor`). Plugins cannot write to the Event Ledger, promote artifacts, or generate platform-level reports (`SkillResult`, `ExecutionReport`, `ExecutionEvaluation`, `GateResult`, `ArtifactPromotionReport`, `Artifact`, `ArtifactLineage`, `SKILL_EXECUTED`).

---

## Writing a Plugin

A plugin consists of:
1. A declarative descriptor file named `plugin.json`.
2. A Python module defining a class that inherits from `BasePlugin`.
3. One or more skill classes inheriting from `BaseSkill`.

### 1. Declarative Descriptor: `plugin.json`
Every plugin directory must contain a `plugin.json` file in its root. This metadata is inspected by the scanner.

```json
{
  "plugin_id": "rv-sentiment-plugin",
  "name": "Sentiment Analyzer Plugin",
  "version": "1.0.0",
  "author": "Third Party Dev",
  "sdk_version": "1.0",
  "entrypoint": {
    "kind": "python",
    "module_path": "rv_sentiment.plugin",
    "class_name": "SentimentPlugin",
    "metadata": {}
  },
  "capabilities": {
    "requires_network": false,
    "requires_filesystem": false,
    "requires_subprocess": false,
    "experimental": false
  }
}
```

### 2. The Plugin Class: `BasePlugin`
Define a plugin class inheriting from `BasePlugin` in the module pointed to by `entrypoint.module_path`.

```python
from rationalevault.skill_platform.plugin import BasePlugin, PluginContext
from rationalevault.skill_platform.manifest import SkillManifest
from rationalevault.skills.base import BaseSkill
from .skills import SentimentAnalysisSkill

class SentimentPlugin(BasePlugin):
    sdk_version = "1.0"

    def manifests(self) -> list[SkillManifest]:
        # Return manifests for all skills provided by the plugin.
        # DO NOT instantiate skill classes here.
        return [
            SkillManifest(
                skill_id=SkillManifest.generate_skill_id("sentiment-skill", "1.0.0"),
                name="sentiment-skill",
                version="1.0.0",
                description="Analyzes the sentiment of a belief.",
                input_schema={
                    "type": "object",
                    "required": ["belief_title", "belief_content"],
                    "properties": {
                        "belief_title": {"type": "string"},
                        "belief_content": {"type": "string"}
                    }
                },
                output_schema={
                    "type": "object",
                    "required": ["status", "summary", "sentiment_score"],
                    "properties": {
                        "status": {"type": "string"},
                        "summary": {"type": "string"},
                        "sentiment_score": {"type": "number"}
                    }
                },
                required_permissions=["projection:memory"],
                accepted_categories=["AFFIRM"],
                timeout_seconds=10,
                idempotent=True
            )
        ]

    def create(self, skill_id: str, context: PluginContext) -> BaseSkill:
        # Lazy-instantiation called only when execution is requested.
        if skill_id == "sentiment-skill":
            return SentimentAnalysisSkill()
        raise ValueError(f"Unknown skill ID: {skill_id}")
```

### 3. The Skill Class: `BaseSkill`
Define the skill class inheriting from `BaseSkill`.

```python
from typing import ClassVar
from rationalevault.skills.base import BaseSkill
from rationalevault.skill_platform.manifest import SkillManifest
from rationalevault.skill_platform.skill_input import SkillInput
from rationalevault.skill_platform.skill_output import SkillOutput

class SentimentAnalysisSkill(BaseSkill):
    deterministic: ClassVar[bool] = True
    side_effect_free: ClassVar[bool] = True
    idempotent: ClassVar[bool] = True
    requires_network: ClassVar[bool] = False

    def manifest(self) -> SkillManifest:
        # Return the same manifest defined in the plugin's metadata.
        ...

    def __call__(self, skill_input: SkillInput) -> SkillOutput:
        # Execute the skill logic.
        content = skill_input.belief_content.lower()
        score = 0.5
        if "excellent" in content or "strong" in content:
            score = 0.9
        elif "weak" in content or "fail" in content:
            score = 0.1

        return SkillOutput(
            status="completed",
            confirmed_items=[skill_input.belief_title],
            recommendations=["Promote this belief based on sentiment scoring"],
            summary=f"Sentiment score: {score:.2f}",
            metrics={"sentiment_score": score}
        )
```
