#!/usr/bin/env node
/**
 * Test to diagnose why agent mode output isn't showing in the UI
 * This test will check each step of the output pipeline:
 * 1. Python process output
 * 2. ProcessManager capture
 * 3. Event emission
 * 4. IPC forwarding
 */

const { spawn } = require('child_process');
const path = require('path');
const { EventEmitter } = require('events');

// Color codes for output
const RED = '\x1b[31m';
const GREEN = '\x1b[32m';
const YELLOW = '\x1b[33m';
const BLUE = '\x1b[34m';
const RESET = '\x1b[0m';

class TestResults {
  constructor() {
    this.tests = [];
    this.currentTest = null;
  }

  startTest(name) {
    console.log(`\n${BLUE}Testing: ${name}${RESET}`);
    this.currentTest = { name, passed: false, output: [], errors: [] };
  }

  pass(message) {
    console.log(`  ${GREEN}✓${RESET} ${message}`);
    if (this.currentTest) {
      this.currentTest.output.push(`✓ ${message}`);
    }
  }

  fail(message) {
    console.log(`  ${RED}✗${RESET} ${message}`);
    if (this.currentTest) {
      this.currentTest.errors.push(`✗ ${message}`);
    }
  }

  info(message) {
    console.log(`  ${YELLOW}ℹ${RESET} ${message}`);
    if (this.currentTest) {
      this.currentTest.output.push(`ℹ ${message}`);
    }
  }

  endTest() {
    if (this.currentTest) {
      this.currentTest.passed = this.currentTest.errors.length === 0;
      this.tests.push(this.currentTest);
      this.currentTest = null;
    }
  }

  summary() {
    console.log(`\n${BLUE}═══════════════════════════════════════════${RESET}`);
    console.log(`${BLUE}Test Summary${RESET}`);
    console.log(`${BLUE}═══════════════════════════════════════════${RESET}`);
    
    const passed = this.tests.filter(t => t.passed).length;
    const failed = this.tests.filter(t => !t.passed).length;
    
    this.tests.forEach(test => {
      const status = test.passed ? `${GREEN}PASS${RESET}` : `${RED}FAIL${RESET}`;
      console.log(`  ${status} ${test.name}`);
      if (!test.passed) {
        test.errors.forEach(err => console.log(`    ${err}`));
      }
    });
    
    console.log(`\n${BLUE}Results: ${GREEN}${passed} passed${RESET}, ${RED}${failed} failed${RESET}`);
    return failed === 0;
  }
}

const results = new TestResults();

// Test 1: Direct Python execution
async function testDirectPythonExecution() {
  results.startTest('Direct Python Execution');
  
  return new Promise((resolve) => {
    const pythonPath = 'python3';
    const cliPath = path.resolve(__dirname, '../../scripts/cli.py');
    const args = [cliPath, 'agent-mode', '--question', 'test'];
    
    results.info(`Command: ${pythonPath} ${args.join(' ')}`);
    
    const child = spawn(pythonPath, args, {
      cwd: path.resolve(__dirname, '../..'),
      env: {
        ...process.env,
        PYTHONPATH: path.resolve(__dirname, '../..'),
        PYTHONUNBUFFERED: '1'
      }
    });
    
    let stdoutData = '';
    let stderrData = '';
    let outputReceived = false;
    
    child.stdout.on('data', (data) => {
      stdoutData += data.toString();
      outputReceived = true;
      results.pass(`Received stdout: ${data.toString().slice(0, 50)}...`);
    });
    
    child.stderr.on('data', (data) => {
      stderrData += data.toString();
      outputReceived = true;
      results.info(`Received stderr: ${data.toString().slice(0, 50)}...`);
    });
    
    // Kill after 5 seconds
    setTimeout(() => {
      child.kill('SIGTERM');
      
      if (!outputReceived) {
        results.fail('No output received from Python process');
      } else {
        results.pass(`Total stdout: ${stdoutData.length} bytes`);
        results.pass(`Total stderr: ${stderrData.length} bytes`);
      }
      
      results.endTest();
      resolve();
    }, 5000);
  });
}

// Test 2: ProcessManager simulation
async function testProcessManagerCapture() {
  results.startTest('ProcessManager Output Capture');
  
  return new Promise((resolve) => {
    class MockProcessManager extends EventEmitter {
      execute(command, args) {
        const id = 'test-id';
        const pythonPath = 'python3';
        const cliPath = path.resolve(__dirname, '../../scripts/cli.py');
        const fullArgs = [cliPath, command, ...args];
        
        results.info(`Spawning: ${pythonPath} ${fullArgs.join(' ')}`);
        
        const child = spawn(pythonPath, fullArgs, {
          cwd: path.resolve(__dirname, '../..'),
          env: {
            ...process.env,
            PYTHONPATH: path.resolve(__dirname, '../..'),
            PYTHONUNBUFFERED: '1'
          }
        });
        
        let outputEmitted = false;
        
        child.stdout?.on('data', (data) => {
          const text = data.toString();
          const lines = text.split('\n');
          results.pass(`Captured ${lines.length} lines from stdout`);
          this.emit('output', { id, type: 'stdout', data: lines });
          outputEmitted = true;
        });
        
        child.stderr?.on('data', (data) => {
          const text = data.toString();
          const lines = text.split('\n');
          results.info(`Captured ${lines.length} lines from stderr`);
          this.emit('output', { id, type: 'stderr', data: lines });
          outputEmitted = true;
        });
        
        child.on('exit', (code) => {
          results.info(`Process exited with code: ${code}`);
          this.emit('process:exit', { id, code });
        });
        
        return { success: true, data: { id } };
      }
    }
    
    const pm = new MockProcessManager();
    let eventsReceived = 0;
    
    pm.on('output', (data) => {
      eventsReceived++;
      results.pass(`Event emitted: ${data.type} with ${data.data.length} lines`);
    });
    
    pm.on('process:exit', (data) => {
      if (eventsReceived === 0) {
        results.fail('No output events were emitted');
      } else {
        results.pass(`Total events emitted: ${eventsReceived}`);
      }
      results.endTest();
      resolve();
    });
    
    pm.execute('agent-mode', ['--question', 'test']);
    
    // Timeout after 5 seconds
    setTimeout(() => {
      if (eventsReceived === 0) {
        results.fail('Timeout: No events received');
        results.endTest();
        resolve();
      }
    }, 5000);
  });
}

// Test 3: Check if Python is buffering output
async function testPythonBuffering() {
  results.startTest('Python Output Buffering');
  
  return new Promise((resolve) => {
    // Create a simple Python script that outputs immediately
    const testScript = `
import sys
import time
print("Line 1", flush=True)
sys.stdout.flush()
print("Line 2", flush=True)
sys.stderr.write("Error line\\n")
sys.stderr.flush()
time.sleep(1)
print("Line 3", flush=True)
`;
    
    const child = spawn('python3', ['-c', testScript], {
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1'
      }
    });
    
    let outputCount = 0;
    let expectedOutput = ['Line 1', 'Line 2', 'Line 3'];
    let receivedOutput = [];
    
    child.stdout.on('data', (data) => {
      const lines = data.toString().trim().split('\n');
      receivedOutput.push(...lines);
      outputCount++;
      results.pass(`Received output chunk ${outputCount}: ${data.toString().trim()}`);
    });
    
    child.stderr.on('data', (data) => {
      results.info(`Stderr: ${data.toString().trim()}`);
    });
    
    child.on('exit', () => {
      if (receivedOutput.length === expectedOutput.length) {
        results.pass('All expected output received');
      } else {
        results.fail(`Expected ${expectedOutput.length} lines, got ${receivedOutput.length}`);
      }
      results.endTest();
      resolve();
    });
  });
}

// Test 4: Check actual CLI path and execution
async function testCLIPath() {
  results.startTest('CLI Path and Execution');
  
  const fs = require('fs');
  const cliPath = path.resolve(__dirname, '../../scripts/cli.py');
  
  if (fs.existsSync(cliPath)) {
    results.pass(`CLI script exists at: ${cliPath}`);
  } else {
    results.fail(`CLI script NOT found at: ${cliPath}`);
    results.endTest();
    return;
  }
  
  // Try to run just the help command
  return new Promise((resolve) => {
    const child = spawn('python3', [cliPath, '--help'], {
      cwd: path.resolve(__dirname, '../..')
    });
    
    let output = '';
    child.stdout.on('data', (data) => {
      output += data.toString();
    });
    
    child.on('exit', (code) => {
      if (code === 0 && output.length > 0) {
        results.pass('CLI script executes successfully');
        results.info(`Help output length: ${output.length} bytes`);
      } else {
        results.fail(`CLI script failed with code ${code}`);
      }
      results.endTest();
      resolve();
    });
  });
}

// Test 5: Test with uv run
async function testWithUv() {
  results.startTest('UV Run Execution');
  
  return new Promise((resolve) => {
    const child = spawn('uv', ['run', 'atg', 'agent-mode', '--question', 'test'], {
      cwd: path.resolve(__dirname, '../..'),
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1'
      }
    });
    
    let outputReceived = false;
    
    child.stdout.on('data', (data) => {
      outputReceived = true;
      results.pass(`UV stdout: ${data.toString().slice(0, 50)}...`);
    });
    
    child.stderr.on('data', (data) => {
      results.info(`UV stderr: ${data.toString().slice(0, 50)}...`);
    });
    
    // Kill after 5 seconds
    setTimeout(() => {
      child.kill('SIGTERM');
      
      if (!outputReceived) {
        results.fail('No output from uv run command');
      } else {
        results.pass('Output received from uv run');
      }
      
      results.endTest();
      resolve();
    }, 5000);
  });
}

// Run all tests
async function runTests() {
  console.log(`${BLUE}═══════════════════════════════════════════${RESET}`);
  console.log(`${BLUE}Agent Mode Output Diagnostic Tests${RESET}`);
  console.log(`${BLUE}═══════════════════════════════════════════${RESET}`);
  
  await testCLIPath();
  await testPythonBuffering();
  await testDirectPythonExecution();
  await testProcessManagerCapture();
  await testWithUv();
  
  const allPassed = results.summary();
  process.exit(allPassed ? 0 : 1);
}

runTests().catch(err => {
  console.error(`${RED}Test suite failed:${RESET}`, err);
  process.exit(1);
});