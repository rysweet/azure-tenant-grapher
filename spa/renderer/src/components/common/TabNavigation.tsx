import React from 'react';
import { Tabs, Tab, Box } from '@mui/material';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Build as BuildIcon,
  Description as SpecIcon,
  Code as CodeIcon,
  AddCircle as CreateIcon,
  Visibility as VisualizeIcon,
  Psychology as AgentIcon,
  Security as ThreatIcon,
  Settings as ConfigIcon,
} from '@mui/icons-material';

const tabs = [
  { label: 'Build', path: '/build', icon: <BuildIcon /> },
  { label: 'Generate Spec', path: '/generate-spec', icon: <SpecIcon /> },
  { label: 'Generate IaC', path: '/generate-iac', icon: <CodeIcon /> },
  { label: 'Create Tenant', path: '/create-tenant', icon: <CreateIcon /> },
  { label: 'Visualize', path: '/visualize', icon: <VisualizeIcon /> },
  { label: 'Agent Mode', path: '/agent-mode', icon: <AgentIcon /> },
  { label: 'Threat Model', path: '/threat-model', icon: <ThreatIcon /> },
  { label: 'Config', path: '/config', icon: <ConfigIcon /> },
];

const TabNavigation: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const currentTab = tabs.findIndex(tab => tab.path === location.pathname);

  const handleChange = (_event: React.SyntheticEvent, newValue: number) => {
    navigate(tabs[newValue].path);
  };

  return (
    <Box sx={{ borderBottom: 1, borderColor: 'divider', backgroundColor: 'background.paper' }}>
      <Tabs
        value={currentTab >= 0 ? currentTab : 0}
        onChange={handleChange}
        variant="scrollable"
        scrollButtons="auto"
      >
        {tabs.map((tab) => (
          <Tab
            key={tab.path}
            label={tab.label}
            icon={tab.icon}
            iconPosition="start"
            sx={{ minHeight: 64 }}
          />
        ))}
      </Tabs>
    </Box>
  );
};

export default TabNavigation;