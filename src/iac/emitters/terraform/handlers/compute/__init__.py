"""Compute handlers for Terraform emission."""

from .disks import ManagedDiskHandler, SnapshotHandler
from .ssh_public_key import SSHPublicKeyHandler
from .virtual_machine import VirtualMachineHandler
from .vm_extensions import VMExtensionHandler, VMRunCommandHandler
from .vm_image import VMImageHandler

__all__ = [
    "ManagedDiskHandler",
    "SSHPublicKeyHandler",
    "SnapshotHandler",
    "VMExtensionHandler",
    "VMImageHandler",
    "VMRunCommandHandler",
    "VirtualMachineHandler",
]
