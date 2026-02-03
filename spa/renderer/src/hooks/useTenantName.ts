import { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { useAuth } from '../context/AuthContext';
import axios from 'axios';

/**
 * Hook to get current tenant name for footer display
 *
 * Tries multiple sources in priority order:
 * 1. Authenticated source tenant from Auth Tab (highest priority)
 * 2. Azure CLI current account (if logged in with az login)
 * 3. Environment variables / config (fallback)
 *
 * Why this priority order:
 * - Auth Tab authentication is most recent and explicit
 * - Azure CLI might be logged into different tenant than Auth Tab
 * - Environment variables are static fallback for development
 *
 * Task 27 Fix: Now checks AuthContext first to show authenticated tenant
 */
export const useTenantName = (): string => {
  const { state } = useApp();
  const auth = useAuth();
  const [tenantName, setTenantName] = useState<string>('');

  useEffect(() => {
    const getTenantName = async () => {
      try {
        // PRIORITY 1: Check if authenticated via Auth Tab (source tenant)
        // This is the most reliable source - user explicitly authenticated
        if (auth.sourceAuth?.authenticated) {
          // Get tenant ID from stored token
          try {
            const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:3001';
            const response = await axios.get(`${apiUrl}/api/auth/token?tenantType=source`);
            if (response.data && response.data.tenantId) {
              setTenantName(formatTenantName(response.data.tenantId));
              return;
            }
          } catch (error) {
            // If token endpoint fails, continue to fallback methods
            // This can happen if backend restarted or token expired
          }
        }

        // PRIORITY 2: Try to get tenant from Azure CLI (az account show)
        // This works if user manually ran az login in terminal
        try {
          const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:3001';
          const response = await axios.get(`${apiUrl}/api/tenant-name`);
          if (response.data && response.data.name) {
            const name = response.data.name;
            // If it's a UUID (tenant ID), format it for display
            if (name.match(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i)) {
              setTenantName(formatTenantName(name));
            } else {
              // It's a friendly name (e.g., "DefenderATEVET17"), use as-is
              setTenantName(name);
            }
            return;
          }
        } catch (error) {
          // Azure CLI not logged in or backend endpoint unavailable
          // Continue to next fallback
        }

        // PRIORITY 3: Fallback to environment variables or config
        // This is static configuration, used when no active authentication
        const tenantId = state.config.tenantId || await window.electronAPI.env.get('AZURE_TENANT_ID');

        if (!tenantId) {
          setTenantName('No Tenant');
          return;
        }

        // Format the tenant ID for display
        setTenantName(formatTenantName(tenantId));
      } catch (error) {
        // All methods failed - show unknown
        setTenantName('Unknown');
      }
    };

    getTenantName();
    // Re-run when auth state changes (user logs in/out)
  }, [state.config.tenantId, auth.sourceAuth]);

  return tenantName;
};

/**
 * Format tenant ID for compact display in footer
 *
 * Handles different tenant ID formats:
 * - Domain format: "defenderatevet.onmicrosoft.com" → "Defenderatevet"
 * - UUID format: "3cd87a41-1f61-4aef-a212-cefdecd9a2d1" → "3cd87a41...a2d1"
 * - Short format: "contoso" → "contoso" (unchanged)
 *
 * Why truncate UUIDs:
 * - Full UUID takes too much footer space
 * - First 8 and last 4 chars are usually sufficient for identification
 * - User can click to see full ID if needed
 *
 * @param tenantId - Azure tenant ID (UUID or domain)
 * @returns Formatted tenant name for display
 */
function formatTenantName(tenantId: string): string {
  if (!tenantId) return 'No Tenant';

  // If it's a domain (contains dots), extract the primary domain name
  if (tenantId.includes('.')) {
    const parts = tenantId.split('.');
    // For domains like "defenderatevet.onmicrosoft.com", return "Defenderatevet"
    // Capitalize first letter for consistency
    if (parts.length > 0) {
      return parts[0].charAt(0).toUpperCase() + parts[0].slice(1);
    }
  }

  // If it's a UUID or other long format, show truncated version
  // Example: "3cd87a41-1f61-4aef-a212-cefdecd9a2d1" → "3cd87a41...a2d1"
  if (tenantId.length > 20) {
    return `${tenantId.substring(0, 8)}...${tenantId.substring(tenantId.length - 4)}`;
  }

  // Short format - return as-is
  return tenantId;
}
