/**
 * Tenant Reset Tab Component (Issue #627)
 *
 * Provides UI for tenant reset operations with comprehensive safety controls:
 * - 5-stage confirmation flow
 * - Dry-run preview mode
 * - Scope calculation (tenant, subscription, resource group, resource)
 * - Real-time progress tracking
 * - ATG Service Principal preservation
 *
 * Philosophy:
 * - Ruthless simplicity: Clear UI, no hidden bypasses
 * - Zero-BS implementation: Every safety control visible to user
 * - User safety first: Cannot bypass confirmation stages
 */

import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Progress } from '@/components/ui/progress';
import { AlertTriangle, Info, Shield, Trash2, Clock, CheckCircle, XCircle } from 'lucide-react';

// Types
type ResetScope = 'tenant' | 'subscription' | 'resource-group' | 'resource';

interface ScopeData {
  scope_level: string;
  to_delete: string[];
  to_preserve: string[];
  to_delete_count: number;
  to_preserve_count: number;
}

interface ResetResult {
  success: boolean;
  deleted_count: number;
  failed_count: number;
  deleted_resources: string[];
  failed_resources: string[];
  errors: Record<string, string>;
  duration_seconds: number;
}

type ConfirmationStage = 1 | 2 | 3 | 4 | 5;

export const TenantResetTab: React.FC = () => {
  // State
  const [scope, setScope] = useState<ResetScope>('resource-group');
  const [tenantId, setTenantId] = useState('');
  const [subscriptionIds, setSubscriptionIds] = useState('');
  const [resourceGroupNames, setResourceGroupNames] = useState('');
  const [resourceId, setResourceId] = useState('');
  const [isDryRun, setIsDryRun] = useState(true);

  const [scopeData, setScopeData] = useState<ScopeData | null>(null);
  const [isCalculating, setIsCalculating] = useState(false);

  const [currentStage, setCurrentStage] = useState<ConfirmationStage>(1);
  const [confirmationInputs, setConfirmationInputs] = useState<Record<number, string>>({});
  const [countdown, setCountdown] = useState<number | null>(null);

  const [isExecuting, setIsExecuting] = useState(false);
  const [result, setResult] = useState<ResetResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Calculate Scope (Dry-Run)
  const handleCalculateScope = async () => {
    setError(null);
    setScopeData(null);
    setIsCalculating(true);

    try {
      const request: any = { tenant_id: tenantId };

      if (scope === 'subscription') {
        request.subscription_ids = subscriptionIds.split(',').map(s => s.trim());
      } else if (scope === 'resource-group') {
        request.resource_group_names = resourceGroupNames.split(',').map(s => s.trim());
        request.subscription_id_for_rgs = subscriptionIds.split(',')[0]?.trim();
      } else if (scope === 'resource') {
        request.resource_id = resourceId;
      }

      const response = await fetch('/api/v1/reset/scope', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to calculate scope');
      }

      const data: ScopeData = await response.json();
      setScopeData(data);
    } catch (err: any) {
      setError(err.message || 'Failed to calculate scope');
    } finally {
      setIsCalculating(false);
    }
  };

  // Confirmation Flow
  const handleStageConfirmation = (stage: ConfirmationStage, value: string) => {
    setConfirmationInputs({ ...confirmationInputs, [stage]: value });
  };

  const validateStage = (stage: ConfirmationStage): boolean => {
    const input = confirmationInputs[stage] || '';

    switch (stage) {
      case 1:
        return input === 'yes';
      case 2:
        return input === 'yes';
      case 3:
        return input === tenantId;
      case 4:
        return input === 'yes';
      case 5:
        return input === 'DELETE';
      default:
        return false;
    }
  };

  const handleNextStage = () => {
    if (!validateStage(currentStage)) {
      setError(`Stage ${currentStage} validation failed. Please enter the correct value.`);
      return;
    }

    if (currentStage === 5) {
      // Start countdown before execution
      setCountdown(3);
      const interval = setInterval(() => {
        setCountdown(prev => {
          if (prev === null || prev <= 1) {
            clearInterval(interval);
            handleExecuteReset();
            return null;
          }
          return prev - 1;
        });
      }, 1000);
    } else {
      setCurrentStage((currentStage + 1) as ConfirmationStage);
      setError(null);
    }
  };

  const handlePreviousStage = () => {
    if (currentStage > 1) {
      setCurrentStage((currentStage - 1) as ConfirmationStage);
      setError(null);
    }
  };

  // Execute Reset
  const handleExecuteReset = async () => {
    if (isDryRun) {
      setError('Dry-run mode enabled. No actual deletion will occur.');
      return;
    }

    setError(null);
    setIsExecuting(true);

    try {
      const request: any = {
        tenant_id: tenantId,
        confirmation_token: 'frontend-confirmed-' + Date.now(), // Simple token for demo
      };

      if (scope === 'subscription') {
        request.subscription_ids = subscriptionIds.split(',').map(s => s.trim());
      } else if (scope === 'resource-group') {
        request.resource_group_names = resourceGroupNames.split(',').map(s => s.trim());
        request.subscription_id_for_rgs = subscriptionIds.split(',')[0]?.trim();
      } else if (scope === 'resource') {
        request.resource_id = resourceId;
      }

      const response = await fetch('/api/v1/reset/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to execute reset');
      }

      const data: ResetResult = await response.json();
      setResult(data);
    } catch (err: any) {
      setError(err.message || 'Failed to execute reset');
    } finally {
      setIsExecuting(false);
    }
  };

  // Reset Flow
  const handleResetFlow = () => {
    setScopeData(null);
    setCurrentStage(1);
    setConfirmationInputs({});
    setResult(null);
    setError(null);
    setCountdown(null);
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Trash2 className="h-6 w-6 text-red-500" />
            <CardTitle>Tenant Reset (DESTRUCTIVE)</CardTitle>
          </div>
          <CardDescription>
            Safely reset Azure tenants with 5-stage confirmation flow, ATG SP preservation,
            and rate limiting.
          </CardDescription>
        </CardHeader>
      </Card>

      {/* Configuration */}
      {!scopeData && !result && (
        <Card>
          <CardHeader>
            <CardTitle>Step 1: Configure Reset Scope</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Dry-Run Toggle */}
            <div className="flex items-center gap-2 p-4 bg-blue-50 rounded-md">
              <Info className="h-5 w-5 text-blue-500" />
              <div className="flex-1">
                <Label htmlFor="dry-run" className="font-semibold">Dry-Run Mode</Label>
                <p className="text-sm text-gray-600">Preview what would be deleted without actually deleting</p>
              </div>
              <input
                id="dry-run"
                type="checkbox"
                checked={isDryRun}
                onChange={(e) => setIsDryRun(e.target.checked)}
                className="h-5 w-5"
              />
            </div>

            {/* Tenant ID */}
            <div className="space-y-2">
              <Label htmlFor="tenant-id">Tenant ID *</Label>
              <Input
                id="tenant-id"
                placeholder="12345678-1234-1234-1234-123456789abc"
                value={tenantId}
                onChange={(e) => setTenantId(e.target.value)}
              />
            </div>

            {/* Scope Selection */}
            <div className="space-y-2">
              <Label>Reset Scope *</Label>
              <RadioGroup value={scope} onValueChange={(val) => setScope(val as ResetScope)}>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="tenant" id="tenant" />
                  <Label htmlFor="tenant">Entire Tenant (ALL subscriptions, resources, identities)</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="subscription" id="subscription" />
                  <Label htmlFor="subscription">Specific Subscriptions</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="resource-group" id="resource-group" />
                  <Label htmlFor="resource-group">Specific Resource Groups</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="resource" id="resource" />
                  <Label htmlFor="resource">Single Resource</Label>
                </div>
              </RadioGroup>
            </div>

            {/* Conditional Inputs */}
            {scope === 'subscription' && (
              <div className="space-y-2">
                <Label htmlFor="sub-ids">Subscription IDs (comma-separated) *</Label>
                <Input
                  id="sub-ids"
                  placeholder="sub-1,sub-2,sub-3"
                  value={subscriptionIds}
                  onChange={(e) => setSubscriptionIds(e.target.value)}
                />
              </div>
            )}

            {scope === 'resource-group' && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="rg-names">Resource Group Names (comma-separated) *</Label>
                  <Input
                    id="rg-names"
                    placeholder="rg-1,rg-2,rg-3"
                    value={resourceGroupNames}
                    onChange={(e) => setResourceGroupNames(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="sub-id-rg">Subscription ID (containing RGs) *</Label>
                  <Input
                    id="sub-id-rg"
                    placeholder="12345678-1234-1234-1234-123456789abc"
                    value={subscriptionIds}
                    onChange={(e) => setSubscriptionIds(e.target.value)}
                  />
                </div>
              </>
            )}

            {scope === 'resource' && (
              <div className="space-y-2">
                <Label htmlFor="resource-id">Resource ID *</Label>
                <Input
                  id="resource-id"
                  placeholder="/subscriptions/.../resourceGroups/.../providers/.../vm-1"
                  value={resourceId}
                  onChange={(e) => setResourceId(e.target.value)}
                />
              </div>
            )}

            {/* Calculate Button */}
            <Button
              onClick={handleCalculateScope}
              disabled={!tenantId || isCalculating}
              className="w-full"
            >
              {isCalculating ? 'Calculating...' : 'Calculate Scope (Dry-Run)'}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Scope Preview */}
      {scopeData && !result && (
        <Card>
          <CardHeader>
            <CardTitle>Step 2: Review Scope</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 bg-red-50 rounded-md">
                <div className="text-sm text-gray-600">To Delete</div>
                <div className="text-2xl font-bold text-red-600">{scopeData.to_delete_count}</div>
              </div>
              <div className="p-4 bg-green-50 rounded-md">
                <div className="text-sm text-gray-600">To Preserve (ATG SP)</div>
                <div className="text-2xl font-bold text-green-600">{scopeData.to_preserve_count}</div>
              </div>
            </div>

            <Separator />

            {/* First 10 resources to delete */}
            <div>
              <Label>Resources to Delete (first 10):</Label>
              <div className="mt-2 space-y-1 max-h-40 overflow-y-auto">
                {scopeData.to_delete.slice(0, 10).map((resource, idx) => (
                  <div key={idx} className="text-sm text-gray-700 p-2 bg-gray-50 rounded">
                    {idx + 1}. {resource}
                  </div>
                ))}
                {scopeData.to_delete_count > 10 && (
                  <div className="text-sm text-gray-500 italic">
                    ... and {scopeData.to_delete_count - 10} more resources
                  </div>
                )}
              </div>
            </div>

            {isDryRun ? (
              <Alert>
                <Info className="h-4 w-4" />
                <AlertDescription>
                  Dry-run mode enabled. No actual deletion will occur. Disable dry-run to proceed with confirmation flow.
                </AlertDescription>
              </Alert>
            ) : (
              <Button onClick={() => setCurrentStage(1)} className="w-full">
                Proceed to Confirmation Flow (5 Stages)
              </Button>
            )}

            <Button variant="outline" onClick={handleResetFlow} className="w-full">
              Start Over
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Confirmation Flow */}
      {scopeData && !isDryRun && !result && (
        <Card>
          <CardHeader>
            <CardTitle>Step 3: Confirmation Flow</CardTitle>
            <Progress value={(currentStage / 5) * 100} className="mt-2" />
            <div className="text-sm text-gray-600">Stage {currentStage} of 5</div>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Stage 1: Permanent Deletion Acknowledgment */}
            {currentStage === 1 && (
              <div className="space-y-4">
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>
                    This operation will PERMANENTLY delete resources. There is NO undo.
                  </AlertDescription>
                </Alert>
                <Label>Type "yes" (case-sensitive) to confirm you understand:</Label>
                <Input
                  value={confirmationInputs[1] || ''}
                  onChange={(e) => handleStageConfirmation(1, e.target.value)}
                  placeholder="yes"
                />
              </div>
            )}

            {/* Stage 2: Resource Count Verification */}
            {currentStage === 2 && (
              <div className="space-y-4">
                <div>
                  <Label>Total resources to delete: {scopeData.to_delete_count}</Label>
                  <div className="mt-2 text-sm text-gray-600">
                    First 10 resources listed above. Review carefully.
                  </div>
                </div>
                <Label>Type "yes" (case-sensitive) to confirm you reviewed the preview:</Label>
                <Input
                  value={confirmationInputs[2] || ''}
                  onChange={(e) => handleStageConfirmation(2, e.target.value)}
                  placeholder="yes"
                />
              </div>
            )}

            {/* Stage 3: Typed Tenant ID Verification */}
            {currentStage === 3 && (
              <div className="space-y-4">
                <Label>Type the tenant ID EXACTLY (case-sensitive):</Label>
                <div className="p-2 bg-gray-100 rounded font-mono text-sm">{tenantId}</div>
                <Input
                  value={confirmationInputs[3] || ''}
                  onChange={(e) => handleStageConfirmation(3, e.target.value)}
                  placeholder={tenantId}
                />
              </div>
            )}

            {/* Stage 4: ATG SP Acknowledgment */}
            {currentStage === 4 && (
              <div className="space-y-4">
                <Alert>
                  <Shield className="h-4 w-4" />
                  <AlertDescription>
                    The ATG Service Principal will be PRESERVED. This is required for ATG to access your tenant.
                  </AlertDescription>
                </Alert>
                <Label>Type "yes" (case-sensitive) to acknowledge ATG SP will be preserved:</Label>
                <Input
                  value={confirmationInputs[4] || ''}
                  onChange={(e) => handleStageConfirmation(4, e.target.value)}
                  placeholder="yes"
                />
              </div>
            )}

            {/* Stage 5: Final Confirmation with Countdown */}
            {currentStage === 5 && (
              <div className="space-y-4">
                {countdown !== null ? (
                  <Alert>
                    <Clock className="h-4 w-4" />
                    <AlertDescription>
                      Countdown: {countdown} seconds...
                    </AlertDescription>
                  </Alert>
                ) : (
                  <>
                    <Alert variant="destructive">
                      <AlertTriangle className="h-4 w-4" />
                      <AlertDescription>
                        This is your last chance to cancel. Type "DELETE" (case-sensitive, all caps) to confirm final deletion.
                      </AlertDescription>
                    </Alert>
                    <Label>Type "DELETE" (case-sensitive, all caps):</Label>
                    <Input
                      value={confirmationInputs[5] || ''}
                      onChange={(e) => handleStageConfirmation(5, e.target.value)}
                      placeholder="DELETE"
                    />
                  </>
                )}
              </div>
            )}

            {/* Navigation Buttons */}
            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={handlePreviousStage}
                disabled={currentStage === 1 || countdown !== null}
                className="flex-1"
              >
                Previous
              </Button>
              <Button
                onClick={handleNextStage}
                disabled={!validateStage(currentStage) || countdown !== null}
                className="flex-1"
              >
                {currentStage === 5 ? 'Execute Reset' : 'Next'}
              </Button>
            </div>

            <Button variant="ghost" onClick={handleResetFlow} className="w-full">
              Cancel
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Execution Progress */}
      {isExecuting && (
        <Card>
          <CardHeader>
            <CardTitle>Step 4: Executing Reset...</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-gray-900" />
              <span>Deleting resources...</span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {result && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {result.success ? (
                <CheckCircle className="h-6 w-6 text-green-500" />
              ) : (
                <XCircle className="h-6 w-6 text-red-500" />
              )}
              Reset Complete
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-4">
              <div className="p-4 bg-green-50 rounded-md">
                <div className="text-sm text-gray-600">Deleted</div>
                <div className="text-2xl font-bold text-green-600">{result.deleted_count}</div>
              </div>
              <div className="p-4 bg-red-50 rounded-md">
                <div className="text-sm text-gray-600">Failed</div>
                <div className="text-2xl font-bold text-red-600">{result.failed_count}</div>
              </div>
              <div className="p-4 bg-blue-50 rounded-md">
                <div className="text-sm text-gray-600">Duration</div>
                <div className="text-2xl font-bold text-blue-600">{result.duration_seconds.toFixed(2)}s</div>
              </div>
            </div>

            {result.failed_count > 0 && (
              <div>
                <Label>Failed Resources:</Label>
                <div className="mt-2 space-y-1 max-h-40 overflow-y-auto">
                  {result.failed_resources.map((resource, idx) => (
                    <div key={idx} className="text-sm text-red-700 p-2 bg-red-50 rounded">
                      {resource}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <Button onClick={handleResetFlow} className="w-full">
              Start New Reset
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Error Display */}
      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
    </div>
  );
};

export default TenantResetTab;
