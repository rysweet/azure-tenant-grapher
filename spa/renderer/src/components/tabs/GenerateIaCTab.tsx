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
  Chip,
} from '@mui/material';
import { Code as GenerateIcon, Save as SaveIcon, FilterList as FilterIcon } from '@mui/icons-material';
import MonacoEditor from '@monaco-editor/react';
import { useApp } from '../../context/AppContext';

const GenerateIaCTab: React.FC = () => {
  const { state, dispatch } = useApp();
  const [tenantId, setTenantId] = useState(state.config.tenantId || '');
  const [outputFormat, setOutputFormat] = useState<'terraform' | 'arm' | 'bicep'>('terraform');
  const [resourceFilters, setResourceFilters] = useState<string[]>([]);
  const [filterInput, setFilterInput] = useState('');
  const [dryRun, setDryRun] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generatedCode, setGeneratedCode] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    if (!tenantId) {
      setError('Tenant ID is required');
      return;
    }

    setError(null);
    setIsGenerating(true);
    setGeneratedCode('');

    const args = [
      '--tenant-id', tenantId,
      '--format', outputFormat,
    ];

    if (dryRun) args.push('--dry-run');
    
    resourceFilters.forEach(filter => {
      args.push('--filter', filter);
    });

    try {
      const result = await window.electronAPI.cli.execute('generate-iac', args);
      
      let codeContent = '';
      window.electronAPI.on('process:output', (data: any) => {
        if (data.id === result.data.id) {
          codeContent += data.data.join('\n');
        }
      });

      window.electronAPI.on('process:exit', (data: any) => {
        if (data.id === result.data.id) {
          setIsGenerating(false);
          if (data.code === 0) {
            setGeneratedCode(codeContent);
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
    if (!generatedCode) {
      setError('No code to save');
      return;
    }

    const extensions: Record<string, string> = {
      terraform: 'tf',
      arm: 'json',
      bicep: 'bicep',
    };

    try {
      const filePath = await window.electronAPI.dialog.saveFile({
        defaultPath: `infrastructure.${extensions[outputFormat]}`,
        filters: [
          { name: outputFormat.toUpperCase(), extensions: [extensions[outputFormat]] },
          { name: 'All Files', extensions: ['*'] }
        ]
      });

      if (filePath) {
        await window.electronAPI.file.write(filePath, generatedCode);
        setError(null);
      }
    } catch (err: any) {
      setError(err.message);
    }
  };

  const addFilter = () => {
    if (filterInput.trim() && !resourceFilters.includes(filterInput.trim())) {
      setResourceFilters([...resourceFilters, filterInput.trim()]);
      setFilterInput('');
    }
  };

  const removeFilter = (filter: string) => {
    setResourceFilters(resourceFilters.filter(f => f !== filter));
  };

  const getLanguage = () => {
    switch (outputFormat) {
      case 'terraform': return 'hcl';
      case 'arm': return 'json';
      case 'bicep': return 'bicep';
      default: return 'plaintext';
    }
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Paper sx={{ p: 3, mb: 2 }}>
        <Typography variant="h5" gutterBottom>
          Generate Infrastructure as Code
        </Typography>
        
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <Grid container spacing={3}>
          <Grid item xs={12} md={4}>
            <TextField
              fullWidth
              label="Tenant ID"
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
              disabled={isGenerating}
              helperText="Azure AD Tenant ID"
              required
            />
          </Grid>
          
          <Grid item xs={12} md={4}>
            <FormControl fullWidth>
              <InputLabel>Output Format</InputLabel>
              <Select
                value={outputFormat}
                onChange={(e) => setOutputFormat(e.target.value as any)}
                disabled={isGenerating}
                label="Output Format"
              >
                <MenuItem value="terraform">Terraform</MenuItem>
                <MenuItem value="arm">ARM Template</MenuItem>
                <MenuItem value="bicep">Bicep</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} md={4}>
            <FormControlLabel
              control={
                <Checkbox
                  checked={dryRun}
                  onChange={(e) => setDryRun(e.target.checked)}
                  disabled={isGenerating}
                />
              }
              label="Dry Run"
            />
          </Grid>

          <Grid item xs={12}>
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
              <TextField
                label="Resource Filters"
                value={filterInput}
                onChange={(e) => setFilterInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && addFilter()}
                disabled={isGenerating}
                placeholder="e.g., Microsoft.Compute/virtualMachines"
                sx={{ flex: 1 }}
              />
              <Button
                startIcon={<FilterIcon />}
                onClick={addFilter}
                disabled={isGenerating}
              >
                Add Filter
              </Button>
            </Box>
            
            {resourceFilters.length > 0 && (
              <Box sx={{ mt: 1, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                {resourceFilters.map(filter => (
                  <Chip
                    key={filter}
                    label={filter}
                    onDelete={() => removeFilter(filter)}
                    disabled={isGenerating}
                  />
                ))}
              </Box>
            )}
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
                {isGenerating ? 'Generating...' : 'Generate IaC'}
              </Button>
              
              {generatedCode && (
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
          Generated Infrastructure Code
        </Typography>
        <Box sx={{ height: 'calc(100% - 30px)' }}>
          <MonacoEditor
            value={generatedCode || `// Generated ${outputFormat.toUpperCase()} code will appear here`}
            language={getLanguage()}
            theme="vs-dark"
            options={{
              readOnly: true,
              minimap: { enabled: false },
              fontSize: 14,
              wordWrap: 'on',
            }}
          />
        </Box>
      </Paper>
    </Box>
  );
};

export default GenerateIaCTab;