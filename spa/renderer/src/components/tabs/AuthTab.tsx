/**
 * AuthTab Component
 *
 * Tab for managing Azure tenant authentication.
 * Displays two tenant cards (source and gameboard) with sign in/out buttons.
 *
 * Features:
 * - Tenant cards showing authentication status
 * - Sign In/Sign Out buttons
 * - Status indicators (authenticated, not authenticated)
 * - Token expiry display
 * - Device code modal integration
 *
 * Philosophy:
 * - Single responsibility: Authentication UI
 * - Uses AuthContext for state
 * - Uses AuthLoginModal for device code flow
 * - Self-contained and regeneratable
 */

import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  CardActions,
  Typography,
  Button,
  Chip,
  Grid,
  Alert,
} from '@mui/material';
import {
  CheckCircle as CheckIcon,
  Cancel as CancelIcon,
} from '@mui/icons-material';
import { useAuth } from '../../context/AuthContext';
import { AuthLoginModal } from '../AuthLoginModal';

export interface AuthTabProps {
  sourceTenantId: string;
  targetTenantId: string;
}

export const AuthTab: React.FC<AuthTabProps> = ({ sourceTenantId, targetTenantId }) => {
  const auth = useAuth();
  const [modalOpen, setModalOpen] = useState(false);
  const [currentTenant, setCurrentTenant] = useState<'source' | 'target'>('source');

  /**
   * Start sign in flow for a tenant
   */
  const handleSignIn = async (tenantType: 'source' | 'target', tenantId: string) => {
    try {
      setCurrentTenant(tenantType);
      await auth.startDeviceCodeFlow(tenantType, tenantId);
      setModalOpen(true);
    } catch (error) {
      console.error('Failed to start sign in:', error);
    }
  };

  /**
   * Sign out from a tenant
   */
  const handleSignOut = async (tenantType: 'source' | 'target') => {
    try {
      await auth.signOut(tenantType);
    } catch (error) {
      console.error('Failed to sign out:', error);
    }
  };

  /**
   * Close modal
   */
  const handleCloseModal = () => {
    setModalOpen(false);
  };

  /**
   * Format timestamp for display
   */
  const formatExpiry = (timestamp: number): string => {
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  /**
   * Calculate time until expiry
   */
  const getTimeUntilExpiry = (timestamp: number): string => {
    const now = Date.now();
    const diff = timestamp - now;

    if (diff <= 0) {
      return 'Expired';
    }

    const minutes = Math.floor(diff / 60000);
    if (minutes < 60) {
      return `${minutes} minute${minutes !== 1 ? 's' : ''}`;
    }

    const hours = Math.floor(minutes / 60);
    return `${hours} hour${hours !== 1 ? 's' : ''}`;
  };

  /**
   * Render tenant card
   */
  const renderTenantCard = (
    tenantType: 'source' | 'target',
    tenantId: string,
    label: string
  ) => {
    const authState = tenantType === 'source' ? auth.sourceAuth : auth.targetAuth;
    const isAuthenticated = authState?.authenticated ?? false;

    return (
      <Card sx={{ height: '100%' }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {label}
          </Typography>

          <Typography variant="body2" color="text.secondary" gutterBottom>
            Tenant ID: {tenantId}
          </Typography>

          {/* Status indicator */}
          <Box sx={{ mt: 2, mb: 2 }}>
            {isAuthenticated ? (
              <Chip
                icon={<CheckIcon />}
                label="Authenticated"
                color="success"
                size="small"
              />
            ) : (
              <Chip
                icon={<CancelIcon />}
                label="Not Authenticated"
                color="default"
                size="small"
              />
            )}
          </Box>

          {/* Token info */}
          {isAuthenticated && authState?.expiresAt && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="caption" color="text.secondary" display="block">
                Expires: {formatExpiry(authState.expiresAt)}
              </Typography>
              <Typography variant="caption" color="text.secondary" display="block">
                ({getTimeUntilExpiry(authState.expiresAt)} remaining)
              </Typography>
            </Box>
          )}
        </CardContent>

        <CardActions>
          {isAuthenticated ? (
            <Button
              size="small"
              variant="outlined"
              color="error"
              onClick={() => handleSignOut(tenantType)}
            >
              Sign Out
            </Button>
          ) : (
            <Button
              size="small"
              variant="contained"
              color="primary"
              onClick={() => handleSignIn(tenantType, tenantId)}
            >
              Sign In
            </Button>
          )}
        </CardActions>
      </Card>
    );
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h5" gutterBottom>
        Authentication
      </Typography>

      <Typography variant="body2" color="text.secondary" paragraph>
        Authenticate with Azure to enable scanning and deployment operations.
      </Typography>

      {/* Feature gates info */}
      <Alert severity="info" sx={{ mb: 3 }}>
        <Typography variant="body2" gutterBottom>
          <strong>Scanning:</strong> Requires Source Tenant authentication
        </Typography>
        <Typography variant="body2">
          <strong>Deployment:</strong> Requires both Source and Gameboard Tenant authentication
        </Typography>
      </Alert>

      {/* Tenant cards */}
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          {renderTenantCard('source', sourceTenantId, 'Source Tenant')}
        </Grid>
        <Grid item xs={12} md={6}>
          {renderTenantCard('target', targetTenantId, 'Target / Gameboard Tenant')}
        </Grid>
      </Grid>

      {/* Feature gates status */}
      <Box sx={{ mt: 3 }}>
        <Typography variant="subtitle2" gutterBottom>
          Available Operations:
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          <Chip
            label="Scan"
            color={auth.canScan ? 'success' : 'default'}
            size="small"
          />
          <Chip
            label="Deploy"
            color={auth.canDeploy ? 'success' : 'default'}
            size="small"
          />
        </Box>
      </Box>

      {/* Device code modal */}
      <AuthLoginModal
        open={modalOpen}
        onClose={handleCloseModal}
        tenantType={currentTenant}
        deviceCodeInfo={auth.deviceCodeInfo}
      />
    </Box>
  );
};
