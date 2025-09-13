/**
 * SECURE VERSION OF NEO4J-SERVICE.TS
 * Implements secure credential management and query sanitization
 */

import neo4j, { Driver, Session, DateTime } from 'neo4j-driver';
import credentialManager from './security/credential-manager';
import { validateNodeId, validateSearchQuery } from './security/input-validator';

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties: Record<string, any>;
  resourceName?: string;
  azureId?: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  properties: Record<string, any>;
}

export interface TimestampInfo {
  timestamp: DateTime | string | null;
  utcString: string | null;
  localString: string | null;
  timezone: string;
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

export interface DatabaseStats {
  nodeCount: number;
  edgeCount: number;
  nodeTypes: Array<{ type: string; count: number }>;
  edgeTypes: Array<{ type: string; count: number }>;
  lastUpdate: TimestampInfo;
  isEmpty: boolean;
  labelCount?: number;
  relTypeCount?: number;
}

export class Neo4jService {
  private driver: Driver | null = null;
  private connectionAttempts = 0;
  private maxConnectionAttempts = 3;

  constructor() {
    this.connect();
  }

  private async connect() {
    try {
      // Get credentials securely from credential manager
      const { uri, user, password } = credentialManager.getNeo4jCredentials();
      
      // Validate credentials before use
      if (!credentialManager.validateCredential(password, 'password')) {
        throw new Error('Invalid Neo4j password format');
      }

      this.driver = neo4j.driver(uri, neo4j.auth.basic(user, password), {
        maxConnectionLifetime: 3 * 60 * 60 * 1000, // 3 hours
        maxConnectionPoolSize: 50,
        connectionAcquisitionTimeout: 2 * 60 * 1000, // 2 minutes
        logging: {
          level: 'warn',
          logger: (level, message) => {
            if (level === 'error' || level === 'warn') {
              console.log('[Neo4j]', level.toUpperCase(), ':', message);
            }
          }
        }
      });

      // Verify connectivity
      const session = this.driver.session();
      try {
        await session.run('RETURN 1');
        console.log('Connected to Neo4j at', credentialManager.maskCredential(uri));
      } finally {
        await session.close();
      }
    } catch (error) {
      this.connectionAttempts++;
      console.error('Failed to connect to Neo4j (attempt', this.connectionAttempts, '):', error);
      
      if (this.connectionAttempts < this.maxConnectionAttempts) {
        // Retry connection after delay
        setTimeout(() => this.connect(), 5000);
      } else {
        console.error('Max connection attempts reached. Neo4j service unavailable.');
      }
    }
  }

  async getFullGraph(): Promise<GraphData> {
    if (!this.driver) {
      throw new Error('Neo4j connection not available');
    }

    const session = this.driver.session({ defaultAccessMode: neo4j.session.READ });

    try {
      // Use parameterized query (even though no user input here)
      const result = await session.run(
        'MATCH (n) WITH collect(DISTINCT n) AS nodes OPTIONAL MATCH (a)-[r]->(b) WITH nodes, collect(DISTINCT r) AS relationships RETURN nodes, relationships',
        {},
        { timeout: 30000 } // 30 second timeout
      );

      const nodes: GraphNode[] = [];
      const edges: GraphEdge[] = [];
      const nodeTypes: Record<string, number> = {};
      const edgeTypes: Record<string, number> = {};

      if (result.records.length > 0) {
        const record = result.records[0];

        // Process nodes with sanitization
        const rawNodes = record.get('nodes') || [];
        rawNodes.forEach((node: any) => {
          const labels = node.labels || [];
          const props = this.sanitizeProperties(node.properties || {});

          let nodeType = labels[0] || 'Unknown';
          if (nodeType === 'Resource' && props.type) {
            const azureType = props.type;
            const typeParts = azureType.split('/');
            nodeType = typeParts.length > 1 ? typeParts[typeParts.length - 1] : azureType;
            nodeType = nodeType.charAt(0).toUpperCase() + nodeType.slice(1);
          }

          nodeTypes[nodeType] = (nodeTypes[nodeType] || 0) + 1;

          const displayName = props.name ||
                            props.displayName ||
                            props.id ||
                            node.elementId ||
                            'Unnamed';

          const graphNode: GraphNode = {
            id: node.elementId || node.identity.toString(),
            label: this.sanitizeString(displayName),
            type: nodeType,
            properties: props
          };

          if (nodeType === 'ResourceGroup' || labels.includes('ResourceGroup')) {
            graphNode.resourceName = props.name || displayName;
          }

          if (props.id && typeof props.id === 'string' && props.id.startsWith('/')) {
            graphNode.azureId = props.id;
          }

          nodes.push(graphNode);
        });

        // Process relationships
        const rawRelationships = record.get('relationships') || [];
        rawRelationships.forEach((rel: any) => {
          const relType = rel.type || 'RELATED_TO';
          edgeTypes[relType] = (edgeTypes[relType] || 0) + 1;

          edges.push({
            id: rel.elementId || rel.identity.toString(),
            source: rel.startNodeElementId || rel.start.toString(),
            target: rel.endNodeElementId || rel.end.toString(),
            type: relType,
            properties: this.sanitizeProperties(rel.properties || {})
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

    // Validate and sanitize query
    const validation = validateSearchQuery(query);
    if (!validation.valid || !validation.sanitized) {
      throw new Error(validation.error || 'Invalid search query');
    }

    const session = this.driver.session({ defaultAccessMode: neo4j.session.READ });

    try {
      // Use parameterized query to prevent Cypher injection
      const result = await session.run(
        `MATCH (n)
         WHERE n.name CONTAINS $query
            OR n.displayName CONTAINS $query
            OR n.id CONTAINS $query
         RETURN n
         LIMIT 100`,
        { query: validation.sanitized },
        { timeout: 10000 } // 10 second timeout
      );

      return result.records.map(record => {
        const node = record.get('n');
        const labels = node.labels || [];
        const props = this.sanitizeProperties(node.properties || {});

        let nodeType = labels[0] || 'Unknown';
        if (nodeType === 'Resource' && props.type) {
          const azureType = props.type;
          const typeParts = azureType.split('/');
          nodeType = typeParts.length > 1 ? typeParts[typeParts.length - 1] : azureType;
          nodeType = nodeType.charAt(0).toUpperCase() + nodeType.slice(1);
        }

        const displayName = props.name ||
                          props.displayName ||
                          props.id ||
                          node.elementId ||
                          'Unnamed';

        return {
          id: node.elementId || node.identity.toString(),
          label: this.sanitizeString(displayName),
          type: nodeType,
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

    // Validate node ID
    if (!validateNodeId(nodeId)) {
      throw new Error('Invalid node ID');
    }

    const session = this.driver.session({ defaultAccessMode: neo4j.session.READ });

    try {
      // Use parameterized query
      const result = await session.run(
        `MATCH (n)
         WHERE elementId(n) = $nodeId OR toString(id(n)) = $nodeId
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
                }) AS connections`,
        { nodeId },
        { timeout: 10000 }
      );

      if (result.records.length > 0) {
        const record = result.records[0];
        const node = record.get('n');
        const connections = record.get('connections');

        return {
          id: node.elementId || node.identity.toString(),
          labels: node.labels,
          properties: this.sanitizeProperties(node.properties),
          connections: connections.filter((c: any) => c.connectedNode !== null)
        };
      }

      return null;
    } finally {
      await session.close();
    }
  }

  private formatTimestamp(timestamp: any): TimestampInfo {
    if (!timestamp) {
      return {
        timestamp: null,
        utcString: null,
        localString: null,
        timezone: 'N/A'
      };
    }

    try {
      if (timestamp && typeof timestamp === 'object' && 'toString' in timestamp) {
        const utcString = timestamp.toString();
        const localDate = new Date(utcString);

        return {
          timestamp: timestamp,
          utcString: utcString + ' UTC',
          localString: localDate.toLocaleString() + ' (Local)',
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
        };
      }

      if (typeof timestamp === 'string') {
        const date = new Date(timestamp);
        if (!isNaN(date.getTime())) {
          return {
            timestamp: timestamp,
            utcString: date.toISOString() + ' UTC',
            localString: date.toLocaleString() + ' (Local)',
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
          };
        }
      }

      return {
        timestamp: timestamp,
        utcString: String(timestamp) + ' (Unknown timezone)',
        localString: String(timestamp) + ' (Unknown timezone)',
        timezone: 'Unknown'
      };
    } catch (error) {
      console.error('Error formatting timestamp:', error);
      return {
        timestamp: timestamp,
        utcString: 'Error formatting timestamp',
        localString: 'Error formatting timestamp',
        timezone: 'Error'
      };
    }
  }

  async getDatabaseStats(): Promise<DatabaseStats> {
    if (!this.driver) {
      throw new Error('Neo4j connection not available');
    }

    const session = this.driver.session({ defaultAccessMode: neo4j.session.READ });

    try {
      // Secure query for stats
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

        OPTIONAL MATCH (n)
        WHERE n.updated_at IS NOT NULL
        WITH nodeStats, edgeStats, totalNodes, totalEdges,
             max(n.updated_at) as lastUpdateFromUpdated

        OPTIONAL MATCH (n)
        WHERE n.created_at IS NOT NULL AND n.updated_at IS NULL
        WITH nodeStats, edgeStats, totalNodes, totalEdges, lastUpdateFromUpdated,
             max(n.created_at) as lastUpdateFromCreated

        WITH nodeStats, edgeStats, totalNodes, totalEdges,
             CASE
               WHEN lastUpdateFromUpdated IS NOT NULL AND lastUpdateFromCreated IS NOT NULL
               THEN CASE WHEN lastUpdateFromUpdated > lastUpdateFromCreated
                         THEN lastUpdateFromUpdated
                         ELSE lastUpdateFromCreated END
               WHEN lastUpdateFromUpdated IS NOT NULL THEN lastUpdateFromUpdated
               WHEN lastUpdateFromCreated IS NOT NULL THEN lastUpdateFromCreated
               ELSE null
             END as lastUpdate

        RETURN {
          nodeCount: totalNodes,
          edgeCount: totalEdges,
          nodeTypes: nodeStats,
          edgeTypes: edgeStats,
          lastUpdate: lastUpdate,
          isEmpty: totalNodes = 0
        } as stats
      `;

      const result = await session.run(statsQuery, {}, { timeout: 30000 });

      if (result.records.length > 0) {
        const stats = result.records[0].get('stats');

        const processedStats: any = {
          nodeCount: stats.nodeCount?.toNumber ? stats.nodeCount.toNumber() : stats.nodeCount || 0,
          edgeCount: stats.edgeCount?.toNumber ? stats.edgeCount.toNumber() : stats.edgeCount || 0,
          nodeTypes: (stats.nodeTypes || []).map((nt: any) => ({
            type: nt.type,
            count: nt.count?.toNumber ? nt.count.toNumber() : nt.count || 0
          })),
          edgeTypes: (stats.edgeTypes || []).map((et: any) => ({
            type: et.type,
            count: et.count?.toNumber ? et.count.toNumber() : et.count || 0
          })),
          lastUpdate: this.formatTimestamp(stats.lastUpdate),
          isEmpty: stats.isEmpty,
          labelCount: 0,
          relTypeCount: 0
        };

        return processedStats;
      }

      return {
        nodeCount: 0,
        edgeCount: 0,
        nodeTypes: [],
        edgeTypes: [],
        lastUpdate: this.formatTimestamp(null),
        isEmpty: true
      };
    } catch (error) {
      // Fallback to basic query
      try {
        const basicResult = await session.run(
          'MATCH (n) WITH count(n) as nodeCount OPTIONAL MATCH ()-[r]->() WITH nodeCount, count(r) as edgeCount RETURN nodeCount, edgeCount, nodeCount = 0 as isEmpty',
          {},
          { timeout: 10000 }
        );

        if (basicResult.records.length > 0) {
          const record = basicResult.records[0];
          return {
            nodeCount: record.get('nodeCount').toNumber(),
            edgeCount: record.get('edgeCount').toNumber(),
            isEmpty: record.get('isEmpty'),
            nodeTypes: [],
            edgeTypes: [],
            lastUpdate: this.formatTimestamp(null)
          };
        }
      } catch (fallbackError) {
        console.error('Error getting DB stats:', fallbackError);
        throw fallbackError;
      }

      return {
        nodeCount: 0,
        edgeCount: 0,
        isEmpty: true,
        nodeTypes: [],
        edgeTypes: [],
        lastUpdate: this.formatTimestamp(null)
      };
    } finally {
      await session.close();
    }
  }

  async isDatabasePopulated(): Promise<boolean> {
    if (!this.driver) {
      return false;
    }

    const session = this.driver.session({ defaultAccessMode: neo4j.session.READ });

    try {
      const result = await session.run(
        'MATCH (n) RETURN count(n) > 0 as hasData LIMIT 1',
        {},
        { timeout: 5000 }
      );

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

  /**
   * Sanitize properties to prevent injection or XSS
   */
  private sanitizeProperties(props: Record<string, any>): Record<string, any> {
    const sanitized: Record<string, any> = {};
    
    for (const [key, value] of Object.entries(props)) {
      if (typeof value === 'string') {
        sanitized[key] = this.sanitizeString(value);
      } else if (typeof value === 'object' && value !== null) {
        sanitized[key] = this.sanitizeProperties(value);
      } else {
        sanitized[key] = value;
      }
    }
    
    return sanitized;
  }

  /**
   * Sanitize a string value
   */
  private sanitizeString(str: string): string {
    // Remove any potential script tags or HTML
    return str
      .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
      .replace(/<[^>]+>/g, '')
      .trim();
  }

  async close() {
    if (this.driver) {
      await this.driver.close();
      this.driver = null;
    }
  }
}
