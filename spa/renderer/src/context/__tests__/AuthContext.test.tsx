/**
 * TDD Tests for AuthContext
 *
 * Testing Strategy:
 * - Unit tests (60% of test suite)
 * - Mock API calls to backend
 * - Test state management, polling, auto-refresh
 *
 * These tests will FAIL initially (TDD approach) until implementation is complete.
 */

import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import { AuthProvider, useAuth } from '../AuthContext';
import axios from 'axios';

// Mock axios
jest.mock('axios');
const mockAxios = axios as jest.Mocked<typeof axios>;

// Test component to access context
const TestComponent = () => {
  const auth = useAuth();
  return (
    <div>
      <div data-testid="source-auth">{auth.sourceAuth ? 'authenticated' : 'not-authenticated'}</div>
      <div data-testid="target-auth">{auth.targetAuth ? 'authenticated' : 'not-authenticated'}</div>
      <button onClick={() => auth.startDeviceCodeFlow('source', 'source-tenant-id')}>
        Sign In Source
      </button>
      <button onClick={() => auth.signOut('source')}>Sign Out Source</button>
    </div>
  );
};

describe('AuthContext - Unit Tests (60% coverage)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('Initial State', () => {
    it('should initialize with both tenants unauthenticated', () => {
      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      expect(screen.getByTestId('source-auth')).toHaveTextContent('not-authenticated');
      expect(screen.getByTestId('target-auth')).toHaveTextContent('not-authenticated');
    });

    it('should check existing tokens on mount', async () => {
      mockAxios.get.mockResolvedValueOnce({
        data: {
          accessToken: 'existing-source-token',
          expiresAt: Date.now() + 3600000,
        },
      });

      mockAxios.get.mockResolvedValueOnce({
        data: {
          accessToken: 'existing-target-token',
          expiresAt: Date.now() + 3600000,
        },
      });

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(mockAxios.get).toHaveBeenCalledWith('/api/auth/token?tenantType=source');
        expect(mockAxios.get).toHaveBeenCalledWith('/api/auth/token?tenantType=target');
      });
    });
  });

  describe('Device Code Flow', () => {
    it('should start device code flow for source tenant', async () => {
      const mockDeviceCode = {
        userCode: 'ABCD1234',
        verificationUri: 'https://microsoft.com/devicelogin',
        expiresIn: 900,
        message: 'Enter code ABCD1234',
      };

      mockAxios.post.mockResolvedValueOnce({ data: mockDeviceCode });

      const { container } = render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      const button = screen.getByText('Sign In Source');
      act(() => {
        button.click();
      });

      await waitFor(() => {
        expect(mockAxios.post).toHaveBeenCalledWith('/api/auth/device-code/start', {
          tenantType: 'source',
          tenantId: 'source-tenant-id',
        });
      });
    });

    it('should poll for authentication status after starting flow', async () => {
      const mockDeviceCode = {
        userCode: 'ABCD1234',
        verificationUri: 'https://microsoft.com/devicelogin',
        expiresIn: 900,
        message: 'Enter code ABCD1234',
      };

      mockAxios.post.mockResolvedValueOnce({ data: mockDeviceCode });

      // First poll: pending
      mockAxios.get.mockResolvedValueOnce({
        data: {
          success: false,
          status: 'pending',
          message: 'User has not authenticated',
        },
        status: 202,
      });

      // Second poll: success
      mockAxios.get.mockResolvedValueOnce({
        data: {
          success: true,
          accessToken: 'mock-access-token',
          expiresAt: Date.now() + 3600000,
        },
        status: 200,
      });

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      const button = screen.getByText('Sign In Source');
      act(() => {
        button.click();
      });

      await waitFor(() => {
        expect(mockAxios.post).toHaveBeenCalled();
      });

      // Advance timer to trigger polling
      act(() => {
        jest.advanceTimersByTime(5000); // 5 seconds
      });

      await waitFor(() => {
        expect(mockAxios.get).toHaveBeenCalledWith('/api/auth/device-code/status', {
          params: {
            tenantType: 'source',
            tenantId: 'source-tenant-id',
          },
        });
      });
    });

    it('should update state when authentication succeeds', async () => {
      const mockDeviceCode = {
        userCode: 'ABCD1234',
        verificationUri: 'https://microsoft.com/devicelogin',
        expiresIn: 900,
        message: 'Enter code ABCD1234',
      };

      mockAxios.post.mockResolvedValueOnce({ data: mockDeviceCode });
      mockAxios.get.mockResolvedValueOnce({
        data: {
          success: true,
          accessToken: 'mock-access-token',
          expiresAt: Date.now() + 3600000,
        },
        status: 200,
      });

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      const button = screen.getByText('Sign In Source');
      act(() => {
        button.click();
      });

      await waitFor(() => {
        expect(screen.getByTestId('source-auth')).toHaveTextContent('authenticated');
      });
    });

    it('should stop polling when authentication succeeds', async () => {
      const mockDeviceCode = {
        userCode: 'ABCD1234',
        verificationUri: 'https://microsoft.com/devicelogin',
        expiresIn: 900,
        message: 'Enter code ABCD1234',
      };

      mockAxios.post.mockResolvedValueOnce({ data: mockDeviceCode });
      mockAxios.get.mockResolvedValueOnce({
        data: {
          success: true,
          accessToken: 'mock-access-token',
          expiresAt: Date.now() + 3600000,
        },
        status: 200,
      });

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      const button = screen.getByText('Sign In Source');
      act(() => {
        button.click();
      });

      await waitFor(() => {
        expect(mockAxios.get).toHaveBeenCalled();
      });

      // Advance timer further - should not poll again
      const callCount = mockAxios.get.mock.calls.length;

      act(() => {
        jest.advanceTimersByTime(10000);
      });

      await waitFor(() => {
        expect(mockAxios.get.mock.calls.length).toBe(callCount); // No additional calls
      });
    });

    it('should handle authentication timeout', async () => {
      const mockDeviceCode = {
        userCode: 'ABCD1234',
        verificationUri: 'https://microsoft.com/devicelogin',
        expiresIn: 900,
        message: 'Enter code ABCD1234',
      };

      mockAxios.post.mockResolvedValueOnce({ data: mockDeviceCode });
      mockAxios.get.mockResolvedValueOnce({
        data: {
          success: false,
          status: 'expired',
          message: 'Device code has expired',
        },
        status: 408,
      });

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      const button = screen.getByText('Sign In Source');
      act(() => {
        button.click();
      });

      await waitFor(() => {
        expect(screen.getByTestId('source-auth')).toHaveTextContent('not-authenticated');
      });
    });
  });

  describe('Auto-Refresh', () => {
    it('should start auto-refresh timer when authenticated', async () => {
      const mockToken = {
        accessToken: 'mock-access-token',
        expiresAt: Date.now() + 3600000,
      };

      mockAxios.get.mockResolvedValueOnce({ data: mockToken });

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(mockAxios.get).toHaveBeenCalled();
      });

      // Advance timer to trigger refresh (4 minutes)
      mockAxios.get.mockResolvedValueOnce({
        data: {
          accessToken: 'refreshed-token',
          expiresAt: Date.now() + 3600000,
        },
      });

      act(() => {
        jest.advanceTimersByTime(240000); // 4 minutes
      });

      await waitFor(() => {
        expect(mockAxios.get).toHaveBeenCalledWith('/api/auth/token?tenantType=source');
      });
    });

    it('should refresh token before expiry (5 min buffer)', async () => {
      const expiringToken = {
        accessToken: 'expiring-token',
        expiresAt: Date.now() + 240000, // 4 minutes
      };

      mockAxios.get.mockResolvedValueOnce({ data: expiringToken });

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(mockAxios.get).toHaveBeenCalled();
      });

      // Trigger refresh
      mockAxios.post.mockResolvedValueOnce({
        data: {
          accessToken: 'refreshed-token',
          expiresAt: Date.now() + 3600000,
        },
      });

      act(() => {
        jest.advanceTimersByTime(240000);
      });

      await waitFor(() => {
        expect(mockAxios.post).toHaveBeenCalledWith('/api/auth/refresh', {
          tenantType: 'source',
        });
      });
    });

    it('should stop auto-refresh on sign out', async () => {
      mockAxios.post.mockResolvedValueOnce({ data: { success: true } });

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      const signOutButton = screen.getByText('Sign Out Source');
      act(() => {
        signOutButton.click();
      });

      await waitFor(() => {
        expect(mockAxios.post).toHaveBeenCalledWith('/api/auth/signout', {
          tenantType: 'source',
        });
      });

      // Advance timer - should not refresh
      const callCount = mockAxios.get.mock.calls.length;

      act(() => {
        jest.advanceTimersByTime(240000);
      });

      expect(mockAxios.get.mock.calls.length).toBe(callCount);
    });
  });

  describe('Sign Out', () => {
    it('should sign out source tenant', async () => {
      mockAxios.post.mockResolvedValueOnce({ data: { success: true } });

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      const button = screen.getByText('Sign Out Source');
      act(() => {
        button.click();
      });

      await waitFor(() => {
        expect(mockAxios.post).toHaveBeenCalledWith('/api/auth/signout', {
          tenantType: 'source',
        });
        expect(screen.getByTestId('source-auth')).toHaveTextContent('not-authenticated');
      });
    });

    it('should sign out all tenants', async () => {
      mockAxios.post.mockResolvedValueOnce({ data: { success: true } });

      const TestComponentAll = () => {
        const auth = useAuth();
        return <button onClick={() => auth.signOutAll()}>Sign Out All</button>;
      };

      render(
        <AuthProvider>
          <TestComponentAll />
        </AuthProvider>
      );

      const button = screen.getByText('Sign Out All');
      act(() => {
        button.click();
      });

      await waitFor(() => {
        expect(mockAxios.post).toHaveBeenCalledWith('/api/auth/signout', {});
      });
    });
  });

  describe('Feature Gates', () => {
    it('should enable scanning when source tenant authenticated', async () => {
      const mockToken = {
        accessToken: 'source-token',
        expiresAt: Date.now() + 3600000,
      };

      mockAxios.get.mockResolvedValueOnce({ data: mockToken });

      const TestFeatureGates = () => {
        const auth = useAuth();
        return <div data-testid="can-scan">{auth.canScan ? 'yes' : 'no'}</div>;
      };

      render(
        <AuthProvider>
          <TestFeatureGates />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('can-scan')).toHaveTextContent('yes');
      });
    });

    it('should enable deployment when both tenants authenticated', async () => {
      mockAxios.get.mockResolvedValueOnce({
        data: {
          accessToken: 'source-token',
          expiresAt: Date.now() + 3600000,
        },
      });

      mockAxios.get.mockResolvedValueOnce({
        data: {
          accessToken: 'target-token',
          expiresAt: Date.now() + 3600000,
        },
      });

      const TestFeatureGates = () => {
        const auth = useAuth();
        return <div data-testid="can-deploy">{auth.canDeploy ? 'yes' : 'no'}</div>;
      };

      render(
        <AuthProvider>
          <TestFeatureGates />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('can-deploy')).toHaveTextContent('yes');
      });
    });

    it('should disable deployment when only source tenant authenticated', async () => {
      mockAxios.get.mockResolvedValueOnce({
        data: {
          accessToken: 'source-token',
          expiresAt: Date.now() + 3600000,
        },
      });

      mockAxios.get.mockResolvedValueOnce({
        data: null,
      });

      const TestFeatureGates = () => {
        const auth = useAuth();
        return <div data-testid="can-deploy">{auth.canDeploy ? 'yes' : 'no'}</div>;
      };

      render(
        <AuthProvider>
          <TestFeatureGates />
        </AuthProvider>
      );

      await waitFor(() => {
        expect(screen.getByTestId('can-deploy')).toHaveTextContent('no');
      });
    });
  });

  describe('Error Handling', () => {
    it('should handle API errors gracefully', async () => {
      mockAxios.post.mockRejectedValueOnce(new Error('Network error'));

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      const button = screen.getByText('Sign In Source');
      act(() => {
        button.click();
      });

      await waitFor(() => {
        expect(screen.getByTestId('source-auth')).toHaveTextContent('not-authenticated');
      });
    });

    it('should handle polling errors', async () => {
      const mockDeviceCode = {
        userCode: 'ABCD1234',
        verificationUri: 'https://microsoft.com/devicelogin',
        expiresIn: 900,
        message: 'Enter code ABCD1234',
      };

      mockAxios.post.mockResolvedValueOnce({ data: mockDeviceCode });
      mockAxios.get.mockRejectedValueOnce(new Error('Polling failed'));

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      const button = screen.getByText('Sign In Source');
      act(() => {
        button.click();
      });

      await waitFor(() => {
        expect(screen.getByTestId('source-auth')).toHaveTextContent('not-authenticated');
      });
    });
  });

  describe('Edge Cases', () => {
    it('should handle concurrent sign-in requests', async () => {
      const mockDeviceCode = {
        userCode: 'ABCD1234',
        verificationUri: 'https://microsoft.com/devicelogin',
        expiresIn: 900,
        message: 'Enter code ABCD1234',
      };

      mockAxios.post.mockResolvedValue({ data: mockDeviceCode });

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      const button = screen.getByText('Sign In Source');

      // Click multiple times rapidly
      act(() => {
        button.click();
        button.click();
        button.click();
      });

      await waitFor(() => {
        // Should only call API once (debounced)
        expect(mockAxios.post).toHaveBeenCalledTimes(1);
      });
    });

    it('should cleanup timers on unmount', async () => {
      const clearIntervalSpy = jest.spyOn(global, 'clearInterval');

      const { unmount } = render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      );

      unmount();

      expect(clearIntervalSpy).toHaveBeenCalled();
    });
  });
});
