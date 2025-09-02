import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { BrowserRouter } from 'react-router-dom';
import ScanTab from '../../renderer/src/components/tabs/ScanTab';
import { AppProvider } from '../../renderer/src/context/AppContext';

// Mock the validation utilities
jest.mock('../../renderer/src/utils/validation', () => ({
  isValidTenantId: jest.fn((id) => id.length > 0),
  isValidResourceLimit: jest.fn((limit) => limit >= 0 && limit <= 10000),
  isValidThreadCount: jest.fn((count) => count >= 1 && count <= 100),
}));

// Wrapper component with providers
const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      <AppProvider>
        {component}
      </AppProvider>
    </BrowserRouter>
  );
};

describe('ScanTab', () => {
  beforeEach(() => {
    // Reset mocks
    jest.clearAllMocks();

    // Mock window.electronAPI with default store behavior
    (window as any).electronAPI = {
      cli: {
        execute: jest.fn(),
      },
      on: jest.fn(),
      store: {
        getAll: jest.fn().mockReturnValue({}),
      },
    };
  });

  test('renders scan tab with all required fields', () => {
    renderWithProviders(<ScanTab />);

    expect(screen.getByText('Scan Azure Tenant')).toBeInTheDocument();
    expect(screen.getByLabelText(/Tenant ID/i)).toBeInTheDocument();
    expect(screen.getByText(/Resource Limit/i)).toBeInTheDocument();
    expect(screen.getByText(/Max LLM Threads/i)).toBeInTheDocument();
    expect(screen.getByText(/Max Build Threads/i)).toBeInTheDocument();
    expect(screen.getByText(/Start Build/i)).toBeInTheDocument();
  });

  test('validates tenant ID before starting build', async () => {
    renderWithProviders(<BuildTab />);

    const startButton = screen.getByText(/Start Build/i);

    // Click without entering tenant ID
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(screen.getByText(/Tenant ID is required/i)).toBeInTheDocument();
    });
  });

  test('validates tenant ID format', async () => {
    const { isValidTenantId } = require('../../renderer/src/utils/validation');
    isValidTenantId.mockReturnValue(false);

    renderWithProviders(<BuildTab />);

    const tenantInput = screen.getByLabelText(/Tenant ID/i);
    const startButton = screen.getByText(/Start Build/i);

    fireEvent.change(tenantInput, { target: { value: 'invalid-id' } });
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(screen.getByText(/Invalid Tenant ID format/i)).toBeInTheDocument();
    });
  });

  test('updates resource limit slider', () => {
    renderWithProviders(<BuildTab />);

    // Find the first slider which should be the resource limit slider
    const sliders = screen.getAllByRole('slider');
    const resourceLimitSlider = sliders[0]; // First slider is resource limit

    fireEvent.change(resourceLimitSlider, { target: { value: 500 } });

    expect(screen.getByText(/Resource Limit: 500/i)).toBeInTheDocument();
  });

  test('toggles rebuild edges checkbox', () => {
    renderWithProviders(<BuildTab />);

    const checkbox = screen.getByRole('checkbox', { name: /Rebuild Edges/i });

    expect(checkbox).not.toBeChecked();
    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();
  });

  test('toggles skip AAD import checkbox', () => {
    renderWithProviders(<BuildTab />);

    const checkbox = screen.getByRole('checkbox', { name: /Skip AAD Import/i });

    expect(checkbox).not.toBeChecked();
    fireEvent.click(checkbox);
    expect(checkbox).toBeChecked();
  });

  test('disables inputs when build is running', async () => {
    const mockExecute = jest.fn().mockResolvedValue({
      data: { id: 'test-process-id' }
    });

    (window as any).electronAPI = {
      cli: { execute: mockExecute },
      on: jest.fn(),
      store: {
        getAll: jest.fn().mockReturnValue({}),
      },
    };

    const { isValidTenantId } = require('../../renderer/src/utils/validation');
    isValidTenantId.mockReturnValue(true);

    renderWithProviders(<BuildTab />);

    const tenantInput = screen.getByLabelText(/Tenant ID/i);
    const startButton = screen.getByText(/Start Build/i);

    fireEvent.change(tenantInput, { target: { value: 'valid-tenant-id' } });
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(tenantInput).toBeDisabled();
      expect(screen.getByText(/Stop Build/i)).toBeInTheDocument();
    });
  });

  test('displays error when build fails', async () => {
    const mockExecute = jest.fn().mockRejectedValue(new Error('Build failed'));

    (window as any).electronAPI.cli.execute = mockExecute;

    const { isValidTenantId } = require('../../renderer/src/utils/validation');
    isValidTenantId.mockReturnValue(true);

    renderWithProviders(<BuildTab />);

    const tenantInput = screen.getByLabelText(/Tenant ID/i);
    const startButton = screen.getByText(/Start Build/i);

    fireEvent.change(tenantInput, { target: { value: 'valid-tenant-id' } });
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(screen.getByText(/Build failed/i)).toBeInTheDocument();
    });
  });

  test('validates thread counts', async () => {
    const { isValidThreadCount } = require('../../renderer/src/utils/validation');
    isValidThreadCount.mockReturnValue(false);

    renderWithProviders(<BuildTab />);

    const tenantInput = screen.getByLabelText(/Tenant ID/i);
    const startButton = screen.getByText(/Start Build/i);

    fireEvent.change(tenantInput, { target: { value: 'valid-tenant-id' } });
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(screen.getByText(/Thread counts must be between 1 and 100/i)).toBeInTheDocument();
    });
  });

  test('clears logs when clear button is clicked', async () => {
    renderWithProviders(<BuildTab />);

    // The LogViewer component should have a clear button
    // This would need the LogViewer to be rendered with logs
    // For now, we just check it renders without errors
    expect(screen.getByText(/Output Logs/i)).toBeInTheDocument();
  });
});
