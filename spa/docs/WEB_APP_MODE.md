# Web App Mode - Azure Tenant Grapher SPA

This guide explains how to run the Azure Tenant Grapher SPA as a standalone web application accessible from other machines, rather than as an Electron desktop application.

## Overview

By default, the Azure Tenant Grapher SPA runs as an Electron desktop application. However, you can also run it as a web application that can be accessed from any browser on your network or through SSH tunneling (e.g., Azure Bastion).

**Key Differences:**
- **Desktop Mode (Electron)**: Runs as a standalone desktop app, managed by `npm start`
- **Web Mode**: Runs as a web server accessible from browsers, managed by `npm run start:web`

## Quick Start

### 1. Build the Application

First, build the React frontend and backend:

```bash
cd spa
npm run build:web
```

This will:
- Build the React frontend (`npm run build:renderer`)
- Compile the TypeScript backend (`npm run build:backend`)

### 2. Start the Web Server

```bash
npm run start:web
```

The application will be available at:
- Local: `http://localhost:3000`
- Network: `http://<your-ip-address>:3000` (if accessible)

### 3. Access from Browser

Open your browser and navigate to the URL displayed in the console output.

## Configuration

### Environment Variables

You can configure the web server using environment variables or the config file at `spa/config/web-server.config.js`.

#### Port Configuration

```bash
# Change the port (default: 3000)
export WEB_SERVER_PORT=8080
npm run start:web
```

#### Host Binding

```bash
# Bind to specific interface
export WEB_SERVER_HOST=0.0.0.0  # All interfaces (default)
# OR
export WEB_SERVER_HOST=127.0.0.1  # Local only
```

#### CORS Configuration

```bash
# Enable/disable CORS (default: enabled)
export ENABLE_CORS=true

# Allowed origins (default: *)
export ALLOWED_ORIGINS="http://10.0.0.5:3000,http://192.168.1.10:3000"
# OR allow all
export ALLOWED_ORIGINS="*"
```

### Configuration File

Edit `spa/config/web-server.config.js` to set default values:

```javascript
module.exports = {
  port: 3000,
  host: '0.0.0.0',
  enableCors: true,
  allowedOrigins: ['*'],
  // ... other settings
};
```

## Development Mode

For development with hot reload:

```bash
npm run start:web:dev
```

This uses `tsx watch` to automatically restart the server when you make changes to the backend code.

## Network Access

### Local Network Access

To access from other machines on your local network:

1. **Start the server** with host binding to `0.0.0.0`:
   ```bash
   export WEB_SERVER_HOST=0.0.0.0
   npm run start:web
   ```

2. **Find your IP address**:
   ```bash
   # Linux/macOS
   ip addr show | grep inet
   # OR
   ifconfig | grep inet
   ```

3. **Configure firewall** to allow connections on the port:
   ```bash
   # Example for Ubuntu/Linux
   sudo ufw allow 3000/tcp
   ```

4. **Access from browser**:
   ```
   http://<your-ip-address>:3000
   ```

### Remote Access via SSH Tunnel

If the server is not directly accessible (e.g., behind a firewall), you can use SSH tunneling:

```bash
# From your local machine
ssh -L 3000:localhost:3000 user@remote-server

# Then access locally at:
# http://localhost:3000
```

### Azure Bastion Connection

For detailed instructions on accessing through Azure Bastion, see [Azure Bastion Connection Guide](../../docs/AZURE_BASTION_CONNECTION_GUIDE.md).

## Security Considerations

### Production Deployment

When deploying to production, consider these security measures:

1. **Use HTTPS**: Set up a reverse proxy (nginx, Apache) with SSL/TLS
2. **Restrict CORS**: Don't use `*` for allowed origins in production
3. **Enable Authentication**: Set `ENABLE_AUTH=true` (requires additional setup)
4. **Use Firewall Rules**: Restrict access to specific IP addresses
5. **Environment Variables**: Store sensitive credentials securely (Azure Key Vault, etc.)

### Example HTTPS Setup with Nginx

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # WebSocket support
    location /socket.io/ {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Rate Limiting

The web server includes basic rate limiting:
- 100 requests per 15 minutes per IP address
- Configurable in `spa/config/web-server.config.js`

## Troubleshooting

### Port Already in Use

```bash
# Find process using the port
lsof -i :3000
# OR
netstat -tulpn | grep 3000

# Kill the process
kill -9 <PID>
```

### Frontend Not Found

If you see "Frontend not built" error:

```bash
cd spa
npm run build:renderer
npm run start:web
```

### CORS Errors

If you see CORS errors in the browser console:

1. Check `ENABLE_CORS` is set to `true`
2. Add your origin to `ALLOWED_ORIGINS`:
   ```bash
   export ALLOWED_ORIGINS="http://your-client-ip:3000"
   ```

### Neo4j Connection Issues

Ensure Neo4j is running and accessible:

```bash
# Check Neo4j status
docker ps | grep neo4j

# Check Neo4j connection
export NEO4J_URI=bolt://localhost:7687
export NEO4J_PASSWORD=your-password
```

### Cannot Access from Other Machines

1. **Check host binding**: Must be `0.0.0.0`, not `localhost`
2. **Check firewall**: Port must be open
3. **Check network**: Both machines must be on same network (or use SSH tunnel)

## API Endpoints

The web server exposes these REST API endpoints:

### Health Check
- `GET /api/health` - Server health status

### Authentication
- `POST /api/auth/token` - Generate auth token
- `GET /api/auth/stats` - Get auth statistics

### Graph Operations
- `GET /api/graph/status` - Check if database is populated
- `GET /api/graph/stats` - Get database statistics
- `GET /api/graph` - Get full graph data
- `GET /api/graph/search?query=<term>` - Search nodes
- `GET /api/graph/node/:nodeId` - Get node details

### Process Management
- `POST /api/execute` - Execute CLI command
- `POST /api/cancel/:processId` - Cancel running process
- `GET /api/status/:processId` - Get process status
- `GET /api/processes` - List all active processes

### Neo4j Management
- `GET /api/neo4j/status` - Get Neo4j container status
- `POST /api/neo4j/start` - Start Neo4j container
- `POST /api/neo4j/stop` - Stop Neo4j container
- `GET /api/neo4j/tenants` - List tenants in database

### Configuration
- `GET /api/config/env` - Get environment configuration

## WebSocket Events

The server uses Socket.IO for real-time communication:

### Client -> Server Events
- `subscribe` - Subscribe to process output
- `unsubscribe` - Unsubscribe from process output

### Server -> Client Events
- `output` - Process output (stdout/stderr)
- `process-exit` - Process completed
- `process-error` - Process error

## Comparison: Desktop vs Web Mode

| Feature | Desktop Mode | Web Mode |
|---------|-------------|----------|
| Installation | Electron app | Web browser |
| Access | Local machine only | Network accessible |
| Updates | App restart required | Browser refresh |
| Multiple Users | One per machine | Multiple simultaneous |
| Resource Usage | Higher (Electron) | Lower (browser only) |
| Deployment | Package & distribute | Run on server |
| Offline | Works offline | Requires network |

## Use Cases

### When to Use Web Mode

- **Remote Access**: Access from multiple machines
- **Team Collaboration**: Multiple users need access
- **Azure VM Deployment**: Running on Azure VM with Bastion
- **CI/CD Integration**: Automated testing/deployment
- **Lower Resource Footprint**: No Electron overhead

### When to Use Desktop Mode

- **Single User**: One person using locally
- **Offline Access**: No network required
- **Native Features**: Better OS integration
- **Simpler Setup**: No web server configuration needed

## Advanced Configuration

### Running as System Service

Create a systemd service file (Linux):

```ini
[Unit]
Description=Azure Tenant Grapher Web Server
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/atg/spa
Environment="NODE_ENV=production"
Environment="WEB_SERVER_PORT=3000"
Environment="WEB_SERVER_HOST=0.0.0.0"
ExecStart=/usr/bin/npm run start:web
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable azure-tenant-grapher
sudo systemctl start azure-tenant-grapher
```

### Docker Deployment

Create a `Dockerfile` in the spa directory:

```dockerfile
FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy built application
COPY dist/ ./dist/
COPY config/ ./config/

# Expose port
EXPOSE 3000

# Start server
CMD ["node", "dist/backend/web-server.js"]
```

Build and run:
```bash
docker build -t atg-web .
docker run -p 3000:3000 \
  -e NEO4J_URI=bolt://neo4j:7687 \
  -e NEO4J_PASSWORD=your-password \
  atg-web
```

## Support

For issues or questions:
- Check the [Azure Bastion Connection Guide](../../docs/AZURE_BASTION_CONNECTION_GUIDE.md)
- Review the [main README](../../README.md)
- Check logs: The web server outputs detailed logs to console
- Enable debug mode: `export NODE_ENV=development`

## Related Documentation

- [Azure Bastion Connection Guide](../../docs/AZURE_BASTION_CONNECTION_GUIDE.md) - How to connect through Azure Bastion
- [SPA Architecture](../../CLAUDE.md#spagui-architecture) - Architecture overview
- [Backend API](../backend/src/server.ts) - Full API implementation
