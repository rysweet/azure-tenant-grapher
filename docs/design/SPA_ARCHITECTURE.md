# Azure Tenant Grapher SPA Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Electron Application                      │
├───────────────────────────┬─────────────────────────────────┤
│      Main Process         │       Renderer Process           │
│  ┌──────────────────┐     │    ┌─────────────────────┐      │
│  │   IPC Handlers   │◄────┼───►│   React Frontend    │      │
│  │                  │     │    │   - Tabs/Routes     │      │
│  │  ┌────────────┐  │     │    │   - Components      │      │
│  │  │Process Mgr │  │     │    │   - State Mgmt      │      │
│  │  └────────────┘  │     │    └─────────────────────┘      │
│  │                  │     │                                  │
│  │  ┌────────────┐  │     │    ┌─────────────────────┐      │
│  │  │ CLI Bridge │  │     │    │   Context API       │      │
│  │  └────────────┘  │     │    │   - App State      │      │
│  │                  │     │    │   - User Prefs      │      │
│  └──────────────────┘     │    └─────────────────────┘      │
└───────────────────────────┴─────────────────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   Local Backend API   │
                    │   - Express Server    │
                    │   - WebSocket for logs│
                    └──────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   CLI Subprocess      │
                    │   - Python scripts    │
                    │   - Neo4j interaction │
                    └──────────────────────┘
```

## Component Architecture

### 1. Electron Main Process (`/spa/main/`)

#### Core Modules
- **`index.ts`**: Entry point, app lifecycle management
- **`ipc-handlers.ts`**: IPC communication handlers
- **`process-manager.ts`**: CLI subprocess management
- **`window-manager.ts`**: Window creation and management
- **`menu.ts`**: Application menu configuration

#### Key Responsibilities
- Application lifecycle (start, stop, restart)
- Window management
- IPC routing between renderer and backend
- Process spawning and management
- File system operations
- Native dialog integration

### 2. Renderer Process (`/spa/renderer/`)

#### React Application Structure
```
renderer/
├── src/
│   ├── App.tsx                 # Main app component
│   ├── components/
│   │   ├── common/             # Shared components
│   │   │   ├── Header.tsx
│   │   │   ├── TabNavigation.tsx
│   │   │   ├── StatusBar.tsx
│   │   │   └── LogViewer.tsx
│   │   ├── tabs/               # Feature tabs
│   │   │   ├── BuildTab.tsx
│   │   │   ├── GenerateSpecTab.tsx
│   │   │   ├── GenerateIaCTab.tsx
│   │   │   ├── CreateTenantTab.tsx
│   │   │   ├── VisualizeTab.tsx
│   │   │   ├── AgentModeTab.tsx
│   │   │   ├── ThreatModelTab.tsx
│   │   │   └── ConfigTab.tsx
│   │   └── widgets/            # Reusable widgets
│   │       ├── CodeEditor.tsx
│   │       ├── GraphViewer.tsx
│   │       └── ProgressTracker.tsx
│   ├── hooks/                  # Custom React hooks
│   │   ├── useIPC.ts
│   │   ├── useWebSocket.ts
│   │   └── useLocalStorage.ts
│   ├── services/               # Frontend services
│   │   ├── api.ts
│   │   ├── ipc.ts
│   │   └── websocket.ts
│   ├── context/                # React Context providers
│   │   ├── AppContext.tsx
│   │   └── ThemeContext.tsx
│   ├── utils/                  # Utility functions
│   └── types/                  # TypeScript definitions
```

### 3. Backend API Server (`/spa/backend/`)

#### Express Server Structure
```
backend/
├── src/
│   ├── server.ts               # Express server setup
│   ├── routes/                 # API routes
│   │   ├── build.ts
│   │   ├── generate.ts
│   │   ├── tenant.ts
│   │   ├── visualize.ts
│   │   └── config.ts
│   ├── services/               # Backend services
│   │   ├── cli-executor.ts    # CLI command execution
│   │   ├── process-pool.ts    # Process management
│   │   ├── log-streamer.ts    # Log streaming
│   │   └── file-manager.ts    # File operations
│   ├── middleware/             # Express middleware
│   │   ├── error-handler.ts
│   │   ├── validator.ts
│   │   └── logger.ts
│   └── websocket/              # WebSocket handlers
│       └── log-handler.ts
```

### 4. IPC Communication

#### Channel Structure
```typescript
interface IPCChannels {
  // Command execution
  'cli:execute': (command: string, args: string[]) => Promise<ExecutionResult>;
  'cli:cancel': (processId: string) => Promise<void>;
  
  // File operations
  'file:read': (path: string) => Promise<string>;
  'file:write': (path: string, content: string) => Promise<void>;
  'file:dialog': (options: DialogOptions) => Promise<string[]>;
  
  // App lifecycle
  'app:quit': () => void;
  'app:minimize': () => void;
  'app:maximize': () => void;
  
  // Configuration
  'config:get': (key: string) => Promise<any>;
  'config:set': (key: string, value: any) => Promise<void>;
}
```

### 5. Process Management

#### CLI Command Execution Flow
1. **User Action**: User clicks button in UI
2. **IPC Request**: Renderer sends IPC message to main
3. **Process Spawn**: Main spawns Python subprocess
4. **Output Streaming**: Stdout/stderr streamed via WebSocket
5. **Result Return**: Final result sent back via IPC
6. **UI Update**: Renderer updates UI with results

#### Process Pool Management
```typescript
class ProcessPool {
  private processes: Map<string, ChildProcess>;
  private maxConcurrent: number = 5;
  
  async execute(command: CLICommand): Promise<ExecutionResult> {
    const process = spawn('python', ['-m', 'src.cli', ...command.args]);
    this.processes.set(command.id, process);
    
    // Stream output
    process.stdout.on('data', (data) => {
      this.streamToWebSocket(command.id, data);
    });
    
    // Handle completion
    process.on('exit', (code) => {
      this.processes.delete(command.id);
      this.resolveCommand(command.id, code);
    });
  }
}
```

### 6. State Management

#### Frontend State (React Context)
```typescript
interface AppState {
  // Current operation
  currentOperation: Operation | null;
  isLoading: boolean;
  
  // Configuration
  config: {
    tenantId: string;
    azureConfig: AzureConfig;
    neo4jConfig: Neo4jConfig;
  };
  
  // Results cache
  results: Map<string, any>;
  
  // UI state
  activeTab: string;
  theme: 'light' | 'dark';
  preferences: UserPreferences;
}
```

#### Backend State
- Process pool status
- Active subprocess PIDs
- WebSocket connections
- File system watchers
- Cache management

### 7. Security Architecture

#### Process Isolation
- Renderer process runs in sandboxed context
- No direct file system access from renderer
- All operations proxied through IPC

#### Secret Management
- Environment variables loaded in main process only
- Secrets never sent to renderer
- Secure storage for sensitive configs

#### Input Validation
- All IPC messages validated
- Command injection prevention
- Path traversal protection

### 8. Testing Architecture

#### Unit Testing
```typescript
// Component testing
describe('BuildTab', () => {
  it('should validate tenant ID input', () => {
    const { getByRole } = render(<BuildTab />);
    const input = getByRole('textbox', { name: /tenant id/i });
    // Test validation logic
  });
});

// Service testing
describe('CLIExecutor', () => {
  it('should spawn process with correct arguments', async () => {
    const result = await executor.execute('build', ['--tenant-id', 'test']);
    expect(spawn).toHaveBeenCalledWith('python', expect.arrayContaining(['-m', 'src.cli', 'build']));
  });
});
```

#### Integration Testing
```typescript
// IPC integration
describe('IPC Integration', () => {
  it('should execute CLI command through IPC', async () => {
    const result = await ipcRenderer.invoke('cli:execute', 'build', ['--tenant-id', 'test']);
    expect(result.exitCode).toBe(0);
  });
});
```

#### E2E Testing with Playwright
```typescript
// Full workflow testing
test('Build workflow', async ({ electronApp }) => {
  const window = await electronApp.firstWindow();
  await window.click('[data-testid="build-tab"]');
  await window.fill('[data-testid="tenant-id-input"]', 'test-tenant');
  await window.click('[data-testid="build-button"]');
  await expect(window.locator('[data-testid="success-message"]')).toBeVisible();
});
```

### 9. Build and Deployment

#### Development Build
```json
{
  "scripts": {
    "dev": "concurrently \"npm run dev:main\" \"npm run dev:renderer\" \"npm run dev:backend\"",
    "dev:main": "tsc -w -p main/",
    "dev:renderer": "vite",
    "dev:backend": "nodemon backend/src/server.ts"
  }
}
```

#### Production Build
```json
{
  "scripts": {
    "build": "npm run build:renderer && npm run build:main && npm run build:backend",
    "package": "electron-builder",
    "package:all": "electron-builder -mwl"
  }
}
```

### 10. Performance Considerations

#### Optimization Strategies
- Lazy loading of tab components
- Virtual scrolling for large logs
- Debounced input validation
- Memoized expensive computations
- Process output buffering
- WebSocket message batching

#### Resource Management
- Process pool limiting
- Memory usage monitoring
- Automatic cleanup on exit
- Cache eviction policies

## Technology Decisions

### Why Electron?
- Cross-platform desktop support
- Native file system access
- Process management capabilities
- Rich ecosystem

### Why React?
- Component reusability
- Strong TypeScript support
- Extensive testing tools
- Large community

### Why Express Backend?
- Separation of concerns
- WebSocket support
- Middleware ecosystem
- Easy subprocess integration

### Why WebSockets for Logs?
- Real-time streaming
- Bidirectional communication
- Efficient for high-frequency updates
- Browser native support