import React, { useState, useRef, useEffect } from 'react';
import {
  Box,
  Paper,
  TextField,
  Button,
  Typography,
  List,
  ListItem,
  ListItemText,
  Divider,
  IconButton,
  Chip,
  Grid,
  Card,
  CardContent,
} from '@mui/material';
import {
  Send as SendIcon,
  Clear as ClearIcon,
  Storage as StorageIcon,
  Security as SecurityIcon,
  Group as GroupIcon,
  AccountTree as NetworkIcon,
  VpnKey as KeyIcon,
  Settings as SettingsIcon
} from '@mui/icons-material';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface SampleQuery {
  title: string;
  query: string;
  category: string;
  icon: React.ElementType;
  description: string;
}

const sampleQueries: SampleQuery[] = [
  {
    title: "Key Vaults by Resource Group",
    query: "Which resource groups have key vaults?",
    category: "Security",
    icon: KeyIcon,
    description: "Find key vaults and their resource group locations"
  },
  {
    title: "Tenant Admin Users",
    query: "How many users have tenant admin permissions?",
    category: "Identity",
    icon: GroupIcon,
    description: "Identify users with elevated tenant permissions"
  },
  {
    title: "Public Storage Accounts",
    query: "List all storage accounts with public access enabled",
    category: "Security",
    icon: StorageIcon,
    description: "Find storage accounts that allow public access"
  },
  {
    title: "Network Topology",
    query: "Show virtual networks with their subnets and NSG rules",
    category: "Networking",
    icon: NetworkIcon,
    description: "Explore network infrastructure and security groups"
  },
  {
    title: "Compliance Issues",
    query: "What resources are not compliant with security policies?",
    category: "Compliance",
    icon: SecurityIcon,
    description: "Identify non-compliant resources and security gaps"
  },
  {
    title: "Service Principal Permissions",
    query: "List all service principals with owner role assignments",
    category: "Identity",
    icon: SettingsIcon,
    description: "Find service principals with elevated permissions"
  }
];

const AgentModeTab: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

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

    try {
      const result = await window.electronAPI.cli.execute('agent-mode', ['--prompt', messageText]);

      let response = '';
      window.electronAPI.on('process:output', (data: any) => {
        if (data.id === result.data.id) {
          response += data.data.join('\n');
        }
      });

      window.electronAPI.on('process:exit', (data: any) => {
        if (data.id === result.data.id) {
          setIsProcessing(false);

          const assistantMessage: Message = {
            role: 'assistant',
            content: response || 'No response received',
            timestamp: new Date(),
          };

          setMessages((prev) => [...prev, assistantMessage]);
        }
      });

    } catch (err: any) {
      setIsProcessing(false);
      const errorMessage: Message = {
        role: 'assistant',
        content: `Error: ${err.message}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    }
  };

  const handleClear = () => {
    setMessages([]);
  };

  const handleSampleQueryClick = async (query: string, autoRun: boolean = false) => {
    if (autoRun) {
      handleSend(query);
    } else {
      setInput(query);
    }
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Paper sx={{ p: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
        <Typography variant="h5" sx={{ flexGrow: 1 }}>
          AI Agent Mode
        </Typography>
        <IconButton onClick={handleClear} title="Clear conversation">
          <ClearIcon />
        </IconButton>
      </Paper>

      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', m: 2, gap: 2 }}>
        {messages.length === 0 && (
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Sample Questions
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Click on any question below to get started, or type your own question in the text field.
            </Typography>

            <Grid container spacing={2}>
              {sampleQueries.map((sample, index) => (
                <Grid item xs={12} sm={6} md={4} key={index}>
                  <Card
                    sx={{
                      transition: 'all 0.2s ease-in-out',
                      '&:hover': {
                        transform: 'translateY(-2px)',
                        boxShadow: 3,
                      }
                    }}
                  >
                    <CardContent sx={{ p: 2 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                        <sample.icon sx={{ mr: 1, color: 'primary.main' }} />
                        <Chip
                          label={sample.category}
                          size="small"
                          variant="outlined"
                          sx={{ ml: 'auto' }}
                        />
                      </Box>
                      <Typography variant="subtitle2" gutterBottom>
                        {sample.title}
                      </Typography>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        {sample.description}
                      </Typography>
                      <Typography
                        variant="caption"
                        sx={{
                          fontStyle: 'italic',
                          color: 'text.secondary',
                          display: 'block',
                          mb: 2
                        }}
                      >
                        "{sample.query}"
                      </Typography>
                      <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
                        <Button
                          size="small"
                          variant="outlined"
                          onClick={() => handleSampleQueryClick(sample.query, false)}
                        >
                          Use Query
                        </Button>
                        <Button
                          size="small"
                          variant="contained"
                          onClick={() => handleSampleQueryClick(sample.query, true)}
                          disabled={isProcessing}
                        >
                          Run Now
                        </Button>
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          </Paper>
        )}

        <Paper sx={{ flex: 1, p: 2, overflow: 'auto', minHeight: 200 }}>
          <List>
            {messages.length === 0 ? (
              <ListItem>
                <ListItemText
                  primary="Ready for your questions"
                  secondary="Use the sample questions above or ask anything about your Azure tenant"
                />
              </ListItem>
            ) : (
              messages.map((message, index) => (
                <React.Fragment key={index}>
                  <ListItem alignItems="flex-start">
                    <ListItemText
                      primary={
                        <Typography
                          component="span"
                          variant="subtitle2"
                          color={message.role === 'user' ? 'primary' : 'secondary'}
                        >
                          {message.role === 'user' ? 'You' : 'Assistant'}
                        </Typography>
                      }
                      secondary={
                        <>
                          <Typography
                            component="span"
                            variant="body2"
                            color="text.primary"
                            sx={{ whiteSpace: 'pre-wrap' }}
                          >
                            {message.content}
                          </Typography>
                          <Typography
                            component="span"
                            variant="caption"
                            color="text.secondary"
                            sx={{ display: 'block', mt: 1 }}
                          >
                            {message.timestamp.toLocaleTimeString()}
                          </Typography>
                        </>
                      }
                    />
                  </ListItem>
                  {index < messages.length - 1 && <Divider variant="inset" component="li" />}
                </React.Fragment>
              ))
            )}
            <div ref={messagesEndRef} />
          </List>
        </Paper>
      </Box>

      <Paper sx={{ p: 2, m: 2, mt: 0 }}>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <TextField
            fullWidth
            placeholder="Ask a question or request analysis..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
            disabled={isProcessing}
            multiline
            maxRows={4}
          />
          <Button
            variant="contained"
            endIcon={<SendIcon />}
            onClick={handleSend}
            disabled={isProcessing || !input.trim()}
          >
            Send
          </Button>
        </Box>
      </Paper>
    </Box>
  );
};

export default AgentModeTab;
