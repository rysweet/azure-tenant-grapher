<#
.SYNOPSIS
    Deploys Azure Sentinel data connectors across multiple tenants via Azure Lighthouse

.DESCRIPTION
    This script uses Azure Lighthouse delegation to deploy and configure
    data connectors (Azure AD, Office 365, Azure Security Center) across
    all customer tenants from your managing tenant.

.PARAMETER ManagingTenantId
    Your service provider tenant ID

.PARAMETER ServicePrincipalId
    Application/Client ID of your service principal

.PARAMETER ServicePrincipalSecret
    Client secret for authentication

.PARAMETER ConnectorTypes
    Array of connector types to deploy

.EXAMPLE
    .\Deploy-SentinelConnectors.ps1 -ManagingTenantId "xxxx-xxxx" `
        -ServicePrincipalId "yyyy-yyyy" `
        -ServicePrincipalSecret $secret
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$ManagingTenantId,

    [Parameter(Mandatory=$true)]
    [string]$ServicePrincipalId,

    [Parameter(Mandatory=$true)]
    [SecureString]$ServicePrincipalSecret,

    [Parameter(Mandatory=$false)]
    [string[]]$ConnectorTypes = @("AzureActiveDirectory", "Office365", "AzureSecurityCenter")
)

# Authenticate to managing tenant
Write-Host "Authenticating to managing tenant..." -ForegroundColor Cyan
$credential = New-Object System.Management.Automation.PSCredential($ServicePrincipalId, $ServicePrincipalSecret)
Connect-AzAccount -ServicePrincipal -Credential $credential -Tenant $ManagingTenantId | Out-Null

# Get all delegated subscriptions (via Azure Lighthouse)
Write-Host "Discovering delegated customer tenants..." -ForegroundColor Cyan
$delegatedSubs = Get-AzSubscription | Where-Object { $_.TenantId -ne $ManagingTenantId }

Write-Host "Found $($delegatedSubs.Count) delegated customer subscriptions" -ForegroundColor Green

$results = @()

foreach ($sub in $delegatedSubs) {
    Write-Host "`nProcessing subscription: $($sub.Name) (Tenant: $($sub.TenantId))" -ForegroundColor Yellow
    Set-AzContext -Subscription $sub.Id | Out-Null

    # Find Sentinel workspaces
    $workspaces = Get-AzOperationalInsightsWorkspace | Where-Object {
        $solutions = Get-AzOperationalInsightsIntelligencePack `
            -ResourceGroupName $_.ResourceGroupName `
            -WorkspaceName $_.Name
        $solutions | Where-Object { $_.Name -eq "SecurityInsights" -and $_.Enabled -eq $true }
    }

    foreach ($workspace in $workspaces) {
        Write-Host "  Found Sentinel workspace: $($workspace.Name)" -ForegroundColor Cyan

        foreach ($connectorType in $ConnectorTypes) {
            try {
                $connectorId = "$connectorType-$($sub.TenantId)"

                # Build connector properties
                $connectorProperties = Get-ConnectorProperties -Type $connectorType -TenantId $sub.TenantId -SubscriptionId $sub.Id

                # Deploy connector via REST API
                $apiVersion = "2023-02-01"
                $uri = "https://management.azure.com/subscriptions/$($sub.Id)/resourceGroups/$($workspace.ResourceGroupName)/providers/Microsoft.OperationalInsights/workspaces/$($workspace.Name)/providers/Microsoft.SecurityInsights/dataConnectors/$connectorId?api-version=$apiVersion"

                $body = @{
                    kind = $connectorType
                    properties = $connectorProperties
                } | ConvertTo-Json -Depth 10

                $token = (Get-AzAccessToken).Token
                $headers = @{
                    "Authorization" = "Bearer $token"
                    "Content-Type" = "application/json"
                }

                $response = Invoke-RestMethod -Uri $uri -Method Put -Headers $headers -Body $body

                Write-Host "    ✓ Deployed $connectorType connector" -ForegroundColor Green

                $results += [PSCustomObject]@{
                    Tenant = $sub.Name
                    TenantId = $sub.TenantId
                    Workspace = $workspace.Name
                    Connector = $connectorType
                    Status = "Success"
                }

            } catch {
                Write-Host "    ✗ Failed to deploy $connectorType : $($_.Exception.Message)" -ForegroundColor Red

                $results += [PSCustomObject]@{
                    Tenant = $sub.Name
                    TenantId = $sub.TenantId
                    Workspace = $workspace.Name
                    Connector = $connectorType
                    Status = "Failed"
                    Error = $_.Exception.Message
                }
            }
        }
    }
}

# Summary
Write-Host "`n$('='*70)" -ForegroundColor Cyan
Write-Host "Deployment Summary" -ForegroundColor Cyan
Write-Host $('='*70) -ForegroundColor Cyan
Write-Host "Total Deployments: $($results.Count)" -ForegroundColor White
Write-Host "Successful: $($results | Where-Object {$_.Status -eq 'Success'} | Measure-Object | Select-Object -ExpandProperty Count)" -ForegroundColor Green
Write-Host "Failed: $($results | Where-Object {$_.Status -eq 'Failed'} | Measure-Object | Select-Object -ExpandProperty Count)" -ForegroundColor Red

# Export results
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$results | Export-Csv -Path ".\connector-deployment-$timestamp.csv" -NoTypeInformation
Write-Host "`nResults exported to: connector-deployment-$timestamp.csv" -ForegroundColor Cyan

# Helper function
function Get-ConnectorProperties {
    param(
        [string]$Type,
        [string]$TenantId,
        [string]$SubscriptionId
    )

    switch ($Type) {
        "AzureActiveDirectory" {
            return @{
                tenantId = $TenantId
                dataTypes = @{
                    alerts = @{ state = "Enabled" }
                }
            }
        }
        "Office365" {
            return @{
                tenantId = $TenantId
                dataTypes = @{
                    exchange = @{ state = "Enabled" }
                    sharePoint = @{ state = "Enabled" }
                    teams = @{ state = "Enabled" }
                }
            }
        }
        "AzureSecurityCenter" {
            return @{
                subscriptionId = $SubscriptionId
                dataTypes = @{
                    alerts = @{ state = "Enabled" }
                }
            }
        }
        default {
            throw "Unsupported connector type: $Type"
        }
    }
}
