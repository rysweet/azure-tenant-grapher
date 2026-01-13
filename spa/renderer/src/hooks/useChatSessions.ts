import { useState, useEffect, useCallback } from 'react';

export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
}

export interface ConsoleOutput {
  type: 'stdout' | 'stderr' | 'info';
  content: string;
  timestamp: Date;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  consoleOutput: ConsoleOutput[];
  createdAt: Date;
  updatedAt: Date;
}

const STORAGE_KEY = 'agentModeChatSessions';
const ACTIVE_SESSION_KEY = 'agentModeActiveSession';

// Helper to serialize/deserialize dates
const serializeSession = (session: ChatSession): any => ({
  ...session,
  messages: session.messages.map(m => ({
    ...m,
    timestamp: m.timestamp.toISOString()
  })),
  consoleOutput: session.consoleOutput.map(o => ({
    ...o,
    timestamp: o.timestamp.toISOString()
  })),
  createdAt: session.createdAt.toISOString(),
  updatedAt: session.updatedAt.toISOString()
});

const deserializeSession = (data: any): ChatSession => ({
  ...data,
  messages: data.messages.map((m: any) => ({
    ...m,
    timestamp: new Date(m.timestamp)
  })),
  consoleOutput: data.consoleOutput.map((o: any) => ({
    ...o,
    timestamp: new Date(o.timestamp)
  })),
  createdAt: new Date(data.createdAt),
  updatedAt: new Date(data.updatedAt)
});

export function useChatSessions() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);

  // Load sessions from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) {
          const deserialized = parsed.map(deserializeSession);
          setSessions(deserialized);
        } else {
          // Invalid data format, clear it
          localStorage.removeItem(STORAGE_KEY);
        }
      }

      const activeId = localStorage.getItem(ACTIVE_SESSION_KEY);
      if (activeId) {
        setActiveSessionId(activeId);
      }
    } catch (e) {
      // Corrupted data, clear it
      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem(ACTIVE_SESSION_KEY);
      setSessions([]);
      setActiveSessionId(null);
    }
  }, []);

  // Save sessions to localStorage whenever they change
  useEffect(() => {
    try {
      const serialized = sessions.map(serializeSession);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(serialized));
    } catch (e) {
      // Console error removed
    }
  }, [sessions]);

  // Save active session ID
  useEffect(() => {
    if (activeSessionId) {
      localStorage.setItem(ACTIVE_SESSION_KEY, activeSessionId);
    } else {
      localStorage.removeItem(ACTIVE_SESSION_KEY);
    }
  }, [activeSessionId]);

  const createSession = useCallback((title?: string): ChatSession => {
    const now = new Date();
    const session: ChatSession = {
      id: `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      title: title || `Chat ${now.toLocaleString()}`,
      messages: [],
      consoleOutput: [],
      createdAt: now,
      updatedAt: now
    };

    setSessions(prev => [...prev, session]);
    setActiveSessionId(session.id);
    return session;
  }, []);

  const getActiveSession = useCallback((): ChatSession | null => {
    if (!activeSessionId) return null;
    return sessions.find(s => s.id === activeSessionId) || null;
  }, [sessions, activeSessionId]);

  const updateSession = useCallback((sessionId: string, updates: Partial<ChatSession>) => {
    setSessions(prev => prev.map(session => {
      if (session.id === sessionId) {
        return {
          ...session,
          ...updates,
          updatedAt: new Date()
        };
      }
      return session;
    }));
  }, []);

  const addMessage = useCallback((sessionId: string, message: Message) => {
    setSessions(prev => prev.map(session => {
      if (session.id === sessionId) {
        return {
          ...session,
          messages: [...session.messages, message],
          updatedAt: new Date()
        };
      }
      return session;
    }));
  }, []);

  const addConsoleOutput = useCallback((sessionId: string, output: ConsoleOutput) => {
    setSessions(prev => prev.map(session => {
      if (session.id === sessionId) {
        return {
          ...session,
          consoleOutput: [...session.consoleOutput, output],
          updatedAt: new Date()
        };
      }
      return session;
    }));
  }, []);

  const clearSession = useCallback((sessionId: string) => {
    setSessions(prev => prev.map(session => {
      if (session.id === sessionId) {
        return {
          ...session,
          messages: [],
          consoleOutput: [],
          updatedAt: new Date()
        };
      }
      return session;
    }));
  }, []);

  const deleteSession = useCallback((sessionId: string) => {
    setSessions(prev => prev.filter(s => s.id !== sessionId));
    if (activeSessionId === sessionId) {
      setActiveSessionId(null);
    }
  }, [activeSessionId]);

  const switchSession = useCallback((sessionId: string) => {
    setActiveSessionId(sessionId);
  }, []);

  const clearAllSessions = useCallback(() => {
    setSessions([]);
    setActiveSessionId(null);
  }, []);

  return {
    sessions,
    activeSessionId,
    getActiveSession,
    createSession,
    updateSession,
    addMessage,
    addConsoleOutput,
    clearSession,
    deleteSession,
    switchSession,
    clearAllSessions
  };
}
