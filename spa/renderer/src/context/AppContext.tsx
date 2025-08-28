import React, { createContext, useContext, useReducer, ReactNode } from 'react';

interface AppState {
  activeTab: string;
  currentOperation: any | null;
  isLoading: boolean;
  config: {
    tenantId: string;
    azureConfig: any;
    neo4jConfig: any;
  };
  results: Map<string, any>;
  logs: string[];
  theme: 'light' | 'dark';
}

type AppAction =
  | { type: 'SET_ACTIVE_TAB'; payload: string }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_OPERATION'; payload: any }
  | { type: 'SET_CONFIG'; payload: Partial<AppState['config']> }
  | { type: 'ADD_RESULT'; payload: { key: string; value: any } }
  | { type: 'ADD_LOG'; payload: string }
  | { type: 'CLEAR_LOGS' }
  | { type: 'SET_THEME'; payload: 'light' | 'dark' };

const initialState: AppState = {
  activeTab: 'build',
  currentOperation: null,
  isLoading: false,
  config: {
    tenantId: '',
    azureConfig: {},
    neo4jConfig: {},
  },
  results: new Map(),
  logs: [],
  theme: 'dark',
};

function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'SET_ACTIVE_TAB':
      return { ...state, activeTab: action.payload };
    
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    
    case 'SET_OPERATION':
      return { ...state, currentOperation: action.payload };
    
    case 'SET_CONFIG':
      return {
        ...state,
        config: { ...state.config, ...action.payload },
      };
    
    case 'ADD_RESULT':
      const newResults = new Map(state.results);
      newResults.set(action.payload.key, action.payload.value);
      return { ...state, results: newResults };
    
    case 'ADD_LOG':
      return { ...state, logs: [...state.logs, action.payload] };
    
    case 'CLEAR_LOGS':
      return { ...state, logs: [] };
    
    case 'SET_THEME':
      return { ...state, theme: action.payload };
    
    default:
      return state;
  }
}

interface AppContextType {
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState);

  React.useEffect(() => {
    // Load saved config from electron store
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      const savedConfig = await window.electronAPI.config.get('appConfig');
      if (savedConfig) {
        dispatch({ type: 'SET_CONFIG', payload: savedConfig });
      }
      
      const theme = await window.electronAPI.config.get('theme');
      if (theme) {
        dispatch({ type: 'SET_THEME', payload: theme });
      }
    } catch (error) {
      console.error('Failed to load config:', error);
    }
  };

  // Save config when it changes
  React.useEffect(() => {
    if (state.config.tenantId) {
      window.electronAPI.config.set('appConfig', state.config);
    }
  }, [state.config]);

  return (
    <AppContext.Provider value={{ state, dispatch }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
}