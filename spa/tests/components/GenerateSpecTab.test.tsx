import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { BrowserRouter } from 'react-router-dom';
import GenerateSpecTab from '../../renderer/src/components/tabs/GenerateSpecTab';
import { AppProvider } from '../../renderer/src/context/AppContext';

// Mock Monaco Editor
jest.mock('@monaco-editor/react', () => ({
  __esModule: true,
  default: ({ value, onChange, language }: any) => (
    <textarea
      data-testid={`monaco-editor-${language}`}
      value={value}
      onChange={(e) => onChange && onChange(e.target.value)}
      aria-label={`${language} editor`}
      readOnly={!onChange}
    />
  ),
}));

// Mock the LogViewer component
jest.mock('../../renderer/src/components/widgets/LogViewer', () => ({
  __esModule: true,
  default: ({ logs, onClear }: any) => (
    <div data-testid="log-viewer">
      Log Viewer
      {logs && logs.length > 0 && <span>{logs.length} logs</span>}
      <button onClick={onClear}>Clear Logs</button>
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

describe('GenerateSpecTab', () => {
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

  test('renders generate spec tab with all components', () => {
    renderWithProviders(<GenerateSpecTab />);
    
    expect(screen.getByText('Generate Specification')).toBeInTheDocument();
    expect(screen.getByText(/Generate Spec/i)).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /Include Resource Details/i })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /Include Relationships/i })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /Include IaC Templates/i })).toBeInTheDocument();
    expect(screen.getByTestId('monaco-editor-markdown')).toBeInTheDocument();
    expect(screen.getByTestId('log-viewer')).toBeInTheDocument();
  });

  test('toggles include options checkboxes', () => {
    renderWithProviders(<GenerateSpecTab />);
    
    const resourceDetailsCheckbox = screen.getByRole('checkbox', { name: /Include Resource Details/i });
    const relationshipsCheckbox = screen.getByRole('checkbox', { name: /Include Relationships/i });
    const iacTemplatesCheckbox = screen.getByRole('checkbox', { name: /Include IaC Templates/i });
    
    expect(resourceDetailsCheckbox).toBeChecked();
    expect(relationshipsCheckbox).toBeChecked();
    expect(iacTemplatesCheckbox).not.toBeChecked();
    
    fireEvent.click(resourceDetailsCheckbox);
    expect(resourceDetailsCheckbox).not.toBeChecked();
    
    fireEvent.click(iacTemplatesCheckbox);
    expect(iacTemplatesCheckbox).toBeChecked();
  });

  test('generates spec successfully', async () => {
    const mockOutput = '# Azure Tenant Specification\n\n## Resources\n- Resource 1\n- Resource 2';
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
    
    (window as any).electronAPI.cli.execute = mockExecute;
    (window as any).electronAPI.on = mockOn;
    
    renderWithProviders(<GenerateSpecTab />);
    
    const generateButton = screen.getByText(/Generate Spec/i);
    fireEvent.click(generateButton);
    
    await waitFor(() => {
      expect(mockExecute).toHaveBeenCalledWith(
        'generate-spec',
        expect.arrayContaining(['--include-details', '--include-relationships'])
      );
    });
    
    await waitFor(() => {
      const editor = screen.getByTestId('monaco-editor-markdown');
      expect(editor).toHaveValue(expect.stringContaining('Azure Tenant Specification'));
    });
  });

  test('shows loading state during generation', async () => {
    const mockExecute = jest.fn(() => new Promise(resolve => setTimeout(resolve, 100)));
    (window as any).electronAPI.cli.execute = mockExecute;
    
    renderWithProviders(<GenerateSpecTab />);
    
    const generateButton = screen.getByText(/Generate Spec/i);
    fireEvent.click(generateButton);
    
    expect(screen.getByText(/Generating.../i)).toBeInTheDocument();
    expect(generateButton).toBeDisabled();
    
    await waitFor(() => {
      expect(mockExecute).toHaveBeenCalled();
    });
  });

  test('displays error when generation fails', async () => {
    const mockExecute = jest.fn().mockRejectedValue(new Error('Generation failed'));
    (window as any).electronAPI.cli.execute = mockExecute;
    
    renderWithProviders(<GenerateSpecTab />);
    
    const generateButton = screen.getByText(/Generate Spec/i);
    fireEvent.click(generateButton);
    
    await waitFor(() => {
      expect(screen.getByText(/Generation failed/i)).toBeInTheDocument();
    });
  });

  test('exports specification to file', async () => {
    const mockSpec = '# Test Specification\n\nContent here';
    const mockExecute = jest.fn().mockResolvedValue({ 
      data: { id: 'test-process-id' } 
    });
    
    const mockOn = jest.fn((event, callback) => {
      if (event === 'process:output') {
        callback({ 
          id: 'test-process-id', 
          data: { type: 'stdout', data: mockSpec.split('\n') } 
        });
      } else if (event === 'process:exit') {
        callback({ id: 'test-process-id', code: 0 });
      }
    });
    
    (window as any).electronAPI.cli.execute = mockExecute;
    (window as any).electronAPI.on = mockOn;
    
    // Mock createElement and click
    const mockClick = jest.fn();
    const mockAnchor = { href: '', download: '', click: mockClick };
    jest.spyOn(document, 'createElement').mockReturnValue(mockAnchor as any);
    
    renderWithProviders(<GenerateSpecTab />);
    
    // Generate spec first
    const generateButton = screen.getByText(/Generate Spec/i);
    fireEvent.click(generateButton);
    
    await waitFor(() => {
      const editor = screen.getByTestId('monaco-editor-markdown');
      expect(editor).toHaveValue(expect.stringContaining('Test Specification'));
    });
    
    // Export the spec
    const exportButton = screen.getByText(/Export/i);
    fireEvent.click(exportButton);
    
    expect(global.URL.createObjectURL).toHaveBeenCalled();
    expect(mockAnchor.download).toMatch(/azure_spec_\d+\.md/);
    expect(mockClick).toHaveBeenCalled();
    expect(global.URL.revokeObjectURL).toHaveBeenCalled();
  });

  test('copies specification to clipboard', async () => {
    const mockSpec = '# Test Specification';
    const mockExecute = jest.fn().mockResolvedValue({ 
      data: { id: 'test-process-id' } 
    });
    
    const mockOn = jest.fn((event, callback) => {
      if (event === 'process:output') {
        callback({ 
          id: 'test-process-id', 
          data: { type: 'stdout', data: [mockSpec] } 
        });
      } else if (event === 'process:exit') {
        callback({ id: 'test-process-id', code: 0 });
      }
    });
    
    (window as any).electronAPI.cli.execute = mockExecute;
    (window as any).electronAPI.on = mockOn;
    
    // Mock clipboard API
    Object.assign(navigator, {
      clipboard: {
        writeText: jest.fn().mockResolvedValue(undefined),
      },
    });
    
    renderWithProviders(<GenerateSpecTab />);
    
    // Generate spec first
    const generateButton = screen.getByText(/Generate Spec/i);
    fireEvent.click(generateButton);
    
    await waitFor(() => {
      const editor = screen.getByTestId('monaco-editor-markdown');
      expect(editor).toHaveValue(mockSpec);
    });
    
    // Copy the spec
    const copyButton = screen.getByText(/Copy/i);
    fireEvent.click(copyButton);
    
    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(mockSpec);
    });
    
    expect(screen.getByText(/Copied!/i)).toBeInTheDocument();
  });

  test('clears logs when clear button is clicked', () => {
    renderWithProviders(<GenerateSpecTab />);
    
    const logViewer = screen.getByTestId('log-viewer');
    const clearButton = screen.getByText(/Clear Logs/i);
    
    expect(logViewer).toBeInTheDocument();
    fireEvent.click(clearButton);
    
    // Clear button should be in the log viewer
    expect(clearButton).toBeInTheDocument();
  });

  test('includes IaC templates when checkbox is selected', async () => {
    const mockExecute = jest.fn().mockResolvedValue({ 
      data: { id: 'test-process-id' } 
    });
    
    (window as any).electronAPI.cli.execute = mockExecute;
    
    renderWithProviders(<GenerateSpecTab />);
    
    const iacCheckbox = screen.getByRole('checkbox', { name: /Include IaC Templates/i });
    fireEvent.click(iacCheckbox);
    
    const generateButton = screen.getByText(/Generate Spec/i);
    fireEvent.click(generateButton);
    
    await waitFor(() => {
      expect(mockExecute).toHaveBeenCalledWith(
        'generate-spec',
        expect.arrayContaining(['--include-iac'])
      );
    });
  });

  test('disables export and copy buttons when no spec is generated', () => {
    renderWithProviders(<GenerateSpecTab />);
    
    const exportButton = screen.getByText(/Export/i);
    const copyButton = screen.getByText(/Copy/i);
    
    expect(exportButton).toBeDisabled();
    expect(copyButton).toBeDisabled();
  });
});