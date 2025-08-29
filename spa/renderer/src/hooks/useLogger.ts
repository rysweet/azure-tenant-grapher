import { useCallback } from 'react';
import { useApp } from '../context/AppContext';
import { LogLevel } from '../context/AppContext';

interface LoggerOptions {
  source?: string;
}

export function useLogger(defaultSource: string = 'System') {
  const { dispatch } = useApp();

  const log = useCallback((
    level: LogLevel,
    message: string,
    data?: any,
    options?: LoggerOptions
  ) => {
    dispatch({
      type: 'ADD_STRUCTURED_LOG',
      payload: {
        level,
        source: options?.source || defaultSource,
        message,
        data,
      },
    });
  }, [dispatch, defaultSource]);

  const debug = useCallback((message: string, data?: any, options?: LoggerOptions) => {
    log('debug', message, data, options);
  }, [log]);

  const info = useCallback((message: string, data?: any, options?: LoggerOptions) => {
    log('info', message, data, options);
  }, [log]);

  const warning = useCallback((message: string, data?: any, options?: LoggerOptions) => {
    log('warning', message, data, options);
  }, [log]);

  const error = useCallback((message: string, data?: any, options?: LoggerOptions) => {
    log('error', message, data, options);
  }, [log]);

  // Convenience methods for common operations
  const logApiCall = useCallback((
    method: string,
    url: string,
    status: number,
    responseTime?: number,
    error?: any
  ) => {
    const level: LogLevel = status >= 400 ? 'error' : status >= 300 ? 'warning' : 'debug';
    const message = `${method.toUpperCase()} ${url} - ${status}`;
    
    log(level, message, {
      method,
      url,
      status,
      responseTime: responseTime ? `${responseTime}ms` : undefined,
      error: error?.message || error,
    }, { source: 'API' });
  }, [log]);

  const logProcessEvent = useCallback((
    processId: string,
    event: 'started' | 'completed' | 'failed' | 'cancelled',
    details?: any
  ) => {
    const levelMap: Record<string, LogLevel> = {
      started: 'info',
      completed: 'info',
      failed: 'error',
      cancelled: 'warning',
    };

    log(levelMap[event], `Process ${event}: ${processId}`, {
      processId,
      event,
      ...details,
    }, { source: 'Process' });
  }, [log]);

  const logWebSocketEvent = useCallback((
    event: 'connected' | 'disconnected' | 'error' | 'message',
    details?: any
  ) => {
    const levelMap: Record<string, LogLevel> = {
      connected: 'info',
      disconnected: 'warning',
      error: 'error',
      message: 'debug',
    };

    log(levelMap[event], `WebSocket ${event}`, details, { source: 'WebSocket' });
  }, [log]);

  const logGraphOperation = useCallback((
    operation: string,
    success: boolean,
    details?: any
  ) => {
    log(
      success ? 'info' : 'error',
      `Graph operation ${success ? 'completed' : 'failed'}: ${operation}`,
      details,
      { source: 'Graph' }
    );
  }, [log]);

  return {
    log,
    debug,
    info,
    warning,
    error,
    logApiCall,
    logProcessEvent,
    logWebSocketEvent,
    logGraphOperation,
  };
}

export default useLogger;