from ...models import ArtifactType
from ..base import CertificationRule, RulePack
from ..checks.ast_checks import CheckNoInternalImports, CheckReducerPurity
from ..checks.doc_checks import CheckReadmeExists, CheckPublicDocstrings

ProjectionPack = RulePack(
    id="projection-pack",
    artifact_types=[ArtifactType.PROJECTION],
    rules=[
        CertificationRule(
            id="R_PROJ_01",
            name="Projection Purity",
            category="Architecture",
            checks=[CheckReducerPurity()]
        )
    ]
)

DocumentationPack = RulePack(
    id="documentation-pack",
    artifact_types=[
        ArtifactType.PROJECTION, 
        ArtifactType.SKILL, 
        ArtifactType.RUNTIME,
        ArtifactType.STORAGE_BACKEND,
        ArtifactType.TRANSPORT,
        ArtifactType.EMBEDDING_PROVIDER,
        ArtifactType.CLI_EXTENSION,
        ArtifactType.MCP_EXTENSION
    ],
    rules=[
        CertificationRule(
            id="R_DOC_01",
            name="Documentation Completeness",
            category="Documentation",
            checks=[CheckReadmeExists(), CheckPublicDocstrings()]
        )
    ]
)

ArchitecturePack = RulePack(
    id="architecture-pack",
    artifact_types=[
        ArtifactType.PROJECTION, 
        ArtifactType.SKILL, 
        ArtifactType.RUNTIME,
        ArtifactType.STORAGE_BACKEND,
        ArtifactType.TRANSPORT,
        ArtifactType.EMBEDDING_PROVIDER,
        ArtifactType.CLI_EXTENSION,
        ArtifactType.MCP_EXTENSION
    ],
    rules=[
        CertificationRule(
            id="R_ARCH_01",
            name="API Boundaries",
            category="Architecture",
            checks=[CheckNoInternalImports()]
        )
    ]
)

# Register them automatically
def register_core_packs():
    from ..registry import rule_pack_registry
    rule_pack_registry.register(ProjectionPack)
    rule_pack_registry.register(DocumentationPack)
    rule_pack_registry.register(ArchitecturePack)
