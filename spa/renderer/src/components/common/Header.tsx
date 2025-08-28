import React from 'react';
import { AppBar, Toolbar, Typography, IconButton, Box } from '@mui/material';
import {
  Minimize as MinimizeIcon,
  Crop54 as MaximizeIcon,
  Close as CloseIcon,
} from '@mui/icons-material';

const Header: React.FC = () => {
  const handleMinimize = () => {
    window.electronAPI.window.minimize();
  };

  const handleMaximize = () => {
    window.electronAPI.window.maximize();
  };

  const handleClose = () => {
    window.electronAPI.window.close();
  };

  return (
    <AppBar position="static" sx={{ WebkitAppRegion: 'drag', userSelect: 'none' }}>
      <Toolbar variant="dense">
        <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
          Azure Tenant Grapher
        </Typography>
        
        <Box sx={{ WebkitAppRegion: 'no-drag', display: 'flex', gap: 1 }}>
          <IconButton size="small" onClick={handleMinimize} color="inherit">
            <MinimizeIcon fontSize="small" />
          </IconButton>
          <IconButton size="small" onClick={handleMaximize} color="inherit">
            <MaximizeIcon fontSize="small" />
          </IconButton>
          <IconButton size="small" onClick={handleClose} color="inherit">
            <CloseIcon fontSize="small" />
          </IconButton>
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default Header;