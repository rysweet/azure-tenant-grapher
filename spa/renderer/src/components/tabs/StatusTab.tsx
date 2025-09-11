import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Grid,
  Card,
  CardContent,
  Alert,
  LinearProgress,
  CircularProgress,
  Chip,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Divider,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Stack,
} from '@mui/material';
import {
  Storage as StorageIcon,
  AccountTree as TreeIcon,
  Link as LinkIcon,
  Schedule as ScheduleIcon,
  Refresh as RefreshIcon,
  CloudDownload as BackupIcon,
  CloudUpload as RestoreIcon,
  DeleteForever as WipeIcon,
  CheckCircle as ConnectedIcon,
  Error as DisconnectedIcon,
  PlayArrow as StartIcon,
  Stop as StopIcon,
  Check as CheckIcon,
  Error as ErrorIcon,
  LocalHospital as DoctorIcon,
  Warning as WarningIcon,
  Person as PersonIcon,
  Groups as GroupsIcon,
  Apps as AppsIcon,
  AdminPanelSettings as AdminIcon,
  MenuBook as DocsIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

interface TimestampInfo {
  timestamp: any;
  utcString: string | null;
  localString: string | null;
  timezone: string;
}

interface DBStats {
  nodeCount: number;
  edgeCount: number;
  nodeTypes: Array<{ type: string; count: number }>;
  edgeTypes: Array<{ type: string; count: number }>;
  lastUpdate: TimestampInfo;
  isEmpty: boolean;
  labelCount?: number;
  relTypeCount?: number;
}

interface Dependency {
  name: string;
  installed: boolean;
  version?: string;
  required: string;
}

const StatusTab: React.FC = () => {
  const navigate = useNavigate();
  const [dbStats, setDbStats] = useState<DBStats | null>(null);
  const [loadingStats, setLoadingStats] = useState(false);
  const [neo4jStatus, setNeo4jStatus] = useState<any>(null);
  const [startingNeo4j, setStartingNeo4j] = useState(false);
  const [stoppingNeo4j, setStoppingNeo4j] = useState(false);
  const [backupDialog, setBackupDialog] = useState(false);
  const [restoreDialog, setRestoreDialog] = useState(false);
  const [wipeDialog, setWipeDialog] = useState(false);
  const [backupPath, setBackupPath] = useState('');
  const [restorePath, setRestorePath] = useState('');
  const [operationInProgress, setOperationInProgress] = useState(false);
  const [operationMessage, setOperationMessage] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [isCheckingDeps, setIsCheckingDeps] = useState(false);
  const [dependencies, setDependencies] = useState<Dependency[]>([]);
  const [azureStatus, setAzureStatus] = useState<{ connected: boolean; error?: string; loading: boolean; accountInfo?: any }>({ connected: false, loading: true });
  const [openAIStatus, setOpenAIStatus] = useState<{ connected: boolean; error?: string; loading: boolean; endpoint?: string; models?: any; testResponse?: string }>({ connected: false, loading: true });
  const [graphPermissions, setGraphPermissions] = useState<{
    loading: boolean;
    permissions?: {
      users: boolean;
      groups: boolean;
      servicePrincipals: boolean;
      directoryRoles: boolean;
    };
    success?: boolean;
    error?: string;
    message?: string;
  }>({ loading: true });

  useEffect(() => {
    // Initial load
    checkNeo4jStatus();
    checkDependencies();
    checkAzureConnection();
    checkOpenAIConnection();
    checkGraphPermissions();

    // Set up auto-refresh every 5 seconds for Neo4j
    const interval = setInterval(() => {
      checkNeo4jStatus();
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  const checkNeo4jStatus = async () => {
    try {
      const response = await axios.get('http://localhost:3001/api/neo4j/status');
      setNeo4jStatus(response.data);

      // If Neo4j is running, load database stats
      if (response.data.running) {
        await loadDatabaseStats();
      }
    } catch (err) {
      console.error('Failed to check Neo4j status:', err);
      setNeo4jStatus({ status: 'error', running: false });
    }
  };

  const loadDatabaseStats = async () => {
    setLoadingStats(true);
    try {
      const response = await axios.get('http://localhost:3001/api/graph/stats');
      const stats = response.data;
      setDbStats(stats);
    } catch (err) {
      console.error('Failed to load database stats:', err);
      setDbStats({
        nodeCount: 0,
        edgeCount: 0,
        nodeTypes: [],
        edgeTypes: [],
        lastUpdate: { timestamp: null, utcString: null, localString: null, timezone: 'N/A' },
        isEmpty: true
      });
    } finally {
      setLoadingStats(false);
    }
  };

  const checkAzureConnection = async () => {
    setAzureStatus(prev => ({ ...prev, loading: true }));
    try {
      const response = await axios.get('http://localhost:3001/api/test/azure');
      setAzureStatus({
        connected: response.data.success,
        error: response.data.error,
        loading: false,
        accountInfo: response.data.accountInfo
      });
    } catch (err: any) {
      setAzureStatus({ connected: false, error: err.response?.data?.error || err.message, loading: false });
    }
  };

  const checkOpenAIConnection = async () => {
    setOpenAIStatus(prev => ({ ...prev, loading: true }));
    try {
      const response = await axios.get('http://localhost:3001/api/test/azure-openai');
      setOpenAIStatus({
        connected: response.data.success,
        error: response.data.error,
        loading: false,
        endpoint: response.data.endpoint,
        models: response.data.models,
        testResponse: response.data.testResponse
      });
    } catch (err: any) {
      setOpenAIStatus({ connected: false, error: err.response?.data?.error || err.message, loading: false });
    }
  };

  const checkGraphPermissions = async () => {
    setGraphPermissions(prev => ({ ...prev, loading: true }));
    try {
      const response = await axios.get('http://localhost:3001/api/test/graph-permissions');
      setGraphPermissions({
        loading: false,
        success: response.data.success,
        permissions: response.data.permissions,
        error: response.data.error,
        message: response.data.message
      });
    } catch (err: any) {
      setGraphPermissions({
        loading: false,
        success: false,
        error: err.response?.data?.error || err.message,
        permissions: {
          users: false,
          groups: false,
          servicePrincipals: false,
          directoryRoles: false
        }
      });
    }
  };

  const checkDependencies = async () => {
    setIsCheckingDeps(true);
    try {
      const response = await axios.get('http://localhost:3001/api/dependencies');
      setDependencies(response.data);
    } catch (err: any) {
      console.error('Failed to check dependencies:', err);
      // Fallback to empty array if API fails
      setDependencies([]);
    } finally {
      setIsCheckingDeps(false);
    }
  };

  const handleRunDoctor = () => {
    navigate('/cli?autoCommand=doctor');
  };

  const startNeo4j = async () => {
    setStartingNeo4j(true);
    setError(null);
    try {
      await axios.post('http://localhost:3001/api/neo4j/start');
      setSuccess('Neo4j started successfully');
      setTimeout(() => {
        checkNeo4jStatus();
        setStartingNeo4j(false);
      }, 3000);
    } catch (err: any) {
      setError('Failed to start Neo4j: ' + (err.response?.data?.error || err.message));
      setStartingNeo4j(false);
    }
  };

  const stopNeo4j = async () => {
    setStoppingNeo4j(true);
    setError(null);
    try {
      await axios.post('http://localhost:3001/api/neo4j/stop');
      setSuccess('Neo4j stopped successfully');
      setTimeout(() => {
        checkNeo4jStatus();
        setStoppingNeo4j(false);
      }, 2000);
    } catch (err: any) {
      setError('Failed to stop Neo4j: ' + (err.response?.data?.error || err.message));
      setStoppingNeo4j(false);
    }
  };

  const handleBackup = async () => {
    if (!backupPath) {
      setError('Please specify a backup path');
      return;
    }

    setOperationInProgress(true);
    setOperationMessage('Creating backup...');
    setError(null);

    try {
      const response = await axios.post('http://localhost:3001/api/database/backup', {
        path: backupPath
      });
      setSuccess(`Backup created successfully at ${backupPath}`);
      setBackupDialog(false);
      setBackupPath('');
    } catch (err: any) {
      setError('Backup failed: ' + (err.response?.data?.error || err.message));
    } finally {
      setOperationInProgress(false);
      setOperationMessage('');
    }
  };

  const handleRestore = async () => {
    if (!restorePath) {
      setError('Please specify a restore path');
      return;
    }

    setOperationInProgress(true);
    setOperationMessage('Restoring database...');
    setError(null);

    try {
      const response = await axios.post('http://localhost:3001/api/database/restore', {
        path: restorePath
      });
      setSuccess('Database restored successfully');
      setRestoreDialog(false);
      setRestorePath('');
      // Reload stats after restore
      setTimeout(() => {
        checkNeo4jStatus();
      }, 3000);
    } catch (err: any) {
      setError('Restore failed: ' + (err.response?.data?.error || err.message));
    } finally {
      setOperationInProgress(false);
      setOperationMessage('');
    }
  };

  const handleWipe = async () => {
    setOperationInProgress(true);
    setOperationMessage('Wiping database...');
    setError(null);

    try {
      const response = await axios.post('http://localhost:3001/api/database/wipe');
      setSuccess('Database wiped successfully');
      setWipeDialog(false);
      // Reload stats after wipe
      setTimeout(() => {
        checkNeo4jStatus();
      }, 2000);
    } catch (err: any) {
      setError('Wipe failed: ' + (err.response?.data?.error || err.message));
    } finally {
      setOperationInProgress(false);
      setOperationMessage('');
    }
  };

  const formatNumber = (num: number) => {
    return num.toLocaleString();
  };

  const formatTimestampDisplay = (timestampInfo: TimestampInfo | null) => {
    if (!timestampInfo || !timestampInfo.timestamp) {
      return (
        <Typography variant="body2" color="textSecondary">
          Never
        </Typography>
      );
    }

    const { utcString, localString, timezone } = timestampInfo;

    if (!utcString && !localString) {
      return (
        <Typography variant="body2" color="error">
          Invalid timestamp
        </Typography>
      );
    }

    return (
      <Stack spacing={0.5}>
        <Typography variant="body2" sx={{ fontWeight: 'medium' }}>
          {localString || 'Unable to display local time'}
        </Typography>
        <Typography variant="caption" color="textSecondary" sx={{ fontSize: '0.75rem' }}>
          {utcString || 'Unable to display UTC time'}
        </Typography>
        {timezone && timezone !== 'N/A' && timezone !== 'Unknown' && (
          <Typography variant="caption" color="textSecondary" sx={{ fontSize: '0.7rem', fontStyle: 'italic' }}>
            Timezone: {timezone}
          </Typography>
        )}
      </Stack>
    );
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 2 }}>
      {/* Neo4j Database Status with Statistics */}
      <Paper sx={{ p: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
          <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1, fontSize: '1.1rem' }}>
            <StorageIcon fontSize="small" /> Neo4j Database
          </Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            {neo4jStatus?.running ? (
              <Button
                variant="outlined"
                color="error"
                startIcon={<StopIcon />}
                onClick={stopNeo4j}
                disabled={stoppingNeo4j}
              >
                {stoppingNeo4j ? 'Stopping...' : 'Stop'}
              </Button>
            ) : (
              <Button
                variant="contained"
                color="success"
                startIcon={<StartIcon />}
                onClick={startNeo4j}
                disabled={startingNeo4j}
              >
                {startingNeo4j ? 'Starting...' : 'Start'}
              </Button>
            )}
            <Button
              variant="outlined"
              startIcon={<BackupIcon />}
              onClick={() => setBackupDialog(true)}
              disabled={!neo4jStatus?.running || operationInProgress}
            >
              Backup
            </Button>
            <Button
              variant="outlined"
              startIcon={<RestoreIcon />}
              onClick={() => setRestoreDialog(true)}
              disabled={!neo4jStatus?.running || operationInProgress}
            >
              Restore
            </Button>
            <Button
              variant="outlined"
              color="error"
              startIcon={<WipeIcon />}
              onClick={() => setWipeDialog(true)}
              disabled={!neo4jStatus?.running || operationInProgress}
            >
              Wipe
            </Button>
            <Tooltip title="Refresh Status">
              <IconButton onClick={checkNeo4jStatus} disabled={loadingStats}>
                <RefreshIcon />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {success && (
          <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>
            {success}
          </Alert>
        )}

        {operationInProgress && (
          <Box sx={{ mb: 2 }}>
            <LinearProgress />
            <Typography variant="body2" sx={{ mt: 1 }}>
              {operationMessage}
            </Typography>
          </Box>
        )}

        <Grid container spacing={1}>
          <Grid item xs={6} md={3}>
            <Card variant="outlined" sx={{ height: '100%' }}>
              <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
                <Typography color="textSecondary" variant="caption">
                  Status
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  {neo4jStatus?.running ? (
                    <>
                      <ConnectedIcon color="success" fontSize="small" />
                      <Typography variant="body2" color="success.main" fontWeight="medium">Connected</Typography>
                    </>
                  ) : (
                    <>
                      <DisconnectedIcon color="error" fontSize="small" />
                      <Typography variant="body2" color="error.main" fontWeight="medium">Disconnected</Typography>
                    </>
                  )}
                </Box>
                {neo4jStatus?.containerName && (
                  <Typography variant="caption" color="textSecondary">
                    Container: {neo4jStatus.containerName}
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={6} md={3}>
            <Card variant="outlined" sx={{ height: '100%' }}>
              <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
                <Typography color="textSecondary" variant="caption">
                  Connection
                </Typography>
                <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>
                  {neo4jStatus?.uri || 'Not available'}
                </Typography>
                <Typography variant="caption" color="textSecondary">
                  Port: {neo4jStatus?.port || 'N/A'}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={6} md={3}>
            <Card variant="outlined" sx={{ height: '100%' }}>
              <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
                <Typography color="textSecondary" variant="caption">
                  Health
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  {neo4jStatus?.health === 'healthy' && (
                    <>
                      <CheckIcon color="success" />
                      <Typography variant="body2" color="success.main" fontWeight="medium">Healthy</Typography>
                    </>
                  )}
                  {neo4jStatus?.health === 'starting' && (
                    <>
                      <LinearProgress sx={{ width: 16, height: 16, borderRadius: 1 }} />
                      <Typography variant="h6" color="warning.main">Starting</Typography>
                    </>
                  )}
                  {neo4jStatus?.health === 'stopped' && (
                    <>
                      <StopIcon color="disabled" />
                      <Typography variant="h6" color="text.disabled">Stopped</Typography>
                    </>
                  )}
                  {neo4jStatus?.health === 'error' && (
                    <>
                      <ErrorIcon color="error" />
                      <Typography variant="h6" color="error.main">Error</Typography>
                    </>
                  )}
                  {!neo4jStatus?.health && (
                    <Typography variant="h6" color="text.disabled">Unknown</Typography>
                  )}
                </Box>
                {neo4jStatus?.startedAt && (
                  <Typography variant="caption" color="textSecondary">
                    Started: {new Date(neo4jStatus.startedAt).toLocaleTimeString()}
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={6} md={3}>
            <Card variant="outlined" sx={{ height: '100%' }}>
              <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
                <Typography color="textSecondary" variant="caption">
                  PID
                </Typography>
                <Typography variant="body2" fontWeight="medium">
                  {neo4jStatus?.pid || 'N/A'}
                </Typography>
                <Typography variant="caption" color="textSecondary">
                  Docker Container
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Database Statistics - integrated */}
        {neo4jStatus?.running && (
          <>
            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle2" color="textSecondary" gutterBottom>
              Database Statistics
            </Typography>
            {loadingStats ? (
              <LinearProgress />
          ) : (
            <Grid container spacing={1}>
              <Grid item xs={6} md={3}>
                <Card variant="outlined">
                  <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
                    <Typography color="textSecondary" variant="caption" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <TreeIcon sx={{ fontSize: 14 }} /> Nodes
                    </Typography>
                    <Typography variant="h6">
                      {formatNumber(dbStats?.nodeCount || 0)}
                    </Typography>
                    {dbStats?.labelCount && (
                      <Typography variant="caption" color="textSecondary">
                        {dbStats.labelCount} types
                      </Typography>
                    )}
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={6} md={3}>
                <Card variant="outlined">
                  <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
                    <Typography color="textSecondary" variant="caption" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <LinkIcon sx={{ fontSize: 14 }} /> Edges
                    </Typography>
                    <Typography variant="h6">
                      {formatNumber(dbStats?.edgeCount || 0)}
                    </Typography>
                    {dbStats?.relTypeCount && (
                      <Typography variant="caption" color="textSecondary">
                        {dbStats.relTypeCount} types
                      </Typography>
                    )}
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={6} md={3}>
                <Card variant="outlined">
                  <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
                    <Typography color="textSecondary" variant="caption" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <ScheduleIcon sx={{ fontSize: 14 }} /> Updated
                    </Typography>
                    <Typography variant="body2">
                      {dbStats?.lastUpdate?.localString ? dbStats.lastUpdate.localString.split(' ')[1] : 'Never'}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>

              <Grid item xs={6} md={3}>
                <Card variant="outlined">
                  <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
                    <Typography color="textSecondary" variant="caption">
                      State
                    </Typography>
                    <Chip
                      label={dbStats?.isEmpty ? 'Empty' : 'Populated'}
                      color={dbStats?.isEmpty ? 'default' : 'success'}
                      size="small"
                      variant="outlined"
                    />
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          )}
          </>
        )}
      </Paper>

      {/* External Services Status */}
      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" sx={{ fontSize: '1.1rem', mb: 1.5 }}>
          External Services
        </Typography>
        <Grid container spacing={1}>
          {/* Azure Connection */}
          <Grid item xs={6}>
            <Card variant="outlined" sx={{
              backgroundColor: azureStatus.connected ? 'rgba(76, 175, 80, 0.05)' : 'rgba(244, 67, 54, 0.05)',
              borderColor: azureStatus.connected ? 'success.main' : 'error.main'
            }}>
              <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <Box>
                    <Typography color="textSecondary" variant="caption">
                      Azure
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.5 }}>
                      {azureStatus.loading ? (
                        <CircularProgress size={16} />
                      ) : azureStatus.connected ? (
                        <>
                          <CheckIcon color="success" sx={{ fontSize: 16 }} />
                          <Typography variant="body2" color="success.main">Connected</Typography>
                        </>
                      ) : (
                        <>
                          <ErrorIcon color="error" sx={{ fontSize: 16 }} />
                          <Typography variant="body2" color="error.main">Disconnected</Typography>
                        </>
                      )}
                    </Box>
                    {azureStatus.error && (
                      <Typography variant="caption" color="error" sx={{ fontSize: '0.65rem', mt: 0.5, display: 'block' }}>
                        {azureStatus.error}
                      </Typography>
                    )}
                    {azureStatus.connected && azureStatus.accountInfo && (
                      <Box sx={{ mt: 0.5 }}>
                        <Typography variant="caption" sx={{ fontSize: '0.65rem', display: 'block', color: 'text.secondary' }}>
                          {azureStatus.accountInfo.name}
                        </Typography>
                        <Typography variant="caption" sx={{ fontSize: '0.6rem', display: 'block', color: 'text.disabled' }}>
                          {azureStatus.accountInfo.user}
                        </Typography>
                      </Box>
                    )}
                  </Box>
                  <Tooltip title="Test Azure Connection">
                    <IconButton
                      onClick={checkAzureConnection}
                      disabled={azureStatus.loading}
                      size="small"
                      sx={{ padding: '2px' }}
                    >
                      <RefreshIcon sx={{ fontSize: 14 }} />
                    </IconButton>
                  </Tooltip>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* Azure OpenAI Connection */}
          <Grid item xs={6}>
            <Card variant="outlined" sx={{
              backgroundColor: openAIStatus.connected ? 'rgba(76, 175, 80, 0.05)' : 'rgba(244, 67, 54, 0.05)',
              borderColor: openAIStatus.connected ? 'success.main' : 'warning.main'
            }}>
              <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <Box>
                    <Typography color="textSecondary" variant="caption">
                      Azure OpenAI
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.5 }}>
                      {openAIStatus.loading ? (
                        <CircularProgress size={16} />
                      ) : openAIStatus.connected ? (
                        <>
                          <CheckIcon color="success" sx={{ fontSize: 16 }} />
                          <Typography variant="body2" color="success.main">Connected</Typography>
                        </>
                      ) : (
                        <>
                          <WarningIcon color="warning" sx={{ fontSize: 16 }} />
                          <Typography variant="body2" color="warning.main">Not Configured</Typography>
                        </>
                      )}
                    </Box>
                    {openAIStatus.error && (
                      <Typography variant="caption" color="error" sx={{ fontSize: '0.65rem', mt: 0.5, display: 'block' }}>
                        {openAIStatus.error}
                      </Typography>
                    )}
                    {openAIStatus.connected && openAIStatus.endpoint && (
                      <Box sx={{ mt: 0.5 }}>
                        <Typography variant="caption" sx={{ fontSize: '0.65rem', display: 'block', color: 'text.secondary' }}>
                          {openAIStatus.endpoint}
                        </Typography>
                        {openAIStatus.models && (
                          <Typography variant="caption" sx={{ fontSize: '0.6rem', display: 'block', color: 'text.disabled' }}>
                            Chat: {openAIStatus.models.chat}
                          </Typography>
                        )}
                        {openAIStatus.testResponse && (
                          <Box sx={{ mt: 1, p: 1, bgcolor: 'background.default', borderRadius: 1 }}>
                            <Typography variant="caption" sx={{ fontSize: '0.65rem', fontStyle: 'italic', color: 'text.secondary' }}>
                              "{openAIStatus.testResponse}"
                            </Typography>
                          </Box>
                        )}
                      </Box>
                    )}
                    {!openAIStatus.connected && !openAIStatus.error && (
                      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.65rem', mt: 0.5, display: 'block' }}>
                        Optional - Used for enhanced descriptions
                      </Typography>
                    )}
                  </Box>
                  <Tooltip title="Test Azure OpenAI Connection">
                    <IconButton
                      onClick={checkOpenAIConnection}
                      disabled={openAIStatus.loading}
                      size="small"
                      sx={{ padding: '2px' }}
                    >
                      <RefreshIcon sx={{ fontSize: 14 }} />
                    </IconButton>
                  </Tooltip>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>

        {/* Graph API Permissions - New Section */}
        <Divider sx={{ my: 2 }} />
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
          <Typography variant="subtitle2" color="textSecondary">
            Microsoft Graph API Permissions
          </Typography>
          <Tooltip title="Check Graph API Permissions">
            <IconButton
              onClick={checkGraphPermissions}
              disabled={graphPermissions.loading}
              size="small"
            >
              <RefreshIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>
        </Box>

        {graphPermissions.loading ? (
          <LinearProgress />
        ) : (
          <Box>
            <Grid container spacing={1}>
              {/* User.Read Permission */}
              <Grid item xs={6} md={3}>
                <Card variant="outlined" sx={{
                  backgroundColor: graphPermissions.permissions?.users
                    ? 'rgba(76, 175, 80, 0.05)'
                    : 'rgba(244, 67, 54, 0.05)',
                  borderColor: graphPermissions.permissions?.users
                    ? 'success.main'
                    : 'error.main'
                }}>
                  <CardContent sx={{ p: 1, '&:last-child': { pb: 1 } }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <PersonIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
                      <Typography variant="caption" fontWeight="medium">
                        User.Read.All
                      </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.5 }}>
                      {graphPermissions.permissions?.users ? (
                        <CheckIcon color="success" sx={{ fontSize: 12 }} />
                      ) : (
                        <ErrorIcon color="error" sx={{ fontSize: 12 }} />
                      )}
                      <Typography variant="caption" sx={{ fontSize: '0.65rem' }}>
                        {graphPermissions.permissions?.users ? 'Granted' : 'Missing'}
                      </Typography>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>

              {/* Group.Read Permission */}
              <Grid item xs={6} md={3}>
                <Card variant="outlined" sx={{
                  backgroundColor: graphPermissions.permissions?.groups
                    ? 'rgba(76, 175, 80, 0.05)'
                    : 'rgba(244, 67, 54, 0.05)',
                  borderColor: graphPermissions.permissions?.groups
                    ? 'success.main'
                    : 'error.main'
                }}>
                  <CardContent sx={{ p: 1, '&:last-child': { pb: 1 } }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <GroupsIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
                      <Typography variant="caption" fontWeight="medium">
                        Group.Read.All
                      </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.5 }}>
                      {graphPermissions.permissions?.groups ? (
                        <CheckIcon color="success" sx={{ fontSize: 12 }} />
                      ) : (
                        <ErrorIcon color="error" sx={{ fontSize: 12 }} />
                      )}
                      <Typography variant="caption" sx={{ fontSize: '0.65rem' }}>
                        {graphPermissions.permissions?.groups ? 'Granted' : 'Missing'}
                      </Typography>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>

              {/* ServicePrincipal.Read Permission */}
              <Grid item xs={6} md={3}>
                <Card variant="outlined" sx={{
                  backgroundColor: graphPermissions.permissions?.servicePrincipals
                    ? 'rgba(76, 175, 80, 0.05)'
                    : 'rgba(255, 152, 0, 0.05)',
                  borderColor: graphPermissions.permissions?.servicePrincipals
                    ? 'success.main'
                    : 'warning.main'
                }}>
                  <CardContent sx={{ p: 1, '&:last-child': { pb: 1 } }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <AppsIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
                      <Typography variant="caption" fontWeight="medium">
                        Application.Read
                      </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.5 }}>
                      {graphPermissions.permissions?.servicePrincipals ? (
                        <CheckIcon color="success" sx={{ fontSize: 12 }} />
                      ) : (
                        <WarningIcon color="warning" sx={{ fontSize: 12 }} />
                      )}
                      <Typography variant="caption" sx={{ fontSize: '0.65rem' }}>
                        {graphPermissions.permissions?.servicePrincipals ? 'Granted' : 'Optional'}
                      </Typography>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>

              {/* DirectoryRole.Read Permission */}
              <Grid item xs={6} md={3}>
                <Card variant="outlined" sx={{
                  backgroundColor: graphPermissions.permissions?.directoryRoles
                    ? 'rgba(76, 175, 80, 0.05)'
                    : 'rgba(255, 152, 0, 0.05)',
                  borderColor: graphPermissions.permissions?.directoryRoles
                    ? 'success.main'
                    : 'warning.main'
                }}>
                  <CardContent sx={{ p: 1, '&:last-child': { pb: 1 } }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <AdminIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
                      <Typography variant="caption" fontWeight="medium">
                        RoleManagement.Read
                      </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.5 }}>
                      {graphPermissions.permissions?.directoryRoles ? (
                        <CheckIcon color="success" sx={{ fontSize: 12 }} />
                      ) : (
                        <WarningIcon color="warning" sx={{ fontSize: 12 }} />
                      )}
                      <Typography variant="caption" sx={{ fontSize: '0.65rem' }}>
                        {graphPermissions.permissions?.directoryRoles ? 'Granted' : 'Optional'}
                      </Typography>
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            </Grid>

            {/* Alert if missing required permissions */}
            {!graphPermissions.success && (
              <Alert
                severity="warning"
                sx={{ mt: 2 }}
                action={
                  <Button
                    color="inherit"
                    size="small"
                    startIcon={<DocsIcon />}
                    onClick={() => {
                      // Open the docs in the CLI tab with a command to view them
                      navigate('/cli?autoCommand=cat%20docs/GRAPH_API_SETUP.md');
                    }}
                  >
                    View Setup Guide
                  </Button>
                }
              >
                {graphPermissions.message || 'Missing required Graph API permissions for AAD/Entra ID discovery'}
              </Alert>
            )}

            {/* Success message if all required permissions are granted */}
            {graphPermissions.success && (
              <Alert severity="success" sx={{ mt: 2 }}>
                {graphPermissions.message || 'All required Graph API permissions are configured'}
              </Alert>
            )}
          </Box>
        )}
      </Paper>

      {/* System Dependencies - Compact */}
      <Paper sx={{ p: 2 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
          <Typography variant="h6" sx={{ fontSize: '1.1rem' }}>
            System Dependencies
          </Typography>
          <IconButton onClick={checkDependencies} disabled={isCheckingDeps} size="small">
            <RefreshIcon fontSize="small" />
          </IconButton>
        </Box>

        {isCheckingDeps ? (
          <LinearProgress />
        ) : (
          <>
            <Grid container spacing={1}>
              {dependencies.map((dep) => (
                <Grid item xs={6} md={3} key={dep.name}>
                  <Card variant="outlined" sx={{
                    backgroundColor: dep.installed ? 'rgba(76, 175, 80, 0.05)' : 'rgba(244, 67, 54, 0.05)',
                    borderColor: dep.installed ? 'success.main' : 'error.main'
                  }}>
                    <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 0.5 }}>
                        {dep.installed ? (
                          <CheckIcon color="success" sx={{ fontSize: 16 }} />
                        ) : (
                          <ErrorIcon color="error" sx={{ fontSize: 16 }} />
                        )}
                        <Typography variant="body2" fontWeight="medium">
                          {dep.name}
                        </Typography>
                      </Box>
                      <Typography variant="caption" color="textSecondary" sx={{ fontSize: '0.7rem' }}>
                        {dep.installed
                          ? `v${dep.version}`
                          : `Required: ${dep.required}`}
                      </Typography>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>

            {dependencies.some((d) => !d.installed) && (
              <Alert
                severity="warning"
                sx={{ mt: 2 }}
                action={
                  <Button
                    color="inherit"
                    size="small"
                    startIcon={<DoctorIcon />}
                    onClick={handleRunDoctor}
                  >
                    Run Doctor
                  </Button>
                }
              >
                Some dependencies are missing. Run 'atg doctor' to install them.
              </Alert>
            )}
          </>
        )}
      </Paper>


      {/* Backup Dialog */}
      <Dialog open={backupDialog} onClose={() => setBackupDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Backup Database</DialogTitle>
        <DialogContent>
          <Typography variant="body2" sx={{ mb: 2 }}>
            Create a backup of the current Neo4j database. The database will be temporarily stopped during backup.
          </Typography>
          <TextField
            fullWidth
            label="Backup Path"
            value={backupPath}
            onChange={(e) => setBackupPath(e.target.value)}
            placeholder="/path/to/backup.dump"
            helperText="Full path where the backup file will be saved"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setBackupDialog(false)}>Cancel</Button>
          <Button onClick={handleBackup} variant="contained" disabled={operationInProgress}>
            Create Backup
          </Button>
        </DialogActions>
      </Dialog>

      {/* Restore Dialog */}
      <Dialog open={restoreDialog} onClose={() => setRestoreDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Restore Database</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            This will replace the current database with the backup. All current data will be lost.
          </Alert>
          <TextField
            fullWidth
            label="Restore Path"
            value={restorePath}
            onChange={(e) => setRestorePath(e.target.value)}
            placeholder="/path/to/backup.dump"
            helperText="Full path to the backup file to restore"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRestoreDialog(false)}>Cancel</Button>
          <Button onClick={handleRestore} variant="contained" color="warning" disabled={operationInProgress}>
            Restore Backup
          </Button>
        </DialogActions>
      </Dialog>

      {/* Wipe Dialog */}
      <Dialog open={wipeDialog} onClose={() => setWipeDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Wipe Database</DialogTitle>
        <DialogContent>
          <Alert severity="error" sx={{ mb: 2 }}>
            This will permanently delete all data in the database. This action cannot be undone.
          </Alert>
          <Typography variant="body2">
            Are you sure you want to wipe the entire database?
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setWipeDialog(false)}>Cancel</Button>
          <Button onClick={handleWipe} variant="contained" color="error" disabled={operationInProgress}>
            Wipe Database
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default StatusTab;
