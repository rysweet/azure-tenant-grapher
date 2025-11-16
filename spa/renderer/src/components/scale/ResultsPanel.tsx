import React, { useEffect, useRef } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Alert,
  Divider,
} from '@mui/material';
import {
  CheckCircle,
  Error as ErrorIcon,
  Visibility as VisualizeIcon,
  Refresh as RefreshIcon,
  CloudDownload as IaCIcon,
} from '@mui/icons-material';
import { useScaleOperations } from '../../context/ScaleOperationsContext';
import { useApp } from '../../context/AppContext';
import { OperationResult } from '../../types/scaleOperations';

interface ResultsPanelProps {
  result: OperationResult;
}

const ResultsPanel: React.FC<ResultsPanelProps> = ({ result }) => {
  const { dispatch } = useScaleOperations();
  const { dispatch: appDispatch } = useApp();
  const firstActionButtonRef = useRef<HTMLButtonElement>(null);

  // Focus first action button when results are displayed for accessibility
  useEffect(() => {
    if (firstActionButtonRef.current) {
      firstActionButtonRef.current.focus();
    }
  }, []);

  const handleRunAnother = () => {
    dispatch({ type: 'SET_SHOW_RESULTS', payload: false });
    dispatch({ type: 'CLEAR_OPERATION' });
  };

  const handleViewGraph = () => {
    appDispatch({ type: 'SET_ACTIVE_TAB', payload: 'visualize' });
  };

  const handleGenerateIaC = () => {
    appDispatch({ type: 'SET_ACTIVE_TAB', payload: 'generate-iac' });
  };

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    if (mins > 0) {
      return `${mins} minute${mins > 1 ? 's' : ''} ${secs} second${secs !== 1 ? 's' : ''}`;
    }
    return `${secs} second${secs !== 1 ? 's' : ''}`;
  };

  const nodesDelta = result.afterStats.totalNodes - result.beforeStats.totalNodes;
  const relationshipsDelta = result.afterStats.totalRelationships - result.beforeStats.totalRelationships;

  return (
    <Paper sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        {result.success ? (
          <CheckCircle color="success" sx={{ fontSize: 40 }} />
        ) : (
          <ErrorIcon color="error" sx={{ fontSize: 40 }} />
        )}
        <Box sx={{ flex: 1 }}>
          <Typography variant="h5">
            {result.success ? 'Operation Completed Successfully' : 'Operation Failed'}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {new Date(result.timestamp).toLocaleString()} • Duration: {formatDuration(result.duration)}
          </Typography>
        </Box>
      </Box>

      {/* Error Message */}
      {!result.success && result.error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          <Typography variant="subtitle2">Error Details:</Typography>
          <Typography variant="body2">{result.error}</Typography>
        </Alert>
      )}

      {/* Operation Summary */}
      {result.success && (
        <>
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Operation Summary
            </Typography>
            <Alert severity="success" icon={<CheckCircle />}>
              {result.operationType === 'scale-up' ? (
                <>
                  Successfully scaled up graph by adding{' '}
                  <strong>{result.scaleUpStats?.nodesCreated || 0}</strong> synthetic nodes
                  and <strong>{result.scaleUpStats?.relationshipsCreated || 0}</strong> relationships.
                </>
              ) : (
                <>
                  Successfully sampled graph, retaining{' '}
                  <strong>{result.scaleDownStats?.nodesRetained || 0}</strong> nodes
                  (removed <strong>{result.scaleDownStats?.nodesDeleted || 0}</strong>).
                </>
              )}
            </Alert>
          </Box>

          {/* Before & After Comparison */}
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Before & After Comparison
            </Typography>
            <TableContainer component={Paper} variant="outlined">
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Metric</TableCell>
                    <TableCell align="right">Before</TableCell>
                    <TableCell align="right">After</TableCell>
                    <TableCell align="right">Change</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  <TableRow>
                    <TableCell>Total Nodes</TableCell>
                    <TableCell align="right">{result.beforeStats.totalNodes.toLocaleString()}</TableCell>
                    <TableCell align="right">{result.afterStats.totalNodes.toLocaleString()}</TableCell>
                    <TableCell align="right">
                      <Chip
                        label={`${nodesDelta >= 0 ? '+' : ''}${nodesDelta.toLocaleString()}`}
                        size="small"
                        color={nodesDelta > 0 ? 'success' : nodesDelta < 0 ? 'error' : 'default'}
                      />
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Total Relationships</TableCell>
                    <TableCell align="right">{result.beforeStats.totalRelationships.toLocaleString()}</TableCell>
                    <TableCell align="right">{result.afterStats.totalRelationships.toLocaleString()}</TableCell>
                    <TableCell align="right">
                      <Chip
                        label={`${relationshipsDelta >= 0 ? '+' : ''}${relationshipsDelta.toLocaleString()}`}
                        size="small"
                        color={relationshipsDelta > 0 ? 'success' : relationshipsDelta < 0 ? 'error' : 'default'}
                      />
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Synthetic Nodes</TableCell>
                    <TableCell align="right">{result.beforeStats.syntheticNodes.toLocaleString()}</TableCell>
                    <TableCell align="right">{result.afterStats.syntheticNodes.toLocaleString()}</TableCell>
                    <TableCell align="right">
                      <Chip
                        label={`${result.afterStats.syntheticNodes - result.beforeStats.syntheticNodes}`}
                        size="small"
                        color="warning"
                      />
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </TableContainer>
            {result.operationType === 'scale-up' && result.afterStats.syntheticNodes > 0 && (
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                Synthetic nodes represent{' '}
                {((result.afterStats.syntheticNodes / result.afterStats.totalNodes) * 100).toFixed(1)}%
                of the total graph
              </Typography>
            )}
          </Box>

          {/* Validation Results */}
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Validation Results
            </Typography>
            <Card variant="outlined">
              <CardContent>
                {result.validationResults.length === 0 ? (
                  <Typography variant="body2" color="text.secondary">
                    No validation checks were performed.
                  </Typography>
                ) : (
                  <>
                    <Typography variant="subtitle2" gutterBottom>
                      {result.validationResults.filter(v => v.passed).length} / {result.validationResults.length} checks passed
                    </Typography>
                    <Box sx={{ mt: 2 }}>
                      {result.validationResults.map((validation, idx) => (
                        <Box key={idx} sx={{ mb: 2 }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                            {validation.passed ? (
                              <CheckCircle color="success" fontSize="small" />
                            ) : (
                              <ErrorIcon color="error" fontSize="small" />
                            )}
                            <Typography variant="body2" fontWeight="bold">
                              {validation.checkName}
                            </Typography>
                            <Chip
                              label={validation.passed ? 'Passed' : 'Failed'}
                              size="small"
                              color={validation.passed ? 'success' : 'error'}
                            />
                          </Box>
                          <Typography variant="body2" color="text.secondary" sx={{ ml: 4 }}>
                            {validation.message}
                          </Typography>
                        </Box>
                      ))}
                    </Box>
                  </>
                )}
              </CardContent>
            </Card>
          </Box>

          {/* Output Location (for scale-down) */}
          {result.operationType === 'scale-down' && result.scaleDownStats?.outputPath && (
            <Box sx={{ mb: 3 }}>
              <Typography variant="h6" gutterBottom>
                Output Location
              </Typography>
              <Alert severity="info">
                <Typography variant="body2">
                  Sample exported to: <strong>{result.scaleDownStats.outputPath}</strong>
                </Typography>
              </Alert>
            </Box>
          )}
        </>
      )}

      <Divider sx={{ my: 3 }} />

      {/* Action Buttons */}
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
        <Button
          ref={firstActionButtonRef}
          variant="outlined"
          startIcon={<VisualizeIcon />}
          onClick={handleViewGraph}
        >
          View in Graph Visualizer
        </Button>

        {result.operationType === 'scale-down' && result.success && (
          <Button
            variant="outlined"
            startIcon={<IaCIcon />}
            onClick={handleGenerateIaC}
          >
            Generate IaC from Sample
          </Button>
        )}

        <Button
          variant="contained"
          color="primary"
          startIcon={<RefreshIcon />}
          onClick={handleRunAnother}
        >
          Run Another Operation
        </Button>
      </Box>
    </Paper>
  );
};

export default ResultsPanel;
