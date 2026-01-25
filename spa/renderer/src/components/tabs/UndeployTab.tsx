import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Button,
  Typography,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Checkbox,
  TextField,
  CircularProgress,
} from '@mui/material';
import {
  Delete as DeleteIcon,
  Refresh as RefreshIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';

// const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:3001';

interface Deployment {
  id: string;
  status: string;
  tenant: string;
  directory: string;
  deployed_at: string;
  destroyed_at?: string;
  resources: Record<string, number>;
  terraform_version?: string;
}

interface ProcessOutputData {
  id: string;
  data: string[];
}

interface ProcessExitData {
  id: string;
  code: number;
}

const UndeployTab: React.FC = () => {
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedDeployment, setSelectedDeployment] = useState<Deployment | null>(null);
  const [confirmDialog, setConfirmDialog] = useState(false);
  const [confirmText, setConfirmText] = useState('');
  const [selectedTenant, setSelectedTenant] = useState<'1' | '2'>('1');
  const [dryRun, setDryRun] = useState(false);
  const [isUndeploying, setIsUndeploying] = useState(false);
  const [terminalOutput, setTerminalOutput] = useState('');
  const [outputDialog, setOutputDialog] = useState(false);

  // Fetch deployments on mount
  useEffect(() => {
    fetchDeployments();
  }, []);

  const fetchDeployments = async () => {
    setLoading(true);
    setError(null);

    // Timeout safety mechanism - reset loading after 30 seconds
    const timeoutId = setTimeout(() => {
      setLoading(false);
      setError('Request timed out after 30 seconds. Please try again.');
    }, 30000);

    try {
      const result = await window.electronAPI.cli.execute('list-deployments', ['--json']);

      // Accumulate all output chunks
      const outputChunks: string[] = [];

      const outputHandler = (data: ProcessOutputData) => {
        if (data.id === result.data.id) {
          // Collect all output chunks - don't parse yet!
          outputChunks.push(...data.data);
        }
      };

      const exitHandler = (data: ProcessExitData) => {
        if (data.id === result.data.id) {
          setLoading(false);
          clearTimeout(timeoutId);

          // Clean up event listeners to prevent accumulation
          window.electronAPI?.off?.('process:output', outputHandler);
          window.electronAPI?.off?.('process:exit', exitHandler);

          // Handle non-zero exit codes
          if (data.code !== 0) {
            setError(`Failed to fetch deployments (exit code ${data.code})`);
            return;
          }

          // Now parse the complete JSON output
          try {
            const completeOutput = outputChunks.join('').trim();
            if (!completeOutput) {
              // Empty output means no deployments
              setDeployments([]);
              return;
            }

            // Extract JSON from mixed output (status messages + JSON)
            // Find the first '[' which marks the start of the JSON array
            const jsonStartIndex = completeOutput.indexOf('[');

            if (jsonStartIndex === -1) {
              // No JSON array found - might be empty or error output
              // Check if output contains "no deployments" or similar messages
              if (completeOutput.toLowerCase().includes('no deployment') ||
                  completeOutput.toLowerCase().includes('empty')) {
                setDeployments([]);
                return;
              }
              // Otherwise it's an error
              setError('No deployment data found in response');
              return;
            }

            // Find the matching closing ']' by counting brackets
            let bracketCount = 0;
            let jsonEndIndex = -1;

            for (let i = jsonStartIndex; i < completeOutput.length; i++) {
              if (completeOutput[i] === '[') bracketCount++;
              if (completeOutput[i] === ']') bracketCount--;

              if (bracketCount === 0) {
                jsonEndIndex = i + 1;
                break;
              }
            }

            if (jsonEndIndex === -1) {
              setError('Incomplete JSON data received');
              return;
            }

            // Extract and parse the JSON portion
            const jsonString = completeOutput.substring(jsonStartIndex, jsonEndIndex);
            const deploymentData = JSON.parse(jsonString);
            setDeployments(Array.isArray(deploymentData) ? deploymentData : []);
          } catch (e) {
            const errorMsg = e instanceof Error ? e.message : 'Failed to parse deployment data';
            setError(`Error parsing deployment data: ${errorMsg}`);
          }
        }
      };

      window.electronAPI.on('process:output', outputHandler);
      window.electronAPI.on('process:exit', exitHandler);

    } catch (err: any) {
      clearTimeout(timeoutId);
      setError(err.message || 'Failed to fetch deployments');
      setLoading(false);
    }
  };

  const handleUndeploy = (deployment: Deployment) => {
    setSelectedDeployment(deployment);
    setConfirmDialog(true);
    setConfirmText('');
  };

  const confirmUndeploy = async () => {
    if (!selectedDeployment) return;

    // Validate confirmation text
    if (confirmText !== selectedDeployment.id) {
      setError('Deployment ID does not match. Please type it exactly.');
      return;
    }

    setConfirmDialog(false);
    setIsUndeploying(true);
    setTerminalOutput('');
    setOutputDialog(true);

    const args = [
      '--deployment-id', selectedDeployment.id,
      '--tenant', selectedTenant,
      '--force', // We've already confirmed
    ];

    if (dryRun) {
      args.push('--dry-run');
    }

    try {
      const result = await window.electronAPI.cli.execute('undeploy', args);

      let outputContent = '';

      const outputHandler = (data: ProcessOutputData) => {
        if (data.id === result.data.id) {
          const newContent = data.data.join('\n');
          outputContent += newContent + '\n';
          setTerminalOutput(outputContent);
        }
      };

      const exitHandler = (data: ProcessExitData) => {
        if (data.id === result.data.id) {
          setIsUndeploying(false);

          if (data.code === 0) {
            // Refresh deployments list
            fetchDeployments();
          } else {
            setError(`Undeployment failed with exit code ${data.code}`);
          }

          window.electronAPI?.off?.('process:output', outputHandler);
          window.electronAPI?.off?.('process:exit', exitHandler);
        }
      };

      window.electronAPI.on('process:output', outputHandler);
      window.electronAPI.on('process:exit', exitHandler);

    } catch (err: any) {
      setError(err.message);
      setIsUndeploying(false);
    }
  };

  const getStatusChip = (status: string) => {
    switch (status) {
      case 'active':
        return <Chip label={status} color="success" size="small" />;
      case 'destroyed':
        return <Chip label={status} color="default" size="small" />;
      case 'failed':
        return <Chip label={status} color="error" size="small" />;
      default:
        return <Chip label={status} size="small" />;
    }
  };

  const getTotalResources = (resources: Record<string, number>) => {
    return Object.values(resources).reduce((sum, count) => sum + count, 0);
  };

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Paper sx={{ p: 3, mb: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h5">
            Manage IaC Deployments
          </Typography>
          <Button
            startIcon={<RefreshIcon />}
            onClick={fetchDeployments}
            disabled={loading}
          >
            Refresh
          </Button>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <Alert severity="warning" icon={<WarningIcon />} sx={{ mb: 2 }}>
          <strong>Caution:</strong> Undeploying will permanently destroy Azure resources.
          This action cannot be undone. Always verify the deployment details before proceeding.
        </Alert>
      </Paper>

      <Paper sx={{ flex: 1, overflow: 'auto' }}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
            <CircularProgress />
          </Box>
        ) : deployments.length === 0 ? (
          <Box sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="body1" color="text.secondary">
              No deployments found. Deploy some infrastructure first using the Generate IaC tab.
            </Typography>
          </Box>
        ) : (
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Deployment ID</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Tenant</TableCell>
                  <TableCell>Resources</TableCell>
                  <TableCell>Deployed At</TableCell>
                  <TableCell>Directory</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {deployments.map((deployment) => (
                  <TableRow key={deployment.id}>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                        {deployment.id}
                      </Typography>
                    </TableCell>
                    <TableCell>{getStatusChip(deployment.status)}</TableCell>
                    <TableCell>{deployment.tenant}</TableCell>
                    <TableCell>{getTotalResources(deployment.resources)} resources</TableCell>
                    <TableCell>{formatDate(deployment.deployed_at)}</TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontSize: '0.85rem' }}>
                        {deployment.directory}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Button
                        startIcon={<DeleteIcon />}
                        color="error"
                        variant="outlined"
                        size="small"
                        onClick={() => handleUndeploy(deployment)}
                        disabled={deployment.status !== 'active' || isUndeploying}
                      >
                        Undeploy
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      {/* Confirmation Dialog */}
      <Dialog
        open={confirmDialog}
        onClose={() => setConfirmDialog(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <WarningIcon color="error" />
            Confirm Resource Destruction
          </Box>
        </DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ mb: 2 }}>
            You are about to destroy all resources in deployment <strong>{selectedDeployment?.id}</strong>.
            This will permanently delete {selectedDeployment ? getTotalResources(selectedDeployment.resources) : 0} Azure resources.
          </DialogContentText>

          <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Gameboard Tenant</InputLabel>
            <Select
              value={selectedTenant}
              onChange={(e) => setSelectedTenant(e.target.value as '1' | '2')}
              label="Gameboard Tenant"
            >
              <MenuItem value="1">Tenant 1 (Primary)</MenuItem>
              <MenuItem value="2">Tenant 2 (Simuland)</MenuItem>
            </Select>
          </FormControl>

          <FormControlLabel
            control={
              <Checkbox
                checked={dryRun}
                onChange={(e) => setDryRun(e.target.checked)}
              />
            }
            label="Dry run (preview only, don't actually destroy)"
            sx={{ mb: 2 }}
          />

          <Alert severity="error" sx={{ mb: 2 }}>
            To confirm, type the deployment ID exactly: <strong>{selectedDeployment?.id}</strong>
          </Alert>

          <TextField
            fullWidth
            label="Type deployment ID to confirm"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            error={!!error && error.includes('does not match')}
            helperText="Must match exactly to proceed"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDialog(false)}>
            Cancel
          </Button>
          <Button
            onClick={confirmUndeploy}
            color="error"
            variant="contained"
            disabled={confirmText !== selectedDeployment?.id}
          >
            {dryRun ? 'Preview Destruction' : 'Destroy Resources'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Output Dialog */}
      <Dialog
        open={outputDialog}
        onClose={() => !isUndeploying && setOutputDialog(false)}
        maxWidth="lg"
        fullWidth
      >
        <DialogTitle>
          {isUndeploying ? 'Undeploying Resources...' : 'Undeployment Complete'}
        </DialogTitle>
        <DialogContent>
          <Box sx={{
            backgroundColor: '#1e1e1e',
            color: '#cccccc',
            fontFamily: 'monospace',
            fontSize: '13px',
            overflow: 'auto',
            p: 2,
            borderRadius: 1,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-all',
            height: '400px'
          }}>
            {terminalOutput || 'Waiting for output...'}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => setOutputDialog(false)}
            disabled={isUndeploying}
          >
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default UndeployTab;
