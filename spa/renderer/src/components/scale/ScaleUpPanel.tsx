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
import { useScaleUpOperation } from '../../hooks/useScaleUpOperation';
import { useApp } from '../../context/AppContext';
import { ScaleUpConfig, ScaleUpStrategy } from '../../types/scaleOperations';

const ScaleUpPanel: React.FC = () => {
  const { state: appState } = useApp();
  const { state, dispatch } = useScaleOperations();
  const { executeScaleUp, previewScaleUp, isRunning } = useScaleUpOperation();

  const [tenantId, setTenantId] = useState(appState.config.tenantId || '');
  const [strategy, setStrategy] = useState<ScaleUpStrategy>('template');
  const [templateFile, setTemplateFile] = useState('templates/scale_up_template.yaml');
  const [scaleFactor, setScaleFactor] = useState(2);
  const [nodeCount, setNodeCount] = useState(1000);
  const [pattern, setPattern] = useState('standard');
  const [scenarioType, setScenarioType] = useState('enterprise');
  const [validate, setValidate] = useState(true);
  const [isPreviewing, setIsPreviewing] = useState(false);

  // Update tenant ID when app config changes
  useEffect(() => {
    if (appState.config.tenantId && !tenantId) {
      setTenantId(appState.config.tenantId);
    }
  }, [appState.config.tenantId, tenantId]);

  const getStrategyDescription = (strat: ScaleUpStrategy): string => {
    switch (strat) {
      case 'template':
        return 'Generate nodes based on a predefined template file';
      case 'scenario':
        return 'Generate nodes based on common deployment scenarios';
      case 'random':
        return 'Generate random nodes with configurable patterns';
      default:
        return '';
    }
  };

  const buildConfig = useCallback((): ScaleUpConfig => {
    const config: ScaleUpConfig = {
      tenantId,
      strategy,
      validate,
    };

    if (strategy === 'template') {
      config.templateFile = templateFile;
      config.scaleFactor = scaleFactor;
    } else if (strategy === 'scenario') {
      config.scenarioType = scenarioType;
    } else if (strategy === 'random') {
      config.nodeCount = nodeCount;
      config.pattern = pattern;
    }

    return config;
  }, [tenantId, strategy, validate, templateFile, scaleFactor, scenarioType, nodeCount, pattern]);

  const handleExecute = async () => {
    const config = buildConfig();
    await executeScaleUp(config);
  };

  const handlePreview = async () => {
    setIsPreviewing(true);
    const config = buildConfig();
    await previewScaleUp(config);
    setIsPreviewing(false);
  };

  const handleBrowse = async () => {
    // TODO: Implement file browser dialog via electron API
    console.log('Browse for template file');
  };

  const handleClear = () => {
    setTenantId(appState.config.tenantId || '');
    setStrategy('template');
    setTemplateFile('templates/scale_up_template.yaml');
    setScaleFactor(2);
    setValidate(true);
    dispatch({ type: 'CLEAR_OPERATION' });
  };

  const isExecuteDisabled = !tenantId || isRunning || (strategy === 'template' && !templateFile);

  return (
    <Paper sx={{ p: 3 }}>
      <Typography variant="h6" gutterBottom>
        Scale-Up Configuration
      </Typography>

      {state.error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => dispatch({ type: 'SET_ERROR', payload: null })}>
          {state.error}
        </Alert>
      )}

      {state.previewResult && (
        <Alert severity="info" sx={{ mb: 2 }} icon={<InfoIcon />}>
          <Typography variant="subtitle2" gutterBottom>
            Preview: Scale-Up Operation
          </Typography>
          <Typography variant="body2">
            Will create approximately <strong>{state.previewResult.estimatedNodes}</strong> nodes
            and <strong>{state.previewResult.estimatedRelationships}</strong> relationships
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Estimated duration: {state.previewResult.estimatedDuration} seconds
          </Typography>
          {state.previewResult.warnings.length > 0 && (
            <Box sx={{ mt: 1 }}>
              <Typography variant="body2" color="warning.main">
                Warnings:
              </Typography>
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                {state.previewResult.warnings.map((warning, idx) => (
                  <li key={idx}>
                    <Typography variant="body2">{warning}</Typography>
                  </li>
                ))}
              </ul>
            </Box>
          )}
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
            helperText="Azure tenant ID to scale"
          />
        </Grid>

        <Grid item xs={12} md={6}>
          <FormControl fullWidth>
            <InputLabel>Strategy</InputLabel>
            <Select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value as ScaleUpStrategy)}
              disabled={isRunning}
              label="Strategy"
            >
              <MenuItem value="template">Template-Based</MenuItem>
              <MenuItem value="scenario">Scenario-Based</MenuItem>
              <MenuItem value="random">Random Generation</MenuItem>
            </Select>
          </FormControl>
        </Grid>

        <Grid item xs={12}>
          <Alert severity="info" icon={<InfoIcon />}>
            {getStrategyDescription(strategy)}
          </Alert>
        </Grid>

        {/* Strategy-Specific Parameters */}
        {strategy === 'template' && (
          <>
            <Grid item xs={12}>
              <Typography variant="subtitle2" gutterBottom>
                Template Configuration
              </Typography>
            </Grid>

            <Grid item xs={12}>
              <Box sx={{ display: 'flex', gap: 1 }}>
                <TextField
                  fullWidth
                  label="Template File"
                  value={templateFile}
                  onChange={(e) => setTemplateFile(e.target.value)}
                  disabled={isRunning}
                  placeholder="templates/scale_up_template.yaml"
                  required
                />
                <Button
                  variant="outlined"
                  startIcon={<BrowseIcon />}
                  onClick={handleBrowse}
                  disabled={isRunning}
                  sx={{ minWidth: 120 }}
                >
                  Browse
                </Button>
              </Box>
            </Grid>

            <Grid item xs={12}>
              <Typography variant="body2" gutterBottom>
                Scale Factor: {scaleFactor}x
              </Typography>
              <Slider
                value={scaleFactor}
                onChange={(_e, value) => setScaleFactor(value as number)}
                disabled={isRunning}
                min={1}
                max={10}
                step={1}
                marks
                valueLabelDisplay="auto"
                aria-label="scale factor"
              />
              <Typography variant="caption" color="text.secondary">
                Multiplier for template resources (1x = original, 10x = 10 times larger)
              </Typography>
            </Grid>
          </>
        )}

        {strategy === 'scenario' && (
          <>
            <Grid item xs={12}>
              <Typography variant="subtitle2" gutterBottom>
                Scenario Configuration
              </Typography>
            </Grid>

            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Scenario Type</InputLabel>
                <Select
                  value={scenarioType}
                  onChange={(e) => setScenarioType(e.target.value)}
                  disabled={isRunning}
                  label="Scenario Type"
                >
                  <MenuItem value="enterprise">Enterprise (large-scale)</MenuItem>
                  <MenuItem value="startup">Startup (small-scale)</MenuItem>
                  <MenuItem value="hybrid">Hybrid Cloud</MenuItem>
                  <MenuItem value="microservices">Microservices</MenuItem>
                </Select>
              </FormControl>
            </Grid>
          </>
        )}

        {strategy === 'random' && (
          <>
            <Grid item xs={12}>
              <Typography variant="subtitle2" gutterBottom>
                Random Generation Configuration
              </Typography>
            </Grid>

            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                type="number"
                label="Node Count"
                value={nodeCount}
                onChange={(e) => setNodeCount(Number(e.target.value))}
                disabled={isRunning}
                inputProps={{ min: 10, max: 10000, step: 10 }}
                helperText="Number of nodes to generate"
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <FormControl fullWidth>
                <InputLabel>Pattern</InputLabel>
                <Select
                  value={pattern}
                  onChange={(e) => setPattern(e.target.value)}
                  disabled={isRunning}
                  label="Pattern"
                >
                  <MenuItem value="standard">Standard</MenuItem>
                  <MenuItem value="hub-spoke">Hub and Spoke</MenuItem>
                  <MenuItem value="mesh">Mesh</MenuItem>
                  <MenuItem value="hierarchical">Hierarchical</MenuItem>
                </Select>
              </FormControl>
            </Grid>
          </>
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
              {isPreviewing ? 'Previewing...' : 'Preview Changes'}
            </Button>

            <Button
              variant="contained"
              color="primary"
              startIcon={<ExecuteIcon />}
              onClick={handleExecute}
              disabled={isExecuteDisabled}
              size="large"
            >
              Execute Scale-Up
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

export default ScaleUpPanel;
