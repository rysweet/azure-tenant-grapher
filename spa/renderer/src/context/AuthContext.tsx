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
   * Start Azure CLI login flow (triggers az login internally)
   *
   * This function initiates the authentication flow by calling the backend
   * to spawn an `az login` subprocess. The flow works like this:
   *
   * 1. Call /azure-cli/login endpoint with tenant ID
   * 2. Backend spawns `az login --tenant <id> --use-device-code`
   * 3. Backend captures device code from az login output
   * 4. Device code returned to frontend (e.g., "ABC123")
   * 5. Frontend displays device code in modal
   * 6. User opens browser to https://microsoft.com/device
   * 7. User enters code and completes authentication
   * 8. Frontend polls /azure-cli/status every 5 seconds
   * 9. When complete, status endpoint returns token
   * 10. Frontend updates UI to "Authenticated"
   *
   * Why this approach:
   * - Users don't need to manually run terminal commands
   * - Browser authentication handles MFA and SSO automatically
   * - Works with corporate authentication policies
   * - Clean UX like any web application
   *
   * @param tenantType - 'source' or 'target' tenant
   * @param tenantId - Azure tenant ID to authenticate to
   * @returns DeviceCodeInfo with code and URL for modal display
   */
  const startDeviceCodeFlow = useCallback(async (tenantType: TenantType, tenantId: string): Promise<DeviceCodeInfo> => {
    try {
      setError(null);

      console.log(`Starting az login for ${tenantType} tenant: ${tenantId}`);

      // Trigger az login subprocess on backend
      // Backend will spawn process and capture device code
      const response = await axios.post('http://localhost:3001/api/auth/azure-cli/login', {
        tenantType,
        tenantId,
      });

      if (response.data.success) {
        // az login started successfully - extract device code info from response
        const deviceCode: DeviceCodeInfo = {
          userCode: response.data.userCode,           // e.g., "ABC123DEF"  // pragma: allowlist secret
          verificationUri: response.data.verificationUri, // e.g., "https://microsoft.com/device"
          expiresIn: response.data.expiresIn,         // seconds until code expires (900 = 15 min)
          message: response.data.message,             // User-friendly instruction message
        };

        console.log(`Device code received: ${deviceCode.userCode}`);
        console.log(`Verification URL: ${deviceCode.verificationUri}`);

        // Set device code info for modal to display
        setDeviceCodeInfo(deviceCode);

        // Begin polling for authentication completion
        // Polling happens in separate useEffect (see below)
        setPollingTenantType(tenantType);
        setPollingTenantId(tenantId);
        setPollingActive(true);

        console.log('az login started - polling for completion...');

        return deviceCode;
      } else {
        throw new Error(response.data.message || 'Failed to start az login');
      }
    } catch (error: any) {
      // CRITICAL: Clear auth state when authentication fails
      // This prevents UI from showing stale "Authenticated" status
      if (tenantType === 'source') {
        setSourceAuth({ authenticated: false });
      } else {
        setTargetAuth({ authenticated: false });
      }

      const errorMessage = error.response?.data?.error || error.message || 'Failed to start authentication';
      setError(errorMessage);
      throw new Error(errorMessage);
    }
  }, []);

  /**
   * Poll for Azure CLI login completion
   *
   * Automatically polls backend every 5 seconds after user initiates sign-in
   * to check if browser authentication has completed.
   *
   * User Journey:
   * 1. User clicks "Sign In" → /azure-cli/login triggered
   * 2. Modal shows device code (e.g., "ABC123")
   * 3. User goes to https://microsoft.com/device in browser
   * 4. User enters code and completes Microsoft authentication
   * 5. **This polling starts here** - checks if az login completed
   * 6. When complete, backend returns token → UI updates to "Authenticated"
   *
   * Why polling instead of callbacks:
   * - az login is external process - no direct callback available
   * - Polling is simple, reliable, and easy to debug
   * - 5-second interval is good UX (responsive but not excessive)
   *
   * Polling stops when:
   * - Authentication succeeds (200 response)
   * - Authentication expires (user took too long)
   * - User cancels the modal
   * - Component unmounts
   */
  useEffect(() => {
    // Only poll if explicitly activated (after Sign In clicked)
    if (!pollingActive || !pollingTenantType || !pollingTenantId) {
      return;
    }

    console.log(`Polling for ${pollingTenantType} tenant auth completion...`);

    const pollInterval = setInterval(async () => {
      try {
        // Check if az login completed and token is available
        const response = await axios.get('http://localhost:3001/api/auth/azure-cli/status', {
          params: {
            tenantType: pollingTenantType,
            tenantId: pollingTenantId,
          },
        });

        const status = response.data;

        if (status.success) {
          // ✅ SUCCESS: Authentication completed in browser!
          // Backend retrieved token and validated tenant matches
          console.log(`✅ ${pollingTenantType} tenant authenticated successfully`);

          const authState: AuthState = {
            authenticated: true,
            accessToken: status.accessToken,
            expiresAt: status.expiresAt,
          };

          // Update appropriate tenant auth state (source or target)
          if (pollingTenantType === 'source') {
            setSourceAuth(authState);
          } else {
            setTargetAuth(authState);
          }

          // Stop polling - authentication complete
          setPollingActive(false);
          setDeviceCodeInfo(null);
          setPollingTenantType(null);
          setPollingTenantId(null);
        } else if (status.status === 'pending') {
          // ⏳ PENDING: User hasn't completed browser authentication yet
          console.log(`⏳ ${pollingTenantType} tenant auth still pending...`);
          // Continue polling - check again in 5 seconds
        } else if (status.status === 'expired') {
          // ❌ EXPIRED: Device code or login session timed out
          console.log(`❌ ${pollingTenantType} tenant auth expired`);
          setError('Login expired. Please try again.');
          setPollingActive(false);
          setDeviceCodeInfo(null);
        }
      } catch (error: any) {
        if (error.response?.status === 202) {
          // 202 Accepted - still pending, continue polling (normal case)
          console.log(`⏳ ${pollingTenantType} tenant auth pending (202)...`);
        } else {
          // Network error or server issue - log but continue polling
          // Don't stop polling on transient errors (network blips, server restart, etc.)
          console.error('Polling error:', error);
        }
      }
    }, 5000); // Poll every 5 seconds (balance between responsiveness and server load)

    // Cleanup: Stop polling when component unmounts or polling becomes inactive
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
            const response = await axios.get('http://localhost:3001/api/auth/token?tenantType=source');
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
            const response = await axios.get('http://localhost:3001/api/auth/token?tenantType=target');
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
      await axios.post('http://localhost:3001/api/auth/signout', { tenantType });

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
      await axios.post('http://localhost:3001/api/auth/signout', {});
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
