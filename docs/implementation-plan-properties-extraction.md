# Implementation Plan: Full Resource Properties Extraction

## Overview
Implement parallel fetching of full Azure resource properties using `get_by_id()` API calls with configurable concurrency.

## Architecture Design

### Current Flow (Broken)
```
resources.list() → Basic metadata only (properties=None) → Store in Neo4j → Empty properties in specs
```

### New Flow (Fixed)
```
resources.list() → Resource IDs → Parallel get_by_id() → Full properties → Store in Neo4j → Complete specs
```

## Implementation Steps

### Step 1: Add Configuration Parameter
- Add `--max-build-threads` to CLI with default of 20
- Pass through to AzureDiscoveryService
- Use for controlling API call concurrency

### Step 2: Modify Azure Discovery Service

#### 2.1 Add Parallel Fetch Method
```python
async def _fetch_resource_with_properties(
    self,
    resource_id: str,
    semaphore: asyncio.Semaphore
) -> Dict[str, Any]:
    """Fetch full resource details including properties."""
    async with semaphore:
        try:
            # Use sync-to-async wrapper for Azure SDK
            resource = await asyncio.to_thread(
                self.resource_client.resources.get_by_id,
                resource_id,
                api_version='2021-04-01'
            )
            return self._resource_to_dict(resource)
        except Exception as e:
            logger.error(f"Failed to fetch {resource_id}: {e}")
            return None
```

#### 2.2 Update discover_resources_in_subscription
```python
async def discover_resources_in_subscription(self, subscription_id: str):
    # Phase 1: Get all resource IDs (fast)
    resource_basics = []
    for resource in self.resource_client.resources.list():
        resource_basics.append({
            "id": resource.id,
            "name": resource.name,
            "type": resource.type,
            "location": resource.location,
            "tags": resource.tags
        })

    # Phase 2: Fetch full details in parallel (slower but complete)
    semaphore = asyncio.Semaphore(self.max_build_threads)
    tasks = [
        self._fetch_resource_with_properties(r["id"], semaphore)
        for r in resource_basics
    ]

    # Process in batches to avoid memory issues
    batch_size = 100
    all_resources = []
    for i in range(0, len(tasks), batch_size):
        batch = tasks[i:i + batch_size]
        results = await asyncio.gather(*batch, return_exceptions=True)
        all_resources.extend([r for r in results if r and not isinstance(r, Exception)])

    return all_resources
```

### Step 3: Handle API Rate Limiting

```python
class RateLimiter:
    def __init__(self, max_calls_per_second=20):
        self.semaphore = asyncio.Semaphore(max_calls_per_second)
        self.min_interval = 1.0 / max_calls_per_second
        self.last_call = 0

    async def acquire(self):
        async with self.semaphore:
            now = time.time()
            sleep_time = self.last_call + self.min_interval - now
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            self.last_call = time.time()
```

### Step 4: Update Resource Processor
- Ensure properties field is properly serialized
- Handle complex nested structures
- Increase JSON length limit if needed

### Step 5: Error Handling & Retry Logic

```python
async def fetch_with_retry(self, func, *args, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await func(*args)
        except ClientError as e:
            if e.response['Error']['Code'] == 'TooManyRequestsException':
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                await asyncio.sleep(wait_time)
            else:
                raise
    raise Exception(f"Max retries exceeded")
```

## Performance Metrics

### Expected Performance
- **Sequential**: 1151 resources × 0.5s/request = ~10 minutes
- **Parallel (20 threads)**: 1151 resources ÷ 20 = ~30 seconds
- **With rate limiting**: ~2-3 minutes for 1000+ resources

### Memory Considerations
- Batch processing prevents holding all resources in memory
- Stream results to database as they complete
- Monitor memory usage during large builds

## Testing Strategy

1. **Unit Tests**
   - Mock get_by_id responses with full properties
   - Test semaphore limiting
   - Verify retry logic

2. **Integration Tests**
   - Test with real Azure resources (limited set)
   - Verify properties are stored correctly
   - Check spec generation includes properties

3. **Performance Tests**
   - Measure time with different thread counts
   - Monitor memory usage
   - Test rate limit handling

## Rollback Plan
If issues occur:
1. Keep old list-only method as fallback
2. Add feature flag to disable parallel fetching
3. Allow graceful degradation if get_by_id fails

## Success Criteria
- [ ] Properties populated for all resource types
- [ ] Build time remains under 5 minutes for 1000 resources
- [ ] Memory usage stays under 2GB
- [ ] Rate limits handled gracefully
- [ ] Generated specs show complete configuration details
