# Azure Tenant Grapher SPA

A desktop application providing a graphical interface for Azure Tenant Grapher, built with Electron, React, and TypeScript.

## Features

- **Full CLI Command Parity**: Every CLI command available through intuitive UI tabs
- **Real-time Progress Tracking**: Live logs and status updates for all operations
- **Cross-Platform**: Works on Windows, macOS, and Linux
- **Secure**: Local-only operation with no cloud dependencies
- **Accessible**: WCAG 2.1 AA compliant interface

## Quick Start

### Prerequisites

- Node.js 18+ and npm
- Python 3.9+ (for CLI backend)
- Docker (for Neo4j database)
- Azure CLI (optional, for Azure operations)

### Installation

1. **Install dependencies:**
   ```bash
   cd spa
   npm install
   ```

2. **Start the application:**
   ```bash
   # Using the CLI wrapper
   atg start
   
   # Or directly with npm
   npm run start
   ```

3. **Stop the application:**
   ```bash
   atg stop
   ```

## Development

### Project Structure

```
spa/
├── main/               # Electron main process
│   ├── index.ts       # Entry point
│   ├── ipc-handlers.ts # IPC communication
│   └── process-manager.ts # CLI subprocess management
├── renderer/           # React frontend
│   ├── src/
│   │   ├── components/ # UI components
│   │   ├── context/   # React context providers
│   │   └── App.tsx    # Main app component
│   └── index.html     # HTML template
├── backend/           # Express backend (optional)
└── tests/            # Test suites
```

### Available Scripts

```bash
# Development
npm run dev           # Start in development mode with hot reload
npm run dev:main     # Watch main process only
npm run dev:renderer # Watch renderer process only

# Building
npm run build        # Build for production
npm run package      # Package for current platform
npm run package:all  # Package for all platforms

# Testing
npm test            # Run unit tests
npm run test:e2e    # Run end-to-end tests
npm run test:coverage # Generate coverage report

# Code Quality
npm run lint        # Run ESLint
npm run format      # Format with Prettier
```

### Development Workflow

1. **Start development server:**
   ```bash
   npm run dev
   ```

2. **Make changes:** The app will hot-reload automatically

3. **Run tests:**
   ```bash
   npm test
   ```

4. **Build for production:**
   ```bash
   npm run build
   ```

## UI Features

### Build Tab
- Configure and execute Azure tenant graph builds
- Set resource limits and thread counts
- Real-time progress tracking with logs
- Options for edge rebuilding and AAD import

### Generate Spec Tab
- Generate tenant specifications in JSON/YAML
- Syntax-highlighted code viewer
- Export functionality

### Generate IaC Tab
- Generate Infrastructure as Code (Terraform/ARM/Bicep)
- Resource filtering capabilities
- Dry run mode for testing

### Create Tenant Tab
- Create tenants from specification files
- Upload or paste specifications
- Validation and error feedback

### Visualize Tab
- Interactive Neo4j graph visualization
- Custom Cypher query support
- Export graph as image

### Agent Mode Tab
- AI-powered conversational interface
- Context-aware assistance
- Command history

### Threat Model Tab
- Security assessment and analysis
- Risk matrix visualization
- Export threat reports

### Configuration Tab
- Environment variable management
- Dependency checking
- Connection testing

## Architecture

### Electron Main Process
- Manages application lifecycle
- Handles IPC communication
- Spawns CLI subprocesses
- File system operations

### React Renderer Process
- User interface rendering
- State management with Context API
- WebSocket for real-time updates
- Material-UI components

### IPC Communication
- Secure message passing
- Type-safe channel definitions
- Bidirectional data flow
- Error handling

### Process Management
- CLI command execution
- Output streaming
- Process lifecycle control
- Resource cleanup

## Security

### Principles
- **Process Isolation**: Renderer runs in sandboxed context
- **No Direct Access**: File system accessed only through IPC
- **Secret Management**: Credentials never exposed to renderer
- **Input Validation**: All user inputs validated and sanitized

### Best Practices
- Environment variables stored securely
- No hardcoded credentials
- Secure IPC channels
- Regular security audits

## Testing

### Unit Tests
```bash
npm test
```
- Component testing with React Testing Library
- Service testing with Jest
- IPC handler testing
- Process manager testing

### Integration Tests
```bash
npm run test:integration
```
- CLI command integration
- IPC communication testing
- File system operations
- Database connections

### E2E Tests
```bash
npm run test:e2e
```
- Full workflow testing with Playwright
- Cross-platform validation
- Performance benchmarks
- Accessibility audits

### Coverage
```bash
npm run test:coverage
```
Target: 80% code coverage

## Troubleshooting

### Common Issues

#### Application won't start
- Ensure Node.js 18+ is installed: `node --version`
- Check npm installation: `npm --version`
- Verify dependencies: `npm install`
- Check for port conflicts on 5173 (development)

#### CLI commands not working
- Verify Python installation: `python --version`
- Check Python path in environment
- Ensure CLI is properly installed
- Review logs in `outputs/` directory

#### Neo4j connection issues
- Verify Docker is running: `docker ps`
- Check Neo4j container status
- Validate credentials in configuration
- Test connection from Config tab

#### Build failures
- Clear node_modules: `rm -rf node_modules && npm install`
- Clean build artifacts: `npm run clean`
- Check TypeScript errors: `npx tsc --noEmit`
- Review webpack configuration

### Debug Mode

Enable debug logging:
```bash
DEBUG=* npm run dev
```

View Electron logs:
```bash
# Main process logs
tail -f ~/.config/azure-tenant-grapher/logs/main.log

# Renderer console
# Open DevTools with Ctrl+Shift+I (Cmd+Option+I on macOS)
```

## Performance Optimization

### Tips
- Use production builds for testing performance
- Enable hardware acceleration
- Optimize bundle size with code splitting
- Implement virtual scrolling for large lists
- Use Web Workers for heavy computations

### Monitoring
- Memory usage: DevTools Performance tab
- CPU profiling: DevTools Profiler
- Network requests: DevTools Network tab
- React DevTools for component optimization

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run tests and linting
6. Submit a pull request

See [CONTRIBUTING.md](../CONTRIBUTING.md) for detailed guidelines.

## License

MIT License - see [LICENSE](../LICENSE) for details.

## Support

- GitHub Issues: [Report bugs or request features](https://github.com/your-org/azure-tenant-grapher/issues)
- Documentation: [Full documentation](../docs/README.md)
- Discord: [Join our community](https://discord.gg/azure-tenant-grapher)