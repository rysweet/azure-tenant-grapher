// Query: Detailed VM configuration exploration
// Purpose: Deep dive into VM settings and configurations
// Usage: Execute in Neo4j Browser or cypher-shell

// Variables to set:
// :param tenant_id => 'YOUR_TENANT_ID' (source or target)

// List all VMs with detailed hardware profiles
MATCH (vm:Resource {type: 'Microsoft.Compute/virtualMachines'})
WHERE vm.tenant_id = $tenant_id
RETURN
  vm.name AS vm_name,
  vm.properties.hardwareProfile.vmSize AS vm_size,
  vm.properties.osProfile.computerName AS computer_name,
  vm.properties.osProfile.adminUsername AS admin_username,
  vm.location AS location,
  vm.properties.provisioningState AS status
ORDER BY vm.name;

// VMs with OS image details
MATCH (vm:Resource {type: 'Microsoft.Compute/virtualMachines'})
WHERE vm.tenant_id = $tenant_id
RETURN
  vm.name AS vm_name,
  vm.properties.storageProfile.imageReference.publisher AS os_publisher,
  vm.properties.storageProfile.imageReference.offer AS os_offer,
  vm.properties.storageProfile.imageReference.sku AS os_sku,
  vm.properties.storageProfile.imageReference.version AS os_version,
  vm.properties.storageProfile.osDisk.osType AS os_type
ORDER BY vm.name;

// VMs with storage configuration
MATCH (vm:Resource {type: 'Microsoft.Compute/virtualMachines'})
WHERE vm.tenant_id = $tenant_id
RETURN
  vm.name AS vm_name,
  vm.properties.storageProfile.osDisk.name AS os_disk_name,
  vm.properties.storageProfile.osDisk.diskSizeGB AS os_disk_size_gb,
  vm.properties.storageProfile.osDisk.createOption AS os_disk_create_option,
  vm.properties.storageProfile.osDisk.caching AS os_disk_caching,
  size(vm.properties.storageProfile.dataDisks) AS data_disk_count
ORDER BY vm.name;

// VMs with data disk details
MATCH (vm:Resource {type: 'Microsoft.Compute/virtualMachines'})
WHERE vm.tenant_id = $tenant_id
  AND size(vm.properties.storageProfile.dataDisks) > 0
UNWIND vm.properties.storageProfile.dataDisks AS data_disk
RETURN
  vm.name AS vm_name,
  data_disk.lun AS disk_lun,
  data_disk.name AS disk_name,
  data_disk.diskSizeGB AS disk_size_gb,
  data_disk.caching AS disk_caching,
  data_disk.createOption AS disk_create_option
ORDER BY vm.name, disk_lun;

// VMs with network interface details
MATCH (vm:Resource {type: 'Microsoft.Compute/virtualMachines'})
WHERE vm.tenant_id = $tenant_id
MATCH (nic:Resource)-[:CONNECTED_TO]->(vm)
RETURN
  vm.name AS vm_name,
  nic.name AS nic_name,
  nic.properties.ipConfigurations[0].name AS ip_config_name,
  nic.properties.ipConfigurations[0].properties.privateIPAddress AS private_ip,
  nic.properties.ipConfigurations[0].properties.privateIPAllocationMethod AS ip_allocation_method,
  nic.properties.enableIPForwarding AS ip_forwarding_enabled,
  nic.properties.enableAcceleratedNetworking AS accelerated_networking
ORDER BY vm.name;

// VM to network topology mapping
MATCH (vm:Resource {type: 'Microsoft.Compute/virtualMachines'})
WHERE vm.tenant_id = $tenant_id
MATCH (nic:Resource)-[:CONNECTED_TO]->(vm)
MATCH (subnet:Resource)-[:CONTAINS]->(nic)
MATCH (vnet:Resource)-[:CONTAINS]->(subnet)
OPTIONAL MATCH (nsg:Resource)-[:ATTACHED_TO]->(nic)
RETURN
  vm.name AS vm_name,
  vm.properties.hardwareProfile.vmSize AS vm_size,
  vnet.name AS vnet_name,
  vnet.properties.addressSpace.addressPrefixes[0] AS vnet_cidr,
  subnet.name AS subnet_name,
  subnet.properties.addressPrefix AS subnet_cidr,
  nic.properties.ipConfigurations[0].properties.privateIPAddress AS private_ip,
  coalesce(nsg.name, 'NONE') AS nsg_name
ORDER BY vnet.name, subnet.name, vm.name;

// Group VMs by VM size
MATCH (vm:Resource {type: 'Microsoft.Compute/virtualMachines'})
WHERE vm.tenant_id = $tenant_id
WITH vm.properties.hardwareProfile.vmSize AS vm_size, collect(vm.name) AS vm_names
RETURN
  vm_size,
  size(vm_names) AS vm_count,
  vm_names
ORDER BY vm_count DESC, vm_size;

// Group VMs by OS type
MATCH (vm:Resource {type: 'Microsoft.Compute/virtualMachines'})
WHERE vm.tenant_id = $tenant_id
WITH
  vm.properties.storageProfile.imageReference.publisher AS publisher,
  vm.properties.storageProfile.imageReference.offer AS offer,
  vm.properties.storageProfile.imageReference.sku AS sku,
  collect(vm.name) AS vm_names
RETURN
  publisher + ' / ' + offer + ' / ' + sku AS os_image,
  size(vm_names) AS vm_count,
  vm_names
ORDER BY vm_count DESC;

// VMs with their complete dependency chain
MATCH path = (vm:Resource {type: 'Microsoft.Compute/virtualMachines'})<-[:CONNECTED_TO|CONTAINS*]-(dep)
WHERE vm.tenant_id = $tenant_id
  AND vm.name = 'WECServer'  // Change this to any VM name
RETURN
  vm.name AS vm_name,
  [node IN nodes(path) | node.type + ': ' + node.name] AS dependency_chain;

// VM resource utilization summary (if available)
MATCH (vm:Resource {type: 'Microsoft.Compute/virtualMachines'})
WHERE vm.tenant_id = $tenant_id
RETURN
  vm.name AS vm_name,
  vm.properties.hardwareProfile.vmSize AS vm_size,
  CASE vm.properties.hardwareProfile.vmSize
    WHEN 'Standard_B2s' THEN '2 vCPUs, 4 GB RAM'
    WHEN 'Standard_D2s_v3' THEN '2 vCPUs, 8 GB RAM'
    WHEN 'Standard_D4s_v3' THEN '4 vCPUs, 16 GB RAM'
    ELSE 'Unknown'
  END AS vm_resources,
  vm.properties.storageProfile.osDisk.diskSizeGB AS os_disk_gb,
  CASE
    WHEN size(vm.properties.storageProfile.dataDisks) > 0
    THEN reduce(total = 0, disk IN vm.properties.storageProfile.dataDisks | total + disk.diskSizeGB)
    ELSE 0
  END AS data_disk_total_gb
ORDER BY vm.name;

// Find VMs with specific configurations
// Example: Windows VMs with data disks
MATCH (vm:Resource {type: 'Microsoft.Compute/virtualMachines'})
WHERE vm.tenant_id = $tenant_id
  AND vm.properties.storageProfile.osDisk.osType = 'Windows'
  AND size(vm.properties.storageProfile.dataDisks) > 0
RETURN
  vm.name AS vm_name,
  vm.properties.storageProfile.imageReference.sku AS windows_version,
  size(vm.properties.storageProfile.dataDisks) AS data_disk_count
ORDER BY vm.name;
