import React, { useState } from 'react';
import {
  Box,
  Paper,
  Button,
  Typography,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  CircularProgress,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  LinearProgress,
} from '@mui/material';
import {
  CleaningServices as CleanIcon,
  CheckCircle as ValidateIcon,
  Assessment as StatsIcon,
  Help as HelpIcon,
} from '@mui/icons-material';
import axios from 'axios';
import { useApp } from '../../context/AppContext';
import { useScaleOperations } from '../../context/ScaleOperationsContext';
import { useGraphStats } from '../../hooks/useGraphStats';
import { CleanSyntheticResponse, ValidationResult } from '../../types/scaleOperations';

const API_BASE_URL = 'http://localhost:3001';

const QuickActionsBar: React.FC = () => {
  const { state: appState } = useApp();
  const { state } = useScaleOperations();
  const { refreshStats } = useGraphStats(appState.config.tenantId);

  const [cleanDialogOpen, setCleanDialogOpen] = useState(false);
  const [statsDialogOpen, setStatsDialogOpen] = useState(false);
  const [validationDialogOpen, setValidationDialogOpen] = useState(false);
  const [helpDialogOpen, setHelpDialogOpen] = useState(false);

  const [cleaning, setCleaning] = useState(false);
  const [validating, setValidating] = useState(false);
  const [cleanResult, setCleanResult] = useState<CleanSyntheticResponse | null>(null);
  const [validationResults, setValidationResults] = useState<ValidationResult[]>([]);
  const [error, setError] = useState<string | null>(null);

  const tenantId = appState.config.tenantId;

  const handleCleanSynthetic = async () => {
    if (!tenantId) {
      setError('Tenant ID is required');
      return;
    }

    setCleaning(true);
    setError(null);
    setCleanResult(null);

    try {
      const response = await axios.post<CleanSyntheticResponse>(`${API_BASE_URL}/api/scale/clean-synthetic`, {
        tenantId,
      });
      setCleanResult(response.data);
      if (response.data.success) {
        await refreshStats();
      }
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Failed to clean synthetic data');
    } finally {
      setCleaning(false);
    }
  };

  const handleValidateGraph = async () => {
    if (!tenantId) {
      setError('Tenant ID is required');
      return;
    }

    setValidating(true);
    setError(null);
    setValidationResults([]);

    try {
      const response = await axios.post<ValidationResult[]>(`${API_BASE_URL}/api/scale/validate`, {
        tenantId,
      });
      setValidationResults(response.data);
      setValidationDialogOpen(true);
    } catch (err: any) {
      setError(err.response?.data?.error || err.message || 'Failed to validate graph');
    } finally {
      setValidating(false);
    }
  };

  const handleShowStats = async () => {
    await refreshStats();
    setStatsDialogOpen(true);
  };

  const formatNumber = (num: number): string => {
    return num.toLocaleString();
  };

  const nodeTypeEntries = state.currentGraphStats?.nodeTypes
    ? Object.entries(state.currentGraphStats.nodeTypes).sort((a, b) => b[1] - a[1])
    : [];

  const relationshipTypeEntries = state.currentGraphStats?.relationshipTypes
    ? Object.entries(state.currentGraphStats.relationshipTypes).sort((a, b) => b[1] - a[1])
    : [];

  return (
    <>
      <Paper sx={{ p: 2 }}>
        <Typography variant="subtitle2" gutterBottom>
          Quick Actions
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <Button
            variant="outlined"
            startIcon={<CleanIcon />}
            onClick={() => setCleanDialogOpen(true)}
            disabled={!tenantId}
          >
            Clean Synthetic Data
          </Button>

          <Button
            variant="outlined"
            startIcon={<ValidateIcon />}
            onClick={handleValidateGraph}
            disabled={!tenantId || validating}
          >
            {validating ? 'Validating...' : 'Validate Graph'}
          </Button>

          <Button
            variant="outlined"
            startIcon={<StatsIcon />}
            onClick={handleShowStats}
            disabled={!tenantId}
          >
            Show Statistics
          </Button>

          <Button
            variant="outlined"
            startIcon={<HelpIcon />}
            onClick={() => setHelpDialogOpen(true)}
          >
            Help
          </Button>
        </Box>
      </Paper>

      {/* Clean Synthetic Data Dialog */}
      <Dialog open={cleanDialogOpen} onClose={() => !cleaning && setCleanDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Clean Synthetic Data</DialogTitle>
        <DialogContent>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          {cleanResult && cleanResult.success && (
            <Alert severity="success" sx={{ mb: 2 }}>
              Successfully removed {cleanResult.nodesDeleted} synthetic nodes
              and {cleanResult.relationshipsDeleted} relationships.
            </Alert>
          )}

          {!cleanResult && !error && (
            <Typography variant="body2" color="text.secondary">
              This will permanently delete all nodes labeled as synthetic from the graph.
              This operation cannot be undone.
            </Typography>
          )}

          {cleaning && (
            <Box sx={{ display: 'flex', justifyContent: 'center', my: 3 }}>
              <CircularProgress />
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCleanDialogOpen(false)} disabled={cleaning}>
            {cleanResult ? 'Close' : 'Cancel'}
          </Button>
          {!cleanResult && (
            <Button onClick={handleCleanSynthetic} color="error" variant="contained" disabled={cleaning}>
              {cleaning ? 'Cleaning...' : 'Confirm Clean'}
            </Button>
          )}
        </DialogActions>
      </Dialog>

      {/* Validation Results Dialog */}
      <Dialog open={validationDialogOpen} onClose={() => setValidationDialogOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Graph Validation Results</DialogTitle>
        <DialogContent>
          {validationResults.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No validation results available.
            </Typography>
          ) : (
            <Box>
              <Typography variant="subtitle2" gutterBottom>
                {validationResults.filter(v => v.passed).length} / {validationResults.length} checks passed
              </Typography>
              {validationResults.map((validation, idx) => (
                <Box key={idx} sx={{ mb: 2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    {validation.passed ? (
                      <CheckCircle color="success" fontSize="small" />
                    ) : (
                      <CleanIcon color="error" fontSize="small" />
                    )}
                    <Typography variant="body2" fontWeight="bold">
                      {validation.checkName}
                    </Typography>
                  </Box>
                  <Typography variant="body2" color="text.secondary" sx={{ ml: 4 }}>
                    {validation.message}
                  </Typography>
                </Box>
              ))}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setValidationDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Statistics Dialog */}
      <Dialog open={statsDialogOpen} onClose={() => setStatsDialogOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Graph Statistics</DialogTitle>
        <DialogContent>
          {!state.currentGraphStats ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', my: 3 }}>
              <CircularProgress />
            </Box>
          ) : (
            <Box>
              <Typography variant="h6" gutterBottom>
                Overview
              </Typography>
              <TableContainer component={Paper} variant="outlined" sx={{ mb: 3 }}>
                <Table size="small">
                  <TableBody>
                    <TableRow>
                      <TableCell>Total Nodes</TableCell>
                      <TableCell align="right">
                        <strong>{formatNumber(state.currentGraphStats.totalNodes)}</strong>
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>Synthetic Nodes</TableCell>
                      <TableCell align="right">
                        <strong>{formatNumber(state.currentGraphStats.syntheticNodes)}</strong>
                        {state.currentGraphStats.totalNodes > 0 && (
                          <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                            ({((state.currentGraphStats.syntheticNodes / state.currentGraphStats.totalNodes) * 100).toFixed(1)}%)
                          </Typography>
                        )}
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>Total Relationships</TableCell>
                      <TableCell align="right">
                        <strong>{formatNumber(state.currentGraphStats.totalRelationships)}</strong>
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </TableContainer>

              <Typography variant="h6" gutterBottom>
                Node Type Distribution
              </Typography>
              <Box sx={{ mb: 3 }}>
                {nodeTypeEntries.slice(0, 10).map(([type, count]) => (
                  <Box key={type} sx={{ mb: 1 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                      <Typography variant="body2">{type}</Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {formatNumber(count)}
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={(count / state.currentGraphStats.totalNodes) * 100}
                      sx={{ height: 6, borderRadius: 1 }}
                    />
                  </Box>
                ))}
              </Box>

              <Typography variant="h6" gutterBottom>
                Relationship Type Distribution
              </Typography>
              <Box>
                {relationshipTypeEntries.slice(0, 10).map(([type, count]) => (
                  <Box key={type} sx={{ mb: 1 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                      <Typography variant="body2">{type}</Typography>
                      <Typography variant="body2" fontWeight="bold">
                        {formatNumber(count)}
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={(count / state.currentGraphStats.totalRelationships) * 100}
                      sx={{ height: 6, borderRadius: 1 }}
                    />
                  </Box>
                ))}
              </Box>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setStatsDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Help Dialog */}
      <Dialog open={helpDialogOpen} onClose={() => setHelpDialogOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>Scale Operations Help</DialogTitle>
        <DialogContent>
          <Typography variant="h6" gutterBottom>
            Scale-Up Operations
          </Typography>
          <Typography variant="body2" paragraph>
            Add synthetic nodes to your graph for testing and validation purposes. Choose from template-based,
            scenario-based, or random generation strategies.
          </Typography>

          <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
            Scale-Down Operations
          </Typography>
          <Typography variant="body2" paragraph>
            Sample a subset of your graph using various algorithms (Forest-Fire, MHRW, Pattern-based).
            Export to file, create a new tenant, or generate IaC directly.
          </Typography>

          <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
            Quick Actions
          </Typography>
          <Typography variant="body2" component="div">
            <ul style={{ margin: 0, paddingLeft: 20 }}>
              <li><strong>Clean Synthetic Data</strong>: Remove all synthetic nodes from the graph</li>
              <li><strong>Validate Graph</strong>: Run integrity checks on the graph structure</li>
              <li><strong>Show Statistics</strong>: View detailed graph metrics and distributions</li>
            </ul>
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setHelpDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default QuickActionsBar;
