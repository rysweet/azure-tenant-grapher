// Query: Compare source vs target resources for fidelity measurement
// Purpose: Quantify replication accuracy
// Usage: Execute in Neo4j Browser or cypher-shell

// Variables to set:
// :param source_tenant_id => 'YOUR_SOURCE_TENANT_ID'
// :param target_tenant_id => 'YOUR_TARGET_TENANT_ID'

// Compare resource counts by type
MATCH (source:Resource)
WHERE source.tenant_id = $source_tenant_id
WITH source.type AS resource_type, count(*) AS source_count
OPTIONAL MATCH (target:Resource)
WHERE target.tenant_id = $target_tenant_id AND target.type = resource_type
WITH resource_type, source_count, count(target) AS target_count
RETURN
  resource_type,
  source_count,
  target_count,
  CASE
    WHEN source_count = 0 THEN 1.0
    ELSE toFloat(target_count) / source_count
  END AS fidelity
ORDER BY resource_type;

// Find resources in source but not in target (missing resources)
MATCH (source:Resource)
WHERE source.tenant_id = $source_tenant_id
OPTIONAL MATCH (target:Resource {name: source.name, type: source.type})
WHERE target.tenant_id = $target_tenant_id
WITH source, target
WHERE target IS NULL
RETURN
  source.type AS resource_type,
  source.name AS resource_name,
  'MISSING' AS status
ORDER BY source.type, source.name;

// Find resources in target but not in source (extra resources)
MATCH (target:Resource)
WHERE target.tenant_id = $target_tenant_id
OPTIONAL MATCH (source:Resource {name: target.name, type: target.type})
WHERE source.tenant_id = $source_tenant_id
WITH source, target
WHERE source IS NULL
RETURN
  target.type AS resource_type,
  target.name AS resource_name,
  'EXTRA' AS status
ORDER BY target.type, target.name;

// Compare VM configurations
MATCH (source_vm:Resource {type: 'Microsoft.Compute/virtualMachines'})
WHERE source_vm.tenant_id = $source_tenant_id
MATCH (target_vm:Resource {name: source_vm.name, type: 'Microsoft.Compute/virtualMachines'})
WHERE target_vm.tenant_id = $target_tenant_id
RETURN
  source_vm.name AS vm_name,
  source_vm.properties.hardwareProfile.vmSize AS source_vm_size,
  target_vm.properties.hardwareProfile.vmSize AS target_vm_size,
  CASE
    WHEN source_vm.properties.hardwareProfile.vmSize = target_vm.properties.hardwareProfile.vmSize
    THEN 'MATCH'
    ELSE 'DIFFERENT'
  END AS vm_size_match,
  source_vm.properties.storageProfile.imageReference.sku AS source_os_sku,
  target_vm.properties.storageProfile.imageReference.sku AS target_os_sku,
  CASE
    WHEN source_vm.properties.storageProfile.imageReference.sku = target_vm.properties.storageProfile.imageReference.sku
    THEN 'MATCH'
    ELSE 'DIFFERENT'
  END AS os_sku_match
ORDER BY vm_name;

// Compare VNet configurations
MATCH (source_vnet:Resource {type: 'Microsoft.Network/virtualNetworks'})
WHERE source_vnet.tenant_id = $source_tenant_id
MATCH (target_vnet:Resource {name: source_vnet.name, type: 'Microsoft.Network/virtualNetworks'})
WHERE target_vnet.tenant_id = $target_tenant_id
RETURN
  source_vnet.name AS vnet_name,
  source_vnet.properties.addressSpace.addressPrefixes[0] AS source_address_space,
  target_vnet.properties.addressSpace.addressPrefixes[0] AS target_address_space,
  CASE
    WHEN source_vnet.properties.addressSpace.addressPrefixes[0] = target_vnet.properties.addressSpace.addressPrefixes[0]
    THEN 'MATCH'
    ELSE 'DIFFERENT'
  END AS address_space_match
ORDER BY vnet_name;

// Compare subnet configurations
MATCH (source_vnet:Resource {type: 'Microsoft.Network/virtualNetworks'})-[:CONTAINS]->(source_subnet:Resource)
WHERE source_vnet.tenant_id = $source_tenant_id
MATCH (target_vnet:Resource {name: source_vnet.name})-[:CONTAINS]->(target_subnet:Resource {name: source_subnet.name})
WHERE target_vnet.tenant_id = $target_tenant_id
RETURN
  source_vnet.name AS vnet_name,
  source_subnet.name AS subnet_name,
  source_subnet.properties.addressPrefix AS source_cidr,
  target_subnet.properties.addressPrefix AS target_cidr,
  CASE
    WHEN source_subnet.properties.addressPrefix = target_subnet.properties.addressPrefix
    THEN 'MATCH'
    ELSE 'DIFFERENT'
  END AS cidr_match
ORDER BY vnet_name, subnet_name;

// Compare relationship counts
MATCH (source:Resource)-[r_source]->()
WHERE source.tenant_id = $source_tenant_id
WITH type(r_source) AS relationship_type, count(*) AS source_count
OPTIONAL MATCH (target:Resource)-[r_target]->()
WHERE target.tenant_id = $target_tenant_id AND type(r_target) = relationship_type
WITH relationship_type, source_count, count(r_target) AS target_count
RETURN
  relationship_type,
  source_count,
  target_count,
  CASE
    WHEN source_count = 0 THEN 1.0
    ELSE toFloat(target_count) / source_count
  END AS relationship_fidelity
ORDER BY relationship_type;

// Overall fidelity summary
MATCH (source:Resource)
WHERE source.tenant_id = $source_tenant_id
WITH count(source) AS total_source_resources
MATCH (target:Resource)
WHERE target.tenant_id = $target_tenant_id
WITH total_source_resources, count(target) AS total_target_resources
MATCH (source:Resource)
WHERE source.tenant_id = $source_tenant_id
OPTIONAL MATCH (target:Resource {name: source.name, type: source.type})
WHERE target.tenant_id = $target_tenant_id
WITH total_source_resources, total_target_resources, count(target) AS matched_resources
RETURN
  total_source_resources,
  total_target_resources,
  matched_resources,
  toFloat(matched_resources) / total_source_resources AS resource_count_fidelity;

// Network topology comparison (VM to VNet mapping)
MATCH (source_vm:Resource {type: 'Microsoft.Compute/virtualMachines'})
WHERE source_vm.tenant_id = $source_tenant_id
MATCH (source_nic:Resource)-[:CONNECTED_TO]->(source_vm)
MATCH (source_subnet:Resource)-[:CONTAINS]->(source_nic)
MATCH (source_vnet:Resource)-[:CONTAINS]->(source_subnet)
OPTIONAL MATCH (target_vm:Resource {name: source_vm.name, type: 'Microsoft.Compute/virtualMachines'})
WHERE target_vm.tenant_id = $target_tenant_id
OPTIONAL MATCH (target_nic:Resource)-[:CONNECTED_TO]->(target_vm)
OPTIONAL MATCH (target_subnet:Resource)-[:CONTAINS]->(target_nic)
OPTIONAL MATCH (target_vnet:Resource)-[:CONTAINS]->(target_subnet)
RETURN
  source_vm.name AS vm_name,
  source_vnet.name AS source_vnet,
  target_vnet.name AS target_vnet,
  CASE
    WHEN source_vnet.name = target_vnet.name THEN 'MATCH'
    WHEN target_vnet IS NULL THEN 'MISSING'
    ELSE 'DIFFERENT'
  END AS vnet_match
ORDER BY vm_name;
