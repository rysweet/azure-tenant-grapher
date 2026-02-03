import express from 'express';
import { createServer } from 'http';
import { Server as SocketIOServer } from 'socket.io';
import cors from 'cors';
import rateLimit from 'express-rate-limit';
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
import { authRouter } from './routes/auth.routes';
import { TokenStorageService } from './services/token-storage.service';
import { DualAuthService } from './services/dual-auth.service';

// Declare global rate limit cache
declare global {
  var rateLimitCache: Record<string, number> | undefined;
}

// Load .env file from the project root
dotenv.config({ path: path.join(__dirname, '../../../.env') });

const app = express();
const httpServer = createServer(app);

// Configure Socket.IO CORS for both Electron and web mode
const socketCorsOrigins = [
  'http://localhost:5173',  // Vite dev server
  'app://./',                // Electron
  'http://localhost:3000',   // Web mode
  'http://127.0.0.1:3000',   // Web mode localhost
];

// Add custom origins from environment variable
if (process.env.ALLOWED_ORIGINS) {
  const customOrigins = process.env.ALLOWED_ORIGINS.split(',').map(o => o.trim());
  socketCorsOrigins.push(...customOrigins);
}

const io = new SocketIOServer(httpServer, {
  cors: {
    origin: (origin, callback) => {
      // Allow requests with no origin
      if (!origin) return callback(null, true);

      // Check if origin is allowed
      if (socketCorsOrigins.includes(origin) ||
          socketCorsOrigins.includes('*') ||
          origin.match(/^http:\/\/(localhost|127\.0\.0\.1):\d+$/)) {
        callback(null, true);
      }
      // Allow file:// protocol for Electron desktop app
      // SECURITY NOTE: This permits file:// origins which are used by Electron.
      // Authentication middleware still enforces token-based auth for all connections.
      // In production on shared systems, ensure auth tokens are properly secured.
      else if (origin.startsWith('file://')) {
        logger.info(`Allowing file:// origin for Electron app: ${origin}`);
        callback(null, true);
      }
      else {
        logger.warn(`Socket.IO CORS: Blocked connection from origin: ${origin}`);
        callback(new Error('Not allowed by CORS'));
      }
    },
    methods: ['GET', 'POST'],
    credentials: true,
  },
});

// Initialize WebSocket server for logger
//const wss = new WebSocketServer({ server: httpServer, path: '/logs' });

// Initialize the logger with WebSocket transport
//initializeLogger(wss);
initializeLogger(null as any);

// Create component logger
const logger = createLogger('server');

// Now we can use the logger
logger.info('Backend starting with environment');
logger.debug('Environment variables:', {
  AZURE_TENANT_ID: process.env.AZURE_TENANT_ID ? 'SET' : 'NOT SET',
  NEO4J_URI: process.env.NEO4J_URI || 'NOT SET',
  NEO4J_PORT: process.env.NEO4J_PORT || 'NOT SET'
});

// CORS middleware - configure for both Electron and remote access
const corsOptions = {
  origin: (origin: string | undefined, callback: (err: Error | null, allow?: boolean) => void) => {
    // Allow requests with no origin (like mobile apps or curl requests)
    if (!origin) return callback(null, true);

    // List of allowed origins
    const allowedOrigins = [
      'http://localhost:5173',  // Vite dev server
      'app://./',                // Electron
      'http://localhost:3000',   // Web mode
      'http://127.0.0.1:3000',   // Web mode localhost
    ];

    // Check if origin is in allowed list or matches pattern
    if (allowedOrigins.includes(origin) || origin.match(/^http:\/\/(localhost|127\.0\.0\.1):\d+$/)) {
      callback(null, true);
    } else {
      // For production web mode, check environment variable
      const customOrigins = process.env.ALLOWED_ORIGINS?.split(',').map(o => o.trim()) || [];
      if (customOrigins.includes(origin) || customOrigins.includes('*')) {
        callback(null, true);
      } else {
        logger.warn(`CORS: Blocked request from origin: ${origin}`);
        callback(null, false);
      }
    }
  },
  methods: ['GET', 'POST'],
  credentials: true,
};

app.use(cors(corsOptions));
app.use(express.json());

// Store active processes
const activeProcesses = new Map<string, ChildProcess>();

// Initialize Neo4j service and container manager
const neo4jService = new Neo4jService();
const neo4jContainer = new Neo4jContainer();

// Initialize authentication services
const encryptionKey = process.env.TOKEN_ENCRYPTION_KEY || 'default-encryption-key-change-in-production';
const tokenStorageService = new TokenStorageService(encryptionKey);
const dualAuthService = new DualAuthService(
  tokenStorageService,
  process.env.AZURE_CLIENT_ID || 'your-app-client-id-here'
);

// Mount auth routes for dual-account authentication (after service initialization)
app.use('/api/auth', authRouter(dualAuthService));

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

// API Routes

// Authentication endpoint - generate token for WebSocket connections
app.post('/api/auth/token', (req, res) => {
  try {
    // In production, validate credentials here
    // For now, we'll use a simple user identification
    const { userId = 'default-user', clientId = uuidv4() } = req.body;

    const ipAddress = req.ip || req.connection.remoteAddress || 'unknown';
    const userAgent = req.headers['user-agent'];

    const token = AuthMiddleware.createSession(userId, clientId, ipAddress, userAgent);

    res.json({
      success: true,
      token,
      expiresIn: 86400 // 24 hours in seconds
    });
  } catch (error) {
    logger.error('Failed to generate auth token', { error });
    res.status(500).json({ error: 'Failed to generate authentication token' });
  }
});

// Get authentication stats (admin endpoint)
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
      // Try to get subscription name from Azure CLI (this is the human-readable name)
      const { stdout } = await execPromise('az account show --query "name" --output tsv');
      const name = stdout.trim();
      if (name && !name.includes('error') && name.length > 0) {
        logger.debug('Got Azure subscription name:', name);
        res.json({ name });
        return;
      }
    } catch (azError: any) {
      logger.debug('Azure CLI not available or not logged in:', azError?.message || azError);
    }

    // Fallback to tenant ID from env
    const tenantId = process.env.AZURE_TENANT_ID || 'Unknown';
    res.json({ name: tenantId });
  } catch (error) {
    logger.error('Error getting tenant name', { error });
    res.status(500).json({ error: 'Failed to get tenant name' });
  }
});

/**
 * Execute a CLI command with input validation
 */
app.post('/api/execute', (req, res) => {
  const { command, args = [] } = req.body;
  const processId = uuidv4();

  if (!command) {
    return res.status(400).json({ error: 'Command is required' });
  }

  // Validate command input
  const commandValidation = InputValidator.validateCommand(command);
  if (!commandValidation.isValid) {
    logger.warn('Invalid command attempted:', { command, error: commandValidation.error });
    return res.status(400).json({ error: commandValidation.error });
  }

  // Validate arguments
  const argsValidation = InputValidator.validateArguments(args);
  if (!argsValidation.isValid) {
    logger.warn('Invalid arguments:', { args, error: argsValidation.error });
    return res.status(400).json({ error: argsValidation.error });
  }

  // Use uv to run the atg CLI command
  const uvPath = process.env.UV_PATH || 'uv';
  const projectRoot = path.resolve(__dirname, '../../..');

const fullArgs = ['run', 'atg', command, ...args];

  // Check for filter arguments for better logging
  const hasSubscriptionFilter = args.some((arg: string) => arg.startsWith('--filter-by-subscriptions'));
  const hasResourceGroupFilter = args.some((arg: string) => arg.startsWith('--filter-by-rgs'));
  const filters = [];
  if (hasSubscriptionFilter) {
    const subFilter = args.find((arg: string) => arg.startsWith('--filter-by-subscriptions'));
    filters.push(subFilter);
  }
  if (hasResourceGroupFilter) {
    const rgFilter = args.find((arg: string) => arg.startsWith('--filter-by-rgs'));
    filters.push(rgFilter);
  }

  logger.info('Executing CLI command:', {
    command: `${uvPath} ${fullArgs.join(' ')}`,
    cwd: projectRoot,
    processId,
    filters: filters.length > 0 ? filters : undefined
  });

  // Log filter details for debugging
  if (filters.length > 0) {
    logger.info(`Applying resource filters: ${filters.join(', ')}`);
  }

  // Never use shell: true to prevent command injection
  const childProcess = spawn(uvPath, fullArgs, {
    cwd: projectRoot,
    shell: false, // Explicitly disable shell execution
    env: {
      ...process.env,
      // Ensure the project root is in PYTHONPATH for proper module resolution
      PYTHONPATH: projectRoot,
      // Disable Python output buffering for real-time streaming
      PYTHONUNBUFFERED: '1',
    },
  });

  activeProcesses.set(processId, childProcess);

  // Stream stdout with output sanitization
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

  // Stream stderr with output sanitization
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

  // Handle process exit
  childProcess.on('exit', (code) => {
    io.to(`process-${processId}`).emit('process-exit', {
      processId,
      code,
      timestamp: new Date().toISOString(),
    });
    activeProcesses.delete(processId);
  });

  // Handle process error
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

/**
 * Cancel a running process
 */
app.post('/api/cancel/:processId', (req, res) => {
  const { processId } = req.params;
  const process = activeProcesses.get(processId);

  if (!process) {
    // Process already completed or doesn't exist - treat as success
    logger.debug(`Cancel request for non-existent process: ${processId} (likely already completed)`);
    return res.json({ status: 'not_running', message: 'Process already completed or not found' });
  }

  try {
    process.kill('SIGTERM');
    activeProcesses.delete(processId);
    logger.info(`Process ${processId} cancelled successfully`);
    res.json({ status: 'cancelled' });
  } catch (error) {
    logger.error(`Failed to kill process ${processId}`, { error });
    // Still remove from active processes even if kill fails
    activeProcesses.delete(processId);
    res.json({ status: 'cancelled', warning: 'Process may have already exited' });
  }
});

/**
 * Get process status
 */
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

/**
 * List all active processes
 */
app.get('/api/processes', (req, res) => {
  const processes = Array.from(activeProcesses.entries()).map(([id, process]) => ({
    id,
    pid: process.pid,
    status: 'running',
  }));

  res.json(processes);
});

/**
 * Check if database is populated
 */
app.get('/api/graph/status', async (req, res) => {
  try {
    const isPopulated = await neo4jService.isDatabasePopulated();
    const stats = isPopulated ? await neo4jService.getDatabaseStats() : null;
    res.json({
      isPopulated,
      stats
    });
  } catch (error) {
    logger.error('Error checking database status', { error });
    res.status(500).json({
      error: error instanceof Error ? error.message : 'Failed to check database status'
    });
  }
});

/**
 * Get database statistics
 */
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

/**
 * Get full graph data from Neo4j
 */
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

/**
 * Search nodes in the graph
 */
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

/**
 * Get node details
 */
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

/**
 * Fetch tenants from Neo4j graph database
 */
app.get('/api/neo4j/tenants', async (req, res) => {
  try {
    const neo4j = require('neo4j-driver');
    const { CredentialManager } = require('./security/credential-manager');

    // Get credentials from secure manager
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

/**
 * Neo4j container status endpoint
 */
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

/**
 * Start Neo4j container
 */
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

/**
 * Stop Neo4j container
 */
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

/**
 * MCP server status endpoint
 */
app.get('/api/mcp/status', async (req, res) => {
  try {
    // Check if MCP pidfile exists - use the project root path
    const projectRoot = path.join(__dirname, '../../..');
    const mcpPidfile = path.join(projectRoot, 'outputs', 'mcp_server.pid');
    const statusFile = path.join(projectRoot, 'outputs', 'mcp_server.status');

    // First try to check the healthcheck endpoint
    try {
      const healthResponse = await fetch('http://localhost:8080/health', {
        signal: AbortSignal.timeout(1000) // 1 second timeout
      });
      if (healthResponse.ok) {
        // MCP server is running with healthcheck
        let pid: number | undefined;
        if (fs.existsSync(mcpPidfile)) {
          pid = parseInt(fs.readFileSync(mcpPidfile, 'utf-8').trim());
        }
        res.json({ running: true, pid, status: 'ready', healthcheck: true });
        return;
      }
    } catch (e) {
      // Healthcheck failed, fall back to file checks
      logger.debug('MCP healthcheck failed, checking files');
    }

    // Check the status file for readiness state
    if (fs.existsSync(statusFile)) {
      const status = fs.readFileSync(statusFile, 'utf-8').trim();
      if (status === 'ready') {
        // Double-check the PID is still valid
        if (fs.existsSync(mcpPidfile)) {
          const pid = parseInt(fs.readFileSync(mcpPidfile, 'utf-8').trim());
          try {
            process.kill(pid, 0); // Signal 0 checks if process exists
            res.json({ running: true, pid, status: 'ready' });
            return;
          } catch {
            // Process doesn't exist, clean up files
            fs.unlinkSync(mcpPidfile);
            fs.unlinkSync(statusFile);
            res.json({ running: false });
            return;
          }
        }
      } else if (status === 'starting') {
        // MCP is still starting up
        res.json({ running: false, status: 'starting' });
        return;
      }
    }

    // Fallback to just PID check
    if (fs.existsSync(mcpPidfile)) {
      const pid = parseInt(fs.readFileSync(mcpPidfile, 'utf-8').trim());

      // Check if process is actually running
      try {
        process.kill(pid, 0); // Signal 0 checks if process exists
        res.json({ running: true, pid });
        return;
      } catch {
        // Process not running, clean up pidfile
        fs.unlinkSync(mcpPidfile);
      }
    }

    // Final fallback: Check for STDIO mode MCP server process
    try {
      const { exec } = require('child_process');
      const util = require('util');
      const execPromise = util.promisify(exec);
      const { stdout } = await execPromise('ps aux | grep -E "mcp-neo4j-cypher|uvx.*mcp" | grep -v grep');
      if (stdout && stdout.trim().length > 0) {
        logger.debug('Found MCP server running in STDIO mode');
        res.json({ running: true, status: 'stdio', mode: 'stdio' });
        return;
      }
    } catch (e) {
      // No process found
      logger.debug('No MCP process found');
    }

    res.json({ running: false });
  } catch (error) {
    logger.error('Failed to check MCP status', { error });
    res.json({ running: false, error: error instanceof Error ? error.message : 'Unknown error' });
  }
});

/**
 * Get environment configuration
 */
app.get('/api/config/env', (req, res) => {
  logger.debug('Config endpoint accessed');

  // Read from .env file if it exists
  const envPath = path.join(process.cwd(), '.env');
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

  // Merge with process.env (process.env takes precedence)
  const config = {
    AZURE_TENANT_ID: process.env.AZURE_TENANT_ID || envConfig.AZURE_TENANT_ID || '',
    AZURE_CLIENT_ID: process.env.AZURE_CLIENT_ID || envConfig.AZURE_CLIENT_ID || '',
    AZURE_CLIENT_SECRET: process.env.AZURE_CLIENT_SECRET || envConfig.AZURE_CLIENT_SECRET || '',
    NEO4J_PORT: process.env.NEO4J_PORT || envConfig.NEO4J_PORT || '7687',
    NEO4J_URI: process.env.NEO4J_URI || envConfig.NEO4J_URI || 'bolt://localhost:7687',
    NEO4J_USER: process.env.NEO4J_USER || envConfig.NEO4J_USER || 'neo4j',
    NEO4J_PASSWORD: process.env.NEO4J_PASSWORD || envConfig.NEO4J_PASSWORD || '',
    LOG_LEVEL: process.env.LOG_LEVEL || envConfig.LOG_LEVEL || 'INFO',
    AZURE_OPENAI_ENDPOINT: process.env.AZURE_OPENAI_ENDPOINT || envConfig.AZURE_OPENAI_ENDPOINT || '',
    AZURE_OPENAI_KEY: process.env.AZURE_OPENAI_KEY || envConfig.AZURE_OPENAI_KEY || '',
    AZURE_OPENAI_API_VERSION: process.env.AZURE_OPENAI_API_VERSION || envConfig.AZURE_OPENAI_API_VERSION || '2024-02-01',
    AZURE_OPENAI_MODEL_CHAT: process.env.AZURE_OPENAI_MODEL_CHAT || envConfig.AZURE_OPENAI_MODEL_CHAT || '',
    AZURE_OPENAI_MODEL_REASONING: process.env.AZURE_OPENAI_MODEL_REASONING || envConfig.AZURE_OPENAI_MODEL_REASONING || '',
    RESOURCE_LIMIT: process.env.RESOURCE_LIMIT || envConfig.RESOURCE_LIMIT || '',
  };

  res.json(config);
});

/**
 * Get markdown file content
 */
app.get('/api/docs/:filePath(*)', async (req, res) => {
  try {
    const filePath = decodeURIComponent(req.params.filePath);

    // Security: ensure the file is within the project directory
    // From spa/backend/src, we need to go up 3 levels to reach azure-tenant-grapher root
    const projectRoot = path.resolve(__dirname, '../../..');
    const fullFilePath = path.resolve(projectRoot, filePath);

    // Check if the resolved path is within the project directory
    if (!fullFilePath.startsWith(projectRoot)) {
      logger.warn('Docs API: Access denied - path outside project root', { filePath });
      return res.status(403).json({ error: 'Access denied' });
    }

    // Check if file exists and is a markdown file
    if (!fs.existsSync(fullFilePath)) {
      return res.status(404).json({ error: 'File not found', path: fullFilePath });
    }

    if (!fullFilePath.endsWith('.md')) {
      return res.status(400).json({ error: 'Only markdown files are supported' });
    }

    // Read file content
    const content = fs.readFileSync(fullFilePath, 'utf8');
    res.json(content);

  } catch (error) {
    logger.error('Error serving markdown file', { error });
    res.status(500).json({
      error: error instanceof Error ? error.message : 'Failed to read file'
    });
  }
});

/**
 * Check system dependencies
 */
app.get('/api/dependencies', async (req, res) => {
  const { exec } = require('child_process');
  const util = require('util');
  const execPromise = util.promisify(exec);

  const dependencies = [];

  // Check Python
  try {
    const { stdout } = await execPromise('python3 --version');
    const version = stdout.trim().split(' ')[1];
    dependencies.push({ name: 'Python', installed: true, version, required: '>=3.9' });
  } catch {
    dependencies.push({ name: 'Python', installed: false, required: '>=3.9' });
  }

  // Check Docker
  try {
    const { stdout } = await execPromise('docker --version');
    const version = stdout.match(/Docker version ([0-9.]+)/)?.[1] || 'unknown';
    dependencies.push({ name: 'Docker', installed: true, version, required: 'any' });
  } catch {
    dependencies.push({ name: 'Docker', installed: false, required: 'any' });
  }

  // Check Azure CLI - try multiple approaches
  let azInstalled = false;
  let azVersion = 'unknown';

  // Method 1: Try 'which az' command
  try {
    const { stdout: whichOutput } = await execPromise('which az');
    if (whichOutput && whichOutput.trim()) {
      // Found az in PATH, now get version (capture both stdout and stderr)
      try {
        const { stdout: versionOutput } = await execPromise('az --version 2>&1 | grep azure-cli | head -1');
        if (versionOutput && versionOutput.includes('azure-cli')) {
          azVersion = versionOutput.match(/azure-cli\s+([0-9.]+)/)?.[1] || 'unknown';
          azInstalled = true;
        }
      } catch {
        // Fallback: just check if az command exists
        azInstalled = true;
        azVersion = 'detected';
      }
    }
  } catch (error) {
    // Method 2: Try common installation paths
    const commonPaths = ['/usr/local/bin/az', '/opt/homebrew/bin/az', '/usr/bin/az'];

    for (const azPath of commonPaths) {
      try {
        // Check if file exists and is executable
        await execPromise(`test -x "${azPath}"`);
        // If we get here, the file exists and is executable
        const { stdout: versionOutput } = await execPromise(`"${azPath}" --version 2>&1 | grep azure-cli | head -1`);
        if (versionOutput && versionOutput.includes('azure-cli')) {
          azVersion = versionOutput.match(/azure-cli\s+([0-9.]+)/)?.[1] || 'unknown';
          azInstalled = true;
          break;
        } else {
          // File exists but couldn't get version - still mark as installed
          azInstalled = true;
          azVersion = 'detected';
          break;
        }
      } catch (pathError) {
        // Continue to next path
        continue;
      }
    }

    // Method 3: Last resort - try direct az command (might work even if which fails)
    if (!azInstalled) {
      try {
        const { stdout: directOutput } = await execPromise('az --version 2>&1 | head -1');
        if (directOutput && directOutput.includes('azure-cli')) {
          azVersion = directOutput.match(/azure-cli\s+([0-9.]+)/)?.[1] || 'unknown';
          azInstalled = true;
        }
      } catch (finalError) {
        // All methods failed
      }
    }
  }

  dependencies.push({
    name: 'Azure CLI',
    installed: azInstalled,
    version: azInstalled ? azVersion : undefined,
    required: '>=2.0'
  });

  // Check Neo4j - check if Docker container is running
  const neo4jStatus = await neo4jContainer.getStatus();
  dependencies.push({
    name: 'Neo4j',
    installed: neo4jStatus.running && (neo4jStatus.health === 'healthy' || neo4jStatus.health === 'starting'),
    version: neo4jStatus.version || '5.25.1', // Use actual version from container if available
    required: '>=5.0',
    status: neo4jStatus.health
  });

  // Check Terraform
  try {
    const { stdout } = await execPromise('terraform --version');
    const version = stdout.match(/Terraform v([0-9.]+)/)?.[1] || 'unknown';
    dependencies.push({ name: 'Terraform', installed: true, version, required: '>=1.0' });
  } catch {
    dependencies.push({ name: 'Terraform', installed: false, required: '>=1.0' });
  }

  res.json(dependencies);
});

/**
 * Health check endpoint
 */
app.get('/api/health', async (req, res) => {
  const neo4jStatus = await neo4jContainer.getStatus();
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    activeProcesses: activeProcesses.size,
    neo4j: neo4jStatus
  });
});

/**
 * Test Azure connection
 */
app.get('/api/test/azure', async (req, res) => {
  try {
    const { exec } = require('child_process');
    const { promisify } = require('util');
    const execPromise = promisify(exec);

    // Check if Azure CLI is installed
    try {
      await execPromise('which az');
    } catch {
      return res.json({ success: false, error: 'Azure CLI not installed' });
    }

    // Check current Azure authentication status
    try {
      const { stdout } = await execPromise('az account show --only-show-errors 2>&1');
      const account = JSON.parse(stdout);

      // Successfully got account info, we're authenticated
      return res.json({
        success: true,
        accountInfo: {
          name: account.name,
          id: account.id,
          tenantId: account.tenantId,
          user: account.user?.name || account.user?.type || 'Service Principal'
        }
      });
    } catch (error: any) {
      // Not authenticated, check if we have service principal credentials to try
      const tenantId = process.env.AZURE_TENANT_ID;
      const clientId = process.env.AZURE_CLIENT_ID;
      const clientSecret = process.env.AZURE_CLIENT_SECRET;

      if (tenantId && clientId && clientSecret) {
        // Try to authenticate with service principal
        try {
          await execPromise(`az login --service-principal -u ${clientId} -p ${clientSecret} --tenant ${tenantId} --only-show-errors 2>&1`);
          const { stdout } = await execPromise('az account show --only-show-errors 2>&1');
          const account = JSON.parse(stdout);
          return res.json({
            success: true,
            accountInfo: {
              name: account.name,
              id: account.id,
              tenantId: account.tenantId,
              user: 'Service Principal'
            }
          });
        } catch (loginError: any) {
          return res.json({ success: false, error: 'Failed to authenticate with service principal' });
        }
      } else {
        return res.json({ success: false, error: 'Not authenticated with Azure CLI' });
      }
    }
  } catch (error: any) {
    logger.error('Azure connection test failed', { error });
    res.json({ success: false, error: error.message });
  }
});

/**
 * Test Azure OpenAI connection
 */
app.get('/api/test/azure-openai', async (req, res) => {
  try {
    const endpoint = process.env.AZURE_OPENAI_ENDPOINT;
    const apiKey = process.env.AZURE_OPENAI_KEY;
    const apiVersion = process.env.AZURE_OPENAI_API_VERSION || '2024-02-01';
    const modelChat = process.env.AZURE_OPENAI_MODEL_CHAT;
    const modelReasoning = process.env.AZURE_OPENAI_MODEL_REASONING;

    logger.debug('Azure OpenAI config check:', {
      endpoint: endpoint ? 'SET' : 'NOT SET',
      apiKey: apiKey ? 'SET' : 'NOT SET',
      apiVersion,
      modelChat: modelChat || 'NOT SET',
      modelReasoning: modelReasoning || 'NOT SET'
    });

    if (!endpoint || !apiKey) {
      const missing = [];
      if (!endpoint) missing.push('AZURE_OPENAI_ENDPOINT');
      if (!apiKey) missing.push('AZURE_OPENAI_KEY');
      return res.json({
        success: false,
        error: `Azure OpenAI not configured. Missing: ${missing.join(', ')}`
      });
    }

    // Rate limiting: Only allow one test per 5 seconds per client IP
    const clientIp = req.ip || req.connection.remoteAddress || 'unknown';
    const rateLimitKey = `azure-openai-test:${clientIp}`;
    const now = Date.now();

    if (global.rateLimitCache && global.rateLimitCache[rateLimitKey]) {
      const lastRequest = global.rateLimitCache[rateLimitKey];
      const timeSinceLastRequest = now - lastRequest;
      if (timeSinceLastRequest < 5000) { // 5 seconds
        return res.status(429).json({
          success: false,
          error: `Rate limit exceeded. Please wait ${Math.ceil((5000 - timeSinceLastRequest) / 1000)} seconds before testing again.`
        });
      }
    }

    // Initialize rate limit cache if not exists
    if (!global.rateLimitCache) {
      global.rateLimitCache = {};
    }
    global.rateLimitCache[rateLimitKey] = now;

    // Test with actual API call - use the endpoint as configured
    try {
      // Determine the URL to use
      let url: string;
      let actualModel = modelChat || 'gpt-4';

      // If endpoint already contains /chat/completions, it's a full URL - use as-is
      if (endpoint.includes('/chat/completions')) {
        url = endpoint;
        // Extract model name from URL if possible (for display)
        const deploymentMatch = endpoint.match(/\/deployments\/([^\/]+)\//);
        if (deploymentMatch) {
          actualModel = deploymentMatch[1];
        }
      } else {
        // It's a base URL - construct the full URL
        // Map gpt-4.1 to gpt-4o (the actual deployment name)
        const deploymentName = modelChat === 'gpt-4.1' ? 'gpt-4o' : (modelChat || 'gpt-4');
        url = `${endpoint}/openai/deployments/${deploymentName}/chat/completions?api-version=${apiVersion}`;
      }

      logger.debug('Testing Azure OpenAI with URL', { url });

      // Make a test call with the joke prompt as specified in requirements
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'api-key': apiKey,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          messages: [{role: 'user', content: 'Tell me a joke about Microsoft Azure'}],
          max_tokens: 100,
          temperature: 0.7
        }),
        signal: AbortSignal.timeout(10000) // 10 second timeout for the API call
      });

      if (response.ok) {
        const data: any = await response.json();

        // Validate response structure
        if (!data || typeof data !== 'object') {
          logger.error('Invalid response structure from Azure OpenAI', { data });
          return res.json({
            success: false,
            error: 'Invalid response from Azure OpenAI API',
            configured: true
          });
        }

        const endpointHost = new URL(endpoint.includes('://') ? endpoint : `https://${endpoint}`).host;

        // Extract the joke response if available with validation
        let testResponse = 'Connection successful';
        if (data.choices &&
            Array.isArray(data.choices) &&
            data.choices.length > 0 &&
            data.choices[0].message &&
            typeof data.choices[0].message.content === 'string') {
          testResponse = data.choices[0].message.content || 'Connection successful';
        }

        // Sanitize response to prevent XSS
        testResponse = testResponse.replace(/[<>]/g, '').substring(0, 200);

        return res.json({
          success: true,
          message: 'Azure OpenAI is working correctly',
          endpoint: endpointHost,
          model: data.model || actualModel,
          models: {
            chat: modelChat || actualModel,
            reasoning: modelReasoning || 'Not configured'
          },
          testResponse
        });
      } else if (response.status === 401) {
        return res.json({ success: false, error: 'Invalid Azure OpenAI API key' });
      } else if (response.status === 404) {
        return res.json({
          success: false,
          error: `Model deployment '${actualModel}' not found`,
          configured: true
        });
      } else if (response.status === 429) {
        return res.json({
          success: false,
          error: 'Azure OpenAI rate limit exceeded. Please try again later.',
          configured: true
        });
      } else {
        const errorText = await response.text();
        logger.error(`Azure OpenAI test failed: ${response.status}`, { errorText });
        return res.json({
          success: false,
          error: `API test failed: ${response.status}`,
          configured: true
        });
      }
    } catch (error: any) {
      logger.error('Azure OpenAI API call failed', { error });
      return res.json({ success: false, error: `Failed to connect to Azure OpenAI: ${error.message}` });
    }
  } catch (error: any) {
    logger.error('Azure OpenAI connection test failed', { error });
    res.json({ success: false, error: error.message });
  }
});

/**
 * Check Microsoft Graph API permissions
 */
app.get('/api/test/graph-permissions', async (req, res) => {
  try {
    logger.debug('Checking Graph API permissions...');

    // Check if we have the required environment variables for service principal auth
    const tenantId = process.env.AZURE_TENANT_ID;
    const clientId = process.env.AZURE_CLIENT_ID;
    const clientSecret = process.env.AZURE_CLIENT_SECRET;

    const hasServicePrincipalAuth = tenantId && clientId && clientSecret;
    let accessToken = null;

    if (hasServicePrincipalAuth) {
      logger.debug('Testing Graph API permissions with service principal authentication');
    } else {
      logger.debug('Service principal credentials not found, attempting Azure CLI authentication');

      // Try to get access token from Azure CLI
      try {
        const { exec } = require('child_process');
        const { promisify } = require('util');
        const execPromise = promisify(exec);

        const { stdout } = await execPromise('az account get-access-token --resource https://graph.microsoft.com --query "accessToken" --output tsv', {
          timeout: 10000
        });
        accessToken = stdout.trim();
        logger.debug('Successfully obtained access token from Azure CLI');
      } catch (error: any) {
        logger.debug('Azure CLI authentication failed:', error.message);
        return res.json({
          success: false,
          error: 'No authentication method available. Please either:\n1. Set AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET environment variables, OR\n2. Login with Azure CLI (az login)',
          permissions: {
            users: false,
            groups: false,
            servicePrincipals: false,
            directoryRoles: false
          }
        });
      }
    }

    // Try to make actual Graph API calls to test permissions
    try {
      const permissions = {
        users: false,
        groups: false,
        servicePrincipals: false,
        directoryRoles: false
      };

      // Get access token for Microsoft Graph (if not already obtained from Azure CLI)
      if (!accessToken && hasServicePrincipalAuth) {
        const tokenUrl = `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/token`;
        const tokenResponse = await fetch(tokenUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
          body: new URLSearchParams({
            client_id: clientId,
            client_secret: clientSecret,
            scope: 'https://graph.microsoft.com/.default',
            grant_type: 'client_credentials'
          })
        });

        if (!tokenResponse.ok) {
          const tokenError = await tokenResponse.text();
          logger.error('Failed to get Graph API token', { tokenError });
          return res.json({
            success: false,
            error: 'Failed to authenticate with Microsoft Graph API. Check your service principal credentials.',
            permissions
          });
        }

        const tokenData: any = await tokenResponse.json();
        accessToken = tokenData.access_token;

        if (!accessToken) {
          return res.json({
            success: false,
            error: 'No access token received from Microsoft Graph API',
            permissions
          });
        }
      }

      const headers = {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      };

      // Test 1: Check if we can read users
      try {
        const usersResponse = await fetch('https://graph.microsoft.com/v1.0/users?$top=1', {
          headers,
          signal: AbortSignal.timeout(10000)
        });

        if (usersResponse.ok) {
          const usersData: any = await usersResponse.json();
          permissions.users = true;
          logger.debug(`✅ Can read users: ${usersData.value?.length || 0} users found`);
        } else if (usersResponse.status === 403) {
          logger.debug('❌ Cannot read users - insufficient permissions');
        } else {
          logger.debug(`❌ Cannot read users - error: ${usersResponse.status}`);
        }
      } catch (error) {
        logger.debug('❌ Cannot read users - network error', { error });
      }

      // Test 2: Check if we can read groups
      try {
        const groupsResponse = await fetch('https://graph.microsoft.com/v1.0/groups?$top=1', {
          headers,
          signal: AbortSignal.timeout(10000)
        });

        if (groupsResponse.ok) {
          const groupsData: any = await groupsResponse.json();
          permissions.groups = true;
          logger.debug(`✅ Can read groups: ${groupsData.value?.length || 0} groups found`);
        } else if (groupsResponse.status === 403) {
          logger.debug('❌ Cannot read groups - insufficient permissions');
        } else {
          logger.debug(`❌ Cannot read groups - error: ${groupsResponse.status}`);
        }
      } catch (error) {
        logger.debug('❌ Cannot read groups - network error', { error });
      }

      // Test 3: Check if we can read service principals
      try {
        const spResponse = await fetch('https://graph.microsoft.com/v1.0/servicePrincipals?$top=1', {
          headers,
          signal: AbortSignal.timeout(10000)
        });

        if (spResponse.ok) {
          const spData: any = await spResponse.json();
          permissions.servicePrincipals = true;
          logger.debug(`✅ Can read service principals: ${spData.value?.length || 0} service principals found`);
        } else if (spResponse.status === 403) {
          logger.debug('❌ Cannot read service principals - insufficient permissions');
        } else {
          logger.debug(`❌ Cannot read service principals - error: ${spResponse.status}`);
        }
      } catch (error) {
        logger.debug('❌ Cannot read service principals - network error', { error });
      }

      // Test 4: Check if we can read directory roles
      try {
        const rolesResponse = await fetch('https://graph.microsoft.com/v1.0/directoryRoles?$top=1', {
          headers,
          signal: AbortSignal.timeout(10000)
        });

        if (rolesResponse.ok) {
          const rolesData: any = await rolesResponse.json();
          permissions.directoryRoles = true;
          logger.debug(`✅ Can read directory roles: ${rolesData.value?.length || 0} roles found`);
        } else if (rolesResponse.status === 403) {
          logger.debug('❌ Cannot read directory roles - insufficient permissions');
        } else {
          logger.debug(`❌ Cannot read directory roles - error: ${rolesResponse.status}`);
        }
      } catch (error) {
        logger.debug('❌ Cannot read directory roles - network error', { error });
      }

      // Determine if user has sufficient permissions
      // Method 1: Has the basic required permissions (User.Read.All AND Group.Read.All)
      const hasBasicRequired = permissions.users && permissions.groups;

      // Method 2: Has Directory.Read.All (indicated by having servicePrincipals AND directoryRoles)
      const hasDirectoryReadAll = permissions.servicePrincipals && permissions.directoryRoles;

      // Method 3: Has mixed permissions that include core requirements + additional (likely Directory.Read.All)
      const hasSufficientMixed = (permissions.users || permissions.servicePrincipals) &&
                                 (permissions.groups || permissions.directoryRoles) &&
                                 (permissions.servicePrincipals || permissions.directoryRoles);

      const success = hasBasicRequired || hasDirectoryReadAll || hasSufficientMixed;

      let message = '';
      if (success) {
        if (hasBasicRequired) {
          message = 'Required Graph API permissions (User.Read.All, Group.Read.All) are configured';
        } else if (hasDirectoryReadAll) {
          message = 'Directory.Read.All permission detected - provides access to all required resources';
        } else {
          message = 'Sufficient Graph API permissions detected - can read required directory objects';
        }
      } else {
        const missing = [];
        const suggestions = [];

        if (!permissions.users && !permissions.servicePrincipals) {
          missing.push('User.Read.All');
        }
        if (!permissions.groups && !permissions.directoryRoles) {
          missing.push('Group.Read.All');
        }

        if (missing.length > 0) {
          suggestions.push(`Grant specific permissions: ${missing.join(', ')}`);
        }
        suggestions.push('Or grant Directory.Read.All for comprehensive access');

        message = `Insufficient Graph API permissions. ${suggestions.join(' ')}`;
      }

      return res.json({
        success,
        permissions,
        allRequired: success, // Updated to reflect the actual success status
        message,
        details: {
          authMethod: hasServicePrincipalAuth ? 'Service Principal' : 'Azure CLI',
          tenantId: tenantId || 'Unknown',
          clientId: hasServicePrincipalAuth && clientId ? clientId.substring(0, 8) + '...' : undefined,
          detectedPermissionLevel: hasDirectoryReadAll ? 'Directory.Read.All' :
                                   hasBasicRequired ? 'Specific (User+Group)' :
                                   hasSufficientMixed ? 'Mixed/Sufficient' : 'Insufficient'
        }
      });

    } catch (error: any) {
      logger.error('Graph API permissions test failed', { error });

      return res.json({
        success: false,
        error: `Failed to test Graph API permissions: ${error.message}`,
        permissions: {
          users: false,
          groups: false,
          servicePrincipals: false,
          directoryRoles: false
        }
      });
    }

  } catch (error: any) {
    logger.error('Graph API permissions check failed', { error });
    res.json({
      success: false,
      error: error.message,
      permissions: {
        users: false,
        groups: false,
        servicePrincipals: false,
        directoryRoles: false
      }
    });
  }
});

// ==================== Scale Operations API Routes ====================

/**
 * Execute scale-up operation
 */
app.post('/api/scale/up/execute', async (req, res) => {
  try {
    const { tenantId, strategy, validate, templateFile, scaleFactor, scenarioType, nodeCount, pattern } = req.body;

    if (!tenantId) {
      return res.status(400).json({ error: 'Tenant ID is required' });
    }

    const processId = uuidv4();
    const args = ['scale-up', '--tenant-id', tenantId, '--strategy', strategy];

    if (validate) {
      args.push('--validate');
    }

    if (strategy === 'template') {
      if (templateFile) args.push('--template-file', templateFile);
      if (scaleFactor) args.push('--scale-factor', scaleFactor.toString());
    } else if (strategy === 'scenario') {
      if (scenarioType) args.push('--scenario-type', scenarioType);
    } else if (strategy === 'random') {
      if (nodeCount) args.push('--node-count', nodeCount.toString());
      if (pattern) args.push('--pattern', pattern);
    }

    const uvPath = process.env.UV_PATH || 'uv';
    const projectRoot = path.resolve(__dirname, '../../..');
    const fullArgs = ['run', 'atg', ...args];

    logger.info('Starting scale-up operation', { processId, args });

    const childProcess = spawn(uvPath, fullArgs, {
      cwd: projectRoot,
      env: { ...process.env },
    });

    activeProcesses.set(processId, childProcess);

    childProcess.stdout.on('data', (data) => {
      const lines = data.toString().split('\n').filter((line: string) => line.trim());
      io.to(`process-${processId}`).emit('output', {
        processId,
        type: 'stdout',
        data: lines,
        timestamp: new Date().toISOString(),
      });
    });

    childProcess.stderr.on('data', (data) => {
      const lines = data.toString().split('\n').filter((line: string) => line.trim());
      io.to(`process-${processId}`).emit('output', {
        processId,
        type: 'stderr',
        data: lines,
        timestamp: new Date().toISOString(),
      });
    });

    childProcess.on('close', (code) => {
      io.to(`process-${processId}`).emit('process-exit', {
        processId,
        code,
        timestamp: new Date().toISOString(),
      });
      activeProcesses.delete(processId);
      logger.info('Scale-up operation completed', { processId, exitCode: code });
    });

    childProcess.on('error', (error) => {
      io.to(`process-${processId}`).emit('process-error', {
        processId,
        error: error.message,
        timestamp: new Date().toISOString(),
      });
      activeProcesses.delete(processId);
      logger.error('Scale-up operation failed', { processId, error });
    });

    res.json({ success: true, processId });
  } catch (error: any) {
    logger.error('Failed to start scale-up operation', { error });
    res.status(500).json({ error: error.message || 'Failed to start scale-up operation' });
  }
});

/**
 * Rate limiter for preview endpoint - 10 requests per minute per IP
 */
const previewRateLimiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute
  max: 10, // limit each IP to 10 requests per windowMs
  message: 'Too many preview requests, please try again later.',
  standardHeaders: true, // Return rate limit info in `RateLimit-*` headers
  legacyHeaders: false, // Disable the `X-RateLimit-*` headers
});

/**
 * Preview scale-up operation
 */
app.post('/api/scale/up/preview', previewRateLimiter, async (req, res) => {
  try {
    const { tenantId, strategy } = req.body;

    if (!tenantId) {
      return res.status(400).json({ error: 'Tenant ID is required' });
    }

    // Mock preview result for now - in production this would analyze the template/strategy
    res.json({
      estimatedNodes: strategy === 'template' ? 2500 : strategy === 'random' ? 1000 : 500,
      estimatedRelationships: strategy === 'template' ? 5000 : strategy === 'random' ? 2000 : 1000,
      estimatedDuration: 120,
      warnings: [],
      canProceed: true,
    });
  } catch (error: any) {
    logger.error('Failed to preview scale-up', { error });
    res.status(500).json({ error: error.message || 'Failed to preview scale-up' });
  }
});

/**
 * Execute scale-down operation
 */
app.post('/api/scale/down/execute', async (req, res) => {
  try {
    const {
      tenantId,
      algorithm,
      sampleSize,
      validate,
      outputMode,
      burnInSteps,
      forwardProbability,
      walkLength,
      pattern,
      outputPath,
      iacFormat,
      newTenantId,
      preserveRelationships,
      includeProperties,
    } = req.body;

    if (!tenantId) {
      return res.status(400).json({ error: 'Tenant ID is required' });
    }

    const processId = uuidv4();
    const args = ['scale-down', '--tenant-id', tenantId, '--algorithm', algorithm, '--sample-size', sampleSize.toString()];

    if (validate) {
      args.push('--validate');
    }

    if (algorithm === 'forest-fire') {
      if (burnInSteps) args.push('--burn-in', burnInSteps.toString());
      if (forwardProbability !== undefined) args.push('--forward-probability', forwardProbability.toString());
    } else if (algorithm === 'mhrw') {
      if (walkLength) args.push('--walk-length', walkLength.toString());
    } else if (algorithm === 'pattern') {
      if (pattern) args.push('--pattern', pattern);
    }

    if (outputMode === 'file' && outputPath) {
      args.push('--output-path', outputPath);
    } else if (outputMode === 'iac' && iacFormat) {
      args.push('--iac-format', iacFormat);
    } else if (outputMode === 'new-tenant' && newTenantId) {
      args.push('--new-tenant-id', newTenantId);
    }

    if (preserveRelationships) {
      args.push('--preserve-relationships');
    }

    if (includeProperties) {
      args.push('--include-properties');
    }

    const uvPath = process.env.UV_PATH || 'uv';
    const projectRoot = path.resolve(__dirname, '../../..');
    const fullArgs = ['run', 'atg', ...args];

    logger.info('Starting scale-down operation', { processId, args });

    const childProcess = spawn(uvPath, fullArgs, {
      cwd: projectRoot,
      env: { ...process.env },
    });

    activeProcesses.set(processId, childProcess);

    childProcess.stdout.on('data', (data) => {
      const lines = data.toString().split('\n').filter((line: string) => line.trim());
      io.to(`process-${processId}`).emit('output', {
        processId,
        type: 'stdout',
        data: lines,
        timestamp: new Date().toISOString(),
      });
    });

    childProcess.stderr.on('data', (data) => {
      const lines = data.toString().split('\n').filter((line: string) => line.trim());
      io.to(`process-${processId}`).emit('output', {
        processId,
        type: 'stderr',
        data: lines,
        timestamp: new Date().toISOString(),
      });
    });

    childProcess.on('close', (code) => {
      io.to(`process-${processId}`).emit('process-exit', {
        processId,
        code,
        timestamp: new Date().toISOString(),
      });
      activeProcesses.delete(processId);
      logger.info('Scale-down operation completed', { processId, exitCode: code });
    });

    childProcess.on('error', (error) => {
      io.to(`process-${processId}`).emit('process-error', {
        processId,
        error: error.message,
        timestamp: new Date().toISOString(),
      });
      activeProcesses.delete(processId);
      logger.error('Scale-down operation failed', { processId, error });
    });

    res.json({ success: true, processId });
  } catch (error: any) {
    logger.error('Failed to start scale-down operation', { error });
    res.status(500).json({ error: error.message || 'Failed to start scale-down operation' });
  }
});

/**
 * Preview scale-down operation
 */
app.post('/api/scale/down/preview', async (req, res) => {
  try {
    const { tenantId, sampleSize } = req.body;

    if (!tenantId) {
      return res.status(400).json({ error: 'Tenant ID is required' });
    }

    // Mock preview result for now
    res.json({
      estimatedNodes: sampleSize || 500,
      estimatedRelationships: (sampleSize || 500) * 2,
      estimatedDuration: 60,
      warnings: [],
      canProceed: true,
    });
  } catch (error: any) {
    logger.error('Failed to preview scale-down', { error });
    res.status(500).json({ error: error.message || 'Failed to preview scale-down' });
  }
});

/**
 * Cancel scale operation
 */
app.post('/api/scale/cancel/:processId', (req, res) => {
  try {
    const { processId } = req.params;
    const process = activeProcesses.get(processId);

    if (!process) {
      return res.status(404).json({ error: 'Process not found' });
    }

    process.kill('SIGTERM');
    activeProcesses.delete(processId);
    logger.info('Scale operation cancelled', { processId });

    res.json({ success: true });
  } catch (error: any) {
    logger.error('Failed to cancel operation', { error });
    res.status(500).json({ error: error.message || 'Failed to cancel operation' });
  }
});

/**
 * Clean synthetic data
 */
app.post('/api/scale/clean-synthetic', async (req, res) => {
  try {
    const { tenantId } = req.body;

    if (!tenantId) {
      return res.status(400).json({ error: 'Tenant ID is required' });
    }

    // Execute clean synthetic command
    const result = await neo4jService.query(
      `MATCH (n {synthetic: true, tenantId: $tenantId})
       OPTIONAL MATCH (n)-[r]-()
       WITH n, count(r) as relCount
       DETACH DELETE n
       RETURN count(n) as nodesDeleted, sum(relCount) as relationshipsDeleted`,
      { tenantId }
    );

    const nodesDeleted = result.records[0]?.get('nodesDeleted')?.toNumber() || 0;
    const relationshipsDeleted = result.records[0]?.get('relationshipsDeleted')?.toNumber() || 0;

    logger.info('Cleaned synthetic data', { tenantId, nodesDeleted, relationshipsDeleted });

    res.json({
      success: true,
      nodesDeleted,
      relationshipsDeleted,
    });
  } catch (error: any) {
    logger.error('Failed to clean synthetic data', { error });
    res.status(500).json({ error: error.message || 'Failed to clean synthetic data' });
  }
});

/**
 * Validate graph
 */
app.post('/api/scale/validate', async (req, res) => {
  try {
    const { tenantId } = req.body;

    if (!tenantId) {
      return res.status(400).json({ error: 'Tenant ID is required' });
    }

    const validationResults = [];

    // Check for orphaned nodes
    const orphanedCheck = await neo4jService.query(
      `MATCH (n {tenantId: $tenantId})
       WHERE NOT (n)-[]-()
       RETURN count(n) as orphanedCount`,
      { tenantId }
    );
    const orphanedCount = orphanedCheck.records[0]?.get('orphanedCount')?.toNumber() || 0;
    validationResults.push({
      checkName: 'Orphaned Nodes',
      passed: orphanedCount === 0,
      message: orphanedCount === 0 ? 'No orphaned nodes found' : `Found ${orphanedCount} orphaned nodes`,
    });

    // Check for broken relationships
    const brokenRelCheck = await neo4jService.query(
      `MATCH (n {tenantId: $tenantId})-[r]->(m)
       WHERE m.tenantId IS NULL OR m.tenantId <> $tenantId
       RETURN count(r) as brokenCount`,
      { tenantId }
    );
    const brokenCount = brokenRelCheck.records[0]?.get('brokenCount')?.toNumber() || 0;
    validationResults.push({
      checkName: 'Relationship Integrity',
      passed: brokenCount === 0,
      message: brokenCount === 0 ? 'All relationships are valid' : `Found ${brokenCount} broken relationships`,
    });

    // Check synthetic node labeling
    const syntheticCheck = await neo4jService.query(
      `MATCH (n {tenantId: $tenantId, synthetic: true})
       WHERE NOT 'Synthetic' IN labels(n)
       RETURN count(n) as unlabeledCount`,
      { tenantId }
    );
    const unlabeledCount = syntheticCheck.records[0]?.get('unlabeledCount')?.toNumber() || 0;
    validationResults.push({
      checkName: 'Synthetic Node Labeling',
      passed: unlabeledCount === 0,
      message: unlabeledCount === 0 ? 'All synthetic nodes properly labeled' : `Found ${unlabeledCount} improperly labeled synthetic nodes`,
    });

    logger.info('Graph validation completed', { tenantId, validationResults });

    res.json(validationResults);
  } catch (error: any) {
    logger.error('Failed to validate graph', { error });
    res.status(500).json({ error: error.message || 'Failed to validate graph' });
  }
});

/**
 * Get graph statistics
 */
app.get('/api/scale/stats/:tenantId', async (req, res) => {
  try {
    const { tenantId } = req.params;

    if (!tenantId) {
      return res.status(400).json({ error: 'Tenant ID is required' });
    }

    // Get node counts
    const nodeStatsResult = await neo4jService.query(
      `MATCH (n {tenantId: $tenantId})
       OPTIONAL MATCH (s {tenantId: $tenantId, synthetic: true})
       RETURN count(n) as totalNodes, count(s) as syntheticNodes`,
      { tenantId }
    );

    const totalNodes = nodeStatsResult.records[0]?.get('totalNodes')?.toNumber() || 0;
    const syntheticNodes = nodeStatsResult.records[0]?.get('syntheticNodes')?.toNumber() || 0;

    // Get relationship count
    const relStatsResult = await neo4jService.query(
      `MATCH ({tenantId: $tenantId})-[r]->({tenantId: $tenantId})
       RETURN count(r) as totalRelationships`,
      { tenantId }
    );

    const totalRelationships = relStatsResult.records[0]?.get('totalRelationships')?.toNumber() || 0;

    // Get node type distribution
    const nodeTypesResult = await neo4jService.query(
      `MATCH (n {tenantId: $tenantId})
       UNWIND labels(n) as label
       WITH label, count(*) as count
       WHERE label <> 'Synthetic'
       RETURN label, count
       ORDER BY count DESC`,
      { tenantId }
    );

    const nodeTypes: Record<string, number> = {};
    nodeTypesResult.records.forEach(record => {
      nodeTypes[record.get('label')] = record.get('count').toNumber();
    });

    // Get relationship type distribution
    const relTypesResult = await neo4jService.query(
      `MATCH ({tenantId: $tenantId})-[r]->({tenantId: $tenantId})
       RETURN type(r) as relType, count(*) as count
       ORDER BY count DESC`,
      { tenantId }
    );

    const relationshipTypes: Record<string, number> = {};
    relTypesResult.records.forEach(record => {
      relationshipTypes[record.get('relType')] = record.get('count').toNumber();
    });

    res.json({
      totalNodes,
      totalRelationships,
      syntheticNodes,
      nodeTypes,
      relationshipTypes,
      lastUpdate: new Date().toISOString(),
    });
  } catch (error: any) {
    logger.error('Failed to get graph statistics', { error });
    res.status(500).json({ error: error.message || 'Failed to get graph statistics' });
  }
});

// ==================== End Scale Operations Routes ====================

// ==================== Layer Management API Routes ====================

/**
 * List all layers
 */
app.get('/api/layers', async (req, res) => {
  try {
    const result = await neo4jService.query(
      `MATCH (l:Layer)
       RETURN l
       ORDER BY l.created_at DESC`
    );

    const layers = result.records.map((record: any) => {
      const node = record.get('l');
      return {
        layer_id: node.properties.layer_id,
        name: node.properties.name,
        description: node.properties.description,
        created_at: node.properties.created_at,
        updated_at: node.properties.updated_at,
        created_by: node.properties.created_by,
        parent_layer_id: node.properties.parent_layer_id,
        is_active: node.properties.is_active || false,
        is_baseline: node.properties.is_baseline || false,
        is_locked: node.properties.is_locked || false,
        tenant_id: node.properties.tenant_id,
        subscription_ids: node.properties.subscription_ids || [],
        node_count: node.properties.node_count || 0,
        relationship_count: node.properties.relationship_count || 0,
        layer_type: node.properties.layer_type || 'experimental',
        metadata: JSON.parse(node.properties.metadata || '{}'),
        tags: node.properties.tags || [],
      };
    });

    res.json({ layers, total: layers.length });
  } catch (error: any) {
    logger.error('Failed to list layers', { error });
    res.status(500).json({ error: error.message || 'Failed to list layers' });
  }
});

/**
 * Get active layer
 */
app.get('/api/layers/active', async (req, res) => {
  try {
    const { tenantId } = req.query;

    let query = `MATCH (l:Layer) WHERE l.is_active = true`;
    const params: any = {};

    if (tenantId) {
      query += ` AND l.tenant_id = $tenantId`;
      params.tenantId = tenantId;
    }

    query += ` RETURN l LIMIT 1`;

    const result = await neo4jService.query(query, params);

    if (result.records.length === 0) {
      return res.json({ layer: null });
    }

    const node = result.records[0].get('l');
    const layer = {
      layer_id: node.properties.layer_id,
      name: node.properties.name,
      description: node.properties.description,
      created_at: node.properties.created_at,
      updated_at: node.properties.updated_at,
      created_by: node.properties.created_by,
      parent_layer_id: node.properties.parent_layer_id,
      is_active: node.properties.is_active || false,
      is_baseline: node.properties.is_baseline || false,
      is_locked: node.properties.is_locked || false,
      tenant_id: node.properties.tenant_id,
      subscription_ids: node.properties.subscription_ids || [],
      node_count: node.properties.node_count || 0,
      relationship_count: node.properties.relationship_count || 0,
      layer_type: node.properties.layer_type || 'experimental',
      metadata: JSON.parse(node.properties.metadata || '{}'),
      tags: node.properties.tags || [],
    };

    res.json({ layer });
  } catch (error: any) {
    logger.error('Failed to get active layer', { error });
    res.status(500).json({ error: error.message || 'Failed to get active layer' });
  }
});

/**
 * Get specific layer
 */
app.get('/api/layers/:layerId', async (req, res) => {
  try {
    const { layerId } = req.params;

    const result = await neo4jService.query(
      `MATCH (l:Layer {layer_id: $layerId})
       RETURN l`,
      { layerId }
    );

    if (result.records.length === 0) {
      return res.status(404).json({ error: 'Layer not found' });
    }

    const node = result.records[0].get('l');
    const layer = {
      layer_id: node.properties.layer_id,
      name: node.properties.name,
      description: node.properties.description,
      created_at: node.properties.created_at,
      updated_at: node.properties.updated_at,
      created_by: node.properties.created_by,
      parent_layer_id: node.properties.parent_layer_id,
      is_active: node.properties.is_active || false,
      is_baseline: node.properties.is_baseline || false,
      is_locked: node.properties.is_locked || false,
      tenant_id: node.properties.tenant_id,
      subscription_ids: node.properties.subscription_ids || [],
      node_count: node.properties.node_count || 0,
      relationship_count: node.properties.relationship_count || 0,
      layer_type: node.properties.layer_type || 'experimental',
      metadata: JSON.parse(node.properties.metadata || '{}'),
      tags: node.properties.tags || [],
    };

    res.json({ layer });
  } catch (error: any) {
    logger.error('Failed to get layer', { error });
    res.status(500).json({ error: error.message || 'Failed to get layer' });
  }
});

/**
 * Create new layer
 */
app.post('/api/layers', async (req, res) => {
  try {
    const {
      layer_id,
      name,
      description,
      layer_type = 'experimental',
      tenant_id = 'unknown',
      created_by = 'ui',
      parent_layer_id = null,
      make_active = false,
    } = req.body;

    if (!layer_id || !name) {
      return res.status(400).json({ error: 'layer_id and name are required' });
    }

    // Check if layer already exists
    const existingResult = await neo4jService.query(
      `MATCH (l:Layer {layer_id: $layerId}) RETURN l`,
      { layerId: layer_id }
    );

    if (existingResult.records.length > 0) {
      return res.status(409).json({ error: 'Layer already exists' });
    }

    // Deactivate current active layer if make_active=true
    if (make_active) {
      await neo4jService.query(
        `MATCH (l:Layer)
         WHERE l.is_active = true
         SET l.is_active = false, l.updated_at = datetime()`
      );
    }

    // Create new layer
    const createdAt = new Date().toISOString();
    const result = await neo4jService.query(
      `CREATE (l:Layer {
         layer_id: $layer_id,
         name: $name,
         description: $description,
         created_at: $created_at,
         updated_at: null,
         created_by: $created_by,
         parent_layer_id: $parent_layer_id,
         is_active: $is_active,
         is_baseline: $is_baseline,
         is_locked: false,
         tenant_id: $tenant_id,
         subscription_ids: [],
         node_count: 0,
         relationship_count: 0,
         layer_type: $layer_type,
         metadata: $metadata,
         tags: []
       })
       RETURN l`,
      {
        layer_id,
        name,
        description: description || `Layer created at ${new Date().toLocaleString()}`,
        created_at: createdAt,
        created_by,
        parent_layer_id,
        is_active: make_active,
        is_baseline: layer_type === 'baseline',
        tenant_id,
        layer_type,
        metadata: JSON.stringify({}),
      }
    );

    const node = result.records[0].get('l');
    const layer = {
      layer_id: node.properties.layer_id,
      name: node.properties.name,
      description: node.properties.description,
      created_at: node.properties.created_at,
      updated_at: node.properties.updated_at,
      created_by: node.properties.created_by,
      parent_layer_id: node.properties.parent_layer_id,
      is_active: node.properties.is_active || false,
      is_baseline: node.properties.is_baseline || false,
      is_locked: node.properties.is_locked || false,
      tenant_id: node.properties.tenant_id,
      subscription_ids: node.properties.subscription_ids || [],
      node_count: node.properties.node_count || 0,
      relationship_count: node.properties.relationship_count || 0,
      layer_type: node.properties.layer_type || 'experimental',
      metadata: JSON.parse(node.properties.metadata || '{}'),
      tags: node.properties.tags || [],
    };

    logger.info(`Created layer: ${layer_id}`);
    res.status(201).json({ layer });
  } catch (error: any) {
    logger.error('Failed to create layer', { error });
    res.status(500).json({ error: error.message || 'Failed to create layer' });
  }
});

/**
 * Activate a layer
 */
app.post('/api/layers/:layerId/activate', async (req, res) => {
  try {
    const { layerId } = req.params;

    // Check if layer exists
    const existingResult = await neo4jService.query(
      `MATCH (l:Layer {layer_id: $layerId}) RETURN l`,
      { layerId }
    );

    if (existingResult.records.length === 0) {
      return res.status(404).json({ error: 'Layer not found' });
    }

    // Deactivate all layers
    await neo4jService.query(
      `MATCH (l:Layer)
       WHERE l.is_active = true
       SET l.is_active = false, l.updated_at = datetime()`
    );

    // Activate target layer
    const result = await neo4jService.query(
      `MATCH (l:Layer {layer_id: $layerId})
       SET l.is_active = true, l.updated_at = datetime()
       RETURN l`,
      { layerId }
    );

    const node = result.records[0].get('l');
    const layer = {
      layer_id: node.properties.layer_id,
      name: node.properties.name,
      description: node.properties.description,
      created_at: node.properties.created_at,
      updated_at: node.properties.updated_at,
      created_by: node.properties.created_by,
      parent_layer_id: node.properties.parent_layer_id,
      is_active: true,
      is_baseline: node.properties.is_baseline || false,
      is_locked: node.properties.is_locked || false,
      tenant_id: node.properties.tenant_id,
      subscription_ids: node.properties.subscription_ids || [],
      node_count: node.properties.node_count || 0,
      relationship_count: node.properties.relationship_count || 0,
      layer_type: node.properties.layer_type || 'experimental',
      metadata: JSON.parse(node.properties.metadata || '{}'),
      tags: node.properties.tags || [],
    };

    logger.info(`Activated layer: ${layerId}`);
    res.json({ layer });
  } catch (error: any) {
    logger.error('Failed to activate layer', { error });
    res.status(500).json({ error: error.message || 'Failed to activate layer' });
  }
});

/**
 * Delete a layer
 */
app.delete('/api/layers/:layerId', async (req, res) => {
  try {
    const { layerId } = req.params;
    const { force = false } = req.query;

    // Check if layer exists
    const existingResult = await neo4jService.query(
      `MATCH (l:Layer {layer_id: $layerId}) RETURN l`,
      { layerId }
    );

    if (existingResult.records.length === 0) {
      return res.status(404).json({ error: 'Layer not found' });
    }

    const node = existingResult.records[0].get('l');
    const isActive = node.properties.is_active;
    const isBaseline = node.properties.is_baseline;
    const isLocked = node.properties.is_locked;

    // Check protections
    if (isLocked) {
      return res.status(403).json({ error: 'Layer is locked and cannot be deleted' });
    }

    if ((isActive || isBaseline) && force !== 'true') {
      return res.status(403).json({
        error: 'Cannot delete active or baseline layer without force=true',
        is_active: isActive,
        is_baseline: isBaseline,
      });
    }

    // Delete all Resource nodes in this layer
    await neo4jService.query(
      `MATCH (r:Resource)
       WHERE NOT r:Original AND r.layer_id = $layerId
       DETACH DELETE r`,
      { layerId }
    );

    // Delete layer metadata node
    await neo4jService.query(
      `MATCH (l:Layer {layer_id: $layerId})
       DETACH DELETE l`,
      { layerId }
    );

    logger.info(`Deleted layer: ${layerId}`);
    res.json({ success: true, message: `Layer ${layerId} deleted` });
  } catch (error: any) {
    logger.error('Failed to delete layer', { error });
    res.status(500).json({ error: error.message || 'Failed to delete layer' });
  }
});

/**
 * Update layer metadata
 */
app.patch('/api/layers/:layerId', async (req, res) => {
  try {
    const { layerId } = req.params;
    const { name, description, tags, is_locked } = req.body;

    // Check if layer exists
    const existingResult = await neo4jService.query(
      `MATCH (l:Layer {layer_id: $layerId}) RETURN l`,
      { layerId }
    );

    if (existingResult.records.length === 0) {
      return res.status(404).json({ error: 'Layer not found' });
    }

    // Build SET clauses
    const setClauses = ['l.updated_at = datetime()'];
    const params: any = { layerId };

    if (name !== undefined) {
      setClauses.push('l.name = $name');
      params.name = name;
    }

    if (description !== undefined) {
      setClauses.push('l.description = $description');
      params.description = description;
    }

    if (tags !== undefined) {
      setClauses.push('l.tags = $tags');
      params.tags = tags;
    }

    if (is_locked !== undefined) {
      setClauses.push('l.is_locked = $is_locked');
      params.is_locked = is_locked;
    }

    // Update layer
    const result = await neo4jService.query(
      `MATCH (l:Layer {layer_id: $layerId})
       SET ${setClauses.join(', ')}
       RETURN l`,
      params
    );

    const node = result.records[0].get('l');
    const layer = {
      layer_id: node.properties.layer_id,
      name: node.properties.name,
      description: node.properties.description,
      created_at: node.properties.created_at,
      updated_at: node.properties.updated_at,
      created_by: node.properties.created_by,
      parent_layer_id: node.properties.parent_layer_id,
      is_active: node.properties.is_active || false,
      is_baseline: node.properties.is_baseline || false,
      is_locked: node.properties.is_locked || false,
      tenant_id: node.properties.tenant_id,
      subscription_ids: node.properties.subscription_ids || [],
      node_count: node.properties.node_count || 0,
      relationship_count: node.properties.relationship_count || 0,
      layer_type: node.properties.layer_type || 'experimental',
      metadata: JSON.parse(node.properties.metadata || '{}'),
      tags: node.properties.tags || [],
    };

    logger.info(`Updated layer: ${layerId}`);
    res.json({ layer });
  } catch (error: any) {
    logger.error('Failed to update layer', { error });
    res.status(500).json({ error: error.message || 'Failed to update layer' });
  }
});

/**
 * Refresh layer statistics
 */
app.post('/api/layers/:layerId/refresh-stats', async (req, res) => {
  try {
    const { layerId } = req.params;

    // Count nodes
    const nodeResult = await neo4jService.query(
      `MATCH (r:Resource)
       WHERE NOT r:Original AND r.layer_id = $layerId
       RETURN count(r) as count`,
      { layerId }
    );
    const nodeCount = nodeResult.records[0]?.get('count')?.toNumber() || 0;

    // Count relationships
    const relResult = await neo4jService.query(
      `MATCH (r1:Resource)-[rel]->(r2:Resource)
       WHERE NOT r1:Original AND NOT r2:Original
         AND r1.layer_id = $layerId
         AND r2.layer_id = $layerId
         AND type(rel) <> 'SCAN_SOURCE_NODE'
       RETURN count(rel) as count`,
      { layerId }
    );
    const relCount = relResult.records[0]?.get('count')?.toNumber() || 0;

    // Update layer metadata
    const result = await neo4jService.query(
      `MATCH (l:Layer {layer_id: $layerId})
       SET l.node_count = $nodeCount,
           l.relationship_count = $relCount,
           l.updated_at = datetime()
       RETURN l`,
      { layerId, nodeCount, relCount }
    );

    if (result.records.length === 0) {
      return res.status(404).json({ error: 'Layer not found' });
    }

    const node = result.records[0].get('l');
    const layer = {
      layer_id: node.properties.layer_id,
      name: node.properties.name,
      description: node.properties.description,
      created_at: node.properties.created_at,
      updated_at: node.properties.updated_at,
      created_by: node.properties.created_by,
      parent_layer_id: node.properties.parent_layer_id,
      is_active: node.properties.is_active || false,
      is_baseline: node.properties.is_baseline || false,
      is_locked: node.properties.is_locked || false,
      tenant_id: node.properties.tenant_id,
      subscription_ids: node.properties.subscription_ids || [],
      node_count: nodeCount,
      relationship_count: relCount,
      layer_type: node.properties.layer_type || 'experimental',
      metadata: JSON.parse(node.properties.metadata || '{}'),
      tags: node.properties.tags || [],
    };

    logger.info(`Refreshed stats for layer ${layerId}: ${nodeCount} nodes, ${relCount} relationships`);
    res.json({ layer });
  } catch (error: any) {
    logger.error('Failed to refresh layer stats', { error });
    res.status(500).json({ error: error.message || 'Failed to refresh layer stats' });
  }
});

// ==================== End Layer Management Routes ====================

// Error handling middleware
app.use((err: any, req: express.Request, res: express.Response, next: express.NextFunction) => {
  logger.error('Internal server error', { err });
  res.status(500).json({ error: 'Internal server error' });
});

// Cleanup on exit
process.on('SIGINT', async () => {
  logger.info('Shutting down server...');
  activeProcesses.forEach((process) => {
    process.kill('SIGTERM');
  });
  await neo4jService.close();
  process.exit(0);
});

const PORT = process.env.BACKEND_PORT || 3001;

// Start the server and initialize Neo4j
async function startServer() {
  try {
    // Start Neo4j container first
    logger.info('Starting Neo4j container...');
    await neo4jContainer.start();
    logger.info('Neo4j container is ready');

    // Re-initialize Neo4j service connection after container is ready
    setTimeout(() => {
      // Give Neo4j service a moment to reconnect
      logger.debug('Neo4j service should now be connected');
    }, 2000);

  } catch (error) {
    logger.error('Failed to start Neo4j container', { error });
    logger.warn('Continuing without Neo4j - some features may not work');
  }

  // Start the HTTP server
  httpServer.listen(PORT, () => {
    logger.info(`Backend server running on http://localhost:${PORT}`);
    logger.info('WebSocket server ready for connections');
  });
}

// Start everything
startServer();
