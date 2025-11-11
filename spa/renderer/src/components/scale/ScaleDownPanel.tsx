import React, { useState, useCallback, useEffect } from 'react';
import {
  Box,
  Paper,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  Button,
  Typography,
  Alert,
  Checkbox,
  FormControlLabel,
  Grid,
  Divider,
  Radio,
  RadioGroup,
  Slider,
} from '@mui/material';
import {
  PlayArrow as ExecuteIcon,
  Visibility as PreviewIcon,
  Clear as ClearIcon,
  FolderOpen as BrowseIcon,
  Info as InfoIcon,
} from '@mui/icons-material';
import { useScaleOperations } from '../../context/ScaleOperationsContext';
import { useScaleDownOperation } from '../../hooks/useScaleDownOperation';
import { useApp } from '../../context/AppContext';
import { ScaleDownConfig, ScaleDownAlgorithm, OutputMode } from '../../types/scaleOperations';

const ScaleDownPanel: React.FC = () => {
  const { state: appState } = useApp();
  const { state, dispatch } = useScaleOperations();
  const { executeScaleDown, previewScaleDown, isRunning } = useScaleDownOperation();

  const [tenantId, setTenantId] = useState(appState.config.tenantId || '');
  const [algorithm, setAlgorithm] = useState<ScaleDownAlgorithm>('forest-fire');
  const [sampleSize, setSampleSize] = useState(500);
  const [burnInSteps, setBurnInSteps] = useState(5);
  const [forwardProbability, setForwardProbability] = useState(0.7);
  const [walkLength, setWalkLength] = useState(100);
  const [pattern, setPattern] = useState('');
  const [outputMode, setOutputMode] = useState<OutputMode>('file');
  const [outputPath, setOutputPath] = useState('outputs/sample_graph.json');
  const [iacFormat, setIacFormat] = useState<'terraform' | 'arm' | 'bicep'>('terraform');
  const [newTenantId, setNewTenantId] = useState('');
  const [validate, setValidate] = useState(true);
  const [preserveRelationships, setPreserveRelationships] = useState(true);
  const [includeProperties, setIncludeProperties] = useState(false);
  const [isPreviewing, setIsPreviewing] = useState(false);

  // Update tenant ID when app config changes
  useEffect(() => {
    if (appState.config.tenantId && !tenantId) {
      setTenantId(appState.config.tenantId);
    }
  }, [appState.config.tenantId, tenantId]);

  const getAlgorithmDescription = (alg: ScaleDownAlgorithm): string => {
    switch (alg) {
      case 'forest-fire':
        return 'Grows sample from seed nodes like fire spreading through forest';
      case 'mhrw':
        return 'Metropolis-Hastings Random Walk - statistically unbiased sampling';
      case 'pattern':
        return 'Sample nodes matching specific patterns or queries';
      default:
        return '';
    }
  };

  const buildConfig = useCallback((): ScaleDownConfig => {
    const config: ScaleDownConfig = {
      tenantId,
      algorithm,
      sampleSize,
      validate,
      outputMode,
      preserveRelationships,
      includeProperties,
    };

    if (algorithm === 'forest-fire') {
      config.burnInSteps = burnInSteps;
      config.forwardProbability = forwardProbability;
    } else if (algorithm === 'mhrw') {
      config.walkLength = walkLength;
    } else if (algorithm === 'pattern') {
      config.pattern = pattern;
    }

    if (outputMode === 'file') {
      config.outputPath = outputPath;
    } else if (outputMode === 'iac') {
      config.iacFormat = iacFormat;
    } else if (outputMode === 'new-tenant') {
      config.newTenantId = newTenantId;
    }

    return config;
  }, [tenantId, algorithm, sampleSize, validate, outputMode, burnInSteps, forwardProbability,
      walkLength, pattern, outputPath, iacFormat, newTenantId, preserveRelationships, includeProperties]);

  const handleExecute = async () => {
    const config = buildConfig();
    await executeScaleDown(config);
  };

  const handlePreview = async () => {
    setIsPreviewing(true);
    const config = buildConfig();
    await previewScaleDown(config);
    setIsPreviewing(false);
  };

  const handleBrowseOutput = async () => {
    // TODO: Implement file browser dialog via electron API
    console.log('Browse for output path');
  };

  const handleClear = () => {
    setTenantId(appState.config.tenantId || '');
    setAlgorithm('forest-fire');
    setSampleSize(500);
    setValidate(true);
    dispatch({ type: 'CLEAR_OPERATION' });
  };

  const isExecuteDisabled = !tenantId || isRunning || sampleSize <= 0;

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h6" gutterBottom>
        Scale-Down Configuration
      </Typography>

      {state.error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => dispatch({ type: 'SET_ERROR', payload: null })}>
          {state.error}
        </Alert>
      )}

      {state.previewResult && (
        <Alert severity="info" sx={{ mb: 2 }} icon={<InfoIcon />}>
          <Typography variant="subtitle2" gutterBottom>
            Preview: Scale-Down Operation
          </Typography>
          <Typography variant="body2">
            Will retain approximately <strong>{state.previewResult.estimatedNodes}</strong> nodes
            and <strong>{state.previewResult.estimatedRelationships}</strong> relationships
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Estimated duration: {state.previewResult.estimatedDuration} seconds
          </Typography>
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Tenant Configuration */}
        <Grid item xs={12}>
          <Typography variant="subtitle2" gutterBottom>
            Tenant Configuration
          </Typography>
        </Grid>

        <Grid item xs={12} md={6}>
          <TextField
            fullWidth
            label="Tenant ID"
            value={tenantId}
            onChange={(e) => setTenantId(e.target.value)}
            disabled={isRunning}
            required
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            helperText="Azure tenant ID to sample from"
          />
        </Grid>

        <Grid item xs={12} md={6}>
          <FormControl fullWidth>
            <InputLabel>Sampling Algorithm</InputLabel>
            <Select
              value={algorithm}
              onChange={(e) => setAlgorithm(e.target.value as ScaleDownAlgorithm)}
              disabled={isRunning}
              label="Sampling Algorithm"
            >
              <MenuItem value="forest-fire">Forest-Fire</MenuItem>
              <MenuItem value="mhrw">MHRW (Metropolis-Hastings)</MenuItem>
              <MenuItem value="pattern">Pattern-Based</MenuItem>
            </Select>
          </FormControl>
        </Grid>

        <Grid item xs={12}>
          <Alert severity="info" icon={<InfoIcon />}>
            {getAlgorithmDescription(algorithm)}
          </Alert>
        </Grid>

        {/* Sampling Parameters */}
        <Grid item xs={12}>
          <Typography variant="subtitle2" gutterBottom>
            Sampling Parameters
          </Typography>
        </Grid>

        <Grid item xs={12} md={6}>
          <TextField
            fullWidth
            type="number"
            label="Sample Size"
            value={sampleSize}
            onChange={(e) => setSampleSize(Number(e.target.value))}
            disabled={isRunning}
            required
            inputProps={{ min: 10, max: 100000, step: 10 }}
            helperText="Number of nodes to retain in sample"
          />
        </Grid>

        {/* Algorithm-Specific Parameters */}
        {algorithm === 'forest-fire' && (
          <>
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                type="number"
                label="Burn-In Steps"
                value={burnInSteps}
                onChange={(e) => setBurnInSteps(Number(e.target.value))}
                disabled={isRunning}
                inputProps={{ min: 1, max: 20, step: 1 }}
                helperText="Number of iterations to stabilize sample"
              />
            </Grid>

            <Grid item xs={12}>
              <Typography variant="body2" gutterBottom>
                Forward Probability: {forwardProbability.toFixed(2)}
              </Typography>
              <Slider
                value={forwardProbability}
                onChange={(_e, value) => setForwardProbability(value as number)}
                disabled={isRunning}
                min={0.0}
                max={1.0}
                step={0.1}
                marks
                valueLabelDisplay="auto"
                aria-label="forward probability"
              />
              <Typography variant="caption" color="text.secondary">
                Likelihood of following forward edges (0.0 = never, 1.0 = always)
              </Typography>
            </Grid>
          </>
        )}

        {algorithm === 'mhrw' && (
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              type="number"
              label="Walk Length"
              value={walkLength}
              onChange={(e) => setWalkLength(Number(e.target.value))}
              disabled={isRunning}
              inputProps={{ min: 10, max: 1000, step: 10 }}
              helperText="Length of each random walk"
            />
          </Grid>
        )}

        {algorithm === 'pattern' && (
          <Grid item xs={12}>
            <TextField
              fullWidth
              label="Pattern Query"
              value={pattern}
              onChange={(e) => setPattern(e.target.value)}
              disabled={isRunning}
              multiline
              rows={3}
              placeholder="e.g., VirtualMachine{name:contains('prod')}"
              helperText="Cypher-like pattern to match nodes"
            />
          </Grid>
        )}

        {/* Output Configuration */}
        <Grid item xs={12}>
          <Divider sx={{ my: 1 }} />
          <Typography variant="subtitle2" gutterBottom sx={{ mt: 2 }}>
            Output Configuration
          </Typography>
        </Grid>

        <Grid item xs={12}>
          <FormControl component="fieldset">
            <RadioGroup
              row
              value={outputMode}
              onChange={(e) => setOutputMode(e.target.value as OutputMode)}
            >
              <FormControlLabel
                value="file"
                control={<Radio />}
                label="Export to File"
                disabled={isRunning}
              />
              <FormControlLabel
                value="new-tenant"
                control={<Radio />}
                label="Create New Tenant"
                disabled={isRunning}
              />
              <FormControlLabel
                value="iac"
                control={<Radio />}
                label="Generate IaC"
                disabled={isRunning}
              />
            </RadioGroup>
          </FormControl>
        </Grid>

        {outputMode === 'file' && (
          <Grid item xs={12}>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <TextField
                fullWidth
                label="Output File Path"
                value={outputPath}
                onChange={(e) => setOutputPath(e.target.value)}
                disabled={isRunning}
                placeholder="outputs/sample_graph.json"
              />
              <Button
                variant="outlined"
                startIcon={<BrowseIcon />}
                onClick={handleBrowseOutput}
                disabled={isRunning}
                sx={{ minWidth: 120 }}
              >
                Browse
              </Button>
            </Box>
          </Grid>
        )}

        {outputMode === 'iac' && (
          <Grid item xs={12} md={6}>
            <FormControl fullWidth>
              <InputLabel>IaC Format</InputLabel>
              <Select
                value={iacFormat}
                onChange={(e) => setIacFormat(e.target.value as 'terraform' | 'arm' | 'bicep')}
                disabled={isRunning}
                label="IaC Format"
              >
                <MenuItem value="terraform">Terraform</MenuItem>
                <MenuItem value="arm">ARM Templates</MenuItem>
                <MenuItem value="bicep">Bicep</MenuItem>
              </Select>
            </FormControl>
          </Grid>
        )}

        {outputMode === 'new-tenant' && (
          <Grid item xs={12} md={6}>
            <TextField
              fullWidth
              label="New Tenant ID"
              value={newTenantId}
              onChange={(e) => setNewTenantId(e.target.value)}
              disabled={isRunning}
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              helperText="Tenant ID for the new sample tenant"
            />
          </Grid>
        )}

        {/* Options */}
        <Grid item xs={12}>
          <Divider sx={{ my: 1 }} />
          <Typography variant="subtitle2" gutterBottom sx={{ mt: 2 }}>
            Options
          </Typography>
        </Grid>

        <Grid item xs={12}>
          <FormControlLabel
            control={
              <Checkbox
                checked={validate}
                onChange={(e) => setValidate(e.target.checked)}
                disabled={isRunning}
              />
            }
            label="Run validation before and after operation"
          />
        </Grid>

        <Grid item xs={12}>
          <FormControlLabel
            control={
              <Checkbox
                checked={preserveRelationships}
                onChange={(e) => setPreserveRelationships(e.target.checked)}
                disabled={isRunning}
              />
            }
            label="Preserve relationships between sampled nodes"
          />
        </Grid>

        <Grid item xs={12}>
          <FormControlLabel
            control={
              <Checkbox
                checked={includeProperties}
                onChange={(e) => setIncludeProperties(e.target.checked)}
                disabled={isRunning}
              />
            }
            label="Include node properties in output"
          />
        </Grid>

        {/* Action Buttons */}
        <Grid item xs={12}>
          <Divider sx={{ my: 1 }} />
        </Grid>

        <Grid item xs={12}>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <Button
              variant="outlined"
              startIcon={<PreviewIcon />}
              onClick={handlePreview}
              disabled={isExecuteDisabled || isPreviewing}
            >
              {isPreviewing ? 'Previewing...' : 'Preview Sample'}
            </Button>

            <Button
              variant="contained"
              color="primary"
              startIcon={<ExecuteIcon />}
              onClick={handleExecute}
              disabled={isExecuteDisabled}
              size="large"
            >
              Execute Scale-Down
            </Button>

            <Button
              variant="outlined"
              startIcon={<ClearIcon />}
              onClick={handleClear}
              disabled={isRunning}
            >
              Clear
            </Button>
          </Box>
        </Grid>
      </Grid>
    </Paper>
  );
};

export default ScaleDownPanel;
