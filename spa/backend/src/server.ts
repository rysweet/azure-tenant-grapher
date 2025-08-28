import express from 'express';
import { createServer } from 'http';
import { Server as SocketIOServer } from 'socket.io';
import cors from 'cors';
import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import { v4 as uuidv4 } from 'uuid';

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
  const cliPath = path.resolve(__dirname, '../../../../scripts/cli.py');
  
  const fullArgs = [cliPath, command, ...args];
  const childProcess = spawn(pythonPath, fullArgs, {
    cwd: path.resolve(__dirname, '../../../..'),
    env: {
      ...process.env,
      PYTHONPATH: path.resolve(__dirname, '../../../..'),
    },
  });

  activeProcesses.set(processId, childProcess);

  // Stream stdout
  childProcess.stdout?.on('data', (data) => {
    const lines = data.toString().split('\n').filter(line => line);
    io.to(`process-${processId}`).emit('output', {
      processId,
      type: 'stdout',
      data: lines,
      timestamp: new Date().toISOString(),
    });
  });

  // Stream stderr
  childProcess.stderr?.on('data', (data) => {
    const lines = data.toString().split('\n').filter(line => line);
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
 * Health check endpoint
 */
app.get('/api/health', (req, res) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    activeProcesses: activeProcesses.size,
  });
});

// Error handling middleware
app.use((err: any, req: express.Request, res: express.Response, next: express.NextFunction) => {
  console.error('Error:', err);
  res.status(500).json({ error: 'Internal server error' });
});

// Cleanup on exit
process.on('SIGINT', () => {
  console.log('Shutting down server...');
  activeProcesses.forEach((process) => {
    process.kill('SIGTERM');
  });
  process.exit(0);
});

const PORT = process.env.BACKEND_PORT || 3001;

httpServer.listen(PORT, () => {
  console.log(`Backend server running on http://localhost:${PORT}`);
  console.log(`WebSocket server ready for connections`);
});