#!/usr/bin/env powershell
# PowerShell script to start Neo4j container and run the Azure Tenant Grapher

param(
    [Parameter(Mandatory=$true)]
    [string]$TenantId,
    
    [string]$Neo4jUri = "bolt://localhost:7688",
    [string]$Neo4jUser = "neo4j", 
    [SecureString]$Neo4jPassword,
    [switch]$ContainerOnly,
    [switch]$NoContainer
)

# Change to script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Load environment variables
if (Test-Path ".env") {
    Get-Content ".env" | Where-Object { $_ -match "^\s*[^#]" } | ForEach-Object {
        $key, $value = $_ -split "=", 2
        [Environment]::SetEnvironmentVariable($key.Trim(), $value.Trim(), "Process")
    }
}

# Convert SecureString password if provided, otherwise use default
if ($Neo4jPassword) {
    $PlainPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($Neo4jPassword))
} else {
    $PlainPassword = "azure-grapher-2024"
}

# Build arguments
$ScriptArgs = @(
    "run",
    "python",
    "azure_tenant_grapher.py",
    "--tenant-id", $TenantId,
    "--neo4j-uri", $Neo4jUri,
    "--neo4j-user", $Neo4jUser,
    "--neo4j-password", $PlainPassword
)

if ($ContainerOnly) {
    $ScriptArgs += "--container-only"
}

if ($NoContainer) {
    $ScriptArgs += "--no-container" 
}

# Run the application
Write-Host "Starting Azure Tenant Resource Grapher..." -ForegroundColor Green
& "uv" @ScriptArgs
