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

// Load .env file from the project root
dotenv.config({ path: path.join(__dirname, '../../../.env') });
logger.info('Backend starting with environment');
logger.debug('Environment variables:', {
  AZURE_TENANT_ID: process.env.AZURE_TENANT_ID ? 'SET' : 'NOT SET',
  NEO4J_URI: process.env.NEO4J_URI || 'NOT SET',
  NEO4J_PORT: process.env.NEO4J_PORT || 'NOT SET'
});

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
  logger.info('Client connected:', socket.id);

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
    logger.info('Client disconnected:', socket.id);
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
    logger.error('Error getting tenant name:', error);
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

  // Use uv to run the atg CLI command
  const uvPath = process.env.UV_PATH || 'uv';
  const projectRoot = path.resolve(__dirname, '../../..');

  const fullArgs = ['run', 'atg', command, ...args];

  logger.info('Executing CLI command:', {
    command: `${uvPath} ${fullArgs.join(' ')}`,
    cwd: projectRoot,
    processId
  });

  const childProcess = spawn(uvPath, fullArgs, {
    cwd: projectRoot,
    env: {
      ...process.env,
      // Ensure the project root is in PYTHONPATH for proper module resolution
      PYTHONPATH: projectRoot,
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
    logger.error('Error checking database status:', error);
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
    logger.error('Error fetching database stats:', error);
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
    logger.error('Error fetching graph:', error);
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
    logger.error('Error searching nodes:', error);
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
    logger.error('Error fetching node details:', error);
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
    const driver = neo4j.driver(
      process.env.NEO4J_URI || 'bolt://localhost:7687',
      neo4j.auth.basic('neo4j', process.env.NEO4J_PASSWORD || 'password')
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
    console.error('Failed to fetch tenants from Neo4j:', error);
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
      } catch {
        // Process not running, clean up pidfile
        fs.unlinkSync(mcpPidfile);
        res.json({ running: false });
      }
    } else {
      res.json({ running: false });
    }
  } catch (error) {
    console.error('Failed to check MCP status:', error);
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
      logger.error('Failed to read .env file:', error);
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
      logger.warn('Docs API: Access denied - path outside project root:', filePath);
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
    logger.error('Error serving markdown file:', error);
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
    logger.error('Azure connection test failed:', error);
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

    // Test the API key by making a minimal inference request
    try {
      // If we have a chat model configured, test with actual inference
      if (modelChat) {
        const url = `${endpoint}/openai/deployments/${modelChat}/chat/completions?api-version=${apiVersion}`;
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'api-key': apiKey,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            messages: [{role: 'user', content: 'test'}],
            max_tokens: 1,
            temperature: 0
          })
        });

        if (response.ok) {
          const data: any = await response.json();
          const endpointHost = new URL(endpoint).host;
          return res.json({
            success: true,
            message: 'Inference test successful',
            endpoint: endpointHost,
            model: data.model || modelChat,
            models: {
              chat: modelChat,
              reasoning: modelReasoning || 'Not configured'
            }
          });
        } else if (response.status === 401) {
          return res.json({ success: false, error: 'Invalid Azure OpenAI API key' });
        } else if (response.status === 404) {
          return res.json({ success: false, error: `Deployment '${modelChat}' not found` });
        } else {
          const errorText = await response.text();
          logger.error('Azure OpenAI inference failed:', response.status, errorText);
          return res.json({ success: false, error: `Inference test failed: ${response.status}` });
        }
      } else {
        // When no model is configured, use gpt-4 as default for health check
        // This tests if the endpoint and API key are valid
        const testModel = 'gpt-4';
        const url = `${endpoint}/openai/deployments/${testModel}/chat/completions?api-version=${apiVersion}`;
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'api-key': apiKey,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            messages: [{role: 'user', content: 'Tell me a joke about Microsoft Azure'}],
            max_tokens: 50,
            temperature: 0.7
          })
        });

        if (response.ok) {
          const data: any = await response.json();
          const endpointHost = new URL(endpoint).host;
          return res.json({
            success: true,
            message: 'Azure OpenAI configured and working',
            endpoint: endpointHost,
            models: {
              chat: 'gpt-4 (default for test)',
              reasoning: modelReasoning || 'Not configured'
            }
          });
        } else if (response.status === 401) {
          return res.json({ success: false, error: 'Invalid Azure OpenAI API key' });
        } else if (response.status === 404) {
          // If gpt-4 deployment not found, the API is working but deployment name is different
          return res.json({ 
            success: false, 
            error: `No 'gpt-4' deployment found. Please configure AZURE_OPENAI_MODEL_CHAT with your deployment name.` 
          });
        } else {
          return res.json({ success: false, error: `Azure OpenAI API returned status ${response.status}` });
        }
      }
    } catch (error: any) {
      logger.error('Azure OpenAI API call failed:', error);
      return res.json({ success: false, error: `Failed to connect to Azure OpenAI: ${error.message}` });
    }
  } catch (error: any) {
    logger.error('Azure OpenAI connection test failed:', error);
    res.json({ success: false, error: error.message });
  }
});

/**
 * Check Microsoft Graph API permissions
 */
app.get('/api/test/graph-permissions', async (req, res) => {
  try {
    const { exec } = require('child_process');
    const { promisify } = require('util');
    const execPromise = promisify(exec);

    logger.debug('Checking Graph API permissions...');

    // Run the test_graph_api.py script
    try {
      const { stdout, stderr } = await execPromise('uv run python test_graph_api.py', {
        cwd: path.join(__dirname, '../../..'),
        timeout: 30000
      });

      // Combine stdout and stderr (logging goes to stderr)
      const output = stdout + stderr;

      // Parse the results
      const hasUsers = output.includes('✅ Can read users');
      const hasGroups = output.includes('✅ Can read groups');
      const hasServicePrincipals = output.includes('✅ Can read service principals');
      const hasDirectoryRoles = output.includes('✅ Can read directory roles');

      return res.json({
        success: hasUsers && hasGroups,
        permissions: {
          users: hasUsers,
          groups: hasGroups,
          servicePrincipals: hasServicePrincipals,
          directoryRoles: hasDirectoryRoles
        },
        allRequired: hasUsers && hasGroups,
        message: hasUsers && hasGroups
          ? 'All required Graph API permissions are configured'
          : 'Missing required Graph API permissions'
      });
    } catch (error: any) {
      logger.error('Failed to run Graph API test:', error);

      // Check if it's because dependencies are missing
      if (error.message?.includes('uv: command not found')) {
        return res.json({
          success: false,
          error: 'uv package manager not found',
          permissions: {
            users: false,
            groups: false,
            servicePrincipals: false,
            directoryRoles: false
          }
        });
      }

      return res.json({
        success: false,
        error: 'Failed to check Graph API permissions',
        permissions: {
          users: false,
          groups: false,
          servicePrincipals: false,
          directoryRoles: false
        }
      });
    }
  } catch (error: any) {
    logger.error('Graph API permissions check failed:', error);
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

// Error handling middleware
app.use((err: any, req: express.Request, res: express.Response, next: express.NextFunction) => {
  logger.error('Internal server error:', err);
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
    logger.error('Failed to start Neo4j container:', error);
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
