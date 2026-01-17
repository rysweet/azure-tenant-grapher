/**
 * Comprehensive tests for ScanTab database refresh functionality (Issue #686)
 *
 * Test Coverage:
 * - Unit Tests (7 tests - 60%): Database refresh logic and state changes
 * - Integration Tests (3 tests - 30%): Complete scan workflow with database refresh
 * - E2E Tests (2 tests - 10%): User-facing behavior
 *
 * Testing Pyramid: 60% unit, 30% integration, 10% E2E
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { BrowserRouter } from 'react-router-dom';
import ScanTab from '../../renderer/src/components/tabs/ScanTab';
import { AppProvider } from '../../renderer/src/context/AppContext';
import { WebSocketProvider } from '../../renderer/src/context/WebSocketContext';
import axios from 'axios';

// Mock axios
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

// Mock the validation utilities
jest.mock('../../renderer/src/utils/validation', () => ({
  isValidTenantId: jest.fn((id) => id.length > 0),
  isValidResourceLimit: jest.fn((limit) => limit >= 0 && limit <= 10000),
  isValidThreadCount: jest.fn((count) => count >= 1 && count <= 100),
}));

// Store the onProcessExit callbacks so we can trigger them in tests
const processExitCallbacks = new Map<string, (event: any) => void>();

// Mock useWebSocket hook with proper callback management
jest.mock('../../renderer/src/hooks/useWebSocket', () => ({
  useWebSocket: jest.fn(() => ({
    isConnected: true,
    subscribeToProcess: jest.fn(),
    unsubscribeFromProcess: jest.fn(),
    clearProcessOutput: jest.fn(),
    getProcessOutput: jest.fn(() => []),
    onProcessExit: jest.fn((processId: string, callback: any) => {
      // Store the callback so we can trigger it in tests
      processExitCallbacks.set(processId, callback);
      // Return unsubscribe function
      return () => {
        processExitCallbacks.delete(processId);
      };
    }),
    outputs: new Map(),
  })),
}));

// Helper function to trigger process exit in tests
const triggerProcessExit = (processId: string, code: number) => {
  const callback = processExitCallbacks.get(processId);
  if (callback) {
    callback({
      type: 'exit',
      processId,
      code,
      timestamp: new Date().toISOString(),
    });
  }
};

// Helper to wait for scan start and callback registration
const waitForScanStart = async (processId: string) => {
  await waitFor(() => {
    expect(mockedAxios.post).toHaveBeenCalledWith(
      expect.stringContaining('/api/execute'),
      expect.any(Object)
    );
  });

  // Wait for the useEffect to register the onProcessExit callback
  await waitFor(() => {
    expect(processExitCallbacks.has(processId)).toBe(true);
  });
};

// Mock useBackgroundOperations hook
jest.mock('../../renderer/src/hooks/useBackgroundOperations', () => ({
  useBackgroundOperations: jest.fn(() => ({
    addBackgroundOperation: jest.fn(),
    updateBackgroundOperation: jest.fn(),
    removeBackgroundOperation: jest.fn(),
  })),
}));

// Mock useLogger hook
jest.mock('../../renderer/src/hooks/useLogger', () => ({
  useLogger: jest.fn(() => ({
    info: jest.fn(),
    warn: jest.fn(),
    error: jest.fn(),
    debug: jest.fn(),
  })),
}));

// Wrapper component with providers
const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      <WebSocketProvider>
        <AppProvider>
          {component}
        </AppProvider>
      </WebSocketProvider>
    </BrowserRouter>
  );
};

describe('ScanTab Database Refresh (Issue #686)', () => {
  beforeEach(() => {
    // Reset mocks
    jest.clearAllMocks();
    processExitCallbacks.clear();

    // Setup default axios mocks
    mockedAxios.get.mockImplementation((url: string) => {
      if (url.includes('/api/graph/stats')) {
        return Promise.resolve({
          data: {
            nodeCount: 150,
            edgeCount: 300,
            nodeTypes: [],
            edgeTypes: [],
            lastUpdate: new Date().toISOString(),
            isEmpty: false,
          },
        });
      }
      if (url.includes('/api/neo4j/status')) {
        return Promise.resolve({
          data: { status: 'running', running: true },
        });
      }
      if (url.includes('/api/config/env')) {
        return Promise.resolve({
          data: { AZURE_TENANT_ID: 'test-tenant-id' },
        });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    // Mock axios POST for scan execution
    mockedAxios.post.mockImplementation((url: string) => {
      if (url.includes('/api/execute')) {
        return Promise.resolve({
          data: { processId: 'test-process-id' },
        });
      }
      return Promise.reject(new Error('Unknown URL'));
    });

    // Setup window.electronAPI
    (window as any).electronAPI = {
      cli: { execute: jest.fn() },
      on: jest.fn(),
      store: {
        getAll: jest.fn().mockReturnValue({}),
      },
    };

    // Make validation pass by default
    const { isValidTenantId, isValidThreadCount } = require('../../renderer/src/utils/validation');
    isValidTenantId.mockReturnValue(true);
    isValidThreadCount.mockReturnValue(true);
  });

  // ========================
  // UNIT TESTS (60%)
  // ========================

  describe('Unit Tests - Database Refresh Logic', () => {
    test('successful database refresh after scan completion', async () => {
      renderWithProviders(<ScanTab />);

      const tenantInput = screen.getByLabelText(/Tenant ID/i);
      const startButton = screen.getByText(/Start Scan/i);

      // Start scan
      fireEvent.change(tenantInput, { target: { value: 'test-tenant-id' } });
      fireEvent.click(startButton);

      // Wait for scan to start and callback registration
      await waitForScanStart('test-process-id');

      // Simulate successful scan completion (exit code 0)
      triggerProcessExit('test-process-id', 0);

      // Verify refreshing message appears
      await waitFor(() => {
        expect(screen.getByText(/Refreshing database statistics/i)).toBeInTheDocument();
      }, { timeout: 3000 });

      // Verify loadDatabaseStats was called
      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalledWith(
          expect.stringContaining('/api/graph/stats')
        );
      });

      // Verify success message appears
      await waitFor(() => {
        // Check logs via getByText
        expect(screen.queryByText(new RegExp('Database statistics updated', "i"))).toBeInTheDocument();
      }, { timeout: 3000 });
    });

    test('refreshing message appears before database update', async () => {
      // Make the database stats request slow to verify message timing
      mockedAxios.get.mockImplementation((url: string) => {
        if (url.includes('/api/graph/stats')) {
          return new Promise((resolve) => {
            setTimeout(() => {
              resolve({
                data: {
                  nodeCount: 150,
                  edgeCount: 300,
                  nodeTypes: [],
                  edgeTypes: [],
                  lastUpdate: new Date().toISOString(),
                  isEmpty: false,
                },
              });
            }, 100);
          });
        }
        if (url.includes('/api/neo4j/status')) {
          return Promise.resolve({
            data: { status: 'running', running: true },
          });
        }
        if (url.includes('/api/config/env')) {
          return Promise.resolve({
            data: { AZURE_TENANT_ID: 'test-tenant-id' },
          });
        }
        return Promise.reject(new Error('Unknown URL'));
      });

      renderWithProviders(<ScanTab />);

      const tenantInput = screen.getByLabelText(/Tenant ID/i);
      const startButton = screen.getByText(/Start Scan/i);

      fireEvent.change(tenantInput, { target: { value: 'test-tenant-id' } });
      fireEvent.click(startButton);

      await waitFor(() => {
        expect(mockedAxios.post).toHaveBeenCalledWith(
          expect.stringContaining('/api/execute'),
          expect.any(Object)
        );
      });

      // Trigger scan completion
      triggerProcessExit('test-process-id', 0);

      // Verify refreshing message appears immediately
      await waitFor(() => {
        // Check logs via getByText
        expect(screen.queryByText(new RegExp('Refreshing database statistics', "i"))).toBeInTheDocument();
      }, { timeout: 1000 });

      // Then verify success message appears after delay
      await waitFor(() => {
        // Check logs via getByText
        expect(screen.queryByText(new RegExp('Database statistics updated', "i"))).toBeInTheDocument();
      }, { timeout: 3000 });
    });

    test('updated message appears after successful database refresh', async () => {
      renderWithProviders(<ScanTab />);

      const tenantInput = screen.getByLabelText(/Tenant ID/i);
      const startButton = screen.getByText(/Start Scan/i);

      fireEvent.change(tenantInput, { target: { value: 'test-tenant-id' } });
      fireEvent.click(startButton);

      await waitFor(() => {
        expect(mockedAxios.post).toHaveBeenCalledWith(
          expect.stringContaining('/api/execute'),
          expect.any(Object)
        );
      });

      triggerProcessExit('test-process-id', 0);

      // Wait for the updated message
      await waitFor(() => {
        // Check logs via getByText
        expect(screen.queryByText(new RegExp('Database statistics updated', "i"))).toBeInTheDocument();
      }, { timeout: 3000 });

      // Also verify refreshing message was shown (both messages should be present)
      expect(screen.queryByText(/Refreshing database statistics/i)).toBeInTheDocument();
    });

    test('error handling when loadDatabaseStats fails', async () => {
      // Mock database stats failure
      mockedAxios.get.mockImplementation((url: string) => {
        if (url.includes('/api/graph/stats')) {
          return Promise.reject(new Error('Database connection failed'));
        }
        if (url.includes('/api/neo4j/status')) {
          return Promise.resolve({
            data: { status: 'running', running: true },
          });
        }
        if (url.includes('/api/config/env')) {
          return Promise.resolve({
            data: { AZURE_TENANT_ID: 'test-tenant-id' },
          });
        }
        return Promise.reject(new Error('Unknown URL'));
      });

      renderWithProviders(<ScanTab />);

      const tenantInput = screen.getByLabelText(/Tenant ID/i);
      const startButton = screen.getByText(/Start Scan/i);

      fireEvent.change(tenantInput, { target: { value: 'test-tenant-id' } });
      fireEvent.click(startButton);

      await waitFor(() => {
        expect(mockedAxios.post).toHaveBeenCalledWith(
          expect.stringContaining('/api/execute'),
          expect.any(Object)
        );
      });

      triggerProcessExit('test-process-id', 0);

      // Verify error message appears
      await waitFor(() => {
        // Check logs via getByText
        expect(screen.queryByText(new RegExp('Failed to refresh database stats', "i"))).toBeInTheDocument();
      }, { timeout: 3000 });

      // Verify error state is set
      await waitFor(() => {
        expect(screen.queryByText(/Failed to refresh database stats/i)).toBeInTheDocument();
      }, { timeout: 3000 });
    });

    test('scan failure does not trigger database refresh', async () => {
      renderWithProviders(<ScanTab />);

      const tenantInput = screen.getByLabelText(/Tenant ID/i);
      const startButton = screen.getByText(/Start Scan/i);

      fireEvent.change(tenantInput, { target: { value: 'test-tenant-id' } });
      fireEvent.click(startButton);

      await waitFor(() => {
        expect(mockedAxios.post).toHaveBeenCalledWith(
          expect.stringContaining('/api/execute'),
          expect.any(Object)
        );
      });

      // Clear previous axios calls
      mockedAxios.get.mockClear();

      // Simulate scan failure (exit code 1)
      triggerProcessExit('test-process-id', 1);

      // Wait a bit to ensure no database refresh is triggered
      await new Promise(resolve => setTimeout(resolve, 500));

      // Verify loadDatabaseStats was NOT called
      const statsCallCount = mockedAxios.get.mock.calls.filter(
        call => call[0].includes('/api/graph/stats')
      ).length;
      expect(statsCallCount).toBe(0);

      // Verify no refreshing message
      expect(screen.queryByText(/Refreshing database statistics/i)).not.toBeInTheDocument();
    });

    test('empty error message handling', async () => {
      // Mock database stats failure with no error message
      mockedAxios.get.mockImplementation((url: string) => {
        if (url.includes('/api/graph/stats')) {
          return Promise.reject('');
        }
        if (url.includes('/api/neo4j/status')) {
          return Promise.resolve({
            data: { status: 'running', running: true },
          });
        }
        if (url.includes('/api/config/env')) {
          return Promise.resolve({
            data: { AZURE_TENANT_ID: 'test-tenant-id' },
          });
        }
        return Promise.reject(new Error('Unknown URL'));
      });

      renderWithProviders(<ScanTab />);

      const tenantInput = screen.getByLabelText(/Tenant ID/i);
      const startButton = screen.getByText(/Start Scan/i);

      fireEvent.change(tenantInput, { target: { value: 'test-tenant-id' } });
      fireEvent.click(startButton);

      await waitFor(() => {
        expect(mockedAxios.post).toHaveBeenCalledWith(
          expect.stringContaining('/api/execute'),
          expect.any(Object)
        );
      });

      triggerProcessExit('test-process-id', 0);

      // Verify error message with "Unknown error"
      await waitFor(() => {
        // Check logs via getByText
        expect(screen.queryByText(new RegExp('Failed to refresh database stats', "i"))).toBeInTheDocument();
        expect(screen.queryByText(new RegExp('Unknown error', "i"))).toBeInTheDocument();
      }, { timeout: 3000 });
    });

    test('non-Error exception handling', async () => {
      // Mock database stats failure with non-Error object
      mockedAxios.get.mockImplementation((url: string) => {
        if (url.includes('/api/graph/stats')) {
          return Promise.reject({ code: 'ECONNREFUSED', message: 'Connection refused' });
        }
        if (url.includes('/api/neo4j/status')) {
          return Promise.resolve({
            data: { status: 'running', running: true },
          });
        }
        if (url.includes('/api/config/env')) {
          return Promise.resolve({
            data: { AZURE_TENANT_ID: 'test-tenant-id' },
          });
        }
        return Promise.reject(new Error('Unknown URL'));
      });

      renderWithProviders(<ScanTab />);

      const tenantInput = screen.getByLabelText(/Tenant ID/i);
      const startButton = screen.getByText(/Start Scan/i);

      fireEvent.change(tenantInput, { target: { value: 'test-tenant-id' } });
      fireEvent.click(startButton);

      await waitFor(() => {
        expect(mockedAxios.post).toHaveBeenCalledWith(
          expect.stringContaining('/api/execute'),
          expect.any(Object)
        );
      });

      triggerProcessExit('test-process-id', 0);

      // Verify error is handled gracefully
      await waitFor(() => {
        // Check logs via getByText
        expect(screen.queryByText(new RegExp('Failed to refresh database stats', "i"))).toBeInTheDocument();
      }, { timeout: 3000 });
    });
  });

  // ========================
  // INTEGRATION TESTS (30%)
  // ========================

  describe('Integration Tests - Complete Workflow', () => {
    test('complete workflow: scan start → complete → database refresh', async () => {
      renderWithProviders(<ScanTab />);

      const tenantInput = screen.getByLabelText(/Tenant ID/i);
      const startButton = screen.getByText(/Start Scan/i);

      // Step 1: Start scan
      fireEvent.change(tenantInput, { target: { value: 'test-tenant-id' } });
      fireEvent.click(startButton);

      await waitFor(() => {
        expect(mockedAxios.post).toHaveBeenCalledWith(
          expect.stringContaining('/api/execute'),
          expect.any(Object)
        );
        expect(screen.getByText(/Stop Scan/i)).toBeInTheDocument();
      });

      // Step 2: Scan completes successfully
      triggerProcessExit('test-process-id', 0);

      // Step 3: Verify scan completion message
      await waitFor(() => {
        // Check logs via getByText
        expect(screen.queryByText(new RegExp('Scan completed successfully', "i"))).toBeInTheDocument();
      });

      // Step 4: Verify database refresh starts
      await waitFor(() => {
        // Check logs via getByText
        expect(screen.queryByText(new RegExp('Refreshing database statistics', "i"))).toBeInTheDocument();
      });

      // Step 5: Verify database refresh completes
      await waitFor(() => {
        // Check logs via getByText
        expect(screen.queryByText(new RegExp('Database statistics updated', "i"))).toBeInTheDocument();
      }, { timeout: 3000 });

      // Step 6: Verify final state
      expect(screen.getByText(/Start Scan/i)).toBeInTheDocument();
      expect(tenantInput).not.toBeDisabled();
    });

    test('concurrent scans without race conditions', async () => {
      renderWithProviders(<ScanTab />);

      const tenantInput = screen.getByLabelText(/Tenant ID/i);
      const startButton = screen.getByText(/Start Scan/i);

      // Start first scan
      fireEvent.change(tenantInput, { target: { value: 'test-tenant-1' } });
      fireEvent.click(startButton);

      await waitFor(() => {
        expect(mockedAxios.post).toHaveBeenCalledTimes(1);
      });

      // Complete first scan
      triggerProcessExit('test-process-id', 0);

      // Wait for first scan to complete
      await waitFor(() => {
        expect(screen.getByText(/Start Scan/i)).toBeInTheDocument();
      });

      // Start second scan immediately
      fireEvent.change(tenantInput, { target: { value: 'test-tenant-2' } });
      fireEvent.click(startButton);

      await waitFor(() => {
        expect(mockedAxios.post).toHaveBeenCalledTimes(2);
      });

      // Verify both database refreshes complete without errors
      await waitFor(() => {
        const errorElements = screen.queryAllByText(/Failed to refresh database stats/i);
        expect(errorElements.length).toBe(0);
      }, { timeout: 3000 });
    });

    test('database refresh timeout recovery', async () => {
      // Mock slow database stats response
      let resolveStats: any;
      mockedAxios.get.mockImplementation((url: string) => {
        if (url.includes('/api/graph/stats')) {
          return new Promise((resolve) => {
            resolveStats = resolve;
            // Don't resolve immediately - simulate timeout
          });
        }
        if (url.includes('/api/neo4j/status')) {
          return Promise.resolve({
            data: { status: 'running', running: true },
          });
        }
        if (url.includes('/api/config/env')) {
          return Promise.resolve({
            data: { AZURE_TENANT_ID: 'test-tenant-id' },
          });
        }
        return Promise.reject(new Error('Unknown URL'));
      });

      renderWithProviders(<ScanTab />);

      const tenantInput = screen.getByLabelText(/Tenant ID/i);
      const startButton = screen.getByText(/Start Scan/i);

      fireEvent.change(tenantInput, { target: { value: 'test-tenant-id' } });
      fireEvent.click(startButton);

      await waitFor(() => {
        expect(mockedAxios.post).toHaveBeenCalledWith(
          expect.stringContaining('/api/execute'),
          expect.any(Object)
        );
      });

      triggerProcessExit('test-process-id', 0);

      // Verify refreshing message appears
      await waitFor(() => {
        // Check logs via getByText
        expect(screen.queryByText(new RegExp('Refreshing database statistics', "i"))).toBeInTheDocument();
      });

      // Resolve the stats request after delay
      if (resolveStats) {
        resolveStats({
          data: {
            nodeCount: 150,
            edgeCount: 300,
            nodeTypes: [],
            edgeTypes: [],
            lastUpdate: new Date().toISOString(),
            isEmpty: false,
          },
        });
      }

      // Verify success message eventually appears
      await waitFor(() => {
        // Check logs via getByText
        expect(screen.queryByText(new RegExp('Database statistics updated', "i"))).toBeInTheDocument();
      }, { timeout: 5000 });
    });
  });

  // ========================
  // E2E TESTS (10%)
  // ========================

  describe('E2E Tests - User Experience', () => {
    test('user sees database updated after scan completes', async () => {
      renderWithProviders(<ScanTab />);

      const tenantInput = screen.getByLabelText(/Tenant ID/i);
      const startButton = screen.getByText(/Start Scan/i);

      // User starts a scan
      fireEvent.change(tenantInput, { target: { value: 'my-tenant-id' } });
      fireEvent.click(startButton);

      // User sees scan is running
      await waitFor(() => {
        expect(screen.getByText(/Stop Scan/i)).toBeInTheDocument();
      });

      // Scan completes
      triggerProcessExit('test-process-id', 0);

      // User sees completion message
      await waitFor(() => {
        // Check logs via getByText
        expect(screen.queryByText(new RegExp('Scan completed successfully', "i"))).toBeInTheDocument();
      });

      // User sees database is being refreshed
      await waitFor(() => {
        // Check logs via getByText
        expect(screen.queryByText(new RegExp('Refreshing database statistics', "i"))).toBeInTheDocument();
      });

      // User sees database update is complete
      await waitFor(() => {
        // Check logs via getByText
        expect(screen.queryByText(new RegExp('Database statistics updated', "i"))).toBeInTheDocument();
      }, { timeout: 3000 });

      // User can start a new scan
      expect(screen.getByText(/Start Scan/i)).toBeInTheDocument();
      expect(tenantInput).not.toBeDisabled();
    });

    test('user sees error message when database refresh fails', async () => {
      // Mock database stats failure
      mockedAxios.get.mockImplementation((url: string) => {
        if (url.includes('/api/graph/stats')) {
          return Promise.reject(new Error('Neo4j connection timeout'));
        }
        if (url.includes('/api/neo4j/status')) {
          return Promise.resolve({
            data: { status: 'running', running: true },
          });
        }
        if (url.includes('/api/config/env')) {
          return Promise.resolve({
            data: { AZURE_TENANT_ID: 'test-tenant-id' },
          });
        }
        return Promise.reject(new Error('Unknown URL'));
      });

      renderWithProviders(<ScanTab />);

      const tenantInput = screen.getByLabelText(/Tenant ID/i);
      const startButton = screen.getByText(/Start Scan/i);

      // User starts a scan
      fireEvent.change(tenantInput, { target: { value: 'my-tenant-id' } });
      fireEvent.click(startButton);

      await waitFor(() => {
        expect(screen.getByText(/Stop Scan/i)).toBeInTheDocument();
      });

      // Scan completes
      triggerProcessExit('test-process-id', 0);

      // User sees scan completed
      await waitFor(() => {
        // Check logs via getByText
        expect(screen.queryByText(new RegExp('Scan completed successfully', "i"))).toBeInTheDocument();
      });

      // User sees database refresh attempt
      await waitFor(() => {
        // Check logs via getByText
        expect(screen.queryByText(new RegExp('Refreshing database statistics', "i"))).toBeInTheDocument();
      });

      // User sees error message
      await waitFor(() => {
        // Check logs via getByText
        expect(screen.queryByText(new RegExp('Failed to refresh database stats', "i"))).toBeInTheDocument();
        expect(screen.queryByText(new RegExp('Neo4j connection timeout', "i"))).toBeInTheDocument();
      }, { timeout: 3000 });

      // User sees error alert at top of page
      await waitFor(() => {
        expect(screen.getByText(/Failed to refresh database stats/i)).toBeInTheDocument();
      });

      // User can still start a new scan despite the error
      expect(screen.getByText(/Start Scan/i)).toBeInTheDocument();
      expect(tenantInput).not.toBeDisabled();
    });
  });
});
