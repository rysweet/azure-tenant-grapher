/**
 * Security Module: Rate Limiting
 * Prevents DoS attacks and resource exhaustion
 */

import { Request, Response, NextFunction } from 'express';
import { Socket } from 'socket.io';

/**
 * Rate limit configuration
 */
interface RateLimitConfig {
  windowMs: number;     // Time window in milliseconds
  maxRequests: number;  // Maximum requests per window
  message?: string;     // Error message
  skipSuccessfulRequests?: boolean; // Only count failed requests
}

/**
 * Client request tracking
 */
interface ClientTracker {
  requests: number[];  // Timestamps of requests
  blocked: boolean;
  blockExpiry?: number;
}

class RateLimiter {
  private clients: Map<string, ClientTracker> = new Map();
  private readonly defaultConfig: RateLimitConfig = {
    windowMs: 60 * 1000,  // 1 minute
    maxRequests: 100,     // 100 requests per minute
    message: 'Too many requests, please try again later'
  };
  
  // Specific limits for different operations
  private readonly limits: Map<string, RateLimitConfig> = new Map([
    ['api:execute', { windowMs: 60000, maxRequests: 10 }],  // 10 executions per minute
    ['api:auth', { windowMs: 300000, maxRequests: 5 }],     // 5 login attempts per 5 minutes
    ['api:neo4j', { windowMs: 60000, maxRequests: 30 }],    // 30 Neo4j queries per minute
    ['api:search', { windowMs: 60000, maxRequests: 50 }],   // 50 searches per minute
    ['ws:subscribe', { windowMs: 60000, maxRequests: 20 }], // 20 subscriptions per minute
    ['api:test', { windowMs: 300000, maxRequests: 10 }],    // 10 test operations per 5 minutes
  ]);

  constructor() {
    // Clean up old entries every minute
    setInterval(() => this.cleanup(), 60 * 1000);
  }

  /**
   * Get client identifier from request or socket
   */
  private getClientId(source: Request | Socket): string {
    if ('ip' in source) {
      // Express Request
      return source.ip || source.socket.remoteAddress || 'unknown';
    } else {
      // Socket.io Socket
      return source.handshake.address || 'unknown';
    }
  }

  /**
   * Check if a client has exceeded rate limit
   */
  checkLimit(clientId: string, operation: string): boolean {
    const config = this.limits.get(operation) || this.defaultConfig;
    const now = Date.now();
    
    // Get or create client tracker
    let tracker = this.clients.get(clientId);
    if (!tracker) {
      tracker = { requests: [], blocked: false };
      this.clients.set(clientId, tracker);
    }

    // Check if client is currently blocked
    if (tracker.blocked && tracker.blockExpiry) {
      if (now < tracker.blockExpiry) {
        return false; // Still blocked
      } else {
        // Unblock
        tracker.blocked = false;
        tracker.blockExpiry = undefined;
      }
    }

    // Remove old requests outside the window
    const windowStart = now - config.windowMs;
    tracker.requests = tracker.requests.filter(timestamp => timestamp > windowStart);

    // Check if limit exceeded
    if (tracker.requests.length >= config.maxRequests) {
      // Block the client for the window duration
      tracker.blocked = true;
      tracker.blockExpiry = now + config.windowMs;
      return false;
    }

    // Add current request
    tracker.requests.push(now);
    return true;
  }

  /**
   * Express middleware for rate limiting
   */
  middleware(operation: string) {
    return (req: Request, res: Response, next: NextFunction) => {
      const clientId = this.getClientId(req);
      
      if (!this.checkLimit(clientId, operation)) {
        const config = this.limits.get(operation) || this.defaultConfig;
        res.status(429).json({ 
          error: config.message || 'Too many requests',
          retryAfter: Math.ceil(config.windowMs / 1000) // Retry-After in seconds
        });
        return;
      }

      next();
    };
  }

  /**
   * Socket.io rate limit check
   */
  checkSocketLimit(socket: Socket, operation: string): boolean {
    const clientId = this.getClientId(socket);
    return this.checkLimit(clientId, operation);
  }

  /**
   * Clean up old client trackers
   */
  private cleanup(): void {
    const now = Date.now();
    const maxAge = 10 * 60 * 1000; // 10 minutes

    for (const [clientId, tracker] of this.clients.entries()) {
      // Remove if no recent requests and not blocked
      if (!tracker.blocked && tracker.requests.length === 0) {
        this.clients.delete(clientId);
        continue;
      }

      // Remove if all requests are old
      const hasRecentRequests = tracker.requests.some(
        timestamp => (now - timestamp) < maxAge
      );
      
      if (!hasRecentRequests && !tracker.blocked) {
        this.clients.delete(clientId);
      }
    }
  }

  /**
   * Get current client count for monitoring
   */
  getClientCount(): number {
    return this.clients.size;
  }

  /**
   * Get rate limit status for a client
   */
  getClientStatus(clientId: string): { requests: number; blocked: boolean } | null {
    const tracker = this.clients.get(clientId);
    if (!tracker) {
      return null;
    }

    const now = Date.now();
    const windowStart = now - this.defaultConfig.windowMs;
    const recentRequests = tracker.requests.filter(timestamp => timestamp > windowStart);

    return {
      requests: recentRequests.length,
      blocked: tracker.blocked && (tracker.blockExpiry ? now < tracker.blockExpiry : false)
    };
  }

  /**
   * Reset rate limit for a specific client (admin function)
   */
  resetClient(clientId: string): void {
    this.clients.delete(clientId);
  }
}

// Singleton instance
const rateLimiter = new RateLimiter();

/**
 * Pre-configured middleware for common operations
 */
export const rateLimiters = {
  execute: rateLimiter.middleware('api:execute'),
  auth: rateLimiter.middleware('api:auth'),
  neo4j: rateLimiter.middleware('api:neo4j'),
  search: rateLimiter.middleware('api:search'),
  test: rateLimiter.middleware('api:test'),
  default: rateLimiter.middleware('default')
};

/**
 * Socket rate limit checker
 */
export function checkSocketRateLimit(socket: Socket, operation: string): boolean {
  return rateLimiter.checkSocketLimit(socket, operation);
}

/**
 * Global rate limiter instance
 */
export { rateLimiter };

export default {
  rateLimiter,
  rateLimiters,
  checkSocketRateLimit
};
