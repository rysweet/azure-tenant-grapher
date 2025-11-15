# Quick Start - Web App Mode

Run Azure Tenant Grapher as a web application accessible from other machines.

## 30-Second Start

```bash
cd spa
npm run build:web
npm run start:web
```

Open browser: http://localhost:3000

## Remote Access via Azure Bastion

### Step 1: Start Bastion Tunnel
```bash
az network bastion tunnel \
  --name <bastion-name> \
  --resource-group <resource-group> \
  --target-resource-id <vm-resource-id> \
  --resource-port 22 \
  --port 50022
```

### Step 2: Connect with Port Forwarding (New Terminal)
```bash
ssh -L 3000:localhost:3000 -p 50022 azureuser@127.0.0.1
```

### Step 3: Start Web Server (On VM via SSH)
```bash
cd /path/to/azure-tenant-grapher/spa
export WEB_SERVER_HOST=127.0.0.1
npm run start:web
```

### Step 4: Access from Browser (Local Machine)
```
http://localhost:3000
```

## Configuration

### Change Port
```bash
export WEB_SERVER_PORT=8080
npm run start:web
```

### Allow Remote Access (Local Network)
```bash
export WEB_SERVER_HOST=0.0.0.0
export ALLOWED_ORIGINS="*"
npm run start:web

# Access from other machines:
# http://<server-ip>:3000
```

## Troubleshooting

### Port Already in Use
```bash
lsof -i :3000
kill -9 <PID>
```

### Frontend Not Found
```bash
npm run build:renderer
npm run start:web
```

### CORS Errors
```bash
export ENABLE_CORS=true
export ALLOWED_ORIGINS="*"
npm run start:web
```

## Full Documentation

- **[Complete Web App Guide](spa/docs/WEB_APP_MODE.md)**
- **[Azure Bastion Guide](docs/AZURE_BASTION_CONNECTION_GUIDE.md)**
- **[Summary](WEB_APP_MODE_SUMMARY.md)**

## Need Help?

See the comprehensive guides above or check [CLAUDE.md](CLAUDE.md) for development details.
