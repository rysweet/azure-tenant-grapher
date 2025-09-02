import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import CLITab from '../../renderer/src/components/tabs/CLITab';
import { AppProvider } from '../../renderer/src/context/AppContext';

// Mock the WebSocket hook
jest.mock('../../renderer/src/hooks/useWebSocket', () => ({
  useWebSocket: () => ({
    isConnected: true,
    subscribeToProcess: jest.fn(),
    unsubscribeFromProcess: jest.fn(),
    getProcessOutput: jest.fn(() => []),
  }),
}));

// Mock axios
jest.mock('axios');

// Mock xterm
jest.mock('xterm', () => ({
  Terminal: jest.fn().mockImplementation(() => ({
    open: jest.fn(),
    writeln: jest.fn(),
    write: jest.fn(),
    dispose: jest.fn(),
  })),
}));

// Mock socket.io-client
jest.mock('socket.io-client', () => ({
  io: jest.fn(() => ({
    on: jest.fn(),
    disconnect: jest.fn(),
  })),
}));

const renderWithContext = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      <AppProvider>
        {component}
      </AppProvider>
    </BrowserRouter>
  );
};

describe('CLITab', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders CLI interface correctly', () => {
    renderWithContext(<CLITab />);

    expect(screen.getByText('Command Builder')).toBeInTheDocument();
    expect(screen.getByText('Terminal Output')).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: /command/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /execute/i })).toBeInTheDocument();
  });

  it('allows command selection', async () => {
    renderWithContext(<CLITab />);

    const commandSelect = screen.getByRole('combobox', { name: /command/i });
    fireEvent.mouseDown(commandSelect);

    await waitFor(() => {
      expect(screen.getByText('Build Graph')).toBeInTheDocument();
      expect(screen.getByText('Generate IaC')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Generate IaC'));

    await waitFor(() => {
      expect(screen.getByText('Generate Infrastructure-as-Code templates from graph data')).toBeInTheDocument();
    });
  });

  it('shows command arguments when command is selected', async () => {
    renderWithContext(<CLITab />);

    const commandSelect = screen.getByRole('combobox', { name: /command/i });
    fireEvent.mouseDown(commandSelect);

    await waitFor(() => {
      fireEvent.click(screen.getByText('Build Graph'));
    });

    await waitFor(() => {
      expect(screen.getByLabelText(/tenant id/i)).toBeInTheDocument();
      expect(screen.getByText(/Max LLM Threads/)).toBeInTheDocument();
    });
  });

  it('displays command line preview', async () => {
    renderWithContext(<CLITab />);

    const tenantIdInput = screen.getByLabelText(/tenant id/i);
    fireEvent.change(tenantIdInput, { target: { value: 'test-tenant' } });

    await waitFor(() => {
      expect(screen.getByText(/atg build --tenant-id test-tenant/)).toBeInTheDocument();
    });
  });

  it('shows validation errors for required fields', async () => {
    renderWithContext(<CLITab />);

    const executeButton = screen.getByRole('button', { name: /execute/i });
    fireEvent.click(executeButton);

    await waitFor(() => {
      expect(screen.getByText(/Missing required arguments/)).toBeInTheDocument();
    });
  });

  it('opens command history dialog', async () => {
    renderWithContext(<CLITab />);

    const historyButton = screen.getByLabelText(/command history/i);
    fireEvent.click(historyButton);

    await waitFor(() => {
      expect(screen.getByText('Command History')).toBeInTheDocument();
      expect(screen.getByText('No commands executed yet')).toBeInTheDocument();
    });
  });

  it('handles boolean arguments correctly', async () => {
    renderWithContext(<CLITab />);

    const rebuildEdgesCheckbox = screen.getByLabelText(/rebuild edges/i);
    fireEvent.click(rebuildEdgesCheckbox);

    await waitFor(() => {
      expect(screen.getByText(/--rebuild-edges/)).toBeInTheDocument();
    });
  });

  it('handles slider arguments', async () => {
    renderWithContext(<CLITab />);

    const maxLlmThreadsSlider = screen.getByRole('slider', { name: /max llm threads/i });
    fireEvent.change(maxLlmThreadsSlider, { target: { value: 10 } });

    await waitFor(() => {
      expect(screen.getByText(/--max-llm-threads 10/)).toBeInTheDocument();
    });
  });

  it('copies command to clipboard', async () => {
    // Mock navigator.clipboard
    Object.assign(navigator, {
      clipboard: {
        writeText: jest.fn(),
      },
    });

    renderWithContext(<CLITab />);

    const tenantIdInput = screen.getByLabelText(/tenant id/i);
    fireEvent.change(tenantIdInput, { target: { value: 'test-tenant' } });

    const copyButton = screen.getByLabelText(/copy command/i);
    fireEvent.click(copyButton);

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      expect.stringContaining('atg build --tenant-id test-tenant')
    );
  });

  it('shows examples for selected command', async () => {
    renderWithContext(<CLITab />);

    const examplesSection = screen.getByText('Examples');
    fireEvent.click(examplesSection);

    await waitFor(() => {
      expect(screen.getByText(/build --tenant-id contoso.onmicrosoft.com/)).toBeInTheDocument();
    });
  });
});
