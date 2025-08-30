import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  TextField,
  Button,
  Typography,
  Alert,
  Grid,
  FormControlLabel,
  Switch,
  IconButton,
} from '@mui/material';
import {
  Save as SaveIcon,
  Visibility as ShowIcon,
  VisibilityOff as HideIcon,
  AppRegistration as AppRegIcon,
} from '@mui/icons-material';

interface ConfigItem {
  key: string;
  value: string;
  isSecret?: boolean;
}


const ConfigTab: React.FC = () => {
  const [config, setConfig] = useState<ConfigItem[]>([
    { key: 'AZURE_TENANT_ID', value: '', isSecret: false },
    { key: 'AZURE_CLIENT_ID', value: '', isSecret: false },
    { key: 'AZURE_CLIENT_SECRET', value: '', isSecret: true },
    { key: 'NEO4J_URI', value: 'bolt://localhost:7687', isSecret: false },
    { key: 'NEO4J_PASSWORD', value: '', isSecret: true },
    { key: 'OPENAI_API_KEY', value: '', isSecret: true },
  ]);
  const [showSecrets, setShowSecrets] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      const envVars = await window.electronAPI.env.getAll();
      setConfig((prev) =>
        prev.map((item) => ({
          ...item,
          value: envVars[item.key] || item.value,
        }))
      );
    } catch (err) {
      console.error('Failed to load config:', err);
    }
  };


  const handleConfigChange = (index: number, value: string) => {
    setConfig((prev) => {
      const updated = [...prev];
      updated[index].value = value;
      return updated;
    });
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      // Save each config item
      for (const item of config) {
        if (item.value) {
          await window.electronAPI.config.set(item.key, item.value);
        }
      }
      
      setMessage({ type: 'success', text: 'Configuration saved successfully' });
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message });
    } finally {
      setIsSaving(false);
    }
  };

  const testConnection = async (service: string) => {
    try {
      const result = await window.electronAPI.cli.execute('test-connection', ['--service', service]);
      setMessage({ type: 'success', text: `${service} connection successful` });
    } catch (err: any) {
      setMessage({ type: 'error', text: `${service} connection failed: ${err.message}` });
    }
  };

  return (
    <Box sx={{ height: '100%', overflow: 'auto' }}>
      <Typography variant="h5" sx={{ p: 3, pb: 0 }}>
        Configuration & Environment
      </Typography>

      {message && (
        <Alert
          severity={message.type}
          sx={{ mx: 3, mt: 2 }}
          onClose={() => setMessage(null)}
        >
          {message.text}
        </Alert>
      )}

      <Grid container spacing={3} sx={{ p: 3 }}>
        <Grid item xs={12}>
          <Paper sx={{ p: 3, mb: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Box>
                <Typography variant="h6" gutterBottom>
                  Azure AD App Registration
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Create an Azure AD application with the required permissions for Azure Tenant Grapher
                </Typography>
              </Box>
              <Button
                variant="contained"
                color="primary"
                startIcon={<AppRegIcon />}
                onClick={async () => {
                  try {
                    const result = await window.electronAPI.cli.execute('app-registration', []);
                    setMessage({ type: 'success', text: 'App registration command launched' });
                  } catch (err: any) {
                    setMessage({ type: 'error', text: `Failed to run app-registration: ${err.message}` });
                  }
                }}
              >
                Create App Registration
              </Button>
            </Box>
            
            {(!config.find(c => c.key === 'AZURE_CLIENT_ID')?.value || 
              !config.find(c => c.key === 'AZURE_CLIENT_SECRET')?.value) && (
              <Alert severity="info" sx={{ mt: 2 }}>
                Azure AD credentials not configured. Click "Create App Registration" to set up authentication.
              </Alert>
            )}
          </Paper>
        </Grid>
        
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Environment Variables
            </Typography>
            
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={showSecrets}
                    onChange={(e) => setShowSecrets(e.target.checked)}
                  />
                }
                label="Show Secrets"
              />
              
              <Button
                variant="contained"
                startIcon={<SaveIcon />}
                onClick={handleSave}
                disabled={isSaving}
              >
                Save Config
              </Button>
            </Box>

            {config.map((item, index) => (
              <TextField
                key={item.key}
                fullWidth
                label={item.key}
                value={item.value}
                onChange={(e) => handleConfigChange(index, e.target.value)}
                type={item.isSecret && !showSecrets ? 'password' : 'text'}
                sx={{ mb: 2 }}
                InputProps={{
                  endAdornment: item.isSecret && (
                    <IconButton
                      size="small"
                      onClick={() => setShowSecrets(!showSecrets)}
                    >
                      {showSecrets ? <HideIcon /> : <ShowIcon />}
                    </IconButton>
                  ),
                }}
              />
            ))}

            <Box sx={{ display: 'flex', gap: 1, mt: 2 }}>
              <Button size="small" onClick={() => testConnection('neo4j')}>
                Test Neo4j
              </Button>
              <Button size="small" onClick={() => testConnection('azure')}>
                Test Azure
              </Button>
              <Button size="small" onClick={() => testConnection('openai')}>
                Test OpenAI
              </Button>
            </Box>
          </Paper>
        </Grid>

      </Grid>
    </Box>
  );
};

export default ConfigTab;