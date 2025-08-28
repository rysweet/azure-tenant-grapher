import neo4j, { Driver, Session } from 'neo4j-driver';

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties: Record<string, any>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  properties: Record<string, any>;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: {
    nodeCount: number;
    edgeCount: number;
    nodeTypes: Record<string, number>;
    edgeTypes: Record<string, number>;
  };
}

export class Neo4jService {
  private driver: Driver | null = null;

  constructor() {
    this.connect();
  }

  private connect() {
    const uri = process.env.NEO4J_URI || 'bolt://localhost:7687';
    const user = process.env.NEO4J_USER || 'neo4j';
    const password = process.env.NEO4J_PASSWORD || 'azure-grapher-2024';
    
    try {
      this.driver = neo4j.driver(uri, neo4j.auth.basic(user, password));
      console.log(`Connected to Neo4j at ${uri}`);
    } catch (error) {
      console.error('Failed to connect to Neo4j:', error);
    }
  }

  async getFullGraph(): Promise<GraphData> {
    if (!this.driver) {
      throw new Error('Neo4j connection not available');
    }

    const session = this.driver.session();
    
    try {
      // Query to get all nodes and relationships
      const result = await session.run(`
        MATCH (n)
        WITH collect(DISTINCT n) AS nodes
        OPTIONAL MATCH (a)-[r]->(b)
        WITH nodes, collect(DISTINCT r) AS relationships
        RETURN nodes, relationships
      `);

      const nodes: GraphNode[] = [];
      const edges: GraphEdge[] = [];
      const nodeTypes: Record<string, number> = {};
      const edgeTypes: Record<string, number> = {};

      if (result.records.length > 0) {
        const record = result.records[0];
        
        // Process nodes
        const rawNodes = record.get('nodes') || [];
        rawNodes.forEach((node: any) => {
          const labels = node.labels || [];
          const nodeType = labels[0] || 'Unknown';
          
          // Count node types
          nodeTypes[nodeType] = (nodeTypes[nodeType] || 0) + 1;
          
          // Get display name
          const props = node.properties || {};
          const displayName = props.name || 
                            props.displayName || 
                            props.id || 
                            node.elementId || 
                            'Unnamed';
          
          nodes.push({
            id: node.elementId || node.identity.toString(),
            label: displayName,
            type: nodeType,
            properties: props
          });
        });

        // Process relationships
        const rawRelationships = record.get('relationships') || [];
        rawRelationships.forEach((rel: any) => {
          const relType = rel.type || 'RELATED_TO';
          
          // Count edge types
          edgeTypes[relType] = (edgeTypes[relType] || 0) + 1;
          
          edges.push({
            id: rel.elementId || rel.identity.toString(),
            source: rel.startNodeElementId || rel.start.toString(),
            target: rel.endNodeElementId || rel.end.toString(),
            type: relType,
            properties: rel.properties || {}
          });
        });
      }

      return {
        nodes,
        edges,
        stats: {
          nodeCount: nodes.length,
          edgeCount: edges.length,
          nodeTypes,
          edgeTypes
        }
      };
    } finally {
      await session.close();
    }
  }

  async searchNodes(query: string): Promise<GraphNode[]> {
    if (!this.driver) {
      throw new Error('Neo4j connection not available');
    }

    const session = this.driver.session();
    
    try {
      const result = await session.run(`
        MATCH (n)
        WHERE n.name CONTAINS $query 
           OR n.displayName CONTAINS $query 
           OR n.id CONTAINS $query
        RETURN n
        LIMIT 100
      `, { query });

      return result.records.map(record => {
        const node = record.get('n');
        const labels = node.labels || [];
        const props = node.properties || {};
        const displayName = props.name || 
                          props.displayName || 
                          props.id || 
                          node.elementId || 
                          'Unnamed';
        
        return {
          id: node.elementId || node.identity.toString(),
          label: displayName,
          type: labels[0] || 'Unknown',
          properties: props
        };
      });
    } finally {
      await session.close();
    }
  }

  async getNodeDetails(nodeId: string): Promise<any> {
    if (!this.driver) {
      throw new Error('Neo4j connection not available');
    }

    const session = this.driver.session();
    
    try {
      const result = await session.run(`
        MATCH (n)
        WHERE elementId(n) = $nodeId OR id(n) = $nodeId
        OPTIONAL MATCH (n)-[r]-(connected)
        RETURN n, 
               collect(DISTINCT {
                 relationship: type(r),
                 direction: CASE WHEN startNode(r) = n THEN 'outgoing' ELSE 'incoming' END,
                 connectedNode: {
                   id: elementId(connected),
                   label: connected.name,
                   type: labels(connected)[0]
                 }
               }) AS connections
      `, { nodeId });

      if (result.records.length > 0) {
        const record = result.records[0];
        const node = record.get('n');
        const connections = record.get('connections');
        
        return {
          id: node.elementId || node.identity.toString(),
          labels: node.labels,
          properties: node.properties,
          connections: connections.filter((c: any) => c.connectedNode !== null)
        };
      }
      
      return null;
    } finally {
      await session.close();
    }
  }

  async getDatabaseStats(): Promise<any> {
    if (!this.driver) {
      throw new Error('Neo4j connection not available');
    }

    const session = this.driver.session();
    
    try {
      // Get node and edge counts by type
      const statsQuery = `
        MATCH (n)
        WITH labels(n) as nodeLabels, n
        UNWIND nodeLabels as label
        WITH label, count(distinct n) as nodeCount
        WITH collect({type: label, count: nodeCount}) as nodeStats
        
        MATCH ()-[r]->()
        WITH nodeStats, type(r) as relType, count(r) as relCount
        WITH nodeStats, collect({type: relType, count: relCount}) as edgeStats
        
        MATCH (n)
        WITH nodeStats, edgeStats, count(n) as totalNodes
        
        OPTIONAL MATCH ()-[r]->()
        WITH nodeStats, edgeStats, totalNodes, count(r) as totalEdges
        
        // Get the most recent created/modified timestamp
        OPTIONAL MATCH (n)
        WHERE n.createdAt IS NOT NULL OR n.modifiedAt IS NOT NULL OR n.created IS NOT NULL OR n.modified IS NOT NULL
        WITH nodeStats, edgeStats, totalNodes, totalEdges, 
             max(coalesce(n.modifiedAt, n.modified, n.createdAt, n.created)) as lastUpdate
        
        RETURN {
          nodeCount: totalNodes,
          edgeCount: totalEdges,
          nodeTypes: nodeStats,
          edgeTypes: edgeStats,
          lastUpdate: lastUpdate,
          isEmpty: totalNodes = 0
        } as stats
      `;

      const result = await session.run(statsQuery);
      
      if (result.records.length > 0) {
        const stats = result.records[0].get('stats');
        
        // Get database size
        const sizeResult = await session.run(`
          CALL apoc.meta.stats() YIELD nodeCount, relCount, labelCount, relTypeCount
          RETURN nodeCount, relCount, labelCount, relTypeCount
        `).catch(() => null);
        
        if (sizeResult && sizeResult.records.length > 0) {
          const record = sizeResult.records[0];
          stats.labelCount = record.get('labelCount').toNumber();
          stats.relTypeCount = record.get('relTypeCount').toNumber();
        }
        
        return stats;
      }
      
      return {
        nodeCount: 0,
        edgeCount: 0,
        nodeTypes: [],
        edgeTypes: [],
        lastUpdate: null,
        isEmpty: true
      };
    } catch (error) {
      // If APOC is not installed, fall back to basic query
      try {
        const basicResult = await session.run(`
          MATCH (n)
          WITH count(n) as nodeCount
          OPTIONAL MATCH ()-[r]->()
          WITH nodeCount, count(r) as edgeCount
          RETURN nodeCount, edgeCount, nodeCount = 0 as isEmpty
        `);
        
        if (basicResult.records.length > 0) {
          const record = basicResult.records[0];
          return {
            nodeCount: record.get('nodeCount').toNumber(),
            edgeCount: record.get('edgeCount').toNumber(),
            isEmpty: record.get('isEmpty'),
            nodeTypes: [],
            edgeTypes: [],
            lastUpdate: null
          };
        }
      } catch (fallbackError) {
        console.error('Error getting DB stats:', fallbackError);
        throw fallbackError;
      }
    } finally {
      await session.close();
    }
  }

  async isDatabasePopulated(): Promise<boolean> {
    if (!this.driver) {
      return false;
    }

    const session = this.driver.session();
    
    try {
      const result = await session.run('MATCH (n) RETURN count(n) > 0 as hasData LIMIT 1');
      
      if (result.records.length > 0) {
        return result.records[0].get('hasData');
      }
      
      return false;
    } catch (error) {
      console.error('Error checking if database is populated:', error);
      return false;
    } finally {
      await session.close();
    }
  }

  async close() {
    if (this.driver) {
      await this.driver.close();
    }
  }
}