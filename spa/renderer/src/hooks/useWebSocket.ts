import { useEffect, useState, useCallback, useRef } from 'react';
import io, { Socket } from 'socket.io-client';

interface WebSocketOptions {
  url?: string;
  autoConnect?: boolean;
}

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

export function useWebSocket(options: WebSocketOptions = {}) {
  const {
    url = 'http://localhost:3001',
    autoConnect = true,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [outputs, setOutputs] = useState<Map<string, OutputData[]>>(new Map());
  const socketRef = useRef<Socket | null>(null);
  const subscribedProcesses = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (autoConnect) {
      socketRef.current = io(url, {
        transports: ['websocket'],
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionAttempts: 5,
      });

      socketRef.current.on('connect', () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        
        // Re-subscribe to any processes we were watching
        subscribedProcesses.current.forEach(processId => {
          socketRef.current?.emit('subscribe', processId);
        });
      });

      socketRef.current.on('disconnect', () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);
      });

      socketRef.current.on('output', (data: OutputData) => {
        setOutputs(prev => {
          const newMap = new Map(prev);
          const existing = newMap.get(data.processId) || [];
          newMap.set(data.processId, [...existing, data]);
          return newMap;
        });
      });

      socketRef.current.on('process-exit', (event: ProcessEvent) => {
        console.log('Process exited:', event);
        subscribedProcesses.current.delete(event.processId);
      });

      socketRef.current.on('process-error', (event: ProcessEvent) => {
        console.error('Process error:', event);
        subscribedProcesses.current.delete(event.processId);
      });

      return () => {
        socketRef.current?.disconnect();
        socketRef.current = null;
      };
    }
  }, [url, autoConnect]);

  const subscribeToProcess = useCallback((processId: string) => {
    if (socketRef.current && !subscribedProcesses.current.has(processId)) {
      socketRef.current.emit('subscribe', processId);
      subscribedProcesses.current.add(processId);
      setOutputs(prev => {
        const newMap = new Map(prev);
        if (!newMap.has(processId)) {
          newMap.set(processId, []);
        }
        return newMap;
      });
    }
  }, []);

  const unsubscribeFromProcess = useCallback((processId: string) => {
    if (socketRef.current && subscribedProcesses.current.has(processId)) {
      socketRef.current.emit('unsubscribe', processId);
      subscribedProcesses.current.delete(processId);
    }
  }, []);

  const clearProcessOutput = useCallback((processId: string) => {
    setOutputs(prev => {
      const newMap = new Map(prev);
      newMap.delete(processId);
      return newMap;
    });
  }, []);

  const getProcessOutput = useCallback((processId: string): string[] => {
    const processOutputs = outputs.get(processId) || [];
    return processOutputs.flatMap(output => output.data);
  }, [outputs]);

  return {
    isConnected,
    subscribeToProcess,
    unsubscribeFromProcess,
    clearProcessOutput,
    getProcessOutput,
    outputs,
  };
}