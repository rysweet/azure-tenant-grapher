import logging
import uuid
from typing import Any, Dict, List, Optional


class STRIDEThreatEnumerator:
    """
    STRIDE-based threat enumeration for Azure resources.
    Analyzes Azure resources and generates threats based on STRIDE methodology.
    """

    def __init__(self):
        self.resource_threat_patterns = self._init_resource_patterns()
        self.stride_categories = {
            "S": "Spoofing",
            "T": "Tampering",
            "R": "Repudiation",
            "I": "Information Disclosure",
            "D": "Denial of Service",
            "E": "Elevation of Privilege",
        }

    def _init_resource_patterns(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Initialize threat patterns for different Azure resource types.
        Each pattern defines threats based on STRIDE methodology.
        """
        return {
            "Microsoft.Compute/virtualMachines": [
                {
                    "stride": "S",
                    "title": "VM Identity Spoofing",
                    "description": "Attacker may spoof VM identity to gain unauthorized access to connected resources.",
                    "severity": "High",
                    "impact": "Unauthorized access to VM and connected resources",
                    "likelihood": "Medium"
                },
                {
                    "stride": "T",
                    "title": "VM Configuration Tampering",
                    "description": "VM configuration, OS, or installed software could be tampered with by malicious actors.",
                    "severity": "High",
                    "impact": "System compromise and data integrity loss",
                    "likelihood": "Medium"
                },
                {
                    "stride": "R",
                    "title": "VM Activity Repudiation",
                    "description": "Insufficient logging may allow repudiation of malicious activities performed on the VM.",
                    "severity": "Medium",
                    "impact": "Inability to trace malicious activities",
                    "likelihood": "High"
                },
                {
                    "stride": "I",
                    "title": "VM Data Disclosure",
                    "description": "Sensitive data on VM disks or in memory could be disclosed through unauthorized access.",
                    "severity": "High",
                    "impact": "Exposure of sensitive data",
                    "likelihood": "Medium"
                },
                {
                    "stride": "D",
                    "title": "VM Availability Attack",
                    "description": "VM could be subject to DoS attacks affecting service availability.",
                    "severity": "Medium",
                    "impact": "Service disruption",
                    "likelihood": "High"
                },
                {
                    "stride": "E",
                    "title": "VM Privilege Escalation",
                    "description": "Local privilege escalation could allow attackers to gain higher privileges on the VM.",
                    "severity": "High",
                    "impact": "Full system compromise",
                    "likelihood": "Medium"
                }
            ],
            "Microsoft.Storage/storageAccounts": [
                {
                    "stride": "S",
                    "title": "Storage Account Identity Spoofing",
                    "description": "Attacker may spoof storage account identity using stolen keys or tokens.",
                    "severity": "High",
                    "impact": "Unauthorized data access",
                    "likelihood": "Medium"
                },
                {
                    "stride": "T",
                    "title": "Data Tampering in Storage",
                    "description": "Stored data could be tampered with if proper access controls are not in place.",
                    "severity": "High",
                    "impact": "Data integrity compromise",
                    "likelihood": "Low"
                },
                {
                    "stride": "I",
                    "title": "Storage Data Disclosure",
                    "description": "Sensitive data in storage could be disclosed through misconfigured access policies.",
                    "severity": "Critical",
                    "impact": "Massive data breach",
                    "likelihood": "Medium"
                },
                {
                    "stride": "D",
                    "title": "Storage Service Denial",
                    "description": "Storage service could be overwhelmed or made unavailable through various attack vectors.",
                    "severity": "Medium",
                    "impact": "Service disruption",
                    "likelihood": "Medium"
                }
            ],
            "Microsoft.Sql/servers": [
                {
                    "stride": "S",
                    "title": "SQL Server Identity Spoofing",
                    "description": "Attacker may spoof SQL Server identity using compromised credentials.",
                    "severity": "High",
                    "impact": "Unauthorized database access",
                    "likelihood": "Medium"
                },
                {
                    "stride": "T",
                    "title": "Database Data Tampering",
                    "description": "Database data could be tampered with through SQL injection or privilege escalation.",
                    "severity": "Critical",
                    "impact": "Data integrity compromise",
                    "likelihood": "High"
                },
                {
                    "stride": "I",
                    "title": "Database Data Disclosure",
                    "description": "Sensitive database information could be disclosed through various attack vectors.",
                    "severity": "Critical",
                    "impact": "Sensitive data exposure",
                    "likelihood": "High"
                },
                {
                    "stride": "E",
                    "title": "SQL Server Privilege Escalation",
                    "description": "Attackers may escalate privileges within the SQL Server environment.",
                    "severity": "High",
                    "impact": "Full database server compromise",
                    "likelihood": "Medium"
                }
            ],
            "Microsoft.Web/sites": [
                {
                    "stride": "S",
                    "title": "Web App Identity Spoofing",
                    "description": "Attacker may spoof web application identity through session hijacking or credential theft.",
                    "severity": "High",
                    "impact": "Unauthorized application access",
                    "likelihood": "High"
                },
                {
                    "stride": "T",
                    "title": "Web App Code Tampering",
                    "description": "Application code or configuration could be tampered with through various attack vectors.",
                    "severity": "High",
                    "impact": "Application compromise",
                    "likelihood": "Medium"
                },
                {
                    "stride": "I",
                    "title": "Web App Data Disclosure",
                    "description": "Sensitive application data could be disclosed through vulnerabilities or misconfigurations.",
                    "severity": "High",
                    "impact": "Data exposure",
                    "likelihood": "High"
                },
                {
                    "stride": "D",
                    "title": "Web App Service Denial",
                    "description": "Web application could be subject to DoS attacks affecting availability.",
                    "severity": "Medium",
                    "impact": "Service disruption",
                    "likelihood": "High"
                },
                {
                    "stride": "E",
                    "title": "Web App Privilege Escalation",
                    "description": "Attackers may escalate privileges within the web application environment.",
                    "severity": "High",
                    "impact": "Full application compromise",
                    "likelihood": "Medium"
                }
            ],
            "Microsoft.Network/virtualNetworks": [
                {
                    "stride": "S",
                    "title": "Network Identity Spoofing",
                    "description": "Attacker may spoof network identities through ARP or DNS spoofing attacks.",
                    "severity": "Medium",
                    "impact": "Network traffic interception",
                    "likelihood": "Medium"
                },
                {
                    "stride": "T",
                    "title": "Network Traffic Tampering",
                    "description": "Network traffic could be tampered with if not properly secured in transit.",
                    "severity": "High",
                    "impact": "Data integrity compromise",
                    "likelihood": "Low"
                },
                {
                    "stride": "I",
                    "title": "Network Traffic Disclosure",
                    "description": "Network traffic could be intercepted and analyzed by unauthorized parties.",
                    "severity": "High",
                    "impact": "Sensitive data exposure",
                    "likelihood": "Medium"
                },
                {
                    "stride": "D",
                    "title": "Network Service Denial",
                    "description": "Network services could be overwhelmed or made unavailable through DoS attacks.",
                    "severity": "Medium",
                    "impact": "Network service disruption",
                    "likelihood": "Medium"
                }
            ],
            "Microsoft.KeyVault/vaults": [
                {
                    "stride": "S",
                    "title": "Key Vault Identity Spoofing",
                    "description": "Attacker may spoof Key Vault identity using compromised service principals or managed identities.",
                    "severity": "Critical",
                    "impact": "Unauthorized access to secrets",
                    "likelihood": "Low"
                },
                {
                    "stride": "I",
                    "title": "Key Vault Secret Disclosure",
                    "description": "Secrets, keys, and certificates could be disclosed through unauthorized access.",
                    "severity": "Critical",
                    "impact": "Exposure of sensitive secrets",
                    "likelihood": "Medium"
                },
                {
                    "stride": "E",
                    "title": "Key Vault Privilege Escalation",
                    "description": "Attackers may escalate privileges to gain broader access to Key Vault resources.",
                    "severity": "High",
                    "impact": "Full Key Vault compromise",
                    "likelihood": "Low"
                }
            ]
        }

    def enumerate_resource_threats(
        self, resource: Dict[str, Any], logger: Optional[logging.Logger] = None
    ) -> List[Dict[str, Any]]:
        """
        Enumerate threats for a specific Azure resource based on its type and configuration.
        
        Args:
            resource: Azure resource dictionary with type, properties, etc.
            logger: Optional logger for error reporting.
            
        Returns:
            List of threat dictionaries.
        """
        if logger is None:
            logger = logging.getLogger("ThreatEnumerator")
            
        resource_type = resource.get("type", "")
        resource_id = resource.get("id", "")
        resource_name = resource.get("name", "Unknown")
        
        threats = []
        
        # Get threat patterns for this resource type
        patterns = self.resource_threat_patterns.get(resource_type, [])
        
        for pattern in patterns:
            threat_id = str(uuid.uuid4())
            threat = {
                "id": threat_id,
                "title": pattern["title"],
                "description": pattern["description"],
                "severity": pattern["severity"],
                "category": self.stride_categories.get(pattern["stride"], "Unknown"),
                "stride": pattern["stride"],
                "element": resource_name,
                "resource_id": resource_id,
                "resource_type": resource_type,
                "impact": pattern.get("impact", "Unknown"),
                "likelihood": pattern.get("likelihood", "Unknown"),
                "raw": pattern
            }
            
            # Enhance threat based on specific resource configuration
            threat = self._enhance_threat_with_config(threat, resource, logger)
            threats.append(threat)
            
        # Add generic threats that apply to all resources
        generic_threats = self._get_generic_threats(resource, logger)
        threats.extend(generic_threats)
        
        logger.info(f"Enumerated {len(threats)} threats for {resource_type} '{resource_name}'")
        return threats
        
    def _enhance_threat_with_config(
        self, threat: Dict[str, Any], resource: Dict[str, Any], logger: logging.Logger
    ) -> Dict[str, Any]:
        """
        Enhance threat assessment based on specific resource configuration.
        """
        try:
            resource_type = resource.get("type", "")
            properties = resource.get("properties", {})
            
            # Enhance VM threats based on configuration
            if resource_type == "Microsoft.Compute/virtualMachines":
                # Check for encryption
                if not self._has_disk_encryption(properties):
                    if threat["stride"] == "I":
                        threat["severity"] = "Critical"
                        threat["description"] += " Disk encryption is not enabled, increasing data exposure risk."
                        
                # Check for security monitoring
                if not self._has_security_monitoring(properties):
                    if threat["stride"] == "R":
                        threat["severity"] = "High"
                        threat["description"] += " Security monitoring extensions are not detected."
            
            # Enhance storage account threats
            elif resource_type == "Microsoft.Storage/storageAccounts":
                # Check for public access
                if self._allows_public_access(properties):
                    if threat["stride"] == "I":
                        threat["severity"] = "Critical"
                        threat["likelihood"] = "High"
                        threat["description"] += " Public access is enabled, significantly increasing exposure risk."
                        
                # Check for encryption
                if not self._has_storage_encryption(properties):
                    if threat["stride"] in ["I", "T"]:
                        threat["severity"] = "High"
                        threat["description"] += " Storage encryption may not be properly configured."
            
            # Enhance SQL server threats
            elif resource_type == "Microsoft.Sql/servers":
                # Check for firewall rules
                if self._has_open_firewall(properties):
                    if threat["stride"] in ["S", "I", "T"]:
                        threat["severity"] = "Critical"
                        threat["likelihood"] = "High"
                        threat["description"] += " Firewall allows broad access, increasing attack surface."
                        
        except Exception as e:
            logger.warning(f"Failed to enhance threat with config: {e}")
            
        return threat
    
    def _get_generic_threats(
        self, resource: Dict[str, Any], logger: logging.Logger
    ) -> List[Dict[str, Any]]:
        """
        Get generic threats that apply to all Azure resources.
        """
        resource_id = resource.get("id", "")
        resource_name = resource.get("name", "Unknown")
        resource_type = resource.get("type", "")
        
        generic_threats = [
            {
                "id": str(uuid.uuid4()),
                "title": "Insufficient Access Controls",
                "description": "Resource may have overly permissive RBAC assignments or access policies.",
                "severity": "Medium",
                "category": "Elevation of Privilege",
                "stride": "E",
                "element": resource_name,
                "resource_id": resource_id,
                "resource_type": resource_type,
                "impact": "Unauthorized access to resource",
                "likelihood": "Medium",
                "raw": {}
            },
            {
                "id": str(uuid.uuid4()),
                "title": "Inadequate Monitoring",
                "description": "Resource may lack sufficient logging and monitoring to detect security incidents.",
                "severity": "Medium",
                "category": "Repudiation",
                "stride": "R",
                "element": resource_name,
                "resource_id": resource_id,
                "resource_type": resource_type,
                "impact": "Inability to detect or investigate security incidents",
                "likelihood": "High",
                "raw": {}
            }
        ]
        
        return generic_threats
    
    def _has_disk_encryption(self, properties: Dict[str, Any]) -> bool:
        """
        Check if VM has disk encryption enabled.
        """
        storage_profile = properties.get("storageProfile", {})
        os_disk = storage_profile.get("osDisk", {})
        encryption_settings = os_disk.get("encryptionSettings", {})
        return encryption_settings.get("enabled", False)
    
    def _has_security_monitoring(self, properties: Dict[str, Any]) -> bool:
        """
        Check if VM has security monitoring extensions.
        """
        # This would typically check for extensions like Microsoft Monitoring Agent
        # For now, we'll assume false to encourage security monitoring
        return False
    
    def _allows_public_access(self, properties: Dict[str, Any]) -> bool:
        """
        Check if storage account allows public access.
        """
        public_access = properties.get("allowBlobPublicAccess", False)
        network_access = properties.get("networkAcls", {}).get("defaultAction", "Allow")
        return public_access or network_access == "Allow"
    
    def _has_storage_encryption(self, properties: Dict[str, Any]) -> bool:
        """
        Check if storage account has encryption enabled.
        """
        encryption = properties.get("encryption", {})
        services = encryption.get("services", {})
        blob_encryption = services.get("blob", {}).get("enabled", False)
        file_encryption = services.get("file", {}).get("enabled", False)
        return blob_encryption and file_encryption
    
    def _has_open_firewall(self, properties: Dict[str, Any]) -> bool:
        """
        Check if SQL server has overly permissive firewall rules.
        """
        # This would check for firewall rules that allow 0.0.0.0-255.255.255.255
        # For demonstration, we'll check for public network access
        public_network_access = properties.get("publicNetworkAccess", "Enabled")
        return public_network_access == "Enabled"


def enumerate_threats(
    resources_or_tmt_output: Any, logger: Optional[logging.Logger] = None
) -> List[Dict[str, Any]]:
    """
    Enumerate threats for Azure resources using STRIDE methodology.
    
    Args:
        resources_or_tmt_output: List of Azure resources or legacy TMT output
        logger: Optional logger for error reporting
        
    Returns:
        List of structured threat dictionaries
    """
    if logger is None:
        logger = logging.getLogger("ThreatEnumerator")
        
    enumerator = STRIDEThreatEnumerator()
    all_threats = []
    
    try:
        if not resources_or_tmt_output:
            logger.warning("No resources provided for threat enumeration")
            return []
        
        # Handle list of Azure resources
        if isinstance(resources_or_tmt_output, list):
            for resource in resources_or_tmt_output:
                if isinstance(resource, dict) and "type" in resource:
                    # This is an Azure resource
                    resource_threats = enumerator.enumerate_resource_threats(resource, logger)
                    all_threats.extend(resource_threats)
                else:
                    # This might be legacy TMT output - handle it
                    logger.info("Processing legacy TMT-style output")
                    legacy_threat = {
                        "id": resource.get("id", str(uuid.uuid4())),
                        "title": resource.get("title", "Unknown Threat"),
                        "description": resource.get("description", ""),
                        "severity": resource.get("severity", "Medium"),
                        "category": resource.get("category", ""),
                        "stride": resource.get("stride", ""),
                        "element": resource.get("element", ""),
                        "resource_id": "",
                        "resource_type": "",
                        "raw": resource
                    }
                    all_threats.append(legacy_threat)
        
        # Deduplicate threats by title and description
        seen = set()
        unique_threats = []
        for threat in all_threats:
            dedup_key = (threat["title"].lower().strip(), threat["description"].lower().strip())
            if dedup_key not in seen:
                seen.add(dedup_key)
                unique_threats.append(threat)
                
        logger.info(f"Enumerated {len(unique_threats)} unique threats from {len(resources_or_tmt_output)} resources")
        return unique_threats
        
    except Exception as e:
        logger.error(f"Threat enumeration failed: {e}")
        return []