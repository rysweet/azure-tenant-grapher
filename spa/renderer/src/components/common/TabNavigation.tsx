import React from 'react';
import {
  Box,
  Tabs,
  Tab,
  useTheme,
  useMediaQuery
} from '@mui/material';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Dashboard as StatusIcon,
  BugReport as LogsIcon,
  Search as ScanIcon,
  Visibility as VisualizeIcon,
  Description as SpecIcon,
  Code as CodeIcon,
  CloudUpload as DeployIcon,
  CheckCircle as ValidateIcon,
  Delete as DeleteIcon,
  AddCircle as CreateIcon,
  Psychology as AgentIcon,
  Security as ThreatIcon,
  Settings as ConfigIcon,
  Terminal as TerminalIcon,
  MenuBook as DocsIcon,
  ZoomOutMap as ScaleIcon,
} from '@mui/icons-material';

// All tabs in a simple flat array
const allTabs = [
  { label: 'Status', path: '/status', icon: <StatusIcon /> },
  { label: 'Scan', path: '/scan', icon: <ScanIcon /> },
  { label: 'Visualize', path: '/visualize', icon: <VisualizeIcon /> },
  { label: 'Export Spec', path: '/generate-spec', icon: <SpecIcon /> },
  { label: 'Generate IaC', path: '/generate-iac', icon: <CodeIcon /> },
  { label: 'Deploy', path: '/deploy', icon: <DeployIcon /> },
  { label: 'Validate', path: '/validate-deployment', icon: <ValidateIcon /> },
  { label: 'Undeploy', path: '/undeploy', icon: <DeleteIcon /> },
  { label: 'Create Tenant', path: '/create-tenant', icon: <CreateIcon /> },
  { label: 'Agent Mode', path: '/agent-mode', icon: <AgentIcon /> },
  { label: 'Threat Model', path: '/threat-model', icon: <ThreatIcon /> },
  { label: 'Scale Operations', path: '/scale-operations', icon: <ScaleIcon /> },
  { label: 'Docs', path: '/docs', icon: <DocsIcon /> },
  { label: 'Logs', path: '/logs', icon: <LogsIcon /> },
  { label: 'CLI', path: '/cli', icon: <TerminalIcon /> },
  { label: 'Config', path: '/config', icon: <ConfigIcon /> },
];

const TabNavigation: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  const isSmallScreen = useMediaQuery(theme.breakpoints.down('md'));

  const handleTabChange = (_: React.SyntheticEvent, newValue: string) => {
    navigate(newValue);
  };

  return (
    <Box sx={{
      backgroundColor: '#000000',  // Black background to match header
      px: isSmallScreen ? 1 : 2,
      py: isSmallScreen ? 0.5 : 1,
      overflow: 'hidden'
    }}>
      {/* Single row of tabs that wraps naturally */}
      <Tabs
        value={location.pathname}
        onChange={handleTabChange}
        variant="scrollable"
        scrollButtons="auto"
        sx={{
          minHeight: isSmallScreen ? 36 : 48,
          '& .MuiTabs-indicator': {
            backgroundColor: theme.palette.primary.main,
            height: 2,
          },
          '& .MuiTabs-flexContainer': {
            flexWrap: 'wrap',  // Allow tabs to wrap naturally
          },
          '& .MuiTab-root': {
            minHeight: isSmallScreen ? 36 : 48,
            minWidth: 'auto',
            fontSize: isSmallScreen ? '0.75rem' : '0.875rem',
            textTransform: 'none',
            color: '#969696',  // Grey text on black
            backgroundColor: 'transparent',
            border: 'none',
            px: isSmallScreen ? 1 : 1.5,
            py: isSmallScreen ? 0.5 : 0.75,
            '&.Mui-selected': {
              color: '#ffffff',  // White when selected
              backgroundColor: 'rgba(255, 255, 255, 0.1)',
            },
            '&:hover': {
              backgroundColor: 'rgba(255, 255, 255, 0.05)',
            },
            '& .MuiTab-iconWrapper': {
              marginRight: isSmallScreen ? 0.5 : 1,
              marginBottom: 0,
            }
          }
        }}
      >
        {allTabs.map((tab) => (
          <Tab
            key={tab.path}
            label={tab.label}
            value={tab.path}
            icon={tab.icon}
            iconPosition="start"
          />
        ))}
      </Tabs>
    </Box>
  );
};

export default TabNavigation;
