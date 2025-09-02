import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { BrowserRouter } from 'react-router-dom';
import ConfigTab from '../../renderer/src/components/tabs/ConfigTab';
import { AppProvider } from '../../renderer/src/context/AppContext';

// Mock the validation utilities
jest.mock('../../renderer/src/utils/validation', () => ({
  isValidTenantId: jest.fn((id) => id.length > 0),
  isValidUUID: jest.fn((id) => /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id)),
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

describe('ConfigTab', () => {
  beforeEach(() => {
    jest.clearAllMocks();

    // Mock window.electronAPI
    (window as any).electronAPI = {
      store: {
        get: jest.fn(),
        set: jest.fn(),
        delete: jest.fn(),
        getAll: jest.fn(),
      },
    };
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('renders configuration tab with all sections', () => {
    (window as any).electronAPI.store.getAll = jest.fn().mockReturnValue({});

    renderWithProviders(<ConfigTab />);

    expect(screen.getByText('Configuration')).toBeInTheDocument();
    expect(screen.getByText('Azure Credentials')).toBeInTheDocument();
    expect(screen.getByText('Neo4j Settings')).toBeInTheDocument();
    expect(screen.getByText('Application Settings')).toBeInTheDocument();
  });

  test('loads existing configuration on mount', async () => {
    const mockConfig = {
      'azure.tenantId': 'test-tenant-id',
      'azure.clientId': 'test-client-id',
      'azure.clientSecret': 'test-secret',
      'neo4j.uri': 'bolt://localhost:7687',
      'neo4j.username': 'neo4j',
      'neo4j.password': 'test-password',
      'app.maxThreads': 10,
      'app.resourceLimit': 1000,
    };

    (window as any).electronAPI.store.getAll = jest.fn().mockReturnValue(mockConfig);

    renderWithProviders(<ConfigTab />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('test-tenant-id')).toBeInTheDocument();
      expect(screen.getByDisplayValue('test-client-id')).toBeInTheDocument();
      expect(screen.getByDisplayValue('bolt://localhost:7687')).toBeInTheDocument();
      expect(screen.getByDisplayValue('neo4j')).toBeInTheDocument();
    });
  });

  test('validates Azure tenant ID format', async () => {
    const { isValidUUID } = require('../../renderer/src/utils/validation');
    isValidUUID.mockReturnValue(false);

    (window as any).electronAPI.store.getAll = jest.fn().mockReturnValue({});

    renderWithProviders(<ConfigTab />);

    const tenantInput = screen.getByLabelText(/Tenant ID/i);
    const saveButton = screen.getByText(/Save Configuration/i);

    fireEvent.change(tenantInput, { target: { value: 'invalid-id' } });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(screen.getByText(/Invalid Tenant ID format/i)).toBeInTheDocument();
    });
  });

  test('validates Azure client ID format', async () => {
    const { isValidUUID } = require('../../renderer/src/utils/validation');
    isValidUUID.mockImplementation((id) => {
      return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id);
    });

    (window as any).electronAPI.store.getAll = jest.fn().mockReturnValue({});

    renderWithProviders(<ConfigTab />);

    const tenantInput = screen.getByLabelText(/Tenant ID/i);
    const clientInput = screen.getByLabelText(/Client ID/i);
    const saveButton = screen.getByText(/Save Configuration/i);

    fireEvent.change(tenantInput, { target: { value: '12345678-1234-1234-1234-123456789012' } });
    fireEvent.change(clientInput, { target: { value: 'invalid-client-id' } });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(screen.getByText(/Invalid Client ID format/i)).toBeInTheDocument();
    });
  });

  test('saves configuration successfully', async () => {
    const { isValidUUID } = require('../../renderer/src/utils/validation');
    isValidUUID.mockReturnValue(true);

    const mockSet = jest.fn().mockResolvedValue(undefined);
    (window as any).electronAPI.store.set = mockSet;
    (window as any).electronAPI.store.getAll = jest.fn().mockReturnValue({});

    renderWithProviders(<ConfigTab />);

    const tenantInput = screen.getByLabelText(/Tenant ID/i);
    const clientInput = screen.getByLabelText(/Client ID/i);
    const secretInput = screen.getByLabelText(/Client Secret/i);
    const saveButton = screen.getByText(/Save Configuration/i);

    fireEvent.change(tenantInput, { target: { value: '12345678-1234-1234-1234-123456789012' } });
    fireEvent.change(clientInput, { target: { value: '87654321-4321-4321-4321-210987654321' } });
    fireEvent.change(secretInput, { target: { value: 'test-secret' } });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(mockSet).toHaveBeenCalledWith('azure.tenantId', '12345678-1234-1234-1234-123456789012');
      expect(mockSet).toHaveBeenCalledWith('azure.clientId', '87654321-4321-4321-4321-210987654321');
      expect(mockSet).toHaveBeenCalledWith('azure.clientSecret', 'test-secret');
      expect(screen.getByText(/Configuration saved successfully/i)).toBeInTheDocument();
    });
  });

  test('toggles password visibility', () => {
    (window as any).electronAPI.store.getAll = jest.fn().mockReturnValue({
      'azure.clientSecret': 'hidden-secret',
      'neo4j.password': 'hidden-password',
    });

    renderWithProviders(<ConfigTab />);

    const secretInput = screen.getByLabelText(/Client Secret/i);
    const neo4jPasswordInput = screen.getByLabelText(/Neo4j Password/i);

    // Initially passwords should be hidden
    expect(secretInput).toHaveAttribute('type', 'password');
    expect(neo4jPasswordInput).toHaveAttribute('type', 'password');

    // Find and click visibility toggle buttons
    const visibilityButtons = screen.getAllByRole('button', { name: /toggle password visibility/i });

    // Toggle Azure client secret visibility
    fireEvent.click(visibilityButtons[0]);
    expect(secretInput).toHaveAttribute('type', 'text');

    // Toggle Neo4j password visibility
    fireEvent.click(visibilityButtons[1]);
    expect(neo4jPasswordInput).toHaveAttribute('type', 'text');
  });

  test('updates Neo4j settings', async () => {
    const mockSet = jest.fn().mockResolvedValue(undefined);
    (window as any).electronAPI.store.set = mockSet;
    (window as any).electronAPI.store.getAll = jest.fn().mockReturnValue({});

    renderWithProviders(<ConfigTab />);

    const uriInput = screen.getByLabelText(/Neo4j URI/i);
    const usernameInput = screen.getByLabelText(/Neo4j Username/i);
    const passwordInput = screen.getByLabelText(/Neo4j Password/i);
    const saveButton = screen.getByText(/Save Configuration/i);

    fireEvent.change(uriInput, { target: { value: 'bolt://neo4j-server:7687' } });
    fireEvent.change(usernameInput, { target: { value: 'admin' } });
    fireEvent.change(passwordInput, { target: { value: 'secure-password' } });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(mockSet).toHaveBeenCalledWith('neo4j.uri', 'bolt://neo4j-server:7687');
      expect(mockSet).toHaveBeenCalledWith('neo4j.username', 'admin');
      expect(mockSet).toHaveBeenCalledWith('neo4j.password', 'secure-password');
    });
  });

  test('updates application settings', async () => {
    const mockSet = jest.fn().mockResolvedValue(undefined);
    (window as any).electronAPI.store.set = mockSet;
    (window as any).electronAPI.store.getAll = jest.fn().mockReturnValue({});

    renderWithProviders(<ConfigTab />);

    const threadsSlider = screen.getByLabelText(/Max Threads/i);
    const limitSlider = screen.getByLabelText(/Resource Limit/i);
    const saveButton = screen.getByText(/Save Configuration/i);

    fireEvent.change(threadsSlider, { target: { value: 20 } });
    fireEvent.change(limitSlider, { target: { value: 2000 } });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(mockSet).toHaveBeenCalledWith('app.maxThreads', 20);
      expect(mockSet).toHaveBeenCalledWith('app.resourceLimit', 2000);
    });
  });

  test('resets configuration to defaults', async () => {
    const mockSet = jest.fn().mockResolvedValue(undefined);
    const mockDelete = jest.fn().mockResolvedValue(undefined);
    (window as any).electronAPI.store.set = mockSet;
    (window as any).electronAPI.store.delete = mockDelete;
    (window as any).electronAPI.store.getAll = jest.fn().mockReturnValue({
      'azure.tenantId': 'old-tenant',
      'neo4j.uri': 'bolt://old-server:7687',
    });

    renderWithProviders(<ConfigTab />);

    const resetButton = screen.getByText(/Reset to Defaults/i);

    // Mock window.confirm
    window.confirm = jest.fn(() => true);

    fireEvent.click(resetButton);

    await waitFor(() => {
      expect(window.confirm).toHaveBeenCalledWith(
        'Are you sure you want to reset all settings to their default values?'
      );
      expect(mockDelete).toHaveBeenCalled();
      expect(screen.getByText(/Configuration reset to defaults/i)).toBeInTheDocument();
    });

    // Check that fields are reset
    const uriInput = screen.getByLabelText(/Neo4j URI/i) as HTMLInputElement;
    expect(uriInput.value).toBe('bolt://localhost:7687');
  });

  test('cancels reset when user declines confirmation', async () => {
    const mockDelete = jest.fn();
    (window as any).electronAPI.store.delete = mockDelete;
    (window as any).electronAPI.store.getAll = jest.fn().mockReturnValue({
      'azure.tenantId': 'existing-tenant',
    });

    renderWithProviders(<ConfigTab />);

    const resetButton = screen.getByText(/Reset to Defaults/i);

    // Mock window.confirm to return false
    window.confirm = jest.fn(() => false);

    fireEvent.click(resetButton);

    await waitFor(() => {
      expect(window.confirm).toHaveBeenCalled();
      expect(mockDelete).not.toHaveBeenCalled();
    });

    // Original values should remain
    const tenantInput = screen.getByLabelText(/Tenant ID/i) as HTMLInputElement;
    expect(tenantInput.value).toBe('existing-tenant');
  });

  test('displays error when save fails', async () => {
    const mockSet = jest.fn().mockRejectedValue(new Error('Failed to save'));
    (window as any).electronAPI.store.set = mockSet;
    (window as any).electronAPI.store.getAll = jest.fn().mockReturnValue({});

    renderWithProviders(<ConfigTab />);

    const tenantInput = screen.getByLabelText(/Tenant ID/i);
    const saveButton = screen.getByText(/Save Configuration/i);

    fireEvent.change(tenantInput, { target: { value: '12345678-1234-1234-1234-123456789012' } });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(screen.getByText(/Failed to save configuration/i)).toBeInTheDocument();
    });
  });

  test('validates Neo4j URI format', async () => {
    (window as any).electronAPI.store.getAll = jest.fn().mockReturnValue({});

    renderWithProviders(<ConfigTab />);

    const uriInput = screen.getByLabelText(/Neo4j URI/i);
    const saveButton = screen.getByText(/Save Configuration/i);

    fireEvent.change(uriInput, { target: { value: 'invalid-uri' } });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(screen.getByText(/Invalid Neo4j URI format/i)).toBeInTheDocument();
    });
  });

  test('exports configuration to file', async () => {
    const mockConfig = {
      'azure.tenantId': 'export-tenant-id',
      'azure.clientId': 'export-client-id',
      'neo4j.uri': 'bolt://localhost:7687',
    };

    (window as any).electronAPI.store.getAll = jest.fn().mockReturnValue(mockConfig);

    // Mock URL and document methods
    global.URL.createObjectURL = jest.fn(() => 'blob:mock-url');
    global.URL.revokeObjectURL = jest.fn();

    const mockClick = jest.fn();
    const mockAnchor = { href: '', download: '', click: mockClick };
    jest.spyOn(document, 'createElement').mockReturnValue(mockAnchor as any);

    renderWithProviders(<ConfigTab />);

    const exportButton = screen.getByText(/Export Configuration/i);
    fireEvent.click(exportButton);

    await waitFor(() => {
      expect(global.URL.createObjectURL).toHaveBeenCalled();
      expect(mockAnchor.download).toMatch(/atg_config_\d+\.json/);
      expect(mockClick).toHaveBeenCalled();
      expect(global.URL.revokeObjectURL).toHaveBeenCalled();
    });
  });
});
