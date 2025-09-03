#!/usr/bin/env node

const { exec } = require('child_process');
const util = require('util');
const execPromise = util.promisify(exec);

async function testAzureCliDetection() {
  console.log('Testing Azure CLI detection methods...\n');

  // Method 1: Direct check
  console.log('Method 1: az --version');
  try {
    const { stdout } = await execPromise('az --version 2>&1 | head -1');
    console.log('✅ SUCCESS:', stdout.trim());
  } catch (error) {
    console.log('❌ FAILED:', error.message);
  }

  // Method 2: which az
  console.log('\nMethod 2: which az');
  try {
    const { stdout } = await execPromise('which az');
    console.log('✅ SUCCESS: Found at', stdout.trim());

    // Now try to get version
    const azPath = stdout.trim();
    const { stdout: version } = await execPromise(`"${azPath}" --version 2>&1 | head -1`);
    console.log('   Version:', version.trim());
  } catch (error) {
    console.log('❌ FAILED:', error.message);
  }

  // Method 3: Check Homebrew path directly
  console.log('\nMethod 3: /opt/homebrew/bin/az');
  try {
    await execPromise('test -x /opt/homebrew/bin/az');
    console.log('✅ File exists and is executable');

    const { stdout } = await execPromise('/opt/homebrew/bin/az --version 2>&1 | head -1');
    console.log('   Version:', stdout.trim());
  } catch (error) {
    console.log('❌ FAILED:', error.message);
  }

  // Method 4: Check what the server.ts code is doing
  console.log('\nMethod 4: Exact server.ts approach');
  let azInstalled = false;
  let azVersion = 'unknown';

  // Method 1 from server.ts
  try {
    const { stdout: whichOutput } = await execPromise('which az');
    if (whichOutput && whichOutput.trim()) {
      const { stdout: versionOutput } = await execPromise('az --version 2>&1 | head -1');
      if (versionOutput && versionOutput.includes('azure-cli')) {
        azVersion = versionOutput.match(/azure-cli\s+([0-9.]+)/)?.[1] || 'unknown';
        azInstalled = true;
      }
    }
  } catch (error) {
    console.log('   Method 1 failed:', error.message);

    // Method 2: Try common paths
    const commonPaths = ['/usr/local/bin/az', '/opt/homebrew/bin/az', '/usr/bin/az'];

    for (const azPath of commonPaths) {
      try {
        await execPromise(`test -x "${azPath}"`);
        const { stdout: versionOutput } = await execPromise(`"${azPath}" --version 2>&1 | head -1`);
        if (versionOutput && versionOutput.includes('azure-cli')) {
          azVersion = versionOutput.match(/azure-cli\s+([0-9.]+)/)?.[1] || 'unknown';
          azInstalled = true;
          console.log(`   Found at ${azPath}`);
          break;
        }
      } catch (pathError) {
        continue;
      }
    }
  }

  console.log(`\n✅ Final result: installed=${azInstalled}, version=${azVersion}`);

  // Now test from Node.js environment (how the server runs)
  console.log('\n\nTesting from Node.js spawn (how server.ts runs):');
  const { spawn } = require('child_process');

  // Test with spawn
  const azProcess = spawn('az', ['--version']);

  azProcess.stdout.on('data', (data) => {
    console.log('✅ spawn stdout:', data.toString().split('\n')[0]);
  });

  azProcess.stderr.on('data', (data) => {
    console.log('❌ spawn stderr:', data.toString());
  });

  azProcess.on('error', (error) => {
    console.log('❌ spawn error:', error.message);
    console.log('   This is likely the issue - spawn cannot find az in PATH');
  });

  azProcess.on('close', (code) => {
    if (code === 0) {
      console.log('✅ spawn succeeded with code 0');
    } else {
      console.log(`❌ spawn exited with code ${code}`);
    }
  });
}

testAzureCliDetection();
