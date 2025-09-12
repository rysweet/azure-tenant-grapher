"""
Hierarchical Tenant Specification Generator

Generates tenant specifications organized by containment hierarchy:
Tenant → Subscriptions → Regions → Resource Groups → Resources

Includes purpose inference at each level.
"""

import logging
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from neo4j import GraphDatabase

from src.tenant_spec_generator import TenantSpecificationGenerator, ResourceAnonymizer

logger = logging.getLogger(__name__)


class TenantAnalyzer:
    """Analyzes tenant-level patterns and infers purpose."""
    
    @staticmethod
    def infer_tenant_purpose(resources: List[Dict[str, Any]]) -> str:
        """Infer the overall purpose of the tenant based on resources."""
        patterns = {
            'development': ['dev', 'test', 'staging', 'sandbox', 'poc'],
            'production': ['prod', 'production', 'live', 'prd'],
            'hybrid_cloud': ['dc', 'domain', 'ad', 'hybrid', 'onprem'],
            'data_platform': ['databricks', 'synapse', 'datalake', 'datafactory', 'hdinsight'],
            'web_hosting': ['app-service', 'webapp', 'api', 'functionapp', 'frontdoor'],
            'infrastructure': ['bastion', 'vpn', 'firewall', 'gateway', 'expressroute'],
            'analytics': ['analytics', 'loganalytics', 'powerbi', 'insights'],
            'ml_ai': ['machinelearning', 'cognitive', 'openai', 'ml-', 'ai-'],
            'containers': ['kubernetes', 'aks', 'container', 'registry'],
            'iot': ['iothub', 'iotcentral', 'eventhub', 'stream'],
        }
        
        scores = defaultdict(int)
        total_resources = len(resources)
        
        for resource in resources:
            name = resource.get('name', '').lower()
            rtype = resource.get('type', '').lower()
            description = resource.get('llm_description', '').lower()
            
            combined_text = f"{name} {rtype} {description}"
            
            for category, keywords in patterns.items():
                for keyword in keywords:
                    if keyword in combined_text:
                        scores[category] += 1
        
        # Determine primary purposes
        purposes = []
        for category, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]:
            if score > total_resources * 0.1:  # At least 10% of resources
                purposes.append(category.replace('_', ' ').title())
        
        if not purposes:
            return "General Purpose Cloud Infrastructure"
        
        return f"{', '.join(purposes)} Infrastructure"


class ResourceGroupAnalyzer:
    """Analyzes resource group patterns and infers purpose."""
    
    @staticmethod
    def infer_rg_purpose(resources: List[Dict[str, Any]]) -> str:
        """Infer the purpose of a resource group based on contained resources."""
        if not resources:
            return "Empty Resource Group"
        
        # Count resource types
        type_counts = defaultdict(int)
        for resource in resources:
            rtype = resource.get('type', '').split('/')[-1].lower()
            type_counts[rtype] += 1
        
        # Common patterns
        if 'virtualMachines' in type_counts and 'networkInterfaces' in type_counts:
            if 'loadBalancers' in type_counts:
                return "Load-Balanced Compute Cluster"
            return "Virtual Machine Infrastructure"
        
        if 'sites' in type_counts:
            if 'serverfarms' in type_counts:
                return "Web Application Hosting"
            return "App Service Infrastructure"
        
        if 'storageAccounts' in type_counts and 'factories' in type_counts:
            return "Data Pipeline Infrastructure"
        
        if 'workspaces' in type_counts:
            if 'databricks' in str(type_counts):
                return "Databricks Analytics Platform"
            return "Log Analytics Workspace"
        
        if 'vaults' in type_counts:
            return "Security and Secrets Management"
        
        if 'databaseAccounts' in type_counts or 'servers' in type_counts:
            return "Database Infrastructure"
        
        if 'virtualNetworks' in type_counts or 'networkSecurityGroups' in type_counts:
            return "Network Infrastructure"
        
        # Default to most common resource type
        if type_counts:
            most_common = max(type_counts.items(), key=lambda x: x[1])
            return f"{most_common[0].title()} Resources"
        
        return "Mixed Resources"


class HierarchicalSpecGenerator(TenantSpecificationGenerator):
    """Generates hierarchical tenant specifications with purpose inference."""
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str, 
                 anonymizer: Optional[ResourceAnonymizer] = None, 
                 spec_config: Optional[Any] = None):
        """Initialize the hierarchical spec generator."""
        super().__init__(neo4j_uri, neo4j_user, neo4j_password, anonymizer, spec_config)
        self.tenant_analyzer = TenantAnalyzer()
        self.rg_analyzer = ResourceGroupAnalyzer()
    
    def generate_specification(self, output_path: Optional[str] = None) -> str:
        """Generate a hierarchical tenant specification."""
        # Query all resources with hierarchy information
        resources = self._query_resources_with_hierarchy()
        
        if not resources:
            content = "# No resources found in the graph database\n"
        else:
            # Build hierarchical structure
            hierarchy = self._build_hierarchy(resources)
            
            # Generate markdown
            content = self._generate_hierarchical_markdown(hierarchy, resources)
        
        # Save to file if output path provided
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return output_path
        
        return content
    
    def _query_resources_with_hierarchy(self) -> List[Dict[str, Any]]:
        """Query resources with full hierarchy information."""
        query = """
        MATCH (r:Resource)
        OPTIONAL MATCH (r)-[:BELONGS_TO]->(rg:ResourceGroup)
        OPTIONAL MATCH (rg)-[:BELONGS_TO]->(s:Subscription)
        RETURN r, rg.name as resource_group, s.id as subscription_id, 
               r.location as region, r.type as type, r.name as name,
               r.id as id, r.llm_description as llm_description,
               properties(r) as properties
        ORDER BY s.id, r.location, rg.name, r.type, r.name
        """
        
        resources = []
        with self.driver.session() as session:
            result = session.run(query)
            for record in result:
                resource = dict(record['r'])
                resource['resource_group'] = record['resource_group'] or 'unknown-rg'
                resource['subscription_id'] = record['subscription_id'] or 'unknown-sub'
                resource['region'] = record['region'] or 'global'
                resources.append(resource)
        
        return resources
    
    def _build_hierarchy(self, resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build a hierarchical structure from flat resource list."""
        hierarchy = {
            'subscriptions': defaultdict(lambda: {
                'regions': defaultdict(lambda: {
                    'resource_groups': defaultdict(list)
                })
            })
        }
        
        for resource in resources:
            sub_id = resource['subscription_id']
            region = resource['region']
            rg = resource['resource_group']
            
            hierarchy['subscriptions'][sub_id]['regions'][region]['resource_groups'][rg].append(resource)
        
        return hierarchy
    
    def _generate_hierarchical_markdown(self, hierarchy: Dict[str, Any], all_resources: List[Dict[str, Any]]) -> str:
        """Generate markdown from hierarchical structure."""
        lines = []
        
        # Header
        lines.append("# Azure Tenant Infrastructure Specification")
        lines.append(f"\n*Generated: {datetime.now(timezone.utc).isoformat()}*\n")
        
        # Executive Summary
        lines.append("## Executive Summary\n")
        lines.append(self._generate_executive_summary(hierarchy, all_resources))
        
        # Subscriptions
        for sub_id, sub_data in hierarchy['subscriptions'].items():
            lines.append(f"\n## Subscription: {self._anonymize_id(sub_id)}\n")
            
            # Subscription overview
            sub_resources = self._get_subscription_resources(sub_data)
            lines.append("### Overview\n")
            lines.append(f"- **Total Resources**: {len(sub_resources)}")
            lines.append(f"- **Regions**: {', '.join(sub_data['regions'].keys())}")
            lines.append(f"- **Resource Groups**: {self._count_resource_groups(sub_data)}")
            
            # Infer subscription purpose
            sub_purpose = self._infer_subscription_purpose(sub_resources)
            lines.append(f"- **Primary Purpose**: {sub_purpose}\n")
            
            # Regions
            for region, region_data in sorted(sub_data['regions'].items()):
                if region == 'global':
                    lines.append(f"\n### Global Resources\n")
                else:
                    lines.append(f"\n### Region: {region}\n")
                
                # Resource Groups
                for rg_name, resources in sorted(region_data['resource_groups'].items()):
                    lines.append(f"\n#### Resource Group: {self._anonymize_id(rg_name)}\n")
                    
                    # Infer RG purpose
                    rg_purpose = self.rg_analyzer.infer_rg_purpose(resources)
                    lines.append(f"**Purpose**: {rg_purpose}\n")
                    lines.append(f"**Resource Count**: {len(resources)}\n")
                    
                    # Resources
                    lines.append("\n##### Resources:\n")
                    for resource in sorted(resources, key=lambda r: (r.get('type', ''), r.get('name', ''))):
                        lines.append(self._format_resource(resource))
        
        # Cross-subscription relationships (if any)
        lines.append("\n## Cross-Subscription Dependencies\n")
        lines.append(self._identify_cross_subscription_dependencies(all_resources))
        
        return '\n'.join(lines)
    
    def _generate_executive_summary(self, hierarchy: Dict[str, Any], all_resources: List[Dict[str, Any]]) -> str:
        """Generate executive summary section."""
        lines = []
        
        # Basic statistics
        total_subs = len(hierarchy['subscriptions'])
        total_resources = len(all_resources)
        
        # Get all regions
        all_regions = set()
        total_rgs = 0
        for sub_data in hierarchy['subscriptions'].values():
            all_regions.update(sub_data['regions'].keys())
            for region_data in sub_data['regions'].values():
                total_rgs += len(region_data['resource_groups'])
        
        lines.append(f"- **Tenant Purpose**: {self.tenant_analyzer.infer_tenant_purpose(all_resources)}")
        lines.append(f"- **Total Subscriptions**: {total_subs}")
        lines.append(f"- **Total Resource Groups**: {total_rgs}")
        lines.append(f"- **Total Resources**: {total_resources}")
        lines.append(f"- **Primary Regions**: {', '.join(sorted(all_regions)[:5])}")
        
        # Key technologies
        tech_patterns = self._identify_key_technologies(all_resources)
        if tech_patterns:
            lines.append(f"- **Key Technologies**: {', '.join(tech_patterns)}")
        
        return '\n'.join(lines)
    
    def _identify_key_technologies(self, resources: List[Dict[str, Any]]) -> List[str]:
        """Identify key technologies used in the tenant."""
        tech_map = {
            'Microsoft.Compute/virtualMachines': 'Virtual Machines',
            'Microsoft.Web/sites': 'App Services',
            'Microsoft.ContainerService/managedClusters': 'Kubernetes (AKS)',
            'Microsoft.Storage/storageAccounts': 'Storage',
            'Microsoft.Sql/servers': 'SQL Database',
            'Microsoft.DocumentDB/databaseAccounts': 'Cosmos DB',
            'Microsoft.Databricks/workspaces': 'Databricks',
            'Microsoft.Synapse/workspaces': 'Synapse Analytics',
            'Microsoft.KeyVault/vaults': 'Key Vault',
            'Microsoft.Network/applicationGateways': 'Application Gateway',
            'Microsoft.Network/frontDoors': 'Front Door',
            'Microsoft.MachineLearningServices/workspaces': 'Machine Learning',
        }
        
        found_tech = set()
        for resource in resources:
            rtype = resource.get('type', '')
            if rtype in tech_map:
                found_tech.add(tech_map[rtype])
        
        return sorted(list(found_tech))[:10]  # Top 10 technologies
    
    def _get_subscription_resources(self, sub_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get all resources in a subscription."""
        resources = []
        for region_data in sub_data['regions'].values():
            for rg_resources in region_data['resource_groups'].values():
                resources.extend(rg_resources)
        return resources
    
    def _count_resource_groups(self, sub_data: Dict[str, Any]) -> int:
        """Count resource groups in a subscription."""
        count = 0
        for region_data in sub_data['regions'].values():
            count += len(region_data['resource_groups'])
        return count
    
    def _infer_subscription_purpose(self, resources: List[Dict[str, Any]]) -> str:
        """Infer subscription purpose based on resource patterns."""
        # Check for environment patterns in resource names
        names = ' '.join([r.get('name', '').lower() for r in resources])
        
        if any(env in names for env in ['prod', 'production', 'prd']):
            return "Production Environment"
        elif any(env in names for env in ['dev', 'development', 'test']):
            return "Development/Test Environment"
        elif any(env in names for env in ['staging', 'stage', 'uat']):
            return "Staging/UAT Environment"
        
        # Fall back to technology-based inference
        return self.tenant_analyzer.infer_tenant_purpose(resources)
    
    def _format_resource(self, resource: Dict[str, Any]) -> str:
        """Format a single resource for markdown output."""
        name = self._anonymize_id(resource.get('name', 'unknown'))
        rtype = resource.get('type', 'unknown')
        description = resource.get('llm_description', '')
        
        # Clean up description
        if description:
            description = self._remove_azure_identifiers(description)
            # Truncate if too long
            if len(description) > 200:
                description = description[:197] + "..."
        
        return f"- **{name}** ({rtype})\n  {description}\n"
    
    def _identify_cross_subscription_dependencies(self, resources: List[Dict[str, Any]]) -> str:
        """Identify cross-subscription dependencies."""
        # This would require relationship queries in the real implementation
        # For now, return a placeholder
        return "*No cross-subscription dependencies detected in this analysis.*\n"
    
    def _anonymize_id(self, identifier: str) -> str:
        """Anonymize an identifier."""
        if not self.anonymizer:
            return identifier
        
        # Use the anonymizer's placeholder cache if available
        if hasattr(self.anonymizer, 'placeholder_cache'):
            if identifier in self.anonymizer.placeholder_cache:
                return self.anonymizer.placeholder_cache[identifier]
        
        # Generate a simple hash-based placeholder
        import hashlib
        hash_val = hashlib.md5(identifier.encode()).hexdigest()[:8]
        return f"anon-{hash_val}"
    
    def _remove_azure_identifiers(self, text: str) -> str:
        """Remove Azure identifiers from text."""
        if not text:
            return text
        
        # Patterns to remove
        patterns = [
            r'/subscriptions/[a-f0-9-]{36}',
            r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}',
            r'https://[\w-]+\.vault\.azure\.net',
            r'[\w-]+\.database\.windows\.net',
        ]
        
        result = text
        for pattern in patterns:
            result = re.sub(pattern, '[REDACTED]', result, flags=re.IGNORECASE)
        
        return result