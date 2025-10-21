# Azure Cost Management Service

This module provides comprehensive cost tracking, forecasting, and anomaly detection for Azure resources using the Azure Cost Management API and Neo4j graph database.

## Overview

The Cost Management Service enables:
- Fetching cost data from Azure Cost Management API
- Storing cost data in Neo4j with relationships to resources
- Querying and analyzing costs across different scopes
- Forecasting future costs using linear regression
- Detecting cost anomalies using Z-score method
- Generating cost reports in multiple formats

## Architecture

### Data Models (`src/models/cost_models.py`)

#### Core Models
- **CostData**: Represents actual cost data for a resource or scope
- **ForecastData**: Contains predicted future costs with confidence intervals
- **CostAnomaly**: Represents detected cost anomalies with severity levels
- **CostSummary**: Aggregated cost summary for a scope and period

#### Enums
- **Granularity**: `DAILY`, `MONTHLY`
- **TimeFrame**: `MONTH_TO_DATE`, `CUSTOM`, etc.
- **SeverityLevel**: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`

### Service Implementation (`src/services/cost_management_service.py`)

#### Key Features

**Rate Limiting**
- Implements 20 calls per 10 seconds limit for Azure API
- Automatic retry with exponential backoff for failed requests

**Error Handling**
- Custom exceptions: `CostManagementError`, `APIRateLimitError`, `InvalidScopeError`, `DataValidationError`
- Handles HTTP errors: 429 (rate limit), 401 (auth), 400 (bad request), 404 (not found)

**Neo4j Integration**
- Creates `Cost`, `CostForecast`, and `CostAnomaly` nodes
- Establishes `INCURS_COST` relationships between Resources/ResourceGroups/Subscriptions and Costs
- Efficient querying with proper indexing

## Usage Examples

### Initialize the Service

```python
from azure.identity import DefaultAzureCredential
from neo4j import AsyncGraphDatabase
from src.services.cost_management_service import CostManagementService

credential = DefaultAzureCredential()
neo4j_driver = AsyncGraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))

service = CostManagementService(neo4j_driver, credential)
await service.initialize()
```

### Fetch and Store Costs

```python
from datetime import date
from src.models.cost_models import TimeFrame, Granularity

# Fetch costs for a subscription
scope = "/subscriptions/12345678-1234-1234-1234-123456789abc"
costs = await service.fetch_costs(
    scope=scope,
    time_frame=TimeFrame.MONTH_TO_DATE,
    granularity=Granularity.DAILY
)

# Store in Neo4j
count = await service.store_costs(costs)
print(f"Stored {count} cost records")
```

### Query Cost Summary

```python
from datetime import date

summary = await service.query_costs(
    scope=scope,
    start_date=date(2024, 1, 1),
    end_date=date(2024, 1, 31),
    group_by="service_name"
)

print(f"Total cost: {summary.total_cost:.2f} {summary.currency}")
print(f"Average daily: {summary.average_daily_cost:.2f}")
```

### Forecast Costs

```python
# Forecast next 30 days
forecasts = await service.forecast_costs(
    scope=scope,
    forecast_days=30
)

for forecast in forecasts[:7]:
    print(f"{forecast.forecast_date}: ${forecast.predicted_cost:.2f} "
          f"({forecast.confidence_lower:.2f} - {forecast.confidence_upper:.2f})")
```

### Detect Anomalies

```python
# Detect cost anomalies in last 30 days
anomalies = await service.detect_anomalies(
    scope=scope,
    lookback_days=30,
    sensitivity=2.0  # Z-score threshold
)

for anomaly in anomalies:
    print(f"{anomaly.date}: {anomaly.resource_id}")
    print(f"  Expected: ${anomaly.expected_cost:.2f}")
    print(f"  Actual: ${anomaly.actual_cost:.2f}")
    print(f"  Deviation: {anomaly.deviation_percent:+.1f}%")
    print(f"  Severity: {anomaly.severity.value}")
```

### Allocate Costs by Tags

```python
allocation = await service.allocate_by_tags(
    tag_key="environment",
    start_date=date(2024, 1, 1),
    end_date=date(2024, 1, 31)
)

for tag_value, cost in allocation.items():
    print(f"{tag_value}: ${cost:.2f}")
```

### Generate Reports

```python
# Markdown report with forecast and anomalies
report = await service.generate_report(
    scope=scope,
    start_date=date(2024, 1, 1),
    end_date=date(2024, 1, 31),
    output_format="markdown",
    include_forecast=True,
    include_anomalies=True
)

print(report)

# JSON report
json_report = await service.generate_report(
    scope=scope,
    start_date=date(2024, 1, 1),
    end_date=date(2024, 1, 31),
    output_format="json"
)
```

## Neo4j Schema

### Nodes

**Cost Node**
```cypher
(:Cost {
    id: string,
    resource_id: string,
    resource_group: string,
    subscription_id: string,
    date: date,
    actual_cost: float,
    amortized_cost: float,
    usage_quantity: float,
    currency: string,
    service_name: string,
    meter_category: string,
    meter_name: string,
    tags: string (JSON),
    created_at: datetime,
    updated_at: datetime
})
```

**CostForecast Node**
```cypher
(:CostForecast {
    id: string,
    scope: string,
    forecast_date: date,
    predicted_cost: float,
    confidence_lower: float,
    confidence_upper: float,
    model_version: string,
    created_at: datetime
})
```

**CostAnomaly Node**
```cypher
(:CostAnomaly {
    id: string,
    resource_id: string,
    date: date,
    expected_cost: float,
    actual_cost: float,
    deviation_percent: float,
    severity: string,
    detected_at: datetime
})
```

### Relationships

```cypher
(:Resource)-[:INCURS_COST]->(:Cost)
(:ResourceGroup)-[:INCURS_COST]->(:Cost)
(:Subscription)-[:INCURS_COST]->(:Cost)
```

## Algorithms

### Linear Regression Forecasting

Uses simple linear regression to predict future costs:
1. Fetches last 90 days of historical data
2. Calculates slope and intercept: `y = mx + b`
3. Generates predictions for specified forecast period
4. Computes 95% confidence intervals using standard error

### Z-Score Anomaly Detection

Detects cost anomalies using statistical analysis:
1. Calculates mean and standard deviation for historical costs
2. Computes Z-score for each data point: `z = (x - μ) / σ`
3. Flags values exceeding sensitivity threshold (default: 2.0)
4. Assigns severity based on Z-score magnitude:
   - Z > 4: CRITICAL
   - Z > 3: HIGH
   - Z > 2.5: MEDIUM
   - Z > 2: LOW

## Error Handling

The service provides custom exceptions for different error scenarios:

```python
try:
    costs = await service.fetch_costs(scope=invalid_scope)
except InvalidScopeError:
    print("Invalid Azure scope provided")
except APIRateLimitError:
    print("Azure API rate limit exceeded")
except DataValidationError:
    print("Invalid input parameters")
except CostManagementError as e:
    print(f"General cost management error: {e}")
```

## Best Practices

1. **Rate Limiting**: Service automatically handles rate limiting, but be mindful of query frequency
2. **Scope Validation**: Always validate scope format before making API calls
3. **Data Freshness**: Cost data typically has 8-24 hour lag in Azure
4. **Forecasting**: Requires at least 14 days of historical data for accurate predictions
5. **Anomaly Detection**: Needs minimum 7 days of data per resource
6. **Neo4j Indexing**: Ensure proper indexes on `resource_id`, `date`, and `subscription_id` for performance

## Testing

Run unit tests:
```bash
uv run pytest tests/test_cost_models.py -v
```

## Dependencies

- `azure-mgmt-costmanagement>=4.0.0`
- `azure-identity>=1.15.0`
- `neo4j>=5.14.0`
- Python 3.12+

## Future Enhancements

- [ ] Machine learning models for more accurate forecasting
- [ ] Cost optimization recommendations
- [ ] Budget alerts and notifications
- [ ] Multi-cloud cost aggregation
- [ ] Cost allocation rules engine
- [ ] Interactive cost dashboards
