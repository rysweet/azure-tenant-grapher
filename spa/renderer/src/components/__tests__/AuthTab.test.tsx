/**
 * TDD Tests for AuthTab Component
 *
 * Testing Strategy:
 * - Unit tests (60% of test suite)
 * - Mock AuthContext
 * - Test UI rendering, button states, tenant cards
 *
 * These tests will FAIL initially (TDD approach) until implementation is complete.
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { AuthTab } from '../tabs/AuthTab';
import { useAuth } from '../../context/AuthContext';

// Mock AuthContext
jest.mock('../../context/AuthContext');
const mockUseAuth = useAuth as jest.MockedFunction<typeof useAuth>;

describe('AuthTab - Unit Tests (60% coverage)', () => {
  const mockStartDeviceCodeFlow = jest.fn();
  const mockSignOut = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();

    mockUseAuth.mockReturnValue({
      sourceAuth: null,
      targetAuth: null,
      canScan: false,
      canDeploy: false,
      startDeviceCodeFlow: mockStartDeviceCodeFlow,
      signOut: mockSignOut,
      signOutAll: jest.fn(),
      isLoading: false,
    });
  });

  describe('Rendering', () => {
    it('should render two tenant cards (source and target)', () => {
      render(<AuthTab sourceTenantId="source-123" targetTenantId="target-456" />);

      expect(screen.getByText(/Source Tenant/i)).toBeInTheDocument();
      expect(screen.getByText(/Target \/ Gameboard Tenant/i)).toBeInTheDocument();
    });

    it('should display tenant IDs', () => {
      render(<AuthTab sourceTenantId="source-tenant-123" targetTenantId="target-tenant-456" />);

      expect(screen.getByText(/source-tenant-123/i)).toBeInTheDocument();
      expect(screen.getByText(/target-tenant-456/i)).toBeInTheDocument();
    });

    it('should show Sign In buttons when not authenticated', () => {
      render(<AuthTab sourceTenantId="source-123" targetTenantId="target-456" />);

      const signInButtons = screen.getAllByText(/Sign In/i);
      expect(signInButtons).toHaveLength(2);
    });

    it('should show Sign Out buttons when authenticated', () => {
      mockUseAuth.mockReturnValue({
        sourceAuth: {
          accessToken: 'source-token',
          expiresAt: Date.now() + 3600000,
          tenantId: 'source-123',
        },
        targetAuth: {
          accessToken: 'target-token',
          expiresAt: Date.now() + 3600000,
          tenantId: 'target-456',
        },
        canScan: true,
        canDeploy: true,
        startDeviceCodeFlow: mockStartDeviceCodeFlow,
        signOut: mockSignOut,
        signOutAll: jest.fn(),
        isLoading: false,
      });

      render(<AuthTab sourceTenantId="source-123" targetTenantId="target-456" />);

      const signOutButtons = screen.getAllByText(/Sign Out/i);
      expect(signOutButtons).toHaveLength(2);
    });
  });

  describe('Status Indicators', () => {
    it('should show "Not Authenticated" status when no auth', () => {
      render(<AuthTab sourceTenantId="source-123" targetTenantId="target-456" />);

      const notAuthStatuses = screen.getAllByText(/Not Authenticated/i);
      expect(notAuthStatuses).toHaveLength(2);
    });

    it('should show "Authenticated" status with checkmark when authenticated', () => {
      mockUseAuth.mockReturnValue({
        sourceAuth: {
          accessToken: 'source-token',
          expiresAt: Date.now() + 3600000,
          tenantId: 'source-123',
        },
        targetAuth: null,
        canScan: true,
        canDeploy: false,
        startDeviceCodeFlow: mockStartDeviceCodeFlow,
        signOut: mockSignOut,
        signOutAll: jest.fn(),
        isLoading: false,
      });

      render(<AuthTab sourceTenantId="source-123" targetTenantId="target-456" />);

      expect(screen.getByText(/Authenticated/i)).toBeInTheDocument();
      // Should have checkmark icon
      expect(screen.getByTestId('check-circle-icon')).toBeInTheDocument();
    });

    it('should show token expiration time', () => {
      const expiresAt = Date.now() + 3600000; // 1 hour from now

      mockUseAuth.mockReturnValue({
        sourceAuth: {
          accessToken: 'source-token',
          expiresAt,
          tenantId: 'source-123',
        },
        targetAuth: null,
        canScan: true,
        canDeploy: false,
        startDeviceCodeFlow: mockStartDeviceCodeFlow,
        signOut: mockSignOut,
        signOutAll: jest.fn(),
        isLoading: false,
      });

      render(<AuthTab sourceTenantId="source-123" targetTenantId="target-456" />);

      // Should show "Expires in ~60 minutes"
      expect(screen.getByText(/Expires in/i)).toBeInTheDocument();
      expect(screen.getByText(/60 minutes/i)).toBeInTheDocument();
    });

    it('should show warning when token expires soon (< 10 minutes)', () => {
      const expiresAt = Date.now() + 480000; // 8 minutes from now

      mockUseAuth.mockReturnValue({
        sourceAuth: {
          accessToken: 'source-token',
          expiresAt,
          tenantId: 'source-123',
        },
        targetAuth: null,
        canScan: true,
        canDeploy: false,
        startDeviceCodeFlow: mockStartDeviceCodeFlow,
        signOut: mockSignOut,
        signOutAll: jest.fn(),
        isLoading: false,
      });

      render(<AuthTab sourceTenantId="source-123" targetTenantId="target-456" />);

      // Should show warning icon and message
      expect(screen.getByTestId('warning-icon')).toBeInTheDocument();
      expect(screen.getByText(/Expires soon/i)).toBeInTheDocument();
    });
  });

  describe('User Interactions', () => {
    it('should call startDeviceCodeFlow when Sign In clicked', () => {
      render(<AuthTab sourceTenantId="source-123" targetTenantId="target-456" />);

      const signInButtons = screen.getAllByText(/Sign In/i);
      fireEvent.click(signInButtons[0]); // Click source tenant sign in

      expect(mockStartDeviceCodeFlow).toHaveBeenCalledWith('source', 'source-123');
    });

    it('should call signOut when Sign Out clicked', () => {
      mockUseAuth.mockReturnValue({
        sourceAuth: {
          accessToken: 'source-token',
          expiresAt: Date.now() + 3600000,
          tenantId: 'source-123',
        },
        targetAuth: null,
        canScan: true,
        canDeploy: false,
        startDeviceCodeFlow: mockStartDeviceCodeFlow,
        signOut: mockSignOut,
        signOutAll: jest.fn(),
        isLoading: false,
      });

      render(<AuthTab sourceTenantId="source-123" targetTenantId="target-456" />);

      const signOutButton = screen.getByText(/Sign Out/i);
      fireEvent.click(signOutButton);

      expect(mockSignOut).toHaveBeenCalledWith('source');
    });

    it('should open AuthLoginModal when Sign In clicked', () => {
      render(<AuthTab sourceTenantId="source-123" targetTenantId="target-456" />);

      const signInButtons = screen.getAllByText(/Sign In/i);
      fireEvent.click(signInButtons[0]);

      // Modal should be visible
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText(/Sign in to Source Tenant/i)).toBeInTheDocument();
    });

    it('should close modal on successful authentication', async () => {
      const { rerender } = render(<AuthTab sourceTenantId="source-123" targetTenantId="target-456" />);

      const signInButtons = screen.getAllByText(/Sign In/i);
      fireEvent.click(signInButtons[0]);

      // Modal is open
      expect(screen.getByRole('dialog')).toBeInTheDocument();

      // Simulate authentication success
      mockUseAuth.mockReturnValue({
        sourceAuth: {
          accessToken: 'source-token',
          expiresAt: Date.now() + 3600000,
          tenantId: 'source-123',
        },
        targetAuth: null,
        canScan: true,
        canDeploy: false,
        startDeviceCodeFlow: mockStartDeviceCodeFlow,
        signOut: mockSignOut,
        signOutAll: jest.fn(),
        isLoading: false,
      });

      rerender(<AuthTab sourceTenantId="source-123" targetTenantId="target-456" />);

      // Modal should close
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  describe('Feature Gates Display', () => {
    it('should show "Scanning Enabled" when source tenant authenticated', () => {
      mockUseAuth.mockReturnValue({
        sourceAuth: {
          accessToken: 'source-token',
          expiresAt: Date.now() + 3600000,
          tenantId: 'source-123',
        },
        targetAuth: null,
        canScan: true,
        canDeploy: false,
        startDeviceCodeFlow: mockStartDeviceCodeFlow,
        signOut: mockSignOut,
        signOutAll: jest.fn(),
        isLoading: false,
      });

      render(<AuthTab sourceTenantId="source-123" targetTenantId="target-456" />);

      expect(screen.getByText(/Scanning Enabled/i)).toBeInTheDocument();
      expect(screen.getByText(/Deployment Disabled/i)).toBeInTheDocument();
    });

    it('should show "Deployment Enabled" when both tenants authenticated', () => {
      mockUseAuth.mockReturnValue({
        sourceAuth: {
          accessToken: 'source-token',
          expiresAt: Date.now() + 3600000,
          tenantId: 'source-123',
        },
        targetAuth: {
          accessToken: 'target-token',
          expiresAt: Date.now() + 3600000,
          tenantId: 'target-456',
        },
        canScan: true,
        canDeploy: true,
        startDeviceCodeFlow: mockStartDeviceCodeFlow,
        signOut: mockSignOut,
        signOutAll: jest.fn(),
        isLoading: false,
      });

      render(<AuthTab sourceTenantId="source-123" targetTenantId="target-456" />);

      expect(screen.getByText(/Scanning Enabled/i)).toBeInTheDocument();
      expect(screen.getByText(/Deployment Enabled/i)).toBeInTheDocument();
    });

    it('should show "All Features Disabled" when no authentication', () => {
      render(<AuthTab sourceTenantId="source-123" targetTenantId="target-456" />);

      expect(screen.getByText(/Scanning Disabled/i)).toBeInTheDocument();
      expect(screen.getByText(/Deployment Disabled/i)).toBeInTheDocument();
    });
  });

  describe('Loading States', () => {
    it('should disable Sign In button while loading', () => {
      mockUseAuth.mockReturnValue({
        sourceAuth: null,
        targetAuth: null,
        canScan: false,
        canDeploy: false,
        startDeviceCodeFlow: mockStartDeviceCodeFlow,
        signOut: mockSignOut,
        signOutAll: jest.fn(),
        isLoading: true,
      });

      render(<AuthTab sourceTenantId="source-123" targetTenantId="target-456" />);

      const signInButtons = screen.getAllByText(/Sign In/i);
      expect(signInButtons[0]).toBeDisabled();
    });

    it('should show spinner during authentication', () => {
      mockUseAuth.mockReturnValue({
        sourceAuth: null,
        targetAuth: null,
        canScan: false,
        canDeploy: false,
        startDeviceCodeFlow: mockStartDeviceCodeFlow,
        signOut: mockSignOut,
        signOutAll: jest.fn(),
        isLoading: true,
      });

      render(<AuthTab sourceTenantId="source-123" targetTenantId="target-456" />);

      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('should display error message when authentication fails', () => {
      mockUseAuth.mockReturnValue({
        sourceAuth: null,
        targetAuth: null,
        canScan: false,
        canDeploy: false,
        startDeviceCodeFlow: mockStartDeviceCodeFlow,
        signOut: mockSignOut,
        signOutAll: jest.fn(),
        isLoading: false,
        error: 'Authentication failed: Network error',
      });

      render(<AuthTab sourceTenantId="source-123" targetTenantId="target-456" />);

      expect(screen.getByText(/Authentication failed/i)).toBeInTheDocument();
      expect(screen.getByTestId('error-icon')).toBeInTheDocument();
    });

    it('should allow retry after error', () => {
      mockUseAuth.mockReturnValue({
        sourceAuth: null,
        targetAuth: null,
        canScan: false,
        canDeploy: false,
        startDeviceCodeFlow: mockStartDeviceCodeFlow,
        signOut: mockSignOut,
        signOutAll: jest.fn(),
        isLoading: false,
        error: 'Authentication failed',
      });

      render(<AuthTab sourceTenantId="source-123" targetTenantId="target-456" />);

      const signInButtons = screen.getAllByText(/Sign In/i);
      fireEvent.click(signInButtons[0]);

      // Should call startDeviceCodeFlow again
      expect(mockStartDeviceCodeFlow).toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    it('should have accessible labels for tenant cards', () => {
      render(<AuthTab sourceTenantId="source-123" targetTenantId="target-456" />);

      expect(screen.getByRole('region', { name: /Source Tenant/i })).toBeInTheDocument();
      expect(screen.getByRole('region', { name: /Target.*Tenant/i })).toBeInTheDocument();
    });

    it('should have accessible button labels', () => {
      render(<AuthTab sourceTenantId="source-123" targetTenantId="target-456" />);

      expect(screen.getByRole('button', { name: /Sign In to Source Tenant/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Sign In to Target.*Tenant/i })).toBeInTheDocument();
    });

    it('should support keyboard navigation', () => {
      render(<AuthTab sourceTenantId="source-123" targetTenantId="target-456" />);

      const signInButtons = screen.getAllByText(/Sign In/i);

      // Should be focusable
      signInButtons[0].focus();
      expect(document.activeElement).toBe(signInButtons[0]);

      // Should activate on Enter key
      fireEvent.keyDown(signInButtons[0], { key: 'Enter' });
      expect(mockStartDeviceCodeFlow).toHaveBeenCalled();
    });
  });
});
