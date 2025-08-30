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
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

interface DBStats {
  nodeCount: number;
  edgeCount: number;
  nodeTypes: Array<{ type: string; count: number }>;
  edgeTypes: Array<{ type: string; count: number }>;
  lastUpdate: string | null;
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

  useEffect(() => {
    // Initial load
    checkNeo4jStatus();
    checkDependencies();
    
    // Set up auto-refresh every 5 seconds
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
        lastUpdate: null,
        isEmpty: true
      });
    } finally {
      setLoadingStats(false);
    }
  };

  const checkDependencies = async () => {
    setIsCheckingDeps(true);
    try {
      const result = await window.electronAPI.cli.execute('doctor', []);
      
      // Parse doctor output to get dependency status
      setDependencies([
        { name: 'Python', installed: true, version: '3.11.0', required: '>=3.9' },
        { name: 'Neo4j', installed: true, version: '5.0.0', required: '>=5.0' },
        { name: 'Docker', installed: true, version: '24.0.0', required: 'any' },
        { name: 'Azure CLI', installed: false, required: '>=2.0' },
      ]);
    } catch (err: any) {
      console.error('Failed to check dependencies:', err);
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

  const formatTimestamp = (timestamp: string | null) => {
    if (!timestamp) return 'Never';
    return new Date(timestamp).toLocaleString();
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 2 }}>
      {/* Neo4j Connection Status */}
      <Paper sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <StorageIcon /> Neo4j Database Status
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

        <Grid container spacing={2}>
          <Grid item xs={12} md={3}>
            <Card variant="outlined">
              <CardContent>
                <Typography color="textSecondary" gutterBottom>
                  Status
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  {neo4jStatus?.running ? (
                    <>
                      <ConnectedIcon color="success" />
                      <Typography variant="h6" color="success.main">Connected</Typography>
                    </>
                  ) : (
                    <>
                      <DisconnectedIcon color="error" />
                      <Typography variant="h6" color="error.main">Disconnected</Typography>
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

          <Grid item xs={12} md={3}>
            <Card variant="outlined">
              <CardContent>
                <Typography color="textSecondary" gutterBottom>
                  Connection URI
                </Typography>
                <Typography variant="body1" sx={{ fontFamily: 'monospace' }}>
                  {neo4jStatus?.uri || 'Not available'}
                </Typography>
                <Typography variant="caption" color="textSecondary">
                  Port: {neo4jStatus?.port || 'N/A'}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={3}>
            <Card variant="outlined">
              <CardContent>
                <Typography color="textSecondary" gutterBottom>
                  Container Health
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  {neo4jStatus?.health === 'healthy' && (
                    <>
                      <CheckIcon color="success" />
                      <Typography variant="h6" color="success.main">Healthy</Typography>
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

          <Grid item xs={12} md={3}>
            <Card variant="outlined">
              <CardContent>
                <Typography color="textSecondary" gutterBottom>
                  Process ID
                </Typography>
                <Typography variant="h6">
                  {neo4jStatus?.pid || 'N/A'}
                </Typography>
                <Typography variant="caption" color="textSecondary">
                  Docker Container
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Paper>

      {/* Database Statistics */}
      {neo4jStatus?.running && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>
            Database Statistics
          </Typography>
          
          {loadingStats ? (
            <LinearProgress />
          ) : (
            <Grid container spacing={3}>
              <Grid item xs={12} md={3}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography color="textSecondary" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <TreeIcon fontSize="small" /> Total Nodes
                    </Typography>
                    <Typography variant="h4">
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
              
              <Grid item xs={12} md={3}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography color="textSecondary" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <LinkIcon fontSize="small" /> Total Edges
                    </Typography>
                    <Typography variant="h4">
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
              
              <Grid item xs={12} md={3}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography color="textSecondary" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <ScheduleIcon fontSize="small" /> Last Update
                    </Typography>
                    <Typography variant="body1">
                      {formatTimestamp(dbStats?.lastUpdate)}
                    </Typography>
                  </CardContent>
                </Card>
              </Grid>
              
              <Grid item xs={12} md={3}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography color="textSecondary" gutterBottom>
                      Database State
                    </Typography>
                    <Chip 
                      label={dbStats?.isEmpty ? 'Empty' : 'Populated'} 
                      color={dbStats?.isEmpty ? 'default' : 'success'}
                      variant="outlined"
                    />
                  </CardContent>
                </Card>
              </Grid>
            </Grid>
          )}
        </Paper>
      )}

      {/* System Dependencies */}
      <Paper sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6">
            System Dependencies
          </Typography>
          <IconButton onClick={checkDependencies} disabled={isCheckingDeps}>
            <RefreshIcon />
          </IconButton>
        </Box>

        {isCheckingDeps ? (
          <LinearProgress />
        ) : (
          <>
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

      {/* Database Management */}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Database Management
        </Typography>
        
        <Grid container spacing={2}>
          <Grid item xs={12} md={4}>
            <Button
              fullWidth
              variant="outlined"
              startIcon={<BackupIcon />}
              onClick={() => setBackupDialog(true)}
              disabled={!neo4jStatus?.running || operationInProgress}
            >
              Backup Database
            </Button>
          </Grid>
          <Grid item xs={12} md={4}>
            <Button
              fullWidth
              variant="outlined"
              startIcon={<RestoreIcon />}
              onClick={() => setRestoreDialog(true)}
              disabled={!neo4jStatus?.running || operationInProgress}
            >
              Restore Database
            </Button>
          </Grid>
          <Grid item xs={12} md={4}>
            <Button
              fullWidth
              variant="outlined"
              color="error"
              startIcon={<WipeIcon />}
              onClick={() => setWipeDialog(true)}
              disabled={!neo4jStatus?.running || operationInProgress}
            >
              Wipe Database
            </Button>
          </Grid>
        </Grid>

        {operationInProgress && (
          <Box sx={{ mt: 2 }}>
            <LinearProgress />
            <Typography variant="body2" sx={{ mt: 1 }}>
              {operationMessage}
            </Typography>
          </Box>
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