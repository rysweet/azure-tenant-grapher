# Azure Bastion Connection Guide

This guide explains how to access the Azure Tenant Grapher web application running on an Azure VM through Azure Bastion using SSH port forwarding.

## Overview

Azure Bastion provides secure RDP and SSH connectivity to your Azure VMs without exposing public IP addresses. When running Azure Tenant Grapher in web mode on an Azure VM, you can use Bastion's SSH tunneling feature to forward the web server port to your local machine.

**Architecture:**
```
Your Browser → localhost:3000 → SSH Tunnel → Azure Bastion → Azure VM:3000 → ATG Web Server
```

## Prerequisites

- Azure VM with Azure Tenant Grapher installed
- Azure Bastion deployed in the same VNet
- SSH access to the VM (key-based or password)
- Azure CLI installed on your local machine
- Bastion SKU that supports tunneling (Standard tier)

## Method 1: Azure CLI SSH Tunnel (Recommended)

This is the easiest and most secure method.

### Step 1: Install Azure CLI

If not already installed:

```bash
# macOS
brew install azure-cli

# Windows (PowerShell)
winget install Microsoft.AzureCLI

# Linux (Ubuntu/Debian)
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

### Step 2: Login to Azure

```bash
az login
```

Select your subscription:
```bash
az account set --subscription "<your-subscription-id>"
```

### Step 3: Start SSH Tunnel via Bastion

```bash
az network bastion tunnel \
  --name <bastion-name> \
  --resource-group <resource-group> \
  --target-resource-id <vm-resource-id> \
  --resource-port 22 \
  --port 50022
```

**Parameters:**
- `--name`: Name of your Azure Bastion resource
- `--resource-group`: Resource group containing the Bastion
- `--target-resource-id`: Full resource ID of your VM
- `--resource-port`: SSH port on the VM (usually 22)
- `--port`: Local port to forward to (can be any available port)

**Find your VM Resource ID:**
```bash
az vm show \
  --name <vm-name> \
  --resource-group <resource-group> \
  --query id -o tsv
```

### Step 4: Connect via SSH with Port Forwarding

In a **new terminal** (keep the tunnel command running):

```bash
ssh -i ~/.ssh/your-key.pem \
  -L 3000:localhost:3000 \
  -p 50022 \
  azureuser@127.0.0.1
```

**Parameters:**
- `-i ~/.ssh/your-key.pem`: Your SSH private key
- `-L 3000:localhost:3000`: Forward local port 3000 to VM's port 3000
- `-p 50022`: Connect to the tunnel port from Step 3
- `azureuser@127.0.0.1`: Connect to localhost (tunneled to VM)

**For password authentication:**
```bash
ssh -L 3000:localhost:3000 \
  -p 50022 \
  azureuser@127.0.0.1
```

### Step 5: Start Azure Tenant Grapher Web Server

On the SSH session (on the VM):

```bash
cd /path/to/azure-tenant-grapher/spa
export WEB_SERVER_HOST=127.0.0.1  # Bind to localhost for security
export WEB_SERVER_PORT=3000
npm run start:web
```

### Step 6: Access from Browser

On your **local machine**, open your browser:
```
http://localhost:3000
```

You should now see the Azure Tenant Grapher web interface!

## Method 2: Azure Portal Native SSH (Alternative)

Azure Portal provides a browser-based SSH client, but it doesn't support port forwarding directly. This method is useful for starting the server but requires Method 1 for accessing the web UI.

### Step 1: Access VM via Portal

1. Navigate to Azure Portal: https://portal.azure.com
2. Go to your VM resource
3. Click **Connect** → **Bastion**
4. Choose **SSH** authentication
5. Enter username and SSH key/password
6. Click **Connect**

### Step 2: Start the Web Server

In the browser terminal:
```bash
cd /path/to/azure-tenant-grapher/spa
export WEB_SERVER_HOST=127.0.0.1
export WEB_SERVER_PORT=3000
npm run start:web
```

### Step 3: Use Method 1 for Port Forwarding

Since the portal SSH doesn't support port forwarding, use Method 1 to access the web UI.

## Method 3: Direct Bastion SSH Tunnel (Advanced)

For advanced users who want a single command solution.

### Single Command Tunnel

```bash
az network bastion ssh \
  --name <bastion-name> \
  --resource-group <resource-group> \
  --target-resource-id <vm-resource-id> \
  --auth-type ssh-key \
  --username azureuser \
  --ssh-key ~/.ssh/your-key.pem \
  -- -L 3000:localhost:3000
```

This combines the tunnel and SSH connection in one command.

## Configuration Examples

### Example 1: Full Setup Script

Create a script `connect-atg-bastion.sh`:

```bash
#!/bin/bash

# Configuration
BASTION_NAME="myBastion"
RESOURCE_GROUP="myResourceGroup"
VM_NAME="atg-vm"
LOCAL_PORT=3000
VM_PORT=3000
SSH_KEY="~/.ssh/id_rsa"
SSH_USER="azureuser"

# Get VM Resource ID
VM_ID=$(az vm show --name $VM_NAME --resource-group $RESOURCE_GROUP --query id -o tsv)

echo "Starting Bastion tunnel..."
az network bastion tunnel \
  --name $BASTION_NAME \
  --resource-group $RESOURCE_GROUP \
  --target-resource-id $VM_ID \
  --resource-port 22 \
  --port 50022 &

TUNNEL_PID=$!

echo "Waiting for tunnel to establish..."
sleep 5

echo "Connecting via SSH with port forwarding..."
ssh -i $SSH_KEY \
  -L $LOCAL_PORT:localhost:$VM_PORT \
  -p 50022 \
  $SSH_USER@127.0.0.1

# Cleanup
kill $TUNNEL_PID
```

Make it executable:
```bash
chmod +x connect-atg-bastion.sh
./connect-atg-bastion.sh
```

### Example 2: PowerShell Script (Windows)

Create `Connect-ATG-Bastion.ps1`:

```powershell
# Configuration
$BastionName = "myBastion"
$ResourceGroup = "myResourceGroup"
$VMName = "atg-vm"
$LocalPort = 3000
$VMPort = 3000
$SSHKey = "~\.ssh\id_rsa"
$SSHUser = "azureuser"

# Get VM Resource ID
$VMId = az vm show --name $VMName --resource-group $ResourceGroup --query id -o tsv

Write-Host "Starting Bastion tunnel..."
Start-Process -NoNewWindow az -ArgumentList "network bastion tunnel --name $BastionName --resource-group $ResourceGroup --target-resource-id $VMId --resource-port 22 --port 50022"

Write-Host "Waiting for tunnel to establish..."
Start-Sleep -Seconds 5

Write-Host "Connecting via SSH with port forwarding..."
ssh -i $SSHKey -L "${LocalPort}:localhost:${VMPort}" -p 50022 "${SSHUser}@127.0.0.1"
```

Run it:
```powershell
.\Connect-ATG-Bastion.ps1
```

## Troubleshooting

### Issue: "Bastion does not support tunneling"

**Solution:** Upgrade your Bastion to Standard SKU:
```bash
az network bastion update \
  --name <bastion-name> \
  --resource-group <resource-group> \
  --sku Standard
```

### Issue: "Connection refused" on localhost:3000

**Causes:**
1. Web server not started on VM
2. Wrong port configured
3. Port already in use locally

**Solutions:**

Check if web server is running on VM:
```bash
# On VM via SSH
ps aux | grep web-server
netstat -tulpn | grep 3000
```

Check local port availability:
```bash
# On local machine
lsof -i :3000  # macOS/Linux
netstat -ano | findstr :3000  # Windows
```

### Issue: "Permission denied" when connecting via SSH

**Solutions:**

1. Check SSH key permissions:
   ```bash
   chmod 600 ~/.ssh/your-key.pem
   ```

2. Verify SSH key matches VM:
   ```bash
   # Check your public key
   ssh-keygen -y -f ~/.ssh/your-key.pem

   # Compare with VM's authorized_keys
   # (check in Azure Portal → VM → Reset Password → Reset SSH public key)
   ```

3. Use password authentication instead:
   ```bash
   ssh -L 3000:localhost:3000 -p 50022 azureuser@127.0.0.1
   # Enter password when prompted
   ```

### Issue: SSH tunnel disconnects frequently

**Solution:** Keep the connection alive:
```bash
ssh -i ~/.ssh/your-key.pem \
  -L 3000:localhost:3000 \
  -p 50022 \
  -o ServerAliveInterval=60 \
  -o ServerAliveCountMax=3 \
  azureuser@127.0.0.1
```

### Issue: "Address already in use" for local port

**Solution:** Use a different local port:
```bash
# Forward local port 8080 to VM port 3000
ssh -L 8080:localhost:3000 -p 50022 azureuser@127.0.0.1

# Access at http://localhost:8080
```

### Issue: Slow connection or timeouts

**Causes:**
- Network latency
- VM under heavy load
- Neo4j database issues

**Solutions:**

1. Check VM performance:
   ```bash
   # On VM
   top
   df -h
   free -m
   ```

2. Check Neo4j status:
   ```bash
   docker ps | grep neo4j
   docker logs <neo4j-container-id>
   ```

3. Restart web server with debug mode:
   ```bash
   export NODE_ENV=development
   npm run start:web:dev
   ```

## Security Best Practices

### 1. Use Localhost Binding on VM

Always bind the web server to localhost on the VM:
```bash
export WEB_SERVER_HOST=127.0.0.1
```

This ensures the web server is only accessible through SSH tunnel, not directly from the network.

### 2. Use SSH Key Authentication

Avoid password authentication when possible:
```bash
# Generate key pair if needed
ssh-keygen -t rsa -b 4096 -f ~/.ssh/atg-bastion-key

# Add public key to VM in Azure Portal
```

### 3. Restrict CORS Origins

Configure CORS to only allow localhost:
```bash
export ALLOWED_ORIGINS="http://localhost:3000"
```

### 4. Enable Firewall on VM

Only allow SSH from Azure Bastion subnet:
```bash
# On VM (Ubuntu/Debian)
sudo ufw allow from <bastion-subnet-cidr> to any port 22
sudo ufw enable
```

### 5. Use HTTPS (Production)

For production deployments, set up HTTPS with Let's Encrypt or Azure certificates.

## Alternative: Jump Host Configuration

If you have a jump host (bastion VM) with public IP:

```bash
# SSH to jump host with port forwarding
ssh -i ~/.ssh/jump-key.pem \
  -L 3000:atg-vm-private-ip:3000 \
  jumpuser@jump-host-public-ip

# Access at http://localhost:3000
```

## Monitoring and Logging

### View Web Server Logs

On the VM via SSH:
```bash
# Follow logs in real-time
tail -f /path/to/logs/web-server.log

# Or view console output
# (if running in foreground)
```

### Monitor SSH Tunnel

Check tunnel status:
```bash
# On local machine
netstat -an | grep 50022  # Tunnel port
netstat -an | grep 3000   # Forwarded port
```

### Check Bastion Logs

View Bastion diagnostic logs in Azure Portal:
1. Navigate to Bastion resource
2. Click **Diagnostic settings**
3. Enable logs for troubleshooting

## Performance Tips

### 1. Use Compression

Enable SSH compression for faster transfers:
```bash
ssh -C -L 3000:localhost:3000 -p 50022 azureuser@127.0.0.1
```

### 2. Keep Tunnel Alive

Prevent timeout disconnections:
```bash
# In ~/.ssh/config
Host bastion-tunnel
    HostName 127.0.0.1
    Port 50022
    User azureuser
    IdentityFile ~/.ssh/your-key.pem
    LocalForward 3000 localhost:3000
    ServerAliveInterval 60
    ServerAliveCountMax 3
    Compression yes

# Then simply:
ssh bastion-tunnel
```

### 3. Optimize VM Size

Ensure VM has sufficient resources:
- **Minimum**: Standard_B2s (2 vCPU, 4 GB RAM)
- **Recommended**: Standard_D2s_v3 (2 vCPU, 8 GB RAM)

## Automation

### Auto-Start on VM Boot

Create systemd service on VM:

```bash
sudo nano /etc/systemd/system/atg-web.service
```

```ini
[Unit]
Description=Azure Tenant Grapher Web Server
After=network.target docker.service

[Service]
Type=simple
User=azureuser
WorkingDirectory=/home/azureuser/azure-tenant-grapher/spa
Environment="NODE_ENV=production"
Environment="WEB_SERVER_HOST=127.0.0.1"
Environment="WEB_SERVER_PORT=3000"
ExecStart=/usr/bin/npm run start:web
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable atg-web
sudo systemctl start atg-web
```

### Connection Script with Auto-Restart

Create `auto-connect-bastion.sh`:

```bash
#!/bin/bash

while true; do
    echo "Connecting to Azure Tenant Grapher via Bastion..."
    ./connect-atg-bastion.sh

    echo "Connection lost. Reconnecting in 5 seconds..."
    sleep 5
done
```

## Cost Considerations

- **Bastion Standard**: ~$140/month + data transfer costs
- **Bastion Basic**: ~$70/month (no tunneling support)
- Consider shutting down VMs and Bastion when not in use:
  ```bash
  az vm deallocate --name <vm-name> --resource-group <resource-group>
  ```

## Summary

**Quick Setup:**
1. Deploy Azure Bastion (Standard SKU)
2. Start tunnel: `az network bastion tunnel ...`
3. Connect with forwarding: `ssh -L 3000:localhost:3000 ...`
4. Start web server on VM: `npm run start:web`
5. Access at: `http://localhost:3000`

**For detailed web app configuration, see [Web App Mode Documentation](../spa/docs/WEB_APP_MODE.md).**

## Additional Resources

- [Azure Bastion Documentation](https://learn.microsoft.com/en-us/azure/bastion/)
- [Azure CLI Network Bastion Commands](https://learn.microsoft.com/en-us/cli/azure/network/bastion)
- [Web App Mode Guide](../spa/docs/WEB_APP_MODE.md)
- [SSH Tunneling Guide](https://www.ssh.com/academy/ssh/tunneling)
