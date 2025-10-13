// Query: List all source Simuland resources
// Purpose: Discover what resources exist in the source tenant
// Usage: Execute in Neo4j Browser or cypher-shell

// Variables to set:
// :param source_tenant_id => 'YOUR_SOURCE_TENANT_ID'

// List all VMs in source tenant
MATCH (vm:Resource {type: 'Microsoft.Compute/virtualMachines'})
WHERE vm.tenant_id = $source_tenant_id
RETURN
  vm.name AS vm_name,
  vm.properties.hardwareProfile.vmSize AS vm_size,
  vm.properties.osProfile.computerName AS computer_name,
  vm.location AS location
ORDER BY vm.name;

// List all VNets in source tenant
MATCH (vnet:Resource {type: 'Microsoft.Network/virtualNetworks'})
WHERE vnet.tenant_id = $source_tenant_id
RETURN
  vnet.name AS vnet_name,
  vnet.properties.addressSpace.addressPrefixes[0] AS address_space,
  vnet.location AS location
ORDER BY vnet.name;

// List all subnets with their VNets
MATCH (vnet:Resource {type: 'Microsoft.Network/virtualNetworks'})-[:CONTAINS]->(subnet:Resource {type: 'Microsoft.Network/virtualNetworks/subnets'})
WHERE vnet.tenant_id = $source_tenant_id
RETURN
  vnet.name AS vnet_name,
  subnet.name AS subnet_name,
  subnet.properties.addressPrefix AS subnet_cidr
ORDER BY vnet.name, subnet.name;

// List all NICs with their subnet associations
MATCH (subnet:Resource)-[:CONTAINS]->(nic:Resource {type: 'Microsoft.Network/networkInterfaces'})
WHERE subnet.tenant_id = $source_tenant_id
MATCH (vnet:Resource)-[:CONTAINS]->(subnet)
RETURN
  nic.name AS nic_name,
  vnet.name AS vnet_name,
  subnet.name AS subnet_name,
  nic.properties.ipConfigurations[0].properties.privateIPAddress AS private_ip
ORDER BY vnet.name, subnet.name;

// List all NSGs and their associations
MATCH (nsg:Resource {type: 'Microsoft.Network/networkSecurityGroups'})
WHERE nsg.tenant_id = $source_tenant_id
OPTIONAL MATCH (nsg)-[:ATTACHED_TO]->(target)
RETURN
  nsg.name AS nsg_name,
  count(target) AS attached_to_count,
  collect(distinct target.type) AS attached_to_types
ORDER BY nsg.name;

// Count resources by type
MATCH (r:Resource)
WHERE r.tenant_id = $source_tenant_id
RETURN
  r.type AS resource_type,
  count(*) AS count
ORDER BY count DESC;

// Full network topology visualization
MATCH path = (vnet:Resource {type: 'Microsoft.Network/virtualNetworks'})-[:CONTAINS*]->(leaf)
WHERE vnet.tenant_id = $source_tenant_id
  AND NOT (leaf)-[:CONTAINS]->()
RETURN path
LIMIT 100;
