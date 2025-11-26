"""Miscellaneous resource handlers for Terraform emission.

This module contains handlers for various Azure resource types
that don't fit into other categories.
"""

from .app_config import AppConfigurationHandler
from .data_factory import DataFactoryHandler
from .databricks import DatabricksWorkspaceHandler
from .dns_zone import DNSZoneHandler, PrivateDNSZoneHandler
from .eventhub import EventHubHandler, EventHubNamespaceHandler
from .recovery_vault import RecoveryServicesVaultHandler
from .redis import RedisCacheHandler
from .resource_group import ResourceGroupHandler
from .search_service import SearchServiceHandler
from .servicebus import ServiceBusNamespaceHandler, ServiceBusQueueHandler
from .waf_policy import WAFPolicyHandler

__all__ = [
    "AppConfigurationHandler",
    "DNSZoneHandler",
    "DataFactoryHandler",
    "DatabricksWorkspaceHandler",
    "EventHubHandler",
    "EventHubNamespaceHandler",
    "PrivateDNSZoneHandler",
    "RecoveryServicesVaultHandler",
    "RedisCacheHandler",
    "ResourceGroupHandler",
    "SearchServiceHandler",
    "ServiceBusNamespaceHandler",
    "ServiceBusQueueHandler",
    "WAFPolicyHandler",
]
