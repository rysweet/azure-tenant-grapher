import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Paper,
  TextField,
  IconButton,
  Typography,
  List,
  ListItem,
  ListItemText,
  Divider,
  Alert,
  CircularProgress,
  Chip,
  Stack,
  Grid,
  Button,
  Card,
  CardContent,
  CardActions,
  Tooltip,
} from '@mui/material';
import {
  Send as SendIcon,
  SmartToy as AIIcon,
  Person as PersonIcon,
  Terminal as TerminalIcon,
  Clear as ClearIcon,
} from '@mui/icons-material';

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
}

interface ConsoleOutput {
  type: 'stdout' | 'stderr' | 'info';
  content: string;
  timestamp: Date;
}

interface SampleQuery {
  title: string;
  query: string;
  description: string;
}

const sampleQueries: SampleQuery[] = [
  {
    title: 'Resource Groups',
    query: 'How many resource groups are in the tenant?',
    description: 'Count all resource groups'
  },
  {
    title: 'Key Vaults',
    query: 'Which resource groups have key vaults?',
    description: 'Find resource groups containing Key Vaults'
  },
  {
    title: 'Virtual Networks',
    query: 'List all virtual networks and their address spaces',
    description: 'Show VNet configurations'
  },
  {
    title: 'Storage Accounts',
    query: 'What storage accounts exist and what are their configurations?',
    description: 'List storage account details'
  },
  {
    title: 'Network Security',
    query: 'Show me all network security groups and their rules',
    description: 'Analyze NSG configurations'
  },
  {
    title: 'Identity Resources',
    query: 'List all service principals and managed identities',
    description: 'Show identity resources'
  },
  {
    title: 'Database Resources',
    query: 'What databases are deployed in the tenant?',
    description: 'Find all database resources'
  },
  {
    title: 'Resource Dependencies',
    query: 'Show the dependencies between resources in the tenant',
    description: 'Analyze resource relationships'
  }
];

const AgentModeTab: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [consoleOutput, setConsoleOutput] = useState<ConsoleOutput[]>([]);
  const [input, setInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentProcessId, setCurrentProcessId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const consoleEndRef = useRef<HTMLDivElement>(null);

  const scrollChatToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const scrollConsoleToBottom = () => {
    consoleEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollChatToBottom();
  }, [messages]);

  useEffect(() => {
    scrollConsoleToBottom();
  }, [consoleOutput]);

  // Set up event listeners for process output
  useEffect(() => {
    const handleProcessOutput = (data: any) => {
      console.log('Process output received:', data);
      
      if (currentProcessId && data.id === currentProcessId) {
        const lines = Array.isArray(data.data) ? data.data : [data.data];
        lines.forEach((line: string) => {
          // Always add to console output, even if empty
          const output: ConsoleOutput = {
            type: data.type === 'stderr' ? 'stderr' : 'stdout',
            content: line || '',
            timestamp: new Date(),
          };
          setConsoleOutput(prev => [...prev, output]);
          
          // Parse for important messages to add to chat
          if (line && line.trim()) {
            if (line.includes('🎯 Final Answer:') || 
                line.includes('✅') || 
                line.includes('❌') ||
                line.includes('🔄')) {
              const assistantMessage: Message = {
                role: 'assistant',
                content: line,
                timestamp: new Date(),
              };
              setMessages(prev => [...prev, assistantMessage]);
            }
          }
        });
      }
    };

    const handleProcessExit = (data: any) => {
      console.log('Process exit received:', data);
      
      if (currentProcessId && data.id === currentProcessId) {
        setIsProcessing(false);
        setCurrentProcessId(null);
        
        // Add console message
        const exitOutput: ConsoleOutput = {
          type: 'info',
          content: `\n=== Process exited with code ${data.code} ===\n`,
          timestamp: new Date(),
        };
        setConsoleOutput(prev => [...prev, exitOutput]);
        
        // Add chat message if exit was not successful
        if (data.code !== 0) {
          const errorMessage: Message = {
            role: 'system',
            content: `Process failed with exit code ${data.code}. Check console output for details.`,
            timestamp: new Date(),
          };
          setMessages(prev => [...prev, errorMessage]);
        }
      }
    };

    const handleProcessError = (data: any) => {
      console.log('Process error received:', data);
      
      if (currentProcessId && data.id === currentProcessId) {
        const errorOutput: ConsoleOutput = {
          type: 'stderr',
          content: `Error: ${data.error}`,
          timestamp: new Date(),
        };
        setConsoleOutput(prev => [...prev, errorOutput]);
      }
    };

    // Subscribe to events
    window.electronAPI.on('process:output', handleProcessOutput);
    window.electronAPI.on('process:exit', handleProcessExit);
    window.electronAPI.on('process:error', handleProcessError);

    // Cleanup
    return () => {
      window.electronAPI.off('process:output', handleProcessOutput);
      window.electronAPI.off('process:exit', handleProcessExit);
      window.electronAPI.off('process:error', handleProcessError);
    };
  }, [currentProcessId]);

  const handleSend = async (queryText?: string) => {
    const messageText = queryText || input;
    if (!messageText.trim()) return;

    const userMessage: Message = {
      role: 'user',
      content: messageText,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsProcessing(true);

    // Clear console for new query
    setConsoleOutput([{
      type: 'info',
      content: `=== Executing: atg agent-mode --question "${messageText}" ===\n`,
      timestamp: new Date(),
    }]);

    try {
      // Execute with --question parameter
      const result = await window.electronAPI.cli.execute('agent-mode', ['--question', messageText]);
      console.log('CLI execute result:', result);
      
      if (result.success && result.data?.id) {
        setCurrentProcessId(result.data.id);
        
        // Add console info
        const startOutput: ConsoleOutput = {
          type: 'info',
          content: `Process ID: ${result.data.id}\n`,
          timestamp: new Date(),
        };
        setConsoleOutput(prev => [...prev, startOutput]);
      } else {
        throw new Error(result.error || 'Failed to start agent mode');
      }
    } catch (err: any) {
      setIsProcessing(false);
      
      const errorMessage: Message = {
        role: 'system',
        content: `Error: ${err.message}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
      
      const errorOutput: ConsoleOutput = {
        type: 'stderr',
        content: `Error: ${err.message}\n`,
        timestamp: new Date(),
      };
      setConsoleOutput(prev => [...prev, errorOutput]);
    }
  };

  const clearAll = () => {
    setMessages([]);
    setConsoleOutput([]);
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', p: 2 }}>
      {/* Header */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="h5" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <AIIcon color="primary" />
          AI Agent Mode
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Ask questions about your Azure tenant graph using natural language
        </Typography>
      </Box>

      {/* Sample Queries - Scrollable */}
      <Box sx={{ mb: 2, maxHeight: '120px', overflowY: 'auto' }}>
        <Stack direction="row" spacing={1} sx={{ flexWrap: 'nowrap', minWidth: 'min-content' }}>
          {sampleQueries.map((sample, index) => (
            <Tooltip key={index} title={sample.description} arrow>
              <Chip
                label={sample.title}
                onClick={() => !isProcessing && handleSend(sample.query)}
                disabled={isProcessing}
                color="primary"
                variant="outlined"
                sx={{ 
                  cursor: isProcessing ? 'not-allowed' : 'pointer',
                  minWidth: 'fit-content',
                  whiteSpace: 'nowrap'
                }}
              />
            </Tooltip>
          ))}
        </Stack>
      </Box>

      {/* Main Content - Split View */}
      <Grid container spacing={2} sx={{ flex: 1, minHeight: 0 }}>
        {/* Chat Panel */}
        <Grid item xs={12} md={6}>
          <Paper 
            elevation={2} 
            sx={{ 
              height: '100%', 
              display: 'flex', 
              flexDirection: 'column',
              bgcolor: 'background.paper'
            }}
          >
            <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Typography variant="h6">Chat</Typography>
              <IconButton size="small" onClick={clearAll} disabled={isProcessing}>
                <ClearIcon />
              </IconButton>
            </Box>
            
            <List 
              sx={{ 
                flex: 1, 
                overflow: 'auto', 
                p: 2,
                bgcolor: 'background.default'
              }}
            >
              {messages.length === 0 ? (
                <Box sx={{ textAlign: 'center', py: 4 }}>
                  <AIIcon sx={{ fontSize: 48, color: 'text.disabled', mb: 2 }} />
                  <Typography color="text.secondary">
                    Start by asking a question about your Azure tenant
                  </Typography>
                </Box>
              ) : (
                messages.map((message, index) => (
                  <ListItem
                    key={index}
                    sx={{
                      flexDirection: 'column',
                      alignItems: 'flex-start',
                      mb: 2,
                      bgcolor: message.role === 'user' ? 'primary.light' : 
                               message.role === 'system' ? 'info.light' : 
                               'background.paper',
                      borderRadius: 1,
                      boxShadow: 1,
                    }}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                      {message.role === 'user' ? (
                        <PersonIcon fontSize="small" />
                      ) : (
                        <AIIcon fontSize="small" />
                      )}
                      <Typography variant="subtitle2" fontWeight="bold">
                        {message.role === 'user' ? 'You' : 
                         message.role === 'system' ? 'System' : 'Assistant'}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {message.timestamp.toLocaleTimeString()}
                      </Typography>
                    </Box>
                    <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', width: '100%' }}>
                      {message.content}
                    </Typography>
                  </ListItem>
                ))
              )}
              <div ref={messagesEndRef} />
            </List>
          </Paper>
        </Grid>

        {/* Console Panel */}
        <Grid item xs={12} md={6}>
          <Paper 
            elevation={2} 
            sx={{ 
              height: '100%', 
              display: 'flex', 
              flexDirection: 'column',
              bgcolor: 'background.paper'
            }}
          >
            <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider', display: 'flex', alignItems: 'center', gap: 1 }}>
              <TerminalIcon />
              <Typography variant="h6">Console Output</Typography>
              {isProcessing && <CircularProgress size={20} />}
            </Box>
            
            <Box 
              sx={{ 
                flex: 1, 
                overflow: 'auto', 
                p: 2,
                bgcolor: '#1e1e1e',
                fontFamily: 'monospace',
                fontSize: '0.875rem'
              }}
            >
              {consoleOutput.length === 0 ? (
                <Typography sx={{ color: '#888', fontFamily: 'monospace' }}>
                  Console output will appear here...
                </Typography>
              ) : (
                consoleOutput.map((output, index) => (
                  <Box
                    key={index}
                    sx={{
                      color: output.type === 'stderr' ? '#ff6b6b' : 
                             output.type === 'info' ? '#4fc3f7' : 
                             '#90ee90',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                      lineHeight: 1.5,
                    }}
                  >
                    {output.content}
                  </Box>
                ))
              )}
              <div ref={consoleEndRef} />
            </Box>
          </Paper>
        </Grid>
      </Grid>

      {/* Input Area */}
      <Box sx={{ mt: 2 }}>
        <Paper elevation={2} sx={{ p: 2 }}>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <TextField
              fullWidth
              variant="outlined"
              placeholder="Ask about your Azure tenant (e.g., 'Which resource groups have key vaults?')"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              disabled={isProcessing}
              multiline
              maxRows={3}
            />
            <IconButton
              color="primary"
              onClick={() => handleSend()}
              disabled={isProcessing || !input.trim()}
              sx={{ alignSelf: 'flex-end' }}
            >
              {isProcessing ? <CircularProgress size={24} /> : <SendIcon />}
            </IconButton>
          </Box>
        </Paper>
      </Box>
    </Box>
  );
};

export default AgentModeTab;