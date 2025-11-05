from typing import Any, Dict

from .relationship_rule import RelationshipRule


class MonitoringRule(RelationshipRule):
    """
    Emits monitoring-related relationships:
    - (Resource) -[:LOGS_TO]-> (LogAnalyticsWorkspace)

    Supports dual-graph architecture - creates relationships in both original and abstracted graphs.
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
                # Use dual-graph helper for Resource-to-Resource relationships
                self.create_dual_graph_relationship(
                    db_ops, str(rid), "LOGS_TO", str(ws)
                )
