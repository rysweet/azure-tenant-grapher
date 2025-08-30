import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Box,
  Paper,
  Grid,
  Typography,
  TextField,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormControlLabel,
  Checkbox,
  Slider,
  Chip,
  IconButton,
  Tooltip,
  Alert,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Card,
  CardContent,
  CardActions,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  SelectChangeEvent,
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  Clear as ClearIcon,
  History as HistoryIcon,
  ContentCopy as CopyIcon,
  ExpandMore as ExpandMoreIcon,
  Terminal as TerminalIcon,
  Build as BuildIcon,
  Code as CodeIcon,
  Description as DescriptionIcon,
  Visibility as VisibilityIcon,
  AddCircle as AddCircleIcon,
  Security as SecurityIcon,
  Psychology as PsychologyIcon,
} from '@mui/icons-material';
import { Terminal } from 'xterm';
import axios from 'axios';
import { useWebSocket } from '../../hooks/useWebSocket';
import { useApp } from '../../context/AppContext';
import { io, Socket } from 'socket.io-client';
import { useLocation, useSearchParams } from 'react-router-dom';

interface CommandDefinition {
  name: string;
  label: string;
  description: string;
  icon: React.ReactElement;
  category: string;
  args: {
    name: string;
    label: string;
    type: 'string' | 'number' | 'boolean' | 'select';
    required?: boolean;
    default?: any;
    options?: string[];
    min?: number;
    max?: number;
    description?: string;
  }[];
  examples?: string[];
}

const CLI_COMMANDS: CommandDefinition[] = [
  {
    name: 'build',
    label: 'Build Graph',
    description: 'Build the complete Azure tenant graph with enhanced processing',
    icon: <BuildIcon />,
    category: 'Core',
    args: [
      { name: 'tenant-id', label: 'Tenant ID', type: 'string', required: true, description: 'Azure tenant ID or domain' },
      { name: 'resource-limit', label: 'Resource Limit', type: 'number', min: 1, max: 10000, description: 'Maximum number of resources to process' },
      { name: 'max-llm-threads', label: 'Max LLM Threads', type: 'number', default: 5, min: 1, max: 20, description: 'Maximum parallel LLM threads' },
      { name: 'max-build-threads', label: 'Max Build Threads', type: 'number', default: 20, min: 1, max: 100, description: 'Maximum concurrent API calls' },
      { name: 'max-retries', label: 'Max Retries', type: 'number', default: 3, min: 1, max: 10, description: 'Maximum retries for failed resources' },
      { name: 'no-container', label: 'No Container', type: 'boolean', description: 'Do not auto-start Neo4j container' },
      { name: 'generate-spec', label: 'Generate Spec', type: 'boolean', description: 'Generate tenant specification after building' },
      { name: 'visualize', label: 'Visualize', type: 'boolean', description: 'Generate graph visualization after building' },
      { name: 'no-dashboard', label: 'No Dashboard', type: 'boolean', description: 'Disable Rich dashboard, emit logs line by line' },
      { name: 'rebuild-edges', label: 'Rebuild Edges', type: 'boolean', description: 'Force re-evaluation of all relationships' },
      { name: 'no-aad-import', label: 'No AAD Import', type: 'boolean', description: 'Skip Azure AD user/group import' },
    ],
    examples: [
      'build --tenant-id contoso.onmicrosoft.com',
      'build --tenant-id contoso.onmicrosoft.com --resource-limit 100 --no-dashboard',
    ],
  },
  {
    name: 'generate-iac',
    label: 'Generate IaC',
    description: 'Generate Infrastructure-as-Code templates from graph data',
    icon: <CodeIcon />,
    category: 'Core',
    args: [
      { name: 'tenant-id', label: 'Tenant ID', type: 'string', description: 'Azure tenant ID (defaults to env)' },
      { name: 'format', label: 'Format', type: 'select', options: ['terraform', 'arm', 'bicep'], default: 'terraform', description: 'Target IaC format' },
      { name: 'output', label: 'Output Directory', type: 'string', description: 'Output directory for generated templates' },
      { name: 'rules-file', label: 'Rules File', type: 'string', description: 'Path to transformation rules configuration' },
      { name: 'dry-run', label: 'Dry Run', type: 'boolean', description: 'Validate inputs without generating templates' },
      { name: 'resource-filters', label: 'Resource Filters', type: 'string', description: 'Resource type filters (comma-separated)' },
      { name: 'subset-filter', label: 'Subset Filter', type: 'string', description: 'Subset filter string' },
      { name: 'dest-rg', label: 'Destination RG', type: 'string', description: 'Target resource group name' },
      { name: 'location', label: 'Location', type: 'string', description: 'Target location/region' },
      { name: 'domain-name', label: 'Domain Name', type: 'string', description: 'Domain name for entities' },
    ],
    examples: [
      'generate-iac --format terraform',
      'generate-iac --format bicep --dest-rg my-rg --location eastus',
    ],
  },
  {
    name: 'generate-spec',
    label: 'Generate Spec',
    description: 'Generate anonymized tenant Markdown specification',
    icon: <DescriptionIcon />,
    category: 'Core',
    args: [
      { name: 'limit', label: 'Resource Limit', type: 'number', description: 'Resource limit (overrides config)' },
      { name: 'output', label: 'Output Path', type: 'string', description: 'Custom output path' },
    ],
    examples: [
      'generate-spec',
      'generate-spec --limit 500 --output ./custom-spec.md',
    ],
  },
  {
    name: 'create-tenant',
    label: 'Create Tenant',
    description: 'Create Azure tenant from specification',
    icon: <AddCircleIcon />,
    category: 'Core',
    args: [
      { name: 'spec', label: 'Spec File', type: 'string', required: true, description: 'Path to tenant specification markdown file' },
    ],
    examples: [
      'create-tenant --spec ./tenant-spec.md',
    ],
  },
  {
    name: 'visualize',
    label: 'Visualize',
    description: 'Generate graph visualization from existing Neo4j data',
    icon: <VisibilityIcon />,
    category: 'Analysis',
    args: [
      { name: 'link-hierarchy', label: 'Link Hierarchy', type: 'boolean', description: 'Enable hierarchical edges' },
      { name: 'no-container', label: 'No Container', type: 'boolean', description: 'Do not auto-start Neo4j container' },
    ],
    examples: [
      'visualize',
      'visualize --link-hierarchy',
    ],
  },
  {
    name: 'agent-mode',
    label: 'Agent Mode',
    description: 'Start AutoGen MCP agent mode',
    icon: <PsychologyIcon />,
    category: 'Analysis',
    args: [
      { name: 'question', label: 'Question', type: 'string', description: 'Ask a single question and exit' },
    ],
    examples: [
      'agent-mode',
      'agent-mode --question "What are the security risks in this tenant?"',
    ],
  },
  {
    name: 'threat-model',
    label: 'Threat Model',
    description: 'Generate threat model and security analysis',
    icon: <SecurityIcon />,
    category: 'Analysis',
    args: [],
    examples: [
      'threat-model',
    ],
  },
  {
    name: 'test',
    label: 'Test Build',
    description: 'Run test with limited resources to validate setup',
    icon: <BuildIcon />,
    category: 'Utility',
    args: [
      { name: 'tenant-id', label: 'Tenant ID', type: 'string', description: 'Azure tenant ID (defaults to env)' },
      { name: 'limit', label: 'Resource Limit', type: 'number', default: 50, min: 1, max: 1000, description: 'Maximum resources to process' },
    ],
    examples: [
      'test',
      'test --tenant-id contoso.onmicrosoft.com --limit 20',
    ],
  },
  {
    name: 'doctor',
    label: 'Doctor',
    description: 'Check system dependencies and fix missing ones automatically',
    icon: <SecurityIcon />,
    category: 'Utility',
    args: [],
    examples: [
      'doctor',
    ],
  },
];

interface CommandHistoryItem {
  id: string;
  command: string;
  args: string[];
  timestamp: Date;
  status: 'running' | 'completed' | 'error';
  output?: string[];
}

const CLITab: React.FC = () => {
  const { state } = useApp();
  const { isConnected, subscribeToProcess, unsubscribeFromProcess, getProcessOutput } = useWebSocket();
  const [searchParams] = useSearchParams();
  
  // Terminal state
  const terminalRef = useRef<HTMLDivElement>(null);
  const terminalInstance = useRef<Terminal | null>(null);
  
  // Command state
  const [selectedCommand, setSelectedCommand] = useState<string>('build');
  const [commandArgs, setCommandArgs] = useState<Record<string, any>>({});
  const [isRunning, setIsRunning] = useState(false);
  const [currentProcessId, setCurrentProcessId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // History state
  const [commandHistory, setCommandHistory] = useState<CommandHistoryItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  
  // Output state
  const [terminalOutput, setTerminalOutput] = useState<string[]>([]);
  const [processSocket, setProcessSocket] = useState<Socket | null>(null);

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
      terminalInstance.current.write('Terminal cleared.\r\n');
    }
    setTerminalOutput([]);
  }, []);

  // Resize window when CLI tab is mounted
  useEffect(() => {
    const resizeWindow = async () => {
      try {
        if (window.electronAPI?.window?.resize) {
          await window.electronAPI.window.resize(1600, 1200);
          console.log('Window resized for CLI tab');
        }
      } catch (error) {
        console.error('Failed to resize window:', error);
      }
    };

    resizeWindow();
  }, []); // Run once on mount

  // Initialize terminal
  useEffect(() => {
    if (terminalRef.current && !terminalInstance.current) {
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
      term.writeln('Azure Tenant Grapher CLI Interface');
      term.writeln('Select a command and configure its parameters, then click Execute.');
      term.writeln('');
      
      terminalInstance.current = term;
    }
    
    return () => {
      // Don't dispose terminal on unmount - keep it alive
    };
  }, []);

  // Set up WebSocket for process events
  useEffect(() => {
    if (isConnected && !processSocket) {
      const socket = io('http://localhost:3001');
      
      socket.on('connect', () => {
        console.log('CLI tab: Process event socket connected');
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
          
          setIsRunning(false);
          setCurrentProcessId(null);
          
          // Update history - find the most recent running item for this process
          setCommandHistory(prev => 
            prev.map((item, index) => 
              index === 0 && item.status === 'running'
                ? { ...item, status: event.code === 0 ? 'completed' : 'error' }
                : item
            )
          );
          
          unsubscribeFromProcess(event.processId);
        }
      });
      
      socket.on('process-error', (event: any) => {
        if (event.processId === currentProcessId) {
          writeToTerminal(`Process error: ${event.error}`, '31'); // Red color
          setIsRunning(false);
          setCurrentProcessId(null);
          setError(`Process error: ${event.error}`);
          
          // Update history - find the most recent running item for this process
          setCommandHistory(prev => 
            prev.map((item, index) => 
              index === 0 && item.status === 'running'
                ? { ...item, status: 'error' }
                : item
            )
          );
          
          unsubscribeFromProcess(event.processId);
        }
      });
      
      setProcessSocket(socket);
    }
    
    return () => {
      if (processSocket) {
        processSocket.disconnect();
        setProcessSocket(null);
      }
    };
  }, [isConnected, processSocket, currentProcessId, unsubscribeFromProcess, writeToTerminal]);

  // Monitor process output from the main WebSocket hook
  useEffect(() => {
    if (currentProcessId && isRunning) {
      const processOutput = getProcessOutput(currentProcessId);
      if (processOutput.length > terminalOutput.length) {
        const newLines = processOutput.slice(terminalOutput.length);
        newLines.forEach(line => {
          writeToTerminal(line);
        });
        setTerminalOutput(processOutput);
      }
    }
  }, [currentProcessId, isRunning, getProcessOutput, terminalOutput.length, writeToTerminal]);

  // Handle auto-command execution from URL parameters
  useEffect(() => {
    const autoCommand = searchParams.get('autoCommand');
    if (autoCommand && isConnected && !isRunning && terminalInstance.current) {
      const commandExists = CLI_COMMANDS.find(cmd => cmd.name === autoCommand);
      if (commandExists) {
        // Set the command and execute it automatically
        setSelectedCommand(autoCommand);
        
        // Clear any existing args and set defaults
        const defaults: Record<string, any> = {};
        commandExists.args.forEach(arg => {
          if (arg.default !== undefined) {
            defaults[arg.name] = arg.default;
          }
        });
        setCommandArgs(defaults);
        
        // Execute after a short delay to ensure everything is initialized
        const timeoutId = setTimeout(() => {
          writeToTerminal(`Auto-executing command: atg ${autoCommand}`, '36'); // Cyan color
          
          // Execute the command inline to avoid circular dependency
          const args: string[] = [];
          commandExists.args.forEach(argDef => {
            const value = defaults[argDef.name];
            if (value !== undefined && value !== null && value !== '') {
              if (argDef.type === 'boolean') {
                if (value === true) {
                  args.push(`--${argDef.name}`);
                }
              } else {
                args.push(`--${argDef.name}`, String(value));
              }
            }
          });
          
          const commandLine = `${commandExists.name} ${args.join(' ')}`;
          writeToTerminal(`$ atg ${commandLine}`, '32'); // Green color
          
          // Add to history
          const historyItem = {
            id: `${Date.now()}-${Math.random()}`,
            command: commandExists.name,
            args,
            timestamp: new Date(),
            status: 'running' as const,
          };
          setCommandHistory(prev => [historyItem, ...prev]);
          setIsRunning(true);
          
          // Execute via backend API
          axios.post('http://localhost:3001/api/execute', {
            command: commandExists.name,
            args: args
          }).then(response => {
            const processId = response.data.processId;
            setCurrentProcessId(processId);
            writeToTerminal(`Process started with ID: ${processId}`, '36'); // Cyan color
            subscribeToProcess(processId);
          }).catch(err => {
            const errorMessage = err.response?.data?.error || err.message;
            setError(errorMessage);
            setIsRunning(false);
            writeToTerminal(`Error: ${errorMessage}`, '31'); // Red color
            setCommandHistory(prev => 
              prev.map((item, index) => 
                index === 0 && item.status === 'running'
                  ? { ...item, status: 'error' as const }
                  : item
              )
            );
          });
        }, 500);
        
        return () => clearTimeout(timeoutId);
      }
    }
  }, [searchParams, isConnected, isRunning, writeToTerminal, subscribeToProcess]);

  // Get selected command definition
  const getSelectedCommandDef = (): CommandDefinition | undefined => {
    return CLI_COMMANDS.find(cmd => cmd.name === selectedCommand);
  };

  // Handle command selection
  const handleCommandChange = (event: SelectChangeEvent) => {
    const newCommand = event.target.value;
    setSelectedCommand(newCommand);
    setCommandArgs({});
    setError(null);
    
    // Set default values for the new command
    const commandDef = CLI_COMMANDS.find(cmd => cmd.name === newCommand);
    if (commandDef) {
      const defaults: Record<string, any> = {};
      commandDef.args.forEach(arg => {
        if (arg.default !== undefined) {
          defaults[arg.name] = arg.default;
        }
      });
      setCommandArgs(defaults);
    }
  };

  // Handle argument changes
  const handleArgChange = (argName: string, value: any) => {
    setCommandArgs(prev => ({
      ...prev,
      [argName]: value
    }));
  };

  // Build command line from current selection
  const buildCommandLine = (): string[] => {
    const commandDef = getSelectedCommandDef();
    if (!commandDef) return [];
    
    const args: string[] = [];
    
    commandDef.args.forEach(argDef => {
      const value = commandArgs[argDef.name];
      
      if (value !== undefined && value !== null && value !== '') {
        if (argDef.type === 'boolean') {
          if (value === true) {
            args.push(`--${argDef.name}`);
          }
        } else {
          args.push(`--${argDef.name}`, String(value));
        }
      }
    });
    
    return args;
  };

  // Execute command
  const executeCommand = async () => {
    const commandDef = getSelectedCommandDef();
    if (!commandDef) return;

    if (!isConnected) {
      setError('Not connected to backend server. Please check if the backend is running.');
      return;
    }

    // Validate required arguments
    const missingArgs: string[] = [];
    commandDef.args.forEach(argDef => {
      if (argDef.required && (!commandArgs[argDef.name] || commandArgs[argDef.name] === '')) {
        missingArgs.push(argDef.label);
      }
    });

    if (missingArgs.length > 0) {
      setError(`Missing required arguments: ${missingArgs.join(', ')}`);
      return;
    }

    setError(null);
    setIsRunning(true);
    
    const args = buildCommandLine();
    const commandLine = `${commandDef.name} ${args.join(' ')}`;
    
    // Write command to terminal
    writeToTerminal(`$ atg ${commandLine}`, '32'); // Green color
    
    // Add to history
    const historyItem: CommandHistoryItem = {
      id: `${Date.now()}-${Math.random()}`,
      command: commandDef.name,
      args,
      timestamp: new Date(),
      status: 'running',
    };
    setCommandHistory(prev => [historyItem, ...prev]);

    try {
      // Execute via backend API
      const response = await axios.post('http://localhost:3001/api/execute', {
        command: commandDef.name,
        args: args
      });
      
      const processId = response.data.processId;
      setCurrentProcessId(processId);
      
      writeToTerminal(`Process started with ID: ${processId}`, '36'); // Cyan color
      
      // Subscribe to process output
      subscribeToProcess(processId);
      
    } catch (err: any) {
      const errorMessage = err.response?.data?.error || err.message;
      setError(errorMessage);
      setIsRunning(false);
      writeToTerminal(`Error: ${errorMessage}`, '31'); // Red color
      
      setCommandHistory(prev => 
        prev.map((item, index) => 
          index === 0 && item.status === 'running'
            ? { ...item, status: 'error' }
            : item
        )
      );
    }
  };

  // Stop running command
  const stopCommand = async () => {
    if (currentProcessId) {
      try {
        await axios.post(`http://localhost:3001/api/cancel/${currentProcessId}`);
        writeToTerminal('Process cancelled by user', '33'); // Yellow color
        setIsRunning(false);
        setCurrentProcessId(null);
        unsubscribeFromProcess(currentProcessId);
      } catch (err: any) {
        setError(`Failed to stop process: ${err.message}`);
      }
    }
  };

  // Copy command to clipboard
  const copyCommand = () => {
    const args = buildCommandLine();
    const commandLine = `atg ${selectedCommand} ${args.join(' ')}`;
    navigator.clipboard.writeText(commandLine);
  };

  // Load command from history
  const loadFromHistory = (historyItem: CommandHistoryItem) => {
    setSelectedCommand(historyItem.command);
    
    // Reconstruct args object from command line args
    const newArgs: Record<string, any> = {};
    const commandDef = CLI_COMMANDS.find(cmd => cmd.name === historyItem.command);
    
    if (commandDef) {
      for (let i = 0; i < historyItem.args.length; i += 2) {
        const argName = historyItem.args[i].replace('--', '');
        const argValue = historyItem.args[i + 1];
        const argDef = commandDef.args.find(a => a.name === argName);
        
        if (argDef) {
          if (argDef.type === 'boolean') {
            newArgs[argName] = true;
          } else if (argDef.type === 'number') {
            newArgs[argName] = parseInt(argValue, 10);
          } else {
            newArgs[argName] = argValue;
          }
        }
      }
    }
    
    setCommandArgs(newArgs);
    setShowHistory(false);
  };

  const commandDef = getSelectedCommandDef();
  const commandLine = commandDef ? `atg ${selectedCommand} ${buildCommandLine().join(' ')}` : '';

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 2 }}>
      {/* Connection Status */}
      {!isConnected && (
        <Alert severity="warning">
          Not connected to backend server. Some functionality may be unavailable.
        </Alert>
      )}

      {/* Error Display */}
      {error && (
        <Alert severity="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Grid container spacing={2} sx={{ flex: 1 }}>
        {/* Left Panel - Command Configuration */}
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 2, height: '100%', overflow: 'auto' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
              <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <TerminalIcon />
                Command Builder
              </Typography>
              <Box>
                <Tooltip title="Command History">
                  <IconButton onClick={() => setShowHistory(true)}>
                    <HistoryIcon />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Copy Command">
                  <IconButton onClick={copyCommand}>
                    <CopyIcon />
                  </IconButton>
                </Tooltip>
              </Box>
            </Box>

            {/* Command Selection */}
            <FormControl fullWidth sx={{ mb: 2 }}>
              <InputLabel>Command</InputLabel>
              <Select
                value={selectedCommand}
                onChange={handleCommandChange}
                label="Command"
                disabled={isRunning}
              >
                {CLI_COMMANDS.map((cmd) => (
                  <MenuItem key={cmd.name} value={cmd.name}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      {cmd.icon}
                      <Box>
                        <Typography variant="body2">{cmd.label}</Typography>
                        <Typography variant="caption" color="text.secondary">
                          {cmd.category}
                        </Typography>
                      </Box>
                    </Box>
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            {/* Command Description */}
            {commandDef && (
              <Alert severity="info" sx={{ mb: 2 }}>
                {commandDef.description}
              </Alert>
            )}

            {/* Command Arguments */}
            {commandDef && commandDef.args.length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  Arguments:
                </Typography>
                {commandDef.args.map((arg) => (
                  <Box key={arg.name} sx={{ mb: 2 }}>
                    {arg.type === 'boolean' ? (
                      <FormControlLabel
                        control={
                          <Checkbox
                            checked={commandArgs[arg.name] || false}
                            onChange={(e) => handleArgChange(arg.name, e.target.checked)}
                            disabled={isRunning}
                          />
                        }
                        label={
                          <Box>
                            <Typography variant="body2">
                              {arg.label}
                              {arg.required && <span style={{ color: 'red' }}> *</span>}
                            </Typography>
                            {arg.description && (
                              <Typography variant="caption" color="text.secondary">
                                {arg.description}
                              </Typography>
                            )}
                          </Box>
                        }
                      />
                    ) : arg.type === 'select' ? (
                      <FormControl fullWidth size="small">
                        <InputLabel>{arg.label}</InputLabel>
                        <Select
                          value={commandArgs[arg.name] || arg.default || ''}
                          onChange={(e) => handleArgChange(arg.name, e.target.value)}
                          label={arg.label}
                          disabled={isRunning}
                        >
                          {arg.options?.map((option) => (
                            <MenuItem key={option} value={option}>
                              {option}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    ) : arg.type === 'number' && arg.min !== undefined && arg.max !== undefined ? (
                      <Box>
                        <Typography variant="body2" sx={{ mb: 1 }}>
                          {arg.label}: {commandArgs[arg.name] || arg.default || arg.min}
                          {arg.required && <span style={{ color: 'red' }}> *</span>}
                        </Typography>
                        <Slider
                          value={commandArgs[arg.name] || arg.default || arg.min}
                          onChange={(_, value) => handleArgChange(arg.name, value)}
                          min={arg.min}
                          max={arg.max}
                          marks
                          disabled={isRunning}
                        />
                      </Box>
                    ) : (
                      <TextField
                        fullWidth
                        size="small"
                        label={arg.label}
                        value={commandArgs[arg.name] || ''}
                        onChange={(e) => handleArgChange(arg.name, 
                          arg.type === 'number' ? parseInt(e.target.value, 10) || '' : e.target.value
                        )}
                        type={arg.type === 'number' ? 'number' : 'text'}
                        required={arg.required}
                        disabled={isRunning}
                        helperText={arg.description}
                      />
                    )}
                  </Box>
                ))}
              </Box>
            )}

            {/* Generated Command Line */}
            <Paper variant="outlined" sx={{ p: 1, mb: 2, bgcolor: 'grey.100' }}>
              <Typography variant="caption" color="text.secondary">
                Command Line:
              </Typography>
              <Typography variant="body2" fontFamily="monospace">
                {commandLine}
              </Typography>
            </Paper>

            {/* Execute Button */}
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                variant="contained"
                color="primary"
                startIcon={isRunning ? <StopIcon /> : <PlayIcon />}
                onClick={isRunning ? stopCommand : executeCommand}
                disabled={!isConnected}
                fullWidth
              >
                {isRunning ? 'Stop' : 'Execute'}
              </Button>
            </Box>

            {/* Examples */}
            {commandDef && commandDef.examples && (
              <Accordion sx={{ mt: 2 }}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="subtitle2">Examples</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  {commandDef.examples.map((example, index) => (
                    <Box key={index} sx={{ mb: 1 }}>
                      <Typography variant="body2" fontFamily="monospace" sx={{ bgcolor: 'grey.100', p: 1, borderRadius: 1 }}>
                        atg {example}
                      </Typography>
                    </Box>
                  ))}
                </AccordionDetails>
              </Accordion>
            )}
          </Paper>
        </Grid>

        {/* Right Panel - Terminal Output */}
        <Grid item xs={12} md={8}>
          <Paper sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <TerminalIcon />
                Terminal Output
              </Typography>
              <Tooltip title="Clear Terminal">
                <IconButton onClick={clearTerminal}>
                  <ClearIcon />
                </IconButton>
              </Tooltip>
            </Box>
            <Box
              ref={terminalRef}
              sx={{
                flex: 1,
                overflow: 'hidden',
                backgroundColor: '#1e1e1e',
                minHeight: '400px',
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
          </Paper>
        </Grid>
      </Grid>

      {/* Command History Dialog */}
      <Dialog open={showHistory} onClose={() => setShowHistory(false)} maxWidth="md" fullWidth>
        <DialogTitle>Command History</DialogTitle>
        <DialogContent>
          <List>
            {commandHistory.map((item) => (
              <ListItem key={item.id}>
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Chip
                        size="small"
                        label={item.status}
                        color={
                          item.status === 'completed' ? 'success' :
                          item.status === 'error' ? 'error' : 'default'
                        }
                      />
                      <Typography fontFamily="monospace">
                        atg {item.command} {item.args.join(' ')}
                      </Typography>
                    </Box>
                  }
                  secondary={item.timestamp.toLocaleString()}
                />
                <ListItemSecondaryAction>
                  <Button size="small" onClick={() => loadFromHistory(item)}>
                    Load
                  </Button>
                </ListItemSecondaryAction>
              </ListItem>
            ))}
            {commandHistory.length === 0 && (
              <ListItem>
                <ListItemText primary="No commands executed yet" />
              </ListItem>
            )}
          </List>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowHistory(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default CLITab;