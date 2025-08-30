import { exec, spawn, ChildProcess } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

export class Neo4jContainer {
  private containerName: string;
  private neo4jImage: string = 'neo4j:5.25.1';
  private neo4jPort: string;
  private neo4jPassword: string;

  constructor() {
    // Use the same container name as the Python CLI
    this.containerName = process.env.NEO4J_CONTAINER_NAME || 'azure-tenant-grapher-neo4j';
    this.neo4jPort = process.env.NEO4J_PORT || '7687';
    this.neo4jPassword = process.env.NEO4J_PASSWORD || 'azure-grapher-2024';
  }

  async isDockerAvailable(): Promise<boolean> {
    try {
      await execAsync('docker --version');
      return true;
    } catch {
      return false;
    }
  }

  async isRunning(): Promise<boolean> {
    try {
      const { stdout } = await execAsync(`docker ps --format "{{.Names}}"`);
      const runningContainers = stdout.split('\n').filter(name => name.trim());
      return runningContainers.includes(this.containerName);
    } catch (error) {
      console.error('Error checking if Neo4j is running:', error);
      return false;
    }
  }

  async containerExists(): Promise<boolean> {
    try {
      const { stdout } = await execAsync(`docker ps -a --format "{{.Names}}"`);
      const allContainers = stdout.split('\n').filter(name => name.trim());
      return allContainers.includes(this.containerName);
    } catch (error) {
      console.error('Error checking if Neo4j container exists:', error);
      return false;
    }
  }

  async start(): Promise<void> {
    // Check if Docker is available first
    const dockerAvailable = await this.isDockerAvailable();
    if (!dockerAvailable) {
      throw new Error('Docker is not installed or not running. Please install Docker Desktop and ensure it is running.');
    }

    console.log(`Checking Neo4j container status (${this.containerName})...`);
    
    const running = await this.isRunning();
    if (running) {
      console.log(`Neo4j container '${this.containerName}' is already running on port ${this.neo4jPort}`);
      return;
    }

    const exists = await this.containerExists();
    if (exists) {
      console.log(`Starting existing Neo4j container '${this.containerName}'...`);
      try {
        await execAsync(`docker start ${this.containerName}`);
        console.log('Neo4j container started successfully');
      } catch (error: any) {
        // If container exists but can't start (e.g., port conflict), check if another is using the port
        if (error.message?.includes('port is already allocated')) {
          console.log(`Port ${this.neo4jPort} is already in use, checking for other Neo4j containers...`);
          // Check if the azure-tenant-grapher-neo4j container is already running
          const { stdout } = await execAsync(`docker ps --filter "publish=${this.neo4jPort}" --format "table {{.Names}}"`);
          if (stdout.includes('neo4j')) {
            console.log(`Another Neo4j container is already using port ${this.neo4jPort}: ${stdout.trim()}`);
            console.log('Using the existing Neo4j instance.');
            return;
          }
        }
        console.error('Failed to start Neo4j container:', error);
        throw error;
      }
    } else {
      console.log(`Creating new Neo4j container '${this.containerName}'...`);
      await this.create();
    }

    // Wait for Neo4j to be ready
    await this.waitForReady();
  }

  async create(): Promise<void> {
    const cmd = [
      'run',
      '-d',
      '--name', this.containerName,
      '-p', `${this.neo4jPort}:7687`,
      '-p', '7474:7474',
      '-e', `NEO4J_AUTH=neo4j/${this.neo4jPassword}`,
      '-e', 'NEO4J_PLUGINS=["apoc", "graph-data-science"]',
      '-e', 'NEO4J_apoc_export_file_enabled=true',
      '-e', 'NEO4J_apoc_import_file_enabled=true',
      '-e', 'NEO4J_apoc_import_file_use__neo4j__config=true',
      '-e', 'NEO4J_dbms_security_procedures_unrestricted=apoc.*,gds.*',
      '-v', `${this.containerName}_data:/data`,
      '-v', `${this.containerName}_logs:/logs`,
      this.neo4jImage
    ];

    return new Promise((resolve, reject) => {
      const dockerProcess = spawn('docker', cmd);
      
      dockerProcess.stdout.on('data', (data) => {
        console.log(`Docker: ${data}`);
      });

      dockerProcess.stderr.on('data', (data) => {
        console.error(`Docker Error: ${data}`);
      });

      dockerProcess.on('close', (code) => {
        if (code === 0) {
          console.log('Neo4j container created successfully');
          resolve();
        } else {
          reject(new Error(`Failed to create Neo4j container, exit code: ${code}`));
        }
      });

      dockerProcess.on('error', (error) => {
        reject(error);
      });
    });
  }

  async stop(): Promise<void> {
    try {
      await execAsync(`docker stop ${this.containerName}`);
      console.log('Neo4j container stopped');
    } catch (error) {
      console.error('Failed to stop Neo4j container:', error);
    }
  }

  async remove(): Promise<void> {
    try {
      await this.stop();
      await execAsync(`docker rm ${this.containerName}`);
      console.log('Neo4j container removed');
    } catch (error) {
      console.error('Failed to remove Neo4j container:', error);
    }
  }

  async waitForReady(maxRetries: number = 30, delayMs: number = 2000): Promise<void> {
    console.log('Waiting for Neo4j to be ready...');
    
    for (let i = 0; i < maxRetries; i++) {
      try {
        // Try to connect using the Neo4j driver
        const neo4j = require('neo4j-driver');
        const driver = neo4j.driver(
          `bolt://localhost:${this.neo4jPort}`,
          neo4j.auth.basic('neo4j', this.neo4jPassword)
        );
        
        const session = driver.session();
        await session.run('RETURN 1');
        await session.close();
        await driver.close();
        
        console.log('Neo4j is ready!');
        return;
      } catch (error) {
        if (i === maxRetries - 1) {
          throw new Error('Neo4j failed to start within timeout period');
        }
        await new Promise(resolve => setTimeout(resolve, delayMs));
      }
    }
  }

  async testNeo4jConnection(): Promise<boolean> {
    try {
      const neo4j = require('neo4j-driver');
      const driver = neo4j.driver(
        `bolt://localhost:${this.neo4jPort}`,
        neo4j.auth.basic('neo4j', this.neo4jPassword)
      );
      
      const session = driver.session();
      await session.run('RETURN 1');
      await session.close();
      await driver.close();
      
      return true;
    } catch (error) {
      return false;
    }
  }

  async getStatus(): Promise<any> {
    const running = await this.isRunning();
    const exists = await this.containerExists();
    
    const baseStatus = {
      containerName: this.containerName,
      uri: `bolt://localhost:${this.neo4jPort}`,
      port: this.neo4jPort,
    };
    
    if (!running) {
      return {
        ...baseStatus,
        status: exists ? 'stopped' : 'not_created',
        running: false,
        exists,
        health: 'stopped'
      };
    }

    try {
      const { stdout } = await execAsync(
        `docker inspect ${this.containerName} --format='{{json .State}}'`
      );
      const state = JSON.parse(stdout);
      
      // Test actual Neo4j connection to determine real health
      const isHealthy = await this.testNeo4jConnection();
      const containerHealth = isHealthy ? 'healthy' : 'starting';
      
      return {
        ...baseStatus,
        status: 'running',
        running: true,
        exists: true,
        health: containerHealth,
        startedAt: state.StartedAt,
        pid: state.Pid
      };
    } catch (error) {
      return {
        ...baseStatus,
        status: 'error',
        running: false,
        exists: false,
        health: 'error',
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }
}