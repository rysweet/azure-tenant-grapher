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

// Load .env file from the project root  
dotenv.config({ path: path.join(__dirname, '../../../.env') });
console.log('Backend starting with environment:');
console.log('  AZURE_TENANT_ID:', process.env.AZURE_TENANT_ID || 'NOT SET');
console.log('  NEO4J_URI:', process.env.NEO4J_URI || 'NOT SET');
console.log('  NEO4J_PORT:', process.env.NEO4J_PORT || 'NOT SET');

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
app.use(express.json());

// Store active processes
const activeProcesses = new Map<string, ChildProcess>();

// Initialize Neo4j service and container manager
const neo4jService = new Neo4jService();
const neo4jContainer = new Neo4jContainer();

// WebSocket connection handling
io.on('connection', (socket) => {
  console.log('Client connected:', socket.id);

  // Subscribe to process output
  socket.on('subscribe', (processId: string) => {
    socket.join(`process-${processId}`);
    console.log(`Client ${socket.id} subscribed to process ${processId}`);
  });

  // Unsubscribe from process output
  socket.on('unsubscribe', (processId: string) => {
    socket.leave(`process-${processId}`);
    console.log(`Client ${socket.id} unsubscribed from process ${processId}`);
  });

  socket.on('disconnect', () => {
    console.log('Client disconnected:', socket.id);
  });
});

// API Routes

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
        console.log('Got Azure subscription name:', name);
        res.json({ name });
        return;
      }
    } catch (azError: any) {
      console.log('Azure CLI not available or not logged in:', azError?.message || azError);
    }
    
    // Fallback to tenant ID from env
    const tenantId = process.env.AZURE_TENANT_ID || 'Unknown';
    res.json({ name: tenantId });
  } catch (error) {
    console.error('Error getting tenant name:', error);
    res.status(500).json({ error: 'Failed to get tenant name' });
  }
});

/**
 * Execute a CLI command
 */
app.post('/api/execute', (req, res) => {
  const { command, args = [] } = req.body;
  const processId = uuidv4();
  
  if (!command) {
    return res.status(400).json({ error: 'Command is required' });
  }

  const pythonPath = process.env.PYTHON_PATH || 'python3';
  const cliPath = path.resolve(__dirname, '../../../scripts/cli.py');
  
  const fullArgs = [cliPath, command, ...args];
  const childProcess = spawn(pythonPath, fullArgs, {
    cwd: path.resolve(__dirname, '../../..'),
    env: {
      ...process.env,
      PYTHONPATH: path.resolve(__dirname, '../../..'),
    },
  });

  activeProcesses.set(processId, childProcess);

  // Stream stdout
  childProcess.stdout?.on('data', (data) => {
    const lines = data.toString().split('\n').filter((line: string) => line);
    io.to(`process-${processId}`).emit('output', {
      processId,
      type: 'stdout',
      data: lines,
      timestamp: new Date().toISOString(),
    });
  });

  // Stream stderr
  childProcess.stderr?.on('data', (data) => {
    const lines = data.toString().split('\n').filter((line: string) => line);
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
    return res.status(404).json({ error: 'Process not found' });
  }

  process.kill('SIGTERM');
  activeProcesses.delete(processId);
  
  res.json({ status: 'cancelled' });
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
    console.error('Error checking database status:', error);
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
    console.error('Error fetching database stats:', error);
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
    console.error('Error fetching graph:', error);
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
    console.error('Error searching nodes:', error);
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
    console.error('Error fetching node details:', error);
    res.status(500).json({ 
      error: error instanceof Error ? error.message : 'Failed to fetch node details' 
    });
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
 * Get environment configuration
 */
app.get('/api/config/env', (req, res) => {
  console.log('Config endpoint - AZURE_TENANT_ID:', process.env.AZURE_TENANT_ID);
  console.log('Config endpoint - NEO4J_URI:', process.env.NEO4J_URI);
  // Return safe environment variables that the UI can use
  res.json({
    AZURE_TENANT_ID: process.env.AZURE_TENANT_ID || '',
    AZURE_CLIENT_ID: process.env.AZURE_CLIENT_ID || '',
    // Don't send secrets to the frontend
    HAS_AZURE_CLIENT_SECRET: !!process.env.AZURE_CLIENT_SECRET,
    NEO4J_URI: process.env.NEO4J_URI || 'bolt://localhost:7687',
    NEO4J_PORT: process.env.NEO4J_PORT || '7687',
    RESOURCE_LIMIT: process.env.RESOURCE_LIMIT || '',
  });
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
      console.log('Docs API: Access denied - path outside project root:', filePath);
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
    console.error('Error serving markdown file:', error);
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
  
  // Try direct az command
  try {
    const { stdout } = await execPromise('az --version 2>&1 | head -1');
    if (stdout && stdout.includes('azure-cli')) {
      azVersion = stdout.match(/azure-cli\s+([0-9.]+)/)?.[1] || 'unknown';
      azInstalled = true;
    }
  } catch {
    // Try with full path
    try {
      const { stdout: whichAz } = await execPromise('which az');
      if (whichAz && whichAz.trim()) {
        const { stdout: versionOut } = await execPromise(`${whichAz.trim()} --version 2>&1 | head -1`);
        if (versionOut && versionOut.includes('azure-cli')) {
          azVersion = versionOut.match(/azure-cli\s+([0-9.]+)/)?.[1] || 'unknown';
          azInstalled = true;
        }
      }
    } catch {
      // Check common installation paths
      const paths = ['/usr/local/bin/az', '/usr/bin/az', '/opt/homebrew/bin/az'];
      for (const path of paths) {
        try {
          const { stdout } = await execPromise(`${path} --version 2>&1 | head -1`);
          if (stdout && stdout.includes('azure-cli')) {
            azVersion = stdout.match(/azure-cli\s+([0-9.]+)/)?.[1] || 'unknown';
            azInstalled = true;
            break;
          }
        } catch {
          // Continue to next path
        }
      }
    }
  }
  
  dependencies.push({ 
    name: 'Azure CLI', 
    installed: azInstalled, 
    version: azInstalled ? azVersion : undefined,
    required: '>=2.0' 
  });
  
  // Check Neo4j
  const neo4jStatus = await neo4jContainer.getStatus();
  dependencies.push({ 
    name: 'Neo4j', 
    installed: neo4jStatus.isRunning, 
    version: neo4jStatus.version || '5.0.0',
    required: '>=5.0' 
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

// Error handling middleware
app.use((err: any, req: express.Request, res: express.Response, next: express.NextFunction) => {
  console.error('Error:', err);
  res.status(500).json({ error: 'Internal server error' });
});

// Cleanup on exit
process.on('SIGINT', async () => {
  console.log('Shutting down server...');
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
    console.log('Starting Neo4j container...');
    await neo4jContainer.start();
    console.log('Neo4j container is ready');
    
    // Re-initialize Neo4j service connection after container is ready
    setTimeout(() => {
      // Give Neo4j service a moment to reconnect
      console.log('Neo4j service should now be connected');
    }, 2000);
    
  } catch (error) {
    console.error('Failed to start Neo4j container:', error);
    console.log('Continuing without Neo4j - some features may not work');
  }
  
  // Start the HTTP server
  httpServer.listen(PORT, () => {
    console.log(`Backend server running on http://localhost:${PORT}`);
    console.log(`WebSocket server ready for connections`);
  });
}

// Start everything
startServer();