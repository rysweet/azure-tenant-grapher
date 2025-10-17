/**
 * WebSocket authentication and rate limiting middleware
 * Implements token-based auth, rate limiting, and session management
 */

import { Socket } from 'socket.io';
import { ExtendedError } from 'socket.io/dist/namespace';
import { createHash, randomBytes } from 'crypto';
import { logger } from '../logger';

// Token storage (in production, use Redis or a database)
const activeSessions = new Map<string, SessionInfo>();
const rateLimitStore = new Map<string, RateLimitInfo>();

// Configuration
const CONFIG = {
  TOKEN_EXPIRY_MS: 24 * 60 * 60 * 1000, // 24 hours
  RATE_LIMIT_WINDOW_MS: 60 * 1000,      // 1 minute
  RATE_LIMIT_MAX_REQUESTS: 10,          // 10 requests per minute
  HEARTBEAT_INTERVAL_MS: 30 * 1000,     // 30 seconds
  HEARTBEAT_TIMEOUT_MS: 60 * 1000,      // 60 seconds
  MAX_SESSIONS_PER_USER: 5              // Maximum concurrent sessions
};

interface SessionInfo {
  token: string;
  userId: string;
  clientId: string;
  createdAt: Date;
  expiresAt: Date;
  lastActivity: Date;
  ipAddress: string;
  userAgent?: string;
}

interface RateLimitInfo {
  requests: number;
  windowStart: Date;
}

export class AuthMiddleware {
  /**
   * Generate a secure authentication token
   */
  static generateToken(): string {
    return randomBytes(32).toString('hex');
  }

  /**
   * Create a new session
   */
  static createSession(userId: string, clientId: string, ipAddress: string, userAgent?: string): string {
    const token = this.generateToken();
    const now = new Date();

    const session: SessionInfo = {
      token,
      userId,
      clientId,
      createdAt: now,
      expiresAt: new Date(now.getTime() + CONFIG.TOKEN_EXPIRY_MS),
      lastActivity: now,
      ipAddress,
      userAgent
    };

    // Clean up old sessions for this user
    this.cleanupUserSessions(userId);

    activeSessions.set(token, session);

    logger.info('Session created', {
      userId,
      clientId,
      token: token.substring(0, 8) + '...'
    });

    return token;
  }

  /**
   * Validate a token
   */
  static validateToken(token: string): SessionInfo | null {
    const session = activeSessions.get(token);

    if (!session) {
      return null;
    }

    const now = new Date();

    // Check if token has expired
    if (session.expiresAt < now) {
      activeSessions.delete(token);
      logger.warn('Token expired', { token: token.substring(0, 8) + '...' });
      return null;
    }

    // Update last activity
    session.lastActivity = now;

    return session;
  }

  /**
   * Socket.IO authentication middleware
   */
  static async authenticate(socket: Socket, next: (err?: ExtendedError) => void) {
    try {
      const token = socket.handshake.auth?.token || socket.handshake.headers?.authorization?.replace('Bearer ', '');

      if (!token) {
        logger.warn('WebSocket connection attempt without token', {
          address: socket.handshake.address
        });
        return next(new Error('Authentication required'));
      }

      const session = AuthMiddleware.validateToken(token);

      if (!session) {
        logger.warn('WebSocket connection attempt with invalid token', {
          address: socket.handshake.address,
          token: token.substring(0, 8) + '...'
        });
        return next(new Error('Invalid or expired token'));
      }

      // Check rate limit
      if (!AuthMiddleware.checkRateLimit(session.userId)) {
        logger.warn('Rate limit exceeded', {
          userId: session.userId,
          address: socket.handshake.address
        });
        return next(new Error('Rate limit exceeded'));
      }

      // Attach session info to socket
      (socket as any).session = session;
      (socket as any).userId = session.userId;
      (socket as any).clientId = session.clientId;

      logger.info('WebSocket authenticated', {
        userId: session.userId,
        clientId: session.clientId,
        address: socket.handshake.address
      });

      next();
    } catch (error) {
      logger.error('Authentication error', error);
      next(new Error('Authentication failed'));
    }
  }

  /**
   * Check rate limit for a user
   */
  static checkRateLimit(userId: string): boolean {
    const now = new Date();
    const userRateLimit = rateLimitStore.get(userId);

    if (!userRateLimit) {
      // First request from this user
      rateLimitStore.set(userId, {
        requests: 1,
        windowStart: now
      });
      return true;
    }

    // Check if we're still in the same window
    const windowAge = now.getTime() - userRateLimit.windowStart.getTime();

    if (windowAge > CONFIG.RATE_LIMIT_WINDOW_MS) {
      // New window
      userRateLimit.requests = 1;
      userRateLimit.windowStart = now;
      return true;
    }

    // Same window, check limit
    if (userRateLimit.requests >= CONFIG.RATE_LIMIT_MAX_REQUESTS) {
      return false;
    }

    userRateLimit.requests++;
    return true;
  }

  /**
   * Setup heartbeat mechanism for a socket
   */
  static setupHeartbeat(socket: Socket) {
    let heartbeatInterval: NodeJS.Timeout;
    let heartbeatTimeout: NodeJS.Timeout;
    let isAlive = true;

    const sendPing = () => {
      if (!isAlive) {
        logger.warn('Client heartbeat timeout', {
          userId: (socket as any).userId,
          clientId: (socket as any).clientId
        });
        socket.disconnect(true);
        return;
      }

      isAlive = false;
      socket.emit('ping');

      heartbeatTimeout = setTimeout(() => {
        if (!isAlive) {
          logger.warn('Client failed to respond to ping', {
            userId: (socket as any).userId,
            clientId: (socket as any).clientId
          });
          socket.disconnect(true);
        }
      }, CONFIG.HEARTBEAT_TIMEOUT_MS);
    };

    // Start heartbeat
    heartbeatInterval = setInterval(sendPing, CONFIG.HEARTBEAT_INTERVAL_MS);

    // Listen for pong responses
    socket.on('pong', () => {
      isAlive = true;
      if (heartbeatTimeout) {
        clearTimeout(heartbeatTimeout);
      }
    });

    // Clean up on disconnect
    socket.on('disconnect', () => {
      if (heartbeatInterval) {
        clearInterval(heartbeatInterval);
      }
      if (heartbeatTimeout) {
        clearTimeout(heartbeatTimeout);
      }
    });

    logger.debug('Heartbeat setup for socket', {
      userId: (socket as any).userId,
      clientId: (socket as any).clientId
    });
  }

  /**
   * Revoke a token
   */
  static revokeToken(token: string): boolean {
    const session = activeSessions.get(token);

    if (session) {
      activeSessions.delete(token);
      logger.info('Token revoked', {
        userId: session.userId,
        token: token.substring(0, 8) + '...'
      });
      return true;
    }

    return false;
  }

  /**
   * Revoke all tokens for a user
   */
  static revokeUserTokens(userId: string): number {
    let count = 0;

    for (const [token, session] of activeSessions.entries()) {
      if (session.userId === userId) {
        activeSessions.delete(token);
        count++;
      }
    }

    if (count > 0) {
      logger.info('User tokens revoked', { userId, count });
    }

    return count;
  }

  /**
   * Clean up expired sessions
   */
  static cleanupExpiredSessions() {
    const now = new Date();
    let cleaned = 0;

    for (const [token, session] of activeSessions.entries()) {
      if (session.expiresAt < now) {
        activeSessions.delete(token);
        cleaned++;
      }
    }

    if (cleaned > 0) {
      logger.info('Cleaned up expired sessions', { count: cleaned });
    }

    // Also clean up old rate limit entries
    const rateLimitCutoff = new Date(now.getTime() - CONFIG.RATE_LIMIT_WINDOW_MS * 2);

    for (const [userId, info] of rateLimitStore.entries()) {
      if (info.windowStart < rateLimitCutoff) {
        rateLimitStore.delete(userId);
      }
    }
  }

  /**
   * Clean up old sessions for a user (keep only the most recent ones)
   */
  private static cleanupUserSessions(userId: string) {
    const userSessions: Array<[string, SessionInfo]> = [];

    for (const [token, session] of activeSessions.entries()) {
      if (session.userId === userId) {
        userSessions.push([token, session]);
      }
    }

    // If user has too many sessions, remove the oldest ones
    if (userSessions.length >= CONFIG.MAX_SESSIONS_PER_USER) {
      userSessions.sort((a, b) => a[1].createdAt.getTime() - b[1].createdAt.getTime());

      const toRemove = userSessions.length - CONFIG.MAX_SESSIONS_PER_USER + 1;

      for (let i = 0; i < toRemove; i++) {
        activeSessions.delete(userSessions[i][0]);
        logger.info('Removed old session due to limit', {
          userId,
          token: userSessions[i][0].substring(0, 8) + '...'
        });
      }
    }
  }

  /**
   * Get session statistics
   */
  static getStats() {
    const now = new Date();
    const sessions = Array.from(activeSessions.values());

    return {
      totalSessions: sessions.length,
      activeSessions: sessions.filter(s => s.lastActivity > new Date(now.getTime() - 5 * 60 * 1000)).length,
      uniqueUsers: new Set(sessions.map(s => s.userId)).size,
      rateLimitedUsers: Array.from(rateLimitStore.entries()).filter(([_, info]) => {
        const windowAge = now.getTime() - info.windowStart.getTime();
        return windowAge <= CONFIG.RATE_LIMIT_WINDOW_MS && info.requests >= CONFIG.RATE_LIMIT_MAX_REQUESTS;
      }).length
    };
  }
}

// Start periodic cleanup
setInterval(() => {
  AuthMiddleware.cleanupExpiredSessions();
}, 60 * 60 * 1000); // Run every hour

// Export convenience functions for backward compatibility
export const requireAuth = (req: any, res: any, next: any) => {
  // Simple auth check - in production, validate token
  const token = req.headers.authorization?.replace('Bearer ', '');
  if (!token || !AuthMiddleware.validateToken(token)) {
    return res.status(401).json({ error: 'Unauthorized' });
  }
  next();
};

export const authenticateWebSocket = (socket: Socket, next: (err?: ExtendedError) => void) => {
  const token = socket.handshake.auth?.token;
  if (!token || !AuthMiddleware.validateToken(token)) {
    return next(new Error('Authentication failed'));
  }
  next();
};

export const requireSocketAuth = (socket: Socket): boolean => {
  return !!(socket as any).userId;
};

export const handleLogin = (req: any, res: any) => {
  // Simple login handler - in production, validate credentials
  const { username, password } = req.body;
  if (!username || !password) {
    return res.status(400).json({ error: 'Username and password required' });
  }

  const token = AuthMiddleware.generateToken();
  const session = AuthMiddleware.createSession(username, req.ip || 'unknown', req.headers['user-agent']);

  res.json({ token, userId: username });
};

export const handleLogout = (req: any, res: any) => {
  const token = req.headers.authorization?.replace('Bearer ', '');
  if (token) {
    AuthMiddleware.revokeToken(token);
  }
  res.json({ success: true });
};

export default AuthMiddleware;
