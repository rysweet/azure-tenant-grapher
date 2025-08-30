import React, { useEffect, useRef } from 'react';
import { Box, Paper, Typography, IconButton } from '@mui/material';
import { Clear as ClearIcon, Download as DownloadIcon } from '@mui/icons-material';

interface LogViewerProps {
  logs: string[];
  onClear?: () => void;
  height?: string | number;
}

const LogViewer: React.FC<LogViewerProps> = ({ logs, onClear, height = 300 }) => {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Auto-scroll to bottom when new logs arrive
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  const handleDownload = () => {
    const content = logs.join('\n');
    const blob = new Blob([content], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `logs_${new Date().getTime()}.txt`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  const getLogColor = (log: string): string => {
    if (log.includes('ERROR') || log.includes('Failed')) return 'log-error';
    if (log.includes('WARNING') || log.includes('Warn')) return 'log-warning';
    if (log.includes('SUCCESS') || log.includes('Complete')) return 'log-success';
    if (log.includes('INFO')) return 'log-info';
    return '';
  };

  return (
    <Paper sx={{ p: 1, height, display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
        <Typography variant="subtitle2">Output Logs</Typography>
        <Box>
          <IconButton size="small" onClick={handleDownload} title="Download logs">
            <DownloadIcon fontSize="small" />
          </IconButton>
          {onClear && (
            <IconButton size="small" onClick={onClear} title="Clear logs">
              <ClearIcon fontSize="small" />
            </IconButton>
          )}
        </Box>
      </Box>
      
      <Box
        ref={scrollRef}
        className="log-viewer"
        sx={{
          flex: 1,
          overflow: 'auto',
          fontFamily: 'monospace',
          fontSize: '0.875rem',
          backgroundColor: 'background.default',
          borderRadius: 1,
        }}
      >
        {logs.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ p: 1 }}>
            No logs yet...
          </Typography>
        ) : (
          logs.map((log, index) => (
            <div key={index} className={getLogColor(log)}>
              {log}
            </div>
          ))
        )}
      </Box>
    </Paper>
  );
};

export default LogViewer;