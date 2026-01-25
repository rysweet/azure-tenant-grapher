import React, { useState } from 'react';
import {
  Box,
  Paper,
  Button,
  Typography,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  OutlinedInput,
  InputAdornment,
  Select,
  MenuItem,
  Grid,
} from '@mui/material';
import { Upload as UploadIcon, Create as CreateIcon, AutoAwesome as GenerateIcon } from '@mui/icons-material';
import MonacoEditor from '@monaco-editor/react';
import LogViewer from '../common/LogViewer';

const CreateTenantTab: React.FC = () => {
  const [specContent, setSpecContent] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [genSimDialogOpen, setGenSimDialogOpen] = useState(false);
  const [companySize, setCompanySize] = useState<number>(100);
  const [seedFile, setSeedFile] = useState<string>('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [selectedTenant, setSelectedTenant] = useState<'1' | '2'>('1');

  const handleFileUpload = async () => {
    try {
      const filePath = await window.electronAPI?.dialog?.openFile?.({
        filters: [
          { name: 'Spec Files', extensions: ['json', 'yaml', 'yml'] },
          { name: 'All Files', extensions: ['*'] }
        ]
      });

      if (filePath) {
        const result = await window.electronAPI?.file?.read?.(filePath);
        if (result && typeof result === 'object' && 'success' in result) {
          const typedResult = result as { success: boolean; data?: string; error?: string };
          if (typedResult.success && typedResult.data) {
            setSpecContent(typedResult.data);
          } else {
            setError(typedResult.error || 'Failed to read file');
          }
        } else if (typeof result === 'string') {
          setSpecContent(result);
        } else {
          setError('Invalid file read response');
        }
      }
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleCreate = async () => {
    if (!specContent) {
      setError('Specification content is required');
      return;
    }

    setError(null);
    setIsCreating(true);
    setLogs([]);

    try {
      // Save spec to temp file
      const tempPath = `/tmp/tenant-spec-${Date.now()}.json`;
      await window.electronAPI.file?.write(tempPath, specContent);

      const result = await window.electronAPI.cli.execute('create-tenant', [tempPath]);

      window.electronAPI.on('process:output', (data: any) => {
        if (data.id === result.data.id) {
          setLogs((prev) => [...prev, ...data.data]);
        }
      });

      window.electronAPI.on('process:exit', (data: any) => {
        if (data.id === result.data.id) {
          setIsCreating(false);
          if (data.code === 0) {
            setLogs((prev) => [...prev, 'Tenant created successfully!']);
          } else {
            setError(`Creation failed with exit code ${data.code}`);
          }
        }
      });

    } catch (err: any) {
      setError(err.message);
      setIsCreating(false);
    }
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Paper sx={{ p: 3, mb: 2 }}>
        <Typography variant="h5" gutterBottom>
          Create a new Tenant in the Graph
        </Typography>

        <Typography variant="body1" color="text.secondary" paragraph sx={{ mb: 3 }}>
          Creates simulated tenants for testing and visualization without connecting to real Azure resources.
          Generated tenants can be exported as IaC for deployment to Azure.
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <Grid container spacing={2} sx={{ mb: 2 }}>
          <Grid item xs={12} md={4}>
            <FormControl fullWidth>
              <InputLabel>Gameboard Tenant</InputLabel>
              <Select
                value={selectedTenant}
                onChange={(e) => setSelectedTenant(e.target.value as '1' | '2')}
                disabled={isCreating}
                label="Gameboard Tenant"
              >
                <MenuItem value="1">Tenant 1 (Primary)</MenuItem>
                <MenuItem value="2">Tenant 2 (Simuland)</MenuItem>
              </Select>
            </FormControl>
          </Grid>
        </Grid>

        <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
          <Button
            variant="outlined"
            startIcon={<GenerateIcon />}
            onClick={() => setGenSimDialogOpen(true)}
            disabled={isCreating}
          >
            Generate new Tenant Specification using LLM
          </Button>
          <Button
            variant="outlined"
            startIcon={<UploadIcon />}
            onClick={handleFileUpload}
            disabled={isCreating}
          >
            Upload Spec File
          </Button>

          <Button
            variant="contained"
            color="primary"
            startIcon={<CreateIcon />}
            onClick={handleCreate}
            disabled={isCreating || !specContent}
          >
            {isCreating ? 'Creating...' : 'Create Tenant'}
          </Button>
        </Box>
      </Paper>

      <Box sx={{ flex: 1, display: 'flex', gap: 2, minHeight: 0 }}>
        <Paper sx={{ flex: 1, p: 2 }}>
          <Typography variant="subtitle2" gutterBottom>
            Specification Content
          </Typography>
          <Box sx={{ height: 'calc(100% - 30px)' }}>
            <MonacoEditor
              value={specContent || '// Paste or upload your tenant specification here'}
              language="json"
              theme="vs-dark"
              loading=""
              onChange={(value) => setSpecContent(value || '')}
              options={{
                minimap: { enabled: false },
                fontSize: 14,
                wordWrap: 'on',
              }}
            />
          </Box>
        </Paper>

        <Box sx={{ flex: 1 }}>
          <LogViewer
            logs={logs}
            onClear={() => setLogs([])}
            height="100%"
          />
        </Box>
      </Box>

      {/* Generate Tenant Specification Dialog */}
      <Dialog
        open={genSimDialogOpen}
        onClose={() => setGenSimDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Generate Tenant Specification using LLM</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2, display: 'flex', flexDirection: 'column', gap: 3 }}>
            <FormControl fullWidth variant="outlined">
              <InputLabel htmlFor="company-size">Company Size</InputLabel>
              <OutlinedInput
                id="company-size"
                type="number"
                value={companySize}
                onChange={(e) => setCompanySize(Number(e.target.value))}
                endAdornment={<InputAdornment position="end">employees</InputAdornment>}
                label="Company Size"
              />
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
                Target company size (approximate number of employees)
              </Typography>
            </FormControl>

            <Box>
              <Button
                variant="outlined"
                onClick={async () => {
                  try {
                    const filePath = await window.electronAPI?.dialog?.openFile?.({
                      filters: [
                        { name: 'Markdown Files', extensions: ['md'] },
                        { name: 'All Files', extensions: ['*'] }
                      ]
                    });
                    if (filePath) {
                      setSeedFile(filePath);
                    }
                  } catch (err: any) {
                    setError(err.message);
                  }
                }}
                fullWidth
              >
                {seedFile ? `Seed File: ${seedFile.split('/').pop()}` : 'Select Seed File (Optional)'}
              </Button>
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
                Path to a markdown file with seed/suggestions for the profile
              </Typography>
            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setGenSimDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={async () => {
              setGenSimDialogOpen(false);
              setIsGenerating(true);
              setError(null);
              setLogs([]);

              try {
                const args = ['--size', companySize.toString()];
                if (seedFile) {
                  args.push('--seed', seedFile);
                }

                const result = await window.electronAPI.cli.execute('gensimdoc', args);

                let outputContent = '';

                const outputHandler = (data: any) => {
                  if (data.id === result.data.id) {
                    const output = data.data.join('\n');
                    outputContent += output + '\n';
                    setLogs((prev) => [...prev, output]);

                    // Check if output contains the generated file path
                    const pathMatch = output.match(/Generated simulation document: (.+\.md)/);
                    if (pathMatch) {
                      // Read the generated file and set it as spec content
                      window.electronAPI.file?.read(pathMatch[1]).then((readResult: any) => {
                        if (readResult.success) {
                          setSpecContent(readResult.data);
                        }
                      });
                    }
                  }
                };

                window.electronAPI.on('process:output', outputHandler);

                // Define error handler first (needed by exitHandler cleanup)
                const errorHandler = (data: any) => {
                  if (data.processId === result.data.id || data.id === result.data.id) {
                    setIsGenerating(false);
                    setError(data.error || 'Process execution failed');

                    // Clean up event listeners
                    window.electronAPI.off?.('process:output', outputHandler);
                    window.electronAPI.off?.('process:exit', exitHandler);
                    window.electronAPI.off?.('process:error', errorHandler);
                  }
                };

                const exitHandler = (data: any) => {
                  if (data.id === result.data.id) {
                    setIsGenerating(false);
                    if (data.code === 0) {
                      setLogs((prev) => [...prev, 'Tenant specification generated successfully!']);
                    } else {
                      // Extract error message from terminal output if available
                      let errorMessage = `Generation failed with exit code ${data.code}`;

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
                setIsGenerating(false);
              }
            }}
            variant="contained"
            disabled={isGenerating}
          >
            {isGenerating ? 'Generating...' : 'Generate'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default CreateTenantTab;
