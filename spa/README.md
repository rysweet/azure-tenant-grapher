# Azure Tenant Grapher SPA

A powerful desktop application providing a comprehensive graphical interface for Azure Tenant Grapher, built with Electron, React, and TypeScript. This SPA delivers full CLI command parity through an intuitive, professional-grade user interface with real-time monitoring and advanced visualization capabilities.

## Overview

The Azure Tenant Grapher SPA transforms the command-line Azure discovery and Infrastructure-as-Code generation tool into a rich desktop experience. Built on modern web technologies and packaged as an Electron application, it provides seamless integration with the underlying Python CLI while offering advanced features like real-time progress tracking, interactive graph visualization, and comprehensive documentation browsing.

## Features

### 12 Comprehensive Tabs

The application organizes all functionality into 12 purpose-built tabs:

1. **Status** - System status, connections, and health monitoring with real-time indicators
2. **Build** - Azure tenant discovery and graph building with live progress tracking and WebSocket streaming
3. **Visualize** - Interactive Neo4j graph visualization with custom Cypher queries and export capabilities
4. **Docs** - Integrated documentation browser with searchable markdown files, table of contents, and hierarchical navigation
5. **Generate Spec** - Tenant specification generation in JSON/YAML with syntax highlighting and export functionality
6. **Generate IaC** - Infrastructure-as-Code generation (Terraform/ARM/Bicep) with resource filtering and dry-run support
7. **Create Tenant** - Tenant provisioning from specifications with validation and upload/paste capabilities
8. **Agent Mode** - AI-powered conversational interface with context-aware assistance and command history
9. **Threat Model** - Security assessment and analysis with risk matrix visualization and threat report export
10. **Logs** - Centralized logging with Monaco Editor integration, syntax highlighting, and multi-source filtering
11. **CLI** - Full terminal emulator using xterm.js with complete CLI integration and color support
12. **Config** - Environment configuration, dependency checking, and connection testing

### Core Capabilities

- **Real-time Progress Tracking**: Live logs and WebSocket-based status updates for all operations
- **Cross-Platform Support**: Native applications for Windows, macOS, and Linux
- **Secure Local Operation**: No cloud dependencies, all processing happens locally
- **Professional Interface**: WCAG 2.1 AA compliant with Material-UI design system
- **Advanced Editor Integration**: Monaco Editor for logs and xterm.js for terminal functionality
- **Background Operation Management**: Process tracking with PID monitoring and cancellation support

## Prerequisites

### Required Software
- **Node.js 18+** and npm (automatically checked by CLI)
- **Python 3.9+** (for CLI backend integration)
- **Docker** (for Neo4j database container management)
- **Azure CLI** (optional, for enhanced Azure operations)

### Environment Setup
The application requires several environment variables (see `.env.example` in project root):
- `AZURE_TENANT_ID` - Your Azure tenant identifier
- `AZURE_CLIENT_ID` - Azure service principal client ID
- `AZURE_CLIENT_SECRET` - Azure service principal secret
- `NEO4J_PASSWORD` - Neo4j database password
- `NEO4J_URI` - Neo4j connection URI (default: bolt://localhost:7687)
- `OPENAI_API_KEY` - For AI-powered features (optional)

## Installation

### Quick Start (Recommended)

The SPA is fully integrated with the Azure Tenant Grapher CLI for seamless launching:

```bash
# Start the SPA/Electron dashboard
atg start

# Stop the SPA when done
atg stop
```

The CLI automatically handles dependency installation, environment setup, and process management.

### Alternative Launch Methods

```bash
# Using full command name
azure-tenant-grapher start

# Using Python directly
python scripts/cli.py start

# Direct npm development mode (with hot reload)
cd spa && npm run dev
```

### Manual Installation

If you prefer manual setup:

```bash
# Navigate to SPA directory
cd spa

# Install dependencies
npm install

# Start in development mode
npm run dev

# Or build and run production version
npm run build
npm start
```

## Development

### Project Structure

```
spa/
├── main/                   # Electron main process
│   ├── index.ts           # Application entry point
│   ├── ipc-handlers.ts    # Inter-process communication
│   ├── process-manager.ts # CLI subprocess management
│   └── menu.ts           # Application menu system
├── renderer/              # React frontend
│   ├── src/
│   │   ├── components/    # UI components
│   │   │   ├── common/   # Shared components (Header, StatusBar, etc.)
│   │   │   ├── tabs/     # 12 tab-specific components
│   │   │   └── widgets/  # Reusable widgets
│   │   ├── context/      # React context providers
│   │   ├── hooks/        # Custom React hooks
│   │   ├── services/     # API services
│   │   └── utils/        # Utility functions
│   └── index.html        # HTML template
├── backend/               # Express backend server
│   └── src/
│       ├── server.ts     # Express server with Socket.IO
│       ├── neo4j-service.ts  # Database integration
│       └── neo4j-container.ts # Container management
└── tests/                # Test suites
    ├── components/       # Component tests
    ├── integration/      # Integration tests
    └── e2e/             # End-to-end tests
```

### Development Scripts

```bash
# Development (hot reload enabled)
npm run dev              # All processes concurrently
npm run dev:main         # Watch main process only
npm run dev:renderer     # Watch renderer process only
npm run dev:backend      # Watch backend server only

# Building
npm run build           # Build all processes
npm run build:main      # Build main process
npm run build:renderer  # Build renderer process
npm run build:backend   # Build backend server

# Packaging
npm run package         # Package for current platform
npm run package:all     # Package for all platforms (macOS, Windows, Linux)

# Testing
npm test               # Run unit tests
npm run test:e2e       # Run end-to-end tests with Playwright
npm run test:coverage  # Generate coverage report

# Code Quality
npm run lint           # Run ESLint
npm run format         # Format with Prettier
```

### Development Workflow

1. **Start development environment:**
   ```bash
   npm run dev
   ```

2. **Application automatically opens** with hot-reload enabled across all processes

3. **Make changes** - the app will reload automatically for frontend changes

4. **Run tests during development:**
   ```bash
   npm test -- --watch
   ```

5. **Build for production testing:**
   ```bash
   npm run build && npm start
   ```

## Architecture

### Multi-Process Design

The application follows Electron's multi-process architecture:

- **Main Process**: Manages application lifecycle, window management, and secure IPC
- **Renderer Process**: React-based UI running in a sandboxed environment
- **Backend Server**: Express.js server providing REST API and WebSocket communication

### Technology Stack

**Frontend:**
- React 18 with TypeScript for component architecture
- Material-UI (MUI) v5 for design system and components
- React Router v6 for client-side navigation
- Socket.IO client for real-time communication
- Monaco Editor for advanced text editing
- xterm.js for full terminal emulation

**Backend:**
- Express.js for REST API server
- Socket.IO for real-time bidirectional communication
- Neo4j Driver for graph database connectivity
- CORS for cross-origin request handling

**Development Tools:**
- Vite for fast development and building
- Electron Builder for cross-platform packaging
- Jest + React Testing Library for testing
- Playwright for end-to-end testing
- ESLint + Prettier for code quality

For detailed architectural information, see [DESIGN.md](/Users/ryan/src/msec/atg-0723/azure-tenant-grapher/spa/docs/DESIGN.md).

## Key Components

### Custom React Hooks

- **`useWebSocket`** - Enhanced WebSocket management with auto-reconnection and buffering
- **`useLogger`** - Structured logging with multi-source support (API, Process, WebSocket, Graph, System)
- **`useBackgroundOperations`** - Background process tracking with PID monitoring
- **`useTenantName`** - Intelligent tenant name extraction and display
- **`useGraphAPI`** - Neo4j graph database integration

### Enhanced UI Components

- **Enhanced StatusBar** - Displays tenant information, background operations with PIDs, and connection status
- **TabNavigation** - 12-tab system with scrollable navigation and Material-UI integration
- **LogViewer** - Advanced log viewing with Monaco Editor and syntax highlighting
- **GraphVisualization** - Interactive D3.js/vis-network based graph rendering
- **Terminal Integration** - Full xterm.js terminal emulator in CLI tab

### Core Services

- **Process Manager** - Manages CLI subprocesses with lifecycle control
- **Neo4j Service** - Database operations and container management
- **WebSocket Service** - Real-time communication with memory-efficient buffering

## Keyboard Shortcuts

### Global Shortcuts
- **Ctrl/Cmd + Shift + I** - Open Developer Tools
- **Ctrl/Cmd + R** - Reload application
- **Ctrl/Cmd + Q** - Quit application

### CLI Integration
- **'g' key** - Launch GUI from CLI dashboard (when running CLI commands)
- **'x' key** - Exit CLI dashboard

### Tab Navigation
- **Ctrl/Cmd + [1-12]** - Direct tab navigation
- **Ctrl/Cmd + Tab** - Next tab
- **Ctrl/Cmd + Shift + Tab** - Previous tab

### Editor Shortcuts (Logs Tab)
- **Ctrl/Cmd + F** - Find in logs
- **Ctrl/Cmd + G** - Find next
- **Ctrl/Cmd + Shift + G** - Find previous
- **Ctrl/Cmd + A** - Select all

### Terminal Shortcuts (CLI Tab)
- **Ctrl/Cmd + C** - Copy selection
- **Ctrl/Cmd + V** - Paste
- **Ctrl + L** - Clear terminal
- **Ctrl + C** - Interrupt current command

## Troubleshooting

### Common Issues

#### Application Won't Start
```bash
# Check Node.js version (requires 18+)
node --version

# Check npm installation
npm --version

# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install

# Check for port conflicts
lsof -i :3001 -i :5173
```

#### CLI Commands Not Working
```bash
# Verify Python installation
python --version

# Check CLI is installed
which atg

# Test CLI directly
atg doctor

# Review logs
tail -f spa/outputs/*.log
```

#### Neo4j Connection Issues
```bash
# Check Docker status
docker ps

# Verify Neo4j container
docker ps | grep neo4j

# Test connection from Config tab
# Or manually test connection
curl -u neo4j:password http://localhost:7474
```

#### Build/Package Failures
```bash
# Clean build artifacts
npm run clean  # if available, or:
rm -rf dist dist-electron node_modules

# Reinstall and rebuild
npm install
npm run build

# Check TypeScript compilation
npx tsc --noEmit
```

#### WebSocket Connection Issues
- Verify backend server is running on port 3001
- Check firewall settings for local connections
- Review browser console for WebSocket errors
- Restart the application to reset connections

#### Performance Issues
```bash
# Check memory usage in DevTools
# Enable production mode for performance testing
NODE_ENV=production npm start

# Monitor process resource usage
top -p $(pgrep -f "azure-tenant-grapher")
```

### Debug Mode

Enable comprehensive logging:
```bash
# Development with debug logging
DEBUG=* npm run dev

# View application logs
tail -f ~/.config/azure-tenant-grapher/logs/main.log

# Backend server logs
tail -f spa/outputs/backend.log

# Open DevTools for frontend debugging
# Ctrl/Cmd + Shift + I in the application
```

### Log Locations
- **Main Process**: `~/.config/azure-tenant-grapher/logs/main.log`
- **Backend Server**: `spa/outputs/backend.log`
- **CLI Integration**: `outputs/*.log` in project root
- **WebSocket Communication**: Available in Logs tab

## Recent Updates

### Version 1.1 Enhancements

#### New Features
- **Documentation Integration**: Added dedicated Docs tab with full markdown browser and search
- **Enhanced StatusBar**: Tenant information display and background operation monitoring with PIDs
- **Improved Logging**: Multi-source structured logging with Monaco Editor integration
- **Terminal Integration**: Full xterm.js terminal emulator in CLI tab
- **WebSocket Reliability**: Enhanced auto-reconnection and memory-efficient buffering
- **Tenant Name Extraction**: Intelligent tenant name display with fallback handling

#### Architecture Improvements
- **12-Tab System**: Reorganized UI with logical workflow-based tab ordering
- **Process Management**: Enhanced background operation tracking with cancellation support
- **Real-time Updates**: Improved WebSocket integration for Build tab progress tracking
- **Security Enhancements**: Better environment variable handling and process isolation
- **Performance Optimizations**: Memory-efficient log buffering and output management

#### Developer Experience
- **Enhanced Testing**: Expanded test coverage with component, integration, and E2E tests
- **Better Documentation**: Comprehensive DESIGN.md and inline code documentation
- **Improved Development Workflow**: Hot-reload for all processes and better error handling
- **Cross-platform Packaging**: Streamlined build and packaging for all supported platforms

## Performance Tips

### Optimization Guidelines
- Use production builds for performance testing: `npm run build && npm start`
- Enable hardware acceleration in Electron settings
- Monitor memory usage through DevTools Performance tab
- Use the Config tab to test and optimize database connections
- Consider resource limits when processing large Azure tenants

### System Requirements
- **Minimum RAM**: 4GB (8GB recommended for large tenants)
- **Disk Space**: 2GB free space for application and Neo4j data
- **CPU**: Multi-core processor recommended for concurrent operations
- **Network**: Stable internet connection for Azure API calls

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes with appropriate tests
4. Run the full test suite: `npm test && npm run test:e2e`
5. Ensure code quality: `npm run lint && npm run format`
6. Commit your changes: `git commit -m 'Add amazing feature'`
7. Push to the branch: `git push origin feature/amazing-feature`
8. Open a Pull Request

### Development Standards
- Follow TypeScript strict mode guidelines
- Write tests for new functionality
- Update documentation for API changes
- Follow Material-UI design patterns
- Ensure cross-platform compatibility

## Support & Resources

- **Issues & Bug Reports**: [GitHub Issues](https://github.com/your-org/azure-tenant-grapher/issues)
- **Documentation**: [Full Documentation](../docs/README.md)
- **Architecture Details**: [DESIGN.md](docs/DESIGN.md)
- **API Reference**: Available in Docs tab when running the application
- **CI/CD Status**: Check with `../scripts/check_ci_status.sh`

## License

MIT License - see [LICENSE](../LICENSE) for details.

---

**Azure Tenant Grapher SPA** - Professional Azure tenant visualization and Infrastructure-as-Code generation in a modern desktop application.
