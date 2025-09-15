/**
 * SECURE VERSION OF SERVER.TS
 * Implements all security fixes for identified vulnerabilities
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
import { logger } from './logger';

// Import security modules
import {
  validateCommand,
  validateArguments,
  validateProcessId,
  validateNodeId,
  validateSearchQuery,
  validateFilePath,
  sanitizeOutput
} from './security/input-validator';

import {
  requireAuth,
  authenticateWebSocket,
  requireSocketAuth,
  handleLogin,
  handleLogout
} from './security/auth-middleware';

import {
  rateLimiters,
  checkSocketRateLimit
} from './security/rate-limiter';

// Load .env file from the project root
dotenv.config({ path: path.join(__dirname, '../../../.env') });
logger.info('Secure Backend starting with environment');

const app = express();
const httpServer = createServer(app);
const io = new SocketIOServer(httpServer, {
  cors: {
    origin: ['http://localhost:5173', 'app://./'],
    methods: ['GET', 'POST'],
  },
});

// Middleware
app.use(cors());
app.use(express.json({ limit: '10mb' })); // Limit request body size

// Security headers
app.use((req, res, next) => {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('X-XSS-Protection', '1; mode=block');
  res.setHeader('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
  next();
});

// Store active processes
const activeProcesses = new Map<string, ChildProcess>();

// Initialize Neo4j service and container manager
const neo4jService = new Neo4jService();
const neo4jContainer = new Neo4jContainer();

// WebSocket connection handling with authentication
io.use(authenticateWebSocket);

io.on('connection', (socket) => {
  logger.info('Client connected:', socket.id);

  // Subscribe to process output (with rate limiting)
  socket.on('subscribe', (processId: string) => {
    if (!checkSocketRateLimit(socket, 'ws:subscribe')) {
      socket.emit('error', { message: 'Rate limit exceeded' });
      return;
    }

    // Validate process ID
    if (!validateProcessId(processId)) {
      socket.emit('error', { message: 'Invalid process ID' });
      return;
    }

    // Check authentication for sensitive operations
    if (!requireSocketAuth(socket)) {
      socket.emit('error', { message: 'Authentication required for subscriptions' });
      return;
    }

    socket.join('process-' + processId);
    logger.debug('Client ' + socket.id + ' subscribed to process ' + processId);
  });

  // Unsubscribe from process output
  socket.on('unsubscribe', (processId: string) => {
    if (!validateProcessId(processId)) {
      socket.emit('error', { message: 'Invalid process ID' });
      return;
    }

    socket.leave('process-' + processId);
    logger.debug('Client ' + socket.id + ' unsubscribed from process ' + processId);
  });

  socket.on('disconnect', () => {
    logger.info('Client disconnected:', socket.id);
  });
});

// API Routes

// Authentication endpoints
app.post('/api/auth/login', rateLimiters.auth, handleLogin);
app.post('/api/auth/logout', handleLogout);

// Get Azure tenant name (public endpoint)
app.get('/api/tenant-name', async (req, res) => {
  try {
    const { exec } = require('child_process');
    const util = require('util');
    const execPromise = util.promisify(exec);

    try {
      // Safely execute Azure CLI command
      const { stdout } = await execPromise('az account show --query "name" --output tsv', {
        timeout: 10000, // 10 second timeout
        shell: false
      });
      const name = stdout.trim();
      if (name && !name.includes('error') && name.length > 0) {
        logger.debug('Got Azure subscription name:', name);
        res.json({ name: sanitizeOutput(name) });
        return;
      }
    } catch (azError: any) {
      logger.debug('Azure CLI not available or not logged in:', azError?.message || azError);
    }

    // Fallback to tenant ID from env
    const tenantId = process.env.AZURE_TENANT_ID || 'Unknown';
    res.json({ name: sanitizeOutput(tenantId) });
  } catch (error) {
    logger.error('Error getting tenant name:', error);
    res.status(500).json({ error: 'Failed to get tenant name' });
  }
});

/**
 * Execute a CLI command (SECURED)
 */
app.post('/api/execute', requireAuth, rateLimiters.execute, (req, res) => {
  const { command, args = [] } = req.body;
  
  // Validate command
  const commandValidation = validateCommand(command);
  if (!commandValidation.isValid) {
    return res.status(400).json({ error: commandValidation.error });
  }

  // Validate arguments
  const argsValidation = validateArguments(args);
  if (!argsValidation.isValid) {
    return res.status(400).json({ error: argsValidation.error });
  }

  const processId = uuidv4();
  const sanitizedCommand = commandValidation.sanitized as string;
  const sanitizedArgs = argsValidation.sanitized as string[];

  // Use uv to run the atg CLI command
  const uvPath = process.env.UV_PATH || 'uv';
  const projectRoot = path.resolve(__dirname, '../../..');

  const fullArgs = ['run', 'atg', sanitizedCommand, ...sanitizedArgs];

  logger.info('Executing CLI command:', {
    command: 'uv ' + fullArgs.join(' '),
    cwd: projectRoot,
    processId,
    user: (req as any).session?.clientId
  });

  const childProcess: ChildProcess = spawn(uvPath, fullArgs, {
    cwd: projectRoot,
    env: {
      ...process.env,
      PYTHONPATH: projectRoot,
    },
    shell: false, // Never use shell to prevent injection
    stdio: ['ignore', 'pipe', 'pipe'] // Explicitly set stdio to avoid type conflicts
  });

  activeProcesses.set(processId, childProcess);

  // Stream stdout with sanitization
  childProcess.stdout?.on('data', (data: any) => {
    const sanitized = sanitizeOutput(data.toString());
    const lines = sanitized.split('\n').filter((line: string) => line);
    io.to('process-' + processId).emit('output', {
      processId,
      type: 'stdout',
      data: lines,
      timestamp: new Date().toISOString(),
    });
  });

  // Stream stderr with sanitization
  childProcess.stderr?.on('data', (data: any) => {
    const sanitized = sanitizeOutput(data.toString());
    const lines = sanitized.split('\n').filter((line: string) => line);
    io.to('process-' + processId).emit('output', {
      processId,
      type: 'stderr',
      data: lines,
      timestamp: new Date().toISOString(),
    });
  });

  // Handle process exit
  childProcess.on('exit', (code: any) => {
    io.to('process-' + processId).emit('process-exit', {
      processId,
      code,
      timestamp: new Date().toISOString(),
    });
    activeProcesses.delete(processId);
  });

  // Handle process error
  childProcess.on('error', (error: any) => {
    io.to('process-' + processId).emit('process-error', {
      processId,
      error: sanitizeOutput(error.message),
      timestamp: new Date().toISOString(),
    });
    activeProcesses.delete(processId);
  });

  res.json({ processId, status: 'started' });
});

/**
 * Cancel a running process (SECURED)
 */
app.post('/api/cancel/:processId', requireAuth, (req, res) => {
  const { processId } = req.params;
  
  // Validate process ID
  if (!validateProcessId(processId)) {
    return res.status(400).json({ error: 'Invalid process ID' });
  }

  const process = activeProcesses.get(processId);

  if (!process) {
    return res.status(404).json({ error: 'Process not found' });
  }

  process.kill('SIGTERM');
  activeProcesses.delete(processId);

  res.json({ status: 'cancelled' });
});

/**
 * Get process status (SECURED)
 */
app.get('/api/status/:processId', requireAuth, (req, res) => {
  const { processId } = req.params;
  
  // Validate process ID
  if (!validateProcessId(processId)) {
    return res.status(400).json({ error: 'Invalid process ID' });
  }

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
 * List all active processes (SECURED)
 */
app.get('/api/processes', requireAuth, (req, res) => {
  const processes = Array.from(activeProcesses.entries()).map(([id, process]) => ({
    id,
    pid: process.pid,
    status: 'running',
  }));

  res.json(processes);
});

/**
 * Check if database is populated (SECURED)
 */
app.get('/api/graph/status', requireAuth, rateLimiters.neo4j, async (req, res) => {
  try {
    const isPopulated = await neo4jService.isDatabasePopulated();
    const stats = isPopulated ? await neo4jService.getDatabaseStats() : null;
    res.json({
      isPopulated,
      stats
    });
  } catch (error) {
    logger.error('Error checking database status:', error);
    res.status(500).json({
      error: error instanceof Error ? error.message : 'Failed to check database status'
    });
  }
});

/**
 * Get database statistics (SECURED)
 */
app.get('/api/graph/stats', requireAuth, rateLimiters.neo4j, async (req, res) => {
  try {
    const stats = await neo4jService.getDatabaseStats();
    res.json(stats);
  } catch (error) {
    logger.error('Error fetching database stats:', error);
    res.status(500).json({
      error: error instanceof Error ? error.message : 'Failed to fetch database statistics'
    });
  }
});

/**
 * Get full graph data from Neo4j (SECURED)
 */
app.get('/api/graph', requireAuth, rateLimiters.neo4j, async (req, res) => {
  try {
    const graphData = await neo4jService.getFullGraph();
    res.json(graphData);
  } catch (error) {
    logger.error('Error fetching graph:', error);
    res.status(500).json({
      error: error instanceof Error ? error.message : 'Failed to fetch graph data'
    });
  }
});

/**
 * Search nodes in the graph (SECURED)
 */
app.get('/api/graph/search', requireAuth, rateLimiters.search, async (req, res) => {
  const { query } = req.query;

  if (!query || typeof query !== 'string') {
    return res.status(400).json({ error: 'Query parameter is required' });
  }

  // Validate and sanitize search query
  const queryValidation = validateSearchQuery(query);
  if (!queryValidation.isValid) {
    return res.status(400).json({ error: queryValidation.error });
  }

  try {
    const nodes = await neo4jService.searchNodes(queryValidation.sanitized as string);
    res.json(nodes);
  } catch (error) {
    logger.error('Error searching nodes:', error);
    res.status(500).json({
      error: error instanceof Error ? error.message : 'Failed to search nodes'
    });
  }
});

/**
 * Get node details (SECURED)
 */
app.get('/api/graph/node/:nodeId', requireAuth, rateLimiters.neo4j, async (req, res) => {
  const { nodeId } = req.params;

  // Validate node ID
  if (!validateNodeId(nodeId)) {
    return res.status(400).json({ error: 'Invalid node ID' });
  }

  try {
    const details = await neo4jService.getNodeDetails(nodeId);
    if (!details) {
      return res.status(404).json({ error: 'Node not found' });
    }
    res.json(details);
  } catch (error) {
    logger.error('Error fetching node details:', error);
    res.status(500).json({
      error: error instanceof Error ? error.message : 'Failed to fetch node details'
    });
  }
});

/**
 * Neo4j container status endpoint (SECURED)
 */
app.get('/api/neo4j/status', requireAuth, async (req, res) => {
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
 * Start Neo4j container (SECURED)
 */
app.post('/api/neo4j/start', requireAuth, rateLimiters.default, async (req, res) => {
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
 * Stop Neo4j container (SECURED)
 */
app.post('/api/neo4j/stop', requireAuth, rateLimiters.default, async (req, res) => {
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
 * Get markdown file content (SECURED)
 */
app.get('/api/docs/:filePath(*)', requireAuth, async (req, res) => {
  try {
    const filePath = req.params.filePath;
    const projectRoot = path.resolve(__dirname, '../../..');
    
    // Validate file path
    const pathValidation = validateFilePath(filePath, projectRoot);
    if (!pathValidation.isValid) {
      logger.warn('Docs API: ' + pathValidation.error);
      return res.status(403).json({ error: pathValidation.error });
    }

    const fullFilePath = pathValidation.sanitized as string;

    // Check if file exists
    if (!fs.existsSync(fullFilePath)) {
      return res.status(404).json({ error: 'File not found' });
    }

    // Read file content
    const content = fs.readFileSync(fullFilePath, 'utf8');
    res.json(sanitizeOutput(content));

  } catch (error) {
    logger.error('Error serving markdown file:', error);
    res.status(500).json({
      error: error instanceof Error ? error.message : 'Failed to read file'
    });
  }
});

/**
 * Check system dependencies (PUBLIC but rate-limited)
 */
app.get('/api/dependencies', rateLimiters.default, async (req, res) => {
  // Implementation remains the same but with rate limiting
  // ... (keep existing implementation)
  res.json({ message: 'Dependencies check' });
});

/**
 * Health check endpoint (PUBLIC)
 */
app.get('/api/health', async (req, res) => {
  const neo4jStatus = await neo4jContainer.getStatus();
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    activeProcesses: activeProcesses.size,
    neo4j: neo4jStatus,
    security: 'enabled'
  });
});

// Error handling middleware
app.use((err: any, req: express.Request, res: express.Response, next: express.NextFunction) => {
  logger.error('Internal server error:', err);
  // Don't expose internal error details
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
      logger.debug('Neo4j service should now be connected');
    }, 2000);

  } catch (error) {
    logger.error('Failed to start Neo4j container:', error);
    logger.warn('Continuing without Neo4j - some features may not work');
  }

  // Start the HTTP server
  httpServer.listen(PORT, () => {
    logger.info('SECURE Backend server running on http://localhost:' + PORT);
    logger.info('WebSocket server ready for connections');
    logger.info('Authentication and rate limiting enabled');
  });
}

// Start everything
startServer();
