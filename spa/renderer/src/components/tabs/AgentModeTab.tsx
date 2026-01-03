import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Paper,
  TextField,
  IconButton,
  Typography,
  List,
  ListItem,
  Divider,
  CircularProgress,
  Chip,
  Stack,
  Grid,
  Button,
  Card,
  CardContent,
  CardActions,
  Menu,
  MenuItem,
} from '@mui/material';
import {
  Send as SendIcon,
  SmartToy as AIIcon,
  Person as PersonIcon,
  Terminal as TerminalIcon,
  Clear as ClearIcon,
  ArrowBack as ArrowBackIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  MoreVert as MoreVertIcon,
  Chat as ChatIcon,
} from '@mui/icons-material';
import { useChatSessions, Message, ConsoleOutput } from '../../hooks/useChatSessions';
import { useWebSocketContext } from '../../context/WebSocketContext';
import axios from 'axios';

interface SampleQuery {
  title: string;
  query: string;
  description: string;
  icon?: string;
}

const sampleQueries: SampleQuery[] = [
  {
    title: 'Count Resources',
    query: 'How many resource groups are in the tenant?',
    description: 'Get a count of all resource groups in your Azure tenant',
    icon: '📊',
  },
  {
    title: 'Find Key Vaults',
    query: 'Which resource groups have key vaults?',
    description: 'Identify resource groups containing Azure Key Vaults',
    icon: '🔐',
  },
  {
    title: 'List Virtual Networks',
    query: 'List all virtual networks and their address spaces',
    description: 'Show all VNets with their CIDR blocks and configurations',
    icon: '🌐',
  },
  {
    title: 'Storage Accounts',
    query: 'What storage accounts exist and what are their configurations?',
    description: 'Enumerate storage accounts with their settings',
    icon: '💾',
  },
  {
    title: 'Network Security',
    query: 'Show me all network security groups and their rules',
    description: 'Analyze NSG rules and configurations across the tenant',
    icon: '🛡️',
  },
  {
    title: 'Identity Resources',
    query: 'List all service principals and managed identities',
    description: 'Show all identity resources in the tenant',
    icon: '👤',
  },
  {
    title: 'Database Resources',
    query: 'What databases are deployed in the tenant?',
    description: 'Find all SQL, Cosmos DB, and other database resources',
    icon: '🗄️',
  },
  {
    title: 'Resource Dependencies',
    query: 'Show the dependencies between resources in the tenant',
    description: 'Analyze relationships and dependencies between Azure resources',
    icon: '🔗',
  },
];

const AgentModeTab: React.FC = () => {
  const [showLanding, setShowLanding] = useState(true);
  const [input, setInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentProcessId, setCurrentProcessId] = useState<string | null>(null);
  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const consoleEndRef = useRef<HTMLDivElement>(null);
  const processedOutputCount = useRef<number>(0);
  const { subscribeToProcess, unsubscribeFromProcess, getProcessOutput, outputs, onProcessExit } = useWebSocketContext();

  const {
    sessions,
    activeSessionId,
    getActiveSession,
    createSession,
    addMessage,
    addConsoleOutput,
    clearSession,
    deleteSession,
    switchSession,
    clearAllSessions
  } = useChatSessions();

  const activeSession = getActiveSession();

  // Check if we should show the landing page
  useEffect(() => {
    if (activeSession && activeSession.messages.length > 0) {
      setShowLanding(false);
    }
  }, [activeSession]);

  const scrollChatToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const scrollConsoleToBottom = () => {
    consoleEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollChatToBottom();
  }, [activeSession?.messages]);

  useEffect(() => {
    scrollConsoleToBottom();
  }, [activeSession?.consoleOutput]);

  // Subscribe to process on mount
  useEffect(() => {
    if (currentProcessId) {
      subscribeToProcess(currentProcessId);
      processedOutputCount.current = 0; // Reset counter for new process
      return () => {
        unsubscribeFromProcess(currentProcessId);
      };
    }
  }, [currentProcessId, subscribeToProcess, unsubscribeFromProcess]);

  // Handle process exit
  useEffect(() => {
    if (!currentProcessId || !activeSessionId) {
      return;
    }

    const unsubscribe = onProcessExit(currentProcessId, (event) => {
      setIsProcessing(false);
      setCurrentProcessId(null);

      // Add console message
      const exitOutput: ConsoleOutput = {
        type: 'info',
        content: `\n=== Process exited with code ${event.code ?? 'unknown'} ===\n`,
        timestamp: new Date(),
      };
      addConsoleOutput(activeSessionId, exitOutput);

      // Add chat message if exit was not successful
      if (event.code !== 0) {
        const errorMessage: Message = {
          role: 'system',
          content: `Process failed with exit code ${event.code}. Check console output for details.`,
          timestamp: new Date(),
        };
        addMessage(activeSessionId, errorMessage);
      }
    });

    return unsubscribe;
  }, [currentProcessId, activeSessionId, onProcessExit, addMessage, addConsoleOutput]);

  // Watch for output changes and update console
  useEffect(() => {
    if (!currentProcessId || !activeSessionId) {
      return;
    }

    const processOutputs = outputs.get(currentProcessId);
    if (!processOutputs || processOutputs.length === 0) {
      return;
    }

    // Only process new outputs (outputs we haven't seen before)
    const newOutputs = processOutputs.slice(processedOutputCount.current);
    if (newOutputs.length === 0) {
      return;
    }

    // Process only new output data
    newOutputs.forEach((outputData) => {
      const lines = Array.isArray(outputData.data) ? outputData.data : [outputData.data];
      lines.forEach((line: string) => {
        if (!line) return;

        const consoleOutput: ConsoleOutput = {
          type: outputData.type === 'stderr' ? 'stderr' : 'stdout',
          content: line,
          timestamp: new Date(),
        };
        addConsoleOutput(activeSessionId, consoleOutput);

        // Parse for important messages to add to chat
        if (line.trim()) {
          if (line.includes('🎯 Final Answer:') ||
              line.includes('✅') ||
              line.includes('❌') ||
              line.includes('🔄')) {
            const assistantMessage: Message = {
              role: 'assistant',
              content: line,
              timestamp: new Date(),
            };
            addMessage(activeSessionId, assistantMessage);
          }
        }
      });
    });

    // Update the processed count
    processedOutputCount.current = processOutputs.length;
  }, [outputs, currentProcessId, activeSessionId, addMessage, addConsoleOutput]);

  const handleSend = async (queryText?: string) => {
    const messageText = queryText || input;
    if (!messageText.trim()) return;

    // Create a new session if we don't have one or if we're on the landing page
    let sessionId = activeSessionId;
    if (!sessionId || showLanding) {
      const session = createSession(`Q: ${messageText.substring(0, 50)}...`);
      sessionId = session.id;
    }

    // Switch to chat view
    setShowLanding(false);

    const userMessage: Message = {
      role: 'user',
      content: messageText,
      timestamp: new Date(),
    };

    addMessage(sessionId, userMessage);
    setInput('');
    setIsProcessing(true);

    // Clear console for new query (within the same session)
    const startOutput: ConsoleOutput = {
      type: 'info',
      content: `=== Executing: atg agent-mode --question "${messageText}" ===\n`,
      timestamp: new Date(),
    };
    addConsoleOutput(sessionId, startOutput);

    try {
      // Execute via backend API (works in both browser and Electron)
      const result = await axios.post('http://localhost:3001/api/execute', {
        command: 'agent-mode',
        args: ['--question', messageText]
      });

      if (result.data?.processId) {
        setCurrentProcessId(result.data.processId);

        // Add console info
        const processOutput: ConsoleOutput = {
          type: 'info',
          content: `Process ID: ${result.data.processId}\n`,
          timestamp: new Date(),
        };
        addConsoleOutput(sessionId, processOutput);
      } else {
        throw new Error(result.data?.error || 'Failed to start agent mode');
      }
    } catch (err: any) {
      setIsProcessing(false);

      const errorDetails = err.response?.data?.error || err.message;
      
      const errorMessage: Message = {
        role: 'system',
        content: `Error: ${errorDetails}`,
        timestamp: new Date(),
      };
      addMessage(sessionId, errorMessage);

      const errorOutput: ConsoleOutput = {
        type: 'stderr',
        content: `Error: ${errorDetails}\n${err.response?.data ? JSON.stringify(err.response.data, null, 2) : ''}\n`,
        timestamp: new Date(),
      };
      addConsoleOutput(sessionId, errorOutput);
    }
  };

  const handleNewChat = () => {
    createSession('New Chat');
    setShowLanding(true);
  };

  const handleClearCurrentSession = () => {
    if (activeSessionId) {
      clearSession(activeSessionId);
      setShowLanding(true);
    }
  };

  const handleDeleteSession = (sessionId: string) => {
    deleteSession(sessionId);
    if (sessions.length <= 1) {
      setShowLanding(true);
    }
  };

  const handleSwitchSession = (sessionId: string) => {
    switchSession(sessionId);
    setShowLanding(false);
    setMenuAnchor(null);
  };

  // Landing page view with sample queries
  if (showLanding) {
    return (
      <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', p: 3 }}>
        {/* Header with session menu */}
        <Box sx={{ mb: 4, textAlign: 'center' }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Box />
            <Typography variant="h4" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <AIIcon sx={{ fontSize: 40 }} color="primary" />
              AI Agent Mode
            </Typography>
            {sessions.length > 0 && (
              <Box>
                <IconButton onClick={(e) => setMenuAnchor(e.currentTarget)}>
                  <MoreVertIcon />
                </IconButton>
                <Menu
                  anchorEl={menuAnchor}
                  open={Boolean(menuAnchor)}
                  onClose={() => setMenuAnchor(null)}
                >
                  <MenuItem onClick={handleNewChat}>
                    <AddIcon sx={{ mr: 1 }} /> New Chat
                  </MenuItem>
                  <Divider />
                  {sessions.map(session => (
                    <MenuItem
                      key={session.id}
                      onClick={() => handleSwitchSession(session.id)}
                      selected={session.id === activeSessionId}
                    >
                      <ChatIcon sx={{ mr: 1 }} />
                      {session.title} ({session.messages.length} messages)
                    </MenuItem>
                  ))}
                  {sessions.length > 0 && (
                    <>
                      <Divider />
                      <MenuItem onClick={clearAllSessions}>
                        <DeleteIcon sx={{ mr: 1 }} /> Clear All Sessions
                      </MenuItem>
                    </>
                  )}
                </Menu>
              </Box>
            )}
          </Box>

          <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
            Ask questions about your Azure tenant graph using natural language.
            The agent will analyze your Neo4j database and provide insights.
          </Typography>

          {sessions.length > 0 && (
            <Stack direction="row" spacing={1} justifyContent="center" sx={{ mb: 2 }}>
              {sessions.map(session => (
                <Chip
                  key={session.id}
                  label={`${session.title} (${session.messages.length})`}
                  onClick={() => handleSwitchSession(session.id)}
                  color={session.id === activeSessionId ? "primary" : "default"}
                  variant={session.id === activeSessionId ? "filled" : "outlined"}
                />
              ))}
            </Stack>
          )}
        </Box>

        {/* Sample Query Cards */}
        <Grid container spacing={3} sx={{ flex: 1, overflow: 'auto' }}>
          {sampleQueries.map((sample, index) => (
            <Grid item xs={12} sm={6} md={4} lg={3} key={index}>
              <Card
                sx={{
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                  transition: 'transform 0.2s, box-shadow 0.2s',
                  cursor: 'pointer',
                  '&:hover': {
                    transform: 'translateY(-4px)',
                    boxShadow: 4,
                  }
                }}
                onClick={() => handleSend(sample.query)}
              >
                <CardContent sx={{ flex: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                    <Typography variant="h4" sx={{ mr: 2 }}>
                      {sample.icon}
                    </Typography>
                    <Typography variant="h6" component="div">
                      {sample.title}
                    </Typography>
                  </Box>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    {sample.description}
                  </Typography>
                  <Paper
                    elevation={0}
                    sx={{
                      p: 1,
                      bgcolor: '#000000',
                      borderRadius: 1,
                      fontFamily: 'monospace',
                      fontSize: '0.875rem',
                      color: '#90ee90',
                      border: '1px solid #333'
                    }}
                  >
                    {sample.query}
                  </Paper>
                </CardContent>
                <CardActions>
                  <Button
                    size="small"
                    fullWidth
                    variant="contained"
                    disabled={isProcessing}
                    startIcon={isProcessing ? <CircularProgress size={16} /> : <SendIcon />}
                  >
                    Run Query
                  </Button>
                </CardActions>
              </Card>
            </Grid>
          ))}
        </Grid>

        {/* Custom Query Input */}
        <Box sx={{ mt: 3 }}>
          <Paper elevation={2} sx={{ p: 2 }}>
            <Typography variant="subtitle1" gutterBottom>
              Or ask your own question:
            </Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <TextField
                fullWidth
                variant="outlined"
                placeholder="e.g., 'Which VMs are not in a availability set?' or 'Show me all public IP addresses'"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                disabled={isProcessing}
              />
              <IconButton
                color="primary"
                onClick={() => handleSend()}
                disabled={isProcessing || !input.trim()}
                sx={{ alignSelf: 'center' }}
              >
                {isProcessing ? <CircularProgress size={24} /> : <SendIcon />}
              </IconButton>
            </Box>
          </Paper>
        </Box>
      </Box>
    );
  }

  // Split-pane view for active chat
  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', p: 2 }}>
      {/* Header with session controls */}
      <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
        <IconButton onClick={() => setShowLanding(true)} size="small">
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h5" sx={{ display: 'flex', alignItems: 'center', gap: 1, flex: 1 }}>
          <AIIcon color="primary" />
          {activeSession?.title || 'AI Agent Mode'}
        </Typography>
        <Button
          variant="outlined"
          startIcon={<AddIcon />}
          onClick={handleNewChat}
          size="small"
        >
          New Chat
        </Button>
        <Button
          variant="outlined"
          startIcon={<ClearIcon />}
          onClick={handleClearCurrentSession}
          disabled={isProcessing}
          size="small"
        >
          Clear
        </Button>
        {activeSessionId && (
          <IconButton
            size="small"
            onClick={() => handleDeleteSession(activeSessionId)}
            disabled={isProcessing}
          >
            <DeleteIcon />
          </IconButton>
        )}
      </Box>

      {/* Session tabs */}
      {sessions.length > 1 && (
        <Box sx={{ mb: 2 }}>
          <Stack direction="row" spacing={1} sx={{ overflowX: 'auto' }}>
            {sessions.map(session => (
              <Chip
                key={session.id}
                label={session.title}
                onClick={() => switchSession(session.id)}
                onDelete={() => handleDeleteSession(session.id)}
                color={session.id === activeSessionId ? "primary" : "default"}
                variant={session.id === activeSessionId ? "filled" : "outlined"}
              />
            ))}
          </Stack>
        </Box>
      )}

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
            <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
              <Typography variant="h6">Chat</Typography>
            </Box>

            <List
              sx={{
                flex: 1,
                overflow: 'auto',
                p: 2,
                bgcolor: 'background.default'
              }}
            >
              {activeSession?.messages.map((message, index) => (
                <ListItem
                  key={index}
                  sx={{
                    flexDirection: 'column',
                    alignItems: 'flex-start',
                    mb: 2,
                    bgcolor: message.role === 'user' ? 'rgba(25, 118, 210, 0.15)' :
                             message.role === 'system' ? 'rgba(2, 136, 209, 0.15)' :
                             'rgba(255, 255, 255, 0.05)',
                    borderRadius: 1,
                    border: '1px solid',
                    borderColor: message.role === 'user' ? 'primary.dark' :
                                 message.role === 'system' ? 'info.dark' :
                                 'divider',
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    {message.role === 'user' ? (
                      <PersonIcon fontSize="small" color="primary" />
                    ) : (
                      <AIIcon fontSize="small" color="secondary" />
                    )}
                    <Typography variant="subtitle2" fontWeight="bold" color="text.primary">
                      {message.role === 'user' ? 'You' :
                       message.role === 'system' ? 'System' : 'Assistant'}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {message.timestamp.toLocaleTimeString()}
                    </Typography>
                  </Box>
                  <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', width: '100%', color: 'text.primary' }}>
                    {message.content}
                  </Typography>
                </ListItem>
              ))}
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
              {activeSession?.consoleOutput.map((output, index) => (
                <Box
                  key={index}
                  sx={{
                    color: output.type === 'stderr' ? '#ff6b6b' :
                           output.type === 'info' ? '#4fc3f7' :
                           '#90ee90',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    lineHeight: 1.4,
                    fontFamily: 'monospace',
                    fontSize: '0.875rem',
                  }}
                >
                  {output.content}
                </Box>
              ))}
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
