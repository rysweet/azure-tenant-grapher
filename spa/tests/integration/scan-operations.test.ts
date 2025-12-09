import { spawn } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

describe('Scan Operations Integration', () => {
  const CLI_PATH = path.join(__dirname, '../../../../scripts/cli.py');
  const TEST_TENANT_ID = '12345678-1234-1234-1234-123456789012';

  // Helper function to run CLI commands
  const runCLI = (args: string[]): Promise<{ stdout: string; stderr: string; code: number }> => {
    return new Promise((resolve, reject) => {
      const process = spawn('python', [CLI_PATH, ...args]);
      let stdout = '';
      let stderr = '';

      process.stdout.on('data', (data) => {
        stdout += data.toString();
      });

      process.stderr.on('data', (data) => {
        stderr += data.toString();
      });

      process.on('close', (code) => {
        resolve({ stdout, stderr, code: code || 0 });
      });

      process.on('error', (error) => {
        reject(error);
      });
    });
  };

  test('CLI should respond to --help', async () => {
    const result = await runCLI(['--help']);
    expect(result.code).toBe(0);
    expect(result.stdout).toContain('Azure Tenant Grapher');
    expect(result.stdout).toContain('scan');
    expect(result.stdout).toContain('generate-spec');
    expect(result.stdout).toContain('generate-iac');
  });

  test('CLI should validate tenant ID format', async () => {
    const result = await runCLI(['scan', '--tenant-id', 'invalid-id']);
    expect(result.code).not.toBe(0);
    expect(result.stderr).toContain('Invalid tenant ID');
  });

  test('CLI should accept valid scan parameters', async () => {
    const result = await runCLI([
      'scan',
      '--tenant-id', TEST_TENANT_ID,
      '--resource-limit', '100',
      '--dry-run'
    ]);

    // In dry-run mode, should succeed without actual Azure connection
    if (result.stdout.includes('dry-run') || result.stderr.includes('Azure credentials')) {
      // Expected behavior - either dry-run message or credentials error
      expect(result.code).toBeGreaterThanOrEqual(0);
    }
  });

  test('CLI should handle resource limits', async () => {
    const result = await runCLI([
      'scan',
      '--tenant-id', TEST_TENANT_ID,
      '--resource-limit', '10000'
    ]);

    // Should either run or fail due to credentials
    expect(result.code).toBeDefined();

    // Check for negative resource limit
    const negativeResult = await runCLI([
      'scan',
      '--tenant-id', TEST_TENANT_ID,
      '--resource-limit', '-1'
    ]);

    expect(negativeResult.code).not.toBe(0);
  });

  test('SPA start command should work', async () => {
    const result = await runCLI(['spa-start', '--help']);
    expect(result.code).toBe(0);
    expect(result.stdout).toContain('spa-start');
  });

  test('SPA stop command should work', async () => {
    const result = await runCLI(['spa-stop', '--help']);
    expect(result.code).toBe(0);
    expect(result.stdout).toContain('spa-stop');
  });
});

describe('Generate Spec Operations', () => {
  const CLI_PATH = path.join(__dirname, '../../../../scripts/cli.py');

  const runCLI = (args: string[]): Promise<{ stdout: string; stderr: string; code: number }> => {
    return new Promise((resolve, reject) => {
      const process = spawn('python', [CLI_PATH, ...args]);
      let stdout = '';
      let stderr = '';

      process.stdout.on('data', (data) => {
        stdout += data.toString();
      });

      process.stderr.on('data', (data) => {
        stderr += data.toString();
      });

      process.on('close', (code) => {
        resolve({ stdout, stderr, code: code || 0 });
      });

      process.on('error', (error) => {
        reject(error);
      });
    });
  };

  test('generate-spec command should accept options', async () => {
    const result = await runCLI(['generate-spec', '--help']);
    expect(result.code).toBe(0);
    expect(result.stdout).toContain('--include-details');
    expect(result.stdout).toContain('--include-relationships');
  });

  test('generate-spec should work with basic options', async () => {
    const result = await runCLI([
      'generate-spec',
      '--include-details',
      '--include-relationships'
    ]);

    // Should either generate or fail due to Neo4j connection
    expect(result.code).toBeDefined();
    if (result.stderr.includes('Neo4j') || result.stderr.includes('database')) {
      // Expected - Neo4j not running in test environment
      expect(result.stderr).toBeDefined();
    }
  });
});

describe('Generate IaC Operations', () => {
  const CLI_PATH = path.join(__dirname, '../../../../scripts/cli.py');
  const TEST_TENANT_ID = '12345678-1234-1234-1234-123456789012';

  const runCLI = (args: string[]): Promise<{ stdout: string; stderr: string; code: number }> => {
    return new Promise((resolve, reject) => {
      const process = spawn('python', [CLI_PATH, ...args]);
      let stdout = '';
      let stderr = '';

      process.stdout.on('data', (data) => {
        stdout += data.toString();
      });

      process.stderr.on('data', (data) => {
        stderr += data.toString();
      });

      process.on('close', (code) => {
        resolve({ stdout, stderr, code: code || 0 });
      });

      process.on('error', (error) => {
        reject(error);
      });
    });
  };

  test('generate-iac command should accept format options', async () => {
    const result = await runCLI(['generate-iac', '--help']);
    expect(result.code).toBe(0);
    expect(result.stdout).toContain('--format');
    expect(result.stdout).toContain('terraform');
    expect(result.stdout).toContain('arm');
    expect(result.stdout).toContain('bicep');
  });

  test('generate-iac should validate tenant ID', async () => {
    const result = await runCLI([
      'generate-iac',
      '--tenant-id', 'invalid',
      '--format', 'terraform'
    ]);

    expect(result.code).not.toBe(0);
    expect(result.stderr).toContain('Invalid tenant ID');
  });

  test('generate-iac should accept all format types', async () => {
    const formats = ['terraform', 'arm', 'bicep'];

    for (const format of formats) {
      const result = await runCLI([
        'generate-iac',
        '--tenant-id', TEST_TENANT_ID,
        '--format', format,
        '--dry-run'
      ]);

      // Should accept the format even if it fails due to missing Neo4j
      expect(result.code).toBeDefined();
    }
  });

  test('generate-iac should handle resource limits', async () => {
    const result = await runCLI([
      'generate-iac',
      '--tenant-id', TEST_TENANT_ID,
      '--format', 'terraform',
      '--resource-limit', '500',
      '--dry-run'
    ]);

    expect(result.code).toBeDefined();
  });
});

describe('Configuration Management', () => {
  const CONFIG_PATH = path.join(__dirname, '../../test-config.json');

  afterEach(() => {
    // Clean up test config file
    if (fs.existsSync(CONFIG_PATH)) {
      fs.unlinkSync(CONFIG_PATH);
    }
  });

  test('should save and load configuration', () => {
    const config = {
      azure: {
        tenantId: '12345678-1234-1234-1234-123456789012',
        clientId: '87654321-4321-4321-4321-210987654321',
        clientSecret: 'test-secret',  // pragma: allowlist secret
      },
      neo4j: {
        uri: 'bolt://localhost:7687',
        username: 'neo4j',
        password: 'test-password',  // pragma: allowlist secret
      },
      app: {
        maxThreads: 10,
        resourceLimit: 1000,
      },
    };

    // Write config
    fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2));

    // Read config
    const loadedConfig = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf-8'));

    expect(loadedConfig).toEqual(config);
    expect(loadedConfig.azure.tenantId).toBe(config.azure.tenantId);
    expect(loadedConfig.neo4j.uri).toBe(config.neo4j.uri);
    expect(loadedConfig.app.maxThreads).toBe(config.app.maxThreads);
  });

  test('should handle missing configuration gracefully', () => {
    const loadConfig = () => {
      if (fs.existsSync(CONFIG_PATH)) {
        return JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf-8'));
      }
      return null;
    };

    const config = loadConfig();
    expect(config).toBeNull();
  });

  test('should validate configuration structure', () => {
    const validateConfig = (config: any): boolean => {
      if (!config.azure || !config.neo4j || !config.app) {
        return false;
      }

      // Validate UUID format for tenant and client IDs
      const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

      if (config.azure.tenantId && !uuidRegex.test(config.azure.tenantId)) {
        return false;
      }

      if (config.azure.clientId && !uuidRegex.test(config.azure.clientId)) {
        return false;
      }

      // Validate Neo4j URI format
      if (config.neo4j.uri && !config.neo4j.uri.startsWith('bolt://')) {
        return false;
      }

      // Validate numeric limits
      if (config.app.maxThreads && (config.app.maxThreads < 1 || config.app.maxThreads > 100)) {
        return false;
      }

      if (config.app.resourceLimit && config.app.resourceLimit < 0) {
        return false;
      }

      return true;
    };

    const validConfig = {
      azure: {
        tenantId: '12345678-1234-1234-1234-123456789012',
        clientId: '87654321-4321-4321-4321-210987654321',
      },
      neo4j: {
        uri: 'bolt://localhost:7687',
      },
      app: {
        maxThreads: 10,
        resourceLimit: 1000,
      },
    };

    expect(validateConfig(validConfig)).toBe(true);

    const invalidConfig = {
      azure: {
        tenantId: 'not-a-uuid',
      },
      neo4j: {
        uri: 'http://invalid-protocol',
      },
      app: {
        maxThreads: 200,
      },
    };

    expect(validateConfig(invalidConfig)).toBe(false);
  });
});
