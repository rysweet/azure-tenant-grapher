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
import { CloudUpload as DeployIcon, FolderOpen as FolderIcon } from '@mui/icons-material';

interface ProcessOutputData {
  id: string;
  data: string[];
}

interface ProcessExitData {
  id: string;
  code: number;
}

const DeployTab: React.FC = () => {
  const [iacDir, setIacDir] = useState('output/iac');
  const [targetTenantId, setTargetTenantId] = useState('');
  const [resourceGroup, setResourceGroup] = useState('');
  const [location, setLocation] = useState('eastus');
  const [subscriptionId, setSubscriptionId] = useState('');
  const [iacFormat, setIacFormat] = useState<'auto' | 'terraform' | 'bicep' | 'arm'>('auto');
  const [dryRun, setDryRun] = useState(true);
  const [isDeploying, setIsDeploying] = useState(false);
  const [terminalOutput, setTerminalOutput] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [selectedTenant, setSelectedTenant] = useState<'1' | '2'>('2');

  // Load tenant ID based on selected tenant
  React.useEffect(() => {
    if (selectedTenant === '1') {
      setTargetTenantId('3cd87a41-1f61-4aef-a212-cefdecd9a2d1'); // DefenderATEVET17
    } else if (selectedTenant === '2') {
      setTargetTenantId('506f82b2-e2e7-40a2-b0be-ea6f8cb908f8'); // Simuland
    }
  }, [selectedTenant]);

  const handleDeploy = async () => {
    if (!iacDir || !targetTenantId || !resourceGroup) {
      setError('IaC Directory, Target Tenant ID, and Resource Group are required');
      return;
    }

    setError(null);
    setSuccess(false);
    setIsDeploying(true);
    setTerminalOutput('');

    const args = [
      '--iac-dir', iacDir,
      '--target-tenant-id', targetTenantId,
      '--resource-group', resourceGroup,
      '--location', location,
    ];

    if (subscriptionId) {
      args.push('--subscription-id', subscriptionId);
    }

    if (iacFormat !== 'auto') {
      args.push('--format', iacFormat);
    }

    if (dryRun) {
      args.push('--dry-run');
    }

    try {
      const result = await window.electronAPI.cli.execute('deploy', args);

      let outputContent = '';

      const outputHandler = (data: ProcessOutputData) => {
        if (data.id === result.data.id) {
          const newContent = data.data.join('\n');
          outputContent += newContent + '\n';
          setTerminalOutput(outputContent);
        }
      };

      window.electronAPI.on('process:output', outputHandler);

      // Define error handler first (needed by exitHandler cleanup)
      const errorHandler = (data: any) => {
        if (data.processId === result.data.id || data.id === result.data.id) {
          setIsDeploying(false);
          setError(data.error || 'Process execution failed');

          // Clean up event listeners
          window.electronAPI.off?.('process:output', outputHandler);
          window.electronAPI.off?.('process:exit', exitHandler);
          window.electronAPI.off?.('process:error', errorHandler);
        }
      };

      const exitHandler = (data: ProcessExitData) => {
        if (data.id === result.data.id) {
          setIsDeploying(false);
          if (data.code === 0) {
            setSuccess(true);
          } else {
            // Extract error message from terminal output if available
            let errorMessage = `Deployment failed with exit code ${data.code}`;

            // Look for error patterns in terminal output
            if (outputContent) {
              const errorMatch = outputContent.match(/❌ Error: (.+)/);
              if (errorMatch) {
                errorMessage = errorMatch[1];
              } else if (outputContent.match(/\[ProcessManager\] Invalid command: (.+)/)) {
                const commandMatch = outputContent.match(/\[ProcessManager\] Invalid command: (.+)/);
                if (commandMatch) {
                  errorMessage = commandMatch[1];
                }
              } else if (outputContent.includes('Error:')) {
                // Try to extract any error line
                const lines = outputContent.split('\n');
                const errorLine = lines.find(line => line.includes('Error:'));
                if (errorLine) {
                  errorMessage = errorLine.replace(/^.*Error:\s*/, '');
                }
              }
            }

            setError(errorMessage);
          }

          // Clean up event listeners
          window.electronAPI.off?.('process:output', outputHandler);
          window.electronAPI.off?.('process:exit', exitHandler);
          window.electronAPI.off?.('process:error', errorHandler);
        }
      };

      window.electronAPI.on('process:exit', exitHandler);
      window.electronAPI.on('process:error', errorHandler);

    } catch (err: any) {
      setError(err.message);
      setIsDeploying(false);
    }
  };

  const handleSelectFolder = async () => {
    try {
      const result = await window.electronAPI.dialog?.showOpenDialog({
        properties: ['openDirectory'],
        title: 'Select IaC Directory',
      });

      if (result && !result.canceled && result.filePaths.length > 0) {
        setIacDir(result.filePaths[0]);
      }
    } catch (err: any) {
      setError(`Failed to select folder: ${err.message}`);
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
            This tab deploys generated IaC to a target Azure tenant. Ensure you have:
          </Typography>
          <ul style={{ marginTop: 8, marginBottom: 0 }}>
            <li>Service principal credentials in your .env file (AZURE_TENANT_2_*)</li>
            <li>Required permissions (Contributor role) on the target subscription</li>
            <li>Generated IaC files in the specified directory</li>
          </ul>
        </Alert>

        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
              <TextField
                label="IaC Directory"
                value={iacDir}
                onChange={(e) => setIacDir(e.target.value)}
                disabled={isDeploying}
                fullWidth
                required
                placeholder="output/iac"
                helperText="Path to directory containing IaC files (main.tf.json, *.bicep, etc.)"
              />
              <Button
                startIcon={<FolderIcon />}
                onClick={handleSelectFolder}
                disabled={isDeploying}
                variant="outlined"
              >
                Browse
              </Button>
            </Box>
          </Grid>

          <Grid item xs={12} md={6}>
            <FormControl fullWidth required>
              <InputLabel>Target Tenant</InputLabel>
              <Select
                value={selectedTenant}
                onChange={(e) => setSelectedTenant(e.target.value as '1' | '2')}
                disabled={isDeploying}
                label="Target Tenant"
              >
                <MenuItem value="1">Tenant 1 (DefenderATEVET17)</MenuItem>
                <MenuItem value="2">Tenant 2 (Simuland)</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              label="Target Tenant ID"
              value={targetTenantId}
              onChange={(e) => setTargetTenantId(e.target.value)}
              disabled={isDeploying}
              fullWidth
              required
              placeholder="00000000-0000-0000-0000-000000000000"
              helperText="Azure AD tenant ID for the target environment"
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
