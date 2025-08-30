import { spawn } from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

describe('SPA Electron Build Verification', () => {
  const projectRoot = path.join(__dirname, '..');
  
  // Helper to run npm commands
  const runNpmCommand = (command: string, args: string[] = []): Promise<{ stdout: string; stderr: string; code: number }> => {
    return new Promise((resolve) => {
      const process = spawn('npm', ['run', command, ...args], {
        cwd: projectRoot,
        shell: true,
      });
      
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
      
      process.on('error', () => {
        resolve({ stdout, stderr, code: 1 });
      });
    });
  };

  test('npm run build:renderer should complete without errors', async () => {
    const result = await runNpmCommand('build:renderer');
    
    // Build should complete successfully
    expect(result.code).toBe(0);
    
    // Should NOT have CJS deprecation warning
    expect(result.stderr).not.toContain('CJS build of Vite');
    expect(result.stdout).not.toContain('CJS build of Vite');
    
    // Should NOT have excessive chunk size warnings (we allow up to 1000KB)
    expect(result.stderr).not.toContain('chunks are larger than 1000 kB');
    expect(result.stdout).not.toContain('chunks are larger than 1000 kB');
    
    // Should successfully build
    expect(result.stdout).toContain('built in');
    
    // Check that dist files are created
    const distPath = path.join(projectRoot, 'dist', 'renderer');
    expect(fs.existsSync(distPath)).toBe(true);
    expect(fs.existsSync(path.join(distPath, 'index.html'))).toBe(true);
  }, 30000); // 30 second timeout for build

  test('npm run build:main should complete without TypeScript errors', async () => {
    const result = await runNpmCommand('build:main');
    
    // TypeScript compilation should succeed
    expect(result.code).toBe(0);
    
    // Should not have TypeScript errors
    expect(result.stderr).not.toContain('error TS');
    
    // Check that output file is created
    const mainPath = path.join(projectRoot, 'dist', 'main', 'index.js');
    expect(fs.existsSync(mainPath)).toBe(true);
  }, 30000);

  test('npm run build:backend should complete without TypeScript errors', async () => {
    const result = await runNpmCommand('build:backend');
    
    // TypeScript compilation should succeed
    expect(result.code).toBe(0);
    
    // Should not have TypeScript errors
    expect(result.stderr).not.toContain('error TS');
    
    // Check that output files are created
    const backendPath = path.join(projectRoot, 'dist', 'backend');
    expect(fs.existsSync(backendPath)).toBe(true);
    expect(fs.existsSync(path.join(backendPath, 'server.js'))).toBe(true);
  }, 30000);

  test('npm run build should complete full build successfully', async () => {
    const result = await runNpmCommand('build');
    
    // Full build should succeed
    expect(result.code).toBe(0);
    
    // Should not have any deprecation warnings
    expect(result.stderr).not.toContain('deprecated');
    expect(result.stdout).not.toContain('CJS build of Vite');
    
    // Should not have build errors
    expect(result.stderr).not.toContain('error TS');
    expect(result.stderr).not.toContain('Error:');
    
    // All dist directories should exist
    expect(fs.existsSync(path.join(projectRoot, 'dist', 'renderer'))).toBe(true);
    expect(fs.existsSync(path.join(projectRoot, 'dist', 'main'))).toBe(true);
    expect(fs.existsSync(path.join(projectRoot, 'dist', 'backend'))).toBe(true);
  }, 60000); // 60 second timeout for full build

  test('vite config should be in ESM format', () => {
    // Check that vite.config.mts exists (ESM module)
    const viteMtsPath = path.join(projectRoot, 'vite.config.mts');
    const viteTsPath = path.join(projectRoot, 'vite.config.ts');
    
    expect(fs.existsSync(viteMtsPath)).toBe(true);
    expect(fs.existsSync(viteTsPath)).toBe(false);
    
    // Read the config and verify it uses ESM imports
    const configContent = fs.readFileSync(viteMtsPath, 'utf-8');
    expect(configContent).toContain('import { defineConfig }');
    expect(configContent).not.toContain('require(');
    expect(configContent).not.toContain('module.exports');
  });

  test('lazy loading should be implemented for tabs', () => {
    const appPath = path.join(projectRoot, 'renderer', 'src', 'App.tsx');
    const appContent = fs.readFileSync(appPath, 'utf-8');
    
    // Check for lazy imports
    expect(appContent).toContain('lazy(');
    expect(appContent).toContain('Suspense');
    
    // Check that heavy components are lazy loaded
    expect(appContent).toContain("lazy(() => import('./components/tabs/VisualizeTab'))");
    expect(appContent).toContain("lazy(() => import('./components/tabs/BuildTab'))");
    expect(appContent).toContain("lazy(() => import('./components/tabs/DocsTab'))");
  });

  test('manual chunks should be configured in vite config', () => {
    const configPath = path.join(projectRoot, 'vite.config.mts');
    const configContent = fs.readFileSync(configPath, 'utf-8');
    
    // Check for manual chunks configuration
    expect(configContent).toContain('manualChunks');
    expect(configContent).toContain('vendor-react');
    expect(configContent).toContain('vendor-mui');
    expect(configContent).toContain('vendor-editor');
    expect(configContent).toContain('vendor-markdown');
    expect(configContent).toContain('vendor-utils');
    
    // Check chunk size limit is set
    expect(configContent).toContain('chunkSizeWarningLimit: 1000');
  });

  test('Prettier config should exist for TypeScript formatting', () => {
    const prettierPath = path.join(projectRoot, '.prettierrc.json');
    expect(fs.existsSync(prettierPath)).toBe(true);
    
    const prettierConfig = JSON.parse(fs.readFileSync(prettierPath, 'utf-8'));
    expect(prettierConfig.semi).toBe(true);
    expect(prettierConfig.singleQuote).toBe(true);
    expect(prettierConfig.printWidth).toBe(100);
  });

  test('npm scripts for linting and formatting should exist', () => {
    const packageJson = JSON.parse(fs.readFileSync(path.join(projectRoot, 'package.json'), 'utf-8'));
    
    // Check for TypeScript/JavaScript quality tools
    expect(packageJson.scripts['lint']).toBeDefined();
    expect(packageJson.scripts['lint:fix']).toBeDefined();
    expect(packageJson.scripts['format']).toBeDefined();
    expect(packageJson.scripts['format:check']).toBeDefined();
    expect(packageJson.scripts['typecheck']).toBeDefined();
  });
});