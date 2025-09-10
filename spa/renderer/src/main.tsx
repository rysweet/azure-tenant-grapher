import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { AppProvider } from './context/AppContext';
import App from './App';
import ErrorBoundary from './components/common/ErrorBoundary';
import { theme } from './theme';
import './index.css';

// Initialize error handling services
import './services/errorService';
import './services/axiosConfig';

// Global error handler for React errors
window.addEventListener('error', (event) => {
  // These are already handled by errorService, but we can add React-specific handling here
  if (event.error && event.error.stack && event.error.stack.includes('React')) {
    console.error('React Error:', event.error);
  }
});

// Root error boundary fallback
const RootErrorFallback = (
  <div style={{ 
    padding: '40px', 
    textAlign: 'center',
    fontFamily: 'system-ui, -apple-system, sans-serif'
  }}>
    <h1 style={{ color: '#d32f2f' }}>Application Error</h1>
    <p>The application encountered a critical error and cannot continue.</p>
    <p>Please refresh the page to try again.</p>
    <button 
      onClick={() => window.location.reload()}
      style={{
        marginTop: '20px',
        padding: '10px 20px',
        fontSize: '16px',
        backgroundColor: '#1976d2',
        color: 'white',
        border: 'none',
        borderRadius: '4px',
        cursor: 'pointer'
      }}
    >
      Reload Application
    </button>
  </div>
);

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary fallback={RootErrorFallback}>
      <BrowserRouter>
        <ThemeProvider theme={theme}>
          <CssBaseline />
          <AppProvider>
            <App />
          </AppProvider>
        </ThemeProvider>
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>
);