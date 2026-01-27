import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import ConfigTab from '../../renderer/src/components/tabs/ConfigTab';
import { MemoryRouter } from 'react-router-dom';

// Mock window.electronAPI
const mockExecute = jest.fn();
const mockOn = jest.fn();
const mockOff = jest.fn();
const mockConfigSet = jest.fn();
const mockEnvGetAll = jest.fn();

(global as any).window.electronAPI = {
  cli: { execute: mockExecute },
  on: mockOn,
  off: mockOff,
  config: { set: mockConfigSet },
  env: { getAll: mockEnvGetAll },
};

describe('ConfigTab - App Registration Check', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockEnvGetAll.mockResolvedValue({});
  });

  afterEach(() => {
    jest.clearAllTimers();
  });

  test('displays checking state initially when client ID exists', async () => {
    mockEnvGetAll.mockResolvedValue({
      AZURE_CLIENT_ID: 'test-client-id-123',
    });

    mockExecute.mockResolvedValue({
      data: { id: 'process-1' },
    });

    render(
      <MemoryRouter>
        <ConfigTab />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/checking app registration/i)).toBeInTheDocument();
    });
  });

  test('times out after 15 seconds if no response', async () => {
    jest.useFakeTimers();

    mockEnvGetAll.mockResolvedValue({
      AZURE_CLIENT_ID: 'test-client-id-123',
    });

    mockExecute.mockResolvedValue({
      data: { id: 'process-1' },
    });

    render(
      <MemoryRouter>
        <ConfigTab />
      </MemoryRouter>
    );

    // Wait for checking state
    await waitFor(() => {
      expect(screen.getByText(/checking app registration/i)).toBeInTheDocument();
    });

    // Fast-forward 15 seconds
    jest.advanceTimersByTime(15000);

    // Should no longer be in checking state
    await waitFor(() => {
      expect(screen.queryByText(/checking app registration/i)).not.toBeInTheDocument();
    });

    jest.useRealTimers();
  });

  test('displays success when app registration exists', async () => {
    mockEnvGetAll.mockResolvedValue({
      AZURE_CLIENT_ID: 'test-client-id-123',
    });

    mockExecute.mockResolvedValue({
      data: { id: 'process-1' },
    });

    render(
      <MemoryRouter>
        <ConfigTab />
      </MemoryRouter>
    );

    // Simulate successful response
    const exitHandler = mockOn.mock.calls.find(call => call[0] === 'process:exit')?.[1];
    if (exitHandler) {
      exitHandler({
        id: 'process-1',
        code: 0,
        output: ['My Test App'],
      });
    }

    await waitFor(() => {
      expect(screen.getByText(/app registration found: my test app/i)).toBeInTheDocument();
    });
  });

  test('cleans up event listener after receiving response', async () => {
    mockEnvGetAll.mockResolvedValue({
      AZURE_CLIENT_ID: 'test-client-id-123',
    });

    mockExecute.mockResolvedValue({
      data: { id: 'process-1' },
    });

    render(
      <MemoryRouter>
        <ConfigTab />
      </MemoryRouter>
    );

    // Simulate successful response
    const exitHandler = mockOn.mock.calls.find(call => call[0] === 'process:exit')?.[1];
    if (exitHandler) {
      exitHandler({
        id: 'process-1',
        code: 0,
        output: ['My Test App'],
      });
    }

    await waitFor(() => {
      expect(mockOff).toHaveBeenCalledWith('process:exit', expect.any(Function));
    });
  });

  test('handles empty client ID gracefully', async () => {
    mockEnvGetAll.mockResolvedValue({
      AZURE_CLIENT_ID: '',
    });

    render(
      <MemoryRouter>
        <ConfigTab />
      </MemoryRouter>
    );

    await waitFor(() => {
      // Should not be checking when client ID is empty
      expect(screen.queryByText(/checking app registration/i)).not.toBeInTheDocument();
    });

    // Should not call execute for empty client ID
    expect(mockExecute).not.toHaveBeenCalled();
  });

  test('handles missing client ID gracefully', async () => {
    mockEnvGetAll.mockResolvedValue({});

    render(
      <MemoryRouter>
        <ConfigTab />
      </MemoryRouter>
    );

    await waitFor(() => {
      // Should show error alert for missing credentials
      expect(screen.getByText(/azure ad credentials not configured/i)).toBeInTheDocument();
    });
  });

  test('handles API errors gracefully', async () => {
    mockEnvGetAll.mockResolvedValue({
      AZURE_CLIENT_ID: 'test-client-id-123',
    });

    mockExecute.mockRejectedValue(new Error('API Error'));

    render(
      <MemoryRouter>
        <ConfigTab />
      </MemoryRouter>
    );

    await waitFor(() => {
      // Should not be stuck in checking state after error
      expect(screen.queryByText(/checking app registration/i)).not.toBeInTheDocument();
    });
  });

  test('clears timeout when process exits', async () => {
    jest.useFakeTimers();

    mockEnvGetAll.mockResolvedValue({
      AZURE_CLIENT_ID: 'test-client-id-123',
    });

    mockExecute.mockResolvedValue({
      data: { id: 'process-1' },
    });

    render(
      <MemoryRouter>
        <ConfigTab />
      </MemoryRouter>
    );

    // Get the exit handler
    const exitHandler = mockOn.mock.calls.find(call => call[0] === 'process:exit')?.[1];

    // Simulate response before timeout
    if (exitHandler) {
      exitHandler({
        id: 'process-1',
        code: 0,
        output: ['Test App'],
      });
    }

    // Fast-forward time - timeout should not fire since it was cleared
    jest.advanceTimersByTime(15000);

    await waitFor(() => {
      // Should show success, not timeout state
      expect(screen.getByText(/app registration found: test app/i)).toBeInTheDocument();
    });

    jest.useRealTimers();
  });
});
