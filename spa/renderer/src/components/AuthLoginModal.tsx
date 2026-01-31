/**
 * AuthLoginModal Component
 *
 * Modal dialog for displaying Device Code Flow instructions.
 * Shows user code, verification URL, QR code, and countdown timer.
 *
 * Features:
 * - Large, prominent device code display
 * - Clickable verification URL (opens in new tab)
 * - QR code for mobile authentication
 * - Countdown timer with auto-close on expiry
 * - Copy-to-clipboard functionality
 *
 * Philosophy:
 * - Single responsibility: Display auth instructions
 * - Uses Material-UI components
 * - Self-contained and regeneratable
 */

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Link,
  IconButton,
  Alert,
} from '@mui/material';
import { ContentCopy as CopyIcon } from '@mui/icons-material';
import { QRCodeCanvas } from 'qrcode.react';

export interface DeviceCodeInfo {
  userCode: string;
  verificationUri: string;
  expiresIn: number;
  message: string;
}

export interface AuthLoginModalProps {
  open: boolean;
  onClose: () => void;
  tenantType: 'source' | 'target';
  deviceCodeInfo: DeviceCodeInfo | null;
}

export const AuthLoginModal: React.FC<AuthLoginModalProps> = ({
  open,
  onClose,
  tenantType,
  deviceCodeInfo,
}) => {
  const [timeRemaining, setTimeRemaining] = useState<number>(0);
  const [copied, setCopied] = useState(false);

  // Initialize timer when modal opens
  useEffect(() => {
    if (open && deviceCodeInfo) {
      setTimeRemaining(deviceCodeInfo.expiresIn);
    }
  }, [open, deviceCodeInfo]);

  // Countdown timer
  useEffect(() => {
    if (!open || timeRemaining <= 0) {
      return;
    }

    const timer = setInterval(() => {
      setTimeRemaining((prev) => {
        const newTime = prev - 1;
        if (newTime <= 0) {
          // Auto-close on expiry
          onClose();
          return 0;
        }
        return newTime;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [open, timeRemaining, onClose]);

  /**
   * Copy device code to clipboard
   */
  const handleCopyCode = () => {
    if (deviceCodeInfo) {
      navigator.clipboard.writeText(deviceCodeInfo.userCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  /**
   * Format time remaining as MM:SS
   */
  const formatTime = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  };

  if (!deviceCodeInfo) {
    return null;
  }

  const tenantLabel = tenantType === 'source' ? 'Source Tenant' : 'Gameboard Tenant';

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        Sign in to {tenantLabel}
      </DialogTitle>
      <DialogContent>
        <Box sx={{ textAlign: 'center', py: 2 }}>
          {/* Instructions */}
          <Typography variant="body1" gutterBottom>
            To sign in, follow these steps:
          </Typography>

          {/* Step 1: Visit URL */}
          <Box sx={{ mt: 3, mb: 2 }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              1. Open this URL in your browser:
            </Typography>
            <Link
              href={deviceCodeInfo.verificationUri}
              target="_blank"
              rel="noopener noreferrer"
              sx={{ fontSize: '16px', fontWeight: 'medium' }}
            >
              {deviceCodeInfo.verificationUri}
            </Link>
          </Box>

          {/* Step 2: Enter code */}
          <Box sx={{ mt: 3, mb: 2 }}>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              2. Enter this code:
            </Typography>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 1,
                mt: 1,
              }}
            >
              <Typography
                sx={{
                  fontSize: '24px',
                  fontWeight: 'bold',
                  fontFamily: 'monospace',
                  letterSpacing: '2px',
                  color: 'primary.main',
                }}
              >
                {deviceCodeInfo.userCode}
              </Typography>
              <IconButton
                onClick={handleCopyCode}
                size="small"
                title="Copy code"
                sx={{ ml: 1 }}
              >
                <CopyIcon fontSize="small" />
              </IconButton>
            </Box>
            {copied && (
              <Typography variant="caption" color="success.main" sx={{ mt: 1, display: 'block' }}>
                Code copied!
              </Typography>
            )}
          </Box>

          {/* QR Code */}
          <Box sx={{ mt: 4, mb: 2, display: 'flex', justifyContent: 'center' }}>
            <Box
              sx={{
                padding: 2,
                backgroundColor: 'white',
                borderRadius: 1,
                display: 'inline-block',
              }}
            >
              <QRCodeCanvas
                value={deviceCodeInfo.verificationUri}
                size={150}
                level="M"
                data-testid="qr-code"
              />
            </Box>
          </Box>
          <Typography variant="caption" color="text.secondary">
            Scan with your mobile device
          </Typography>

          {/* Countdown timer */}
          <Box sx={{ mt: 3 }}>
            <Alert severity="info" sx={{ justifyContent: 'center' }}>
              Time remaining: {formatTime(timeRemaining)}
            </Alert>
          </Box>

          {/* Polling indicator */}
          <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block' }}>
            Waiting for authentication... This modal will close automatically once you sign in.
          </Typography>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
      </DialogActions>
    </Dialog>
  );
};
