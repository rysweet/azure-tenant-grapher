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
import { CheckCircle as ValidateIcon, Download as DownloadIcon } from '@mui/icons-material';

interface ProcessOutputData {
  id: string;
  data: string[];
}

interface ProcessExitData {
  id: string;
  code: number;
}

const ValidateDeploymentTab: React.FC = () => {
  const [sourceTenantId, setSourceTenantId] = useState('');
  const [targetTenantId, setTargetTenantId] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [targetFilter, setTargetFilter] = useState('');
  const [outputPath, setOutputPath] = useState('');
  const [outputFormat, setOutputFormat] = useState<'markdown' | 'json'>('markdown');
  const [verbose, setVerbose] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [terminalOutput, setTerminalOutput] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [validationResult, setValidationResult] = useState<string | null>(null);
  const [selectedSourceTenant, setSelectedSourceTenant] = useState<'1' | '2'>('1');
  const [selectedTargetTenant, setSelectedTargetTenant] = useState<'1' | '2'>('2');

  // Load tenant IDs based on selection
  React.useEffect(() => {
    if (selectedSourceTenant === '1') {
      setSourceTenantId('3cd87a41-1f61-4aef-a212-cefdecd9a2d1'); // DefenderATEVET17
    } else if (selectedSourceTenant === '2') {
      setSourceTenantId('506f82b2-e2e7-40a2-b0be-ea6f8cb908f8'); // Simuland
    }
  }, [selectedSourceTenant]);

  React.useEffect(() => {
    if (selectedTargetTenant === '1') {
      setTargetTenantId('3cd87a41-1f61-4aef-a212-cefdecd9a2d1'); // DefenderATEVET17
    } else if (selectedTargetTenant === '2') {
      setTargetTenantId('506f82b2-e2e7-40a2-b0be-ea6f8cb908f8'); // Simuland
    }
  }, [selectedTargetTenant]);

  const handleValidate = async () => {
    if (!sourceTenantId || !targetTenantId) {
      setError('Source and Gameboard Tenant IDs are required');
      return;
    }

    setError(null);
    setSuccess(false);
    setIsValidating(true);
    setTerminalOutput('');
    setValidationResult(null);

    const args = [
      '--source-tenant-id', sourceTenantId,
      '--target-tenant-id', targetTenantId,
      '--format', outputFormat,
    ];

    if (sourceFilter) {
      args.push('--source-filter', sourceFilter);
    }

    if (targetFilter) {
      args.push('--target-filter', targetFilter);
    }

    if (outputPath) {
      args.push('--output', outputPath);
    }

    if (verbose) {
      args.push('--verbose');
    }

    try {
      const result = await window.electronAPI.cli.execute('validate-deployment', args);

      let outputContent = '';

      const outputHandler = (data: ProcessOutputData) => {
        if (data.id === result.data.id) {
          const newContent = data.data.join('\n');
          outputContent += newContent + '\n';
          setTerminalOutput(outputContent);

          // If output format is markdown and no output file, capture the result
          if (!outputPath && outputFormat === 'markdown') {
            setValidationResult(outputContent);
          }
        }
      };

      window.electronAPI.on('process:output', outputHandler);

      // Define error handler first (needed by exitHandler cleanup)
      const errorHandler = (data: any) => {
        if (data.processId === result.data.id || data.id === result.data.id) {
          setIsValidating(false);
          setError(data.error || 'Process execution failed');

          // Clean up event listeners
          window.electronAPI.off?.('process:output', outputHandler);
          window.electronAPI.off?.('process:exit', exitHandler);
          window.electronAPI.off?.('process:error', errorHandler);
        }
      };

      const exitHandler = (data: ProcessExitData) => {
        if (data.id === result.data.id) {
          setIsValidating(false);
          if (data.code === 0) {
            setSuccess(true);
          } else {
            // Extract error message from terminal output if available
            let errorMessage = `Validation failed with exit code ${data.code}`;

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
      setIsValidating(false);
    }
  };

  const handleDownloadReport = () => {
    if (!validationResult) return;

    const blob = new Blob([validationResult], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `validation-report-${Date.now()}.${outputFormat === 'json' ? 'json' : 'md'}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Paper sx={{ p: 3, mb: 2 }}>
        <Typography variant="h5" gutterBottom>
          Validate Cross-Tenant Deployment
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {success && (
          <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(false)}>
            Validation completed successfully! Check the output below for results.
          </Alert>
        )}

        <Alert severity="info" sx={{ mb: 3 }}>
          <Typography variant="body2">
            This tab compares the Neo4j graphs for source and target tenants to validate that
            a deployment successfully replicated the configuration. Both tenants must be scanned
            and available in the graph database.
          </Typography>
        </Alert>

        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <FormControl fullWidth required>
              <InputLabel>Source Tenant</InputLabel>
              <Select
                value={selectedSourceTenant}
                onChange={(e) => setSelectedSourceTenant(e.target.value as '1' | '2')}
                disabled={isValidating}
                label="Source Tenant"
              >
                <MenuItem value="1">Tenant 1 (DefenderATEVET17)</MenuItem>
                <MenuItem value="2">Tenant 2 (Simuland)</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} md={6}>
            <FormControl fullWidth required>
              <InputLabel>Gameboard Tenant</InputLabel>
              <Select
                value={selectedTargetTenant}
                onChange={(e) => setSelectedTargetTenant(e.target.value as '1' | '2')}
                disabled={isValidating}
                label="Gameboard Tenant"
              >
                <MenuItem value="1">Tenant 1 (DefenderATEVET17)</MenuItem>
                <MenuItem value="2">Tenant 2 (Simuland)</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              label="Source Tenant ID"
              value={sourceTenantId}
              onChange={(e) => setSourceTenantId(e.target.value)}
              disabled={isValidating}
              fullWidth
              required
              placeholder="00000000-0000-0000-0000-000000000000"
              helperText="Tenant ID to compare from (source)"
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              label="Gameboard Tenant ID"
              value={targetTenantId}
              onChange={(e) => setTargetTenantId(e.target.value)}
              disabled={isValidating}
              fullWidth
              required
              placeholder="00000000-0000-0000-0000-000000000000"
              helperText="Tenant ID to compare to (gameboard)"
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              label="Source Filter (Optional)"
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              disabled={isValidating}
              fullWidth
              placeholder="resourceGroup=SimuLand"
              helperText="Filter source resources (e.g., resourceGroup=RG1)"
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              label="Target Filter (Optional)"
              value={targetFilter}
              onChange={(e) => setTargetFilter(e.target.value)}
              disabled={isValidating}
              fullWidth
              placeholder="resourceGroup=ReplicatedRG"
              helperText="Filter target resources (e.g., resourceGroup=RG2)"
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              label="Output File Path (Optional)"
              value={outputPath}
              onChange={(e) => setOutputPath(e.target.value)}
              disabled={isValidating}
              fullWidth
              placeholder="validation-report.md"
              helperText="Save report to file (leave empty to display in terminal)"
            />
          </Grid>

          <Grid item xs={12} md={6}>
            <FormControl fullWidth>
              <InputLabel>Output Format</InputLabel>
              <Select
                value={outputFormat}
                onChange={(e) => setOutputFormat(e.target.value as 'markdown' | 'json')}
                disabled={isValidating}
                label="Output Format"
              >
                <MenuItem value="markdown">Markdown</MenuItem>
                <MenuItem value="json">JSON</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={verbose}
                  onChange={(e) => setVerbose(e.target.checked)}
                  disabled={isValidating}
                />
              }
              label="Verbose output (show detailed logging)"
            />
          </Grid>

          <Grid item xs={12}>
            <Box sx={{ display: 'flex', gap: 2 }}>
              <Button
                variant="contained"
                color="primary"
                startIcon={<ValidateIcon />}
                onClick={handleValidate}
                disabled={isValidating}
                size="large"
              >
                {isValidating ? 'Validating...' : 'Validate Deployment'}
              </Button>

              {validationResult && !outputPath && (
                <Button
                  variant="outlined"
                  startIcon={<DownloadIcon />}
                  onClick={handleDownloadReport}
                  size="large"
                >
                  Download Report
                </Button>
              )}
            </Box>
          </Grid>
        </Grid>
      </Paper>

      <Paper sx={{ flex: 1, minHeight: 0, p: 2 }}>
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
          <Typography variant="h6" gutterBottom>
            Validation Output
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
            {terminalOutput || (isValidating ? 'Validating deployment...\n' : 'Validation output will appear here')}
          </Box>
        </Box>
      </Paper>
    </Box>
  );
};

export default ValidateDeploymentTab;
