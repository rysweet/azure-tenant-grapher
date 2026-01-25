import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import UndeployTab from '../../renderer/src/components/tabs/UndeployTab';

// Mock the Electron API
const mockElectronAPI = {
  cli: {
    execute: jest.fn(),
  },
  on: jest.fn(),
  off: jest.fn(),
};

(global as any).window = {
  electronAPI: mockElectronAPI,
};

describe('UndeployTab Loading State', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('should stop loading spinner when deployments are fetched successfully', async () => {
    const mockDeployments = [
      {
        id: 'test-deployment-1',
        status: 'active',
        tenant: 'tenant-1',
        directory: '/test/path',
        deployed_at: '2024-01-01T00:00:00Z',
        resources: { 'vm': 2, 'storage': 1 },
      },
    ];

    // Mock successful CLI execution
    mockElectronAPI.cli.execute.mockResolvedValue({
      data: { id: 'process-1' },
    });

    // Mock event handlers to simulate successful output
    mockElectronAPI.on.mockImplementation((event: string, handler: Function) => {
      if (event === 'process:output') {
        setTimeout(() => {
          handler({
            id: 'process-1',
            data: [JSON.stringify(mockDeployments)],
          });
        }, 100);
      } else if (event === 'process:exit') {
        setTimeout(() => {
          handler({ id: 'process-1', code: 0 });
        }, 150);
      }
    });

    render(<UndeployTab />);

    // Initially should show loading spinner
    expect(screen.getByRole('progressbar')).toBeInTheDocument();

    // Advance timers to trigger handlers
    jest.advanceTimersByTime(200);

    // Wait for loading to complete
    await waitFor(() => {
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    }, { timeout: 3000 });

    // Should show deployment data
    expect(screen.getByText('test-deployment-1')).toBeInTheDocument();
  });

  it('should stop loading spinner and show error when JSON parsing fails', async () => {
    mockElectronAPI.cli.execute.mockResolvedValue({
      data: { id: 'process-2' },
    });

    // Mock event handlers to simulate invalid JSON
    mockElectronAPI.on.mockImplementation((event: string, handler: Function) => {
      if (event === 'process:output') {
        setTimeout(() => {
          handler({
            id: 'process-2',
            data: ['invalid json {'],
          });
        }, 100);
      }
    });

    render(<UndeployTab />);

    // Initially should show loading spinner
    expect(screen.getByRole('progressbar')).toBeInTheDocument();

    // Advance timers to trigger handlers
    jest.advanceTimersByTime(200);

    // Wait for loading to complete
    await waitFor(() => {
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    }, { timeout: 3000 });

    // Should show error message
    expect(screen.getByText(/Error parsing deployment data/i)).toBeInTheDocument();
  });

  it('should stop loading spinner and show error on timeout', async () => {
    mockElectronAPI.cli.execute.mockResolvedValue({
      data: { id: 'process-3' },
    });

    // Mock event handlers that never call the callbacks
    mockElectronAPI.on.mockImplementation(() => {
      // Do nothing - simulates a process that hangs
    });

    render(<UndeployTab />);

    // Initially should show loading spinner
    expect(screen.getByRole('progressbar')).toBeInTheDocument();

    // Advance timers past timeout threshold (30 seconds)
    jest.advanceTimersByTime(31000);

    // Wait for loading to complete
    await waitFor(() => {
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    }, { timeout: 3000 });

    // Should show timeout error
    expect(screen.getByText(/Request timed out after 30 seconds/i)).toBeInTheDocument();
  });

  it('should stop loading spinner and show message when no deployments exist', async () => {
    mockElectronAPI.cli.execute.mockResolvedValue({
      data: { id: 'process-4' },
    });

    // Mock event handlers to simulate empty array
    mockElectronAPI.on.mockImplementation((event: string, handler: Function) => {
      if (event === 'process:output') {
        setTimeout(() => {
          handler({
            id: 'process-4',
            data: ['[]'],
          });
        }, 100);
      } else if (event === 'process:exit') {
        setTimeout(() => {
          handler({ id: 'process-4', code: 0 });
        }, 150);
      }
    });

    render(<UndeployTab />);

    // Initially should show loading spinner
    expect(screen.getByRole('progressbar')).toBeInTheDocument();

    // Advance timers to trigger handlers
    jest.advanceTimersByTime(200);

    // Wait for loading to complete
    await waitFor(() => {
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    }, { timeout: 3000 });

    // Should show "no deployments" message
    expect(screen.getByText(/No deployments found/i)).toBeInTheDocument();
  });

  it('should stop loading spinner and show error on CLI execution failure', async () => {
    // Mock CLI execution failure
    mockElectronAPI.cli.execute.mockRejectedValue(new Error('CLI execution failed'));

    render(<UndeployTab />);

    // Initially should show loading spinner
    expect(screen.getByRole('progressbar')).toBeInTheDocument();

    // Wait for loading to complete
    await waitFor(() => {
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    }, { timeout: 3000 });

    // Should show error message
    expect(screen.getByText(/CLI execution failed/i)).toBeInTheDocument();
  });

  it('should stop loading spinner on non-zero exit code', async () => {
    mockElectronAPI.cli.execute.mockResolvedValue({
      data: { id: 'process-5' },
    });

    // Mock event handlers to simulate exit with error code
    mockElectronAPI.on.mockImplementation((event: string, handler: Function) => {
      if (event === 'process:exit') {
        setTimeout(() => {
          handler({ id: 'process-5', code: 1 });
        }, 100);
      }
    });

    render(<UndeployTab />);

    // Initially should show loading spinner
    expect(screen.getByRole('progressbar')).toBeInTheDocument();

    // Advance timers to trigger handlers
    jest.advanceTimersByTime(200);

    // Wait for loading to complete
    await waitFor(() => {
      expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    }, { timeout: 3000 });

    // Should show error message
    expect(screen.getByText(/Failed to fetch deployments \(exit code 1\)/i)).toBeInTheDocument();
  });

  it('should properly clean up event listeners on exit', async () => {
    mockElectronAPI.cli.execute.mockResolvedValue({
      data: { id: 'process-6' },
    });

    let outputHandler: Function | null = null;
    let exitHandler: Function | null = null;

    // Capture the handlers
    mockElectronAPI.on.mockImplementation((event: string, handler: Function) => {
      if (event === 'process:output') {
        outputHandler = handler;
      } else if (event === 'process:exit') {
        exitHandler = handler;
        setTimeout(() => {
          handler({ id: 'process-6', code: 0 });
        }, 100);
      }
    });

    render(<UndeployTab />);

    // Advance timers to trigger exit handler
    jest.advanceTimersByTime(200);

    // Wait for exit handler to be called
    await waitFor(() => {
      expect(mockElectronAPI.off).toHaveBeenCalledWith('process:output', outputHandler);
      expect(mockElectronAPI.off).toHaveBeenCalledWith('process:exit', exitHandler);
    }, { timeout: 3000 });
  });
});
