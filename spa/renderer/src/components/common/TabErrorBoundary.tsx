import React from 'react';
import ErrorBoundary from './ErrorBoundary';
import { Box, Typography, Button } from '@mui/material';
import { Refresh } from '@mui/icons-material';

interface TabErrorBoundaryProps {
  children: React.ReactNode;
  tabName: string;
}

/**
 * Error boundary specifically for tab components
 * Provides isolated error handling so one tab's error doesn't crash the entire app
 */
const TabErrorBoundary: React.FC<TabErrorBoundaryProps> = ({ children, tabName }) => {
  const [key, setKey] = React.useState(0);

  const handleReset = () => {
    // Force re-mount of the tab component
    setKey(prev => prev + 1);
  };

  const fallback = (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 400,
        p: 3,
      }}
    >
      <Typography variant="h5" gutterBottom color="error">
        {tabName} Tab Error
      </Typography>
      <Typography variant="body1" color="text.secondary" paragraph align="center">
        This tab encountered an error and cannot be displayed.
      </Typography>
      <Button
        variant="contained"
        startIcon={<Refresh />}
        onClick={handleReset}
        sx={{ mt: 2 }}
      >
        Reload Tab
      </Button>
    </Box>
  );

  return (
    <ErrorBoundary
      key={key}
      fallback={fallback}
      onReset={handleReset}
      isolate={true}
    >
      {children}
    </ErrorBoundary>
  );
};

export default TabErrorBoundary;

/**
 * HOC to wrap any component with a tab error boundary
 */
export function withTabErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  tabName: string
): React.ComponentType<P> {
  return (props: P) => (
    <TabErrorBoundary tabName={tabName}>
      <Component {...props} />
    </TabErrorBoundary>
  );
}