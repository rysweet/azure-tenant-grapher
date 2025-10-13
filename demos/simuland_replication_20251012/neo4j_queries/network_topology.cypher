// Query: Network topology visualization and analysis
// Purpose: Explore network relationships and architecture
// Usage: Execute in Neo4j Browser or cypher-shell

// Variables to set:
// :param tenant_id => 'YOUR_TENANT_ID' (source or target)

// Complete network topology overview
MATCH (vnet:Resource {type: 'Microsoft.Network/virtualNetworks'})
WHERE vnet.tenant_id = $tenant_id
OPTIONAL MATCH (vnet)-[:CONTAINS]->(subnet:Resource)
OPTIONAL MATCH (subnet)-[:CONTAINS]->(nic:Resource)
OPTIONAL MATCH (nic)-[:CONNECTED_TO]->(vm:Resource)
RETURN
  vnet.name AS vnet_name,
  vnet.properties.addressSpace.addressPrefixes[0] AS vnet_cidr,
  count(distinct subnet) AS subnet_count,
  count(distinct nic) AS nic_count,
  count(distinct vm) AS vm_count,
  collect(distinct subnet.properties.addressPrefix) AS subnet_cidrs
ORDER BY vnet.name;

// Detailed subnet analysis
MATCH (vnet:Resource {type: 'Microsoft.Network/virtualNetworks'})-[:CONTAINS]->(subnet:Resource)
WHERE vnet.tenant_id = $tenant_id
OPTIONAL MATCH (subnet)-[:CONTAINS]->(nic:Resource)
OPTIONAL MATCH (nic)-[:CONNECTED_TO]->(vm:Resource)
RETURN
  vnet.name AS vnet_name,
  subnet.name AS subnet_name,
  subnet.properties.addressPrefix AS subnet_cidr,
  count(distinct nic) AS nic_count,
  count(distinct vm) AS vm_count,
  collect(distinct vm.name) AS vms_in_subnet
ORDER BY vnet.name, subnet.name;

// VNet peering relationships (if any)
MATCH (vnet1:Resource {type: 'Microsoft.Network/virtualNetworks'})-[r:PEERED_TO]->(vnet2:Resource)
WHERE vnet1.tenant_id = $tenant_id
RETURN
  vnet1.name AS vnet1_name,
  vnet2.name AS vnet2_name,
  type(r) AS relationship,
  properties(r) AS peering_properties
ORDER BY vnet1.name;

// Network Security Group associations
MATCH (nsg:Resource {type: 'Microsoft.Network/networkSecurityGroups'})
WHERE nsg.tenant_id = $tenant_id
OPTIONAL MATCH (nsg)-[:ATTACHED_TO]->(target)
RETURN
  nsg.name AS nsg_name,
  count(distinct target) AS attached_to_count,
  collect(distinct target.type) AS attached_to_types,
  collect(distinct target.name) AS attached_to_names
ORDER BY nsg.name;

// NSG rules analysis
MATCH (nsg:Resource {type: 'Microsoft.Network/networkSecurityGroups'})
WHERE nsg.tenant_id = $tenant_id
UNWIND nsg.properties.securityRules AS rule
RETURN
  nsg.name AS nsg_name,
  rule.name AS rule_name,
  rule.properties.priority AS priority,
  rule.properties.direction AS direction,
  rule.properties.access AS access,
  rule.properties.protocol AS protocol,
  rule.properties.sourcePortRange AS source_port,
  rule.properties.destinationPortRange AS dest_port,
  rule.properties.sourceAddressPrefix AS source_address,
  rule.properties.destinationAddressPrefix AS dest_address
ORDER BY nsg.name, priority;

// IP address allocation summary
MATCH (vnet:Resource {type: 'Microsoft.Network/virtualNetworks'})-[:CONTAINS]->(subnet:Resource)
WHERE vnet.tenant_id = $tenant_id
MATCH (subnet)-[:CONTAINS]->(nic:Resource)
RETURN
  vnet.name AS vnet_name,
  subnet.name AS subnet_name,
  subnet.properties.addressPrefix AS subnet_cidr,
  collect(nic.properties.ipConfigurations[0].properties.privateIPAddress) AS allocated_ips,
  size(collect(nic.properties.ipConfigurations[0].properties.privateIPAddress)) AS ip_count
ORDER BY vnet.name, subnet.name;

// Public IP addresses (if any)
MATCH (pip:Resource {type: 'Microsoft.Network/publicIPAddresses'})
WHERE pip.tenant_id = $tenant_id
OPTIONAL MATCH (pip)<-[:USES]-(nic:Resource)
OPTIONAL MATCH (nic)-[:CONNECTED_TO]->(vm:Resource)
RETURN
  pip.name AS public_ip_name,
  pip.properties.ipAddress AS ip_address,
  pip.properties.publicIPAllocationMethod AS allocation_method,
  coalesce(vm.name, 'UNASSIGNED') AS associated_vm
ORDER BY pip.name;

// Network interface details with all associations
MATCH (nic:Resource {type: 'Microsoft.Network/networkInterfaces'})
WHERE nic.tenant_id = $tenant_id
OPTIONAL MATCH (subnet:Resource)-[:CONTAINS]->(nic)
OPTIONAL MATCH (vnet:Resource)-[:CONTAINS]->(subnet)
OPTIONAL MATCH (nic)-[:CONNECTED_TO]->(vm:Resource)
OPTIONAL MATCH (nsg:Resource)-[:ATTACHED_TO]->(nic)
RETURN
  nic.name AS nic_name,
  coalesce(vm.name, 'UNASSIGNED') AS vm_name,
  coalesce(vnet.name, 'UNKNOWN') AS vnet_name,
  coalesce(subnet.name, 'UNKNOWN') AS subnet_name,
  nic.properties.ipConfigurations[0].properties.privateIPAddress AS private_ip,
  nic.properties.ipConfigurations[0].properties.privateIPAllocationMethod AS ip_allocation,
  coalesce(nsg.name, 'NONE') AS nsg_name
ORDER BY vnet.name, subnet.name, nic.name;

// Subnet address space utilization
MATCH (vnet:Resource {type: 'Microsoft.Network/virtualNetworks'})-[:CONTAINS]->(subnet:Resource)
WHERE vnet.tenant_id = $tenant_id
OPTIONAL MATCH (subnet)-[:CONTAINS]->(nic:Resource)
WITH
  vnet.name AS vnet_name,
  subnet.name AS subnet_name,
  subnet.properties.addressPrefix AS subnet_cidr,
  count(distinct nic) AS nic_count
RETURN
  vnet_name,
  subnet_name,
  subnet_cidr,
  nic_count,
  // Calculate theoretical capacity (rough estimate, doesn't account for Azure reserved IPs)
  CASE
    WHEN subnet_cidr CONTAINS '/24' THEN 254
    WHEN subnet_cidr CONTAINS '/25' THEN 126
    WHEN subnet_cidr CONTAINS '/26' THEN 62
    WHEN subnet_cidr CONTAINS '/27' THEN 30
    WHEN subnet_cidr CONTAINS '/28' THEN 14
    ELSE 0
  END AS theoretical_capacity,
  CASE
    WHEN subnet_cidr CONTAINS '/24' THEN toFloat(nic_count) / 254 * 100
    WHEN subnet_cidr CONTAINS '/25' THEN toFloat(nic_count) / 126 * 100
    WHEN subnet_cidr CONTAINS '/26' THEN toFloat(nic_count) / 62 * 100
    ELSE 0.0
  END AS utilization_percent
ORDER BY vnet_name, subnet_name;

// Network isolation analysis - which VMs can communicate
MATCH (vm1:Resource {type: 'Microsoft.Compute/virtualMachines'})
WHERE vm1.tenant_id = $tenant_id
MATCH (nic1:Resource)-[:CONNECTED_TO]->(vm1)
MATCH (subnet1:Resource)-[:CONTAINS]->(nic1)
MATCH (vnet1:Resource)-[:CONTAINS]->(subnet1)
MATCH (vm2:Resource {type: 'Microsoft.Compute/virtualMachines'})
WHERE vm2.tenant_id = $tenant_id AND vm1.name < vm2.name
MATCH (nic2:Resource)-[:CONNECTED_TO]->(vm2)
MATCH (subnet2:Resource)-[:CONTAINS]->(nic2)
MATCH (vnet2:Resource)-[:CONTAINS]->(subnet2)
RETURN
  vm1.name AS vm1,
  vm2.name AS vm2,
  vnet1.name AS vnet1,
  vnet2.name AS vnet2,
  CASE
    WHEN vnet1.name = vnet2.name THEN 'SAME_VNET'
    ELSE 'DIFFERENT_VNET'
  END AS network_isolation
ORDER BY network_isolation, vm1, vm2;

// Full network visualization paths (for Neo4j Browser visualization)
MATCH path = (vnet:Resource {type: 'Microsoft.Network/virtualNetworks'})-[:CONTAINS*]->(leaf)
WHERE vnet.tenant_id = $tenant_id
  AND NOT (leaf)-[:CONTAINS]->()
RETURN path
LIMIT 100;

// Network dependency graph for a specific VM
// Change 'WECServer' to any VM name
MATCH path = (vm:Resource {name: 'WECServer', type: 'Microsoft.Compute/virtualMachines'})<-[:CONNECTED_TO|CONTAINS*]-(network_resource)
WHERE vm.tenant_id = $tenant_id
  AND network_resource.type IN [
    'Microsoft.Network/networkInterfaces',
    'Microsoft.Network/virtualNetworks/subnets',
    'Microsoft.Network/virtualNetworks',
    'Microsoft.Network/networkSecurityGroups'
  ]
RETURN path;

// Find isolated subnets (no VMs)
MATCH (vnet:Resource {type: 'Microsoft.Network/virtualNetworks'})-[:CONTAINS]->(subnet:Resource)
WHERE vnet.tenant_id = $tenant_id
OPTIONAL MATCH (subnet)-[:CONTAINS]->(nic:Resource)-[:CONNECTED_TO]->(vm:Resource)
WITH vnet, subnet, count(vm) AS vm_count
WHERE vm_count = 0
RETURN
  vnet.name AS vnet_name,
  subnet.name AS subnet_name,
  subnet.properties.addressPrefix AS subnet_cidr,
  'ISOLATED' AS status
ORDER BY vnet.name, subnet.name;
