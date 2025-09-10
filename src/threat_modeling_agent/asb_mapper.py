"""
Azure Security Benchmark (ASB) mapper module.
Maps threats to relevant Azure Security Benchmark v3 controls with detailed recommendations.
"""

import logging
from typing import Any, Dict, List, Optional


class AzureSecurityBenchmarkMapper:
    """
    Maps threats to Azure Security Benchmark (ASB) v3 controls.
    Provides detailed security recommendations based on threat patterns and Azure resource types.
    """

    def __init__(self):
        """Initialize the ASB mapper with comprehensive control mappings."""
        self.stride_to_asb = self._init_stride_mappings()
        self.resource_type_controls = self._init_resource_type_controls()
        self.severity_to_priority = {
            "Critical": "High",
            "High": "Medium",
            "Medium": "Medium",
            "Low": "Low",
        }

    def _init_stride_mappings(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Initialize STRIDE to ASB control mappings based on Azure Security Benchmark v3.
        """
        return {
            "S": [  # Spoofing
                {
                    "control_id": "IM-1",
                    "title": "Use centralized identity and authentication system",
                    "description": "Use Azure Active Directory as the centralized identity and authentication system for all services.",
                    "guidance": "Implement Azure AD for centralized authentication, enable MFA, and use managed identities where possible.",
                    "implementation": [
                        "Enable Azure AD authentication",
                        "Configure MFA",
                        "Use managed identities",
                    ],
                    "category": "Identity Management",
                },
                {
                    "control_id": "IM-2",
                    "title": "Manage application identities securely and automatically",
                    "description": "Use Azure managed identities for applications to authenticate to Azure services automatically.",
                    "guidance": "Avoid using hardcoded credentials and instead use managed identities or service principals with certificates.",
                    "implementation": [
                        "Use system-assigned managed identities",
                        "Implement certificate-based authentication",
                        "Avoid storing credentials in code",
                    ],
                    "category": "Identity Management",
                },
                {
                    "control_id": "IM-3",
                    "title": "Use Azure AD single sign-on (SSO) for application access",
                    "description": "Use Azure AD for SSO to reduce authentication complexity and improve user experience.",
                    "guidance": "Configure applications to use Azure AD for single sign-on to reduce password fatigue and improve security.",
                    "implementation": [
                        "Configure Azure AD SSO",
                        "Use SAML/OIDC protocols",
                        "Implement conditional access",
                    ],
                    "category": "Identity Management",
                },
            ],
            "T": [  # Tampering
                {
                    "control_id": "DP-3",
                    "title": "Monitor for unauthorized transfer of sensitive data",
                    "description": "Monitor and detect unauthorized data transfers using Azure monitoring services.",
                    "guidance": "Implement data loss prevention policies and monitor data access patterns.",
                    "implementation": [
                        "Enable Azure Monitor",
                        "Configure DLP policies",
                        "Implement access logging",
                    ],
                    "category": "Data Protection",
                },
                {
                    "control_id": "DP-4",
                    "title": "Enable data encryption at rest",
                    "description": "Encrypt sensitive data at rest using Azure encryption services.",
                    "guidance": "Enable encryption for all data stores including databases, storage accounts, and virtual machine disks.",
                    "implementation": [
                        "Enable Azure Storage encryption",
                        "Use Azure Disk Encryption",
                        "Configure database encryption",
                    ],
                    "category": "Data Protection",
                },
                {
                    "control_id": "DP-5",
                    "title": "Enable data encryption in transit",
                    "description": "Encrypt data in transit using TLS 1.2 or higher encryption protocols.",
                    "guidance": "Ensure all communications use HTTPS/TLS and configure minimum TLS version requirements.",
                    "implementation": [
                        "Enforce HTTPS",
                        "Configure TLS 1.2+",
                        "Use VPN for network traffic",
                    ],
                    "category": "Data Protection",
                },
            ],
            "R": [  # Repudiation
                {
                    "control_id": "LT-1",
                    "title": "Enable threat detection for Azure services",
                    "description": "Enable Azure Security Center and Azure Sentinel for threat detection and monitoring.",
                    "guidance": "Configure comprehensive logging and monitoring across all Azure services.",
                    "implementation": [
                        "Enable Azure Security Center",
                        "Configure Azure Sentinel",
                        "Set up security alerts",
                    ],
                    "category": "Logging and Threat Detection",
                },
                {
                    "control_id": "LT-2",
                    "title": "Enable security incident detection capability",
                    "description": "Implement security incident detection and response capabilities.",
                    "guidance": "Configure automated incident response and establish security operations center (SOC) procedures.",
                    "implementation": [
                        "Configure SIEM",
                        "Implement automated response",
                        "Establish SOC procedures",
                    ],
                    "category": "Logging and Threat Detection",
                },
                {
                    "control_id": "LT-4",
                    "title": "Enable logging for Azure services",
                    "description": "Enable comprehensive logging for all Azure services and store logs securely.",
                    "guidance": "Configure diagnostic logging for all Azure resources and centralize log storage.",
                    "implementation": [
                        "Enable diagnostic logging",
                        "Configure Log Analytics",
                        "Implement log retention policies",
                    ],
                    "category": "Logging and Threat Detection",
                },
            ],
            "I": [  # Information Disclosure
                {
                    "control_id": "DP-1",
                    "title": "Discovery, classify, and label sensitive data",
                    "description": "Implement data discovery and classification to identify and protect sensitive information.",
                    "guidance": "Use Azure Information Protection and data classification tools to identify sensitive data.",
                    "implementation": [
                        "Implement data classification",
                        "Use Azure Information Protection",
                        "Apply sensitivity labels",
                    ],
                    "category": "Data Protection",
                },
                {
                    "control_id": "DP-2",
                    "title": "Protect sensitive data",
                    "description": "Implement access controls and encryption to protect sensitive data from unauthorized access.",
                    "guidance": "Use role-based access control (RBAC) and encryption to protect sensitive information.",
                    "implementation": [
                        "Implement RBAC",
                        "Enable data encryption",
                        "Use private endpoints",
                    ],
                    "category": "Data Protection",
                },
                {
                    "control_id": "NS-2",
                    "title": "Connect private networks together",
                    "description": "Use private network connections and avoid exposing services to the public internet.",
                    "guidance": "Implement private endpoints, VNet peering, and network segmentation to protect data flows.",
                    "implementation": [
                        "Configure private endpoints",
                        "Implement VNet peering",
                        "Use network segmentation",
                    ],
                    "category": "Network Security",
                },
            ],
            "D": [  # Denial of Service
                {
                    "control_id": "NS-3",
                    "title": "Establish private network access to Azure services",
                    "description": "Use private endpoints and service endpoints to reduce exposure to DDoS attacks.",
                    "guidance": "Implement private network access to minimize attack surface for DoS attacks.",
                    "implementation": [
                        "Configure private endpoints",
                        "Use service endpoints",
                        "Implement network ACLs",
                    ],
                    "category": "Network Security",
                },
                {
                    "control_id": "NS-4",
                    "title": "Protect applications and services from external network attacks",
                    "description": "Use Azure DDoS Protection and Web Application Firewall to protect against attacks.",
                    "guidance": "Enable DDoS protection and implement web application firewall rules.",
                    "implementation": [
                        "Enable Azure DDoS Protection",
                        "Configure WAF",
                        "Implement rate limiting",
                    ],
                    "category": "Network Security",
                },
                {
                    "control_id": "BC-1",
                    "title": "Ensure backup and recovery plan is in place",
                    "description": "Implement backup and disaster recovery capabilities to maintain service availability.",
                    "guidance": "Configure automated backups and test disaster recovery procedures regularly.",
                    "implementation": [
                        "Configure Azure Backup",
                        "Implement geo-redundancy",
                        "Test DR procedures",
                    ],
                    "category": "Backup and Recovery",
                },
            ],
            "E": [  # Elevation of Privilege
                {
                    "control_id": "PA-1",
                    "title": "Protect and limit highly privileged users",
                    "description": "Limit the number of highly privileged accounts and protect them with additional security controls.",
                    "guidance": "Implement privileged identity management and just-in-time access for administrative accounts.",
                    "implementation": [
                        "Use Azure PIM",
                        "Implement JIT access",
                        "Limit privileged accounts",
                    ],
                    "category": "Privileged Access",
                },
                {
                    "control_id": "PA-2",
                    "title": "Restrict admin access to business-critical systems",
                    "description": "Implement additional restrictions and monitoring for administrative access to critical systems.",
                    "guidance": "Use privileged access workstations and implement strict access controls for admin accounts.",
                    "implementation": [
                        "Use PAWs",
                        "Implement strict access controls",
                        "Monitor admin activities",
                    ],
                    "category": "Privileged Access",
                },
                {
                    "control_id": "IM-7",
                    "title": "Eliminate unintended credential exposure",
                    "description": "Prevent credential exposure in code, configuration files, and logs.",
                    "guidance": "Use Azure Key Vault to store secrets and implement credential scanning tools.",
                    "implementation": [
                        "Use Azure Key Vault",
                        "Implement credential scanning",
                        "Avoid hardcoded secrets",
                    ],
                    "category": "Identity Management",
                },
            ],
        }

    def _init_resource_type_controls(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Initialize resource type specific ASB controls.
        """
        return {
            "Microsoft.Compute/virtualMachines": [
                {
                    "control_id": "ES-1",
                    "title": "Use Endpoint Detection and Response (EDR) solution",
                    "description": "Deploy endpoint detection and response capabilities on virtual machines.",
                    "guidance": "Install and configure Microsoft Defender for Endpoint or equivalent EDR solution.",
                    "implementation": [
                        "Deploy EDR agent",
                        "Configure monitoring",
                        "Enable real-time protection",
                    ],
                    "category": "Endpoint Security",
                },
                {
                    "control_id": "ES-2",
                    "title": "Use centrally managed modern anti-malware software",
                    "description": "Deploy and manage anti-malware solutions centrally across all virtual machines.",
                    "guidance": "Use Microsoft Antimalware for Azure or equivalent centrally managed solution.",
                    "implementation": [
                        "Deploy anti-malware",
                        "Configure central management",
                        "Enable real-time scanning",
                    ],
                    "category": "Endpoint Security",
                },
            ],
            "Microsoft.Storage/storageAccounts": [
                {
                    "control_id": "ST-1",
                    "title": "Enable threat protection for storage accounts",
                    "description": "Enable Azure Defender for Storage to detect malicious activities.",
                    "guidance": "Configure threat protection to detect unusual access patterns and malware uploads.",
                    "implementation": [
                        "Enable Azure Defender for Storage",
                        "Configure threat alerts",
                        "Monitor access patterns",
                    ],
                    "category": "Storage Security",
                },
                {
                    "control_id": "ST-2",
                    "title": "Secure storage account access",
                    "description": "Implement secure access controls for storage accounts including network restrictions.",
                    "guidance": "Use private endpoints, firewall rules, and shared access signatures with appropriate restrictions.",
                    "implementation": [
                        "Configure private endpoints",
                        "Implement firewall rules",
                        "Use time-limited SAS",
                    ],
                    "category": "Storage Security",
                },
            ],
            "Microsoft.Sql/servers": [
                {
                    "control_id": "DS-1",
                    "title": "Enable SQL threat detection",
                    "description": "Enable Advanced Threat Protection for SQL databases to detect suspicious activities.",
                    "guidance": "Configure SQL threat detection to identify potential SQL injection and unusual access patterns.",
                    "implementation": [
                        "Enable ATP for SQL",
                        "Configure threat alerts",
                        "Monitor query patterns",
                    ],
                    "category": "Database Security",
                },
                {
                    "control_id": "DS-2",
                    "title": "Secure database access",
                    "description": "Implement strong authentication and network security for database access.",
                    "guidance": "Use Azure AD authentication, private endpoints, and firewall rules for database security.",
                    "implementation": [
                        "Use Azure AD auth",
                        "Configure private endpoints",
                        "Implement firewall rules",
                    ],
                    "category": "Database Security",
                },
            ],
            "Microsoft.Web/sites": [
                {
                    "control_id": "AS-1",
                    "title": "Enable application security features",
                    "description": "Enable security features specific to web applications and app services.",
                    "guidance": "Configure HTTPS only, use managed identities, and enable application insights.",
                    "implementation": [
                        "Enforce HTTPS only",
                        "Use managed identities",
                        "Enable App Insights",
                    ],
                    "category": "Application Security",
                },
                {
                    "control_id": "AS-2",
                    "title": "Implement web application firewall",
                    "description": "Deploy WAF to protect web applications from common attacks.",
                    "guidance": "Configure Application Gateway with WAF or Azure Front Door with WAF.",
                    "implementation": [
                        "Deploy Application Gateway",
                        "Configure WAF rules",
                        "Enable bot protection",
                    ],
                    "category": "Application Security",
                },
            ],
        }

    def map_controls(
        self, threat_list: List[Dict[str, Any]], logger: Optional[logging.Logger] = None
    ) -> List[Dict[str, Any]]:
        """
        Maps each threat in the list to relevant ASB v3 controls with detailed recommendations.

        Args:
            threat_list: List of threat dictionaries
            logger: Optional logger for error/info output

        Returns:
            List of enriched threat dictionaries with ASB control mappings
        """
        if logger is None:
            logger = logging.getLogger("ASBMapper")

        enriched = []

        for threat in threat_list:
            try:
                threat_with_asb = dict(threat)

                # Get STRIDE-based controls
                stride = threat.get("stride", "")
                asb_controls = self.stride_to_asb.get(stride, []).copy()

                # Add resource-type specific controls
                resource_type = threat.get("resource_type", "")
                if resource_type in self.resource_type_controls:
                    resource_controls = self.resource_type_controls[resource_type]
                    asb_controls.extend(resource_controls)

                # Enhance controls based on threat severity and context
                enhanced_controls = self._enhance_controls_for_threat(
                    threat, asb_controls, logger
                )

                # Add priority and implementation guidance
                for control in enhanced_controls:
                    control["priority"] = self._calculate_control_priority(
                        threat, control
                    )
                    control["implementation_effort"] = (
                        self._estimate_implementation_effort(control)
                    )
                    control["cost_impact"] = self._estimate_cost_impact(control)

                threat_with_asb["asb_controls"] = enhanced_controls
                threat_with_asb["control_summary"] = self._generate_control_summary(
                    enhanced_controls
                )

                enriched.append(threat_with_asb)

                logger.info(
                    f"Mapped threat '{threat.get('title', 'unknown')}' to {len(enhanced_controls)} ASB controls"
                )

            except Exception as e:
                logger.error(
                    f"ASB mapping failed for threat '{threat.get('title', 'unknown')}': {e}"
                )
                # Add threat without controls rather than failing completely
                enriched.append(dict(threat))

        logger.info(f"Successfully mapped ASB controls for {len(enriched)} threats")
        return enriched

    def _enhance_controls_for_threat(
        self,
        threat: Dict[str, Any],
        controls: List[Dict[str, Any]],
        logger: logging.Logger,
    ) -> List[Dict[str, Any]]:
        """
        Enhance control recommendations based on specific threat characteristics.
        """
        enhanced_controls = []
        threat_severity = threat.get("severity", "Medium")
        resource_type = threat.get("resource_type", "")

        for control in controls:
            enhanced_control = dict(control)

            # Add threat-specific context
            enhanced_control["threat_context"] = {
                "severity": threat_severity,
                "resource_type": resource_type,
                "threat_title": threat.get("title", ""),
                "applicability": "High",
            }

            # Enhance implementation guidance based on threat severity
            if threat_severity == "Critical":
                enhanced_control["implementation_urgency"] = "Immediate"
                enhanced_control["recommended_timeline"] = "Within 24 hours"
            elif threat_severity == "High":
                enhanced_control["implementation_urgency"] = "High"
                enhanced_control["recommended_timeline"] = "Within 1 week"
            else:
                enhanced_control["implementation_urgency"] = "Medium"
                enhanced_control["recommended_timeline"] = "Within 1 month"

            # Add resource-specific implementation details
            if resource_type:
                enhanced_control["resource_specific_guidance"] = (
                    self._get_resource_specific_guidance(resource_type, control)
                )

            enhanced_controls.append(enhanced_control)

        return enhanced_controls

    def _get_resource_specific_guidance(
        self, resource_type: str, control: Dict[str, Any]
    ) -> List[str]:
        """
        Get resource-specific implementation guidance for a control.
        """
        guidance_map = {
            "Microsoft.Compute/virtualMachines": {
                "IM-1": [
                    "Configure VM to use Azure AD joined or hybrid joined",
                    "Enable MFA for VM access",
                ],
                "DP-4": [
                    "Enable Azure Disk Encryption",
                    "Use customer-managed keys where appropriate",
                ],
                "LT-4": [
                    "Enable VM diagnostic logging",
                    "Configure Log Analytics agent",
                ],
            },
            "Microsoft.Storage/storageAccounts": {
                "DP-4": [
                    "Enable storage service encryption",
                    "Use customer-managed keys for enhanced security",
                ],
                "NS-2": [
                    "Configure private endpoints for storage",
                    "Disable public blob access",
                ],
                "IM-1": [
                    "Use managed identities for storage access",
                    "Disable shared key access",
                ],
            },
            "Microsoft.Sql/servers": {
                "IM-1": [
                    "Enable Azure AD authentication for SQL",
                    "Disable SQL authentication where possible",
                ],
                "DP-4": [
                    "Enable Transparent Data Encryption",
                    "Use customer-managed keys",
                ],
                "NS-2": [
                    "Configure private endpoints for SQL",
                    "Implement firewall rules",
                ],
            },
        }

        control_id = control.get("control_id", "")
        return guidance_map.get(resource_type, {}).get(control_id, [])

    def _calculate_control_priority(
        self, threat: Dict[str, Any], control: Dict[str, Any]
    ) -> str:
        """
        Calculate implementation priority for a control based on threat characteristics.
        """
        severity = threat.get("severity", "Medium")
        likelihood = threat.get("likelihood", "Medium")

        # High severity or high likelihood threats get high priority controls
        if severity in ["Critical", "High"] or likelihood == "High":
            return "High"
        elif severity == "Medium" and likelihood == "Medium":
            return "Medium"
        else:
            return "Low"

    def _estimate_implementation_effort(self, control: Dict[str, Any]) -> str:
        """
        Estimate implementation effort for a control.
        """
        # This is a simplified estimation based on control complexity
        control_id = control.get("control_id", "")

        high_effort_controls = ["LT-1", "LT-2", "PA-1", "PA-2", "AS-2"]
        medium_effort_controls = ["DP-4", "DP-5", "NS-2", "NS-3", "IM-1"]

        if control_id in high_effort_controls:
            return "High"
        elif control_id in medium_effort_controls:
            return "Medium"
        else:
            return "Low"

    def _estimate_cost_impact(self, control: Dict[str, Any]) -> str:
        """
        Estimate cost impact of implementing a control.
        """
        control_id = control.get("control_id", "")

        high_cost_controls = ["LT-1", "LT-2", "ES-1", "AS-2", "BC-1"]
        medium_cost_controls = ["DP-4", "NS-3", "PA-1", "ES-2"]

        if control_id in high_cost_controls:
            return "High"
        elif control_id in medium_cost_controls:
            return "Medium"
        else:
            return "Low"

    def _generate_control_summary(
        self, controls: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate a summary of mapped controls.
        """
        if not controls:
            return {"total_controls": 0, "categories": [], "priorities": {}}

        categories = list({control.get("category", "Unknown") for control in controls})
        priorities = {}

        for control in controls:
            priority = control.get("priority", "Medium")
            priorities[priority] = priorities.get(priority, 0) + 1

        return {
            "total_controls": len(controls),
            "categories": categories,
            "priorities": priorities,
            "high_priority_controls": len(
                [c for c in controls if c.get("priority") == "High"]
            ),
            "immediate_actions": len(
                [c for c in controls if c.get("implementation_urgency") == "Immediate"]
            ),
        }


def map_controls(
    threat_list: List[Dict[str, Any]], logger: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """
    Legacy function for compatibility.
    Maps each threat in the list to relevant ASB v3 controls.

    Args:
        threat_list: List of threat dicts
        logger: Optional logger for error/info output

    Returns:
        List of enriched threat dicts with ASB control mappings
    """
    mapper = AzureSecurityBenchmarkMapper()
    return mapper.map_controls(threat_list, logger)
