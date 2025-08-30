import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  IconButton,
  Paper,
  LinearProgress,
  Alert,
} from '@mui/material';
import {
  Close as CloseIcon,
  Clear as ClearIcon,
  ContentCopy as CopyIcon,
} from '@mui/icons-material';
import { Terminal } from 'xterm';
import { io, Socket } from 'socket.io-client';
import axios from 'axios';

interface CommandOutputDialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  command: string;
  args: string[];
  onCommandComplete?: (output: string[], exitCode: number) => void;
  onError?: (error: string) => void;
}

const CommandOutputDialog: React.FC<CommandOutputDialogProps> = ({
  open,
  onClose,
  title,
  command,
  args,
  onCommandComplete,
  onError,
}) => {
  const terminalRef = useRef<HTMLDivElement>(null);
  const terminalInstance = useRef<Terminal | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [currentProcessId, setCurrentProcessId] = useState<string | null>(null);
  const [processSocket, setProcessSocket] = useState<Socket | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [terminalOutput, setTerminalOutput] = useState<string[]>([]);

  // Initialize terminal
  useEffect(() => {
    if (open && terminalRef.current && !terminalInstance.current) {
      const term = new Terminal({
        theme: {
          background: '#1e1e1e',
          foreground: '#d4d4d4',
          cursor: '#ffffff',
          selection: '#264f78',
          black: '#000000',
          red: '#cd3131',
          green: '#0dbc79',
          yellow: '#e5e510',
          blue: '#2472c8',
          magenta: '#bc3fbc',
          cyan: '#11a8cd',
          white: '#e5e5e5',
          brightBlack: '#555555',
          brightRed: '#f14c4c',
          brightGreen: '#23d18b',
          brightYellow: '#f5f543',
          brightBlue: '#3b8eea',
          brightMagenta: '#d670d6',
          brightCyan: '#29b8db',
          brightWhite: '#e5e5e5',
        },
        fontSize: 13,
        fontFamily: '"Consolas", "Monaco", "Courier New", monospace',
        cursorBlink: true,
        scrollback: 1000,
        convertEol: true,
      });
      
      term.open(terminalRef.current);
      term.writeln(`Preparing to execute: ${command} ${args.join(' ')}`);
      term.writeln('');
      
      terminalInstance.current = term;
    }
  }, [open, command, args]);

  // Write output to terminal
  const writeToTerminal = useCallback((text: string, color?: string) => {
    if (terminalInstance.current) {
      if (color) {
        terminalInstance.current.write(`\x1b[${color}m${text}\x1b[0m\r\n`);
      } else {
        terminalInstance.current.write(`${text}\r\n`);
      }
    }
  }, []);

  // Clear terminal
  const clearTerminal = useCallback(() => {
    if (terminalInstance.current) {
      terminalInstance.current.clear();
      terminalInstance.current.write(`Preparing to execute: ${command} ${args.join(' ')}\r\n\r\n`);
    }
    setTerminalOutput([]);
  }, [command, args]);

  // Copy terminal output
  const copyOutput = useCallback(() => {
    const fullOutput = terminalOutput.join('\n');
    navigator.clipboard.writeText(fullOutput);
  }, [terminalOutput]);

  // Set up WebSocket for process events
  useEffect(() => {
    if (open && !processSocket) {
      const socket = io('http://localhost:3001');
      
      socket.on('connect', () => {
        console.log('CommandOutputDialog: Process event socket connected');
      });
      
      socket.on('output', (data: any) => {
        if (data.processId === currentProcessId) {
          data.data.forEach((line: string) => {
            writeToTerminal(line);
            setTerminalOutput(prev => [...prev, line]);
          });
        }
      });
      
      socket.on('process-exit', (event: any) => {
        if (event.processId === currentProcessId) {
          const exitMessage = `Process exited with code ${event.code}`;
          const color = event.code === 0 ? '32' : '31'; // Green for success, red for error
          writeToTerminal(exitMessage, color);
          writeToTerminal('');
          
          setIsRunning(false);
          setCurrentProcessId(null);
          
          if (onCommandComplete) {
            onCommandComplete(terminalOutput, event.code);
          }
        }
      });
      
      socket.on('process-error', (event: any) => {
        if (event.processId === currentProcessId) {
          const errorMsg = `Process error: ${event.error}`;
          writeToTerminal(errorMsg, '31'); // Red color
          setIsRunning(false);
          setCurrentProcessId(null);
          setError(errorMsg);
          
          if (onError) {
            onError(errorMsg);
          }
        }
      });
      
      setProcessSocket(socket);
    }
    
    return () => {
      if (processSocket && !open) {
        processSocket.disconnect();
        setProcessSocket(null);
      }
    };
  }, [open, processSocket, currentProcessId, writeToTerminal, terminalOutput, onCommandComplete, onError]);

  // Execute command when dialog opens
  useEffect(() => {
    if (open && command && args && !isRunning && !currentProcessId) {
      const executeCommand = async () => {
        setIsRunning(true);
        setError(null);
        setTerminalOutput([]);
        
        const commandLine = `${command} ${args.join(' ')}`;
        writeToTerminal(`$ atg ${commandLine}`, '32'); // Green color
        
        try {
          const response = await axios.post('http://localhost:3001/api/execute', {
            command,
            args
          });
          
          const processId = response.data.processId;
          setCurrentProcessId(processId);
          
          writeToTerminal(`Process started with ID: ${processId}`, '36'); // Cyan color
          
        } catch (err: any) {
          const errorMessage = err.response?.data?.error || err.message;
          setError(errorMessage);
          setIsRunning(false);
          writeToTerminal(`Error: ${errorMessage}`, '31'); // Red color
          
          if (onError) {
            onError(errorMessage);
          }
        }
      };

      // Execute after a short delay to ensure terminal is ready
      const timeoutId = setTimeout(executeCommand, 500);
      return () => clearTimeout(timeoutId);
    }
  }, [open, command, args, isRunning, currentProcessId, writeToTerminal, onError]);

  // Cleanup on close
  useEffect(() => {
    if (!open) {
      if (terminalInstance.current) {
        terminalInstance.current.dispose();
        terminalInstance.current = null;
      }
      if (processSocket) {
        processSocket.disconnect();
        setProcessSocket(null);
      }
      setIsRunning(false);
      setCurrentProcessId(null);
      setError(null);
      setTerminalOutput([]);
    }
  }, [open, processSocket]);

  // Stop command
  const stopCommand = async () => {
    if (currentProcessId) {
      try {
        await axios.post(`http://localhost:3001/api/cancel/${currentProcessId}`);
        writeToTerminal('Process cancelled by user', '33'); // Yellow color
        setIsRunning(false);
        setCurrentProcessId(null);
      } catch (err: any) {
        const errorMsg = `Failed to stop process: ${err.message}`;
        setError(errorMsg);
        writeToTerminal(errorMsg, '31'); // Red color
      }
    }
  };

  const handleClose = () => {
    if (isRunning && currentProcessId) {
      stopCommand();
    }
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="lg"
      fullWidth
      PaperProps={{
        sx: { height: '80vh', display: 'flex', flexDirection: 'column' }
      }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="h6">{title}</Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <IconButton size="small" onClick={clearTerminal} disabled={isRunning}>
            <ClearIcon />
          </IconButton>
          <IconButton size="small" onClick={copyOutput}>
            <CopyIcon />
          </IconButton>
          <IconButton size="small" onClick={handleClose}>
            <CloseIcon />
          </IconButton>
        </Box>
      </DialogTitle>

      <DialogContent sx={{ flex: 1, display: 'flex', flexDirection: 'column', p: 0 }}>
        {isRunning && (
          <Box sx={{ px: 3, py: 1 }}>
            <LinearProgress />
            <Typography variant="body2" sx={{ mt: 1 }}>
              Running command: atg {command} {args.join(' ')}
            </Typography>
          </Box>
        )}

        {error && (
          <Alert severity="error" sx={{ mx: 3, mt: 2 }}>
            {error}
          </Alert>
        )}

        <Box
          ref={terminalRef}
          sx={{
            flex: 1,
            backgroundColor: '#1e1e1e',
            minHeight: 400,
            '& .xterm': {
              height: '100%',
              padding: 1,
            },
            '& .xterm-viewport': {
              overflow: 'auto',
              backgroundColor: '#1e1e1e !important',
            },
            '& .xterm-screen': {
              backgroundColor: '#1e1e1e !important',
            },
          }}
        />
      </DialogContent>

      <DialogActions>
        {isRunning ? (
          <Button variant="outlined" color="error" onClick={stopCommand}>
            Stop Command
          </Button>
        ) : (
          <Button onClick={handleClose}>
            Close
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};

export default CommandOutputDialog;