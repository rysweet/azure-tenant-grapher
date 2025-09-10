import React, { Component, ErrorInfo, ReactNode } from 'react';
import { Alert, Box, Button, Typography, Collapse, IconButton, Stack } from '@mui/material';
import { ExpandMore, ExpandLess, Refresh, Home } from '@mui/icons-material';
import { errorService } from '../../services/errorService';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onReset?: () => void;
  isolate?: boolean; // If true, only affects this component tree
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  showDetails: boolean;
  retryCount: number;
}

class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
    showDetails: false,
    retryCount: 0,
  };

  public static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Log to error service
    errorService.logError(
      error,
      'component',
      {
        componentStack: errorInfo.componentStack,
        retryCount: this.state.retryCount,
      },
      errorInfo.componentStack
    );

    this.setState({ errorInfo });
  }

  private handleReset = () => {
    this.setState((prevState) => ({
      hasError: false,
      error: null,
      errorInfo: null,
      showDetails: false,
      retryCount: prevState.retryCount + 1,
    }));

    // Call custom reset handler if provided
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  private handleReload = () => {
    window.location.reload();
  };

  private handleGoHome = () => {
    window.location.href = '/';
  };

  private toggleDetails = () => {
    this.setState((prevState) => ({
      showDetails: !prevState.showDetails,
    }));
  };

  public render() {
    if (this.state.hasError) {
      // Use custom fallback if provided
      if (this.props.fallback) {
        return <>{this.props.fallback}</>;
      }

      const { error, errorInfo, showDetails, retryCount } = this.state;
      const isIsolated = this.props.isolate;

      return (
        <Box sx={{ p: 3, maxWidth: '100%', overflow: 'auto' }}>
          <Alert 
            severity="error" 
            sx={{ 
              '& .MuiAlert-message': { 
                width: '100%' 
              } 
            }}
          >
            <Stack spacing={2}>
              <Box>
                <Typography variant="h6" gutterBottom>
                  {isIsolated ? 'Component Error' : 'Application Error'}
                </Typography>
                <Typography variant="body2" color="text.secondary" paragraph>
                  {error?.message || 'An unexpected error occurred'}
                </Typography>
                {retryCount > 0 && (
                  <Typography variant="caption" color="text.secondary">
                    Retry attempts: {retryCount}
                  </Typography>
                )}
              </Box>

              <Stack direction="row" spacing={1}>
                <Button
                  variant="contained"
                  size="small"
                  startIcon={<Refresh />}
                  onClick={this.handleReset}
                >
                  Try Again
                </Button>
                {!isIsolated && (
                  <>
                    <Button
                      variant="outlined"
                      size="small"
                      startIcon={<Home />}
                      onClick={this.handleGoHome}
                    >
                      Go to Home
                    </Button>
                    <Button
                      variant="outlined"
                      size="small"
                      onClick={this.handleReload}
                      color="warning"
                    >
                      Reload App
                    </Button>
                  </>
                )}
                <IconButton
                  size="small"
                  onClick={this.toggleDetails}
                  aria-label="toggle error details"
                >
                  {showDetails ? <ExpandLess /> : <ExpandMore />}
                </IconButton>
              </Stack>

              <Collapse in={showDetails}>
                <Box
                  sx={{
                    mt: 2,
                    p: 2,
                    backgroundColor: 'grey.100',
                    borderRadius: 1,
                    fontFamily: 'monospace',
                    fontSize: '0.85rem',
                    overflow: 'auto',
                    maxHeight: 400,
                  }}
                >
                  <Typography variant="subtitle2" gutterBottom>
                    Error Stack:
                  </Typography>
                  <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                    {error?.stack}
                  </pre>
                  {errorInfo?.componentStack && (
                    <>
                      <Typography variant="subtitle2" gutterBottom sx={{ mt: 2 }}>
                        Component Stack:
                      </Typography>
                      <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                        {errorInfo.componentStack}
                      </pre>
                    </>
                  )}
                </Box>
              </Collapse>
            </Stack>
          </Alert>
        </Box>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;