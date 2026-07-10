from packaging.specifiers import SpecifierSet
from packaging.version import Version, InvalidVersion
from rationalevault import __version__ as framework_version

class CompatibilityAnalyzer:
    @staticmethod
    def is_compatible(supported_version_specifier: str) -> bool:
        """
        Evaluates if the current framework version satisfies the supported version specifier.
        """
        try:
            spec = SpecifierSet(supported_version_specifier)
            current = Version(framework_version)
            return current in spec
        except Exception:
            return False
