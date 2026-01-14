import { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import io, { Socket } from 'socket.io-client';
import { useLogger } from './useLogger';

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

type ProcessExitCallback = (event: ProcessEvent) => void;

const MAX_OUTPUT_BUFFER_SIZE = 10000; // Maximum lines per process
const MAX_RECONNECT_DELAY = 30000; // Maximum 30 seconds

export function useWebSocket(options: WebSocketOptions = {}) {
  const {
    url = 'http://localhost:3001',
    autoConnect = true,
  } = options;
  const logger = useLogger('WebSocket');

  const [isConnected, setIsConnected] = useState(false);
  const [outputs, setOutputs] = useState<Map<string, OutputData[]>>(new Map());
  const socketRef = useRef<Socket | null>(null);
  const subscribedProcesses = useRef<Set<string>>(new Set());
  const reconnectAttempt = useRef(0);
  const processExitCallbacks = useRef<Map<string, Set<ProcessExitCallback>>>(new Map());

  useEffect(() => {
    if (autoConnect) {
      // Exponential backoff for reconnection
      const getReconnectionDelay = () => {
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempt.current), MAX_RECONNECT_DELAY);
        reconnectAttempt.current++;
        return delay;
      };

      socketRef.current = io(url, {
        transports: ['websocket'],
        reconnection: true,
        reconnectionDelay: getReconnectionDelay(),
        reconnectionAttempts: 10,
      });

      socketRef.current.on('connect', () => {
        setIsConnected(true);
        reconnectAttempt.current = 0; // Reset reconnect attempts on successful connection

        // Log successful connection
        logger.logWebSocketEvent('connected', { url });

        // Re-subscribe to any processes we were watching
        subscribedProcesses.current.forEach(processId => {
          socketRef.current?.emit('subscribe', processId);
        });
      });

      socketRef.current.on('disconnect', (reason) => {
        setIsConnected(false);

        // Log disconnection with reason
        logger.logWebSocketEvent('disconnected', { url, reason });
        console.log('WebSocket disconnected:', reason);
      });

      socketRef.current.on('connect_error', (error) => {
        console.error('WebSocket connection error:', error);
        logger.logWebSocketEvent('error', { url, error: error.message });
      });

      socketRef.current.on('error', (error) => {
        console.error('WebSocket error:', error);
      });

      // Handle heartbeat ping/pong
      socketRef.current.on('ping', () => {
        socketRef.current?.emit('pong');
        if (process.env.NODE_ENV === 'development') {
          console.debug('WebSocket: Responded to ping with pong');
        }
      });

      socketRef.current.on('output', (data: OutputData) => {
        // Optional debug logging in development
        if (process.env.NODE_ENV === 'development') {
          console.debug('WebSocket: Received output', {
            processId: data.processId,
            type: data.type,
            dataType: Array.isArray(data.data) ? 'array' : typeof data.data,
            dataLength: Array.isArray(data.data) ? data.data.length : 1,
          });
        }

        setOutputs(prev => {
          const newMap = new Map(prev);
          const existing = newMap.get(data.processId) || [];

          // Enforce memory limit - keep only the most recent outputs
          let updatedOutputs = [...existing, data];
          const totalLines = updatedOutputs.reduce((sum, output) => sum + output.data.length, 0);

          if (totalLines > MAX_OUTPUT_BUFFER_SIZE) {
            // Remove oldest outputs until under limit
            while (updatedOutputs.length > 1 &&
                   updatedOutputs.reduce((sum, output) => sum + output.data.length, 0) > MAX_OUTPUT_BUFFER_SIZE) {
              updatedOutputs.shift();
            }
          }

          newMap.set(data.processId, updatedOutputs);
          return newMap;
        });
      });

      socketRef.current.on('process-exit', (event: ProcessEvent) => {
        // Notify all registered callbacks for this process
        const callbacks = processExitCallbacks.current.get(event.processId);
        if (callbacks) {
          callbacks.forEach(callback => callback(event));
        }

        // Clean up
        subscribedProcesses.current.delete(event.processId);
        processExitCallbacks.current.delete(event.processId);
      });

      socketRef.current.on('process-error', (event: ProcessEvent) => {
        subscribedProcesses.current.delete(event.processId);
      });

      return () => {
        // Cleanup: unsubscribe from all processes before disconnecting
        if (socketRef.current) {
          subscribedProcesses.current.forEach(processId => {
            socketRef.current?.emit('unsubscribe', processId);
          });
          subscribedProcesses.current.clear();

          // Remove all listeners to prevent memory leaks
          socketRef.current.removeAllListeners();
          socketRef.current.disconnect();
          socketRef.current = null;
        }

        // Clear outputs to free memory
        setOutputs(new Map());
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

  const onProcessExit = useCallback((processId: string, callback: ProcessExitCallback) => {
    if (!processExitCallbacks.current.has(processId)) {
      processExitCallbacks.current.set(processId, new Set());
    }
    processExitCallbacks.current.get(processId)!.add(callback);

    // Return cleanup function
    return () => {
      const callbacks = processExitCallbacks.current.get(processId);
      if (callbacks) {
        callbacks.delete(callback);
        if (callbacks.size === 0) {
          processExitCallbacks.current.delete(processId);
        }
      }
    };
  }, []);

  return useMemo(() => ({
    isConnected,
    subscribeToProcess,
    unsubscribeFromProcess,
    clearProcessOutput,
    getProcessOutput,
    onProcessExit,
    outputs,
  }), [isConnected, subscribeToProcess, unsubscribeFromProcess, clearProcessOutput, getProcessOutput, onProcessExit, outputs]);
}
