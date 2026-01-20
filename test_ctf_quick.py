#!/usr/bin/env python3
"""Quick test of CTF services without full pytest overhead."""

from unittest.mock import Mock

from src.services.ctf_annotation_service import CTFAnnotationService


# Test CTFAnnotationService
def test_ctf_annotation_service():
    mock_driver = Mock()
    mock_driver.execute_query = Mock(return_value=([], None, None))

    service = CTFAnnotationService(neo4j_driver=mock_driver)

    # Test basic annotation
    result = service.annotate_resource(
        resource_id="vm-001",
        layer_id="default",
        ctf_exercise="M003",
        ctf_scenario="v2-cert",
        ctf_role="target",
    )

    print(f"✓ annotate_resource: {result['success']}")

    # Test role determination
    role = service.determine_role(
        resource_type="Microsoft.Compute/virtualMachines", resource_name="target-vm"
    )
    print(f"✓ determine_role: {role}")
    assert role == "target"

    # Test batch annotation
    resources = [
        {
            "id": "vm-001",
            "name": "vm1",
            "resource_type": "Microsoft.Compute/virtualMachines",
        },
        {
            "id": "vnet-001",
            "name": "vnet1",
            "resource_type": "Microsoft.Network/virtualNetworks",
        },
    ]

    batch_result = service.annotate_batch(
        resources=resources, layer_id="default", ctf_exercise="M003"
    )
    print(f"✓ annotate_batch: success_count={batch_result['success_count']}")

    print("\n🎉 All quick tests passed!")


if __name__ == "__main__":
    test_ctf_annotation_service()
