/**
 * AuthTab Component
 *
 * Tab for managing Azure tenant authentication via Azure CLI device code flow.
 * Displays two tenant cards (source and gameboard) with sign in/out buttons.
 *
 * Authentication Flow (Task 26 - Az Login Integration):
 * 1. User enters tenant ID in text field
 * 2. User clicks "Sign In" button
 * 3. Backend triggers `az login --tenant <id> --use-device-code`
 * 4. Device code modal appears with code (e.g., "ABC123")
 * 5. User opens browser to https://microsoft.com/device
 * 6. User enters code and completes Microsoft authentication
 * 7. Frontend polls backend every 5 seconds
 * 8. When complete, UI updates to "✅ Authenticated"
 * 9. Footer shows tenant ID (Task 27)
 *
 * Features:
 * - Dual-tenant support (source and gameboard/target)
 * - Real-time authentication status
 * - Token expiry countdown display
 * - Device code modal with QR code
 * - Feature gates (Scan requires source, Deploy requires both)
 * - Error display with clear instructions
 *
 * Security:
 * - Uses Azure CLI (no hardcoded credentials)
 * - Tenant validation (prevents cross-tenant attacks)
 * - Tokens stored securely in backend
 * - No sensitive data in localStorage
 *
 * Philosophy:
 * - Single responsibility: Authentication UI
 * - Uses AuthContext for state management
 * - Uses AuthLoginModal for device code display
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
  TextField,
} from '@mui/material';
import {
  CheckCircle as CheckIcon,
  Cancel as CancelIcon,
} from '@mui/icons-material';
import { useAuth } from '../../context/AuthContext';
import { AuthLoginModal } from '../AuthLoginModal';

export const AuthTab: React.FC = () => {
  const auth = useAuth();
  const [modalOpen, setModalOpen] = useState(false);
  const [currentTenant, setCurrentTenant] = useState<'source' | 'target'>('source');
  const [sourceTenantId, setSourceTenantId] = useState('');
  const [targetTenantId, setTargetTenantId] = useState('');

  /**
   * Handle Sign In button click
   *
   * Initiates the Azure CLI authentication flow for a tenant.
   * This is the main entry point for user authentication.
   *
   * Steps:
   * 1. Validate tenant ID is not empty
   * 2. Call auth.startDeviceCodeFlow() which:
   *    - Calls backend /azure-cli/login endpoint
   *    - Backend spawns `az login --tenant <id> --use-device-code`
   *    - Backend captures and returns device code
   * 3. Open modal to display device code to user
   * 4. User completes authentication in browser
   * 5. Polling (in AuthContext) detects completion and updates UI
   *
   * Error handling:
   * - Empty tenant ID → Alert user to enter valid ID
   * - Backend errors → Show error message with details
   * - Network errors → Show generic error message
   *
   * @param tenantType - 'source' or 'target' tenant
   * @param tenantId - Azure tenant ID entered by user
   */
  const handleSignIn = async (tenantType: 'source' | 'target', tenantId: string) => {
    try {
      // Validate user entered a tenant ID
      if (!tenantId || tenantId.trim() === '') {
        alert('Please enter a valid Tenant ID');
        return;
      }

      setCurrentTenant(tenantType);

      console.log(`Starting sign in for ${tenantType} tenant...`);

      // Trigger az login subprocess on backend
      // This returns device code info for modal display
      await auth.startDeviceCodeFlow(tenantType, tenantId);

      // Open modal to show device code to user
      // Modal displays code, URL, and QR code
      setModalOpen(true);

      console.log('Device code modal opened - user should complete authentication');

    } catch (error: any) {
      console.error('Failed to start sign in:', error);
      const errorMessage = error.message || 'Authentication failed';
      alert(`❌ Authentication Failed\n\n${errorMessage}`);
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
    label: string
  ) => {
    const authState = tenantType === 'source' ? auth.sourceAuth : auth.targetAuth;
    const isAuthenticated = authState?.authenticated ?? false;
    const tenantId = tenantType === 'source' ? sourceTenantId : targetTenantId;
    const setTenantId = tenantType === 'source' ? setSourceTenantId : setTargetTenantId;

    return (
      <Card sx={{ height: '100%' }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {label}
          </Typography>

          {/* Tenant ID input */}
          <TextField
            fullWidth
            label="Tenant ID or Domain"
            value={tenantId}
            onChange={(e) => setTenantId(e.target.value)}
            disabled={isAuthenticated}
            size="small"
            placeholder="e.g., contoso.onmicrosoft.com"
            sx={{ mb: 2 }}
          />

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

      {/* Error display */}
      {auth.error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => {}}>
          <Typography variant="body2">
            <strong>Authentication Failed:</strong> {auth.error}
          </Typography>
        </Alert>
      )}

      {/* Tenant cards */}
      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          {renderTenantCard('source', 'Source Tenant')}
        </Grid>
        <Grid item xs={12} md={6}>
          {renderTenantCard('target', 'Target / Gameboard Tenant')}
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

export default AuthTab;
