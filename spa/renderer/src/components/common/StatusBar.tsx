import React from 'react';
import { Box, Typography, Chip } from '@mui/material';
import {
  Circle as CircleIcon,
  CheckCircle as ConnectedIcon,
  Error as DisconnectedIcon,
} from '@mui/icons-material';

interface StatusBarProps {
  connectionStatus: 'connected' | 'disconnected';
}

const StatusBar: React.FC<StatusBarProps> = ({ connectionStatus }) => {
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
      </Box>
      
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <Chip
          size="small"
          icon={connectionStatus === 'connected' ? <ConnectedIcon /> : <DisconnectedIcon />}
          label={connectionStatus === 'connected' ? 'Connected' : 'Disconnected'}
          color={connectionStatus === 'connected' ? 'success' : 'error'}
          variant="outlined"
        />
        
        <Typography variant="caption" color="text.secondary">
          {new Date().toLocaleTimeString()}
        </Typography>
      </Box>
    </Box>
  );
};

export default StatusBar;