import { Component, ErrorInfo, ReactNode } from 'react';
import { Alert, Box, Button, Typography, Collapse, IconButton, Stack, LinearProgress } from '@mui/material';
import { ExpandMore, ExpandLess, Refresh, Home, AutorenewRounded } from '@mui/icons-material';
import { errorService } from '../../services/errorService';
import { errorRecoveryService } from '../../services/errorRecoveryService';
import { ResourceManager } from '../../utils/resourceManager';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onReset?: () => void;
  isolate?: boolean; // If true, only affects this component tree
  maxRetries?: number; // Maximum number of retry attempts
  resetDelay?: number; // Delay in ms before allowing next retry
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  showDetails: boolean;
  retryCount: number;
  lastRetryTime: number;
  isRecovering: boolean;
}

class ErrorBoundary extends Component<Props, State> {
  private cleanupCallbacks: Set<() => void> = new Set();
  private resetTimeoutId: NodeJS.Timeout | null = null;
  private resourceManager: ResourceManager = new ResourceManager();

  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
    showDetails: false,
    retryCount: 0,
    lastRetryTime: 0,
    isRecovering: false,
  };

  public static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  public async componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    const maxRetries = this.props.maxRetries ?? 3;
    const shouldAutoRetry = this.state.retryCount < maxRetries;

    // Log to error service
    errorService.logError(
      error,
      'component',
      {
        componentStack: errorInfo.componentStack,
        retryCount: this.state.retryCount,
        maxRetries,
        willAutoRetry: shouldAutoRetry,
      },
      errorInfo.componentStack || undefined
    );

    this.setState({ errorInfo });

    // Try automatic recovery strategies first
    if (!this.props.isolate) {
      const recoveryResult = await errorRecoveryService.attemptRecovery(error);

      if (recoveryResult.success) {
        // Successfully recovered using recovery strategy
        this.handleReset();
        return;
      }
    }

    // Fall back to auto-retry with exponential backoff if under retry limit
    if (shouldAutoRetry && !this.props.isolate) {
      const delay = Math.min(1000 * Math.pow(2, this.state.retryCount), 10000);
      this.scheduleAutoRecovery(delay);
    }
  }

  private handleReset = () => {
    const maxRetries = this.props.maxRetries ?? 3;
    const resetDelay = this.props.resetDelay ?? 1000;
    const now = Date.now();
    const timeSinceLastRetry = now - this.state.lastRetryTime;

    // Enforce minimum delay between retries
    if (timeSinceLastRetry < resetDelay) {
      // Console warn removed
      return;
    }

    // Check retry limit
    if (this.state.retryCount >= maxRetries) {
      // Console error removed
      return;
    }

    // Clear any pending auto-recovery
    this.clearAutoRecovery();

    // Perform cleanup before reset
    this.performCleanup();

    this.setState((prevState) => ({
      hasError: false,
      error: null,
      errorInfo: null,
      showDetails: false,
      retryCount: prevState.retryCount + 1,
      lastRetryTime: now,
      isRecovering: false,
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

  private scheduleAutoRecovery = (delay: number) => {
    this.setState({ isRecovering: true });

    const timeoutId = setTimeout(() => {
      if (this.state.hasError) {
        // Attempting auto-recovery after delay
        this.handleReset();
      }
    }, delay);

    this.resetTimeoutId = timeoutId;
    this.resourceManager.registerTimer('auto-recovery', timeoutId);
  };

  private clearAutoRecovery = () => {
    if (this.resetTimeoutId) {
      clearTimeout(this.resetTimeoutId);
      this.resetTimeoutId = null;
    }
  };

  private performCleanup = () => {
    // Execute all registered cleanup callbacks
    this.cleanupCallbacks.forEach(callback => {
      try {
        callback();
      } catch (cleanupError) {
        // Console error removed
      }
    });
    this.cleanupCallbacks.clear();

    // Clean up any old resources to prevent memory leaks
    this.resourceManager.cleanupOldResources(60000); // Clean up resources older than 1 minute
  };

  public registerCleanup = (callback: () => void) => {
    this.cleanupCallbacks.add(callback);
    return () => {
      this.cleanupCallbacks.delete(callback);
    };
  };

  public componentWillUnmount() {
    // Clear any pending auto-recovery
    this.clearAutoRecovery();

    // Perform cleanup to prevent memory leaks
    this.performCleanup();

    // Dispose resource manager
    void this.resourceManager.dispose();
  }

  public render() {
    if (this.state.hasError) {
      // Use custom fallback if provided
      if (this.props.fallback) {
        return <>{this.props.fallback}</>;
      }

      const { error, errorInfo, showDetails, retryCount, isRecovering } = this.state;
      const isIsolated = this.props.isolate;
      const maxRetries = this.props.maxRetries ?? 3;
      const canRetry = retryCount < maxRetries;

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
                    Retry attempts: {retryCount}/{maxRetries}
                  </Typography>
                )}
                {isRecovering && (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <AutorenewRounded sx={{ fontSize: 16, animation: 'spin 2s linear infinite' }} />
                    <Typography variant="caption" color="info.main">
                      Auto-recovery in progress...
                    </Typography>
                    <LinearProgress sx={{ flex: 1, maxWidth: 100 }} />
                  </Box>
                )}
              </Box>

              <Stack direction="row" spacing={1}>
                <Button
                  variant="contained"
                  size="small"
                  startIcon={<Refresh />}
                  onClick={this.handleReset}
                  disabled={!canRetry || isRecovering}
                >
                  {canRetry ? 'Try Again' : 'Max Retries Reached'}
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
