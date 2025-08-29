import React, { useState } from 'react';
import {
  Box,
  Paper,
  TextField,
  Button,
  Typography,
  Alert,
} from '@mui/material';
import { Upload as UploadIcon, Create as CreateIcon } from '@mui/icons-material';
import MonacoEditor from '@monaco-editor/react';
import LogViewer from '../common/LogViewer';

const CreateTenantTab: React.FC = () => {
  const [specContent, setSpecContent] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const handleFileUpload = async () => {
    try {
      const filePath = await window.electronAPI.dialog.openFile({
        filters: [
          { name: 'Spec Files', extensions: ['json', 'yaml', 'yml'] },
          { name: 'All Files', extensions: ['*'] }
        ]
      });

      if (filePath) {
        const result = await window.electronAPI.file.read(filePath);
        if (result.success) {
          setSpecContent(result.data);
        } else {
          setError(result.error);
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
      await window.electronAPI.file.write(tempPath, specContent);

      const result = await window.electronAPI.cli.execute('create-tenant', ['--spec', tempPath]);
      
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
          Create Tenant from Specification
        </Typography>
        
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
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
                placeholder: '// Paste or upload your tenant specification here',
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
    </Box>
  );
};

export default CreateTenantTab;