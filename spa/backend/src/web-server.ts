#!/usr/bin/env node
/**
 * Web Server Mode for Azure Tenant Grapher SPA
 *
 * This script starts the Express backend server and serves the built React frontend
 * as a standalone web application accessible from remote machines.
 *
 * Environment Variables:
 * - WEB_SERVER_PORT: Port to bind (default: 3000)
 * - WEB_SERVER_HOST: Host to bind (default: 0.0.0.0 for network access)
 * - ENABLE_CORS: Enable CORS for cross-origin requests (default: true)
 * - ALLOWED_ORIGINS: Comma-separated list of allowed origins (default: *)
 * - NODE_ENV: Environment mode (production/development)
 */

import express from 'express';
import { createServer } from 'http';
import { Server as SocketIOServer } from 'socket.io';
import cors from 'cors';
import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';
import { v4 as uuidv4 } from 'uuid';
import * as dotenv from 'dotenv';
import { Neo4jService } from './neo4j-service';
import { Neo4jContainer } from './neo4j-container';
import { initializeLogger, createLogger } from './logger-setup';
import { WebSocketServer } from 'ws';
import { InputValidator } from './security/input-validator';
import { AuthMiddleware } from './security/auth-middleware';

// Load .env file from the project root
const projectRoot = path.join(__dirname, '../../..');
dotenv.config({ path: path.join(projectRoot, '.env') });

// Web server configuration
const WEB_SERVER_PORT = parseInt(process.env.WEB_SERVER_PORT || '3000', 10);
const WEB_SERVER_HOST = process.env.WEB_SERVER_HOST || '0.0.0.0';
const ENABLE_CORS = process.env.ENABLE_CORS !== 'false';
const ALLOWED_ORIGINS = process.env.ALLOWED_ORIGINS
  ? process.env.ALLOWED_ORIGINS.split(',').map(o => o.trim())
  : ['*'];

console.log('========================================');
console.log('Azure Tenant Grapher - Web Server Mode');
console.log('========================================');
console.log(`Port: ${WEB_SERVER_PORT}`);
console.log(`Host: ${WEB_SERVER_HOST}`);
console.log(`CORS: ${ENABLE_CORS ? 'Enabled' : 'Disabled'}`);
console.log(`Allowed Origins: ${ALLOWED_ORIGINS.join(', ')}`);
console.log('========================================\n');

const app = express();
const httpServer = createServer(app);

// Configure Socket.IO with appropriate CORS settings
const socketCorsOrigin = ENABLE_CORS ? ALLOWED_ORIGINS : false;
const io = new SocketIOServer(httpServer, {
  cors: socketCorsOrigin === false ? undefined : {
    origin: socketCorsOrigin,
    methods: ['GET', 'POST'],
    credentials: true
  },
});

// Initialize WebSocket server for logger
const wss = new WebSocketServer({ server: httpServer, path: '/logs' });

// Initialize the logger with WebSocket transport
initializeLogger(wss);

// Create component logger
const logger = createLogger('web-server');

logger.info('Web server starting', {
  port: WEB_SERVER_PORT,
  host: WEB_SERVER_HOST,
  cors: ENABLE_CORS,
  origins: ALLOWED_ORIGINS
});

// CORS middleware - configure based on environment
if (ENABLE_CORS) {
  const corsOptions = {
    origin: ALLOWED_ORIGINS[0] === '*' ? true : ALLOWED_ORIGINS,
    credentials: true,
    optionsSuccessStatus: 200
  };
  app.use(cors(corsOptions));
  logger.info('CORS enabled', { origins: ALLOWED_ORIGINS });
} else {
  logger.warn('CORS disabled - requests from browsers may be blocked');
}

app.use(express.json());

// Serve static files from the built React app
const rendererPath = path.join(__dirname, '../../dist/renderer');
if (fs.existsSync(rendererPath)) {
  app.use(express.static(rendererPath));
  logger.info(`Serving static files from: ${rendererPath}`);
} else {
  logger.warn(`Renderer build not found at: ${rendererPath}`);
  logger.warn('Run "npm run build:renderer" to build the frontend');
}

// Store active processes
const activeProcesses = new Map<string, ChildProcess>();

// Initialize Neo4j service and container manager
const neo4jService = new Neo4jService();
const neo4jContainer = new Neo4jContainer();

// Apply authentication middleware to WebSocket connections
io.use(AuthMiddleware.authenticate);

// WebSocket connection handling
io.on('connection', (socket) => {
  logger.info('Client connected', { socketId: socket.id });

  // Setup heartbeat for this connection
  AuthMiddleware.setupHeartbeat(socket);

  // Subscribe to process output
  socket.on('subscribe', (processId: string) => {
    socket.join(`process-${processId}`);
    logger.debug(`Client ${socket.id} subscribed to process ${processId}`);
  });

  // Unsubscribe from process output
  socket.on('unsubscribe', (processId: string) => {
    socket.leave(`process-${processId}`);
    logger.debug(`Client ${socket.id} unsubscribed from process ${processId}`);
  });

  socket.on('disconnect', () => {
    logger.info('Client disconnected', { socketId: socket.id });
  });
});

// ==================== API Routes ====================
// Import all routes from the main server.ts
// Note: In production, we should refactor routes into separate modules

// Authentication endpoint
app.post('/api/auth/token', (req, res) => {
  try {
    const { userId = 'default-user', clientId = uuidv4() } = req.body;
    const ipAddress = req.ip || req.connection.remoteAddress || 'unknown';
    const userAgent = req.headers['user-agent'];
    const token = AuthMiddleware.createSession(userId, clientId, ipAddress, userAgent);
    res.json({
      success: true,
      token,
      expiresIn: 86400
    });
  } catch (error) {
    logger.error('Failed to generate auth token', { error });
    res.status(500).json({ error: 'Failed to generate authentication token' });
  }
});

// Get authentication stats
app.get('/api/auth/stats', (req, res) => {
  try {
    const stats = AuthMiddleware.getStats();
    res.json(stats);
  } catch (error) {
    logger.error('Failed to get auth stats', { error });
    res.status(500).json({ error: 'Failed to get authentication statistics' });
  }
});

// Get Azure tenant name
app.get('/api/tenant-name', async (req, res) => {
  try {
    const { exec } = require('child_process');
    const util = require('util');
    const execPromise = util.promisify(exec);

    try {
      const { stdout } = await execPromise('az account show --query "name" --output tsv');
      const name = stdout.trim();
      if (name && !name.includes('error') && name.length > 0) {
        res.json({ name });
        return;
      }
    } catch (azError: any) {
      logger.debug('Azure CLI not available or not logged in');
    }

    const tenantId = process.env.AZURE_TENANT_ID || 'Unknown';
    res.json({ name: tenantId });
  } catch (error) {
    logger.error('Error getting tenant name', { error });
    res.status(500).json({ error: 'Failed to get tenant name' });
  }
});

// Execute CLI command
app.post('/api/execute', (req, res) => {
  const { command, args = [] } = req.body;
  const processId = uuidv4();

  if (!command) {
    return res.status(400).json({ error: 'Command is required' });
  }

  const commandValidation = InputValidator.validateCommand(command);
  if (!commandValidation.isValid) {
    logger.warn('Invalid command attempted:', { command, error: commandValidation.error });
    return res.status(400).json({ error: commandValidation.error });
  }

  const argsValidation = InputValidator.validateArguments(args);
  if (!argsValidation.isValid) {
    logger.warn('Invalid arguments:', { args, error: argsValidation.error });
    return res.status(400).json({ error: argsValidation.error });
  }

  const uvPath = process.env.UV_PATH || 'uv';
  const fullArgs = ['run', 'atg', command, ...args];

  logger.info('Executing CLI command:', {
    command: `${uvPath} ${fullArgs.join(' ')}`,
    cwd: projectRoot,
    processId
  });

  const childProcess = spawn(uvPath, fullArgs, {
    cwd: projectRoot,
    shell: false,
    env: {
      ...process.env,
      PYTHONPATH: projectRoot,
    },
  });

  activeProcesses.set(processId, childProcess);

  childProcess.stdout?.on('data', (data) => {
    const sanitized = InputValidator.sanitizeOutput(data.toString());
    const lines = sanitized.split('\n').filter((line: string) => line);
    io.to(`process-${processId}`).emit('output', {
      processId,
      type: 'stdout',
      data: lines,
      timestamp: new Date().toISOString(),
    });
  });

  childProcess.stderr?.on('data', (data) => {
    const sanitized = InputValidator.sanitizeOutput(data.toString());
    const lines = sanitized.split('\n').filter((line: string) => line);
    io.to(`process-${processId}`).emit('output', {
      processId,
      type: 'stderr',
      data: lines,
      timestamp: new Date().toISOString(),
    });
  });

  childProcess.on('exit', (code) => {
    io.to(`process-${processId}`).emit('process-exit', {
      processId,
      code,
      timestamp: new Date().toISOString(),
    });
    activeProcesses.delete(processId);
  });

  childProcess.on('error', (error) => {
    io.to(`process-${processId}`).emit('process-error', {
      processId,
      error: error.message,
      timestamp: new Date().toISOString(),
    });
    activeProcesses.delete(processId);
  });

  res.json({ processId, status: 'started' });
});

// Cancel process
app.post('/api/cancel/:processId', (req, res) => {
  const { processId } = req.params;
  const process = activeProcesses.get(processId);

  if (!process) {
    return res.status(404).json({ error: 'Process not found' });
  }

  process.kill('SIGTERM');
  activeProcesses.delete(processId);
  res.json({ status: 'cancelled' });
});

// Get process status
app.get('/api/status/:processId', (req, res) => {
  const { processId } = req.params;
  const process = activeProcesses.get(processId);

  if (!process) {
    return res.status(404).json({ error: 'Process not found' });
  }

  res.json({
    processId,
    status: 'running',
    pid: process.pid,
  });
});

// List all active processes
app.get('/api/processes', (req, res) => {
  const processes = Array.from(activeProcesses.entries()).map(([id, process]) => ({
    id,
    pid: process.pid,
    status: 'running',
  }));
  res.json(processes);
});

// Graph status
app.get('/api/graph/status', async (req, res) => {
  try {
    const isPopulated = await neo4jService.isDatabasePopulated();
    const stats = isPopulated ? await neo4jService.getDatabaseStats() : null;
    res.json({ isPopulated, stats });
  } catch (error) {
    logger.error('Error checking database status', { error });
    res.status(500).json({
      error: error instanceof Error ? error.message : 'Failed to check database status'
    });
  }
});

// Get database stats
app.get('/api/graph/stats', async (req, res) => {
  try {
    const stats = await neo4jService.getDatabaseStats();
    res.json(stats);
  } catch (error) {
    logger.error('Error fetching database stats', { error });
    res.status(500).json({
      error: error instanceof Error ? error.message : 'Failed to fetch database statistics'
    });
  }
});

// Get full graph
app.get('/api/graph', async (req, res) => {
  try {
    const graphData = await neo4jService.getFullGraph();
    res.json(graphData);
  } catch (error) {
    logger.error('Error fetching graph', { error });
    res.status(500).json({
      error: error instanceof Error ? error.message : 'Failed to fetch graph data'
    });
  }
});

// Search nodes
app.get('/api/graph/search', async (req, res) => {
  const { query } = req.query;
  if (!query || typeof query !== 'string') {
    return res.status(400).json({ error: 'Query parameter is required' });
  }
  try {
    const nodes = await neo4jService.searchNodes(query);
    res.json(nodes);
  } catch (error) {
    logger.error('Error searching nodes', { error });
    res.status(500).json({
      error: error instanceof Error ? error.message : 'Failed to search nodes'
    });
  }
});

// Get node details
app.get('/api/graph/node/:nodeId', async (req, res) => {
  const { nodeId } = req.params;
  try {
    const details = await neo4jService.getNodeDetails(nodeId);
    if (!details) {
      return res.status(404).json({ error: 'Node not found' });
    }
    res.json(details);
  } catch (error) {
    logger.error('Error fetching node details', { error });
    res.status(500).json({
      error: error instanceof Error ? error.message : 'Failed to fetch node details'
    });
  }
});

// Neo4j tenants
app.get('/api/neo4j/tenants', async (req, res) => {
  try {
    const neo4j = require('neo4j-driver');
    const { CredentialManager } = require('./security/credential-manager');
    const credentials = CredentialManager.getNeo4jCredentials();
    const driver = neo4j.driver(
      credentials.uri,
      neo4j.auth.basic(credentials.username, credentials.password)
    );
    const session = driver.session();
    try {
      const result = await session.run(
        'MATCH (t:Tenant) RETURN t.id as id, t.name as name ORDER BY t.name'
      );
      const tenants = result.records.map((record: any) => ({
        id: record.get('id'),
        name: record.get('name') || record.get('id')
      }));
      res.json({ tenants });
    } finally {
      await session.close();
      await driver.close();
    }
  } catch (error: any) {
    logger.error('Failed to fetch tenants from Neo4j', { error });
    res.json({ tenants: [], error: error.message });
  }
});

// Neo4j container status
app.get('/api/neo4j/status', async (req, res) => {
  try {
    const status = await neo4jContainer.getStatus();
    res.json(status);
  } catch (error) {
    res.status(500).json({
      error: error instanceof Error ? error.message : 'Failed to get Neo4j status'
    });
  }
});

// Start Neo4j
app.post('/api/neo4j/start', async (req, res) => {
  try {
    await neo4jContainer.start();
    res.json({ success: true, message: 'Neo4j container started' });
  } catch (error) {
    res.status(500).json({
      error: error instanceof Error ? error.message : 'Failed to start Neo4j'
    });
  }
});

// Stop Neo4j
app.post('/api/neo4j/stop', async (req, res) => {
  try {
    await neo4jContainer.stop();
    res.json({ success: true, message: 'Neo4j container stopped' });
  } catch (error) {
    res.status(500).json({
      error: error instanceof Error ? error.message : 'Failed to stop Neo4j'
    });
  }
});

// Get environment config
app.get('/api/config/env', (req, res) => {
  const envPath = path.join(projectRoot, '.env');
  let envConfig: Record<string, string> = {};

  if (fs.existsSync(envPath)) {
    try {
      const envContent = fs.readFileSync(envPath, 'utf8');
      envContent.split('\n').forEach(line => {
        line = line.trim();
        if (line && !line.startsWith('#')) {
          const [key, ...valueParts] = line.split('=');
          if (key) {
            envConfig[key.trim()] = valueParts.join('=').trim();
          }
        }
      });
    } catch (error) {
      logger.error('Failed to read .env file', { error });
    }
  }

  const config = {
    AZURE_TENANT_ID: process.env.AZURE_TENANT_ID || envConfig.AZURE_TENANT_ID || '',
    AZURE_CLIENT_ID: process.env.AZURE_CLIENT_ID || envConfig.AZURE_CLIENT_ID || '',
    AZURE_CLIENT_SECRET: process.env.AZURE_CLIENT_SECRET || envConfig.AZURE_CLIENT_SECRET || '',
    NEO4J_PORT: process.env.NEO4J_PORT || envConfig.NEO4J_PORT || '7687',
    NEO4J_URI: process.env.NEO4J_URI || envConfig.NEO4J_URI || 'bolt://localhost:7687',
    NEO4J_USER: process.env.NEO4J_USER || envConfig.NEO4J_USER || 'neo4j',
    NEO4J_PASSWORD: process.env.NEO4J_PASSWORD || envConfig.NEO4J_PASSWORD || '',
    LOG_LEVEL: process.env.LOG_LEVEL || envConfig.LOG_LEVEL || 'INFO',
    RESOURCE_LIMIT: process.env.RESOURCE_LIMIT || envConfig.RESOURCE_LIMIT || '',
  };

  res.json(config);
});

// Health check
app.get('/api/health', async (req, res) => {
  const neo4jStatus = await neo4jContainer.getStatus();
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    activeProcesses: activeProcesses.size,
    neo4j: neo4jStatus,
    mode: 'web'
  });
});

// Catch-all route - serve index.html for client-side routing
app.get('*', (req, res) => {
  const indexPath = path.join(rendererPath, 'index.html');
  if (fs.existsSync(indexPath)) {
    res.sendFile(indexPath);
  } else {
    res.status(404).send('Frontend not built. Run "npm run build:renderer" first.');
  }
});

// Error handling middleware
app.use((err: any, req: express.Request, res: express.Response, next: express.NextFunction) => {
  logger.error('Internal server error', { err });
  res.status(500).json({ error: 'Internal server error' });
});

// Cleanup on exit
process.on('SIGINT', async () => {
  logger.info('Shutting down web server...');
  activeProcesses.forEach((process) => {
    process.kill('SIGTERM');
  });
  await neo4jService.close();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  logger.info('Shutting down web server...');
  activeProcesses.forEach((process) => {
    process.kill('SIGTERM');
  });
  await neo4jService.close();
  process.exit(0);
});

// Start the server
async function startWebServer() {
  try {
    // Start Neo4j container first
    logger.info('Starting Neo4j container...');
    await neo4jContainer.start();
    logger.info('Neo4j container is ready');
  } catch (error) {
    logger.error('Failed to start Neo4j container', { error });
    logger.warn('Continuing without Neo4j - some features may not work');
  }

  // Start the HTTP server
  httpServer.listen(WEB_SERVER_PORT, WEB_SERVER_HOST, () => {
    console.log('\n========================================');
    console.log('Web Server Started Successfully!');
    console.log('========================================');
    console.log(`Local URL:    http://localhost:${WEB_SERVER_PORT}`);
    if (WEB_SERVER_HOST === '0.0.0.0') {
      console.log(`Network URL:  http://<your-ip>:${WEB_SERVER_PORT}`);
      console.log('');
      console.log('To access from other machines:');
      console.log('1. Use your machine\'s IP address');
      console.log('2. Ensure firewall allows port ' + WEB_SERVER_PORT);
      console.log('3. See docs for Azure Bastion setup');
    }
    console.log('========================================\n');

    logger.info('Web server ready for connections', {
      host: WEB_SERVER_HOST,
      port: WEB_SERVER_PORT
    });
  });
}

// Start everything
startWebServer();
