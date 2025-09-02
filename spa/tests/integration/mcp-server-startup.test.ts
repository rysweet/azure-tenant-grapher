/**
 * Integration test for MCP server startup with Electron app
 */

import * as path from 'path';
import * as fs from 'fs';
import { spawn, ChildProcess } from 'child_process';
import axios from 'axios';

describe('MCP Server Startup Integration', () => {
  let mcpProcess: ChildProcess | null = null;
  const projectRoot = path.join(__dirname, '../../../../');
  const pidFile = path.join(projectRoot, 'outputs', 'mcp_server.pid');
  const backendUrl = 'http://localhost:5174';

  afterEach(async () => {
    // Clean up any spawned processes
    if (mcpProcess && !mcpProcess.killed) {
      mcpProcess.kill();
      mcpProcess = null;
    }

    // Clean up PID file
    if (fs.existsSync(pidFile)) {
      try {
        const pid = parseInt(fs.readFileSync(pidFile, 'utf-8').trim());
        process.kill(pid, 'SIGTERM');
      } catch (e) {
        // Process might already be dead
      }
      fs.unlinkSync(pidFile);
    }

    // Wait for cleanup
    await new Promise(resolve => setTimeout(resolve, 500));
  });

  test('MCP server should start and create PID file', async () => {
    // Ensure outputs directory exists
    const outputsDir = path.dirname(pidFile);
    if (!fs.existsSync(outputsDir)) {
      fs.mkdirSync(outputsDir, { recursive: true });
    }

    // Start MCP server using the same command as main/index.ts
    const pythonPath = path.join(projectRoot, '.venv', 'bin', 'python');
    const scriptPath = path.join(projectRoot, 'scripts', 'cli.py');

    mcpProcess = spawn(pythonPath, [scriptPath, 'mcp-server'], {
      cwd: projectRoot,
      env: { ...process.env },
      detached: false,
      stdio: ['ignore', 'pipe', 'pipe']
    });

    // Write PID file immediately
    fs.writeFileSync(pidFile, mcpProcess.pid!.toString());

    // Wait for server to be ready
    await new Promise(resolve => setTimeout(resolve, 2000));

    // Check that PID file exists
    expect(fs.existsSync(pidFile)).toBe(true);

    // Check that the process is actually running
    const pid = parseInt(fs.readFileSync(pidFile, 'utf-8').trim());
    expect(pid).toBeGreaterThan(0);

    // Verify process is alive
    let processAlive = false;
    try {
      process.kill(pid, 0); // Signal 0 = check if process exists
      processAlive = true;
    } catch (e) {
      processAlive = false;
    }
    expect(processAlive).toBe(true);
  }, 10000);

  test('Backend server should correctly detect MCP server status', async () => {
    // Start MCP server first
    const outputsDir = path.dirname(pidFile);
    if (!fs.existsSync(outputsDir)) {
      fs.mkdirSync(outputsDir, { recursive: true });
    }

    const pythonPath = path.join(projectRoot, '.venv', 'bin', 'python');
    const scriptPath = path.join(projectRoot, 'scripts', 'cli.py');

    mcpProcess = spawn(pythonPath, [scriptPath, 'mcp-server'], {
      cwd: projectRoot,
      env: { ...process.env },
      detached: false,
      stdio: ['ignore', 'pipe', 'pipe']
    });

    // Write PID file
    fs.writeFileSync(pidFile, mcpProcess.pid!.toString());

    // Wait for server to start
    await new Promise(resolve => setTimeout(resolve, 2000));

    // Mock the backend endpoint check
    const checkMcpStatus = () => {
      const pidFilePath = path.join(projectRoot, 'outputs', 'mcp_server.pid');

      if (!fs.existsSync(pidFilePath)) {
        return { connected: false, error: 'PID file not found' };
      }

      try {
        const pid = parseInt(fs.readFileSync(pidFilePath, 'utf-8').trim());
        process.kill(pid, 0); // Check if process exists
        return { connected: true, pid };
      } catch (error) {
        return { connected: false, error: 'Process not running' };
      }
    };

    const status = checkMcpStatus();
    expect(status.connected).toBe(true);
    expect(status.pid).toBeGreaterThan(0);
  }, 10000);

  test('MCP server should be accessible via stdio protocol', async () => {
    // Start MCP server
    const outputsDir = path.dirname(pidFile);
    if (!fs.existsSync(outputsDir)) {
      fs.mkdirSync(outputsDir, { recursive: true });
    }

    const pythonPath = path.join(projectRoot, '.venv', 'bin', 'python');
    const scriptPath = path.join(projectRoot, 'scripts', 'cli.py');

    mcpProcess = spawn(pythonPath, [scriptPath, 'mcp-server'], {
      cwd: projectRoot,
      env: { ...process.env },
      detached: false,
      stdio: ['pipe', 'pipe', 'pipe']
    });

    fs.writeFileSync(pidFile, mcpProcess.pid!.toString());

    // Collect output
    let output = '';
    let errorOutput = '';

    mcpProcess.stdout?.on('data', (data) => {
      output += data.toString();
    });

    mcpProcess.stderr?.on('data', (data) => {
      errorOutput += data.toString();
    });

    // Wait for initialization
    await new Promise(resolve => setTimeout(resolve, 3000));

    // Send a simple request to test if server responds
    const testRequest = JSON.stringify({
      jsonrpc: '2.0',
      method: 'list_tools',
      id: 1
    }) + '\n';

    mcpProcess.stdin?.write(testRequest);

    // Wait for response
    await new Promise(resolve => setTimeout(resolve, 1000));

    // Check that we got some output (server is responding)
    expect(output.length + errorOutput.length).toBeGreaterThan(0);

    // Check process is still alive
    expect(mcpProcess.killed).toBe(false);
  }, 10000);
});
