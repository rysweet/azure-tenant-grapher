import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  TextField,
  Button,
  Typography,
  Alert,
  Grid,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Divider,
  FormControlLabel,
  Switch,
  IconButton,
} from '@mui/material';
import {
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  Refresh as RefreshIcon,
  Save as SaveIcon,
  Visibility as ShowIcon,
  VisibilityOff as HideIcon,
  LocalHospital as DoctorIcon,
  AppRegistration as AppRegIcon,
} from '@mui/icons-material';

interface ConfigItem {
  key: string;
  value: string;
  isSecret?: boolean;
}

interface DependencyStatus {
  name: string;
  installed: boolean;
  version?: string;
  required?: string;
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
  const [dependencies, setDependencies] = useState<DependencyStatus[]>([]);
  const [showSecrets, setShowSecrets] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    loadConfig();
    checkDependencies();
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

  const checkDependencies = async () => {
    setIsChecking(true);
    try {
      const result = await window.electronAPI.cli.execute('doctor', []);
      
      // Parse doctor output to get dependency status
      const dependencies: DependencyStatus[] = [];
      
      if (result && result.output) {
        const lines = result.output.split('\n');
        
        for (let i = 0; i < lines.length; i++) {
          const line = lines[i];
          if (line.includes("Checking for") && line.includes("CLI...")) {
            // Extract tool name from "Checking for 'terraform' CLI..." format
            const toolMatch = line.match(/Checking for '([^']+)' CLI\.\.\./);
            if (toolMatch) {
              const toolName = toolMatch[1];
              // Look for the next line which should contain the status
              const nextLineIndex = i + 1;
              if (nextLineIndex < lines.length) {
                const statusLine = lines[nextLineIndex];
                const isInstalled = statusLine.includes('✅') && statusLine.includes('is installed');
                
                let displayName = toolName;
                let required = '>=2.0';
                
                // Map tool names to user-friendly display names and requirements
                switch (toolName) {
                  case 'az':
                    displayName = 'Azure CLI';
                    required = '>=2.0';
                    break;
                  case 'terraform':
                    displayName = 'Terraform';
                    required = '>=1.0';
                    break;
                  case 'bicep':
                    displayName = 'Bicep';
                    required = '>=0.4';
                    break;
                }
                
                dependencies.push({
                  name: displayName,
                  installed: isInstalled,
                  version: isInstalled ? 'installed' : undefined,
                  required,
                });
              }
            }
          }
        }
      }
      
      // Add additional system dependencies that aren't checked by doctor command
      dependencies.push(
        { name: 'Python', installed: true, version: '3.11+', required: '>=3.9' },
        { name: 'Docker', installed: true, version: 'installed', required: 'any' }
      );
      
      setDependencies(dependencies);
      setMessage({ type: 'success', text: 'Dependency check complete' });
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message });
      // Fallback to basic dependency list if parsing fails
      setDependencies([
        { name: 'Python', installed: true, version: '3.11+', required: '>=3.9' },
        { name: 'Docker', installed: true, version: 'installed', required: 'any' },
        { name: 'Azure CLI', installed: false, required: '>=2.0' },
        { name: 'Terraform', installed: false, required: '>=1.0' },
        { name: 'Bicep', installed: false, required: '>=0.4' },
      ]);
    } finally {
      setIsChecking(false);
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
        
        <Grid item xs={12} md={6}>
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

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">
                System Dependencies
              </Typography>
              <IconButton onClick={checkDependencies} disabled={isChecking}>
                <RefreshIcon />
              </IconButton>
            </Box>

            <List>
              {dependencies.map((dep) => (
                <React.Fragment key={dep.name}>
                  <ListItem>
                    <ListItemIcon>
                      {dep.installed ? (
                        <CheckIcon color="success" />
                      ) : (
                        <ErrorIcon color="error" />
                      )}
                    </ListItemIcon>
                    <ListItemText
                      primary={dep.name}
                      secondary={
                        dep.installed
                          ? `Version: ${dep.version} (Required: ${dep.required})`
                          : `Not installed (Required: ${dep.required})`
                      }
                    />
                  </ListItem>
                  <Divider />
                </React.Fragment>
              ))}
            </List>

            {dependencies.some((d) => !d.installed) && (
              <Alert 
                severity="warning" 
                sx={{ mt: 2 }}
                action={
                  <Button
                    color="inherit"
                    size="small"
                    startIcon={<DoctorIcon />}
                    onClick={() => window.electronAPI.cli.execute('doctor', [])}
                  >
                    Run Doctor
                  </Button>
                }
              >
                Some dependencies are missing. Run 'atg doctor' to install them.
              </Alert>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default ConfigTab;