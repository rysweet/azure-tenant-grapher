import { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import axios from 'axios';

export const useTenantName = (): string => {
  const { state } = useApp();
  const [tenantName, setTenantName] = useState<string>('');

  useEffect(() => {
    const getTenantName = async () => {
      try {
        // Try to get the actual tenant name from backend
        try {
          const response = await axios.get('http://localhost:3001/api/tenant-name');
          if (response.data && response.data.name) {
            const name = response.data.name;
            // If it's a UUID, format it
            if (name.match(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i)) {
              setTenantName(formatTenantName(name));
            } else {
              setTenantName(name);
            }
            return;
          }
        } catch (error) {
          console.log('Could not get tenant name from backend');
        }
        
        // Fallback to getting from config/env and formatting
        const tenantId = state.config.tenantId || await window.electronAPI.env.get('AZURE_TENANT_ID');
        
        if (!tenantId) {
          setTenantName('No Tenant');
          return;
        }

        // Fallback to formatting the tenant ID
        setTenantName(formatTenantName(tenantId));
      } catch (error) {
        console.error('Failed to get tenant name:', error);
        setTenantName('Unknown Tenant');
      }
    };

    getTenantName();
  }, [state.config.tenantId]);

  return tenantName;
};

function formatTenantName(tenantId: string): string {
  if (!tenantId) return 'No Tenant';
  
  // If it's a domain (contains dots), extract the domain name
  if (tenantId.includes('.')) {
    const parts = tenantId.split('.');
    // For domains like "defenderatevet.onmicrosoft.com", return "DefenderATEVET"
    if (parts.length > 0) {
      return parts[0].charAt(0).toUpperCase() + parts[0].slice(1);
    }
  }
  
  // If it's a UUID or other format, show truncated version
  if (tenantId.length > 20) {
    return `${tenantId.substring(0, 8)}...${tenantId.substring(tenantId.length - 4)}`;
  }
  
  return tenantId;
}