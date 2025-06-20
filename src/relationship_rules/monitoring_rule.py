from typing import Any, Dict

from .relationship_rule import RelationshipRule


class MonitoringRule(RelationshipRule):
    """
    Emits monitoring-related relationships:
    - (Resource) -[:LOGS_TO]-> (LogAnalyticsWorkspace)
    """

    def applies(self, resource: Dict[str, Any]) -> bool:
        diag_settings = resource.get("diagnosticSettings")
        return isinstance(diag_settings, list) and len(diag_settings) > 0

    def emit(self, resource: Dict[str, Any], db_ops: Any) -> None:
        rid = resource.get("id")
        diag_settings = resource.get("diagnosticSettings", [])
        for ds in diag_settings:
            ws = ds.get("workspaceId")
            if ws and rid:
                db_ops.create_generic_rel(
                    str(rid), "LOGS_TO", str(ws), "Resource", "id"
                )
