import React, { useEffect, useRef, useState } from 'react';
import { Network, DataSet, Options } from 'vis-network/standalone';
import { Box, Paper, Typography, CircularProgress } from '@mui/material';

interface GraphNode {
  id: string;
  label: string;
  group?: string;
  title?: string;
  properties?: Record<string, any>;
}

interface GraphEdge {
  from: string;
  to: string;
  label?: string;
  arrows?: string;
  color?: string;
}

interface GraphViewerProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onNodeClick?: (nodeId: string) => void;
  onEdgeClick?: (edgeId: string) => void;
  height?: number | string;
  loading?: boolean;
}

const GraphViewer: React.FC<GraphViewerProps> = ({
  nodes,
  edges,
  onNodeClick,
  onEdgeClick,
  height = 600,
  loading = false,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    if (!containerRef.current || loading || nodes.length === 0) return;

    // Create datasets
    const nodesDataSet = new DataSet(
      nodes.map(node => ({
        ...node,
        color: getNodeColor(node.group),
        shape: getNodeShape(node.group),
        font: { color: '#ffffff' },
      }))
    );

    const edgesDataSet = new DataSet(
      edges.map(edge => ({
        ...edge,
        arrows: edge.arrows || 'to',
        color: edge.color || { color: '#848484', highlight: '#0078d4' },
        smooth: { type: 'curvedCW', roundness: 0.2 },
      }))
    );

    // Network options
    const options: Options = {
      nodes: {
        borderWidth: 2,
        borderWidthSelected: 3,
        font: {
          size: 14,
          face: 'Segoe UI, Roboto, sans-serif',
        },
        chosen: {
          node: (values, id, selected, hovering) => {
            if (selected) {
              values.borderColor = '#0078d4';
              values.borderWidth = 3;
            }
          },
        },
      },
      edges: {
        width: 2,
        font: {
          size: 12,
          align: 'middle',
          color: '#969696',
        },
        smooth: {
          enabled: true,
          type: 'dynamic',
        },
      },
      physics: {
        enabled: true,
        barnesHut: {
          gravitationalConstant: -8000,
          springConstant: 0.04,
          springLength: 100,
          damping: 0.09,
        },
        stabilization: {
          enabled: true,
          iterations: 200,
          updateInterval: 10,
        },
      },
      interaction: {
        hover: true,
        tooltipDelay: 200,
        zoomView: true,
        dragView: true,
        navigationButtons: true,
        keyboard: {
          enabled: true,
        },
      },
      layout: {
        improvedLayout: true,
        hierarchical: {
          enabled: false,
          direction: 'UD',
          sortMethod: 'directed',
          nodeSpacing: 150,
          levelSeparation: 150,
        },
      },
    };

    // Create network
    const network = new Network(
      containerRef.current,
      { nodes: nodesDataSet, edges: edgesDataSet },
      options
    );

    networkRef.current = network;

    // Event handlers
    if (onNodeClick) {
      network.on('selectNode', (params) => {
        if (params.nodes.length > 0) {
          onNodeClick(params.nodes[0]);
        }
      });
    }

    if (onEdgeClick) {
      network.on('selectEdge', (params) => {
        if (params.edges.length > 0) {
          onEdgeClick(params.edges[0]);
        }
      });
    }

    // Stabilization complete
    network.on('stabilizationIterationsDone', () => {
      network.setOptions({ physics: false });
      setIsInitialized(true);
    });

    // Cleanup
    return () => {
      network.destroy();
      networkRef.current = null;
    };
  }, [nodes, edges, onNodeClick, onEdgeClick, loading]);

  // Helper functions for node styling
  const getNodeColor = (group?: string): string => {
    const colors: Record<string, string> = {
      subscription: '#0078d4',
      resourceGroup: '#40a9ff',
      virtualMachine: '#52c41a',
      storageAccount: '#faad14',
      networkInterface: '#722ed1',
      virtualNetwork: '#13c2c2',
      user: '#f5222d',
      servicePrincipal: '#fa541c',
      default: '#8c8c8c',
    };
    return colors[group || 'default'] || colors.default;
  };

  const getNodeShape = (group?: string): string => {
    const shapes: Record<string, string> = {
      subscription: 'box',
      resourceGroup: 'ellipse',
      virtualMachine: 'square',
      storageAccount: 'database',
      networkInterface: 'diamond',
      virtualNetwork: 'star',
      user: 'dot',
      servicePrincipal: 'triangle',
      default: 'dot',
    };
    return shapes[group || 'default'] || shapes.default;
  };

  // Graph manipulation methods
  const fitNetwork = () => {
    networkRef.current?.fit({
      animation: {
        duration: 1000,
        easingFunction: 'easeInOutQuad',
      },
    });
  };

  const centerNode = (nodeId: string) => {
    networkRef.current?.focus(nodeId, {
      scale: 1.5,
      animation: {
        duration: 1000,
        easingFunction: 'easeInOutQuad',
      },
    });
  };

  const getConnectedNodes = (nodeId: string): string[] => {
    return networkRef.current?.getConnectedNodes(nodeId) as string[] || [];
  };

  const highlightPath = (nodeIds: string[]) => {
    if (!networkRef.current) return;

    networkRef.current.selectNodes(nodeIds, false);
    networkRef.current.focus(nodeIds[0], {
      scale: 1,
      animation: true,
    });
  };

  // Expose methods and network instance via ref
  React.useImperativeHandle(
    React.forwardRef((props, ref) => ref),
    () => ({
      fitNetwork,
      centerNode,
      getConnectedNodes,
      highlightPath,
      network: networkRef.current,
    }),
    [networkRef.current]
  );

  if (loading) {
    return (
      <Paper sx={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Box sx={{ textAlign: 'center' }}>
          <CircularProgress />
          <Typography variant="body2" sx={{ mt: 2 }}>
            Loading graph visualization...
          </Typography>
        </Box>
      </Paper>
    );
  }

  if (nodes.length === 0) {
    return (
      <Paper sx={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Typography variant="body2" color="text.secondary">
          No graph data available. Execute a query to visualize the graph.
        </Typography>
      </Paper>
    );
  }

  return (
    <Paper sx={{ height, position: 'relative', overflow: 'hidden' }}>
      <div
        ref={containerRef}
        role="img"
        aria-label={`Interactive graph visualization with ${nodes.length} nodes and ${edges.length} edges`}
        tabIndex={0}
        style={{
          width: '100%',
          height: '100%',
          backgroundColor: '#1e1e1e',
        }}
      />
      {!isInitialized && (
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
          }}
        >
          <CircularProgress />
        </Box>
      )}
    </Paper>
  );
};

export default GraphViewer;
