from typing import Any, Dict, List, Set

from .relationship_rule import RelationshipRule


class DiagnosticRule(RelationshipRule):
    """
    Emits diagnostics-related relationships:
    - (Resource)-[:SENDS_DIAG_TO]->(DiagnosticSetting)
    - (Resource)-[:ALERTED_BY]->(AlertRule) [future]
    - (DiagnosticSetting)-[:LOGS_TO]->(LogAnalyticsWorkspace) [if workspaceId present]

    Supports dual-graph architecture - creates relationships in both original and abstracted graphs.
    Note: DiagnosticSetting and LogAnalyticsWorkspace nodes are shared between graphs.
    """

    def applies(self, resource: Dict[str, Any]) -> bool:
        # Applies if resource has diagnosticSettings ARM children or property
        if "diagnosticSettings" in resource and isinstance(
            resource["diagnosticSettings"], list
        ):
            return True
        # Also check for ARM children of type Microsoft.Insights/diagnosticSettings
        children = resource.get("resources") or resource.get("children")
        if isinstance(children, list):
            for child in children:
                if (
                    child.get("type", "").lower()
                    == "microsoft.insights/diagnosticsettings"
                ):
                    return True
        return False

    def emit(self, resource: Dict[str, Any], db_ops: Any) -> None:
        resource_id = resource.get("id")
        if not resource_id:
            return
        # 1. Handle diagnosticSettings property (list of dicts)
        diag_settings: List[Dict[str, Any]] = resource.get("diagnosticSettings", [])
        for ds in diag_settings:
            ds_id = (
                ds.get("id")
                or f"{resource_id}/diagnosticSettings/{ds.get('name', 'unknown')}"
            )
            ds_props = {
                "id": ds_id,
                "name": ds.get("name", ""),
                "type": "Microsoft.Insights/diagnosticSettings",
                "properties": ds.get("properties", {}),
            }
            # Upsert DiagnosticSetting node (shared between graphs)
            db_ops.upsert_generic("DiagnosticSetting", "id", ds_id, ds_props)
            # Create Resource -> DiagnosticSetting relationship using dual-graph helper
            self.create_dual_graph_generic_rel(
                db_ops, resource_id, "SENDS_DIAG_TO", ds_id, "DiagnosticSetting", "id"
            )
            # If workspaceId present, create LOGS_TO to LogAnalyticsWorkspace
            ws_id = ds.get("properties", {}).get("workspaceId")
            if ws_id:
                # Upsert LogAnalyticsWorkspace node (shared between graphs)
                db_ops.upsert_generic(
                    "LogAnalyticsWorkspace", "id", ws_id, {"id": ws_id}
                )
                # DiagnosticSetting -> LogAnalyticsWorkspace
                # Note: Since DiagnosticSetting is not a Resource, we can use db_ops directly
                db_ops.create_generic_rel(
                    ds_id, "LOGS_TO", ws_id, "LogAnalyticsWorkspace", "id"
                )
        # 2. Handle ARM children of type Microsoft.Insights/diagnosticSettings
        children = resource.get("resources") or resource.get("children")
        if isinstance(children, list):
            for child in children:
                if (
                    child.get("type", "").lower()
                    == "microsoft.insights/diagnosticsettings"
                ):
                    ds_id = child.get("id")
                    ds_props = {
                        "id": ds_id,
                        "name": child.get("name", ""),
                        "type": "Microsoft.Insights/diagnosticSettings",
                        "properties": child.get("properties", {}),
                    }
                    # Upsert DiagnosticSetting node (shared between graphs)
                    db_ops.upsert_generic("DiagnosticSetting", "id", ds_id, ds_props)
                    # Create Resource -> DiagnosticSetting relationship using dual-graph helper
                    self.create_dual_graph_generic_rel(
                        db_ops,
                        resource_id,
                        "SENDS_DIAG_TO",
                        ds_id,
                        "DiagnosticSetting",
                        "id",
                    )
                    ws_id = child.get("properties", {}).get("workspaceId")
                    if ws_id:
                        # Upsert LogAnalyticsWorkspace node (shared between graphs)
                        db_ops.upsert_generic(
                            "LogAnalyticsWorkspace", "id", ws_id, {"id": ws_id}
                        )
                        # DiagnosticSetting -> LogAnalyticsWorkspace
                        db_ops.create_generic_rel(
                            ds_id, "LOGS_TO", ws_id, "LogAnalyticsWorkspace", "id"
                        )
        # 3. (Future) AlertRule support can be added similarly

    def extract_target_ids(self, resource: Dict[str, Any]) -> Set[str]:
        """
        Extract Log Analytics Workspace resource IDs from diagnostic settings.

        Returns workspace IDs that diagnostics log to.
        Does NOT return DiagnosticSetting IDs (those are generic nodes, not resources).
        """
        target_ids: Set[str] = set()

        # Extract workspace IDs from diagnosticSettings property
        diag_settings: List[Dict[str, Any]] = resource.get("diagnosticSettings", [])
        for ds in diag_settings:
            ws_id = ds.get("properties", {}).get("workspaceId")
            if ws_id:
                target_ids.add(str(ws_id))

        # Extract workspace IDs from ARM children
        children = resource.get("resources") or resource.get("children")
        if isinstance(children, list):
            for child in children:
                if (
                    child.get("type", "").lower()
                    == "microsoft.insights/diagnosticsettings"
                ):
                    ws_id = child.get("properties", {}).get("workspaceId")
                    if ws_id:
                        target_ids.add(str(ws_id))

        return target_ids
