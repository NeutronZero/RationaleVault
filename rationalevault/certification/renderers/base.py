from abc import ABC, abstractmethod
from ..models import CertificationReport

class ReportRenderer(ABC):
    @abstractmethod
    def render(self, report: CertificationReport) -> str:
        pass
