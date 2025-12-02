"""Network handlers for Terraform emission."""

from .application_gateway import ApplicationGatewayHandler
from .bastion import BastionHostHandler
from .load_balancer import LoadBalancerHandler
from .nat_gateway import NATGatewayHandler
from .nic import NetworkInterfaceHandler
from .nsg import NetworkSecurityGroupHandler
from .nsg_associations import NSGAssociationHandler
from .public_ip import PublicIPHandler
from .route_table import RouteTableHandler
from .subnet import SubnetHandler
from .vnet import VirtualNetworkHandler

__all__ = [
    "ApplicationGatewayHandler",
    "BastionHostHandler",
    "LoadBalancerHandler",
    "NATGatewayHandler",
    "NetworkInterfaceHandler",
    "NetworkSecurityGroupHandler",
    "NSGAssociationHandler",
    "PublicIPHandler",
    "RouteTableHandler",
    "SubnetHandler",
    "VirtualNetworkHandler",
]
