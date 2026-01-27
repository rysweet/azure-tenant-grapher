/// <reference types="jest" />
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { BrowserRouter } from 'react-router-dom';
import DeployTab from '../../renderer/src/components/tabs/DeployTab';
import { AppProvider } from '../../renderer/src/context/AppContext';

// Mock the TenantSelector component
jest.mock('../../renderer/src/components/shared/TenantSelector', () => ({
  __esModule: true,
  default: ({ label, value, onChange, disabled, required, helperText }: any) => (
    <div>
      <label htmlFor={label}>{label}</label>
      <input
        id={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        required={required}
        aria-label={label}
      />
      {helperText && <span>{helperText}</span>}
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

describe('DeployTab - Issues #839 and #840', () => {
  let mockExecute: jest.Mock;
  let mockOn: jest.Mock;
  let mockOff: jest.Mock;

  beforeEach(() => {
    // Reset mocks
    jest.clearAllMocks();

    mockExecute = jest.fn();
    mockOn = jest.fn();
    mockOff = jest.fn();

    // Mock window.electronAPI
    (window as any).electronAPI = {
      cli: {
        execute: mockExecute,
      },
      on: mockOn,
      off: mockOff,
      store: {
        getAll: jest.fn().mockReturnValue({}),
      },
    };
  });

  describe('Rendering - Issue #839', () => {
    test('renders deploy tab with all required fields', () => {
      renderWithProviders(<DeployTab />);

      expect(screen.getByText('Deploy Infrastructure as Code to Azure')).toBeInTheDocument();
      expect(screen.getByLabelText('Source Tenant')).toBeInTheDocument();
      expect(screen.getByLabelText('Target Tenant')).toBeInTheDocument();
      expect(screen.getByLabelText(/Resource Group/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Azure Region/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/IaC Format/i)).toBeInTheDocument();
      expect(screen.getByText(/Dry Run/i)).toBeInTheDocument();
    });

    test('does NOT render IaC Directory field (Issue #839)', () => {
      renderWithProviders(<DeployTab />);

      // IaC Directory field should NOT exist
      expect(screen.queryByLabelText(/IaC Directory/i)).not.toBeInTheDocument();
      expect(screen.queryByLabelText(/Infrastructure Directory/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/Browse/i)).not.toBeInTheDocument();
    });

    test('renders Source Tenant selector (Issue #839)', () => {
      renderWithProviders(<DeployTab />);

      const sourceTenantInput = screen.getByLabelText('Source Tenant');
      expect(sourceTenantInput).toBeInTheDocument();
      expect(screen.getByText('Scanned tenant to generate IaC from')).toBeInTheDocument();
    });

    test('renders Target Tenant selector (Issue #839)', () => {
      renderWithProviders(<DeployTab />);

      const targetTenantInput = screen.getByLabelText('Target Tenant');
      expect(targetTenantInput).toBeInTheDocument();
      expect(screen.getByText('Azure tenant to deploy resources to')).toBeInTheDocument();
    });

    test('renders info alert about automatic IaC generation', () => {
      renderWithProviders(<DeployTab />);

      expect(screen.getByText(/This tab automatically generates IaC/i)).toBeInTheDocument();
      expect(screen.getByText(/Scanned the source tenant/i)).toBeInTheDocument();
    });
  });

  describe('Two-Phase Workflow Execution - Issue #839', () => {
    test('executes Phase 1 (generate-iac) with correct arguments', async () => {
      const iacProcessId = 'iac-process-123';
      mockExecute.mockResolvedValueOnce({
        data: { id: iacProcessId }
      });

      renderWithProviders(<DeployTab />);

      const sourceTenantInput = screen.getByLabelText('Source Tenant');
      const targetTenantInput = screen.getByLabelText('Target Tenant');
      const resourceGroupInput = screen.getByLabelText(/Resource Group/i);
      const deployButton = screen.getByRole('button', { name: /Validate Deployment|Deploy to Azure/i });

      fireEvent.change(sourceTenantInput, { target: { value: 'source-tenant-123' } });
      fireEvent.change(targetTenantInput, { target: { value: 'target-tenant-456' } });
      fireEvent.change(resourceGroupInput, { target: { value: 'test-rg' } });
      fireEvent.click(deployButton);

      await waitFor(() => {
        expect(mockExecute).toHaveBeenCalledWith('generate-iac', expect.arrayContaining([
          '--source-tenant-id', 'source-tenant-123',
          '--target-tenant-id', 'target-tenant-456',
          '--output', 'outputs/iac',
          '--format', 'terraform',
          '--skip-conflict-check',
          '--skip-name-validation',
          '--skip-validation',
          '--no-auto-import-existing',
        ]));
      });
    });

    test('shows Phase 1 progress message', async () => {
      mockExecute.mockResolvedValueOnce({ data: { id: 'iac-123' } });

      renderWithProviders(<DeployTab />);

      const sourceTenantInput = screen.getByLabelText('Source Tenant');
      const targetTenantInput = screen.getByLabelText('Target Tenant');
      const resourceGroupInput = screen.getByLabelText(/Resource Group/i);
      const deployButton = screen.getByRole('button', { name: /Validate Deployment|Deploy to Azure/i });

      fireEvent.change(sourceTenantInput, { target: { value: 'source-123' } });
      fireEvent.change(targetTenantInput, { target: { value: 'target-456' } });
      fireEvent.change(resourceGroupInput, { target: { value: 'test-rg' } });
      fireEvent.click(deployButton);

      await waitFor(() => {
        expect(screen.getByText(/Phase 1: Generating Infrastructure as Code/i)).toBeInTheDocument();
      });
    });

    test('does NOT proceed to Phase 2 if Phase 1 fails', async () => {
      const iacProcessId = 'iac-123';

      mockExecute.mockResolvedValueOnce({ data: { id: iacProcessId } });

      let iacExitHandler: any;
      mockOn.mockImplementation((event: string, handler: any) => {
        if (event === 'process:exit') {
          iacExitHandler = handler;
        }
      });

      renderWithProviders(<DeployTab />);

      const sourceTenantInput = screen.getByLabelText('Source Tenant');
      const targetTenantInput = screen.getByLabelText('Target Tenant');
      const resourceGroupInput = screen.getByLabelText(/Resource Group/i);
      const deployButton = screen.getByRole('button', { name: /Validate Deployment|Deploy to Azure/i });

      fireEvent.change(sourceTenantInput, { target: { value: 'source-123' } });
      fireEvent.change(targetTenantInput, { target: { value: 'target-456' } });
      fireEvent.change(resourceGroupInput, { target: { value: 'test-rg' } });
      fireEvent.click(deployButton);

      await waitFor(() => {
        expect(mockExecute).toHaveBeenCalledWith('generate-iac', expect.any(Array));
      });

      // Simulate Phase 1 failure
      if (iacExitHandler) {
        iacExitHandler({ id: iacProcessId, code: 1 });
      }

      await waitFor(() => {
        expect(screen.getByText(/IaC generation failed/i)).toBeInTheDocument();
      });

      // Verify deploy was NOT called (only generate-iac)
      expect(mockExecute).toHaveBeenCalledTimes(1);
      expect(mockExecute).not.toHaveBeenCalledWith('deploy', expect.any(Array));
    });
  });

  describe('Validation', () => {
    test('validates required fields before deployment', async () => {
      renderWithProviders(<DeployTab />);

      const deployButton = screen.getByRole('button', { name: /Validate Deployment|Deploy to Azure/i });

      // Clear required fields
      const sourceTenantInput = screen.getByLabelText('Source Tenant');
      const resourceGroupInput = screen.getByLabelText(/Resource Group/i);

      fireEvent.change(sourceTenantInput, { target: { value: '' } });
      fireEvent.change(resourceGroupInput, { target: { value: '' } });
      fireEvent.click(deployButton);

      await waitFor(() => {
        expect(screen.getByText(/Source Tenant, Target Tenant, and Resource Group are required/i)).toBeInTheDocument();
      });

      expect(mockExecute).not.toHaveBeenCalled();
    });
  });
});
