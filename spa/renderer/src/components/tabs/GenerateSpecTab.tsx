import React, { useState, useEffect } from 'react';
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
} from '@mui/material';
import { PlayArrow as GenerateIcon, Save as SaveIcon } from '@mui/icons-material';
import axios from 'axios';
import MonacoEditor from '@monaco-editor/react';
import { useApp } from '../../context/AppContext';

interface TenantInfo {
  id: string;
  name: string;
}

const GenerateSpecTab: React.FC = () => {
  const { state, dispatch } = useApp();
  const [tenantId, setTenantId] = useState(state.config.tenantId || '');
  const [outputFormat, setOutputFormat] = useState<'json' | 'yaml'>('json');
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedSpec, setGeneratedSpec] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [tenants, setTenants] = useState<TenantInfo[]>([]);
  const [loadingTenants, setLoadingTenants] = useState(false);

  // Fetch tenants from Neo4j on mount
  useEffect(() => {
    fetchTenants();
  }, []);

  const fetchTenants = async () => {
    setLoadingTenants(true);
    try {
      const response = await axios.get('http://localhost:3001/api/neo4j/tenants');
      setTenants(response.data.tenants || []);
      // If there's only one tenant, auto-select it
      if (response.data.tenants?.length === 1 && !tenantId) {
        setTenantId(response.data.tenants[0].id);
      }
    } catch (err) {
      console.error('Failed to fetch tenants:', err);
      // Don't show error, just allow manual input
    } finally {
      setLoadingTenants(false);
    }
  };

  const handleGenerate = async () => {
    if (!tenantId) {
      setError('Tenant ID is required');
      return;
    }

    setError(null);
    setIsGenerating(true);
    setGeneratedSpec('');

    const args = [
      '--tenant-id', tenantId,
      '--format', outputFormat,
    ];

    try {
      const result = await window.electronAPI.cli.execute('generate-spec', args);
      
      // Listen for output and stream content
      let specContent = '';
      window.electronAPI.on('process:output', (data: any) => {
        if (data.id === result.data.id) {
          const newContent = data.data.join('\n');
          specContent += newContent;
          // Update the editor content in real-time
          setGeneratedSpec(specContent);
        }
      });

      // Listen for completion
      window.electronAPI.on('process:exit', (data: any) => {
        if (data.id === result.data.id) {
          setIsGenerating(false);
          if (data.code === 0) {
            setGeneratedSpec(specContent);
          } else {
            setError(`Generation failed with exit code ${data.code}`);
          }
        }
      });

      dispatch({ type: 'SET_CONFIG', payload: { tenantId } });
      
    } catch (err: any) {
      setError(err.message);
      setIsGenerating(false);
    }
  };

  const handleSave = async () => {
    if (!generatedSpec) {
      setError('No specification to save');
      return;
    }

    try {
      const filePath = await window.electronAPI.dialog.saveFile({
        defaultPath: `tenant-spec.${outputFormat}`,
        filters: [
          { name: outputFormat.toUpperCase(), extensions: [outputFormat] },
          { name: 'All Files', extensions: ['*'] }
        ]
      });

      if (filePath) {
        await window.electronAPI.file.write(filePath, generatedSpec);
        setError(null);
        // Show success message
      }
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Paper sx={{ p: 3, mb: 2 }}>
        <Typography variant="h5" gutterBottom>
          Generate Tenant Specification From Graph
        </Typography>
        
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <FormControl fullWidth required>
              <InputLabel>Tenant ID</InputLabel>
              <Select
                value={tenantId}
                onChange={(e) => setTenantId(e.target.value)}
                disabled={isGenerating || loadingTenants}
                label="Tenant ID"
              >
                {tenants.length === 0 && !loadingTenants && (
                  <MenuItem value="" disabled>
                    <em>No tenants found in graph database</em>
                  </MenuItem>
                )}
                {tenants.map((tenant) => (
                  <MenuItem key={tenant.id} value={tenant.id}>
                    {tenant.name} ({tenant.id})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          
          <Grid item xs={12} md={6}>
            <FormControl fullWidth>
              <InputLabel>Output Format</InputLabel>
              <Select
                value={outputFormat}
                onChange={(e) => setOutputFormat(e.target.value as 'json' | 'yaml')}
                disabled={isGenerating}
                label="Output Format"
              >
                <MenuItem value="json">JSON</MenuItem>
                <MenuItem value="yaml">YAML</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12}>
            <Box sx={{ display: 'flex', gap: 2 }}>
              <Button
                variant="contained"
                color="primary"
                startIcon={<GenerateIcon />}
                onClick={handleGenerate}
                disabled={isGenerating}
                size="large"
              >
                {isGenerating ? 'Generating...' : 'Generate Spec'}
              </Button>
              
              {generatedSpec && (
                <Button
                  variant="outlined"
                  startIcon={<SaveIcon />}
                  onClick={handleSave}
                  size="large"
                >
                  Save to File
                </Button>
              )}
            </Box>
          </Grid>
        </Grid>
      </Paper>

      <Paper sx={{ flex: 1, minHeight: 0, p: 2 }}>
        <Typography variant="subtitle2" gutterBottom>
          Generated Specification
        </Typography>
        <Box sx={{ height: 'calc(100% - 30px)' }}>
          <MonacoEditor
            value={generatedSpec || '// Generated specification will appear here'}
            language={outputFormat}
            theme="vs-dark"
            loading=""
            options={{
              readOnly: true,
              minimap: { enabled: false },
              fontSize: 14,
              wordWrap: 'on',
              placeholder: '// Generated specification will appear here',
            }}
          />
        </Box>
      </Paper>
    </Box>
  );
};

export default GenerateSpecTab;