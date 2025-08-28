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
} from '@mui/material';
import { Send as SendIcon, Clear as ClearIcon } from '@mui/icons-material';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

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

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage: Message = {
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsProcessing(true);

    try {
      const result = await window.electronAPI.cli.execute('agent-mode', ['--prompt', input]);
      
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

      <Paper sx={{ flex: 1, m: 2, p: 2, overflow: 'auto' }}>
        <List>
          {messages.length === 0 ? (
            <ListItem>
              <ListItemText
                primary="Start a conversation"
                secondary="Ask questions about your Azure tenant or request analysis"
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