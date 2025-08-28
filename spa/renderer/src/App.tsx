import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Box, Container } from '@mui/material';
import Header from './components/common/Header';
import TabNavigation from './components/common/TabNavigation';
import StatusBar from './components/common/StatusBar';
import BuildTab from './components/tabs/BuildTab';
import GenerateSpecTab from './components/tabs/GenerateSpecTab';
import GenerateIaCTab from './components/tabs/GenerateIaCTab';
import CreateTenantTab from './components/tabs/CreateTenantTab';
import VisualizeTab from './components/tabs/VisualizeTab';
import AgentModeTab from './components/tabs/AgentModeTab';
import ThreatModelTab from './components/tabs/ThreatModelTab';
import ConfigTab from './components/tabs/ConfigTab';
import { useApp } from './context/AppContext';

const App: React.FC = () => {
  const { state, dispatch } = useApp();
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'disconnected'>('disconnected');

  useEffect(() => {
    // Check backend connection
    checkConnection();
    
    // Listen for menu events
    window.electronAPI.on('menu:navigate', (tab: string) => {
      dispatch({ type: 'SET_ACTIVE_TAB', payload: tab });
    });

    window.electronAPI.on('menu:new-build', () => {
      dispatch({ type: 'SET_ACTIVE_TAB', payload: 'build' });
    });

    return () => {
      // Cleanup listeners
    };
  }, [dispatch]);

  const checkConnection = async () => {
    try {
      const platform = await window.electronAPI.system.platform();
      if (platform) {
        setConnectionStatus('connected');
      }
    } catch (error) {
      setConnectionStatus('disconnected');
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <Header />
      <TabNavigation />
      
      <Box sx={{ flex: 1, overflow: 'auto', backgroundColor: '#f5f5f5' }}>
        <Container maxWidth={false} sx={{ py: 3, height: '100%' }}>
          <Routes>
            <Route path="/" element={<Navigate to="/build" replace />} />
            <Route path="/build" element={<BuildTab />} />
            <Route path="/generate-spec" element={<GenerateSpecTab />} />
            <Route path="/generate-iac" element={<GenerateIaCTab />} />
            <Route path="/create-tenant" element={<CreateTenantTab />} />
            <Route path="/visualize" element={<VisualizeTab />} />
            <Route path="/agent-mode" element={<AgentModeTab />} />
            <Route path="/threat-model" element={<ThreatModelTab />} />
            <Route path="/config" element={<ConfigTab />} />
          </Routes>
        </Container>
      </Box>
      
      <StatusBar connectionStatus={connectionStatus} />
    </Box>
  );
};

export default App;