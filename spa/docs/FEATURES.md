# Azure Tenant Grapher SPA Features

This document provides a comprehensive overview of all features implemented in the Azure Tenant Grapher Single Page Application (SPA). The SPA provides a modern, user-friendly interface for managing Azure tenant analysis, Neo4j database operations, and Infrastructure-as-Code generation.

## Architecture Overview

The SPA is built using:
- **Frontend**: React with TypeScript, Material-UI components, React Router
- **Backend**: Node.js Express server with Socket.io for real-time communication
- **Desktop App**: Electron wrapper for cross-platform desktop deployment
- **Real-time Communication**: WebSocket integration for live updates and progress tracking

## Tab Structure (12 Tabs)

The application features a comprehensive tab-based navigation system with 12 specialized tabs:

### 1. Status Tab
**Icon**: Dashboard
**Purpose**: Central hub for database and system monitoring

**Features**:
- Real-time Neo4j container status monitoring
- Database connection health indicators
- Live database statistics (nodes, edges, types)
- Container lifecycle management (start/stop)
- Auto-refresh every 5 seconds
- Database management operations (backup, restore, wipe)
- Process ID tracking and container information
- Last update timestamps

### 2. Build Tab
**Icon**: Build
**Purpose**: Azure tenant discovery and graph building

**Features**:
- Azure tenant resource discovery
- Progress tracking with real-time updates
- Resource filtering and limiting options
- Background operation monitoring
- Error handling and status reporting
- Integration with Azure Discovery Service

### 3. Visualize Tab
**Icon**: Visibility
**Purpose**: Graph visualization and exploration

**Features**:
- Interactive graph visualization
- Node and relationship filtering
- Zoom and pan capabilities
- Graph layout algorithms
- Export functionality
- Real-time graph updates

### 4. Docs Tab
**Icon**: MenuBook
**Purpose**: Documentation browser and help system

**Features**:
- Integrated documentation viewer
- Markdown rendering
- Project documentation access
- Feature guides and tutorials
- API documentation browsing

### 5. Generate Spec Tab
**Icon**: Description
**Purpose**: Infrastructure specification generation

**Features**:
- Azure resource specification creation
- Template-based generation
- Export to various formats
- Customizable templates
- Validation and preview capabilities

### 6. Generate IaC Tab
**Icon**: Code
**Purpose**: Infrastructure-as-Code generation

**Features**:
- Multi-format IaC generation (Terraform, ARM, Bicep)
- Resource dependency mapping
- Configuration customization
- Preview and validation
- Export functionality

### 7. Create Tenant Tab
**Icon**: AddCircle
**Purpose**: Tenant creation and configuration

**Features**:
- New tenant setup wizard
- Configuration templates
- Validation and testing
- Azure connection setup
- Environment configuration

### 8. Agent Mode Tab
**Icon**: Psychology
**Purpose**: AI agent integration and automation

**Features**:
- LLM-powered analysis
- Automated threat detection
- Natural language querying
- Intelligent recommendations
- Context-aware assistance

### 9. Threat Model Tab
**Icon**: Security
**Purpose**: Security analysis and threat modeling

**Features**:
- Automated threat detection
- Security posture analysis
- Risk assessment reports
- Compliance checking
- Remediation suggestions

### 10. Logs Tab
**Icon**: BugReport
**Purpose**: System logging and debugging

**Features**:
- Real-time log streaming
- Log level filtering (INFO, WARN, ERROR, DEBUG)
- Search and filtering capabilities
- Process-specific log isolation
- Auto-scroll and pagination
- Export and saving functionality
- Color-coded log levels

### 11. CLI Tab
**Icon**: Terminal
**Purpose**: Command-line interface integration

**Features**:
- Interactive command builder
- Command history and suggestions
- Real-time command execution
- Output streaming and capture
- Background process management
- Integration with Python CLI

### 12. Config Tab
**Icon**: Settings
**Purpose**: Application configuration and settings

**Features**:
- Environment variable management
- Neo4j connection settings
- Azure authentication configuration
- Application preferences
- Theme and UI customization
- Export/import configuration

## Real-time Features

### WebSocket Integration
- **Live Updates**: Real-time communication between frontend and backend
- **Process Monitoring**: Live tracking of background operations
- **Output Streaming**: Real-time command output and log streaming
- **Status Synchronization**: Instant status updates across all tabs
- **Automatic Reconnection**: Robust connection management with exponential backoff

### Background Operation Tracking
- **Operation Registry**: Centralized tracking of all background processes
- **Progress Indicators**: Real-time progress bars and status updates
- **Memory Management**: Automatic cleanup and buffer size limits
- **Process Isolation**: Separate tracking for different operation types
- **Status Bar Integration**: Live display of active operations

### Auto-refresh Capabilities
- **Database Stats**: Automatic refresh of Neo4j statistics every 5 seconds
- **Process Status**: Continuous monitoring of system processes
- **Connection Health**: Real-time connection status monitoring
- **Intelligent Updates**: Conditional refresh based on system state

## Database Management

### Neo4j Container Management
- **Lifecycle Control**: Start, stop, and restart Neo4j containers
- **Health Monitoring**: Container health checks and status reporting
- **Port Management**: Automatic port detection and configuration
- **Process Tracking**: PID monitoring and resource usage
- **Error Handling**: Comprehensive error reporting and recovery

### Database Operations
- **Backup Operations**:
  - Full database backup with user-specified paths
  - Temporary container shutdown during backup
  - Progress tracking and status reporting
  - Validation and error handling

- **Restore Operations**:
  - Database restoration from backup files
  - Data validation and integrity checks
  - Automatic statistics refresh post-restore
  - Warning dialogs for destructive operations

- **Database Wipe**:
  - Complete database clearing
  - Confirmation dialogs with warnings
  - Automatic cleanup and reset
  - Post-operation verification

### Statistics and Monitoring
- **Real-time Metrics**: Live node and edge counts
- **Type Analysis**: Node and relationship type breakdowns
- **Performance Tracking**: Query performance and response times
- **Historical Data**: Timestamp tracking for updates
- **Visual Indicators**: Status chips and progress bars

## UI Enhancements

### Dark Theme Support
- **Material-UI Theme**: Comprehensive dark theme implementation
- **Consistent Styling**: Dark theme across all components
- **User Preference**: Theme selection and persistence
- **High Contrast**: Optimized for readability and accessibility

### Status Bar Features
- **Tenant Information**: Display of current Azure tenant name
- **Connection Status**: Real-time WebSocket connection indicator
- **Process Indicators**: Active process chips with PIDs
- **Timestamp Display**: Live clock with current time
- **Operation Status**: Background operation status chips
- **Tooltips**: Detailed information on hover

### Window Management
- **Centered Title Bar**: macOS-style hidden inset title bar
- **Resizable Interface**: Flexible window sizing with constraints
- **Default Size**: Optimized 1600x1000 pixel default dimensions
- **Minimum Size**: 1200x800 pixel minimum constraints
- **Maximization**: Full-screen support and window state management

### Navigation and Layout
- **Scrollable Tabs**: Horizontal scrolling for tab overflow
- **Icon Integration**: Material-UI icons for all tabs
- **Responsive Design**: Adaptive layout for different screen sizes
- **Consistent Spacing**: Material-UI spacing system implementation

## Developer Tools

### Logs Tab Advanced Features
- **Multi-level Filtering**: Filter by log level (DEBUG, INFO, WARN, ERROR)
- **Process Filtering**: Isolate logs by specific process IDs
- **Search Functionality**: Text search within log entries
- **Color Coding**: Visual distinction by log level
- **Auto-scroll**: Automatic scrolling to latest entries
- **Buffer Management**: Automatic cleanup of old log entries
- **Export Capability**: Save logs to file for analysis

### CLI Tab Capabilities
- **Command Builder**: Interactive command construction
- **Parameter Assistance**: Context-aware parameter suggestions
- **Execution History**: Command history and recall
- **Output Capture**: Real-time command output display
- **Process Management**: Background process control
- **Error Handling**: Comprehensive error reporting and debugging

### Documentation Integration
- **Inline Help**: Context-sensitive help and documentation
- **Markdown Rendering**: Rich text documentation display
- **Navigation**: Easy browsing of documentation sections
- **Search**: Full-text search within documentation
- **Cross-references**: Linked references between topics

## Integration Features

### Environment Variable Management
- **Automatic Loading**: Environment file loading and parsing
- **Propagation**: Environment variable inheritance to child processes
- **Validation**: Configuration validation and error reporting
- **Security**: Secure handling of sensitive credentials
- **Override Support**: Runtime environment variable overrides

### Python CLI Integration
- **Process Spawning**: Seamless Python CLI process management
- **Output Streaming**: Real-time Python script output capture
- **Error Handling**: Python exception capture and reporting
- **Environment Sync**: Environment variable synchronization
- **Process Lifecycle**: Complete process lifecycle management

### Hotkey Support
- **Global Hotkeys**: System-wide keyboard shortcuts
- **GUI Launch**: 'g' hotkey to launch GUI from CLI
- **Context-aware**: Different shortcuts for different contexts
- **Customizable**: User-configurable hotkey assignments

## Security Features

### Process Isolation
- **Sandboxed Execution**: Isolated process execution
- **Permission Management**: Controlled file system access
- **Resource Limits**: Memory and CPU usage constraints
- **Secure Communication**: Encrypted inter-process communication

### Data Protection
- **Credential Security**: Secure storage of Azure credentials
- **Connection Encryption**: Encrypted database connections
- **Session Management**: Secure session handling
- **Audit Logging**: Security event logging and monitoring

## Performance Optimizations

### Memory Management
- **Buffer Limits**: Automatic cleanup of large data structures
- **Process Cleanup**: Automatic termination of idle processes
- **Memory Monitoring**: Real-time memory usage tracking
- **Garbage Collection**: Proactive memory cleanup

### Network Optimization
- **Connection Pooling**: Efficient database connection management
- **Request Batching**: Batch API requests for efficiency
- **Caching**: Intelligent caching of frequently accessed data
- **Compression**: Data compression for network transfers

### UI Performance
- **Lazy Loading**: On-demand component loading
- **Virtual Scrolling**: Efficient handling of large lists
- **Debounced Updates**: Optimized real-time updates
- **Efficient Re-rendering**: Minimized React re-renders

## Error Handling and Recovery

### Comprehensive Error Management
- **Error Boundaries**: React error boundary implementation
- **Graceful Degradation**: Fallback UI states for errors
- **Error Reporting**: Detailed error logging and reporting
- **Recovery Mechanisms**: Automatic recovery from transient failures

### User Feedback
- **Toast Notifications**: Non-intrusive success/error messages
- **Progress Indicators**: Clear feedback during operations
- **Status Messages**: Informative status updates
- **Help Context**: Context-sensitive help and guidance

## Future Enhancement Placeholders

### Screenshots Section
*[Screenshot placeholders will be added here showing:]*
- Main application interface with all tabs
- Status tab with database statistics
- Real-time log streaming in Logs tab
- CLI tab command execution
- Database management operations
- Theme switcher and customization options

### Performance Metrics
*[Performance data will be added here showing:]*
- Application startup time
- Memory usage statistics
- Network request performance
- Database query response times
- Real-time update latency

---

## Technical Implementation Notes

### WebSocket Architecture
The application uses Socket.io for bidirectional communication:
```typescript
// WebSocket connection with automatic reconnection
const socket = io('http://localhost:3001', {
  transports: ['websocket'],
  reconnection: true,
  reconnectionDelay: getReconnectionDelay,
  reconnectionAttempts: 10,
});
```

### Process Management
Background processes are managed through a centralized ProcessManager:
```typescript
// Process spawning with environment inheritance
const process = spawn(command, args, {
  env: { ...process.env, BACKEND_PORT: '3001' }
});
```

### State Management
Application state is managed through React Context:
```typescript
// Centralized application state
interface AppState {
  backgroundOperations: Map<string, BackgroundOperation>;
  connectionStatus: 'connected' | 'disconnected';
  currentTenant: string;
}
```

This comprehensive feature set provides users with a powerful, intuitive interface for managing Azure tenant analysis, database operations, and infrastructure generation, all wrapped in a modern desktop application with extensive real-time capabilities and developer-friendly tools.
