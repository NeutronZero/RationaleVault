import json
from dataclasses import asdict
from datetime import datetime

from ..models import CertificationReport
from .base import ReportRenderer

class JsonRenderer(ReportRenderer):
    def render(self, report: CertificationReport) -> str:
        # Helper to serialize enums and datetime
        def default_serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            if hasattr(obj, "name"):
                return obj.name
            return str(obj)
            
        report_dict = asdict(report)
        return json.dumps(report_dict, default=default_serializer, indent=2)
