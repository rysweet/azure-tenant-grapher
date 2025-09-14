#!/usr/bin/env node

const { spawn } = require('child_process');
const path = require('path');

// Start the backend server
const backendPath = path.join(__dirname, '../backend/src/server.ts');

console.log('Starting backend server...');

const backend = spawn('npx', ['tsx', backendPath], {
  cwd: path.join(__dirname, '..'),
  env: {
    ...process.env,
    NODE_ENV: 'development',
    BACKEND_PORT: '3001',
    NEO4J_URI: process.env.NEO4J_URI || 'bolt://localhost:7687',
    NEO4J_USER: process.env.NEO4J_USER || 'neo4j',
    NEO4J_PASSWORD: process.env.NEO4J_PASSWORD || require('crypto').randomBytes(16).toString('hex')
  },
  stdio: 'inherit'
});

backend.on('error', (err) => {
  console.error('Failed to start backend:', err);
  process.exit(1);
});

backend.on('close', (code) => {
  console.log(`Backend exited with code ${code}`);
  process.exit(code || 0);
});

// Handle shutdown
process.on('SIGINT', () => {
  console.log('\nShutting down backend...');
  backend.kill('SIGTERM');
});

process.on('SIGTERM', () => {
  backend.kill('SIGTERM');
});
