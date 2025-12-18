# ATG Remote Service API Reference

## Overview

The ATG remote service provides a REST API for executing Azure Tenant Grapher operations remotely. All endpoints require authentication via API key.

**Base URL:**
```
https://atg-{environment}.azurecontainerinstances.net
```

**Authentication:**
```
Authorization: Bearer {api_key}
```

## API Endpoints

### Health and Status

#### GET /health

Check service health and availability.

**Request:**
```bash
curl https://atg-dev.azurecontainerinstances.net/health
```

**Response (200 OK):**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "dev",
  "neo4j": "connected",
  "uptime": 86400,
  "timestamp": "2025-12-09T12:34:56Z"
}
```

**Response Codes:**
- `200 OK` - Service healthy
- `503 Service Unavailable` - Service unhealthy

#### GET /api/v1/status

Get detailed service status (requires authentication).

**Request:**
```bash
curl -H "Authorization: Bearer $ATG_API_KEY" \
  https://atg-dev.azurecontainerinstances.net/api/v1/status
```

**Response (200 OK):**
```json
{
  "authenticated": true,
  "environment": "dev",
  "neo4j": {
    "status": "connected",
    "version": "5.12.0",
    "database": "neo4j"
  },
  "operations": {
    "active": 2,
    "queued": 0,
    "completed_today": 15
  },
  "resources": {
    "memory_used_gb": 42.5,
    "memory_total_gb": 64.0,
    "cpu_usage_percent": 65.2
  },
  "timestamp": "2025-12-09T12:34:56Z"
}
```

**Response Codes:**
- `200 OK` - Status retrieved
- `401 Unauthorized` - Invalid API key

### Scan Operations

#### POST /api/v1/scan

Start a tenant scan operation.

**Request:**
```bash
curl -X POST \
  -H "Authorization: Bearer $ATG_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "12345678-1234-1234-1234-123456789abc",
    "parameters": {
      "rebuild_edges": false,
      "filter_subscriptions": [],
      "filter_resource_groups": [],
      "enable_aad_import": true
    }
  }' \
  https://atg-dev.azurecontainerinstances.net/api/v1/scan
```

**Request Body:**
```json
{
  "tenant_id": "string (required)",
  "parameters": {
    "rebuild_edges": "boolean (default: false)",
    "filter_subscriptions": "array of subscription IDs (optional)",
    "filter_resource_groups": "array of resource group names (optional)",
    "enable_aad_import": "boolean (default: true)",
    "resource_limit": "integer (optional, for testing)"
  }
}
```

**Response (202 Accepted):**
```json
{
  "operation_id": "op-a1b2c3d4e5f6",
  "status": "queued",
  "tenant_id": "12345678-1234-1234-1234-123456789abc",
  "created_at": "2025-12-09T12:34:56Z",
  "websocket_url": "wss://atg-dev.azurecontainerinstances.net/ws/progress/op-a1b2c3d4e5f6"
}
```

**Response Codes:**
- `202 Accepted` - Operation queued
- `400 Bad Request` - Invalid parameters
- `401 Unauthorized` - Invalid API key
- `429 Too Many Requests` - Rate limit exceeded

#### GET /api/v1/scan/{operation_id}

Get status of a scan operation.

**Request:**
```bash
curl -H "Authorization: Bearer $ATG_API_KEY" \
  https://atg-dev.azurecontainerinstances.net/api/v1/scan/op-a1b2c3d4e5f6
```

**Response (200 OK):**
```json
{
  "operation_id": "op-a1b2c3d4e5f6",
  "status": "running",
  "tenant_id": "12345678-1234-1234-1234-123456789abc",
  "progress": {
    "phase": "scanning",
    "current_subscription": 2,
    "total_subscriptions": 5,
    "resources_discovered": 487,
    "percent_complete": 40
  },
  "created_at": "2025-12-09T12:34:56Z",
  "started_at": "2025-12-09T12:35:01Z",
  "updated_at": "2025-12-09T12:42:15Z"
}
```

**Status Values:**
- `queued` - Operation queued, not started
- `running` - Operation in progress
- `completed` - Operation completed successfully
- `failed` - Operation failed with error
- `cancelled` - Operation cancelled by user

**Response Codes:**
- `200 OK` - Status retrieved
- `404 Not Found` - Operation not found
- `401 Unauthorized` - Invalid API key

### IaC Generation

#### POST /api/v1/generate-iac

Generate Infrastructure-as-Code templates.

**Request:**
```bash
curl -X POST \
  -H "Authorization: Bearer $ATG_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "12345678-1234-1234-1234-123456789abc",
    "format": "terraform",
    "parameters": {
      "target_tenant_id": null,
      "target_subscription": null,
      "auto_import_existing": false,
      "import_strategy": "resource_groups"
    }
  }' \
  https://atg-dev.azurecontainerinstances.net/api/v1/generate-iac
```

**Request Body:**
```json
{
  "tenant_id": "string (required)",
  "format": "terraform|bicep|arm (required)",
  "parameters": {
    "target_tenant_id": "string (optional, for cross-tenant)",
    "target_subscription": "string (optional)",
    "auto_import_existing": "boolean (default: false)",
    "import_strategy": "resource_groups|all (default: resource_groups)",
    "subset_filter": "string (optional)",
    "destination_resource_group": "string (optional)",
    "location": "string (optional)"
  }
}
```

**Response (202 Accepted):**
```json
{
  "operation_id": "op-g7h8i9j0k1l2",
  "status": "queued",
  "tenant_id": "12345678-1234-1234-1234-123456789abc",
  "format": "terraform",
  "created_at": "2025-12-09T12:45:00Z",
  "websocket_url": "wss://atg-dev.azurecontainerinstances.net/ws/progress/op-g7h8i9j0k1l2"
}
```

**Response Codes:**
- `202 Accepted` - Operation queued
- `400 Bad Request` - Invalid parameters
- `401 Unauthorized` - Invalid API key
- `404 Not Found` - Tenant graph not found

#### GET /api/v1/generate-iac/{operation_id}

Get status of IaC generation operation.

**Request:**
```bash
curl -H "Authorization: Bearer $ATG_API_KEY" \
  https://atg-dev.azurecontainerinstances.net/api/v1/generate-iac/op-g7h8i9j0k1l2
```

**Response (200 OK):**
```json
{
  "operation_id": "op-g7h8i9j0k1l2",
  "status": "completed",
  "tenant_id": "12345678-1234-1234-1234-123456789abc",
  "format": "terraform",
  "result": {
    "files_generated": 127,
    "resources_included": 845,
    "output_size_bytes": 524288,
    "download_url": "/api/v1/operations/op-g7h8i9j0k1l2/download"
  },
  "created_at": "2025-12-09T12:45:00Z",
  "completed_at": "2025-12-09T12:52:30Z"
}
```

**Response Codes:**
- `200 OK` - Status retrieved
- `404 Not Found` - Operation not found
- `401 Unauthorized` - Invalid API key

### Operations Management

#### GET /api/v1/operations

List all operations for current user.

**Request:**
```bash
curl -H "Authorization: Bearer $ATG_API_KEY" \
  "https://atg-dev.azurecontainerinstances.net/api/v1/operations?limit=10&status=running"
```

**Query Parameters:**
- `limit` (integer, default: 50) - Max results to return
- `offset` (integer, default: 0) - Pagination offset
- `status` (string, optional) - Filter by status
- `operation_type` (string, optional) - Filter by type (scan, generate-iac, etc.)

**Response (200 OK):**
```json
{
  "operations": [
    {
      "operation_id": "op-a1b2c3d4e5f6",
      "type": "scan",
      "status": "completed",
      "tenant_id": "12345678-1234-1234-1234-123456789abc",
      "created_at": "2025-12-09T10:30:00Z",
      "completed_at": "2025-12-09T10:42:15Z",
      "duration_seconds": 735
    },
    {
      "operation_id": "op-g7h8i9j0k1l2",
      "type": "generate-iac",
      "status": "running",
      "tenant_id": "12345678-1234-1234-1234-123456789abc",
      "created_at": "2025-12-09T12:45:00Z",
      "progress_percent": 65
    }
  ],
  "total": 2,
  "limit": 10,
  "offset": 0
}
```

**Response Codes:**
- `200 OK` - Operations retrieved
- `401 Unauthorized` - Invalid API key

#### DELETE /api/v1/operations/{operation_id}

Cancel a running operation.

**Request:**
```bash
curl -X DELETE \
  -H "Authorization: Bearer $ATG_API_KEY" \
  https://atg-dev.azurecontainerinstances.net/api/v1/operations/op-a1b2c3d4e5f6
```

**Response (200 OK):**
```json
{
  "operation_id": "op-a1b2c3d4e5f6",
  "status": "cancelled",
  "cancelled_at": "2025-12-09T12:55:00Z"
}
```

**Response Codes:**
- `200 OK` - Operation cancelled
- `404 Not Found` - Operation not found
- `409 Conflict` - Operation already completed
- `401 Unauthorized` - Invalid API key

#### GET /api/v1/operations/{operation_id}/download

Download operation results.

**Request:**
```bash
curl -H "Authorization: Bearer $ATG_API_KEY" \
  -o results.zip \
  https://atg-dev.azurecontainerinstances.net/api/v1/operations/op-g7h8i9j0k1l2/download
```

**Response (200 OK):**
- Binary file download (ZIP archive)
- Contains generated templates, scripts, documentation

**Response Codes:**
- `200 OK` - Download started
- `404 Not Found` - Operation or results not found
- `410 Gone` - Results expired/deleted
- `401 Unauthorized` - Invalid API key

### Graph Queries

#### POST /api/v1/query

Execute Cypher query against tenant graph.

**Request:**
```bash
curl -X POST \
  -H "Authorization: Bearer $ATG_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "12345678-1234-1234-1234-123456789abc",
    "query": "MATCH (n:Resource) RETURN count(n) as total"
  }' \
  https://atg-dev.azurecontainerinstances.net/api/v1/query
```

**Request Body:**
```json
{
  "tenant_id": "string (required)",
  "query": "string (required, Cypher query)",
  "parameters": "object (optional, query parameters)"
}
```

**Response (200 OK):**
```json
{
  "results": [
    {
      "total": 1247
    }
  ],
  "columns": ["total"],
  "row_count": 1,
  "execution_time_ms": 45
}
```

**Response Codes:**
- `200 OK` - Query executed
- `400 Bad Request` - Invalid query syntax
- `401 Unauthorized` - Invalid API key
- `404 Not Found` - Tenant graph not found

## WebSocket API

### Progress Streaming

Connect to WebSocket for real-time progress updates.

**Endpoint:**
```
wss://atg-{environment}.azurecontainerinstances.net/ws/progress/{operation_id}
```

**Authentication:**
```
Authorization: Bearer {api_key}
```

**Connection:**
```javascript
const ws = new WebSocket(
  'wss://atg-dev.azurecontainerinstances.net/ws/progress/op-a1b2c3d4e5f6',
  {
    headers: {
      'Authorization': `Bearer ${apiKey}`
    }
  }
);

ws.on('open', () => {
  console.log('Connected to progress stream');
});

ws.on('message', (data) => {
  const event = JSON.parse(data);
  console.log('Progress:', event);
});

ws.on('close', () => {
  console.log('Connection closed');
});

ws.on('error', (error) => {
  console.error('WebSocket error:', error);
});
```

**Event Types:**

**Status Update:**
```json
{
  "type": "status",
  "operation_id": "op-a1b2c3d4e5f6",
  "status": "running",
  "timestamp": "2025-12-09T12:35:15Z"
}
```

**Progress Update:**
```json
{
  "type": "progress",
  "operation_id": "op-a1b2c3d4e5f6",
  "phase": "scanning",
  "message": "Scanning subscription 2/5: Development",
  "percent": 40,
  "timestamp": "2025-12-09T12:36:42Z"
}
```

**Log Message:**
```json
{
  "type": "log",
  "operation_id": "op-a1b2c3d4e5f6",
  "level": "INFO",
  "message": "Discovered 125 resources in subscription",
  "timestamp": "2025-12-09T12:37:08Z"
}
```

**Completion:**
```json
{
  "type": "complete",
  "operation_id": "op-a1b2c3d4e5f6",
  "status": "completed",
  "result": {
    "resources_discovered": 1247,
    "relationships_created": 3892,
    "duration_seconds": 735
  },
  "timestamp": "2025-12-09T12:42:15Z"
}
```

**Error:**
```json
{
  "type": "error",
  "operation_id": "op-a1b2c3d4e5f6",
  "error": "Azure authentication failed",
  "error_code": "AUTH_FAILED",
  "timestamp": "2025-12-09T12:35:30Z"
}
```

## Error Codes

### HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | OK | Success |
| 202 | Accepted | Operation queued |
| 400 | Bad Request | Check request parameters |
| 401 | Unauthorized | Verify API key |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Operation state conflict |
| 429 | Too Many Requests | Rate limit exceeded, retry later |
| 500 | Internal Server Error | Server error, contact support |
| 503 | Service Unavailable | Service overloaded or restarting |

### Application Error Codes

**Error Response Format:**
```json
{
  "error": "Error message",
  "error_code": "ERROR_CODE",
  "details": {
    "field": "Additional context"
  },
  "timestamp": "2025-12-09T12:34:56Z"
}
```

**Common Error Codes:**

| Code | Description | Solution |
|------|-------------|----------|
| `INVALID_API_KEY` | API key invalid or expired | Check API key format and expiration |
| `TENANT_NOT_FOUND` | Tenant graph doesn't exist | Run scan operation first |
| `OPERATION_NOT_FOUND` | Operation ID not found | Verify operation ID |
| `INVALID_QUERY` | Cypher query syntax error | Check query syntax |
| `AUTH_FAILED` | Azure authentication failed | Verify Azure credentials |
| `QUOTA_EXCEEDED` | Resource quota exceeded | Wait or contact administrator |
| `RATE_LIMITED` | Too many requests | Implement exponential backoff |

## Rate Limits

**Per API Key:**
- 100 requests per minute
- 1000 requests per hour
- 10 concurrent operations

**Rate Limit Headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 87
X-RateLimit-Reset: 1702134896
```

**Rate Limit Response (429):**
```json
{
  "error": "Rate limit exceeded",
  "error_code": "RATE_LIMITED",
  "retry_after": 42,
  "timestamp": "2025-12-09T12:34:56Z"
}
```

## Pagination

List endpoints support pagination:

**Request:**
```bash
curl -H "Authorization: Bearer $ATG_API_KEY" \
  "https://atg-dev.azurecontainerinstances.net/api/v1/operations?limit=10&offset=20"
```

**Response Headers:**
```
X-Total-Count: 157
X-Limit: 10
X-Offset: 20
Link: <https://.../operations?limit=10&offset=30>; rel="next"
```

## SDK Examples

### Python

```python
import requests
import json

class ATGClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def start_scan(self, tenant_id, parameters=None):
        response = requests.post(
            f"{self.base_url}/api/v1/scan",
            headers=self.headers,
            json={
                "tenant_id": tenant_id,
                "parameters": parameters or {}
            }
        )
        response.raise_for_status()
        return response.json()

    def get_operation(self, operation_id):
        response = requests.get(
            f"{self.base_url}/api/v1/scan/{operation_id}",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

# Usage
client = ATGClient(
    "https://atg-dev.azurecontainerinstances.net",
    "atg_dev_abc123..."
)

result = client.start_scan("12345678-1234-1234-1234-123456789abc")
print(f"Operation ID: {result['operation_id']}")
```

### JavaScript

```javascript
class ATGClient {
  constructor(baseUrl, apiKey) {
    this.baseUrl = baseUrl;
    this.apiKey = apiKey;
  }

  async startScan(tenantId, parameters = {}) {
    const response = await fetch(`${this.baseUrl}/api/v1/scan`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        tenant_id: tenantId,
        parameters
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${await response.text()}`);
    }

    return await response.json();
  }

  async getOperation(operationId) {
    const response = await fetch(
      `${this.baseUrl}/api/v1/scan/${operationId}`,
      {
        headers: {
          'Authorization': `Bearer ${this.apiKey}`
        }
      }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${await response.text()}`);
    }

    return await response.json();
  }
}

// Usage
const client = new ATGClient(
  'https://atg-dev.azurecontainerinstances.net',
  'atg_dev_abc123...'
);

const result = await client.startScan('12345678-1234-1234-1234-123456789abc');
console.log(`Operation ID: ${result.operation_id}`);
```

## Next Steps

- [User Guide](./USER_GUIDE.md) - Learn how to use remote mode
- [Configuration Guide](./CONFIGURATION.md) - Configure client access
- [Troubleshooting Guide](./TROUBLESHOOTING.md) - Common issues
- [Deployment Guide](./DEPLOYMENT.md) - Deploy remote service
