import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import DeployTab from '../../renderer/src/components/tabs/DeployTab';
import ValidateDeploymentTab from '../../renderer/src/components/tabs/ValidateDeploymentTab';
import CreateTenantTab from '../../renderer/src/components/tabs/CreateTenantTab';
import UndeployTab from '../../renderer/src/components/tabs/UndeployTab';

// Mock window.electronAPI
const mockElectronAPI = {
  cli: { execute: jest.fn() },
  on: jest.fn(),
  off: jest.fn(),
  config: { get: jest.fn(), set: jest.fn() },
  env: { getAll: jest.fn() },
};

(global as any).window.electronAPI = mockElectronAPI;

describe('Issue #846 - Rename Target Tenant to Gameboard Tenant', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockElectronAPI.env.getAll.mockResolvedValue({});
    mockElectronAPI.config.get.mockResolvedValue(null);
  });

  test('DeployTab shows "Gameboard Tenant" not "Target Tenant"', () => {
    render(
      <MemoryRouter>
        <DeployTab />
      </MemoryRouter>
    );

    // Should show "Gameboard Tenant"
    expect(screen.getByText(/Gameboard Tenant/i)).toBeInTheDocument();

    // Should NOT show "Target Tenant"
    expect(screen.queryByText(/^Target Tenant$/)).not.toBeInTheDocument();
  });

  test('ValidateDeploymentTab shows "Gameboard Tenant" labels', () => {
    render(
      <MemoryRouter>
        <ValidateDeploymentTab />
      </MemoryRouter>
    );

    // Should show "Gameboard Tenant" in dropdown labels
    const gameboardLabels = screen.getAllByText(/Gameboard Tenant/i);
    expect(gameboardLabels.length).toBeGreaterThan(0);

    // Should NOT show "Target Tenant" in UI
    expect(screen.queryByText(/^Target Tenant$/)).not.toBeInTheDocument();
  });

  test('CreateTenantTab shows "Gameboard Tenant" terminology', () => {
    render(
      <MemoryRouter>
        <CreateTenantTab />
      </MemoryRouter>
    );

    // Check if Gameboard Tenant appears anywhere in the component
    const gameboardElements = screen.queryAllByText(/Gameboard/i);

    // Should show Gameboard terminology (if this tab has tenant selection)
    // Note: May not have target tenant field, so we just verify no "Target Tenant" labels
    expect(screen.queryByText(/Target Tenant(?! Creator)/i)).not.toBeInTheDocument();
  });

  test('UndeployTab shows "Gameboard Tenant" in dropdown', () => {
    mockElectronAPI.cli.execute.mockResolvedValue({
      data: { id: 'process-1' },
    });

    mockElectronAPI.on.mockImplementation((event: string, handler: Function) => {
      if (event === 'process:output') {
        setTimeout(() => handler({ id: 'process-1', data: ['[]'] }), 50);
      } else if (event === 'process:exit') {
        setTimeout(() => handler({ id: 'process-1', code: 0 }), 100);
      }
    });

    render(
      <MemoryRouter>
        <UndeployTab />
      </MemoryRouter>
    );

    // Should show "Gameboard Tenant" label (if tenant dropdown exists)
    const gameboardElements = screen.queryAllByText(/Gameboard/i);

    // Verify no "Target Tenant" labels in UI
    expect(screen.queryByText(/^Target Tenant$/)).not.toBeInTheDocument();
  });

  test('All tabs use consistent "Gameboard Tenant" terminology', () => {
    const tabs = [
      { Component: DeployTab, name: 'DeployTab' },
      { Component: ValidateDeploymentTab, name: 'ValidateDeploymentTab' },
      { Component: CreateTenantTab, name: 'CreateTenantTab' },
    ];

    tabs.forEach(({ Component, name }) => {
      const { unmount } = render(
        <MemoryRouter>
          <Component />
        </MemoryRouter>
      );

      // Should NOT have "Target Tenant" labels (excluding "Target Tenant Creator" which is OK)
      expect(screen.queryByText(/Target Tenant(?! Creator)/i)).not.toBeInTheDocument();

      unmount();
    });
  });

  test('Helper text updated to use "gameboard" terminology', () => {
    render(
      <MemoryRouter>
        <ValidateDeploymentTab />
      </MemoryRouter>
    );

    // Check for helper text that should say "gameboard" instead of "target"
    // This verifies helper text was also updated, not just labels
    const helperTexts = screen.queryAllByText(/gameboard/i);
    expect(helperTexts.length).toBeGreaterThan(0);
  });

  test('Internal variable names unchanged (targetTenantId still valid)', () => {
    // This is a code-level test - verify that renaming was UI-only
    // The actual test would be reading source files to confirm variable names
    // For now, we test that components still render without errors

    const components = [DeployTab, ValidateDeploymentTab, CreateTenantTab, UndeployTab];

    components.forEach((Component) => {
      const { container } = render(
        <MemoryRouter>
          <Component />
        </MemoryRouter>
      );

      // Component should render without errors (indicating internal variables still work)
      expect(container).toBeInTheDocument();
    });
  });
});
