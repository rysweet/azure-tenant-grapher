import { createTheme } from '@mui/material/styles';

export const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#0078d4',
      light: '#40a9ff',
      dark: '#0050a0',
    },
    secondary: {
      main: '#00bcf2',
      light: '#50dfff',
      dark: '#008cba',
    },
    background: {
      default: '#1e1e1e',
      paper: '#2d2d30',
    },
    text: {
      primary: '#cccccc',
      secondary: '#969696',
    },
    error: {
      main: '#f44336',
    },
    warning: {
      main: '#ff9800',
    },
    info: {
      main: '#2196f3',
    },
    success: {
      main: '#4caf50',
    },
  },
  typography: {
    fontFamily: '"Segoe UI", "Roboto", "Helvetica", "Arial", sans-serif',
    h1: {
      fontSize: '2.5rem',
      fontWeight: 600,
    },
    h2: {
      fontSize: '2rem',
      fontWeight: 600,
    },
    h3: {
      fontSize: '1.75rem',
      fontWeight: 600,
    },
    h4: {
      fontSize: '1.5rem',
      fontWeight: 600,
    },
    h5: {
      fontSize: '1.25rem',
      fontWeight: 600,
    },
    h6: {
      fontSize: '1rem',
      fontWeight: 600,
    },
  },
  shape: {
    borderRadius: 4,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 500,
        },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          minHeight: 48,
        },
      },
    },
    MuiTextField: {
      defaultProps: {
        variant: 'outlined',
        size: 'small',
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
      },
    },
    MuiAppBar: {
      defaultProps: {
        color: 'default',
      },
      styleOverrides: {
        root: {
          backgroundColor: '#000000 !important',
          backgroundImage: 'none !important',
          color: '#ffffff !important',
        },
        colorDefault: {
          backgroundColor: '#000000 !important',
          backgroundImage: 'none !important',
          color: '#ffffff !important',
        },
        colorPrimary: {
          backgroundColor: '#000000 !important',
          backgroundImage: 'none !important',
        },
      },
    },
    MuiToolbar: {
      styleOverrides: {
        root: {
          backgroundColor: 'transparent !important',
        },
      },
    },
  },
});