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
import CommandOutputDialog from '../common/CommandOutputDialog';

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
    { key: 'NEO4J_PORT', value: '7687', isSecret: false },
    { key: 'NEO4J_URI', value: 'bolt://localhost:7687', isSecret: false },
    { key: 'NEO4J_USER', value: 'neo4j', isSecret: false },
    { key: 'NEO4J_PASSWORD', value: '', isSecret: true },
    { key: 'LOG_LEVEL', value: 'INFO', isSecret: false },
    { key: 'AZURE_OPENAI_ENDPOINT', value: '', isSecret: false },
    { key: 'AZURE_OPENAI_KEY', value: '', isSecret: true },
    { key: 'AZURE_OPENAI_API_VERSION', value: '2024-02-01', isSecret: false },
    { key: 'AZURE_OPENAI_MODEL_CHAT', value: '', isSecret: false },
    { key: 'AZURE_OPENAI_MODEL_REASONING', value: '', isSecret: false },
  ]);
  const [showSecrets, setShowSecrets] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [showAppRegDialog, setShowAppRegDialog] = useState(false);
  const [appRegStatus, setAppRegStatus] = useState<{ exists: boolean; checking: boolean; appName?: string }>({ exists: false, checking: false });

  useEffect(() => {
    loadConfig();
  }, []);
  
  // Check if app registration exists when client ID changes
  useEffect(() => {
    const clientId = config.find(c => c.key === 'AZURE_CLIENT_ID')?.value;
    if (clientId) {
      checkAppRegistration(clientId);
    }
  }, [config]);

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
  
  const checkAppRegistration = async (clientId: string) => {
    setAppRegStatus({ exists: false, checking: true });
    try {
      // Use Azure CLI to check if the app registration exists
      const result = await window.electronAPI.cli.execute('bash', [
        '-c',
        `az ad app show --id ${clientId} --query displayName -o tsv 2>/dev/null`
      ]);
      
      // Listen for the result
      window.electronAPI.on('process:exit', (data: any) => {
        if (data.id === result.data.id) {
          if (data.code === 0 && data.output && data.output.length > 0) {
            // App exists
            const appName = data.output.join('').trim();
            setAppRegStatus({ exists: true, checking: false, appName });
          } else {
            // App doesn't exist or error
            setAppRegStatus({ exists: false, checking: false });
          }
        }
      });
    } catch (err) {
      console.error('Failed to check app registration:', err);
      setAppRegStatus({ exists: false, checking: false });
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

  const parseAppRegistrationOutput = (output: string[]): { clientId?: string; clientSecret?: string } => {
    const result: { clientId?: string; clientSecret?: string } = {};
    
    // Look for patterns in the output that indicate client ID and secret
    for (const line of output) {
      // Look for Client ID patterns
      if (line.includes('Client ID') || line.includes('Application ID') || line.includes('client_id')) {
        const clientIdMatch = line.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i);
        if (clientIdMatch) {
          result.clientId = clientIdMatch[0];
        }
      }
      
      // Look for Client Secret patterns
      if (line.includes('Client Secret') || line.includes('client_secret') || line.includes('Secret Value')) {
        // Client secrets are typically base64-like strings or specific patterns
        const secretMatch = line.match(/[A-Za-z0-9~._-]{32,}/);
        if (secretMatch && !secretMatch[0].match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i)) {
          result.clientSecret = secretMatch[0];
        }
      }
      
      // Alternative patterns for secrets
      if (line.includes('Secret:') || line.includes('secret=')) {
        const secretMatch = line.split(/Secret:?|secret=/).pop()?.trim();
        if (secretMatch && secretMatch.length > 16) {
          result.clientSecret = secretMatch;
        }
      }
    }
    
    return result;
  };

  const handleAppRegistrationComplete = async (output: string[], exitCode: number) => {
    setShowAppRegDialog(false);
    
    if (exitCode === 0) {
      // Parse the output to extract client ID and secret
      const { clientId, clientSecret } = parseAppRegistrationOutput(output);
      
      if (clientId || clientSecret) {
        // Update config state
        setConfig(prev => prev.map(item => {
          if (item.key === 'AZURE_CLIENT_ID' && clientId) {
            return { ...item, value: clientId };
          }
          if (item.key === 'AZURE_CLIENT_SECRET' && clientSecret) {
            return { ...item, value: clientSecret };
          }
          return item;
        }));

        // Save to backend
        try {
          if (clientId) {
            await window.electronAPI.config.set('AZURE_CLIENT_ID', clientId);
          }
          if (clientSecret) {
            await window.electronAPI.config.set('AZURE_CLIENT_SECRET', clientSecret);
          }
          
          let message = 'App registration completed successfully';
          if (clientId && clientSecret) {
            message += '. Client ID and Secret have been saved to configuration.';
          } else if (clientId) {
            message += '. Client ID has been saved to configuration.';
          } else if (clientSecret) {
            message += '. Client Secret has been saved to configuration.';
          }
          
          setMessage({ type: 'success', text: message });
          
          // Reload config to ensure everything is up to date
          await loadConfig();
          
        } catch (err: any) {
          setMessage({ 
            type: 'error', 
            text: `App registration completed but failed to save configuration: ${err.message}` 
          });
        }
      } else {
        setMessage({ 
          type: 'success', 
          text: 'App registration completed successfully. Please manually copy the Client ID and Secret from the output above.' 
        });
      }
    } else {
      setMessage({ type: 'error', text: 'App registration failed. Please check the output above for details.' });
    }
  };

  const handleAppRegistrationError = (error: string) => {
    setShowAppRegDialog(false);
    setMessage({ type: 'error', text: `App registration failed: ${error}` });
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
                  {appRegStatus.checking ? 'Checking app registration...' :
                   appRegStatus.exists ? `App registration found: ${appRegStatus.appName}` :
                   'Create an Azure AD application with the required permissions for Azure Tenant Grapher'}
                </Typography>
              </Box>
              {!appRegStatus.exists && !appRegStatus.checking && (
                <Button
                  variant="contained"
                  color="primary"
                  startIcon={<AppRegIcon />}
                  onClick={() => setShowAppRegDialog(true)}
                >
                  Create App Registration
                </Button>
              )}
            </Box>
            
            {appRegStatus.exists && config.find(c => c.key === 'AZURE_CLIENT_ID')?.value && (
              <Alert severity="success" sx={{ mt: 2 }}>
                App registration configured: {appRegStatus.appName}
              </Alert>
            )}
            
            {!appRegStatus.exists && (!config.find(c => c.key === 'AZURE_CLIENT_ID')?.value || 
              !config.find(c => c.key === 'AZURE_CLIENT_SECRET')?.value) && !appRegStatus.checking && (
              <Alert severity="error" sx={{ mt: 2 }}>
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
              <Button size="small" onClick={() => testConnection('azure-openai')}>
                Test Azure OpenAI
              </Button>
            </Box>
          </Paper>
        </Grid>

      </Grid>

      {/* App Registration Command Dialog */}
      <CommandOutputDialog
        open={showAppRegDialog}
        onClose={() => setShowAppRegDialog(false)}
        title="Create Azure AD App Registration"
        command="app-registration"
        args={['--create-secret', '--save-to-env']}
        onCommandComplete={handleAppRegistrationComplete}
        onError={handleAppRegistrationError}
      />
    </Box>
  );
};

export default ConfigTab;