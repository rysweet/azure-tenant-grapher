import { useState, useEffect, useRef, useCallback } from 'react';

interface ProcessResult {
  id: string;
  pid?: number;
  command: string;
  args: string[];
  startTime: Date;
}

interface ProcessOutput {
  stdout: string[];
  stderr: string[];
}

interface UseProcessExecutionOptions {
  onOutput?: (data: { type: 'stdout' | 'stderr'; lines: string[] }) => void;
  onExit?: (code: number) => void;
  onError?: (error: string) => void;
}

export function useProcessExecution(options: UseProcessExecutionOptions = {}) {
  const [isRunning, setIsRunning] = useState(false);
  const [output, setOutput] = useState<ProcessOutput>({ stdout: [], stderr: [] });
  const [exitCode, setExitCode] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const currentProcessId = useRef<string | null>(null);

  // Clean up listeners on unmount or when process changes
  useEffect(() => {
    return () => {
      if (currentProcessId.current) {
        cleanup();
      }
    };
  }, []);

  const cleanup = useCallback(() => {
    if (!currentProcessId.current) return;
    
    // Remove all listeners for this process
    window.electronAPI.removeAllListeners('process:output');
    window.electronAPI.removeAllListeners('process:exit');
    window.electronAPI.removeAllListeners('process:error');
    currentProcessId.current = null;
  }, []);

  const execute = useCallback(async (command: string, args: string[] = []) => {
    // Clean up any previous execution
    cleanup();
    
    // Reset state
    setIsRunning(true);
    setOutput({ stdout: [], stderr: [] });
    setExitCode(null);
    setError(null);

    try {
      // Execute the command
      const result = await window.electronAPI.cli.execute(command, args);
      
      if (!result.success) {
        throw new Error(result.error || 'Command execution failed');
      }

      const processId = result.data.id;
      currentProcessId.current = processId;

      // Set up event listeners for this specific process
      const handleOutput = (data: any) => {
        if (data.id === processId) {
          const lines = Array.isArray(data.data) ? data.data : [data.data];
          
          if (data.type === 'stdout') {
            setOutput(prev => ({ ...prev, stdout: [...prev.stdout, ...lines] }));
          } else if (data.type === 'stderr') {
            setOutput(prev => ({ ...prev, stderr: [...prev.stderr, ...lines] }));
          }
          
          // Call user callback if provided
          if (options.onOutput) {
            options.onOutput({ type: data.type, lines });
          }
        }
      };

      const handleExit = (data: any) => {
        if (data.id === processId) {
          setIsRunning(false);
          setExitCode(data.code);
          
          // Call user callback if provided
          if (options.onExit) {
            options.onExit(data.code);
          }
          
          // Clean up listeners after exit
          cleanup();
        }
      };

      const handleError = (data: any) => {
        if (data.id === processId) {
          const errorMsg = data.error || 'Process error occurred';
          setError(errorMsg);
          setIsRunning(false);
          
          // Call user callback if provided
          if (options.onError) {
            options.onError(errorMsg);
          }
          
          // Clean up listeners after error
          cleanup();
        }
      };

      // Register listeners
      window.electronAPI.on('process:output', handleOutput);
      window.electronAPI.on('process:exit', handleExit);
      window.electronAPI.on('process:error', handleError);

      return processId;
    } catch (err: any) {
      setIsRunning(false);
      setError(err.message);
      
      if (options.onError) {
        options.onError(err.message);
      }
      
      throw err;
    }
  }, [cleanup, options]);

  const cancel = useCallback(async () => {
    if (!currentProcessId.current) return;
    
    try {
      await window.electronAPI.cli.cancel(currentProcessId.current);
    } catch (err: any) {
      console.error('Failed to cancel process:', err);
    }
  }, []);

  return {
    execute,
    cancel,
    isRunning,
    output,
    exitCode,
    error,
    cleanup,
  };
}