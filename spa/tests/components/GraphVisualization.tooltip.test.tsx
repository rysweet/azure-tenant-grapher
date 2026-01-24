/**
 * Comprehensive tooltip tests for GraphVisualization component
 *
 * Testing Philosophy: 60% unit, 30% integration, 10% E2E
 * Focus: Tooltip rendering, DOM element creation, inline styles, overflow prevention
 *
 * What Was Fixed (Issue #685):
 * - Tooltips now use DOM elements instead of HTML strings (htmlTitle helper)
 * - All tooltip content uses inline styles for proper rendering
 * - Tooltips display node name, type, properties (resourceGroup, location, etc.)
 * - Edge tooltips show type and description
 * - Overflow prevention with 400px width constraint
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { BrowserRouter } from 'react-router-dom';
import { GraphVisualization } from '../../renderer/src/components/graph/GraphVisualization';
import { AppProvider } from '../../renderer/src/context/AppContext';
import axios from 'axios';

// Mock axios
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

// Mock vis-network
jest.mock('vis-network/standalone', () => {
  return {
    Network: jest.fn().mockImplementation((container, data, options) => {
      // Store the data for verification
      const mockNetwork = {
        container,
        data,
        options,
        on: jest.fn(),
        once: jest.fn(),
        destroy: jest.fn(),
        selectNodes: jest.fn(),
        unselectAll: jest.fn(),
        focus: jest.fn(),
        fit: jest.fn(),
        getScale: jest.fn(() => 1.0),
        getViewPosition: jest.fn(() => ({ x: 0, y: 0 })),
        moveTo: jest.fn(),
        setOptions: jest.fn(),
      };
      return mockNetwork;
    }),
    DataSet: jest.fn().mockImplementation((data) => data),
  };
});

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

// Mock graph data
const createMockGraphData = () => ({
  nodes: [
    {
      id: 'node-1',
      label: 'TestResource',
      type: 'VirtualMachines',
      properties: {
        resourceGroup: 'test-rg',
        location: 'eastus',
        subscriptionId: 'sub-123',
        sku: 'Standard_D2s_v3',
        status: 'Running',
        provisioningState: 'Succeeded',
      },
      synthetic: false,
    },
    {
      id: 'node-2',
      label: 'SyntheticNode',
      type: 'VirtualMachineScaleSets',
      properties: {
        resourceGroup: 'synthetic-rg',
        location: 'westus',
      },
      synthetic: true,
    },
    {
      id: 'node-3',
      label: 'MinimalNode',
      type: 'StorageAccounts',
      properties: {},
      synthetic: false,
    },
  ],
  edges: [
    {
      id: 'edge-1',
      source: 'node-1',
      target: 'node-2',
      type: 'CONTAINS',
      properties: {},
    },
    {
      id: 'edge-2',
      source: 'node-2',
      target: 'node-3',
      type: 'DEPENDS_ON',
      properties: {},
    },
  ],
  stats: {
    nodeCount: 3,
    edgeCount: 2,
    nodeTypes: {
      VirtualMachines: 1,
      VirtualMachineScaleSets: 1,
      StorageAccounts: 1,
    },
    edgeTypes: {
      CONTAINS: 1,
      DEPENDS_ON: 1,
    },
  },
});

describe('GraphVisualization - Tooltip Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedAxios.get.mockResolvedValue({ data: createMockGraphData() });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  // ============================================================
  // UNIT TESTS (60% - Fast, heavily focused on individual pieces)
  // ============================================================

  describe('Unit Tests - htmlTitle() DOM Element Creation', () => {
    test('htmlTitle converts HTML string to DOM element', async () => {
      renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalledWith('http://localhost:3001/api/graph');
      });

      // Verify Network was called with transformed nodes
      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { nodes } = networkCall[1];

      // Verify first node has title as DOM element
      const node = nodes[0];
      expect(node.title).toBeDefined();
      expect(node.title).toBeInstanceOf(HTMLElement);
      expect(node.title.tagName).toBe('DIV');
    });

    test('htmlTitle creates container with correct inline styles', async () => {
      renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { nodes } = networkCall[1];
      const tooltipElement = nodes[0].title as HTMLElement;

      // Verify aggressive overflow prevention styles
      expect(tooltipElement.style.width).toBe('400px');
      expect(tooltipElement.style.maxWidth).toBe('400px');
      expect(tooltipElement.style.wordBreak).toBe('break-all');
      expect(tooltipElement.style.overflowWrap).toBe('break-word');
      expect(tooltipElement.style.padding).toBe('8px');
      expect(tooltipElement.style.boxSizing).toBe('border-box');
      expect(tooltipElement.style.overflow).toBe('hidden');
      expect(tooltipElement.style.whiteSpace).toBe('normal');
    });

    test('tooltip content includes node label as title', async () => {
      renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { nodes } = networkCall[1];
      const tooltipElement = nodes[0].title as HTMLElement;

      // Verify tooltip contains node label
      expect(tooltipElement.innerHTML).toContain('TestResource');
    });

    test('tooltip content includes node type', async () => {
      renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { nodes } = networkCall[1];
      const tooltipElement = nodes[0].title as HTMLElement;

      expect(tooltipElement.innerHTML).toContain('Type:');
      expect(tooltipElement.innerHTML).toContain('VirtualMachines');
    });

    test('tooltip includes resourceGroup when present', async () => {
      renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { nodes } = networkCall[1];
      const tooltipElement = nodes[0].title as HTMLElement;

      expect(tooltipElement.innerHTML).toContain('Resource Group:');
      expect(tooltipElement.innerHTML).toContain('test-rg');
    });

    test('tooltip includes location when present', async () => {
      renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { nodes } = networkCall[1];
      const tooltipElement = nodes[0].title as HTMLElement;

      expect(tooltipElement.innerHTML).toContain('Location:');
      expect(tooltipElement.innerHTML).toContain('eastus');
    });

    test('tooltip includes subscriptionId when present', async () => {
      renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { nodes } = networkCall[1];
      const tooltipElement = nodes[0].title as HTMLElement;

      expect(tooltipElement.innerHTML).toContain('Subscription:');
      expect(tooltipElement.innerHTML).toContain('sub-123');
    });

    test('tooltip includes sku when present', async () => {
      renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { nodes } = networkCall[1];
      const tooltipElement = nodes[0].title as HTMLElement;

      expect(tooltipElement.innerHTML).toContain('SKU:');
      expect(tooltipElement.innerHTML).toContain('Standard_D2s_v3');
    });

    test('tooltip includes status when present', async () => {
      renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { nodes } = networkCall[1];
      const tooltipElement = nodes[0].title as HTMLElement;

      expect(tooltipElement.innerHTML).toContain('Status:');
      expect(tooltipElement.innerHTML).toContain('Running');
    });

    test('tooltip includes provisioningState when present', async () => {
      renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { nodes } = networkCall[1];
      const tooltipElement = nodes[0].title as HTMLElement;

      expect(tooltipElement.innerHTML).toContain('State:');
      expect(tooltipElement.innerHTML).toContain('Succeeded');
    });

    test('tooltip excludes properties when undefined', async () => {
      renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { nodes } = networkCall[1];
      const minimalNodeTooltip = nodes[2].title as HTMLElement;

      // Minimal node should not have resourceGroup, location, etc.
      expect(minimalNodeTooltip.innerHTML).not.toContain('Resource Group:');
      expect(minimalNodeTooltip.innerHTML).not.toContain('Location:');
      expect(minimalNodeTooltip.innerHTML).not.toContain('Subscription:');
    });

    test('synthetic node marker appears for synthetic nodes', async () => {
      renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { nodes } = networkCall[1];
      const syntheticNodeTooltip = nodes[1].title as HTMLElement;

      expect(syntheticNodeTooltip.innerHTML).toContain('🔶 SYNTHETIC NODE');
      expect(syntheticNodeTooltip.innerHTML).toContain('#FFA500');
    });

    test('synthetic node marker absent for non-synthetic nodes', async () => {
      renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { nodes } = networkCall[1];
      const normalNodeTooltip = nodes[0].title as HTMLElement;

      expect(normalNodeTooltip.innerHTML).not.toContain('SYNTHETIC NODE');
    });

    test('tooltip contains "Click for more details" hint', async () => {
      renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { nodes } = networkCall[1];
      const tooltipElement = nodes[0].title as HTMLElement;

      expect(tooltipElement.innerHTML).toContain('Click for more details');
    });
  });

  describe('Unit Tests - Edge Tooltips', () => {
    test('edge tooltip includes type', async () => {
      renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { edges } = networkCall[1];
      const edgeTooltip = edges[0].title as HTMLElement;

      expect(edgeTooltip.innerHTML).toContain('CONTAINS');
    });

    test('edge tooltip includes description', async () => {
      renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { edges } = networkCall[1];
      const edgeTooltip = edges[0].title as HTMLElement;

      expect(edgeTooltip.innerHTML).toContain('Hierarchical containment relationship');
    });

    test('edge tooltip is a DOM element', async () => {
      renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { edges } = networkCall[1];
      const edgeTooltip = edges[0].title;

      expect(edgeTooltip).toBeInstanceOf(HTMLElement);
      expect(edgeTooltip.tagName).toBe('DIV');
    });
  });

  describe('Unit Tests - Inline Styles', () => {
    test('title element has green color inline style', async () => {
      renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { nodes } = networkCall[1];
      const tooltipElement = nodes[0].title as HTMLElement;

      // Check for title style in innerHTML
      expect(tooltipElement.innerHTML).toContain('color: #4caf50');
    });

    test('row elements have white color inline style', async () => {
      renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { nodes } = networkCall[1];
      const tooltipElement = nodes[0].title as HTMLElement;

      // Check for row style
      expect(tooltipElement.innerHTML).toContain('color: #ffffff');
    });

    test('strong elements have green color inline style', async () => {
      renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { nodes } = networkCall[1];
      const tooltipElement = nodes[0].title as HTMLElement;

      // Check for strong style
      expect(tooltipElement.innerHTML).toContain('color: #4caf50');
    });

    test('hint element has gray color inline style', async () => {
      renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { nodes } = networkCall[1];
      const tooltipElement = nodes[0].title as HTMLElement;

      // Check for hint style
      expect(tooltipElement.innerHTML).toContain('color: #888');
      expect(tooltipElement.innerHTML).toContain('font-style: italic');
    });
  });

  // ============================================================
  // INTEGRATION TESTS (30% - Multiple components working together)
  // ============================================================

  describe('Integration Tests - Full Tooltip Rendering Workflow', () => {
    test('complete node tooltip rendering flow: data → HTML → DOM → vis-network', async () => {
      renderWithProviders(<GraphVisualization />);

      // 1. Data fetch
      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalledWith('http://localhost:3001/api/graph');
      });

      // 2. Network creation with transformed data
      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { nodes } = networkCall[1];

      // 3. Verify complete tooltip structure
      const node = nodes[0];
      expect(node.id).toBe('node-1');
      expect(node.label).toBe('TestResource');
      expect(node.title).toBeInstanceOf(HTMLElement);

      const tooltip = node.title as HTMLElement;
      expect(tooltip.innerHTML).toContain('TestResource');
      expect(tooltip.innerHTML).toContain('VirtualMachines');
      expect(tooltip.innerHTML).toContain('test-rg');
      expect(tooltip.innerHTML).toContain('eastus');
      expect(tooltip.innerHTML).toContain('sub-123');
    });

    test('tooltip updates when node properties change', async () => {
      const initialData = createMockGraphData();
      mockedAxios.get.mockResolvedValueOnce({ data: initialData });

      const { rerender } = renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      // Update data
      const updatedData = createMockGraphData();
      updatedData.nodes[0].properties.location = 'westus2';
      mockedAxios.get.mockResolvedValueOnce({ data: updatedData });

      // Trigger re-render by changing component
      rerender(
        <BrowserRouter>
          <AppProvider>
            <GraphVisualization />
          </AppProvider>
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalledTimes(2);
      });

      const { Network } = require('vis-network/standalone');
      const latestCall = Network.mock.calls[Network.mock.calls.length - 1];
      const { nodes } = latestCall[1];
      const tooltip = nodes[0].title as HTMLElement;

      expect(tooltip.innerHTML).toContain('westus2');
    });

    test('multiple node types display correct tooltips', async () => {
      renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { nodes } = networkCall[1];

      // Check VirtualMachines node
      const vmNode = nodes[0].title as HTMLElement;
      expect(vmNode.innerHTML).toContain('VirtualMachines');

      // Check VirtualMachineScaleSets node
      const vmssNode = nodes[1].title as HTMLElement;
      expect(vmssNode.innerHTML).toContain('VirtualMachineScaleSets');

      // Check StorageAccounts node
      const storageNode = nodes[2].title as HTMLElement;
      expect(storageNode.innerHTML).toContain('StorageAccounts');
    });

    test('tooltip overflow prevention works with long strings', async () => {
      const longStringData = createMockGraphData();
      longStringData.nodes[0].label = 'VeryLongResourceNameThatCouldPotentiallyCauseOverflowIssuesInTheTooltipDisplay';  // pragma: allowlist secret
      longStringData.nodes[0].properties.resourceGroup = 'VeryLongResourceGroupNameThatExceedsNormalLengthConstraints';

      mockedAxios.get.mockResolvedValueOnce({ data: longStringData });

      renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { nodes } = networkCall[1];
      const tooltip = nodes[0].title as HTMLElement;

      // Verify overflow prevention styles are applied
      expect(tooltip.style.maxWidth).toBe('400px');
      expect(tooltip.style.wordBreak).toBe('break-all');
      expect(tooltip.style.overflowWrap).toBe('break-word');
      expect(tooltip.style.overflow).toBe('hidden');

      // Verify long content is present
      expect(tooltip.innerHTML).toContain('VeryLongResourceNameThatCouldPotentiallyCauseOverflowIssuesInTheTooltipDisplay');
    });
  });

  describe('Integration Tests - Edge Type Tooltips', () => {
    test('different edge types display correct descriptions', async () => {
      renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { edges } = networkCall[1];

      // CONTAINS edge
      const containsEdge = edges[0].title as HTMLElement;
      expect(containsEdge.innerHTML).toContain('CONTAINS');
      expect(containsEdge.innerHTML).toContain('Hierarchical containment relationship');

      // DEPENDS_ON edge
      const dependsEdge = edges[1].title as HTMLElement;
      expect(dependsEdge.innerHTML).toContain('DEPENDS_ON');
      expect(dependsEdge.innerHTML).toContain('Has a dependency on another resource');
    });
  });

  // ============================================================
  // E2E TESTS (10% - Complete user workflows)
  // ============================================================

  describe('E2E Tests - User Tooltip Interaction', () => {
    test('user hovers over node and sees complete tooltip', async () => {
      renderWithProviders(<GraphVisualization />);

      // User loads page
      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalledWith('http://localhost:3001/api/graph');
      });

      // Graph renders with network
      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      // User hovers over node (simulated by checking tooltip content)
      const networkCall = Network.mock.calls[0];
      const { nodes } = networkCall[1];
      const firstNode = nodes[0];

      // Verify tooltip is ready for hover
      expect(firstNode.title).toBeInstanceOf(HTMLElement);
      const tooltip = firstNode.title as HTMLElement;

      // User sees all expected information
      expect(tooltip.innerHTML).toContain('TestResource');
      expect(tooltip.innerHTML).toContain('Type:');
      expect(tooltip.innerHTML).toContain('VirtualMachines');
      expect(tooltip.innerHTML).toContain('Resource Group:');
      expect(tooltip.innerHTML).toContain('test-rg');
      expect(tooltip.innerHTML).toContain('Location:');
      expect(tooltip.innerHTML).toContain('eastus');
      expect(tooltip.innerHTML).toContain('Subscription:');
      expect(tooltip.innerHTML).toContain('sub-123');
      expect(tooltip.innerHTML).toContain('SKU:');
      expect(tooltip.innerHTML).toContain('Standard_D2s_v3');
      expect(tooltip.innerHTML).toContain('Status:');
      expect(tooltip.innerHTML).toContain('Running');
      expect(tooltip.innerHTML).toContain('Click for more details');
    });

    test('user hovers over edge and sees type + description', async () => {
      renderWithProviders(<GraphVisualization />);

      // User loads page
      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalledWith('http://localhost:3001/api/graph');
      });

      // Graph renders
      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      // User hovers over edge
      const networkCall = Network.mock.calls[0];
      const { edges } = networkCall[1];
      const firstEdge = edges[0];

      expect(firstEdge.title).toBeInstanceOf(HTMLElement);
      const tooltip = firstEdge.title as HTMLElement;

      // User sees edge information
      expect(tooltip.innerHTML).toContain('CONTAINS');
      expect(tooltip.innerHTML).toContain('Hierarchical containment relationship');
    });

    test('user hovers over synthetic node and sees special marker', async () => {
      renderWithProviders(<GraphVisualization />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      const { Network } = require('vis-network/standalone');
      await waitFor(() => {
        expect(Network).toHaveBeenCalled();
      });

      const networkCall = Network.mock.calls[0];
      const { nodes } = networkCall[1];
      const syntheticNode = nodes[1];

      const tooltip = syntheticNode.title as HTMLElement;

      // User sees synthetic marker
      expect(tooltip.innerHTML).toContain('🔶 SYNTHETIC NODE');
      expect(tooltip.innerHTML).toContain('SyntheticNode');
    });
  });
});
