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
  Button,
  Tooltip,
  FormControlLabel,
  Switch,
  Divider,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material';
import {
  Clear as ClearIcon,
  Search as SearchIcon,
  FilterList as FilterIcon,
  VerticalAlignBottom as ScrollDownIcon,
  ExpandMore as ExpandMoreIcon,
  Download as DownloadIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import { useSearchParams } from 'react-router-dom';
import Editor from '@monaco-editor/react';
import { useApp } from '../../context/AppContext';
import { LogEntry, LogLevel } from '../../context/AppContext';
import { useWebSocket } from '../../hooks/useWebSocket';
import { useLogger } from '../../hooks/useLogger';

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
  
  const editorRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const processOutputRef = useRef<Map<string, string[]>>(new Map());
  
  // Initialize WebSocket connection and logger
  const webSocket = useWebSocket();
  const logger = useLogger('LogsTab');
  
  // Track active processes that we're subscribing to
  const [activeProcesses, setActiveProcesses] = useState<Set<string>>(new Set());

  // Convert WebSocket process outputs to LogEntry format
  const processLogs = useMemo(() => {
    const logs: LogEntry[] = [];
    
    webSocket.outputs.forEach((outputs, processId) => {
      outputs.forEach(output => {
        // Handle both single line and array of lines
        const lines = Array.isArray(output.data) ? output.data : [output.data];
        lines.forEach((line, index) => {
          if (line && line.trim()) {
            logs.push({
              id: `${processId}-${output.timestamp}-${index}-${Math.random()}`,
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

  // Combine system logs and process logs
  const allLogs = useMemo(() => {
    return [...state.logs, ...processLogs];
  }, [state.logs, processLogs]);

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

    return filtered;
  }, [allLogs, selectedLevels, searchTerm, pidFilter, sortBy, sortOrder]);

  // Format logs as text for Monaco editor
  const formattedLogsText = useMemo(() => {
    const formattedText = filteredLogs.map(log => {
      const timestamp = log.timestamp.toISOString().replace('T', ' ').replace('Z', '');
      const level = log.level.toUpperCase().padEnd(7);
      const source = log.source.padEnd(12);
      let logLine = `[${timestamp}] ${level} ${source} ${log.message}`;
      
      // Add structured data if present
      if (log.data) {
        try {
          const dataStr = typeof log.data === 'string' ? log.data : JSON.stringify(log.data, null, 2);
          logLine += `\n    ${dataStr.replace(/\n/g, '\n    ')}`;
        } catch (e) {
          logLine += `\n    [Data: ${String(log.data)}]`;
        }
      }
      
      return logLine;
    }).join('\n');
    
    // Optional debug logging (disabled in production)
    if (process.env.NODE_ENV === 'development') {
      console.debug('LogsTab: Formatting logs', {
        totalLogs: allLogs.length,
        filteredLogs: filteredLogs.length,
        processLogs: processLogs.length,
        systemLogs: state.logs.length,
        webSocketOutputs: webSocket.outputs.size,
        formattedTextLength: formattedText.length,
      });
    }
    
    return formattedText;
  }, [filteredLogs, allLogs.length, processLogs.length, state.logs.length, webSocket.outputs.size]);

  // Handle level filter changes
  const handleLevelChange = (event: SelectChangeEvent<LogLevel[]>) => {
    const value = event.target.value;
    const levels = typeof value === 'string' ? value.split(',') as LogLevel[] : value as LogLevel[];
    setSelectedLevels(levels);
  };

  // Clear all logs
  const handleClearLogs = () => {
    dispatch({ type: 'CLEAR_LOGS' });
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

  // Force scroll to bottom
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

  // Monitor running processes and auto-subscribe to their logs
  useEffect(() => {
    const checkActiveProcesses = async () => {
      try {
        const processes = await window.electronAPI.process.list();
        const runningProcessIds = new Set(
          processes
            .filter(p => p.status === 'running')
            .map(p => p.id)
        );
        
        // Subscribe to new processes
        runningProcessIds.forEach(processId => {
          if (!activeProcesses.has(processId)) {
            webSocket.subscribeToProcess(processId);
            logger.debug(`Subscribed to process logs: ${processId}`);
          }
        });
        
        // Unsubscribe from completed processes
        activeProcesses.forEach(processId => {
          if (!runningProcessIds.has(processId)) {
            webSocket.unsubscribeFromProcess(processId);
            logger.debug(`Unsubscribed from process logs: ${processId}`);
          }
        });
        
        setActiveProcesses(runningProcessIds);
      } catch (error) {
        logger.error('Failed to check active processes', { error });
      }
    };
    
    // Check immediately and then every 5 seconds
    checkActiveProcesses();
    const interval = setInterval(checkActiveProcesses, 5000);
    
    return () => clearInterval(interval);
  }, [activeProcesses, webSocket]); // Remove logger from deps to prevent re-runs

  // Log WebSocket connection status (only when it changes)
  useEffect(() => {
    if (webSocket.isConnected) {
      logger.info('Connected to backend WebSocket server');
    } else {
      logger.warning('Disconnected from backend WebSocket server');
    }
  }, [webSocket.isConnected]); // Remove logger from deps to prevent infinite loop

  // Add some test logs for demonstration
  const addTestLogs = () => {
    const testLogs = [
      { level: 'info' as LogLevel, source: 'WebSocket', message: 'Connected to backend server' },
      { level: 'debug' as LogLevel, source: 'API', message: 'GET /api/neo4j/status - 200 OK', data: { responseTime: '45ms' } },
      { level: 'warning' as LogLevel, source: 'Build', message: 'Resource limit reached, some resources may be skipped' },
      { level: 'error' as LogLevel, source: 'Graph', message: 'Failed to create relationship: Invalid node ID', data: { nodeId: 'invalid-123', error: 'Node not found' } },
      { level: 'info' as LogLevel, source: 'Build', message: 'Discovered 1,245 Azure resources across 3 subscriptions' },
      { level: 'debug' as LogLevel, source: 'Neo4j', message: 'Query executed successfully', data: { query: 'MATCH (n) RETURN count(n)', duration: '12ms' } },
    ];

    testLogs.forEach(log => {
      dispatch({
        type: 'ADD_STRUCTURED_LOG',
        payload: log,
      });
    });
    
    // Also add some process-like logs directly to test the formatting
    const processLogs = [
      { level: 'info' as LogLevel, source: 'Process-abcd1234', message: 'Starting Azure resource discovery...' },
      { level: 'info' as LogLevel, source: 'Process-abcd1234', message: 'Authenticating with Azure...' },
      { level: 'info' as LogLevel, source: 'Process-abcd1234', message: 'Discovered 15 resources in resource group "test-rg"' },
      { level: 'debug' as LogLevel, source: 'Process-abcd1234', message: 'Processing virtual machines...' },
      { level: 'info' as LogLevel, source: 'Process-abcd1234', message: 'Found 3 VMs, 2 storage accounts, 1 network security group' },
    ];
    
    processLogs.forEach(log => {
      dispatch({
        type: 'ADD_STRUCTURED_LOG',
        payload: log,
      });
    });
    
    logger.info(`Added ${testLogs.length} test system logs and simulated process output`);
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
          
          {/* WebSocket Status Badge */}
          <Chip
            label={webSocket.isConnected ? 'Live' : 'Offline'}
            size="small"
            variant="outlined"
            color={webSocket.isConnected ? 'success' : 'error'}
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
          <Tooltip title="Scroll to bottom">
            <IconButton onClick={scrollToBottom} size="small">
              <ScrollDownIcon />
            </IconButton>
          </Tooltip>
          
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
            {!webSocket.isConnected && (
              <Typography variant="body2" color="warning.main" sx={{ mt: 1 }}>
                WebSocket disconnected - some logs may not appear.
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
          <Box ref={containerRef} sx={{ flex: 1 }}>
            <Editor
              height="100%"
              defaultLanguage="plaintext"
              value={formattedLogsText}
              loading=""
              onMount={(editor) => {
                editorRef.current = editor;
                // Scroll to bottom on mount if auto-scroll is enabled
                if (autoScroll) {
                  setTimeout(scrollToBottom, 100);
                }
              }}
              options={{
                readOnly: true,
                minimap: { enabled: false },
                scrollBeyondLastLine: false,
                wordWrap: 'on',
                lineNumbers: 'on',
                glyphMargin: false,
                folding: false,
                lineDecorationsWidth: 0,
                lineNumbersMinChars: 4,
                renderLineHighlight: 'none',
                selectionHighlight: false,
                occurrencesHighlight: false,
                overviewRulerBorder: false,
                hideCursorInOverviewRuler: true,
                scrollbar: {
                  vertical: 'visible',
                  horizontal: 'visible',
                  verticalScrollbarSize: 12,
                  horizontalScrollbarSize: 12,
                },
                fontSize: 13,
                fontFamily: 'Monaco, Menlo, "Ubuntu Mono", monospace',
                theme: state.theme === 'dark' ? 'vs-dark' : 'vs-light',
              }}
              theme={state.theme === 'dark' ? 'vs-dark' : 'vs-light'}
            />
          </Box>
        )}
      </Paper>
    </Box>
  );
};

export default LogsTab;