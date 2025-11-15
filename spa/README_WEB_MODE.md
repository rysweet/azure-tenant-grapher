# Azure Tenant Grapher - Web App Mode

This directory contains the Azure Tenant Grapher Single Page Application (SPA), which can run in two modes:

## Modes

### 1. Desktop Mode (Electron)
The default mode - runs as a native desktop application.

```bash
npm install
npm run build
npm start
```

### 2. Web App Mode (NEW)
Run as a web server accessible from browsers on your network or through SSH tunneling.

```bash
npm install
npm run build:web
npm run start:web
```

Access at: `http://localhost:3000` (or your configured port)

## Quick Start - Web Mode

### Development (with hot reload)
```bash
npm run start:web:dev
```

### Production
```bash
npm run build:web
npm run start:web
```

## Configuration

Configure web mode via environment variables or `spa/config/web-server.config.js`.

### Key Environment Variables

```bash
# Port (default: 3000)
export WEB_SERVER_PORT=3000

# Host binding (default: 0.0.0.0)
export WEB_SERVER_HOST=0.0.0.0

# CORS (default: true)
export ENABLE_CORS=true
export ALLOWED_ORIGINS="*"  # Or specific origins: "http://10.0.0.5:3000"
```

### Example: Run on port 8080

```bash
export WEB_SERVER_PORT=8080
npm run start:web
```

## Accessing from Other Machines

### Local Network
1. Start server with `WEB_SERVER_HOST=0.0.0.0`
2. Allow port through firewall
3. Access at `http://<server-ip>:3000`

### Azure Bastion (SSH Tunnel)
```bash
# Step 1: Create Bastion tunnel
az network bastion tunnel \
  --name <bastion> \
  --resource-group <rg> \
  --target-resource-id <vm-id> \
  --resource-port 22 \
  --port 50022

# Step 2: SSH with port forwarding
ssh -L 3000:localhost:3000 -p 50022 azureuser@127.0.0.1

# Step 3: Access at http://localhost:3000
```

## Documentation

- **[Web App Mode Guide](docs/WEB_APP_MODE.md)** - Complete web app setup and configuration
- **[Azure Bastion Connection Guide](../docs/AZURE_BASTION_CONNECTION_GUIDE.md)** - Detailed instructions for remote access via Bastion

## Directory Structure

```
spa/
├── backend/           # Express backend server
│   └── src/
│       ├── server.ts        # Electron mode backend
│       └── web-server.ts    # Web mode backend (NEW)
├── renderer/          # React frontend
├── main/              # Electron main process
├── config/            # Configuration files
│   └── web-server.config.js  # Web server config (NEW)
├── docs/              # Documentation
│   └── WEB_APP_MODE.md      # Web app guide (NEW)
└── dist/              # Built artifacts
```

## Features

Both modes support the same features:
- Azure tenant scanning
- Graph visualization
- IaC generation (Terraform, ARM, Bicep)
- Threat modeling
- Scale operations
- Neo4j graph database management

## NPM Scripts

### Development
- `npm run dev` - Start Electron app in dev mode
- `npm run start:web:dev` - Start web server in dev mode (hot reload)

### Building
- `npm run build` - Build Electron app
- `npm run build:web` - Build web app only
- `npm run build:renderer` - Build React frontend only
- `npm run build:backend` - Build backend only

### Running
- `npm start` - Run Electron app (desktop mode)
- `npm run start:web` - Run web server (web mode)
- `npm run start:backend` - Run backend only (Electron mode)

### Packaging
- `npm run package` - Package Electron app for current platform
- `npm run package:all` - Package for all platforms (Windows, macOS, Linux)

## Use Cases

### Desktop Mode
- Single user on local machine
- Offline usage
- Native OS integration
- Simpler setup

### Web Mode
- Remote access from multiple machines
- Team collaboration
- Azure VM deployment with Bastion
- CI/CD integration
- Lower resource footprint

## Security Considerations

When running in web mode:

1. **Use HTTPS in production** - Set up reverse proxy with SSL/TLS
2. **Restrict CORS** - Don't use `ALLOWED_ORIGINS=*` in production
3. **Enable authentication** - Set `ENABLE_AUTH=true` for production
4. **Firewall rules** - Restrict access to specific IP addresses
5. **Bind to localhost** - When using SSH tunneling, bind to `127.0.0.1`

## Troubleshooting

### Port already in use
```bash
# Find process using the port
lsof -i :3000
# Kill it
kill -9 <PID>
```

### Frontend not found
```bash
npm run build:renderer
npm run start:web
```

### CORS errors
```bash
export ENABLE_CORS=true
export ALLOWED_ORIGINS="http://your-origin:3000"
npm run start:web
```

## Support

For detailed documentation:
- [Main Project README](../README.md)
- [Web App Mode Guide](docs/WEB_APP_MODE.md)
- [Azure Bastion Connection Guide](../docs/AZURE_BASTION_CONNECTION_GUIDE.md)
- [CLAUDE.md](../CLAUDE.md) - Development guide
