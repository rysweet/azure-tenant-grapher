# Scale Operations Architecture Diagram

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ELECTRON SPA (Frontend)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │                      ScaleOperationsTab                             │    │
│  │                    (Main Container Component)                       │    │
│  └────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                    ┌───────────────┼───────────────┐                       │
│                    │               │               │                        │
│                    ▼               ▼               ▼                        │
│         ┌─────────────────┐ ┌─────────────┐ ┌──────────────┐             │
│         │  ScaleUpPanel   │ │ScaleDownPanel│ │ProgressMonitor│             │
│         └─────────────────┘ └─────────────┘ └──────────────┘             │
│                    │               │               │                        │
│                    └───────────────┼───────────────┘                       │
│                                    │                                         │
│                                    ▼                                         │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │              ScaleOperationsContext (State Management)              │   │
│  │  ┌──────────────────────────────────────────────────────────────┐  │   │
│  │  │ State:                                                        │  │   │
│  │  │  - operationType: 'scale-up' | 'scale-down'                  │  │   │
│  │  │  - scaleUpConfig: ScaleUpConfig                              │  │   │
│  │  │  - scaleDownConfig: ScaleDownConfig                          │  │   │
│  │  │  - currentOperation: { processId, status, progress, logs }  │  │   │
│  │  │  - lastResult: OperationResult                               │  │   │
│  │  │  - error: string | null                                      │  │   │
│  │  └──────────────────────────────────────────────────────────────┘  │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                    ┌───────────────┼───────────────┐                       │
│                    │               │               │                        │
│                    ▼               ▼               ▼                        │
│  ┌──────────────────────┐ ┌──────────────────┐ ┌────────────────┐        │
│  │ useScaleUpOperation  │ │useScaleDownOp... │ │ useWebSocket   │        │
│  │  - executeScaleUp()  │ │  - execute...()  │ │  - subscribe() │        │
│  │  - previewScaleUp()  │ │  - preview...()  │ │  - getOutput() │        │
│  │  - cancelOperation() │ │  - cancel...()   │ │  - isConnected │        │
│  └──────────────────────┘ └──────────────────┘ └────────────────┘        │
│            │                        │                      │                │
│            └────────────────────────┼──────────────────────┘               │
│                                     │                                       │
└─────────────────────────────────────┼───────────────────────────────────────┘
                                      │
                 ┌────────────────────┼────────────────────┐
                 │                    │                    │
                 ▼                    ▼                    ▼
        ┌─────────────────┐  ┌──────────────────┐  ┌─────────────┐
        │   HTTP/REST     │  │   WebSocket      │  │  Socket.IO  │
        │  (axios calls)  │  │  (real-time)     │  │  (events)   │
        └─────────────────┘  └──────────────────┘  └─────────────┘
                 │                    │                    │
                 └────────────────────┼────────────────────┘
                                      │
┌─────────────────────────────────────┼───────────────────────────────────────┐
│                           EXPRESS BACKEND                                    │
├─────────────────────────────────────┼───────────────────────────────────────┤
│                                     │                                        │
│  ┌──────────────────────────────────▼─────────────────────────────────┐   │
│  │                        API Endpoints                                 │   │
│  │  POST /api/scale/up/execute                                         │   │
│  │  POST /api/scale/up/preview                                         │   │
│  │  POST /api/scale/down/execute                                       │   │
│  │  POST /api/scale/down/preview                                       │   │
│  │  POST /api/scale/cancel/:processId                                  │   │
│  │  GET  /api/scale/status/:processId                                  │   │
│  │  POST /api/scale/clean-synthetic                                    │   │
│  │  POST /api/scale/validate                                           │   │
│  │  GET  /api/scale/stats/:tenantId                                    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                     │                                        │
│                                     ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Process Manager                                   │   │
│  │  - Spawns Python CLI processes                                      │   │
│  │  - Manages process lifecycle                                        │   │
│  │  - Buffers and streams output                                       │   │
│  │  - Emits Socket.IO events                                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                     │                                        │
│                     ┌───────────────┼───────────────┐                      │
│                     │               │               │                       │
│                     ▼               ▼               ▼                       │
│         ┌──────────────────┐ ┌────────────┐ ┌────────────────┐           │
│         │  Socket.IO       │ │ Neo4j      │ │  File System   │           │
│         │  Event Emitter   │ │ Service    │ │  Operations    │           │
│         └──────────────────┘ └────────────┘ └────────────────┘           │
│                     │               │               │                       │
└─────────────────────┼───────────────┼───────────────┼───────────────────────┘
                      │               │               │
        ┌─────────────┴───────────────┴───────────────┴──────────────┐
        │                                                              │
        ▼                                                              ▼
┌──────────────────┐                                      ┌────────────────────┐
│   WebSocket      │                                      │  Python CLI        │
│   Transport      │                                      │  (uv run atg)      │
│                  │                                      └────────────────────┘
│  Events:         │                                                 │
│  - scale:output  │                                                 ▼
│  - scale:progress│                                      ┌────────────────────┐
│  - scale:complete│                                      │  Scale Commands    │
│  - scale:error   │                                      │                    │
└──────────────────┘                                      │  scale-up          │
                                                           │  scale-down        │
                                                           │  validate          │
                                                           │  stats             │
                                                           └────────────────────┘
                                                                    │
                                                    ┌───────────────┼───────────────┐
                                                    │               │               │
                                                    ▼               ▼               ▼
                                          ┌─────────────┐  ┌──────────────┐ ┌──────────┐
                                          │ Scale-Up    │  │ Scale-Down   │ │ Neo4j    │
                                          │ Service     │  │ Service      │ │ Graph DB │
                                          └─────────────┘  └──────────────┘ └──────────┘
                                                    │               │               │
                                                    └───────────────┼───────────────┘
                                                                    │
                                                                    ▼
                                                          ┌────────────────────┐
                                                          │  Neo4j Database    │
                                                          │                    │
                                                          │  - Original Nodes  │
                                                          │  - Abstracted Nodes│
                                                          │  - Synthetic Nodes │
                                                          │  - Relationships   │
                                                          └────────────────────┘
```

## Data Flow - Scale-Up Operation

```
┌──────────────┐
│   User       │
│  Interface   │
└──────┬───────┘
       │ 1. User clicks "Execute Scale-Up"
       │    with configuration
       ▼
┌──────────────────────────────────┐
│  ScaleUpPanel Component          │
│  - Validates input                │
│  - Builds ScaleUpConfig object   │
└──────┬───────────────────────────┘
       │ 2. Call executeScaleUp(config)
       ▼
┌──────────────────────────────────┐
│  useScaleUpOperation Hook        │
│  - Dispatches START_OPERATION    │
│  - Makes HTTP POST request       │
└──────┬───────────────────────────┘
       │ 3. POST /api/scale/up/execute
       │    Body: { tenantId, strategy, ... }
       ▼
┌──────────────────────────────────┐
│  Express Backend API             │
│  - Validates request              │
│  - Generates processId            │
└──────┬───────────────────────────┘
       │ 4. Spawns Python CLI process
       │    $ uv run atg scale-up --tenant-id xxx ...
       ▼
┌──────────────────────────────────┐
│  Process Manager                 │
│  - Spawns child process           │
│  - Captures stdout/stderr         │
│  - Stores process reference       │
└──────┬───────────────────────────┘
       │ 5. Returns processId to frontend
       ▼
┌──────────────────────────────────┐
│  Frontend receives processId     │
│  - Updates state: status=running │
│  - Subscribes to WebSocket       │
└──────┬───────────────────────────┘
       │
       │ ┌─────────────────────────────────────┐
       │ │  Real-time Updates (WebSocket)      │
       │ └─────────────────────────────────────┘
       │
       │ 6. Python CLI starts executing
       ▼
┌──────────────────────────────────┐
│  Python Scale-Up Service         │
│  ┌────────────────────────────┐  │
│  │ Phase 1: Validation        │  │  ───► Emits: scale:output
│  │  - Check graph state       │  │       { type: 'stdout', data: [...] }
│  │  - Validate config         │  │
│  └────────────────────────────┘  │
│  ┌────────────────────────────┐  │
│  │ Phase 2: Generate Nodes    │  │  ───► Emits: scale:progress
│  │  - Create synthetic nodes  │  │       { progress: 30, phase: 'Creating nodes' }
│  │  - Apply templates         │  │
│  └────────────────────────────┘  │
│  ┌────────────────────────────┐  │
│  │ Phase 3: Build Relations   │  │  ───► Emits: scale:output
│  │  - Create relationships    │  │       { data: ['Created 1000 relationships'] }
│  │  - Link to existing nodes  │  │
│  └────────────────────────────┘  │
│  ┌────────────────────────────┐  │
│  │ Phase 4: Validation        │  │  ───► Emits: scale:progress
│  │  - Run consistency checks  │  │       { progress: 90, stats: {...} }
│  │  - Verify graph integrity  │  │
│  └────────────────────────────┘  │
└──────┬───────────────────────────┘
       │ 7. Operation completes
       │    Exit code: 0 (success) or 1 (error)
       ▼
┌──────────────────────────────────┐
│  Process Manager                 │
│  - Captures exit code             │
│  - Emits completion event         │
└──────┬───────────────────────────┘
       │ 8. Emits: scale:complete
       │    { processId, result: {...} }
       ▼
┌──────────────────────────────────┐
│  Frontend WebSocket Listener     │
│  - Receives completion event      │
│  - Dispatches OPERATION_COMPLETE │
└──────┬───────────────────────────┘
       │ 9. Updates UI state
       ▼
┌──────────────────────────────────┐
│  ProgressMonitor → ResultsPanel  │
│  - Shows completion status        │
│  - Displays before/after stats    │
│  - Shows validation results       │
└───────────────────────────────────┘
```

## Component Communication Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Component Communication                          │
└─────────────────────────────────────────────────────────────────────────┘

  ScaleOperationsTab
        │
        │ Props: none (uses context)
        │ Context: ScaleOperationsContext
        │
        ├─────► ScaleUpPanel
        │         │
        │         │ Props: none
        │         │ Context: ScaleOperationsContext
        │         │ Hooks: useScaleUpOperation, useApp
        │         │
        │         └─────► User interactions:
        │                   - Fill form fields
        │                   - Click "Preview"  ──► previewScaleUp(config)
        │                   - Click "Execute"  ──► executeScaleUp(config)
        │                                            │
        │                                            ├─► HTTP POST to backend
        │                                            └─► Subscribe to WebSocket
        │
        ├─────► ScaleDownPanel
        │         │
        │         │ (Similar to ScaleUpPanel)
        │         │
        │
        ├─────► ProgressMonitor
        │         │
        │         │ Props: none
        │         │ Context: ScaleOperationsContext
        │         │ Hooks: useWebSocket, useScaleUpOperation
        │         │
        │         │ State updates via WebSocket:
        │         │   - output events ──► append to logs
        │         │   - progress events ──► update progress bar
        │         │   - complete events ──► show results
        │         │
        │         └─────► Sub-components:
        │                   - ProgressBar (Material-UI)
        │                   - StatisticsGrid (custom)
        │                   - LogViewer (reused from common)
        │
        ├─────► ResultsPanel
        │         │
        │         │ Props: result: OperationResult
        │         │ Context: ScaleOperationsContext
        │         │
        │         └─────► Display:
        │                   - Operation summary
        │                   - Before/after comparison
        │                   - Validation results
        │                   - Action buttons
        │
        └─────► QuickActionsBar
                  │
                  │ Props: none
                  │ Context: ScaleOperationsContext
                  │
                  └─────► Actions:
                            - Clean synthetic data
                            - Validate graph
                            - Show statistics
```

## State Management Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ScaleOperationsContext State Flow                     │
└─────────────────────────────────────────────────────────────────────────┘

  Initial State
  ┌────────────────────────────────────┐
  │ operationType: 'scale-up'          │
  │ scaleUpConfig: { ... }             │
  │ currentOperation: {                │
  │   processId: null,                 │
  │   status: 'idle',                  │
  │   progress: null,                  │
  │   logs: []                         │
  │ }                                  │
  │ lastResult: null                   │
  │ error: null                        │
  └────────────────────────────────────┘
           │
           │ Action: UPDATE_SCALE_UP_CONFIG
           │ Payload: { tenantId: 'xxx', strategy: 'template' }
           ▼
  ┌────────────────────────────────────┐
  │ scaleUpConfig: {                   │
  │   tenantId: 'xxx',                 │
  │   strategy: 'template',            │
  │   validate: true,                  │
  │   ...                              │
  │ }                                  │
  └────────────────────────────────────┘
           │
           │ Action: START_OPERATION
           │ Payload: { processId: 'abc-123' }
           ▼
  ┌────────────────────────────────────┐
  │ currentOperation: {                │
  │   processId: 'abc-123',            │
  │   status: 'running',               │
  │   progress: {                      │
  │     progress: 0,                   │
  │     phase: 'Initializing',         │
  │     ...                            │
  │   },                               │
  │   logs: []                         │
  │ }                                  │
  └────────────────────────────────────┘
           │
           │ Action: UPDATE_PROGRESS (via WebSocket)
           │ Payload: { progress: 50, phase: 'Creating nodes', stats: {...} }
           ▼
  ┌────────────────────────────────────┐
  │ currentOperation: {                │
  │   processId: 'abc-123',            │
  │   status: 'running',               │
  │   progress: {                      │
  │     progress: 50,                  │
  │     phase: 'Creating nodes',       │
  │     stats: { nodesCreated: 500 }   │
  │   },                               │
  │   logs: ['...']                    │
  │ }                                  │
  └────────────────────────────────────┘
           │
           │ Action: APPEND_LOGS (via WebSocket)
           │ Payload: ['INFO: Created 100 nodes', ...]
           ▼
  ┌────────────────────────────────────┐
  │ currentOperation: {                │
  │   ...                              │
  │   logs: [                          │
  │     'INFO: Created 100 nodes',     │
  │     'INFO: Building relationships',│
  │     ...                            │
  │   ]                                │
  │ }                                  │
  └────────────────────────────────────┘
           │
           │ Action: OPERATION_COMPLETE (via WebSocket)
           │ Payload: { success: true, beforeStats: {...}, afterStats: {...} }
           ▼
  ┌────────────────────────────────────┐
  │ currentOperation: {                │
  │   processId: null,                 │
  │   status: 'success',               │
  │   progress: { progress: 100 },     │
  │   logs: [...]                      │
  │ }                                  │
  │ lastResult: {                      │
  │   success: true,                   │
  │   operationType: 'scale-up',       │
  │   beforeStats: { ... },            │
  │   afterStats: { ... },             │
  │   scaleUpStats: { ... },           │
  │   validationResults: [...]         │
  │ }                                  │
  │ showResults: true                  │
  └────────────────────────────────────┘
```

## WebSocket Event Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      WebSocket Event Timeline                            │
└─────────────────────────────────────────────────────────────────────────┘

Frontend                          Backend                      Python CLI
   │                                 │                              │
   │ 1. Connect WebSocket            │                              │
   ├────────────────────────────────►│                              │
   │                                 │                              │
   │ 2. Execute operation            │                              │
   ├────────────────────────────────►│ 3. Spawn process             │
   │    POST /api/scale/up/execute   ├─────────────────────────────►│
   │                                 │                              │
   │ 4. Subscribe to process         │                              │
   ├────────────────────────────────►│                              │
   │    emit('subscribe', processId) │                              │
   │                                 │                              │
   │                                 │         5. CLI starts        │
   │                                 │◄─────────────────────────────┤
   │                                 │         stdout: "Starting..."│
   │                                 │                              │
   │ 6. Receive output               │                              │
   │◄────────────────────────────────┤                              │
   │    on('output', { data: [...] })│                              │
   │                                 │                              │
   │                                 │         7. CLI progresses    │
   │                                 │◄─────────────────────────────┤
   │                                 │         stdout: "Created 500"│
   │                                 │                              │
   │ 8. Receive progress update      │                              │
   │◄────────────────────────────────┤                              │
   │    on('scale:progress', {...})  │                              │
   │                                 │                              │
   │        [...continuous output and progress events...]          │
   │                                 │                              │
   │                                 │         9. CLI completes     │
   │                                 │◄─────────────────────────────┤
   │                                 │         exit code: 0         │
   │                                 │                              │
   │ 10. Receive completion          │                              │
   │◄────────────────────────────────┤                              │
   │    on('scale:complete', result) │                              │
   │                                 │                              │
   │ 11. Update UI to show results   │                              │
   │                                 │                              │
   │ 12. Unsubscribe                 │                              │
   ├────────────────────────────────►│                              │
   │    emit('unsubscribe', processId)                              │
   │                                 │                              │
```

## Backend API Route Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Express Backend Routes                                │
└─────────────────────────────────────────────────────────────────────────┘

/api/scale
  │
  ├─ /up
  │   ├─ POST /execute
  │   │    ├─ Validate request body (ScaleUpConfig)
  │   │    ├─ Generate unique processId
  │   │    ├─ Build CLI command: ["scale-up", "--tenant-id", ...]
  │   │    ├─ Spawn process via ProcessManager
  │   │    └─ Return { processId, success: true }
  │   │
  │   └─ POST /preview
  │        ├─ Validate request body (ScaleUpConfig)
  │        ├─ Call Python CLI with --dry-run flag
  │        ├─ Parse output for estimates
  │        └─ Return { estimatedNodes, estimatedRelationships, ... }
  │
  ├─ /down
  │   ├─ POST /execute
  │   │    ├─ Validate request body (ScaleDownConfig)
  │   │    ├─ Generate unique processId
  │   │    ├─ Build CLI command: ["scale-down", "--algorithm", ...]
  │   │    ├─ Spawn process via ProcessManager
  │   │    └─ Return { processId, success: true }
  │   │
  │   └─ POST /preview
  │        ├─ Validate request body (ScaleDownConfig)
  │        ├─ Call Python CLI with --dry-run flag
  │        └─ Return preview result
  │
  ├─ POST /cancel/:processId
  │    ├─ Lookup process by processId
  │    ├─ Kill process (SIGTERM)
  │    ├─ Cleanup resources
  │    └─ Return { success: true }
  │
  ├─ GET /status/:processId
  │    ├─ Lookup process by processId
  │    ├─ Return current status, progress, logs
  │    └─ Return { status, progress, logs }
  │
  ├─ POST /clean-synthetic
  │    ├─ Validate tenantId in body
  │    ├─ Call Python CLI: ["clean-synthetic", "--tenant-id", ...]
  │    ├─ Wait for completion
  │    └─ Return { nodesDeleted, success: true }
  │
  ├─ POST /validate
  │    ├─ Validate tenantId in body
  │    ├─ Call Python CLI: ["validate-graph", "--tenant-id", ...]
  │    ├─ Parse validation results
  │    └─ Return [ { checkName, passed, message }, ... ]
  │
  └─ GET /stats/:tenantId
       ├─ Query Neo4j for graph statistics
       ├─ Aggregate node counts, relationship counts
       ├─ Identify synthetic nodes
       └─ Return { totalNodes, totalRelationships, syntheticNodes, ... }
```

## Neo4j Query Patterns

```
┌─────────────────────────────────────────────────────────────────────────┐
│                  Neo4j Queries for Scale Operations                      │
└─────────────────────────────────────────────────────────────────────────┘

1. Get Graph Statistics
   ┌────────────────────────────────────────────────────────────────┐
   │ MATCH (n)                                                       │
   │ WHERE n.tenant_id = $tenantId                                   │
   │ WITH count(n) as totalNodes,                                    │
   │      count(CASE WHEN n.synthetic = true THEN 1 END) as synthetic│
   │ MATCH ()-[r]->()                                                │
   │ RETURN totalNodes, synthetic, count(r) as totalRelationships    │
   └────────────────────────────────────────────────────────────────┘

2. Identify Synthetic Nodes
   ┌────────────────────────────────────────────────────────────────┐
   │ MATCH (n:Synthetic)                                             │
   │ WHERE n.tenant_id = $tenantId                                   │
   │ RETURN n.id, n.type, n.properties                               │
   │ ORDER BY n.created_at DESC                                      │
   └────────────────────────────────────────────────────────────────┘

3. Clean Synthetic Data
   ┌────────────────────────────────────────────────────────────────┐
   │ MATCH (n:Synthetic)                                             │
   │ WHERE n.tenant_id = $tenantId                                   │
   │ WITH count(n) as deletedCount                                   │
   │ MATCH (n:Synthetic)                                             │
   │ WHERE n.tenant_id = $tenantId                                   │
   │ DETACH DELETE n                                                 │
   │ RETURN deletedCount                                             │
   └────────────────────────────────────────────────────────────────┘

4. Validate Graph Consistency
   ┌────────────────────────────────────────────────────────────────┐
   │ // Check for orphaned nodes                                     │
   │ MATCH (n)                                                       │
   │ WHERE n.tenant_id = $tenantId                                   │
   │   AND NOT (n)-[]-()                                             │
   │ RETURN count(n) as orphanedNodes                                │
   │                                                                 │
   │ // Check for duplicate IDs                                      │
   │ MATCH (n)                                                       │
   │ WHERE n.tenant_id = $tenantId                                   │
   │ WITH n.id as nodeId, count(*) as occurrences                    │
   │ WHERE occurrences > 1                                           │
   │ RETURN count(nodeId) as duplicateIds                            │
   └────────────────────────────────────────────────────────────────┘

5. Sample Subgraph (Scale-Down)
   ┌────────────────────────────────────────────────────────────────┐
   │ // Forest-Fire sampling                                         │
   │ MATCH path = (start)-[*1..3]->(neighbor)                        │
   │ WHERE start.tenant_id = $tenantId                               │
   │   AND start.id = $seedNodeId                                    │
   │ WITH nodes(path) as pathNodes                                   │
   │ UNWIND pathNodes as n                                           │
   │ RETURN DISTINCT n                                               │
   │ LIMIT $sampleSize                                               │
   └────────────────────────────────────────────────────────────────┘
```

## Error Handling Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Error Handling Flow                              │
└─────────────────────────────────────────────────────────────────────────┘

Error Source                      Handler                         UI Response
─────────────                     ───────                         ───────────

Frontend Validation
  - Missing tenant ID          ──► Form validation            ──► Red border, error text
  - Invalid format             ──► isValidTenantId()          ──► Alert with message
  - Missing required fields    ──► Button disabled            ──► Tooltip explanation

Backend API Errors
  - 400 Bad Request            ──► axios catch block          ──► Alert: "Invalid request"
  - 404 Not Found              ──► axios catch block          ──► Alert: "Resource not found"
  - 500 Server Error           ──► axios catch block          ──► Alert: "Server error"
  - Network timeout            ──► axios catch block          ──► Alert: "Connection timeout"
                                                                   [Retry] button

Python CLI Errors
  - Exit code 1                ──► ProcessManager            ──► Alert: "Operation failed"
  - Validation failure         ──► Parse stderr              ──► Show validation errors
  - Neo4j connection error     ──► Parse stderr              ──► Alert: "Database error"
  - Permission denied          ──► Parse stderr              ──► Alert: "Permission error"

WebSocket Errors
  - Disconnection              ──► useWebSocket hook         ──► Warning banner
  - Reconnection failed        ──► Exponential backoff       ──► "Reconnecting..." indicator
  - Event parse error          ──► try/catch in listener     ──► Log error, continue

Neo4j Errors
  - Query timeout              ──► Neo4j driver exception    ──► Alert: "Query timeout"
  - Connection lost            ──► Neo4j driver exception    ──► Alert: "Database unavailable"
  - Invalid Cypher             ──► Parse error message       ──► Alert: "Query error"

Operation Timeouts
  - No progress updates        ──► setTimeout in frontend    ──► Alert: "Operation timed out"
  - Process hangs              ──► Backend timeout           ──► Force kill process
                                                                   Alert: "Operation cancelled"
```

## Testing Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Testing Strategy                                │
└─────────────────────────────────────────────────────────────────────────┘

Unit Tests (Jest + React Testing Library)
  ├─ Context & Reducers
  │   ├─ ScaleOperationsContext
  │   │   ├─ Initial state is correct
  │   │   ├─ Actions update state correctly
  │   │   └─ Error states handled properly
  │   └─ Reducer logic
  │       ├─ State transitions
  │       └─ Immutability preserved
  │
  ├─ Custom Hooks
  │   ├─ useScaleUpOperation
  │   │   ├─ Execute operation returns processId
  │   │   ├─ Preview operation returns estimates
  │   │   ├─ Cancel operation stops process
  │   │   └─ Error handling works
  │   └─ useScaleDownOperation
  │       └─ (Similar tests)
  │
  └─ Utility Functions
      ├─ Validation functions
      ├─ Data formatters
      └─ Error parsers

Integration Tests (Jest + React Testing Library)
  ├─ Component Interactions
  │   ├─ ScaleUpPanel
  │   │   ├─ Form field changes update state
  │   │   ├─ Preview button triggers API call
  │   │   ├─ Execute button starts operation
  │   │   └─ Validation errors shown
  │   └─ ProgressMonitor
  │       ├─ Displays progress updates
  │       ├─ Logs stream correctly
  │       └─ Stop button works
  │
  └─ Context Integration
      ├─ Components read from context
      ├─ Components dispatch actions
      └─ State updates trigger re-renders

E2E Tests (Playwright)
  ├─ Complete Workflows
  │   ├─ Scale-Up Flow
  │   │   ├─ Navigate to tab
  │   │   ├─ Fill form
  │   │   ├─ Preview operation
  │   │   ├─ Execute operation
  │   │   ├─ Monitor progress
  │   │   └─ View results
  │   └─ Scale-Down Flow
  │       └─ (Similar steps)
  │
  ├─ Error Scenarios
  │   ├─ Invalid input handling
  │   ├─ Backend unavailable
  │   ├─ Operation failure
  │   └─ Timeout handling
  │
  └─ Cross-Tab Navigation
      ├─ Switch tabs during operation
      ├─ Return to see results
      └─ State persists correctly

Headless CI Tests
  ├─ All E2E tests run in headless mode
  ├─ No browser UI dependencies
  ├─ Screenshot capture on failure
  └─ Test artifacts saved
```

## Summary

This architecture provides:

1. **Clear separation of concerns**: Frontend UI, backend API, Python CLI
2. **Real-time communication**: WebSocket for live updates
3. **Robust error handling**: Multiple layers of validation and error recovery
4. **Scalable state management**: Context + reducer pattern
5. **Type-safe interfaces**: TypeScript throughout
6. **Comprehensive testing**: Unit, integration, and E2E tests
7. **CI/CD friendly**: Headless operation support
8. **Production-ready**: Error handling, timeouts, cleanup

The architecture follows existing SPA patterns while adding specialized support for long-running scale operations with real-time progress monitoring.
