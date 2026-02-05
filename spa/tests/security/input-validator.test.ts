/**
 * Tests for input-validator --agent flag whitelisting
 */

import { InputValidator } from '../../backend/src/security/input-validator';

describe('InputValidator - Agent Flag', () => {
  it('should allow --agent flag in arguments', () => {
    const args = ['deploy', '--iac-dir', 'outputs/iac', '--agent'];
    const result = InputValidator.validateArguments(args);

    expect(result.isValid).toBe(true);
    expect(result.error).toBeUndefined();
  });

  it('should validate deploy command with --agent flag', () => {
    const args = [
      '--iac-dir', 'outputs/iac',
      '--target-tenant-id', 'tenant-123',
      '--resource-group', 'test-rg',
      '--location', 'eastus',
      '--agent'
    ];

    const result = InputValidator.validateArguments(args);

    expect(result.isValid).toBe(true);
    expect(result.sanitized).toEqual(args);
  });

  it('should accept --agent with other deploy flags', () => {
    const args = [
      '--iac-dir', 'outputs/iac',
      '--dry-run',
      '--agent',
      '--format', 'terraform'
    ];

    const result = InputValidator.validateArguments(args);

    expect(result.isValid).toBe(true);
  });
});
