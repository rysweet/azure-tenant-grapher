// Query: List all target (deployed) resources
// Purpose: Verify what was deployed in the target tenant
// Usage: Execute in Neo4j Browser or cypher-shell

// Variables to set:
// :param target_tenant_id => 'YOUR_TARGET_TENANT_ID'

// List all deployed VMs
MATCH (vm:Resource {type: 'Microsoft.Compute/virtualMachines'})
WHERE vm.tenant_id = $target_tenant_id
RETURN
  vm.name AS vm_name,
  vm.properties.hardwareProfile.vmSize AS vm_size,
  vm.properties.provisioningState AS status,
  vm.location AS location
ORDER BY vm.name;

// List all deployed VNets
MATCH (vnet:Resource {type: 'Microsoft.Network/virtualNetworks'})
WHERE vnet.tenant_id = $target_tenant_id
RETURN
  vnet.name AS vnet_name,
  vnet.properties.addressSpace.addressPrefixes[0] AS address_space,
  vnet.properties.provisioningState AS status
ORDER BY vnet.name;

// List all deployed subnets
MATCH (vnet:Resource {type: 'Microsoft.Network/virtualNetworks'})-[:CONTAINS]->(subnet:Resource)
WHERE vnet.tenant_id = $target_tenant_id
RETURN
  vnet.name AS vnet_name,
  subnet.name AS subnet_name,
  subnet.properties.addressPrefix AS subnet_cidr,
  subnet.properties.provisioningState AS status
ORDER BY vnet.name, subnet.name;

// VM to VNet mapping
MATCH (vm:Resource {type: 'Microsoft.Compute/virtualMachines'})
WHERE vm.tenant_id = $target_tenant_id
MATCH (nic:Resource)-[:CONNECTED_TO]->(vm)
MATCH (subnet:Resource)-[:CONTAINS]->(nic)
MATCH (vnet:Resource)-[:CONTAINS]->(subnet)
RETURN
  vm.name AS vm_name,
  vnet.name AS vnet_name,
  subnet.name AS subnet_name,
  nic.properties.ipConfigurations[0].properties.privateIPAddress AS private_ip
ORDER BY vnet.name, vm.name;

// NSG associations in target
MATCH (nsg:Resource {type: 'Microsoft.Network/networkSecurityGroups'})
WHERE nsg.tenant_id = $target_tenant_id
OPTIONAL MATCH (nsg)-[:ATTACHED_TO]->(target)
RETURN
  nsg.name AS nsg_name,
  count(target) AS attached_to_count,
  collect(distinct labels(target)[0]) AS attached_to_labels
ORDER BY nsg.name;

// Count deployed resources by type
MATCH (r:Resource)
WHERE r.tenant_id = $target_tenant_id
RETURN
  r.type AS resource_type,
  count(*) AS count
ORDER BY count DESC;

// Verify provisioning states
MATCH (r:Resource)
WHERE r.tenant_id = $target_tenant_id
  AND r.properties.provisioningState IS NOT NULL
RETURN
  r.type AS resource_type,
  r.properties.provisioningState AS provisioning_state,
  count(*) AS count
ORDER BY r.type, provisioning_state;

// Find any failed deployments
MATCH (r:Resource)
WHERE r.tenant_id = $target_tenant_id
  AND r.properties.provisioningState <> 'Succeeded'
RETURN
  r.type AS resource_type,
  r.name AS resource_name,
  r.properties.provisioningState AS provisioning_state
ORDER BY r.type, r.name;
