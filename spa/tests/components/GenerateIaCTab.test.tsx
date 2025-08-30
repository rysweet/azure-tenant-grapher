import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { BrowserRouter } from 'react-router-dom';
import GenerateIaCTab from '../../renderer/src/components/tabs/GenerateIaCTab';
import { AppProvider } from '../../renderer/src/context/AppContext';

// Mock the validation utilities
jest.mock('../../renderer/src/utils/validation', () => ({
  isValidTenantId: jest.fn((id) => id.length > 0),
  isValidResourceLimit: jest.fn((limit) => limit >= 0 && limit <= 10000),
}));

// Mock Monaco Editor
jest.mock('@monaco-editor/react', () => ({
  __esModule: true,
  default: ({ value, language }: any) => (
    <textarea
      data-testid={`monaco-editor-${language}`}
      value={value}
      readOnly
      aria-label={`${language} editor`}
    />
  ),
}));

// Mock the LogViewer component
jest.mock('../../renderer/src/components/widgets/LogViewer', () => ({
  __esModule: true,
  default: ({ logs }: any) => (
    <div data-testid="log-viewer">
      Log Viewer
      {logs && logs.length > 0 && <span>{logs.length} logs</span>}
    </div>
  ),
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

describe('GenerateIaCTab', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    
    // Mock window.electronAPI
    (window as any).electronAPI = {
      cli: {
        execute: jest.fn(),
      },
      on: jest.fn(),
    };
    
    // Mock file operations
    global.URL.createObjectURL = jest.fn(() => 'blob:mock-url');
    global.URL.revokeObjectURL = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('renders generate IaC tab with all components', () => {
    renderWithProviders(<GenerateIaCTab />);
    
    expect(screen.getByText('Generate Infrastructure as Code')).toBeInTheDocument();
    expect(screen.getByLabelText(/Tenant ID/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/IaC Format/i)).toBeInTheDocument();
    expect(screen.getByText(/Resource Limit/i)).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /Include Comments/i })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /Include Tags/i })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /Dry Run/i })).toBeInTheDocument();
    expect(screen.getByText(/Generate IaC/i)).toBeInTheDocument();
  });

  test('validates tenant ID before generation', async () => {
    renderWithProviders(<GenerateIaCTab />);
    
    const generateButton = screen.getByText(/Generate IaC/i);
    
    // Click without entering tenant ID
    fireEvent.click(generateButton);
    
    await waitFor(() => {
      expect(screen.getByText(/Tenant ID is required/i)).toBeInTheDocument();
    });
  });

  test('validates tenant ID format', async () => {
    const { isValidTenantId } = require('../../renderer/src/utils/validation');
    isValidTenantId.mockReturnValue(false);
    
    renderWithProviders(<GenerateIaCTab />);
    
    const tenantInput = screen.getByLabelText(/Tenant ID/i);
    const generateButton = screen.getByText(/Generate IaC/i);
    
    fireEvent.change(tenantInput, { target: { value: 'invalid-id' } });
    fireEvent.click(generateButton);
    
    await waitFor(() => {
      expect(screen.getByText(/Invalid Tenant ID format/i)).toBeInTheDocument();
    });
  });

  test('changes IaC format selection', () => {
    renderWithProviders(<GenerateIaCTab />);
    
    const formatSelect = screen.getByLabelText(/IaC Format/i);
    
    fireEvent.mouseDown(formatSelect);
    
    const bicepOption = screen.getByText('Bicep');
    fireEvent.click(bicepOption);
    
    expect(formatSelect).toHaveTextContent('Bicep');
  });

  test('generates IaC successfully with Terraform', async () => {
    const mockOutput = 'resource "azurerm_resource_group" "example" {\n  name = "example"\n}';
    const mockExecute = jest.fn().mockResolvedValue({ 
      data: { id: 'test-process-id' } 
    });
    
    const mockOn = jest.fn((event, callback) => {
      if (event === 'process:output') {
        callback({ 
          id: 'test-process-id', 
          data: { type: 'stdout', data: mockOutput.split('\n') } 
        });
      } else if (event === 'process:exit') {
        setTimeout(() => {
          callback({ id: 'test-process-id', code: 0 });
        }, 10);
      }
    });
    
    const { isValidTenantId } = require('../../renderer/src/utils/validation');
    isValidTenantId.mockReturnValue(true);
    
    (window as any).electronAPI.cli.execute = mockExecute;
    (window as any).electronAPI.on = mockOn;
    
    renderWithProviders(<GenerateIaCTab />);
    
    const tenantInput = screen.getByLabelText(/Tenant ID/i);
    fireEvent.change(tenantInput, { target: { value: 'valid-tenant-id' } });
    
    const generateButton = screen.getByText(/Generate IaC/i);
    fireEvent.click(generateButton);
    
    await waitFor(() => {
      expect(mockExecute).toHaveBeenCalledWith(
        'generate-iac',
        expect.arrayContaining(['--tenant-id', 'valid-tenant-id', '--format', 'terraform'])
      );
    });
    
    await waitFor(() => {
      const editor = screen.getByTestId('monaco-editor-hcl');
      expect(editor).toHaveValue(expect.stringContaining('azurerm_resource_group'));
    });
  });

  test('generates IaC with ARM template format', async () => {
    const mockOutput = '{\n  "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#"\n}';
    const mockExecute = jest.fn().mockResolvedValue({ 
      data: { id: 'test-process-id' } 
    });
    
    const mockOn = jest.fn((event, callback) => {
      if (event === 'process:output') {
        callback({ 
          id: 'test-process-id', 
          data: { type: 'stdout', data: mockOutput.split('\n') } 
        });
      } else if (event === 'process:exit') {
        callback({ id: 'test-process-id', code: 0 });
      }
    });
    
    const { isValidTenantId } = require('../../renderer/src/utils/validation');
    isValidTenantId.mockReturnValue(true);
    
    (window as any).electronAPI.cli.execute = mockExecute;
    (window as any).electronAPI.on = mockOn;
    
    renderWithProviders(<GenerateIaCTab />);
    
    const tenantInput = screen.getByLabelText(/Tenant ID/i);
    fireEvent.change(tenantInput, { target: { value: 'valid-tenant-id' } });
    
    const formatSelect = screen.getByLabelText(/IaC Format/i);
    fireEvent.mouseDown(formatSelect);
    const armOption = screen.getByText('ARM Template');
    fireEvent.click(armOption);
    
    const generateButton = screen.getByText(/Generate IaC/i);
    fireEvent.click(generateButton);
    
    await waitFor(() => {
      expect(mockExecute).toHaveBeenCalledWith(
        'generate-iac',
        expect.arrayContaining(['--format', 'arm'])
      );
    });
    
    await waitFor(() => {
      const editor = screen.getByTestId('monaco-editor-json');
      expect(editor).toHaveValue(expect.stringContaining('$schema'));
    });
  });

  test('includes optional parameters when checkboxes are selected', async () => {
    const mockExecute = jest.fn().mockResolvedValue({ 
      data: { id: 'test-process-id' } 
    });
    
    const { isValidTenantId } = require('../../renderer/src/utils/validation');
    isValidTenantId.mockReturnValue(true);
    
    (window as any).electronAPI.cli.execute = mockExecute;
    
    renderWithProviders(<GenerateIaCTab />);
    
    const tenantInput = screen.getByLabelText(/Tenant ID/i);
    fireEvent.change(tenantInput, { target: { value: 'valid-tenant-id' } });
    
    const commentsCheckbox = screen.getByRole('checkbox', { name: /Include Comments/i });
    const tagsCheckbox = screen.getByRole('checkbox', { name: /Include Tags/i });
    const dryRunCheckbox = screen.getByRole('checkbox', { name: /Dry Run/i });
    
    fireEvent.click(commentsCheckbox);
    fireEvent.click(tagsCheckbox);
    fireEvent.click(dryRunCheckbox);
    
    const generateButton = screen.getByText(/Generate IaC/i);
    fireEvent.click(generateButton);
    
    await waitFor(() => {
      expect(mockExecute).toHaveBeenCalledWith(
        'generate-iac',
        expect.arrayContaining(['--include-comments', '--include-tags', '--dry-run'])
      );
    });
  });

  test('updates resource limit slider', async () => {
    const mockExecute = jest.fn().mockResolvedValue({ 
      data: { id: 'test-process-id' } 
    });
    
    const { isValidTenantId } = require('../../renderer/src/utils/validation');
    isValidTenantId.mockReturnValue(true);
    
    (window as any).electronAPI.cli.execute = mockExecute;
    
    renderWithProviders(<GenerateIaCTab />);
    
    const tenantInput = screen.getByLabelText(/Tenant ID/i);
    fireEvent.change(tenantInput, { target: { value: 'valid-tenant-id' } });
    
    const slider = screen.getByRole('slider', { name: /Resource Limit/i });
    fireEvent.change(slider, { target: { value: 500 } });
    
    expect(screen.getByText(/Resource Limit: 500/i)).toBeInTheDocument();
    
    const generateButton = screen.getByText(/Generate IaC/i);
    fireEvent.click(generateButton);
    
    await waitFor(() => {
      expect(mockExecute).toHaveBeenCalledWith(
        'generate-iac',
        expect.arrayContaining(['--resource-limit', '500'])
      );
    });
  });

  test('shows loading state during generation', async () => {
    const mockExecute = jest.fn(() => new Promise(resolve => setTimeout(resolve, 100)));
    const { isValidTenantId } = require('../../renderer/src/utils/validation');
    isValidTenantId.mockReturnValue(true);
    
    (window as any).electronAPI.cli.execute = mockExecute;
    
    renderWithProviders(<GenerateIaCTab />);
    
    const tenantInput = screen.getByLabelText(/Tenant ID/i);
    fireEvent.change(tenantInput, { target: { value: 'valid-tenant-id' } });
    
    const generateButton = screen.getByText(/Generate IaC/i);
    fireEvent.click(generateButton);
    
    expect(screen.getByText(/Generating.../i)).toBeInTheDocument();
    expect(generateButton).toBeDisabled();
    expect(tenantInput).toBeDisabled();
  });

  test('displays error when generation fails', async () => {
    const mockExecute = jest.fn().mockRejectedValue(new Error('Generation failed'));
    const { isValidTenantId } = require('../../renderer/src/utils/validation');
    isValidTenantId.mockReturnValue(true);
    
    (window as any).electronAPI.cli.execute = mockExecute;
    
    renderWithProviders(<GenerateIaCTab />);
    
    const tenantInput = screen.getByLabelText(/Tenant ID/i);
    fireEvent.change(tenantInput, { target: { value: 'valid-tenant-id' } });
    
    const generateButton = screen.getByText(/Generate IaC/i);
    fireEvent.click(generateButton);
    
    await waitFor(() => {
      expect(screen.getByText(/Generation failed/i)).toBeInTheDocument();
    });
  });

  test('exports IaC to file with correct extension', async () => {
    const mockOutput = 'resource "example" {}';
    const mockExecute = jest.fn().mockResolvedValue({ 
      data: { id: 'test-process-id' } 
    });
    
    const mockOn = jest.fn((event, callback) => {
      if (event === 'process:output') {
        callback({ 
          id: 'test-process-id', 
          data: { type: 'stdout', data: [mockOutput] } 
        });
      } else if (event === 'process:exit') {
        callback({ id: 'test-process-id', code: 0 });
      }
    });
    
    const { isValidTenantId } = require('../../renderer/src/utils/validation');
    isValidTenantId.mockReturnValue(true);
    
    (window as any).electronAPI.cli.execute = mockExecute;
    (window as any).electronAPI.on = mockOn;
    
    // Mock createElement and click
    const mockClick = jest.fn();
    const mockAnchor = { href: '', download: '', click: mockClick };
    jest.spyOn(document, 'createElement').mockReturnValue(mockAnchor as any);
    
    renderWithProviders(<GenerateIaCTab />);
    
    const tenantInput = screen.getByLabelText(/Tenant ID/i);
    fireEvent.change(tenantInput, { target: { value: 'valid-tenant-id' } });
    
    // Generate IaC first
    const generateButton = screen.getByText(/Generate IaC/i);
    fireEvent.click(generateButton);
    
    await waitFor(() => {
      const editor = screen.getByTestId('monaco-editor-hcl');
      expect(editor).toHaveValue(mockOutput);
    });
    
    // Export the IaC
    const exportButton = screen.getByText(/Export/i);
    fireEvent.click(exportButton);
    
    expect(global.URL.createObjectURL).toHaveBeenCalled();
    expect(mockAnchor.download).toMatch(/infrastructure_\d+\.tf/);
    expect(mockClick).toHaveBeenCalled();
    expect(global.URL.revokeObjectURL).toHaveBeenCalled();
  });

  test('copies IaC to clipboard', async () => {
    const mockOutput = 'resource "example" {}';
    const mockExecute = jest.fn().mockResolvedValue({ 
      data: { id: 'test-process-id' } 
    });
    
    const mockOn = jest.fn((event, callback) => {
      if (event === 'process:output') {
        callback({ 
          id: 'test-process-id', 
          data: { type: 'stdout', data: [mockOutput] } 
        });
      } else if (event === 'process:exit') {
        callback({ id: 'test-process-id', code: 0 });
      }
    });
    
    const { isValidTenantId } = require('../../renderer/src/utils/validation');
    isValidTenantId.mockReturnValue(true);
    
    (window as any).electronAPI.cli.execute = mockExecute;
    (window as any).electronAPI.on = mockOn;
    
    // Mock clipboard API
    Object.assign(navigator, {
      clipboard: {
        writeText: jest.fn().mockResolvedValue(undefined),
      },
    });
    
    renderWithProviders(<GenerateIaCTab />);
    
    const tenantInput = screen.getByLabelText(/Tenant ID/i);
    fireEvent.change(tenantInput, { target: { value: 'valid-tenant-id' } });
    
    // Generate IaC first
    const generateButton = screen.getByText(/Generate IaC/i);
    fireEvent.click(generateButton);
    
    await waitFor(() => {
      const editor = screen.getByTestId('monaco-editor-hcl');
      expect(editor).toHaveValue(mockOutput);
    });
    
    // Copy the IaC
    const copyButton = screen.getByText(/Copy/i);
    fireEvent.click(copyButton);
    
    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(mockOutput);
    });
    
    expect(screen.getByText(/Copied!/i)).toBeInTheDocument();
  });
});