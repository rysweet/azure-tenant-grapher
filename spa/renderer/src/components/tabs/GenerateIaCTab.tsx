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
  FormControlLabel,
  Checkbox,
  Chip,
} from '@mui/material';
import { Code as GenerateIcon, FilterList as FilterIcon, FolderOpen as FolderIcon } from '@mui/icons-material';
import axios from 'axios';
import { useApp } from '../../context/AppContext';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:3001';

interface TenantInfo {
  id: string;
  name: string;
}

interface TenantsResponse {
  tenants: TenantInfo[];
}

interface ProcessOutputData {
  id: string;
  data: string[];
}

interface ProcessExitData {
  id: string;
  code: number;
}

const GenerateIaCTab: React.FC = () => {
  const { state, dispatch } = useApp();
  const [tenantId, setTenantId] = useState(state.config.tenantId || '');
  const [outputFormat, setOutputFormat] = useState<'terraform' | 'arm' | 'bicep'>('terraform');
  const [resourceFilters, setResourceFilters] = useState<string[]>([]);
  const [filterInput, setFilterInput] = useState('');
  const [dryRun, setDryRun] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [terminalOutput, setTerminalOutput] = useState('');
  const [outputPath, setOutputPath] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tenants, setTenants] = useState<TenantInfo[]>([]);
  const [loadingTenants, setLoadingTenants] = useState(false);
  const [domainName, setDomainName] = useState('');
  const [selectedTenant, setSelectedTenant] = useState<'1' | '2'>('1');
  const [selectedNodeIds, setSelectedNodeIds] = useState<string[]>([]);
  const [selectedNodeDetails, setSelectedNodeDetails] = useState<any[]>([]);

  // Listen for selected nodes from visualization
  useEffect(() => {
    const handleGenerateIaCForNodes = (event: CustomEvent) => {
      const nodeIds = event.detail?.nodeIds || [];
      const nodeDetails = event.detail?.nodeDetails || [];
      setSelectedNodeIds(nodeIds);
      setSelectedNodeDetails(nodeDetails);
      // Switch to this tab (the parent component should handle tab switching)
    };

    window.addEventListener('generateIaCForNodes', handleGenerateIaCForNodes as EventListener);

    return () => {
      window.removeEventListener('generateIaCForNodes', handleGenerateIaCForNodes as EventListener);
    };
  }, []);

  // Fetch tenants from Neo4j on mount
  useEffect(() => {
    fetchTenants();
  }, []);

  const fetchTenants = async () => {
    setLoadingTenants(true);
    try {
      const response = await axios.get<TenantsResponse>(`${API_BASE_URL}/api/neo4j/tenants`);
      setTenants(response.data.tenants || []);
      // If there's only one tenant, auto-select it
      if (response.data.tenants?.length === 1 && !tenantId) {
        setTenantId(response.data.tenants[0].id);
      }
    } catch (err) {
      console.warn('Failed to fetch tenants:', err);
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
    setTerminalOutput('');
    setOutputPath(null);

    const args = [
      '--tenant-id', tenantId,
      '--format', outputFormat,
    ];

    if (domainName) {
      args.push('--domain-name', domainName);
    }

    if (dryRun) args.push('--dry-run');

    // Add selected nodes - use resource names for ResourceGroup nodes
    if (selectedNodeDetails.length > 0) {
      // Separate ResourceGroup nodes from other nodes
      const resourceGroupNames: string[] = [];
      const otherNodeIds: string[] = [];

      selectedNodeDetails.forEach(node => {
        if (node.type === 'ResourceGroup' && node.resourceName) {
          // For ResourceGroup nodes, use the actual resource name
          resourceGroupNames.push(node.resourceName);
        } else {
          // For other nodes, use the node ID
          otherNodeIds.push(node.id);
        }
      });

      // Add resource group filters
      if (resourceGroupNames.length > 0) {
        args.push('--filter-by-rgs', resourceGroupNames.join(','));
      }

      // Add other node IDs
      otherNodeIds.forEach(nodeId => {
        args.push('--node-id', nodeId);
      });
    } else if (selectedNodeIds.length > 0) {
      // Fallback to just node IDs if details aren't available
      selectedNodeIds.forEach(nodeId => {
        args.push('--node-id', nodeId);
      });
    }

    resourceFilters.forEach(filter => {
      args.push('--filter', filter);
    });

    try {
      const result = await window.electronAPI.cli.execute('generate-iac', args);

      let outputContent = '';
      let foundOutputPath = false;

      const outputHandler = (data: ProcessOutputData) => {
        if (data.id === result.data.id) {
          const newContent = data.data.join('\n');
          outputContent += newContent + '\n';
          setTerminalOutput(outputContent);

          // Look for output path in the terminal output
          if (!foundOutputPath) {
            const pathMatch = newContent.match(/Generated .* files? in: (.+)/);
            if (pathMatch) {
              setOutputPath(pathMatch[1]);
              foundOutputPath = true;
            }
            // Also check for other patterns
            const altMatch = newContent.match(/Output written to: (.+)/);
            if (altMatch) {
              setOutputPath(altMatch[1]);
              foundOutputPath = true;
            }
          }
        }
      };

      window.electronAPI.on('process:output', outputHandler);

      const exitHandler = (data: ProcessExitData) => {
        if (data.id === result.data.id) {
          setIsGenerating(false);
          if (data.code === 0) {
            // If we didn't find a specific path, use default
            if (!foundOutputPath && !dryRun) {
              setOutputPath(`outputs/iac/${tenantId}/${outputFormat}`);
            }
          } else {
            setError(`Generation failed with exit code ${data.code}`);
          }

          // Clean up event listeners
          window.electronAPI.off('process:output', outputHandler);
          window.electronAPI.off('process:exit', exitHandler);
        }
      };

      window.electronAPI.on('process:exit', exitHandler);

      dispatch({ type: 'SET_CONFIG', payload: { tenantId } });

    } catch (err: any) {
      setError(err.message);
      setIsGenerating(false);
    }
  };

  const handleOpenFolder = async () => {
    if (!outputPath) return;

    try {
      await window.electronAPI.shell.openPath(outputPath);
    } catch (err: any) {
      setError(`Failed to open folder: ${err.message}`);
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

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Paper sx={{ p: 3, mb: 2 }}>
        <Typography variant="h5" gutterBottom>
          Generate Infrastructure as Code from Graph
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {selectedNodeDetails.length > 0 && (
          <Alert 
            severity="info" 
            sx={{ mb: 2 }} 
            onClose={() => {
              setSelectedNodeIds([]);
              setSelectedNodeDetails([]);
            }}
          >
            <Typography variant="body2">
              Generating IaC for {selectedNodeDetails.length} selected nodes and their connections
            </Typography>
            <Box sx={{ mt: 1, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {selectedNodeDetails.slice(0, 5).map(node => (
                <Chip 
                  key={node.id} 
                  label={
                    node.type === 'ResourceGroup' && node.resourceName 
                      ? `📁 ${node.resourceName}` 
                      : node.label || node.id
                  } 
                  size="small"
                  color={node.type === 'ResourceGroup' ? 'primary' : 'default'}
                />
              ))}
              {selectedNodeDetails.length > 5 && (
                <Chip label={`+${selectedNodeDetails.length - 5} more`} size="small" />
              )}
            </Box>
            {selectedNodeDetails.some(n => n.type === 'ResourceGroup') && (
              <Typography variant="caption" sx={{ mt: 1, display: 'block', color: 'text.secondary' }}>
                ℹ️ Resource groups will be filtered by name, not internal IDs
              </Typography>
            )}
          </Alert>
        )}

        <Grid container spacing={3}>
          <Grid item xs={12} md={4}>
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
            <FormControl fullWidth>
              <InputLabel>Target Tenant</InputLabel>
              <Select
                value={selectedTenant}
                onChange={(e) => setSelectedTenant(e.target.value as '1' | '2')}
                disabled={isGenerating}
                label="Target Tenant"
              >
                <MenuItem value="1">Tenant 1 (Primary)</MenuItem>
                <MenuItem value="2">Tenant 2 (Simuland)</MenuItem>
              </Select>
            </FormControl>
          </Grid>

          <Grid item xs={12} md={6}>
            <TextField
              label="Domain Name (for Azure AD users)"
              value={domainName}
              onChange={(e) => setDomainName(e.target.value)}
              disabled={isGenerating}
              fullWidth
              placeholder="e.g., contoso.onmicrosoft.com"
              helperText="Required for Azure AD user creation"
            />
          </Grid>

          <Grid item xs={12} md={6}>
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

              {outputPath && (
                <Button
                  variant="outlined"
                  startIcon={<FolderIcon />}
                  onClick={handleOpenFolder}
                  size="large"
                >
                  Open Output Folder
                </Button>
              )}
            </Box>
          </Grid>
        </Grid>
      </Paper>

      <Paper sx={{ flex: 1, minHeight: 0, p: 2 }}>
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
          {outputPath && (
            <Alert
              severity="success"
              sx={{ mb: 2 }}
              action={
                <Button
                  color="inherit"
                  size="small"
                  onClick={handleOpenFolder}
                  startIcon={<FolderIcon />}
                >
                  Open Folder
                </Button>
              }
            >
              Files generated in: {outputPath}
            </Alert>
          )}
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
            {terminalOutput || (isGenerating ? 'Generating infrastructure code...\n' : 'Terminal output will appear here when you generate IaC')}
          </Box>
        </Box>
      </Paper>
    </Box>
  );
};

export default GenerateIaCTab;
