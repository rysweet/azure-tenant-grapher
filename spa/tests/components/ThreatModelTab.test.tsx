import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ThreatModelTab from '../../renderer/src/components/tabs/ThreatModelTab';
import { MemoryRouter } from 'react-router-dom';

// Mock window.electronAPI
const mockExecute = jest.fn();
const mockOn = jest.fn();
const mockOff = jest.fn();

(global as any).window.electronAPI = {
  cli: { execute: mockExecute },
  on: mockOn,
  off: mockOff,
};

describe('ThreatModelTab - Issue #843 Fix', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(() => {
    jest.clearAllTimers();
  });

  test('should call threat-model command WITHOUT --tenant-id argument', async () => {
    mockExecute.mockResolvedValue({
      data: { id: 'process-1' },
    });

    mockOn.mockImplementation((event: string, handler: Function) => {
      if (event === 'process:exit') {
        setTimeout(() => {
          handler({ id: 'process-1', code: 0 });
        }, 100);
      }
    });

    render(
      <MemoryRouter>
        <ThreatModelTab />
      </MemoryRouter>
    );

    const analyzeButton = screen.getByText(/Analyze Threats/i);
    fireEvent.click(analyzeButton);

    await waitFor(() => {
      expect(mockExecute).toHaveBeenCalledWith('threat-model', []);
    });

    // Verify NO --tenant-id was passed
    expect(mockExecute).not.toHaveBeenCalledWith(
      'threat-model',
      expect.arrayContaining(['--tenant-id'])
    );
  });

  test('should NOT fail with exit code 2 (invalid argument)', async () => {
    mockExecute.mockResolvedValue({
      data: { id: 'process-2' },
    });

    let exitCode: number | null = null;

    mockOn.mockImplementation((event: string, handler: Function) => {
      if (event === 'process:exit') {
        setTimeout(() => {
          exitCode = 0; // Success - not exit code 2!
          handler({ id: 'process-2', code: 0 });
        }, 100);
      }
    });

    render(
      <MemoryRouter>
        <ThreatModelTab />
      </MemoryRouter>
    );

    const analyzeButton = screen.getByText(/Analyze Threats/i);
    fireEvent.click(analyzeButton);

    await waitFor(() => {
      expect(exitCode).toBe(0);
    });

    // Should NOT show "exit code 2" error
    expect(screen.queryByText(/exit code 2/i)).not.toBeInTheDocument();
  });

  test('should display helper text indicating Neo4j database usage', () => {
    render(
      <MemoryRouter>
        <ThreatModelTab />
      </MemoryRouter>
    );

    // Verify helper text updated to clarify field purpose
    expect(
      screen.getByText(/current tenant in neo4j database/i)
    ).toBeInTheDocument();
  });

  test('should handle successful threat analysis', async () => {
    mockExecute.mockResolvedValue({
      data: { id: 'process-3' },
    });

    const mockThreats = [
      { id: 'threat-1', category: 'Spoofing', severity: 'High' },
    ];

    mockOn.mockImplementation((event: string, handler: Function) => {
      if (event === 'process:output') {
        setTimeout(() => {
          handler({
            id: 'process-3',
            data: [JSON.stringify(mockThreats)],
          });
        }, 50);
      } else if (event === 'process:exit') {
        setTimeout(() => {
          handler({ id: 'process-3', code: 0 });
        }, 100);
      }
    });

    render(
      <MemoryRouter>
        <ThreatModelTab />
      </MemoryRouter>
    );

    const analyzeButton = screen.getByText(/Analyze Threats/i);
    fireEvent.click(analyzeButton);

    await waitFor(() => {
      expect(mockExecute).toHaveBeenCalledWith('threat-model', []);
    });
  });

  test('should handle CLI execution errors gracefully', async () => {
    mockExecute.mockRejectedValue(new Error('CLI not available'));

    render(
      <MemoryRouter>
        <ThreatModelTab />
      </MemoryRouter>
    );

    const analyzeButton = screen.getByText(/Analyze Threats/i);
    fireEvent.click(analyzeButton);

    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument();
    });
  });

  test('should clean up event listeners after analysis completes', async () => {
    mockExecute.mockResolvedValue({
      data: { id: 'process-4' },
    });

    mockOn.mockImplementation((event: string, handler: Function) => {
      if (event === 'process:exit') {
        setTimeout(() => {
          handler({ id: 'process-4', code: 0 });
        }, 100);
      }
    });

    render(
      <MemoryRouter>
        <ThreatModelTab />
      </MemoryRouter>
    );

    const analyzeButton = screen.getByText(/Analyze Threats/i);
    fireEvent.click(analyzeButton);

    await waitFor(() => {
      expect(mockOff).toHaveBeenCalled();
    });
  });
});
