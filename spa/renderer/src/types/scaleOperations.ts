// src/types/scaleOperations.ts
// TypeScript interfaces for Scale Operations feature

export type ScaleOperationType = 'scale-up' | 'scale-down';

export type ScaleUpStrategy = 'template' | 'scenario' | 'random';
export type ScaleDownAlgorithm = 'forest-fire' | 'mhrw' | 'pattern';
export type OutputMode = 'file' | 'new-tenant' | 'iac';

export type OperationStatus =
  | 'idle'
  | 'validating'
  | 'previewing'
  | 'running'
  | 'success'
  | 'error'
  | 'stopped';

export interface ScaleUpConfig {
  tenantId: string;
  strategy: ScaleUpStrategy;
  validate: boolean;
  // Template strategy
  templateFile?: string;
  scaleFactor?: number;
  // Scenario strategy
  scenarioType?: string;
  scenarioParams?: Record<string, any>;
  // Random strategy
  nodeCount?: number;
  pattern?: string;
}

export interface ScaleDownConfig {
  tenantId: string;
  algorithm: ScaleDownAlgorithm;
  sampleSize: number;
  validate: boolean;
  outputMode: OutputMode;
  // Forest-fire algorithm
  burnInSteps?: number;
  forwardProbability?: number;
  // MHRW algorithm
  walkLength?: number;
  // Pattern-based
  pattern?: string;
  // Output settings
  outputPath?: string;
  iacFormat?: 'terraform' | 'arm' | 'bicep';
  newTenantId?: string;
  preserveRelationships?: boolean;
  includeProperties?: boolean;
}

export interface OperationProgress {
  processId: string;
  status: OperationStatus;
  phase: string;
  progress: number; // 0-100
  startTime: string;
  elapsedSeconds: number;
  stats?: {
    nodesCreated?: number;
    nodesDeleted?: number;
    relationshipsAffected?: number;
    validationPassed?: boolean;
  };
}

export interface ScaleUpStats {
  nodesCreated: number;
  relationshipsCreated: number;
  nodeTypeBreakdown: Record<string, number>;
  syntheticNodesCreated: number;
  validationPassed: boolean;
}

export interface ScaleDownStats {
  nodesRetained: number;
  nodesDeleted: number;
  relationshipsRetained: number;
  relationshipsDeleted: number;
  validationPassed: boolean;
  outputPath?: string;
}

export interface GraphStats {
  totalNodes: number;
  totalRelationships: number;
  syntheticNodes: number;
  nodeTypes: Record<string, number>;
  relationshipTypes: Record<string, number>;
  lastUpdate?: string;
}

export interface OperationResult {
  success: boolean;
  operationType: ScaleOperationType;
  beforeStats: GraphStats;
  afterStats: GraphStats;
  scaleUpStats?: ScaleUpStats;
  scaleDownStats?: ScaleDownStats;
  validationResults: ValidationResult[];
  timestamp: string;
  duration: number; // seconds
  error?: string;
}

export interface ValidationResult {
  checkName: string;
  passed: boolean;
  message: string;
  details?: any;
}

export interface PreviewResult {
  estimatedNodes: number;
  estimatedRelationships: number;
  estimatedDuration: number; // seconds
  warnings: string[];
  canProceed: boolean;
  nodeTypeBreakdown?: Record<string, number>;
}

// API response types
export interface ExecuteResponse {
  success: boolean;
  processId: string;
  error?: string;
}

export interface CleanSyntheticResponse {
  success: boolean;
  nodesDeleted: number;
  relationshipsDeleted: number;
  error?: string;
}
