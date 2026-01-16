import { exec, spawn, ChildProcess } from 'child_process';
import { promisify } from 'util';
import { createLogger } from './logger-setup';

const logger = createLogger('neo4j-container');

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
    this.neo4jPassword = process.env.NEO4J_PASSWORD || require('crypto').randomBytes(16).toString('hex');
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
      logger.error('Error checking if Neo4j is running', { error });
      return false;
    }
  }

  async containerExists(): Promise<boolean> {
    try {
      const { stdout } = await execAsync(`docker ps -a --format "{{.Names}}"`);
      const allContainers = stdout.split('\n').filter(name => name.trim());
      return allContainers.includes(this.containerName);
    } catch (error) {
      logger.error('Error checking if Neo4j container exists', { error });
      return false;
    }
  }

  async start(): Promise<void> {
    // Check if Docker is available first
    const dockerAvailable = await this.isDockerAvailable();
    if (!dockerAvailable) {
      throw new Error('Docker is not installed or not running. Please install Docker Desktop and ensure it is running.');
    }

    logger.info(`Checking Neo4j container status (${this.containerName})...`);

    const running = await this.isRunning();
    if (running) {
      logger.info(`Neo4j container '${this.containerName}' is already running on port ${this.neo4jPort}`);
      return;
    }

    const exists = await this.containerExists();
    if (exists) {
      logger.info(`Starting existing Neo4j container '${this.containerName}'...`);
      try {
        await execAsync(`docker start ${this.containerName}`);
        logger.info('Neo4j container started successfully');
      } catch (error: any) {
        // If container exists but can't start (e.g., port conflict), check if another is using the port
        if (error.message?.includes('port is already allocated')) {
          logger.info(`Port ${this.neo4jPort} is already in use, checking for other Neo4j containers...`);
          // Check if the azure-tenant-grapher-neo4j container is already running
          const { stdout } = await execAsync(`docker ps --filter "publish=${this.neo4jPort}" --format "table {{.Names}}"`);
          if (stdout.includes('neo4j')) {
            logger.info(`Another Neo4j container is already using port ${this.neo4jPort}: ${stdout.trim()}`);
            logger.info('Using the existing Neo4j instance.');
            return;
          }
        }
        logger.error('Failed to start Neo4j container', { error });
        throw error;
      }
    } else {
      logger.info(`Creating new Neo4j container '${this.containerName}'...`);
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
        logger.debug(`Docker: ${data}`);
      });

      dockerProcess.stderr.on('data', (data) => {
        logger.error(`Docker Error: ${data}`);
      });

      dockerProcess.on('close', (code) => {
        if (code === 0) {
          logger.info('Neo4j container created successfully');
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
      logger.info('Neo4j container stopped');
    } catch (error) {
      logger.error('Failed to stop Neo4j container', { error });
    }
  }

  async remove(): Promise<void> {
    try {
      await this.stop();
      await execAsync(`docker rm ${this.containerName}`);
      logger.info('Neo4j container removed');
    } catch (error) {
      logger.error('Failed to remove Neo4j container', { error });
    }
  }

  async waitForReady(maxRetries: number = 30, delayMs: number = 2000): Promise<void> {
    logger.info('Waiting for Neo4j to be ready...');

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

        logger.info('Neo4j is ready!');
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
        neo4j.auth.basic('neo4j', this.neo4jPassword),
        {
          connectionTimeout: 5000, // 5 second timeout
          maxConnectionLifetime: 60 * 60 * 1000, // 1 hour
          maxConnectionPoolSize: 50,
          connectionAcquisitionTimeout: 10000 // 10 second timeout
        }
      );

      const session = driver.session();
      await session.run('RETURN 1');
      await session.close();
      await driver.close();

      return true;
    } catch (error) {
      logger.debug('Neo4j connection test failed', { error: error instanceof Error ? error.message : error });
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
        `docker inspect ${this.containerName}`
      );
      const inspectResult = JSON.parse(stdout);
      const state = inspectResult[0].State;

      // First check Docker's built-in health status
      let dockerHealth = 'unknown';
      try {
        if (state.Health && state.Health.Status) {
          dockerHealth = state.Health.Status;
        }
      } catch {
        // Container might not have health check configured
      }

      // Test actual Neo4j connection to determine real health
      const isHealthy = await this.testNeo4jConnection();

      // Determine final health status
      let containerHealth = 'starting';
      if (isHealthy) {
        containerHealth = 'healthy';
      } else if (dockerHealth === 'healthy') {
        // Docker says healthy but we can't connect - might be auth issue
        containerHealth = 'unhealthy';
      } else if (dockerHealth === 'unhealthy') {
        containerHealth = 'unhealthy';
      } else if (state.Running && Date.now() - new Date(state.StartedAt).getTime() > 60000) {
        // If running for more than 60 seconds and still can't connect
        containerHealth = 'unhealthy';
      }

      return {
        ...baseStatus,
        status: 'running',
        running: true,
        exists: true,
        health: containerHealth,
        dockerHealth,
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
