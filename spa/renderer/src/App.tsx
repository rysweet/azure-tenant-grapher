import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import { Box, Container } from '@mui/material';
import axios from 'axios';
import Header from './components/common/Header';
import TabNavigation from './components/common/TabNavigation';
import StatusBar from './components/common/StatusBar';
import ErrorBoundary from './components/common/ErrorBoundary';
import StatusTab from './components/tabs/StatusTab';
import LogsTab from './components/tabs/LogsTab';
import BuildTab from './components/tabs/BuildTab';
import CLITab from './components/tabs/CLITab';
import GenerateSpecTab from './components/tabs/GenerateSpecTab';
import GenerateIaCTab from './components/tabs/GenerateIaCTab';
import CreateTenantTab from './components/tabs/CreateTenantTab';
import VisualizeTab from './components/tabs/VisualizeTab';
import AgentModeTab from './components/tabs/AgentModeTab';
import ThreatModelTab from './components/tabs/ThreatModelTab';
import DocsTab from './components/tabs/DocsTab';
import ConfigTab from './components/tabs/ConfigTab';
import { useApp } from './context/AppContext';

const App: React.FC = () => {
  const { state, dispatch } = useApp();
  const navigate = useNavigate();
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'disconnected'>('disconnected');
  const [dbPopulated, setDbPopulated] = useState<boolean | null>(null);
  const [initialCheckDone, setInitialCheckDone] = useState(false);
  
  // Force black toolbar on mount
  useEffect(() => {
    const style = document.createElement('style');
    style.innerHTML = `
      .MuiAppBar-root, 
      .MuiToolbar-root,
      header,
      div:first-child > div:first-child,
      div:first-child > div:nth-child(2) {
        background-color: #000000 !important;
        background-image: none !important;
      }
      /* Force tab navigation to be black */
      #root > div > div:nth-child(2) {
        background-color: #000000 !important;
      }
    `;
    document.head.appendChild(style);
    return () => {
      document.head.removeChild(style);
    };
  }, []);

  useEffect(() => {
    // Check backend connection and DB status
    checkConnection();
    checkDatabaseStatus();
    
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

  useEffect(() => {
    // Navigate to visualize tab if DB is populated (only on initial load)
    if (!initialCheckDone && dbPopulated === true) {
      setInitialCheckDone(true);
      navigate('/visualize');
      dispatch({ type: 'SET_ACTIVE_TAB', payload: 'visualize' });
    } else if (!initialCheckDone && dbPopulated === false) {
      setInitialCheckDone(true);
      navigate('/build');
      dispatch({ type: 'SET_ACTIVE_TAB', payload: 'build' });
    }
  }, [dbPopulated, navigate, dispatch, initialCheckDone]);

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

  const checkDatabaseStatus = async () => {
    try {
      const response = await axios.get('http://localhost:3001/api/graph/status');
      setDbPopulated(response.data.isPopulated);
    } catch (error) {
      console.error('Failed to check DB status:', error);
      setDbPopulated(false);
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <Header />
      <TabNavigation />
      
      <Box sx={{ flex: 1, overflow: 'auto', backgroundColor: '#f5f5f5' }}>
        <Container maxWidth={false} sx={{ py: 3, height: '100%' }}>
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<Navigate to="/status" replace />} />
              <Route path="/status" element={<StatusTab />} />
              <Route path="/logs" element={<LogsTab />} />
              <Route path="/build" element={<BuildTab />} />
              <Route path="/cli" element={<CLITab />} />
              <Route path="/visualize" element={<VisualizeTab />} />
              <Route path="/generate-spec" element={<GenerateSpecTab />} />
              <Route path="/generate-iac" element={<GenerateIaCTab />} />
              <Route path="/create-tenant" element={<CreateTenantTab />} />
              <Route path="/agent-mode" element={<AgentModeTab />} />
              <Route path="/threat-model" element={<ThreatModelTab />} />
              <Route path="/docs" element={<DocsTab />} />
              <Route path="/config" element={<ConfigTab />} />
            </Routes>
          </ErrorBoundary>
        </Container>
      </Box>
      
      <StatusBar connectionStatus={connectionStatus} />
    </Box>
  );
};

export default App;