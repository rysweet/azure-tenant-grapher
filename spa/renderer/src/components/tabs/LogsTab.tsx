import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Box,
  Paper,
  Typography,
  Toolbar,
  IconButton,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  SelectChangeEvent,
  Chip,
  Tooltip,
  FormControlLabel,
  Switch,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import {
  Clear as ClearIcon,
  Search as SearchIcon,
  FilterList as FilterIcon,
  // VerticalAlignBottom as ScrollDownIcon, // REMOVED: scroll button disabled
  ExpandMore as ExpandMoreIcon,
  Download as DownloadIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useSearchParams } from 'react-router-dom';
// import Editor from '@monaco-editor/react'; // REMOVED: Monaco Editor replaced with simple <pre>
import { useApp } from '../../context/AppContext';
import { useWebSocketContext } from '../../context/WebSocketContext';
import { LogEntry as AppLogEntry, LogLevel as AppLogLevel } from '../../context/AppContext';
import {
  getLogs,
  clearLogs,
  createLogger
} from '../../utils/logger';
import { LogEntry as SystemLogEntry, LogLevel as SystemLogLevel } from '../../../../shared/logger';

// Unified LogLevel type
type LogLevel = AppLogLevel;

// Map SystemLogLevel to AppLogLevel
const mapSystemLogLevel = (level: SystemLogLevel): LogLevel => {
  switch (level) {
    case SystemLogLevel.DEBUG:
      return 'debug';
    case SystemLogLevel.INFO:
      return 'info';
    case SystemLogLevel.WARN:
      return 'warning';
    case SystemLogLevel.ERROR:
      return 'error';
    default:
      return 'info';
  }
};

// Convert SystemLogEntry to AppLogEntry
const convertSystemLogEntry = (entry: SystemLogEntry): AppLogEntry => ({
  id: entry.id,
  timestamp: new Date(entry.timestamp),
  level: mapSystemLogLevel(entry.level),
  source: entry.component || 'System',
  message: entry.message,
  data: entry.metadata
});

// Log level colors for dark theme
const logLevelColors: Record<LogLevel, string> = {
  debug: '#6B7280', // Gray
  info: '#3B82F6',  // Blue
  warning: '#F59E0B', // Amber
  error: '#EF4444',   // Red
};

// Log level priorities for sorting
const logLevelPriority: Record<LogLevel, number> = {
  debug: 1,
  info: 2,
  warning: 3,
  error: 4,
};

const LogsTab: React.FC = () => {
  const { state, dispatch } = useApp();
  const [searchParams, setSearchParams] = useSearchParams();
  const [filterExpanded, setFilterExpanded] = useState(false);
  const [selectedLevels, setSelectedLevels] = useState<LogLevel[]>(['debug', 'info', 'warning', 'error']);
  const [searchTerm, setSearchTerm] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const [sortBy, setSortBy] = useState<'timestamp' | 'level' | 'source'>('timestamp');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [pidFilter, setPidFilter] = useState<string>('');

  // const editorRef = useRef<any>(null); // REMOVED: Monaco Editor no longer used
  const containerRef = useRef<HTMLDivElement>(null);

  // System logs from WebSocket
  const [systemLogs, setSystemLogs] = useState<AppLogEntry[]>([]);
  const [logWebSocketConnected, setLogWebSocketConnected] = useState(false);

  // Initialize WebSocket connection and logger - use shared context
  const webSocket = useWebSocketContext();
  const logger = useMemo(() => createLogger('LogsTab'), []);

  // Track active processes that we're subscribing to
  const [activeProcesses, setActiveProcesses] = useState<Set<string>>(new Set());

  // Fetch logs from memory transport periodically
  useEffect(() => {
    const updateSystemLogs = () => {
      const logs = getLogs();
      const convertedLogs = logs.map(convertSystemLogEntry);
      setSystemLogs(convertedLogs);
    };

    // Initial fetch
    updateSystemLogs();

    // DISABLED: Polling was causing performance issues
    // Only update on manual refresh now
    // const interval = setInterval(updateSystemLogs, 2000);

    // For now, assume WebSocket is connected if we have the logger
    setLogWebSocketConnected(true);

    return () => {
      // clearInterval(interval);
    };
  }, []);

  // Convert WebSocket process outputs to LogEntry format
  const processLogs = useMemo(() => {
    const logs: AppLogEntry[] = [];
    let counter = 0;

    webSocket.outputs.forEach((outputs, processId) => {
      outputs.forEach(output => {
        // Handle both single line and array of lines
        const lines = Array.isArray(output.data) ? output.data : [output.data];
        lines.forEach((line, index) => {
          if (line && line.trim()) {
            logs.push({
              id: `${processId}-${output.timestamp}-${index}-${counter++}`,
              timestamp: new Date(output.timestamp),
              level: output.type === 'stderr' ? 'error' : 'info',
              source: `Process-${processId.slice(0, 8)}`,
              message: line.trim()
            });
          }
        });
      });
    });

    return logs;
  }, [webSocket.outputs]);

  // Combine all log sources: state logs, system logs from WebSocket, and process logs
  // Limit total logs to prevent performance issues
  const MAX_LOGS = 5000;
  const allLogs = useMemo(() => {
    const combined = [...state.logs, ...systemLogs, ...processLogs];
    // Keep only the most recent logs if we exceed the limit
    if (combined.length > MAX_LOGS) {
      // Sort by timestamp descending and take the most recent
      combined.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime());
      return combined.slice(0, MAX_LOGS);
    }
    return combined;
  }, [state.logs, systemLogs, processLogs]);

  // Handle PID parameter from URL
  useEffect(() => {
    const pid = searchParams.get('pid');
    if (pid) {
      setPidFilter(pid);
      setFilterExpanded(true);
      // Clear the URL parameter after setting the filter
      const newSearchParams = new URLSearchParams(searchParams);
      newSearchParams.delete('pid');
      setSearchParams(newSearchParams, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  // Filter and format logs for display
  const filteredLogs = useMemo(() => {
    let filtered = allLogs.filter(log => {
      const levelMatch = selectedLevels.includes(log.level);
      const searchMatch = searchTerm === '' ||
        log.message.toLowerCase().includes(searchTerm.toLowerCase()) ||
        log.source.toLowerCase().includes(searchTerm.toLowerCase());
      const pidMatch = pidFilter === '' ||
        log.message.includes(`PID ${pidFilter}`) ||
        log.source.includes(`PID ${pidFilter}`) ||
        (log.data && String(log.data).includes(`PID ${pidFilter}`)) ||
        (log.data && typeof log.data === 'object' && 'pid' in log.data && String(log.data.pid) === pidFilter);
      return levelMatch && searchMatch && pidMatch;
    });

    // Sort logs
    filtered.sort((a, b) => {
      let comparison = 0;
      switch (sortBy) {
        case 'timestamp':
          comparison = a.timestamp.getTime() - b.timestamp.getTime();
          break;
        case 'level':
          comparison = logLevelPriority[a.level] - logLevelPriority[b.level];
          break;
        case 'source':
          comparison = a.source.localeCompare(b.source);
          break;
      }
      return sortOrder === 'asc' ? comparison : -comparison;
    });

    // LIMIT to last 100 logs for performance
    const MAX_DISPLAY_LOGS = 100;
    if (filtered.length > MAX_DISPLAY_LOGS) {
      filtered = filtered.slice(-MAX_DISPLAY_LOGS);
    }

    return filtered;
  }, [allLogs, selectedLevels, searchTerm, pidFilter, sortBy, sortOrder]);

  // Format logs as text - simplified for performance
  const formattedLogsText = useMemo(() => {
    const formattedText = filteredLogs.map(log => {
      const timestamp = log.timestamp.toISOString().replace('T', ' ').replace('Z', '');
      const level = log.level.toUpperCase().padEnd(7);
      const source = log.source.padEnd(12);
      return `[${timestamp}] ${level} ${source} ${log.message}`;
    }).join('\n');

    return formattedText;
  }, [filteredLogs]);

  // Handle level filter changes
  const handleLevelChange = (event: SelectChangeEvent<LogLevel[]>) => {
    const value = event.target.value;
    const levels = typeof value === 'string' ? value.split(',') as LogLevel[] : value as LogLevel[];
    setSelectedLevels(levels);
  };

  // Clear all logs
  const handleClearLogs = () => {
    dispatch({ type: 'CLEAR_LOGS' });
    clearLogs(); // Clear memory transport
    setSystemLogs([]);
    // Also clear WebSocket outputs
    activeProcesses.forEach(processId => {
      webSocket.clearProcessOutput(processId);
    });
    logger.info('Cleared all logs');
  };

  // Export logs
  const handleExportLogs = () => {
    const blob = new Blob([formattedLogsText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `azure-tenant-grapher-logs-${new Date().toISOString().split('T')[0]}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // Scroll to bottom when new logs arrive (if auto-scroll is enabled)
  // DISABLED: editorRef no longer exists after Monaco Editor removal
  /*
  useEffect(() => {
    if (autoScroll && editorRef.current) {
      const editor = editorRef.current;
      const model = editor.getModel();
      if (model) {
        const lineCount = model.getLineCount();
        editor.setPosition({ lineNumber: lineCount, column: 1 });
        editor.revealLine(lineCount);
      }
    }
  }, [filteredLogs, autoScroll]);
  */

  // Force scroll to bottom
  // DISABLED: editorRef no longer exists after Monaco Editor removal
  /*
  const scrollToBottom = () => {
    if (editorRef.current) {
      const editor = editorRef.current;
      const model = editor.getModel();
      if (model) {
        const lineCount = model.getLineCount();
        editor.setPosition({ lineNumber: lineCount, column: 1 });
        editor.revealLine(lineCount);
      }
    }
  };
  */

  // Monitor running processes and auto-subscribe to their logs
  useEffect(() => {
    const checkActiveProcesses = async () => {
      try {
        const processes = await window.electronAPI?.process?.list?.() || [];
        const runningProcessIds = new Set(
          processes
            .filter(p => p.status === 'running')
            .map(p => p.id)
        );

        // Use functional update to avoid dependency on activeProcesses
        setActiveProcesses(prevActiveProcesses => {
          // Subscribe to new processes
          runningProcessIds.forEach(processId => {
            if (!prevActiveProcesses.has(processId)) {
              webSocket.subscribeToProcess(processId);
              logger.debug(`Subscribed to process logs: ${processId}`);
            }
          });

          // Unsubscribe from completed processes
          prevActiveProcesses.forEach(processId => {
            if (!runningProcessIds.has(processId)) {
              webSocket.unsubscribeFromProcess(processId);
              logger.debug(`Unsubscribed from process logs: ${processId}`);
            }
          });

          return runningProcessIds;
        });
      } catch (error) {
        logger.error('Failed to check active processes', { error });
      }
    };

    // Check immediately and then every 5 seconds
    checkActiveProcesses();
    const interval = setInterval(checkActiveProcesses, 5000);

    return () => clearInterval(interval);
  }, [webSocket]); // FIXED: Removed activeProcesses from deps to prevent infinite loop

  // Log WebSocket connection status changes
  useEffect(() => {
    if (webSocket.isConnected) {
      logger.info('Connected to process WebSocket server');
    } else {
      logger.warn('Disconnected from process WebSocket server');
    }
  }, [webSocket.isConnected, logger]);

  useEffect(() => {
    if (logWebSocketConnected) {
      logger.info('Connected to log stream WebSocket');
    } else {
      logger.warn('Disconnected from log stream WebSocket');
    }
  }, [logWebSocketConnected, logger]);

  // Add some test logs for demonstration
  const addTestLogs = () => {
    // Use the new logger to generate real system logs
    logger.info('WebSocket connected to backend server');
    logger.debug('GET /api/neo4j/status - 200 OK', { responseTime: '45ms' });
    logger.warn('Resource limit reached, some resources may be skipped');
    logger.error('Failed to create relationship: Invalid node ID', { nodeId: 'invalid-123', error: 'Node not found' });
    logger.info('Discovered 1,245 Azure resources across 3 subscriptions');
    logger.debug('Query executed successfully', { query: 'MATCH (n) RETURN count(n)', duration: '12ms' });

    // Also add some logs to the state for testing
    const testLogs = [
      { level: 'info' as LogLevel, source: 'Process-abcd1234', message: 'Starting Azure resource discovery...' },
      { level: 'info' as LogLevel, source: 'Process-abcd1234', message: 'Authenticating with Azure...' },
      { level: 'info' as LogLevel, source: 'Process-abcd1234', message: 'Discovered 15 resources in resource group "test-rg"' },
      { level: 'debug' as LogLevel, source: 'Process-abcd1234', message: 'Processing virtual machines...' },
      { level: 'info' as LogLevel, source: 'Process-abcd1234', message: 'Found 3 VMs, 2 storage accounts, 1 network security group' },
    ];

    testLogs.forEach(log => {
      dispatch({
        type: 'ADD_STRUCTURED_LOG',
        payload: log,
      });
    });

    logger.info(`Added test logs for demonstration`);

    // Manually refresh system logs after adding test logs
    setTimeout(() => {
      const logs = getLogs();
      const convertedLogs = logs.map(convertSystemLogEntry);
      setSystemLogs(convertedLogs);
    }, 100);
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Paper sx={{ mb: 1 }}>
        <Toolbar variant="dense" sx={{ minHeight: 48 }}>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            System Logs
          </Typography>

          {/* Log Count Badge */}
          <Chip
            label={`${filteredLogs.length} / ${allLogs.length} logs`}
            size="small"
            variant="outlined"
            sx={{ mr: 2 }}
          />

          {/* WebSocket Status Badges */}
          <Chip
            label={`Processes: ${webSocket.isConnected ? 'Live' : 'Offline'}`}
            size="small"
            variant="outlined"
            color={webSocket.isConnected ? 'success' : 'error'}
            sx={{ mr: 1 }}
          />
          <Chip
            label={`Logs: ${logWebSocketConnected ? 'Live' : 'Offline'}`}
            size="small"
            variant="outlined"
            color={logWebSocketConnected ? 'success' : 'error'}
            sx={{ mr: 2 }}
          />

          {/* Active Processes Badge */}
          {activeProcesses.size > 0 && (
            <Chip
              label={`${activeProcesses.size} process${activeProcesses.size === 1 ? '' : 'es'}`}
              size="small"
              variant="outlined"
              color="info"
              sx={{ mr: 2 }}
            />
          )}

          {/* Auto-scroll toggle */}
          <FormControlLabel
            control={
              <Switch
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
                size="small"
              />
            }
            label="Auto-scroll"
            sx={{ mr: 2 }}
          />

          {/* Action buttons */}
          {/* DISABLED: scrollToBottom function removed with Monaco Editor
          <Tooltip title="Scroll to bottom">
            <IconButton onClick={scrollToBottom} size="small">
              <ScrollDownIcon />
            </IconButton>
          </Tooltip>
          */}

          <Tooltip title="Export logs">
            <IconButton onClick={handleExportLogs} size="small" disabled={allLogs.length === 0}>
              <DownloadIcon />
            </IconButton>
          </Tooltip>

          <Tooltip title="Add test logs (system + process)">
            <IconButton onClick={addTestLogs} size="small">
              <RefreshIcon />
            </IconButton>
          </Tooltip>

          <Tooltip title="Clear all logs">
            <IconButton onClick={handleClearLogs} size="small" disabled={allLogs.length === 0}>
              <ClearIcon />
            </IconButton>
          </Tooltip>
        </Toolbar>
      </Paper>

      {/* Filters */}
      <Accordion
        expanded={filterExpanded}
        onChange={(_, expanded) => setFilterExpanded(expanded)}
        sx={{ mb: 1 }}
      >
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <FilterIcon sx={{ mr: 1 }} />
          <Typography>Filters & Settings</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
            {/* Search */}
            <TextField
              label="Search logs"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              size="small"
              InputProps={{
                startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />,
              }}
              sx={{ minWidth: 200 }}
            />

            {/* PID Filter */}
            <TextField
              label="Filter by PID"
              value={pidFilter}
              onChange={(e) => setPidFilter(e.target.value)}
              size="small"
              placeholder="e.g., 1234"
              sx={{ minWidth: 150 }}
            />

            {/* Level filter */}
            <FormControl size="small" sx={{ minWidth: 180 }}>
              <InputLabel>Log Levels</InputLabel>
              <Select
                multiple
                value={selectedLevels}
                onChange={handleLevelChange}
                renderValue={(selected) => (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {selected.map((value) => (
                      <Chip
                        key={value}
                        label={value}
                        size="small"
                        sx={{
                          backgroundColor: logLevelColors[value],
                          color: 'white',
                          fontSize: '0.7rem',
                        }}
                      />
                    ))}
                  </Box>
                )}
              >
                {(['debug', 'info', 'warning', 'error'] as LogLevel[]).map((level) => (
                  <MenuItem key={level} value={level}>
                    <Chip
                      label={level}
                      size="small"
                      sx={{
                        backgroundColor: logLevelColors[level],
                        color: 'white',
                        mr: 1,
                      }}
                    />
                    {level}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {/* Sort options */}
            <FormControl size="small" sx={{ minWidth: 120 }}>
              <InputLabel>Sort by</InputLabel>
              <Select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as 'timestamp' | 'level' | 'source')}
              >
                <MenuItem value="timestamp">Time</MenuItem>
                <MenuItem value="level">Level</MenuItem>
                <MenuItem value="source">Source</MenuItem>
              </Select>
            </FormControl>

            <FormControl size="small" sx={{ minWidth: 100 }}>
              <InputLabel>Order</InputLabel>
              <Select
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value as 'asc' | 'desc')}
              >
                <MenuItem value="desc">Latest</MenuItem>
                <MenuItem value="asc">Oldest</MenuItem>
              </Select>
            </FormControl>
          </Box>
        </AccordionDetails>
      </Accordion>

      {/* Logs Display */}
      <Paper sx={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {allLogs.length === 0 ? (
          <Box
            sx={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'text.secondary',
            }}
          >
            <Typography variant="body1" gutterBottom>
              No logs available yet.
            </Typography>
            <Typography variant="body2">
              System logs and process output will appear here in real-time.
            </Typography>
            {(!webSocket.isConnected || !logWebSocketConnected) && (
              <Typography variant="body2" color="warning.main" sx={{ mt: 1 }}>
                {!webSocket.isConnected && !logWebSocketConnected
                  ? 'WebSocket connections disconnected - logs may not appear.'
                  : !webSocket.isConnected
                  ? 'Process WebSocket disconnected - process output may not appear.'
                  : 'Log WebSocket disconnected - system logs may not appear.'}
              </Typography>
            )}
          </Box>
        ) : filteredLogs.length === 0 ? (
          <Box
            sx={{
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'text.secondary',
            }}
          >
            <Typography variant="body1" gutterBottom>
              No logs match current filters.
            </Typography>
            <Typography variant="body2">
              {allLogs.length} log{allLogs.length === 1 ? '' : 's'} available. Adjust filters to see them.
            </Typography>
          </Box>
        ) : (
          <Box ref={containerRef} sx={{ flex: 1, overflow: 'auto', backgroundColor: '#1e1e1e', p: 2 }}>
            <pre style={{
              margin: 0,
              color: '#d4d4d4',
              fontFamily: 'Monaco, Menlo, "Ubuntu Mono", monospace',
              fontSize: '13px',
              lineHeight: '1.5',
              whiteSpace: 'pre-wrap',
              wordWrap: 'break-word'
            }}>
              {formattedLogsText || 'No logs to display'}
            </pre>
          </Box>
        )}
      </Paper>
    </Box>
  );
};

export default LogsTab;
