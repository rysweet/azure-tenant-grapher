import React from 'react';
import { Box } from '@mui/material';
import { GraphVisualization } from '../graph/GraphVisualization';

const VisualizeTab: React.FC = () => {
  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <GraphVisualization />
    </Box>
  );
};

export default VisualizeTab;