import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  TextField,
  Button,
  Typography,
  Alert,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  LinearProgress,
  Tooltip,
  Chip,
} from '@mui/material';
import { Editor } from '@monaco-editor/react';
import { PlayArrow as RunIcon, Save as SaveIcon, Info as InfoIcon } from '@mui/icons-material';
import { useApp } from '../../context/AppContext';
import { useProcessExecution } from '../../hooks/useProcessExecution';

// Feature flag for format selector - set to true when CLI supports JSON output
// TODO: Re-enable format selector when CLI supports JSON output (track in issue #XXX)
const ENABLE_FORMAT_SELECTOR = false;

const GenerateSpecTab: React.FC = () => {
  const { state, dispatch } = useApp();
  const [tenantId, setTenantId] = useState(state.config?.tenantId || '');
  const [limit, setLimit] = useState('');
  const [outputFormat, setOutputFormat] = useState('markdown');
  const [generatedSpec, setGeneratedSpec] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isElectronReady, setIsElectronReady] = useState(false);

  // Check if Electron API is available
  useEffect(() => {
    const checkElectronAPI = () => {
      if (window.electronAPI?.cli?.execute) {
        setIsElectronReady(true);
        return true;
      }
      return false;
    };

    // Try immediately
    if (checkElectronAPI()) {
      return;
    }

    // If not ready, retry with timeout
    const timeout = setTimeout(() => {
      if (!checkElectronAPI()) {
        setError('Electron API not available. Please restart the application.');
      }
    }, 5000);

    return () => clearTimeout(timeout);
  }, []);

  // Use the process execution hook
  const { execute, isRunning, output, exitCode } = useProcessExecution({
    onOutput: ({ type, lines }) => {
      if (type === 'stdout') {
        // Append output to the spec as it streams
        setGeneratedSpec(prev => prev + lines.join('\n'));
      }
    },
    onExit: (code) => {
      if (code !== 0) {
        setError(`Generation failed with exit code ${code}`);
      }
    },
    onError: (err) => {
      setError(err);
    }
  });

  // Update tenant ID from context
  useEffect(() => {
    if (state.config?.tenantId) {
      setTenantId(state.config.tenantId);
    }
  }, [state.config?.tenantId]);

  const handleGenerate = async () => {
    // Validate Electron API availability
    if (!window.electronAPI?.cli?.execute) {
      setError('Electron API not available. Please restart the application.');
      return;
    }

    setError(null);
    setGeneratedSpec(''); // Clear previous spec

    const args = [];

    if (limit) {
      args.push('--limit', limit);
    }

    // Note: --format option removed as generate-spec CLI command doesn't support it
    // The outputFormat state is still used for the editor language and save file extension

    // Set a timeout for the generation process (5 minutes)
    const timeoutId = setTimeout(() => {
      setError('Generation timed out after 5 minutes. Please try with a smaller limit.');
    }, 300000); // 5 minutes

    try {
      await execute('generate-spec', args);
      dispatch({ type: 'SET_CONFIG', payload: { tenantId } });
    } catch (err: any) {
      // Error is already handled by the hook, but ensure loading state is cleared
      if (err.message) {
        setError(err.message);
      }
    } finally {
      clearTimeout(timeoutId);
    }
  };

  const handleSave = async () => {
    if (!generatedSpec) return;

    try {
      const extension = outputFormat === 'json' ? 'json' : 'md';
      const defaultFileName = `tenant-spec-${Date.now()}.${extension}`;

      const filePath = await window.electronAPI?.dialog?.saveFile?.({
        defaultPath: defaultFileName,
        filters: [
          { name: outputFormat === 'json' ? 'JSON' : 'Markdown', extensions: [extension] },
          { name: 'All Files', extensions: ['*'] },
        ],
      });

      if (filePath) {
        await window.electronAPI?.file?.write?.(filePath, generatedSpec);
        // You could show a success message here
      }
    } catch (err: any) {
      setError(`Failed to save file: ${err.message}`);
    }
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Paper sx={{ p: 3, mb: 2 }}>
        <Typography variant="h5" gutterBottom>
          Generate Anonymized Tenant Specification
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2 }}>
          <TextField
            label="Resource Limit"
            value={limit}
            onChange={(e) => setLimit(e.target.value)}
            placeholder="Optional"
            size="small"
            sx={{ width: 200 }}
            type="number"
          />

          {/* Format selector - conditionally shown based on feature flag */}
          {ENABLE_FORMAT_SELECTOR ? (
            <FormControl size="small" sx={{ minWidth: 150 }}>
              <InputLabel>Output Format</InputLabel>
              <Select
                value={outputFormat}
                onChange={(e) => setOutputFormat(e.target.value)}
                label="Output Format"
              >
                <MenuItem value="markdown">Markdown</MenuItem>
                <MenuItem value="json">JSON</MenuItem>
              </Select>
            </FormControl>
          ) : (
            <Tooltip title="Currently only Markdown format is supported. JSON format will be available in a future update.">
              <Chip
                label="Markdown Only"
                size="small"
                icon={<InfoIcon />}
                color="info"
                variant="outlined"
              />
            </Tooltip>
          )}

          <Button
            variant="contained"
            startIcon={<RunIcon />}
            onClick={handleGenerate}
            disabled={isRunning || !isElectronReady}
          >
            {!isElectronReady ? 'Loading...' : isRunning ? 'Generating...' : 'Generate Spec'}
          </Button>

          {generatedSpec && (
            <Button
              variant="outlined"
              startIcon={<SaveIcon />}
              onClick={handleSave}
              disabled={isRunning}
            >
              Save
            </Button>
          )}
        </Box>

        {isRunning && <LinearProgress />}
      </Paper>

      <Paper sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
          <Typography variant="h6">
            Generated Specification
            {exitCode === 0 && ' (Completed)'}
            {isRunning && ' (Generating...)'}
          </Typography>
        </Box>

        <Box sx={{ flex: 1 }}>
          <Editor
            value={generatedSpec || '// Specification will appear here after generation'}
            language={outputFormat === 'json' ? 'json' : 'markdown'}
            theme="vs-dark"
            options={{
              readOnly: true,
              minimap: { enabled: false },
              wordWrap: 'on',
              automaticLayout: true,
            }}
          />
        </Box>

        {output.stderr.length > 0 && (
          <Box sx={{ p: 2, borderTop: 1, borderColor: 'divider', bgcolor: 'error.dark', color: 'error.contrastText' }}>
            <Typography variant="caption" component="pre" sx={{ fontFamily: 'monospace' }}>
              {output.stderr.join('\n')}
            </Typography>
          </Box>
        )}
      </Paper>
    </Box>
  );
};

export default GenerateSpecTab;
