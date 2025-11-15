/**
 * Web Server Configuration
 *
 * Configuration file for running Azure Tenant Grapher SPA as a standalone web application.
 * These settings can be overridden by environment variables.
 */

module.exports = {
  /**
   * Server port
   * Environment variable: WEB_SERVER_PORT
   * Default: 3000
   */
  port: parseInt(process.env.WEB_SERVER_PORT || '3000', 10),

  /**
   * Host to bind to
   * - '0.0.0.0' - Listen on all network interfaces (accessible from other machines)
   * - 'localhost' or '127.0.0.1' - Listen only on local machine
   * Environment variable: WEB_SERVER_HOST
   * Default: 0.0.0.0
   */
  host: process.env.WEB_SERVER_HOST || '0.0.0.0',

  /**
   * Enable CORS (Cross-Origin Resource Sharing)
   * Required for remote access from browsers
   * Environment variable: ENABLE_CORS
   * Default: true
   */
  enableCors: process.env.ENABLE_CORS !== 'false',

  /**
   * Allowed origins for CORS
   * Comma-separated list of allowed origins
   * Use '*' to allow all origins (less secure)
   * Environment variable: ALLOWED_ORIGINS
   * Default: *
   *
   * Examples:
   * - 'http://localhost:3000'
   * - 'http://10.0.0.5:3000,http://192.168.1.10:3000'
   * - '*'
   */
  allowedOrigins: process.env.ALLOWED_ORIGINS
    ? process.env.ALLOWED_ORIGINS.split(',').map(o => o.trim())
    : ['*'],

  /**
   * Neo4j configuration
   * These override the main .env settings for web mode if needed
   */
  neo4j: {
    uri: process.env.NEO4J_URI || 'bolt://localhost:7687',
    port: parseInt(process.env.NEO4J_PORT || '7687', 10),
    user: process.env.NEO4J_USER || 'neo4j',
    password: process.env.NEO4J_PASSWORD || '',
  },

  /**
   * Azure configuration
   * Credentials for connecting to Azure
   */
  azure: {
    tenantId: process.env.AZURE_TENANT_ID || '',
    clientId: process.env.AZURE_CLIENT_ID || '',
    clientSecret: process.env.AZURE_CLIENT_SECRET || '',
  },

  /**
   * Security settings
   */
  security: {
    // Enable authentication middleware (recommended for production)
    enableAuth: process.env.ENABLE_AUTH === 'true',

    // Rate limiting
    rateLimit: {
      windowMs: 15 * 60 * 1000, // 15 minutes
      max: 100, // limit each IP to 100 requests per windowMs
    },
  },

  /**
   * Logging configuration
   */
  logging: {
    level: process.env.LOG_LEVEL || 'info',
    // Log file path (optional)
    logFile: process.env.LOG_FILE || null,
  },

  /**
   * Development settings
   */
  development: {
    // Enable debug mode
    debug: process.env.NODE_ENV === 'development',

    // Enable source maps
    sourceMaps: true,
  },
};
