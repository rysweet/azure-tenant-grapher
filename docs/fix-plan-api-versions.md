# Fix Plan: Azure Discovery Service API Version and Properties Extraction

## Problem Analysis

1. **API Version Issue**: The `get_by_id()` method requires resource-type-specific API versions, not a generic one
2. **SDK Retries**: Azure SDK already has built-in retry mechanisms we should leverage
3. **Error Handling**: Current implementation doesn't log specific errors for debugging

## Solution Design

### 1. Dynamic API Version Resolution

#### Approach A: Query Provider for API Versions (Preferred)
- Cache provider information at startup
- Extract resource provider and type from resource ID
- Look up appropriate API version from cache
- Fall back to a safe default if needed

#### Approach B: Use Latest Stable API Version
- Azure SDK can determine API versions automatically
- Pass `None` for api_version to let SDK decide
- Risk: May use preview versions

### 2. Leverage Azure SDK Retry Policy

The SDK already includes:
- Exponential backoff retry (default: 10 retries)
- Automatic handling of transient errors (408, 429, 5xx)
- Configurable retry policy

We should:
- Use the default retry policy (it's already active)
- Optionally configure custom retry for specific scenarios
- Log retry attempts for visibility

### 3. Improved Error Handling

Add:
- Detailed error logging with resource ID and error type
- Separate handling for different error categories:
  - Authentication errors (no retry)
  - Rate limiting (respect retry-after header)
  - API version mismatch (try alternative version)
  - Network errors (retry with backoff)

## Implementation Steps

### Phase 1: Fix azure_discovery_service.py

1. **Remove the enhanced service** - Delete azure_discovery_service_enhanced.py
2. **Add API version resolution** - Query providers and cache API versions
3. **Implement parallel fetching** - Add to existing service
4. **Improve error handling** - Add detailed logging and categorization

### Phase 2: Testing

1. **Unit tests** with mocked responses
2. **Integration tests** with real API calls (limited)
3. **Error scenario tests** (wrong API version, rate limiting, etc.)

### Phase 3: Cleanup

1. Remove all references to enhanced service
2. Update azure_tenant_grapher.py to use fixed service
3. Ensure backward compatibility

## Code Structure

```python
class AzureDiscoveryService:
    def __init__(self, ...):
        self._api_version_cache = {}  # Cache for provider API versions
        self._max_build_threads = getattr(config.processing, 'max_build_threads', 20)
    
    async def _get_api_version(self, resource_id: str) -> str:
        """Get appropriate API version for resource type."""
        # Parse resource ID to get provider and type
        # Query provider if not cached
        # Return appropriate version
    
    async def _fetch_resource_with_properties(self, resource_id: str, ...):
        """Fetch full resource with proper API version and error handling."""
        api_version = await self._get_api_version(resource_id)
        try:
            # SDK already handles retries
            resource = await asyncio.to_thread(
                client.resources.get_by_id,
                resource_id,
                api_version=api_version
            )
        except specific_errors as e:
            # Handle specific error types
            
    async def discover_resources_in_subscription(self, ...):
        """Enhanced discovery with parallel property fetching."""
        # Phase 1: List resources
        # Phase 2: Parallel fetch with proper API versions
```

## Success Criteria

1. ✅ Properties are successfully fetched for all resource types
2. ✅ Errors are properly logged with actionable information  
3. ✅ SDK retry mechanism is utilized (not duplicated)
4. ✅ Tests cover success and failure scenarios
5. ✅ No regression in existing functionality
6. ✅ CI passes with all tests green