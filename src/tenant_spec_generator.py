import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, ClassVar, Dict, List, Optional

from neo4j import GraphDatabase

from src.config_manager import SpecificationConfig

logger = logging.getLogger(__name__)

# --- Resource Anonymizer ---


class ResourceAnonymizer:
    """Handles consistent anonymization of Azure resource identifiers."""

    AZURE_ID_PATTERNS: ClassVar[list[str]] = [
        r"/subscriptions/[a-f0-9-]{36}",
        r"/resourceGroups/[\w-]+",
        r"[a-f0-9-]{36}",
        r"\w{24}",
        r"https://[\w-]+\.vault\.azure\.net",
        r"[\w-]+\.database\.windows\.net",
    ]

    def __init__(self, seed: Optional[str] = None):
        self.placeholder_cache: Dict[str, str] = {}
        self.seed = seed

    def anonymize_resource(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        orig_id = resource.get("id", "")
        orig_name = resource.get("name", "")
        resource_type = resource.get("type", "")
        ai_desc = resource.get("llm_description", "")

        placeholder = self._generate_placeholder(
            resource_type, orig_name, orig_id, ai_desc
        )
        self.placeholder_cache[orig_id] = placeholder

        anonymized = dict(resource)
        anonymized["id"] = placeholder
        anonymized["name"] = placeholder
        anonymized["resource_group"] = "anon-rg"
        anonymized["subscription_id"] = "anon-sub"
        anonymized["llm_description"] = self._remove_azure_identifiers(ai_desc)
        # Remove Azure IDs from properties and tags
        anonymized["properties"] = self._anonymize_dict(
            anonymized.get("properties", {})
        )
        anonymized["tags"] = self._anonymize_dict(anonymized.get("tags", {}))
        # Relationships will be anonymized separately
        return anonymized

    def anonymize_relationship(self, relationship: Dict[str, Any]) -> Dict[str, Any]:
        target_id = relationship.get("target_id", "")
        # Always generate placeholder if not cached
        if target_id in self.placeholder_cache:
            target_placeholder = self.placeholder_cache[target_id]
        else:
            # Fallback: generate a placeholder using minimal info
            target_placeholder = self._generate_placeholder(
                relationship.get("target_type", ""),
                relationship.get("target_name", ""),
                target_id,
                relationship.get("llm_description", ""),
            )
            self.placeholder_cache[target_id] = target_placeholder
        rel = dict(relationship)
        rel["target_id"] = target_placeholder
        rel["target_name"] = target_placeholder
        return rel

    def get_placeholder_mapping(self) -> Dict[str, str]:
        return dict(self.placeholder_cache)

    def _generate_placeholder(
        self,
        resource_type: str,
        original_name: str,
        original_id: str,
        ai_description: str,
    ) -> str:
        # kind: lower-case short Azure type (vm, vnet, rg, storage, sql, app, res fallback)
        type_prefix = self._extract_type_prefix(resource_type)
        # semantic: first noun-like token from AI summary or alphanumeric stem of original name; if none, 'generic'
        semantic_suffix = self._extract_semantic_suffix(ai_description, original_name)
        # hash8: first 8 chars of SHA256(original id or name)
        hash_input = f"{original_id or original_name}:{self.seed or ''}"
        hash_value = hashlib.sha256(hash_input.encode()).hexdigest()[:8]
        placeholder = f"{type_prefix}-{semantic_suffix}-{hash_value}"
        # Ensure regex match
        if not re.match(r"^[a-z]+-[a-z]+-[0-9a-f]{8}$", placeholder):
            placeholder = f"res-generic-{hash_value}"
        return placeholder

    def _extract_type_prefix(self, resource_type: str) -> str:
        # Map to short, lower-case Azure type
        type_mapping = {
            "Microsoft.Compute/virtualMachines": "vm",
            "Microsoft.Network/virtualNetworks": "vnet",
            "Microsoft.Resources/resourceGroups": "rg",
            "Microsoft.Storage/storageAccounts": "storage",
            "Microsoft.Sql/servers": "sql",
            "Microsoft.Web/sites": "app",
        }
        for k, v in type_mapping.items():
            if resource_type.lower().startswith(k.lower()):
                return v
        return "res"

    def _extract_semantic_suffix(self, ai_description: str, original_name: str) -> str:
        # Try to extract first noun-like token from AI summary
        if ai_description:
            # Simple noun-like extraction: first alphanumeric word >2 chars
            tokens = re.findall(r"\b[a-zA-Z][a-zA-Z0-9]{2,}\b", ai_description)
            if tokens:
                return tokens[0].lower()
        # Fallback: alphanumeric stem of original name
        if original_name:
            stem = re.sub(r"[^a-zA-Z0-9]", "", original_name)
            if stem:
                return stem[:12].lower()
        return "generic"

    def _remove_azure_identifiers(self, text: str) -> str:
        if not text:
            return text
        for pattern in self.AZURE_ID_PATTERNS:
            text = re.sub(pattern, "[ANONYMIZED]", text)
        return text

    def _anonymize_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for k, v in d.items():
            if isinstance(v, str):
                result[k] = self._remove_azure_identifiers(v)
            else:
                result[k] = v
        return result


# --- Tenant Specification Generator ---


class TenantSpecificationGenerator:
    """Generates anonymized Markdown specifications from Neo4j graph data."""

    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        anonymizer: ResourceAnonymizer,
        config: SpecificationConfig,
    ):
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.anonymizer = anonymizer
        self.config = config

    def generate_specification(self, output_path: Optional[str] = None) -> str:
        # Query resources and relationships
        resources = self._query_resources_with_limit()
        self._query_relationships()

        # Anonymize resources
        anonymized_resources = [
            self.anonymizer.anonymize_resource(r) for r in resources
        ]

        # Anonymize relationships
        for r in anonymized_resources:
            r["relationships"] = [
                self.anonymizer.anonymize_relationship(rel)
                for rel in r.get("relationships", [])
            ]

        # Group by category
        grouped = self._group_resources_by_category(anonymized_resources)

        # Render Markdown
        markdown = self._render_markdown(grouped)

        # Write to file
        if not output_path:
            output_path = self._get_default_output_path()

        # Only create directory if it's not the current directory
        output_dir = os.path.dirname(output_path)
        if output_dir and output_dir != "." and output_dir != os.getcwd():
            os.makedirs(output_dir, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown)
        logger.info(f"Specification written to {output_path}")
        return output_path

    def _query_resources_with_limit(self) -> List[Dict[str, Any]]:
        # Connect to Neo4j and query resources with limit
        driver = GraphDatabase.driver(
            self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
        )
        limit = self.config.resource_limit
        query = f"""
        MATCH (r)
        WHERE r.id IS NOT NULL AND r.type IS NOT NULL
        RETURN r
        LIMIT {limit}
        """
        resources: List[Dict[str, Any]] = []
        import json

        with driver.session() as session:
            for record in session.run(query):  # type: ignore[misc]
                node = record["r"]
                # Convert node to dict
                d = dict(node)
                # Parse properties/tags if they are JSON strings
                for key in ("properties", "tags"):
                    if key in d and isinstance(d[key], str):
                        try:
                            d[key] = json.loads(d[key])
                        except Exception:
                            d[key] = {}
                # Relationships will be filled in later
                d["relationships"] = []
                resources.append(d)
        driver.close()
        # Attach relationships
        rels = self._query_relationships()
        rel_map = {}
        for rel in rels:
            src = rel.get("source_id")
            if src not in rel_map:
                rel_map[src] = []
            rel_map[src].append(rel)
        for r in resources:
            r["relationships"] = rel_map.get(r.get("id"), [])
        return resources

    def _query_relationships(self) -> List[Dict[str, Any]]:
        driver = GraphDatabase.driver(
            self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
        )
        query = """
        MATCH (a)-[rel]->(b)
        WHERE a.id IS NOT NULL AND b.id IS NOT NULL
        RETURN a.id as source_id, type(rel) as type, b.id as target_id, b.name as target_name, b.type as target_type
        """
        relationships: List[Dict[str, Any]] = []
        with driver.session() as session:
            for record in session.run(query):
                relationships.append(
                    {
                        "source_id": record["source_id"],
                        "type": record["type"],
                        "target_id": record["target_id"],
                        "target_name": record["target_name"],
                        "target_type": record["target_type"],
                    }
                )
        driver.close()
        return relationships

    def _group_resources_by_category(
        self, resources: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        # Group by major Azure service categories
        categories = {
            "Compute": ["Microsoft.Compute/virtualMachines"],
            "Storage": ["Microsoft.Storage/storageAccounts"],
            "Networking": ["Microsoft.Network/virtualNetworks"],
            "Web": ["Microsoft.Web/sites"],
            "Database": ["Microsoft.Sql/servers"],
            "KeyVault": ["Microsoft.KeyVault/vaults"],
            "Other": [],
        }
        grouped: Dict[str, List[Dict[str, Any]]] = {k: [] for k in categories}
        for r in resources:
            found = False
            for cat, types in categories.items():
                if r.get("type") in types:
                    grouped[cat].append(r)
                    found = True
                    break
            if not found:
                grouped["Other"].append(r)
        return grouped

    def _render_markdown(self, grouped_data: Dict[str, Any]) -> str:
        # Render Markdown per spec
        lines: List[str] = []
        lines.append("# Azure Tenant Infrastructure Specification\n")
        lines.append(
            f"_Generated at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}_\n"
        )
        for category, resources in grouped_data.items():
            if not resources:
                continue
            lines.append(f"## {category}\n")
            for r in resources:
                lines.append(f"### {r['name']} ({r['type']})\n")
                if self.config.include_ai_summaries and r.get("llm_description"):
                    lines.append(f"> {r['llm_description']}\n")
                lines.append(f"- **Location:** {r.get('location', '[ANONYMIZED]')}")
                lines.append(
                    f"- **Resource Group:** {r.get('resource_group', '[ANONYMIZED]')}"
                )
                lines.append(
                    f"- **Subscription:** {r.get('subscription_id', '[ANONYMIZED]')}"
                )
                if self.config.include_configuration_details:
                    lines.append("- **Properties:**")
                    for k, v in r.get("properties", {}).items():
                        lines.append(f"    - {k}: {v}")
                    if r.get("tags"):
                        lines.append("- **Tags:**")
                        for k, v in r.get("tags", {}).items():
                            lines.append(f"    - {k}: {v}")
                if r.get("relationships"):
                    lines.append("- **Relationships:**")
                    for rel in r["relationships"]:
                        lines.append(
                            f"    - {rel['type']} ➔ {rel['target_id']} ({rel['target_type']})"
                        )
                lines.append("")
        return "\n".join(lines)

    def _get_default_output_path(self) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        outdir = self.config.output_directory
        return os.path.join(outdir, f"{ts}_tenant_spec.md")
