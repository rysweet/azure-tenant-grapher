# Azure Tenant Grapher SPA Design Document

## Overview

The Azure Tenant Grapher Single Page Application (SPA) is an Electron-based desktop application that provides a rich graphical interface for Azure tenant discovery, graph visualization, and Infrastructure-as-Code (IaC) generation. The application follows a multi-process architecture with clear separation between the main process, renderer process, and backend services.

## Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Electron Main Process                    │
├─────────────────────┬───────────────────┬──────────────────┤
│   Process Manager   │   IPC Handlers    │   Menu System    │
├─────────────────────┼───────────────────┼──────────────────┤
│                     │                   │                  │
│ ┌─────────────────┐ │ ┌───────────────┐ │ ┌──────────────┐ │
│ │ Child Processes │ │ │   Preload     │ │ │  Application │ │
│ │   Management    │ │ │   Security    │ │ │     Menu     │ │
│ └─────────────────┘ │ └───────────────┘ │ └──────────────┘ │
└─────────────────────┴───────────────────┴──────────────────┘
           │                     │                     │
           │                     │                     │
           ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    Electron Renderer Process                │
├─────────────────────────────────────────────────────────────┤
│               React Application (TypeScript)                │
├─────────────────┬───────────────┬───────────────────────────┤
│  Context API    │  Custom Hooks │     Component Tree        │
│  Global State   │  WebSocket    │   Tab-based Navigation    │
│                 │  Logging      │   Enhanced StatusBar      │
│                 │  Background   │   Documentation Browser   │
│                 │  Operations   │                           │
│                 │  TenantName   │                           │
└─────────────────┴───────────────┴───────────────────────────┘
           │                     │                     │
           │                     │                     │
           ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    Express Backend Server                   │
├─────────────────────────────────────────────────────────────┤
│  REST API       │  WebSocket     │  Process Management     │
│  Neo4j Service  │  Socket.IO     │  CLI Integration        │
│  Container Mgmt │  Real-time     │  Docker Orchestration   │
│  Docs Service   │  Streaming     │  File System Access     │
└─────────────────┴────────────────┴─────────────────────────┘
           │                     │                     │
           │                     │                     │
           ▼                     ▼                     ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   Neo4j Graph   │ │   Python CLI    │ │   Azure APIs    │
│    Database     │ │    (ATG Core)   │ │   Integration   │
│   Container     │ │                 │ │                 │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

### Process Architecture

#### Electron Main Process
- **Entry Point**: `/main/index.ts`
- **Window Size**: Default 1600x1000, minimum 1200x800
- **Responsibilities**:
  - Window lifecycle management
  - Backend server startup
  - Environment variable loading and propagation
  - Process orchestration and cleanup
  - Application menu management
  - IPC communication handling
  - GUI launch hotkey ('g' key) integration

#### Electron Renderer Process
- **Entry Point**: `/renderer/src/main.tsx`
- **Framework**: React 18 with TypeScript
- **Responsibilities**:
  - User interface rendering
  - State management via Context API
  - Real-time communication with backend
  - Tab-based navigation system (12 tabs)
  - User interaction handling
  - Custom hooks integration

#### Backend Express Server
- **Entry Point**: `/backend/src/server.ts`
- **Port**: 3001 (configurable via `BACKEND_PORT`)
- **Responsibilities**:
  - RESTful API endpoints
  - WebSocket communication via Socket.IO
  - Neo4j database integration
  - Python CLI process management
  - Docker container orchestration
  - Documentation file serving

## Styling Architecture

### Design Principles
- **Separation of Concerns**: All styling logic is separated from component code
- **Dark Theme First**: Application uses a dark color scheme by default
- **Material-UI Integration**: Leverages MUI theming for consistent design
- **CSS Modules**: Component-specific styles are isolated to prevent conflicts

### Styling Layers

1. **Global Styles** (`/renderer/src/index.css`)
   - Base resets and global element styles
   - Custom scrollbar styling
   - Terminal and Monaco editor base styles
   - Override styles for third-party components
   - Forced black AppBar/Toolbar styles

2. **Theme Configuration** (`/renderer/src/theme.ts`)
   - Material-UI theme customization
   - Color palette definitions
   - Typography settings
   - Component default props and overrides
   - Consistent spacing and borders

3. **Component Styles**
   - Inline sx props for dynamic styling
   - Material-UI styled components for complex styles
   - CSS classes for repeated patterns

### Color Palette

```typescript
// Primary Colors
Background: #1e1e1e (dark gray)
Paper: #2d2d30 (slightly lighter gray)
Primary: #0078d4 (Microsoft blue)
Secondary: #00bcf2 (cyan)
Text Primary: #cccccc (light gray)
Text Secondary: #969696 (medium gray)

// Status Colors
Success: #4caf50 (green)
Warning: #ff9800 (orange)
Error: #f44336 (red)
Info: #2196f3 (blue)

// AppBar Override
AppBar: #000000 (pure black - forced override)
```

### Styling Best Practices

1. **Use Theme Variables**: Always reference theme colors/spacing instead of hardcoded values
2. **Avoid Inline Styles**: Use sx prop or styled components instead
3. **Responsive Design**: Use MUI breakpoints for responsive layouts
4. **Consistent Spacing**: Use theme.spacing() for margins/padding
5. **Override Specificity**: Use !important sparingly, only for third-party overrides

## Component Architecture

### Core Components Structure

```
renderer/src/
├── components/
│   ├── common/           # Shared UI components
│   │   ├── ErrorBoundary.tsx
│   │   ├── Header.tsx
│   │   ├── LogViewer.tsx
│   │   ├── StatusBar.tsx     # Enhanced with tenant info & PIDs
│   │   └── TabNavigation.tsx # Updated tab order
│   ├── graph/           # Graph visualization
│   │   └── GraphVisualization.tsx
│   ├── tabs/            # Tab-specific components (12 tabs)
│   │   ├── StatusTab.tsx
│   │   ├── BuildTab.tsx     # Real-time WebSocket updates
│   │   ├── VisualizeTab.tsx
│   │   ├── DocsTab.tsx      # NEW: Documentation browser
│   │   ├── GenerateSpecTab.tsx
│   │   ├── GenerateIaCTab.tsx
│   │   ├── CreateTenantTab.tsx
│   │   ├── AgentModeTab.tsx
│   │   ├── ThreatModelTab.tsx
│   │   ├── LogsTab.tsx      # Monaco Editor integration
│   │   ├── CLITab.tsx       # xterm.js terminal
│   │   └── ConfigTab.tsx
│   └── widgets/         # Reusable widgets
│       └── GraphViewer.tsx
├── context/             # Global state management
│   └── AppContext.tsx   # Enhanced with structured logging
├── hooks/               # Custom React hooks
│   ├── useWebSocket.ts      # Auto-reconnection & buffering
│   ├── useLogger.ts         # Structured multi-source logging
│   ├── useBackgroundOperations.ts  # Process tracking
│   ├── useTenantName.ts     # NEW: Tenant identifier handling
│   └── useGraphAPI.ts
├── services/            # API services
├── types/               # TypeScript definitions
└── utils/               # Utility functions
    └── validation.ts
```

### Tab System Architecture

The application uses a comprehensive tab-based navigation system with 12 tabs in the following order:

1. **Status**: System status, connections, and health monitoring
2. **Build**: Azure tenant discovery and graph building with real-time progress
3. **Visualize**: Interactive graph visualization
4. **Docs**: Integrated documentation browser
5. **Generate Spec**: Specification generation from graph data
6. **Generate IaC**: Infrastructure-as-Code generation
7. **Create Tenant**: Tenant provisioning from specifications
8. **Agent Mode**: AI-powered agent interactions
9. **Threat Model**: Security analysis and threat modeling
10. **Logs**: Centralized logging with Monaco Editor
11. **CLI**: Interactive terminal interface with xterm.js
12. **Config**: Application and environment configuration

#### Tab Navigation Component (`TabNavigation.tsx`)
- Updated tab order and icons
- Material-UI scrollable tabs for responsive design
- React Router integration for URL-based navigation
- Consistent styling across all tabs

#### Enhanced Tab Components

**DocsTab.tsx** (NEW):
- Hierarchical file tree navigation
- Full markdown rendering with syntax highlighting
- Table of contents generation
- Search functionality across files and content
- Internal link navigation
- Collapsible sidebar with file browser

**BuildTab.tsx** (Enhanced):
- Real-time WebSocket updates during build operations
- Progress tracking with visual indicators
- Live streaming of build logs
- Process cancellation capabilities

**LogsTab.tsx** (Enhanced):
- Monaco Editor integration for advanced log viewing
- Syntax highlighting for structured logs
- Find and replace functionality
- Memory-efficient log buffering
- Real-time log streaming

**CLITab.tsx** (Enhanced):
- Full xterm.js terminal emulator
- Support for colors and terminal controls
- GUI launch hotkey ('g' key) integration
- Process tracking with PID display

### Shared Components

#### Enhanced StatusBar Component  
- **Tenant Information**: Displays "Tenant: [name]" extracted from configuration
- **Background Operations**: Shows running processes with PIDs
- **Connection Status**: Real-time WebSocket and database status
- **Performance Metrics**: Memory usage and system status
- **Process Indicators**: Visual chips for active background operations

#### Header Component
- Application title and branding
- Connection status indicators
- Quick access to common actions
- Theme toggle integration

#### Error Boundary
- Component-level error catching
- Graceful degradation with fallback UI
- Integration with structured logging system
- User-friendly error reporting

## Data Flow Architecture

### Enhanced State Management with Context API

```typescript
interface AppState {
  activeTab: string;
  currentOperation: any | null;
  isLoading: boolean;
  config: {
    tenantId: string;
    azureConfig: any;
    neo4jConfig: any;
  };
  results: Map<string, any>;
  logs: StructuredLogEntry[];
  logSettings: {
    autoScroll: boolean;
    showLevels: LogLevel[];
    searchFilter: string;
  };
  theme: 'light' | 'dark';
  backgroundOperations: Map<string, BackgroundOperation>;
  tenantName: string;  // NEW: Extracted tenant name
  websocketStatus: 'connected' | 'disconnected' | 'reconnecting';
}

interface StructuredLogEntry {
  id: string;
  timestamp: Date;
  level: LogLevel;
  source: string;  // API, Process, WebSocket, Graph, System
  message: string;
  data?: any;
}

interface BackgroundOperation {
  id: string;
  pid?: number;
  name: string;
  type: string;
  status: 'running' | 'completed' | 'failed';
  startTime: Date;
  endTime?: Date;
  progress?: number;
}
```

### Environment Variable Flow

```
1. .env file (project root)
   ↓
2. Electron Main Process (dotenv.config())
   ↓
3. Backend Server Process (environment inheritance)
   ↓
4. Frontend via /api/config/env endpoint
   ↓
5. React Context (secure environment variables only)
   ↓
6. useTenantName hook (tenant name extraction)
```

### Enhanced WebSocket Communication Layer

#### Connection Management
- **URL**: `http://localhost:3001`
- **Transport**: WebSocket with Socket.IO
- **Features**:
  - Exponential backoff reconnection (max 30s delay)
  - Memory-efficient output buffering (10k lines max per process)
  - Process subscription/unsubscription
  - Connection status monitoring
  - Real-time Build tab progress updates

#### Event Flow
```
Process Started → Backend → WebSocket → Frontend → UI Update
     ↓              ↓          ↓          ↓         ↓
CLI Command → Express API → Socket.IO → React Hook → Component Render
     ↓              ↓          ↓          ↓         ↓
Build Progress → Real-time → WebSocket → BuildTab → Progress Bars
```

### Background Operation Tracking

Enhanced multi-layer operation tracking:

1. **Process Manager (Main Process)**: Manages child processes with PIDs
2. **Backend Server**: Tracks API-initiated processes
3. **WebSocket Layer**: Real-time status updates with process subscription
4. **Frontend State**: UI-ready operation status with structured data
5. **Background Operations Hook**: Component-level integration
6. **StatusBar Display**: Visual indicators with process information

## Custom Hooks Architecture

### Enhanced useWebSocket Hook
```typescript
export function useWebSocket(options: WebSocketOptions = {}) {
  // Features:
  // - Exponential backoff reconnection (max 30s delay)
  // - Memory-efficient output buffering (10k lines max per process)
  // - Automatic process subscription management
  // - Connection status monitoring with state updates
  // - Process-specific output streaming
  // - Cleanup on component unmount
}
```

### Enhanced useLogger Hook
```typescript
export function useLogger(defaultSource: string = 'System') {
  // Features:
  // - Structured logging with timestamps
  // - Multiple sources (API, Process, WebSocket, Graph, System)
  // - Log levels (debug, info, warning, error)
  // - Specialized logging methods:
  //   - logApiCall(): HTTP request/response logging
  //   - logProcessEvent(): Process lifecycle events
  //   - logWebSocketEvent(): WebSocket connection events
  //   - logGraphOperation(): Neo4j operations
  // - Integration with Context API for global state
}
```

### NEW useTenantName Hook
```typescript
export const useTenantName = () => {
  // Features:
  // - Extracts tenant names from various sources
  // - Supports both domain names and UUIDs
  // - Fallback to environment variables
  // - Formatted display names for UI
  // - Real-time updates when configuration changes
}
```

### useBackgroundOperations Hook
```typescript
export const useBackgroundOperations = () => {
  // Features:
  // - Background operation lifecycle management
  // - Status updates and notifications
  // - Integration with global state
  // - PID tracking and display
  // - Process cancellation support
}
```

## Technology Stack

### Frontend Technologies
- **React 18**: Component framework with concurrent features
- **TypeScript**: Type safety and developer experience
- **Material-UI (MUI) v5**: Component library and design system
- **React Router v6**: Client-side routing
- **Emotion**: CSS-in-JS styling
- **Socket.IO Client**: Real-time communication

### Enhanced Editor and Terminal Integration
- **Monaco Editor**: VS Code editor integration for logs and code viewing
  - Syntax highlighting for structured logs
  - Find and replace functionality
  - Multiple cursor support
  - Minimap for navigation
- **xterm.js**: Full terminal emulator for CLI tab
  - Complete terminal capabilities
  - Copy/paste functionality
  - Colors and formatting support
  - Terminal history and scrollback buffer

### Documentation and Markdown
- **ReactMarkdown**: Markdown rendering with GitHub Flavored Markdown
- **react-syntax-highlighter**: Code syntax highlighting
- **rehype-raw**: HTML support in markdown
- **remark-gfm**: GitHub Flavored Markdown support

### Backend Technologies
- **Express.js**: Web server framework
- **Socket.IO**: Real-time bidirectional communication
- **Neo4j Driver**: Graph database connectivity
- **CORS**: Cross-origin resource sharing
- **UUID**: Unique identifier generation

### Graph Visualization
- **D3.js**: Data-driven document manipulation
- **vis-network**: Network visualization library
- **Custom graph algorithms**: Layout and interaction logic

### Development & Build Tools
- **Vite**: Fast build tool and dev server
- **Electron**: Desktop application framework (v27+)
- **Electron Builder**: Application packaging
- **Concurrently**: Parallel script execution
- **TSX**: TypeScript execution engine

## Security Architecture

### Process Isolation
- **Main Process**: Privileged operations (file system, processes)
- **Renderer Process**: Sandboxed web content with context isolation
- **Preload Script**: Controlled API exposure via `contextBridge`

### Environment Variable Security
```typescript
// Secure environment variable handling
app.get('/api/config/env', (req, res) => {
  res.json({
    AZURE_TENANT_ID: process.env.AZURE_TENANT_ID || '',
    AZURE_CLIENT_ID: process.env.AZURE_CLIENT_ID || '',
    // Secrets are not exposed - only flags
    HAS_AZURE_CLIENT_SECRET: !!process.env.AZURE_CLIENT_SECRET,
    NEO4J_URI: process.env.NEO4J_URI || 'bolt://localhost:7687',
    // ...other safe variables
  });
});
```

### IPC Security
- **Context Isolation**: Enabled for renderer process
- **Node Integration**: Disabled in renderer
- **Preload Script**: Controlled API surface
- **Channel Validation**: Whitelist of allowed IPC channels

## Performance Optimizations

### Memory Management

#### WebSocket Output Buffering
- Maximum 10,000 lines per process
- Automatic cleanup of old output
- Memory-efficient circular buffers
- Process-specific output isolation

#### React Optimizations
- Component lazy loading for large tabs
- Memoization of expensive computations
- Efficient re-rendering with proper key props
- Virtual scrolling for large log files

#### Background Process Management
- Process cleanup on application exit
- Graceful termination with SIGTERM
- Resource monitoring and limits
- PID tracking and management

### Network Optimizations

#### Enhanced WebSocket Connection Management
- Single persistent connection with multiplexing
- Efficient event routing and filtering
- Automatic reconnection with exponential backoff
- Process subscription management to reduce bandwidth

#### API Response Caching
- Strategic caching of configuration data
- Graph data pagination for large datasets
- Efficient data serialization
- Documentation file caching

## Key Design Patterns

### Observer Pattern
- WebSocket event handling with process subscriptions
- Process status notifications with PID tracking
- Log entry propagation with structured data
- Real-time Build tab updates

### Provider Pattern
- React Context for global state management
- Dependency injection for services
- Configuration management with validation
- Theme and preferences handling

### Command Pattern
- CLI command execution with process tracking
- Background operation management
- Process lifecycle control with cancellation
- Terminal command handling

### Factory Pattern
- Process creation and management
- WebSocket connection establishment
- Component instantiation with proper props
- Hook creation with configuration

### Facade Pattern
- Custom hooks abstract complex operations
- Service classes hide implementation details
- Unified API interfaces for consistency
- Terminal and editor integrations

## Recent Architectural Decisions

### 1. Enhanced Tab System (v1.1)
**Decision**: Implement 12-tab system with specific order and enhanced functionality
**Rationale**:
- Better organization of features
- Improved user workflow
- Clear feature separation
- Enhanced documentation integration

### 2. Documentation Integration (v1.1)
**Decision**: Add dedicated Docs tab with full markdown browser
**Rationale**:
- Integrated documentation access
- Better developer experience
- Searchable knowledge base
- Real-time file loading

### 3. Enhanced StatusBar (v1.1)
**Decision**: Add tenant information and process tracking to status bar
**Rationale**:
- Better user context awareness
- Real-time process monitoring
- Visual feedback for background operations
- Improved system transparency

### 4. Structured Logging System (v1.1)
**Decision**: Implement multi-source structured logging with Monaco Editor
**Rationale**:
- Better debugging capabilities
- Enhanced log viewing experience
- Source identification for troubleshooting
- Professional log analysis tools

### 5. Terminal Integration (v1.1)
**Decision**: Full xterm.js terminal emulator in CLI tab
**Rationale**:
- Complete terminal experience
- Better CLI integration
- Professional development environment
- GUI launch hotkey support

### 6. WebSocket Enhancements (v1.1)
**Decision**: Improve WebSocket reliability with better reconnection and buffering
**Rationale**:
- More reliable real-time updates
- Better Build tab progress tracking
- Memory-efficient operation
- Improved user experience during long operations

### 7. Tenant Name Extraction (v1.1)
**Decision**: Implement intelligent tenant name extraction and display
**Rationale**:
- Better user context
- Improved UX with readable tenant names
- Fallback handling for different identifier formats
- Enhanced status bar information

## Error Handling Strategy

### Frontend Error Boundaries
- Component-level error catching with graceful fallback
- Integration with structured logging system
- User-friendly error messages with context
- Automatic error reporting to logs

### Backend Error Handling
- Comprehensive try-catch blocks with logging
- Structured error responses with codes
- Process failure recovery mechanisms
- Resource cleanup on errors with proper disposal

### Process Management
- Graceful process termination with cleanup
- Timeout handling for long operations
- Resource leak prevention
- Automatic cleanup procedures with monitoring

## Testing Strategy

### Component Testing
- Jest with React Testing Library
- Component unit tests with mocking
- Custom hook testing with act()
- Snapshot testing for UI consistency

### Integration Testing
- Backend API testing with supertest
- WebSocket communication testing
- Process management testing
- Database integration testing with testcontainers

### End-to-End Testing
- Playwright for comprehensive E2E testing
- Full application workflow testing
- Cross-platform compatibility testing
- Performance testing with metrics

## Deployment Architecture

### Development Mode
```bash
npm run dev  # Concurrent processes:
├── Vite dev server (renderer) - port 5173
├── TypeScript watch (main) - compilation
├── tsx watch (backend) - port 3001
└── Hot reload enabled across all processes
```

### Production Build
```bash
npm run build     # Builds all processes:
├── Renderer build (Vite)
├── Main process build (TypeScript)
├── Backend build (TypeScript)
└── Asset optimization and bundling

npm run package   # Creates distributable:
├── Electron Builder packaging
├── Platform-specific optimization
├── Code signing (when configured)
└── Asset bundling and compression
```

### Application Structure
- **Default Window Size**: 1600x1000 pixels
- **Minimum Window Size**: 1200x800 pixels
- **Cross-platform Support**: macOS, Windows, Linux
- **Auto-updater Ready**: Future enhancement capability
- **Code Signing Support**: macOS and Windows ready

This enhanced architecture provides a robust, scalable, and maintainable foundation for the Azure Tenant Grapher SPA, with comprehensive documentation integration, real-time monitoring, structured logging, and professional development tools.