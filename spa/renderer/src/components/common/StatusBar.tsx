import React, { useState, useEffect } from 'react';
import { Box, Typography, Chip, Tooltip } from '@mui/material';
import {
  Circle as CircleIcon,
  CheckCircle as ConnectedIcon,
  Error as DisconnectedIcon,
  PlayArrow as RunningIcon,
  Business as TenantIcon,
  Storage as DatabaseIcon,
  Api as BackendIcon,
  Psychology as McpIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useTenantName } from '../../hooks/useTenantName';
import { useApp } from '../../context/AppContext';

interface StatusBarProps {
  connectionStatus: 'connected' | 'disconnected';
}

interface ActiveProcess {
  id: string;
  pid?: number;
  command: string;
}

const StatusBar: React.FC<StatusBarProps> = ({ connectionStatus }) => {
  const { state } = useApp();
  const tenantName = useTenantName();
  const navigate = useNavigate();
  const [activeProcesses, setActiveProcesses] = useState<ActiveProcess[]>([]);
  const [neo4jStatus, setNeo4jStatus] = useState<'connected' | 'disconnected'>('disconnected');
  const [mcpStatus, setMcpStatus] = useState<'connected' | 'disconnected'>('disconnected');

  // Get active background operations from app state (only show ones with valid PIDs)
  const activeOperations = Array.from(state.backgroundOperations.values())
    .filter(op => {
      if (op.status !== 'running') return false;

      if (typeof op.pid !== 'number' || op.pid <= 0) {
        if (op.pid !== undefined) {
          console.warn(`Background operation ${op.id} has invalid PID:`, op.pid);
        }
        return false;
      }

      return true;
    });

  // Handle PID chip click - navigate to Logs tab with PID filter
  const handlePidClick = (pid: number) => {
    navigate(`/logs?pid=${pid}`);
  };

  // Fetch active processes and Neo4j status periodically
  useEffect(() => {
    const fetchActiveProcesses = async () => {
      try {
        const processes = await window.electronAPI.process.list();
        setActiveProcesses(processes || []);
      } catch (error) {
        console.error('Failed to fetch active processes:', error);
        setActiveProcesses([]);
      }
    };

    const checkNeo4jStatus = async () => {
      try {
        const response = await axios.get('http://localhost:3001/api/neo4j/status');
        setNeo4jStatus(response.data.running ? 'connected' : 'disconnected');
      } catch (error) {
        setNeo4jStatus('disconnected');
      }
    };

    const checkMcpStatus = async () => {
      try {
        const response = await axios.get('http://localhost:3001/api/mcp/status');
        setMcpStatus(response.data.running ? 'connected' : 'disconnected');
      } catch (error) {
        setMcpStatus('disconnected');
      }
    };

    fetchActiveProcesses();
    checkNeo4jStatus();
    checkMcpStatus();

    const interval = setInterval(() => {
      fetchActiveProcesses();
      checkNeo4jStatus();
      checkMcpStatus();
    }, 5000); // Update every 5 seconds

    return () => clearInterval(interval);
  }, []);

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        px: 2,
        py: 0.5,
        backgroundColor: 'background.paper',
        borderTop: 1,
        borderColor: 'divider',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Typography variant="caption" color="text.secondary">
          Azure Tenant Grapher v1.0.0
        </Typography>

        {/* Tenant Information */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <TenantIcon sx={{ fontSize: 16, color: 'text.secondary' }} />
          <Typography variant="caption" color="text.secondary">
            Tenant:
          </Typography>
          <Typography variant="caption" color="text.primary" fontWeight="medium">
            {tenantName}
          </Typography>
        </Box>

        {/* Active Operations */}
        {(activeOperations.length > 0 || activeProcesses.length > 0) && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            {/* Background Operations from App State */}
            {activeOperations.map((op) => (
              <Tooltip key={op.id} title={`${op.name} - Started: ${op.startTime.toLocaleTimeString()}`}>
                <Chip
                  size="small"
                  icon={<RunningIcon />}
                  label={op.type}
                  color="info"
                  variant="outlined"
                  onClick={op.pid ? () => handlePidClick(op.pid!) : undefined}
                  sx={{
                    fontSize: '0.7rem',
                    height: 20,
                    cursor: op.pid ? 'pointer' : 'default'
                  }}
                />
              </Tooltip>
            ))}

            {/* Active CLI Processes */}
            {activeProcesses
              .filter(process => {
                if (typeof process.pid !== 'number' || process.pid <= 0) {
                  if (process.pid !== undefined) {
                    console.warn(`CLI process ${process.id} has invalid PID:`, process.pid);
                  }
                  return false;
                }
                return true;
              })
              .map((process) => (
                <Tooltip key={process.id} title={`PID: ${process.pid} - Command: ${process.command} (Click to view logs)`}>
                  <Chip
                    size="small"
                    icon={<RunningIcon />}
                    label={`PID ${process.pid}`}
                    color="warning"
                    variant="outlined"
                    onClick={() => handlePidClick(process.pid!)}
                    sx={{
                      fontSize: '0.7rem',
                      height: 20,
                      cursor: 'pointer'
                    }}
                  />
                </Tooltip>
              ))}
          </Box>
        )}
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        {/* Backend Connection Status */}
        <Tooltip title="Backend server connection status">
          <Chip
            size="small"
            icon={<BackendIcon />}
            label={connectionStatus === 'connected' ? 'Backend' : 'Backend Offline'}
            color={connectionStatus === 'connected' ? 'success' : 'error'}
            variant="outlined"
          />
        </Tooltip>

        {/* Neo4j Database Status */}
        <Tooltip title="Neo4j database connection status">
          <Chip
            size="small"
            icon={<DatabaseIcon />}
            label={neo4jStatus === 'connected' ? 'Neo4j' : 'Neo4j Offline'}
            color={neo4jStatus === 'connected' ? 'success' : 'error'}
            variant="outlined"
          />
        </Tooltip>

        {/* MCP Server Status */}
        <Tooltip title="Model Context Protocol server status">
          <Chip
            size="small"
            icon={<McpIcon />}
            label={mcpStatus === 'connected' ? 'MCP' : 'MCP Offline'}
            color={mcpStatus === 'connected' ? 'success' : 'error'}
            variant="outlined"
          />
        </Tooltip>

        <Typography variant="caption" color="text.secondary">
          {new Date().toLocaleTimeString()}
        </Typography>
      </Box>
    </Box>
  );
};

export default StatusBar;
