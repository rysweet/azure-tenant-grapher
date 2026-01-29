/**
 * TDD Tests for AuthLoginModal Component
 *
 * Testing Strategy:
 * - Unit tests (60% of test suite)
 * - Mock QR code generation
 * - Test modal display, device code instructions, auto-close
 *
 * These tests will FAIL initially (TDD approach) until implementation is complete.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AuthLoginModal } from '../AuthLoginModal';

// Mock QR code library
jest.mock('qrcode.react', () => ({
  QRCodeCanvas: ({ value }: { value: string }) => <div data-testid="qr-code">{value}</div>,
}));

describe('AuthLoginModal - Unit Tests (60% coverage)', () => {
  const mockOnClose = jest.fn();

  const defaultDeviceCode = {
    userCode: 'ABCD-1234',
    verificationUri: 'https://microsoft.com/devicelogin',
    expiresIn: 900, // 15 minutes
    message: 'To sign in, use a web browser to open the page https://microsoft.com/devicelogin and enter the code ABCD-1234 to authenticate.',
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render modal when open', () => {
      render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
        />
      );

      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText(/Sign in to Source Tenant/i)).toBeInTheDocument();
    });

    it('should not render modal when closed', () => {
      render(
        <AuthLoginModal
          open={false}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
        />
      );

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('should display device code prominently', () => {
      render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
        />
      );

      const deviceCode = screen.getByText('ABCD-1234');
      expect(deviceCode).toBeInTheDocument();
      expect(deviceCode).toHaveStyle({ fontSize: '24px', fontWeight: 'bold' });
    });

    it('should display verification URL as clickable link', () => {
      render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
        />
      );

      const link = screen.getByRole('link', { name: /microsoft.com\/devicelogin/i });
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute('href', 'https://microsoft.com/devicelogin');
      expect(link).toHaveAttribute('target', '_blank'); // Opens in new tab
    });

    it('should display QR code for verification URL', () => {
      render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
        />
      );

      const qrCode = screen.getByTestId('qr-code');
      expect(qrCode).toBeInTheDocument();
      expect(qrCode).toHaveTextContent('https://microsoft.com/devicelogin');
    });
  });

  describe('Instructions', () => {
    it('should display step-by-step instructions', () => {
      render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
        />
      );

      expect(screen.getByText(/Step 1/i)).toBeInTheDocument();
      expect(screen.getByText(/Step 2/i)).toBeInTheDocument();
      expect(screen.getByText(/Step 3/i)).toBeInTheDocument();

      expect(screen.getByText(/Open.*microsoft.com\/devicelogin/i)).toBeInTheDocument();
      expect(screen.getByText(/Enter.*code/i)).toBeInTheDocument();
      expect(screen.getByText(/Complete.*authentication/i)).toBeInTheDocument();
    });

    it('should highlight device code in instructions', () => {
      render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
        />
      );

      const codeElements = screen.getAllByText('ABCD-1234');
      expect(codeElements.length).toBeGreaterThan(0);

      // Code should be styled differently (monospace, highlighted)
      const highlightedCode = codeElements.find(el =>
        el.className.includes('code') || el.className.includes('highlight')
      );
      expect(highlightedCode).toBeDefined();
    });
  });

  describe('Expiration Timer', () => {
    it('should display time remaining', () => {
      render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
        />
      );

      expect(screen.getByText(/Expires in/i)).toBeInTheDocument();
      expect(screen.getByText(/15 minutes/i)).toBeInTheDocument();
    });

    it('should update countdown every second', async () => {
      jest.useFakeTimers();

      render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={{ ...defaultDeviceCode, expiresIn: 60 }} // 1 minute
        />
      );

      expect(screen.getByText(/1 minute/i)).toBeInTheDocument();

      // Advance time by 10 seconds
      jest.advanceTimersByTime(10000);

      await waitFor(() => {
        expect(screen.getByText(/50 seconds/i)).toBeInTheDocument();
      });

      jest.useRealTimers();
    });

    it('should show warning when less than 2 minutes remain', () => {
      render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={{ ...defaultDeviceCode, expiresIn: 90 }} // 90 seconds
        />
      );

      expect(screen.getByTestId('warning-icon')).toBeInTheDocument();
      expect(screen.getByText(/Expires soon/i)).toBeInTheDocument();
    });

    it('should auto-close when expired', async () => {
      jest.useFakeTimers();

      render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={{ ...defaultDeviceCode, expiresIn: 5 }} // 5 seconds
        />
      );

      // Advance time past expiration
      jest.advanceTimersByTime(6000);

      await waitFor(() => {
        expect(mockOnClose).toHaveBeenCalledWith('expired');
      });

      jest.useRealTimers();
    });
  });

  describe('Copy to Clipboard', () => {
    it('should have copy button for device code', () => {
      render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
        />
      );

      const copyButton = screen.getByRole('button', { name: /Copy Code/i });
      expect(copyButton).toBeInTheDocument();
    });

    it('should copy device code to clipboard when clicked', async () => {
      const mockClipboard = {
        writeText: jest.fn().mockResolvedValue(undefined),
      };
      Object.assign(navigator, { clipboard: mockClipboard });

      render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
        />
      );

      const copyButton = screen.getByRole('button', { name: /Copy Code/i });
      fireEvent.click(copyButton);

      await waitFor(() => {
        expect(mockClipboard.writeText).toHaveBeenCalledWith('ABCD-1234');
      });
    });

    it('should show "Copied!" feedback after copying', async () => {
      const mockClipboard = {
        writeText: jest.fn().mockResolvedValue(undefined),
      };
      Object.assign(navigator, { clipboard: mockClipboard });

      render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
        />
      );

      const copyButton = screen.getByRole('button', { name: /Copy Code/i });
      fireEvent.click(copyButton);

      await waitFor(() => {
        expect(screen.getByText(/Copied!/i)).toBeInTheDocument();
      });
    });
  });

  describe('Auto-Close on Success', () => {
    it('should auto-close when authentication succeeds', async () => {
      const { rerender } = render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
          authStatus="pending"
        />
      );

      // Simulate authentication success
      rerender(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
          authStatus="success"
        />
      );

      await waitFor(() => {
        expect(mockOnClose).toHaveBeenCalledWith('success');
      });
    });

    it('should show success message before closing', async () => {
      const { rerender } = render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
          authStatus="pending"
        />
      );

      rerender(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
          authStatus="success"
        />
      );

      expect(screen.getByText(/Authentication successful!/i)).toBeInTheDocument();
      expect(screen.getByTestId('success-icon')).toBeInTheDocument();
    });

    it('should delay auto-close to show success message', async () => {
      jest.useFakeTimers();

      const { rerender } = render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
          authStatus="pending"
        />
      );

      rerender(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
          authStatus="success"
        />
      );

      // Should NOT close immediately
      expect(mockOnClose).not.toHaveBeenCalled();

      // Advance time to allow success message display (2 seconds)
      jest.advanceTimersByTime(2000);

      await waitFor(() => {
        expect(mockOnClose).toHaveBeenCalledWith('success');
      });

      jest.useRealTimers();
    });
  });

  describe('User Interactions', () => {
    it('should close modal when Cancel button clicked', () => {
      render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
        />
      );

      const cancelButton = screen.getByRole('button', { name: /Cancel/i });
      fireEvent.click(cancelButton);

      expect(mockOnClose).toHaveBeenCalledWith('cancel');
    });

    it('should close modal when clicking outside (backdrop)', () => {
      render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
        />
      );

      const backdrop = screen.getByRole('dialog').parentElement;
      if (backdrop) {
        fireEvent.click(backdrop);
        expect(mockOnClose).toHaveBeenCalledWith('cancel');
      }
    });

    it('should close modal on Escape key', () => {
      render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
        />
      );

      fireEvent.keyDown(document, { key: 'Escape' });

      expect(mockOnClose).toHaveBeenCalledWith('cancel');
    });
  });

  describe('Different Tenant Types', () => {
    it('should show "Source Tenant" in title for source', () => {
      render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
        />
      );

      expect(screen.getByText(/Sign in to Source Tenant/i)).toBeInTheDocument();
    });

    it('should show "Target / Gameboard Tenant" in title for target', () => {
      render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="target"
          deviceCodeInfo={defaultDeviceCode}
        />
      );

      expect(screen.getByText(/Sign in to Target.*Gameboard.*Tenant/i)).toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('should display error message when authentication fails', () => {
      render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
          authStatus="error"
          error="Authentication failed: Network error"
        />
      );

      expect(screen.getByText(/Authentication failed/i)).toBeInTheDocument();
      expect(screen.getByTestId('error-icon')).toBeInTheDocument();
    });

    it('should allow retry after error', () => {
      render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
          authStatus="error"
          error="Network error"
        />
      );

      const retryButton = screen.getByRole('button', { name: /Try Again/i });
      fireEvent.click(retryButton);

      expect(mockOnClose).toHaveBeenCalledWith('retry');
    });
  });

  describe('Accessibility', () => {
    it('should have accessible modal title', () => {
      render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
        />
      );

      expect(screen.getByRole('dialog', { name: /Sign in to Source Tenant/i })).toBeInTheDocument();
    });

    it('should have accessible button labels', () => {
      render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
        />
      );

      expect(screen.getByRole('button', { name: /Copy Code/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Cancel/i })).toBeInTheDocument();
    });

    it('should trap focus within modal', () => {
      render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
        />
      );

      const buttons = screen.getAllByRole('button');
      const link = screen.getByRole('link');

      // Tab through interactive elements
      buttons[0].focus();
      expect(document.activeElement).toBe(buttons[0]);

      // Focus should cycle back to first element after last
      buttons[buttons.length - 1].focus();
      fireEvent.keyDown(document.activeElement!, { key: 'Tab' });

      // Should stay within modal (implementation-dependent)
      const focusedElement = document.activeElement;
      const modalElement = screen.getByRole('dialog');
      expect(modalElement.contains(focusedElement)).toBe(true);
    });

    it('should announce status changes to screen readers', () => {
      const { rerender } = render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
          authStatus="pending"
        />
      );

      rerender(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
          authStatus="success"
        />
      );

      // Should have aria-live region for status updates
      const statusRegion = screen.getByRole('status');
      expect(statusRegion).toHaveTextContent(/Authentication successful/i);
    });
  });

  describe('Edge Cases', () => {
    it('should handle missing device code info', () => {
      render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={null}
        />
      );

      expect(screen.getByText(/Loading/i)).toBeInTheDocument();
    });

    it('should cleanup timers on unmount', () => {
      const clearIntervalSpy = jest.spyOn(global, 'clearInterval');

      const { unmount } = render(
        <AuthLoginModal
          open={true}
          onClose={mockOnClose}
          tenantType="source"
          deviceCodeInfo={defaultDeviceCode}
        />
      );

      unmount();

      expect(clearIntervalSpy).toHaveBeenCalled();
    });
  });
});
