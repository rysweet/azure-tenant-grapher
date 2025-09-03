/**
 * Scenarios module - Test scenario management
 */

import * as yaml from 'js-yaml';
import * as fs from 'fs/promises';
import * as path from 'path';

// Scenario loader utility
export class ScenarioLoader {
  static async loadFromFile(filePath: string): Promise<TestScenario> {
    const content = await fs.readFile(filePath, 'utf-8');
    const scenario = yaml.load(content) as TestScenario;
    return this.validateScenario(scenario);
  }
  
  static async loadFromDirectory(dirPath: string): Promise<TestScenario[]> {
    const files = await fs.readdir(dirPath);
    const yamlFiles = files.filter(f => f.endsWith('.yaml') || f.endsWith('.yml'));
    
    const scenarios = await Promise.all(
      yamlFiles.map(f => this.loadFromFile(path.join(dirPath, f)))
    );
    
    return scenarios;
  }
  
  private static validateScenario(scenario: any): TestScenario {
    if (!scenario.name) {
      throw new Error('Scenario must have a name');
    }
    if (!scenario.steps || !Array.isArray(scenario.steps)) {
      throw new Error('Scenario must have steps array');
    }
    return scenario as TestScenario;
  }
}

// Scenario interfaces
export interface TestScenario {
  name: string;
  description?: string;
  version?: string;
  config?: ScenarioConfig;
  environment?: EnvironmentConfig;
  agents: AgentConfig[];
  steps: TestStep[];
  assertions: TestAssertion[];
  cleanup?: TestStep[];
  metadata?: ScenarioMetadata;
}

export interface ScenarioConfig {
  timeout?: number;
  retries?: number;
  parallel?: boolean;
}

export interface EnvironmentConfig {
  requires?: string[];
  optional?: string[];
}

export interface AgentConfig {
  name: string;
  type: string;
  config?: Record<string, any>;
}

export interface TestStep {
  name: string;
  agent: string;
  action: string;
  params?: Record<string, any>;
  timeout?: number;
  wait_for?: WaitCondition;
  until?: UntilCondition;
}

export interface WaitCondition {
  selector?: string;
  state?: 'visible' | 'hidden' | 'attached' | 'detached';
  timeout?: number;
}

export interface UntilCondition {
  condition: 'contains' | 'equals' | 'matches';
  value: any;
  timeout?: number;
}

export interface TestAssertion {
  name: string;
  type: string;
  agent: string;
  params: Record<string, any>;
}

export interface ScenarioMetadata {
  tags?: string[];
  priority?: 'low' | 'medium' | 'high' | 'critical';
  author?: string;
  created?: string;
  updated?: string;
}