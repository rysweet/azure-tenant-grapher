# Scale Operations UI Design - Quick Reference

## Files Created

1. **SCALE_OPERATIONS_UI_DESIGN.md** - Complete component design, types, and implementation patterns
2. **SCALE_OPERATIONS_ARCHITECTURE_DIAGRAM.md** - Architecture diagrams and data flow visualizations
3. **This file** - Quick reference guide

## Component Tree (Quick View)

```
ScaleOperationsTab
├── OperationModeSelector (Toggle: Scale-Up | Scale-Down)
├── ScaleUpPanel (Config form for scale-up)
├── ScaleDownPanel (Config form for scale-down)
├── ProgressMonitor (Live operation tracking)
├── ResultsPanel (Post-operation summary)
└── QuickActionsBar (Utility buttons)
```

## Key TypeScript Types

```typescript
// Operation configuration
type ScaleOperationType = 'scale-up' | 'scale-down';
type ScaleUpStrategy = 'template' | 'scenario' | 'random';
type ScaleDownAlgorithm = 'forest-fire' | 'mhrw' | 'pattern';
type OperationStatus = 'idle' | 'validating' | 'running' | 'success' | 'error';

// Main config interfaces
interface ScaleUpConfig {
  tenantId: string;
  strategy: ScaleUpStrategy;
  validate: boolean;
  templateFile?: string;
  scaleFactor?: number;
  // ... more fields
}

interface ScaleDownConfig {
  tenantId: string;
  algorithm: ScaleDownAlgorithm;
  sampleSize: number;
  validate: boolean;
  outputMode: 'file' | 'new-tenant' | 'iac';
  // ... more fields
}

// Results
interface OperationResult {
  success: boolean;
  operationType: ScaleOperationType;
  beforeStats: GraphStats;
  afterStats: GraphStats;
  validationResults: ValidationResult[];
  duration: number;
}
```

## API Endpoints (Backend)

```
POST   /api/scale/up/execute         - Start scale-up operation
POST   /api/scale/up/preview         - Preview scale-up changes
POST   /api/scale/down/execute       - Start scale-down operation
POST   /api/scale/down/preview       - Preview scale-down changes
POST   /api/scale/cancel/:processId  - Cancel running operation
GET    /api/scale/status/:processId  - Get operation status
POST   /api/scale/clean-synthetic    - Remove synthetic nodes
POST   /api/scale/validate           - Validate graph integrity
GET    /api/scale/stats/:tenantId    - Get graph statistics
```

## WebSocket Events

```
Event: 'scale:output'    - Real-time stdout/stderr from CLI
Event: 'scale:progress'  - Progress updates (%, phase, stats)
Event: 'scale:complete'  - Operation completion with results
Event: 'scale:error'     - Operation failure with error message
```

## File Structure (To Be Created)

```
spa/renderer/src/
├── components/
│   ├── tabs/
│   │   └── ScaleOperationsTab.tsx         (Main tab component)
│   └── scale/
│       ├── ScaleUpPanel.tsx               (Scale-up configuration form)
│       ├── ScaleDownPanel.tsx             (Scale-down configuration form)
│       ├── ProgressMonitor.tsx            (Live progress display)
│       ├── ResultsPanel.tsx               (Post-operation results)
│       ├── QuickActionsBar.tsx            (Utility action buttons)
│       ├── StrategySelector.tsx           (Scale-up strategy dropdown)
│       ├── AlgorithmSelector.tsx          (Scale-down algorithm dropdown)
│       ├── ValidationAlert.tsx            (Validation status display)
│       └── StatisticsGrid.tsx             (Operation statistics cards)
│
├── context/
│   └── ScaleOperationsContext.tsx         (State management)
│
├── hooks/
│   ├── useScaleUpOperation.ts             (Scale-up hook)
│   ├── useScaleDownOperation.ts           (Scale-down hook)
│   └── useGraphStats.ts                   (Graph statistics hook)
│
├── types/
│   └── scaleOperations.ts                 (TypeScript interfaces)
│
└── utils/
    └── scaleOperationsValidation.ts       (Validation helpers)

spa/backend/src/
├── routes/
│   └── scaleRoutes.ts                     (API route handlers)
└── services/
    └── scaleService.ts                    (Business logic)

spa/tests/
├── unit/
│   ├── scaleOperationsContext.test.ts
│   ├── useScaleUpOperation.test.ts
│   └── useScaleDownOperation.test.ts
├── integration/
│   ├── ScaleUpPanel.test.tsx
│   └── ProgressMonitor.test.tsx
└── e2e/
    └── scale-operations.spec.ts           (Playwright tests)
```

## State Management Pattern

```typescript
// 1. Create Context Provider
<ScaleOperationsProvider>
  <ScaleOperationsTab />
</ScaleOperationsProvider>

// 2. Use context in components
const { state, dispatch } = useScaleOperations();

// 3. Use specialized hooks for operations
const { executeScaleUp, previewScaleUp } = useScaleUpOperation();

// 4. Subscribe to WebSocket for updates
const { subscribeToProcess, getProcessOutput } = useWebSocket();
```

## Operation Lifecycle

```
1. User fills form (ScaleUpPanel / ScaleDownPanel)
2. User clicks "Execute"
3. Frontend validates input
4. Frontend calls API: POST /api/scale/up/execute
5. Backend spawns Python CLI process
6. Backend returns processId
7. Frontend subscribes to WebSocket for processId
8. Backend emits real-time updates via WebSocket
9. Frontend displays progress in ProgressMonitor
10. Operation completes
11. Backend emits 'scale:complete' event
12. Frontend shows results in ResultsPanel
```

## UI States

```
┌─────────────────┬──────────────────────────────────────────────┐
│ State           │ UI Components Shown                          │
├─────────────────┼──────────────────────────────────────────────┤
│ idle            │ OperationModeSelector + Config Panel         │
│ validating      │ Config Panel + Validation spinner            │
│ running         │ ProgressMonitor (live updates)               │
│ success         │ ResultsPanel (summary + stats)               │
│ error           │ Config Panel + Error Alert                   │
└─────────────────┴──────────────────────────────────────────────┘
```

## Visual Design Tokens

```typescript
// Colors
const syntheticNodeColor = '#FF9800';      // Orange
const syntheticBorderColor = '#F57C00';    // Dark orange
const successColor = '#4CAF50';            // Green
const errorColor = '#F44336';              // Red
const progressColor = '#2196F3';           // Blue

// Synthetic node styling
{
  color: syntheticNodeColor,
  borderStyle: 'dashed',
  borderWidth: 2,
  borderColor: syntheticBorderColor,
  icon: '🔧'  // Wrench icon to indicate synthetic
}

// Progress bar styling
<LinearProgress
  variant="determinate"
  value={progress}
  sx={{ height: 8, borderRadius: 1 }}
/>
```

## Key Features

1. **Dual-mode operation**: Toggle between scale-up and scale-down
2. **Strategy selection**: Multiple algorithms for each mode
3. **Preview before execute**: See estimated impact
4. **Real-time progress**: Live logs and statistics
5. **Validation**: Pre and post-operation validation
6. **Results summary**: Before/after comparison
7. **Quick actions**: Clean synthetic data, validate, show stats
8. **Error handling**: Comprehensive error states and recovery
9. **Synthetic node visualization**: Distinct styling in graph
10. **Headless support**: Works in CI/CD environments

## Testing Checklist

- [ ] Unit tests for context and reducers
- [ ] Unit tests for custom hooks
- [ ] Integration tests for component interactions
- [ ] E2E test: Complete scale-up workflow
- [ ] E2E test: Complete scale-down workflow
- [ ] E2E test: Preview operation
- [ ] E2E test: Cancel running operation
- [ ] E2E test: Clean synthetic data
- [ ] E2E test: Error handling
- [ ] E2E test: Headless CI execution
- [ ] Accessibility: Screen reader support
- [ ] Accessibility: Keyboard navigation
- [ ] Performance: Large log rendering
- [ ] Performance: Real-time updates

## Implementation Priority

### Phase 1: Core Infrastructure (High Priority)
1. TypeScript interfaces (`types/scaleOperations.ts`)
2. Context provider (`context/ScaleOperationsContext.tsx`)
3. Custom hooks (`hooks/useScaleUpOperation.ts`, etc.)
4. Backend API routes (`spa/backend/src/routes/scaleRoutes.ts`)

### Phase 2: UI Components (High Priority)
1. Main tab (`ScaleOperationsTab.tsx`)
2. Config panels (`ScaleUpPanel.tsx`, `ScaleDownPanel.tsx`)
3. Progress monitor (`ProgressMonitor.tsx`)
4. Results panel (`ResultsPanel.tsx`)

### Phase 3: Supporting Components (Medium Priority)
1. Quick actions bar (`QuickActionsBar.tsx`)
2. Strategy/Algorithm selectors
3. Validation alerts
4. Statistics cards

### Phase 4: Testing (Medium Priority)
1. Unit tests
2. Integration tests
3. E2E tests

### Phase 5: Polish (Low Priority)
1. Accessibility improvements
2. Performance optimizations
3. Visual refinements
4. Documentation

## Integration Points

### With Existing SPA Components
```typescript
// Reuse LogViewer component
import LogViewer from '../common/LogViewer';

// Reuse WebSocket hook
import { useWebSocket } from '../../hooks/useWebSocket';

// Reuse App context for tenant ID
import { useApp } from '../../context/AppContext';

// Reuse validation utilities
import { isValidTenantId } from '../../utils/validation';
```

### With Backend Services
```typescript
// Use existing Neo4j service
import { Neo4jService } from './neo4j-service';

// Use existing process manager
import { ProcessManager } from '../main/process-manager';

// Use existing logger
import { createLogger } from './logger-setup';
```

### With Python CLI
```bash
# Scale-up commands
uv run atg scale-up --tenant-id <id> --strategy template --template-file <file>
uv run atg scale-up --tenant-id <id> --strategy random --node-count 1000

# Scale-down commands
uv run atg scale-down --tenant-id <id> --algorithm forest-fire --sample-size 500
uv run atg scale-down --tenant-id <id> --algorithm mhrw --sample-size 500

# Utility commands
uv run atg clean-synthetic --tenant-id <id>
uv run atg validate-graph --tenant-id <id>
uv run atg graph-stats --tenant-id <id>
```

## Development Workflow

```bash
# 1. Create component files
mkdir -p spa/renderer/src/components/scale
touch spa/renderer/src/components/tabs/ScaleOperationsTab.tsx

# 2. Add backend routes
mkdir -p spa/backend/src/routes
touch spa/backend/src/routes/scaleRoutes.ts

# 3. Run development server
cd spa && npm run dev

# 4. Access in browser
# Navigate to Scale Operations tab

# 5. Test in headless mode
cd spa && npm run test:e2e -- scale-operations.spec.ts

# 6. Build for production
cd spa && npm run build
```

## Accessibility Quick Reference

```typescript
// ARIA labels
<Button aria-label="Execute scale-up operation">Execute</Button>

// Live regions for screen readers
<div role="status" aria-live="polite">Operation 50% complete</div>

// Focus management
useEffect(() => {
  if (showResults) {
    resultsRef.current?.focus();
  }
}, [showResults]);

// Keyboard shortcuts
- Enter: Execute operation
- Escape: Cancel operation
- Tab: Navigate form fields
```

## Performance Tips

```typescript
// 1. Virtualize long log lists
import { FixedSizeList } from 'react-window';

// 2. Debounce config updates
const debouncedUpdate = debounce(updateConfig, 300);

// 3. Memoize expensive computations
const stats = useMemo(() => computeStats(result), [result]);

// 4. Limit WebSocket buffer size
const MAX_LOG_LINES = 10000;

// 5. Use React.memo for static components
export default React.memo(StatisticsCard);
```

## Common Pitfalls to Avoid

1. **Don't forget to unsubscribe from WebSocket** when component unmounts
2. **Always validate input** before sending to backend
3. **Handle WebSocket disconnection** gracefully with reconnection logic
4. **Show loading states** for all async operations
5. **Clear error states** when user makes changes
6. **Provide cancel functionality** for long-running operations
7. **Test headless mode** in CI environment
8. **Use TypeScript strictly** - no `any` types in production code
9. **Follow existing patterns** from ScanTab and GenerateIaCTab
10. **Document complex logic** with inline comments

## Next Steps

1. Review this design with team
2. Get approval on component structure
3. Implement Phase 1 (core infrastructure)
4. Implement Phase 2 (UI components)
5. Add unit and integration tests
6. Add E2E tests
7. Test in headless CI environment
8. Polish and optimize
9. Document for end users

## References

- **Full Design**: `docs/design/SCALE_OPERATIONS_UI_DESIGN.md`
- **Architecture Diagrams**: `docs/design/SCALE_OPERATIONS_ARCHITECTURE_DIAGRAM.md`
- **Feature Specification**: `docs/features/scale-operations/SPECIFICATION.md`
- **Existing SPA Patterns**: `spa/renderer/src/components/tabs/ScanTab.tsx`
- **WebSocket Hook**: `spa/renderer/src/hooks/useWebSocket.ts`
- **Backend Server**: `spa/backend/src/server.ts`
