import React, { createContext, useContext, ReactNode } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';

interface OutputData {
  processId: string;
  type: 'stdout' | 'stderr';
  data: string[];
  timestamp: string;
}

interface ProcessEvent {
  processId: string;
  code?: number;
  error?: string;
  timestamp: string;
}

type ProcessExitCallback = (event: ProcessEvent) => void;

interface WebSocketContextType {
  isConnected: boolean;
  subscribeToProcess: (processId: string) => void;
  unsubscribeFromProcess: (processId: string) => void;
  clearProcessOutput: (processId: string) => void;
  getProcessOutput: (processId: string) => string[];
  onProcessExit: (processId: string, callback: ProcessExitCallback) => () => void;
  outputs: Map<string, OutputData[]>;
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

interface WebSocketProviderProps {
  children: ReactNode;
}

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({ children }) => {
  // Create a single WebSocket connection that will be shared across all components
  const webSocket = useWebSocket();

  return (
    <WebSocketContext.Provider value={webSocket}>
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocketContext = (): WebSocketContextType => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocketContext must be used within a WebSocketProvider');
  }
  return context;
};
