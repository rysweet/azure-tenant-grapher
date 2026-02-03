import React, { useState } from 'react';
import {
  Box,
  Paper,
  TextField,
  Button,
  Grid,
  Typography,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Checkbox,
} from '@mui/material';
import { CloudUpload as DeployIcon } from '@mui/icons-material';
import TenantSelector from '../shared/TenantSelector';

interface ProcessOutputData {
  id: string;
  data: string[];
}

interface ProcessExitData {
  id: string;
  code: number;
}

const DeployTab: React.FC = () => {
  const [sourceTenantId, setSourceTenantId] = useState('3cd87a41-1f61-4aef-a212-cefdecd9a2d1');
  const [targetTenantId, setTargetTenantId] = useState('506f82b2-e2e7-40a2-b0be-ea6f8cb908f8');
  const [resourceGroup, setResourceGroup] = useState('');
  const [location, setLocation] = useState('eastus');
  const [subscriptionId, setSubscriptionId] = useState('');
  const [iacFormat, setIacFormat] = useState<'auto' | 'terraform' | 'bicep' | 'arm'>('terraform');
  const [dryRun, setDryRun] = useState(true);
  const [isDeploying, setIsDeploying] = useState(false);
  const [terminalOutput, setTerminalOutput] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleDeploy = async () => {
    if (!sourceTenantId || !targetTenantId || !resourceGroup) {
      setError('Source Tenant ID, Gameboard Tenant ID, and Resource Group are required');
      return;
    }

    setError(null);
    setSuccess(false);
    setIsDeploying(true);
    setTerminalOutput('');

    try {
      // PHASE 1: Generate IaC automatically
      setTerminalOutput('🏗️ Phase 1: Generating Infrastructure as Code...\n');

      const iacArgs = [
        '--source-tenant-id', sourceTenantId,
        '--target-tenant-id', targetTenantId,
        '--output', 'outputs/iac',
        '--format', iacFormat === 'auto' ? 'terraform' : iacFormat,
        '--skip-conflict-check',      // Skip pre-deployment conflict detection
        '--skip-name-validation',     // Skip global name validation
        '--skip-validation',          // Skip Terraform validation after generation
        '--no-auto-import-existing',  // Skip importing existing resources (no source tenant auth needed)
      ];

      const iacResult = await window.electronAPI.cli.execute('generate-iac', iacArgs);

      // Listen for IaC generation output
      let iacOutputContent = '';

      const iacOutputHandler = (data: ProcessOutputData) => {
        if (data.id === iacResult.data.id) {
          const newContent = data.data.join('\n');
          iacOutputContent += newContent + '\n';
          setTerminalOutput(prev => prev + newContent + '\n');
        }
      };

      window.electronAPI.on('process:output', iacOutputHandler);

      // Wait for IaC generation to complete
      await new Promise<void>((resolve, reject) => {
        const iacErrorHandler = (data: any) => {
          if (data.processId === iacResult.data.id || data.id === iacResult.data.id) {
            window.electronAPI.off?.('process:output', iacOutputHandler);
            window.electronAPI.off?.('process:exit', iacExitHandler);
            window.electronAPI.off?.('process:error', iacErrorHandler);
            reject(new Error(data.error || 'IaC generation failed'));
          }
        };

        const iacExitHandler = (data: ProcessExitData) => {
          if (data.id === iacResult.data.id) {
            window.electronAPI.off?.('process:output', iacOutputHandler);
            window.electronAPI.off?.('process:exit', iacExitHandler);
            window.electronAPI.off?.('process:error', iacErrorHandler);

            if (data.code === 0) {
              resolve();
            } else {
              let errorMessage = 'IaC generation failed';
              if (iacOutputContent.includes('Error:')) {
                const lines = iacOutputContent.split('\n');
                const errorLine = lines.find(line => line.includes('Error:'));
                if (errorLine) {
                  errorMessage = errorLine.replace(/^.*Error:\s*/, '');
                }
              }
              reject(new Error(errorMessage));
            }
          }
        };

        window.electronAPI.on('process:exit', iacExitHandler);
        window.electronAPI.on('process:error', iacErrorHandler);
      });

      setTerminalOutput(prev => prev + '✅ IaC generated successfully\n\n');

      // PHASE 2: Deploy the generated IaC
      setTerminalOutput(prev => prev + '🚀 Phase 2: Deploying to Azure...\n');

      const deployArgs = [
        '--iac-dir', 'outputs/iac',
        '--target-tenant-id', targetTenantId,
        '--resource-group', resourceGroup,
        '--location', location,
      ];

      if (subscriptionId) {
        deployArgs.push('--subscription-id', subscriptionId);
      }

      if (iacFormat !== 'auto') {
        deployArgs.push('--format', iacFormat);
      }

      if (dryRun) {
        deployArgs.push('--dry-run');
      }

      // Enable agent mode for autonomous error recovery
      deployArgs.push('--agent');

      const deployResult = await window.electronAPI.cli.execute('deploy', deployArgs);

      let deployOutputContent = '';

      const deployOutputHandler = (data: ProcessOutputData) => {
        if (data.id === deployResult.data.id) {
          const newContent = data.data.join('\n');
          deployOutputContent += newContent + '\n';
          setTerminalOutput(prev => prev + newContent + '\n');
        }
      };

      window.electronAPI.on('process:output', deployOutputHandler);

      // Define error handler first (needed by exitHandler cleanup)
      const deployErrorHandler = (data: any) => {
        if (data.processId === deployResult.data.id || data.id === deployResult.data.id) {
          setIsDeploying(false);
          setError(data.error || 'Deployment failed');

          // Clean up event listeners
          window.electronAPI.off?.('process:output', deployOutputHandler);
          window.electronAPI.off?.('process:exit', deployExitHandler);
          window.electronAPI.off?.('process:error', deployErrorHandler);
        }
      };

      const deployExitHandler = (data: ProcessExitData) => {
        if (data.id === deployResult.data.id) {
          setIsDeploying(false);
          if (data.code === 0) {
            setSuccess(true);
          } else {
            // Extract error message from terminal output if available
            let errorMessage = `Deployment failed with exit code ${data.code}`;

            // Look for error patterns in terminal output
            if (deployOutputContent) {
              const errorMatch = deployOutputContent.match(/❌ Error: (.+)/);
              if (errorMatch) {
                errorMessage = errorMatch[1];
              } else if (deployOutputContent.match(/\[ProcessManager\] Invalid command: (.+)/)) {
                const commandMatch = deployOutputContent.match(/\[ProcessManager\] Invalid command: (.+)/);
                if (commandMatch) {
                  errorMessage = commandMatch[1];
                }
              } else if (deployOutputContent.includes('Error:')) {
                // Try to extract any error line
                const lines = deployOutputContent.split('\n');
                const errorLine = lines.find(line => line.includes('Error:'));
                if (errorLine) {
                  errorMessage = errorLine.replace(/^.*Error:\s*/, '');
                }
              }
            }

            setError(errorMessage);
          }

          // Clean up event listeners
          window.electronAPI.off?.('process:output', deployOutputHandler);
          window.electronAPI.off?.('process:exit', deployExitHandler);
          window.electronAPI.off?.('process:error', deployErrorHandler);
        }
      };

      window.electronAPI.on('process:exit', deployExitHandler);
      window.electronAPI.on('process:error', deployErrorHandler);

    } catch (err: any) {
      setError(err.message);
      setIsDeploying(false);
    }
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Paper sx={{ p: 3, mb: 2 }}>
        <Typography variant="h5" gutterBottom>
          Deploy Infrastructure as Code to Azure
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {success && (
          <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(false)}>
            {dryRun ? 'Deployment validation successful!' : 'Deployment completed successfully!'}
          </Alert>
        )}

        <Alert severity="info" sx={{ mb: 3 }}>
          <Typography variant="body2">
            This tab automatically generates IaC from the source tenant and deploys it to the target tenant. Ensure you have:
          </Typography>
          <ul style={{ marginTop: 8, marginBottom: 0 }}>
            <li>Scanned the source tenant (data in Neo4j)</li>
            <li>Service principal credentials in your .env file (AZURE_TENANT_2_*)</li>
            <li>Required permissions (Contributor role) on the target subscription</li>
          </ul>
        </Alert>

        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <TenantSelector
              label="Source Tenant"
              value={sourceTenantId}
              onChange={setSourceTenantId}
              disabled={isDeploying}
              required
              helperText="Scanned tenant to generate IaC from"
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <TenantSelector
              label="Gameboard Tenant"
              value={targetTenantId}
              onChange={setTargetTenantId}
              disabled={isDeploying}
              required
              helperText="Azure tenant for the Gameboard deployment"
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              label="Resource Group"
              value={resourceGroup}
              onChange={(e) => setResourceGroup(e.target.value)}
              disabled={isDeploying}
              fullWidth
              required
              placeholder="my-resource-group"
              helperText="Target resource group name (will be created if it doesn't exist)"
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              label="Azure Region"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              disabled={isDeploying}
              fullWidth
              placeholder="eastus"
              helperText="Azure region for resource deployment"
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              label="Subscription ID (Optional)"
              value={subscriptionId}
              onChange={(e) => setSubscriptionId(e.target.value)}
              disabled={isDeploying}
              fullWidth
              placeholder="00000000-0000-0000-0000-000000000000"
              helperText="Required for Bicep/ARM deployments"
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <FormControl fullWidth>
              <InputLabel>IaC Format</InputLabel>
              <Select
                value={iacFormat}
                onChange={(e) => setIacFormat(e.target.value as any)}
                disabled={isDeploying}
                label="IaC Format"
              >
                <MenuItem value="auto">Auto-detect</MenuItem>
                <MenuItem value="terraform">Terraform</MenuItem>
                <MenuItem value="bicep">Bicep</MenuItem>
                <MenuItem value="arm">ARM Template</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={dryRun}
                  onChange={(e) => setDryRun(e.target.checked)}
                  disabled={isDeploying}
                />
              }
              label="Dry Run (Plan/Validate only, don't actually deploy)"
            />
          </Grid>

          <Grid item xs={12}>
            <Button
              variant="contained"
              color="primary"
              startIcon={<DeployIcon />}
              onClick={handleDeploy}
              disabled={isDeploying}
              size="large"
            >
              {isDeploying ? 'Deploying...' : (dryRun ? 'Validate Deployment' : 'Deploy to Azure')}
            </Button>
          </Grid>
        </Grid>
      </Paper>

      <Paper sx={{ flex: 1, minHeight: 0, p: 2 }}>
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
          <Typography variant="h6" gutterBottom>
            Deployment Output
          </Typography>
          <Box sx={{
            flex: 1,
            backgroundColor: '#1e1e1e',
            color: '#cccccc',
            fontFamily: 'monospace',
            fontSize: '13px',
            overflow: 'auto',
            p: 2,
            borderRadius: 1,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all'
          }}>
            {terminalOutput || (isDeploying ? 'Deploying infrastructure...\n' : 'Deployment output will appear here')}
          </Box>
        </Box>
      </Paper>
    </Box>
  );
};

export default DeployTab;
