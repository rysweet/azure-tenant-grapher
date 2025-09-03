import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import LogsTab from '../../renderer/src/components/tabs/LogsTab';
import { AppProvider } from '../../renderer/src/context/AppContext';

// Mock Monaco Editor
jest.mock('@monaco-editor/react', () => {
  return {
    __esModule: true,
    default: ({ value, onMount }: any) => {
      // Call onMount with a mock editor
      React.useEffect(() => {
        if (onMount) {
          const mockEditor = {
            getModel: () => ({
              getLineCount: () => value ? value.split('\n').length : 1,
            }),
            setPosition: jest.fn(),
            revealLine: jest.fn(),
          };
          onMount(mockEditor);
        }
      }, [onMount]);

      return (
        <textarea
          data-testid="monaco-editor"
          value={value || ''}
          readOnly
          style={{ width: '100%', height: '100%', fontFamily: 'monospace' }}
        />
      );
    },
  };
});

const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      <AppProvider>
        {component}
      </AppProvider>
    </BrowserRouter>
  );
};

describe('LogsTab', () => {
  beforeEach(() => {
    // Clear any existing logs
    jest.clearAllMocks();
  });

  it('renders with no logs message when empty', () => {
    renderWithProviders(<LogsTab />);

    expect(screen.getByText(/System Logs/i)).toBeInTheDocument();
    expect(screen.getByText(/No logs available/i)).toBeInTheDocument();
  });

  it('shows log count badge', () => {
    renderWithProviders(<LogsTab />);

    expect(screen.getByText(/0 \/ 0 logs/i)).toBeInTheDocument();
  });

  it('has auto-scroll toggle', () => {
    renderWithProviders(<LogsTab />);

    const autoScrollToggle = screen.getByLabelText(/auto-scroll/i);
    expect(autoScrollToggle).toBeInTheDocument();
    expect(autoScrollToggle).toBeChecked();
  });

  it('has filter controls', () => {
    renderWithProviders(<LogsTab />);

    // Expand filters
    const filtersButton = screen.getByText(/Filters & Settings/i);
    fireEvent.click(filtersButton);

    expect(screen.getByLabelText(/Search logs/i)).toBeInTheDocument();
    expect(screen.getByText(/Log Levels/i)).toBeInTheDocument();
    expect(screen.getByText(/Sort by/i)).toBeInTheDocument();
  });

  it('has action buttons', () => {
    renderWithProviders(<LogsTab />);

    expect(screen.getByTitle(/Scroll to bottom/i)).toBeInTheDocument();
    expect(screen.getByTitle(/Export logs/i)).toBeInTheDocument();
    expect(screen.getByTitle(/Add test logs/i)).toBeInTheDocument();
    expect(screen.getByTitle(/Clear all logs/i)).toBeInTheDocument();
  });

  it('can add test logs', async () => {
    renderWithProviders(<LogsTab />);

    const addTestLogsButton = screen.getByTitle(/Add test logs/i);
    fireEvent.click(addTestLogsButton);

    // Wait for logs to be added
    await waitFor(() => {
      expect(screen.queryByText(/No logs available/i)).not.toBeInTheDocument();
    });

    // Should show Monaco editor instead of empty message
    expect(screen.getByTestId('monaco-editor')).toBeInTheDocument();
  });

  it('can clear logs', async () => {
    renderWithProviders(<LogsTab />);

    // Add test logs first
    const addTestLogsButton = screen.getByTitle(/Add test logs/i);
    fireEvent.click(addTestLogsButton);

    await waitFor(() => {
      expect(screen.getByTestId('monaco-editor')).toBeInTheDocument();
    });

    // Clear logs
    const clearLogsButton = screen.getByTitle(/Clear all logs/i);
    fireEvent.click(clearLogsButton);

    // Should show empty message again
    expect(screen.getByText(/No logs available/i)).toBeInTheDocument();
  });

  it('can toggle auto-scroll', () => {
    renderWithProviders(<LogsTab />);

    const autoScrollToggle = screen.getByLabelText(/auto-scroll/i);

    expect(autoScrollToggle).toBeChecked();

    fireEvent.click(autoScrollToggle);
    expect(autoScrollToggle).not.toBeChecked();

    fireEvent.click(autoScrollToggle);
    expect(autoScrollToggle).toBeChecked();
  });

  it('can expand and collapse filters', () => {
    renderWithProviders(<LogsTab />);

    const filtersButton = screen.getByText(/Filters & Settings/i);

    // Should not show filter controls initially
    expect(screen.queryByLabelText(/Search logs/i)).not.toBeInTheDocument();

    // Expand filters
    fireEvent.click(filtersButton);
    expect(screen.getByLabelText(/Search logs/i)).toBeInTheDocument();

    // Collapse filters
    fireEvent.click(filtersButton);
    expect(screen.queryByLabelText(/Search logs/i)).not.toBeInTheDocument();
  });
});
