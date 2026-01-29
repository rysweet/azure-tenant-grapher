/**
 * AuthContext
 *
 * React Context for managing dual-tenant Azure authentication.
 * Provides state management, device code flow, auto-refresh, and feature gates.
 *
 * Features:
 * - Device Code Flow for both source and gameboard tenants
 * - Automatic token refresh (polls every 4 minutes, refreshes 5 min before expiry)
 * - Polling during authentication (checks every 5 seconds)
 * - Feature gates (canScan, canDeploy)
 * - Persistent token check on mount
 *
 * Philosophy:
 * - Single responsibility: Authentication state management
 * - Uses backend API for all auth operations
 * - Self-contained and regeneratable
 */

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import axios from 'axios';

// Type definitions
export type TenantType = 'source' | 'target';

export interface DeviceCodeInfo {
  userCode: string;
  verificationUri: string;
  expiresIn: number;
  message: string;
}

export interface AuthState {
  authenticated: boolean;
  accessToken?: string;
  expiresAt?: number;
}

export interface AuthContextValue {
  // Authentication state
  sourceAuth: AuthState | null;
  targetAuth: AuthState | null;

  // Device code flow
  startDeviceCodeFlow: (tenantType: TenantType, tenantId: string) => Promise<DeviceCodeInfo>;
  deviceCodeInfo: DeviceCodeInfo | null;
  pollingActive: boolean;

  // Sign out
  signOut: (tenantType: TenantType) => Promise<void>;
  signOutAll: () => Promise<void>;

  // Feature gates
  canScan: boolean;  // Requires source tenant auth
  canDeploy: boolean; // Requires both source and target tenant auth

  // Loading states
  loading: boolean;
  error: string | null;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [sourceAuth, setSourceAuth] = useState<AuthState | null>(null);
  const [targetAuth, setTargetAuth] = useState<AuthState | null>(null);
  const [deviceCodeInfo, setDeviceCodeInfo] = useState<DeviceCodeInfo | null>(null);
  const [pollingActive, setPollingActive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [pollingTenantType, setPollingTenantType] = useState<TenantType | null>(null);
  const [pollingTenantId, setPollingTenantId] = useState<string | null>(null);

  /**
   * Check if token exists for a tenant
   */
  const checkExistingToken = useCallback(async (tenantType: TenantType): Promise<AuthState | null> => {
    try {
      const response = await axios.get(`/api/auth/token?tenantType=${tenantType}`);
      return {
        authenticated: true,
        accessToken: response.data.accessToken,
        expiresAt: response.data.expiresAt,
      };
    } catch (error: any) {
      // 401 means not authenticated (expected)
      if (error.response?.status === 401) {
        return { authenticated: false };
      }
      // Other errors are unexpected
      console.error(`Failed to check existing token for ${tenantType}:`, error);
      return { authenticated: false };
    }
  }, []);

  /**
   * Check existing tokens on mount
   */
  useEffect(() => {
    const checkTokens = async () => {
      setLoading(true);
      try {
        const [source, target] = await Promise.all([
          checkExistingToken('source'),
          checkExistingToken('target'),
        ]);

        setSourceAuth(source);
        setTargetAuth(target);
      } catch (error) {
        console.error('Failed to check existing tokens:', error);
      } finally {
        setLoading(false);
      }
    };

    checkTokens();
  }, [checkExistingToken]);

  /**
   * Start Device Code Flow
   */
  const startDeviceCodeFlow = useCallback(async (tenantType: TenantType, tenantId: string): Promise<DeviceCodeInfo> => {
    try {
      setError(null);
      const response = await axios.post('/api/auth/device-code/start', {
        tenantType,
        tenantId,
      });

      const deviceCode = response.data;
      setDeviceCodeInfo(deviceCode);
      setPollingTenantType(tenantType);
      setPollingTenantId(tenantId);
      setPollingActive(true);

      return deviceCode;
    } catch (error: any) {
      const errorMessage = error.response?.data?.error || 'Failed to start authentication';
      setError(errorMessage);
      throw new Error(errorMessage);
    }
  }, []);

  /**
   * Poll for authentication status
   * Checks every 5 seconds until user completes authentication
   */
  useEffect(() => {
    if (!pollingActive || !pollingTenantType || !pollingTenantId) {
      return;
    }

    const pollInterval = setInterval(async () => {
      try {
        const response = await axios.get('/api/auth/device-code/status', {
          params: {
            tenantType: pollingTenantType,
            tenantId: pollingTenantId,
          },
        });

        const status = response.data;

        if (status.success) {
          // Authentication successful!
          const authState: AuthState = {
            authenticated: true,
            accessToken: status.accessToken,
            expiresAt: status.expiresAt,
          };

          if (pollingTenantType === 'source') {
            setSourceAuth(authState);
          } else {
            setTargetAuth(authState);
          }

          // Stop polling
          setPollingActive(false);
          setDeviceCodeInfo(null);
          setPollingTenantType(null);
          setPollingTenantId(null);
        } else if (status.status === 'expired') {
          // Device code expired
          setError('Device code expired. Please try again.');
          setPollingActive(false);
          setDeviceCodeInfo(null);
        }
        // If status is 'pending', continue polling
      } catch (error: any) {
        console.error('Polling error:', error);
        // Continue polling even on errors (network issues, etc.)
      }
    }, 5000); // Poll every 5 seconds

    return () => clearInterval(pollInterval);
  }, [pollingActive, pollingTenantType, pollingTenantId]);

  /**
   * Auto-refresh tokens
   * Runs every 4 minutes, refreshes tokens that expire within 5 minutes
   */
  useEffect(() => {
    const autoRefreshInterval = setInterval(async () => {
      const now = Date.now();
      const fiveMinutes = 5 * 60 * 1000;

      // Check source token
      if (sourceAuth?.authenticated && sourceAuth.expiresAt) {
        if (sourceAuth.expiresAt - now < fiveMinutes) {
          try {
            const response = await axios.get('/api/auth/token?tenantType=source');
            setSourceAuth({
              authenticated: true,
              accessToken: response.data.accessToken,
              expiresAt: response.data.expiresAt,
            });
          } catch (error) {
            console.error('Failed to refresh source token:', error);
            // Token might have expired, set to unauthenticated
            setSourceAuth({ authenticated: false });
          }
        }
      }

      // Check target token
      if (targetAuth?.authenticated && targetAuth.expiresAt) {
        if (targetAuth.expiresAt - now < fiveMinutes) {
          try {
            const response = await axios.get('/api/auth/token?tenantType=target');
            setTargetAuth({
              authenticated: true,
              accessToken: response.data.accessToken,
              expiresAt: response.data.expiresAt,
            });
          } catch (error) {
            console.error('Failed to refresh target token:', error);
            setTargetAuth({ authenticated: false });
          }
        }
      }
    }, 240000); // Every 4 minutes

    return () => clearInterval(autoRefreshInterval);
  }, [sourceAuth, targetAuth]);

  /**
   * Sign out from a tenant
   */
  const signOut = useCallback(async (tenantType: TenantType) => {
    try {
      await axios.post('/api/auth/signout', { tenantType });

      if (tenantType === 'source') {
        setSourceAuth({ authenticated: false });
      } else {
        setTargetAuth({ authenticated: false });
      }
    } catch (error) {
      console.error(`Failed to sign out from ${tenantType}:`, error);
      throw error;
    }
  }, []);

  /**
   * Sign out from all tenants
   */
  const signOutAll = useCallback(async () => {
    try {
      await axios.post('/api/auth/signout', {});
      setSourceAuth({ authenticated: false });
      setTargetAuth({ authenticated: false });
    } catch (error) {
      console.error('Failed to sign out from all tenants:', error);
      throw error;
    }
  }, []);

  // Feature gates
  const canScan = sourceAuth?.authenticated ?? false;
  const canDeploy = (sourceAuth?.authenticated && targetAuth?.authenticated) ?? false;

  const value: AuthContextValue = {
    sourceAuth,
    targetAuth,
    startDeviceCodeFlow,
    deviceCodeInfo,
    pollingActive,
    signOut,
    signOutAll,
    canScan,
    canDeploy,
    loading,
    error,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

/**
 * Hook to use auth context
 */
export const useAuth = (): AuthContextValue => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
