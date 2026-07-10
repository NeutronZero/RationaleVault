import tomllib
from pathlib import Path

from ..context import CertificationContext
from ..engine import CertificationStage
from ..models import ArtifactType, ExtensionManifest, Finding, Severity

class DiscoveryStage(CertificationStage):
    @property
    def id(self) -> str:
        return "discovery"
        
    def execute(self, context: CertificationContext) -> CertificationContext:
        pyproject_path = context.target_path / "pyproject.toml"
        if not pyproject_path.exists():
            context.findings.append(Finding(
                id="RV001",
                severity=Severity.ERROR,
                message="Missing pyproject.toml",
                remediation="Ensure the extension is a valid Python package with a pyproject.toml file.",
            ))
            return context
            
        with open(pyproject_path, "rb") as f:
            try:
                data = tomllib.load(f)
            except Exception as e:
                context.findings.append(Finding(
                    id="RV002",
                    severity=Severity.ERROR,
                    message=f"Invalid pyproject.toml: {e}",
                    remediation="Fix TOML syntax errors.",
                ))
                return context

        project = data.get("project", {})
        
        # Build manifest
        context.manifest = ExtensionManifest(
            name=project.get("name", "unknown"),
            version=project.get("version", "0.0.0"),
            description=project.get("description", ""),
            author="unknown", # Parse authors if needed
            license="unknown",
            api_version="1.0",
            supported_rationalevault=project.get("dependencies", ["rationalevault"])[0].replace("rationalevault", "").strip(),
            entry_points=project.get("entry-points", {}).get("rationalevault.plugins", {})
        )
        
        # Determine ArtifactType
        # In a real impl, we'd inspect the entry points or plugin registration.
        # Defaulting to PROJECTION for now, or inferring from name/entry_points
        eps = context.manifest.entry_points
        if any("projection" in k.lower() or "projection" in v.lower() for k, v in eps.items()):
            context.artifact_type = ArtifactType.PROJECTION
        elif any("skill" in k.lower() for k, v in eps.items()):
            context.artifact_type = ArtifactType.SKILL
        else:
            context.artifact_type = ArtifactType.PROJECTION # Fallback
            
        return context
