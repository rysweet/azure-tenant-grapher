import React, { createContext, useContext, useReducer, ReactNode } from 'react';

export interface BackgroundOperation {
  id: string;
  type: string;
  name: string;
  status: 'running' | 'completed' | 'error';
  startTime: Date;
  pid?: number;
}

export type LogLevel = 'debug' | 'info' | 'warning' | 'error';

export interface LogEntry {
  id: string;
  timestamp: Date;
  level: LogLevel;
  source: string;
  message: string;
  data?: any;
}

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
  logs: LogEntry[];
  logSettings: {
    autoScroll: boolean;
    showLevels: LogLevel[];
    searchFilter: string;
  };
  theme: 'light' | 'dark';
  backgroundOperations: Map<string, BackgroundOperation>;
}

type AppAction =
  | { type: 'SET_ACTIVE_TAB'; payload: string }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_OPERATION'; payload: any }
  | { type: 'SET_CONFIG'; payload: Partial<AppState['config']> }
  | { type: 'ADD_RESULT'; payload: { key: string; value: any } }
  | { type: 'ADD_LOG'; payload: string | LogEntry }
  | { type: 'ADD_STRUCTURED_LOG'; payload: { level: LogLevel; source: string; message: string; data?: any } }
  | { type: 'CLEAR_LOGS' }
  | { type: 'SET_LOG_SETTINGS'; payload: Partial<AppState['logSettings']> }
  | { type: 'SET_THEME'; payload: 'light' | 'dark' }
  | { type: 'ADD_BACKGROUND_OPERATION'; payload: BackgroundOperation }
  | { type: 'UPDATE_BACKGROUND_OPERATION'; payload: { id: string; updates: Partial<BackgroundOperation> } }
  | { type: 'REMOVE_BACKGROUND_OPERATION'; payload: string };

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
  logSettings: {
    autoScroll: true,
    showLevels: ['debug', 'info', 'warning', 'error'],
    searchFilter: '',
  },
  theme: 'dark',
  backgroundOperations: new Map(),
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
      // Support both string (legacy) and LogEntry formats
      if (typeof action.payload === 'string') {
        const logEntry: LogEntry = {
          id: Date.now().toString(),
          timestamp: new Date(),
          level: 'info',
          source: 'system',
          message: action.payload,
        };
        return { ...state, logs: [...state.logs, logEntry] };
      }
      return { ...state, logs: [...state.logs, action.payload] };
    
    case 'ADD_STRUCTURED_LOG':
      const logEntry: LogEntry = {
        id: Date.now().toString() + Math.random().toString(36).substr(2, 9),
        timestamp: new Date(),
        level: action.payload.level,
        source: action.payload.source,
        message: action.payload.message,
        data: action.payload.data,
      };
      return { ...state, logs: [...state.logs, logEntry] };
    
    case 'SET_LOG_SETTINGS':
      return {
        ...state,
        logSettings: { ...state.logSettings, ...action.payload },
      };
    
    case 'CLEAR_LOGS':
      return { ...state, logs: [] };
    
    case 'SET_THEME':
      return { ...state, theme: action.payload };
    
    case 'ADD_BACKGROUND_OPERATION':
      const newBackgroundOps = new Map(state.backgroundOperations);
      newBackgroundOps.set(action.payload.id, action.payload);
      return { ...state, backgroundOperations: newBackgroundOps };
    
    case 'UPDATE_BACKGROUND_OPERATION':
      const updatedBackgroundOps = new Map(state.backgroundOperations);
      const existingOp = updatedBackgroundOps.get(action.payload.id);
      if (existingOp) {
        updatedBackgroundOps.set(action.payload.id, { ...existingOp, ...action.payload.updates });
      }
      return { ...state, backgroundOperations: updatedBackgroundOps };
    
    case 'REMOVE_BACKGROUND_OPERATION':
      const filteredBackgroundOps = new Map(state.backgroundOperations);
      filteredBackgroundOps.delete(action.payload);
      return { ...state, backgroundOperations: filteredBackgroundOps };
    
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