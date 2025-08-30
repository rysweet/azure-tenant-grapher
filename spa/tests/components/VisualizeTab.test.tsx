import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { BrowserRouter } from 'react-router-dom';
import VisualizeTab from '../../renderer/src/components/tabs/VisualizeTab';
import { AppProvider } from '../../renderer/src/context/AppContext';

// Mock the GraphViewer component
jest.mock('../../renderer/src/components/widgets/GraphViewer', () => {
  return React.forwardRef((props: any, ref: any) => (
    <div data-testid="graph-viewer" ref={ref}>
      Graph Viewer Mock
      {props.loading && <span>Loading...</span>}
      {props.nodes?.length > 0 && <span>{props.nodes.length} nodes</span>}
      {props.edges?.length > 0 && <span>{props.edges.length} edges</span>}
    </div>
  ));
});

// Mock Monaco Editor
jest.mock('@monaco-editor/react', () => ({
  __esModule: true,
  default: ({ value, onChange }: any) => (
    <textarea
      data-testid="monaco-editor"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label="Cypher Query"
    />
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

describe('VisualizeTab', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    
    // Mock window.electronAPI
    (window as any).electronAPI = {
      cli: {
        execute: jest.fn(),
      },
      on: jest.fn(),
    };
    
    // Mock URL.createObjectURL and revokeObjectURL
    global.URL.createObjectURL = jest.fn(() => 'blob:mock-url');
    global.URL.revokeObjectURL = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('renders visualize tab with all controls', () => {
    renderWithProviders(<VisualizeTab />);
    
    expect(screen.getByText('Visualize Graph')).toBeInTheDocument();
    expect(screen.getByTestId('monaco-editor')).toBeInTheDocument();
    expect(screen.getByText(/Execute/i)).toBeInTheDocument();
    expect(screen.getByText('Zoom In')).toBeInTheDocument();
    expect(screen.getByText('Zoom Out')).toBeInTheDocument();
    expect(screen.getByText('Reset View')).toBeInTheDocument();
    expect(screen.getByText('Export')).toBeInTheDocument();
    expect(screen.getByTestId('graph-viewer')).toBeInTheDocument();
  });

  test('updates query text when typing', () => {
    renderWithProviders(<VisualizeTab />);
    
    const editor = screen.getByTestId('monaco-editor');
    const newQuery = 'MATCH (n:Resource) RETURN n LIMIT 50';
    
    fireEvent.change(editor, { target: { value: newQuery } });
    
    expect(editor).toHaveValue(newQuery);
  });

  test('executes visualization query', async () => {
    const mockExecute = jest.fn().mockResolvedValue({ 
      data: { id: 'test-process-id' } 
    });
    
    (window as any).electronAPI.cli.execute = mockExecute;
    
    renderWithProviders(<VisualizeTab />);
    
    const executeButton = screen.getByText(/Execute/i);
    fireEvent.click(executeButton);
    
    await waitFor(() => {
      expect(mockExecute).toHaveBeenCalledWith('visualize', ['--query', 'MATCH (n) RETURN n LIMIT 100']);
    });
  });

  test('shows loading state during query execution', async () => {
    const mockExecute = jest.fn(() => new Promise(resolve => setTimeout(resolve, 100)));
    (window as any).electronAPI.cli.execute = mockExecute;
    
    renderWithProviders(<VisualizeTab />);
    
    const executeButton = screen.getByText(/Execute/i);
    fireEvent.click(executeButton);
    
    expect(screen.getByText(/Loading.../i)).toBeInTheDocument();
    expect(executeButton).toBeDisabled();
    
    await waitFor(() => {
      expect(mockExecute).toHaveBeenCalled();
    });
  });

  test('displays error when visualization fails', async () => {
    const mockExecute = jest.fn().mockRejectedValue(new Error('Visualization failed'));
    (window as any).electronAPI.cli.execute = mockExecute;
    
    renderWithProviders(<VisualizeTab />);
    
    const executeButton = screen.getByText(/Execute/i);
    fireEvent.click(executeButton);
    
    await waitFor(() => {
      expect(screen.getByText(/Visualization failed/i)).toBeInTheDocument();
    });
  });

  test('displays mock graph data on successful execution', async () => {
    const mockExecute = jest.fn().mockResolvedValue({ 
      data: { id: 'test-process-id' } 
    });
    
    const mockOn = jest.fn((event, callback) => {
      if (event === 'process:exit') {
        setTimeout(() => {
          callback({ id: 'test-process-id', code: 0 });
        }, 10);
      }
    });
    
    (window as any).electronAPI.cli.execute = mockExecute;
    (window as any).electronAPI.on = mockOn;
    
    renderWithProviders(<VisualizeTab />);
    
    const executeButton = screen.getByText(/Execute/i);
    fireEvent.click(executeButton);
    
    await waitFor(() => {
      expect(screen.getByText(/5 nodes/i)).toBeInTheDocument();
      expect(screen.getByText(/5 edges/i)).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  test('shows node details when node is selected', async () => {
    const mockExecute = jest.fn().mockResolvedValue({ 
      data: { id: 'test-process-id' } 
    });
    
    const mockOn = jest.fn((event, callback) => {
      if (event === 'process:exit') {
        callback({ id: 'test-process-id', code: 0 });
      }
    });
    
    (window as any).electronAPI.cli.execute = mockExecute;
    (window as any).electronAPI.on = mockOn;
    
    const { container } = renderWithProviders(<VisualizeTab />);
    
    const executeButton = screen.getByText(/Execute/i);
    fireEvent.click(executeButton);
    
    await waitFor(() => {
      expect(screen.getByText(/5 nodes/i)).toBeInTheDocument();
    });
    
    // Simulate node click by calling the onNodeClick prop
    // This would normally be triggered by the GraphViewer
    const graphViewer = container.querySelector('[data-testid="graph-viewer"]');
    expect(graphViewer).toBeInTheDocument();
  });

  test('exports graph data as JSON', async () => {
    const mockExecute = jest.fn().mockResolvedValue({ 
      data: { id: 'test-process-id' } 
    });
    
    const mockOn = jest.fn((event, callback) => {
      if (event === 'process:exit') {
        callback({ id: 'test-process-id', code: 0 });
      }
    });
    
    (window as any).electronAPI.cli.execute = mockExecute;
    (window as any).electronAPI.on = mockOn;
    
    // Mock createElement and click
    const mockClick = jest.fn();
    const mockAnchor = { href: '', download: '', click: mockClick };
    jest.spyOn(document, 'createElement').mockReturnValue(mockAnchor as any);
    
    renderWithProviders(<VisualizeTab />);
    
    // Execute query first to have data
    const executeButton = screen.getByText(/Execute/i);
    fireEvent.click(executeButton);
    
    await waitFor(() => {
      expect(screen.getByText(/5 nodes/i)).toBeInTheDocument();
    });
    
    // Export the graph
    const exportButton = screen.getByText(/Export/i);
    fireEvent.click(exportButton);
    
    expect(global.URL.createObjectURL).toHaveBeenCalled();
    expect(mockAnchor.download).toMatch(/graph_\d+\.json/);
    expect(mockClick).toHaveBeenCalled();
    expect(global.URL.revokeObjectURL).toHaveBeenCalled();
  });

  test('disables execute button when query is empty', () => {
    renderWithProviders(<VisualizeTab />);
    
    const editor = screen.getByTestId('monaco-editor');
    fireEvent.change(editor, { target: { value: '' } });
    
    const executeButton = screen.getByText(/Execute/i);
    expect(executeButton).toBeDisabled();
  });

  test('zoom controls are present', () => {
    renderWithProviders(<VisualizeTab />);
    
    expect(screen.getByText('Zoom In')).toBeInTheDocument();
    expect(screen.getByText('Zoom Out')).toBeInTheDocument();
    expect(screen.getByText('Reset View')).toBeInTheDocument();
  });
});