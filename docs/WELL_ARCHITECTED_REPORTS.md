# Well-Architected Framework Reports

The Azure Tenant Grapher can generate comprehensive Well-Architected Framework (WAF) analysis reports that identify architectural patterns in your Azure environment and provide actionable recommendations aligned with Microsoft's best practices.

## Overview

The `atg report well-architected` command analyzes your Azure tenant graph to:

1. **Detect Architectural Patterns**: Identifies 10 common Azure patterns (Web Apps, VM Workloads, Containers, etc.)
2. **Map to WAF Pillars**: Associates patterns with WAF pillars (Reliability, Security, Cost Optimization, etc.)
3. **Provide Recommendations**: Generates specific, actionable recommendations for each pattern
4. **Update Resource Descriptions**: Enhances Neo4j resource descriptions with WAF insights and documentation links
5. **Generate Multiple Report Formats**: Creates markdown reports, interactive Jupyter notebooks, and JSON data

## Quick Start

```bash
# Generate a full Well-Architected Framework report
uv run atg report well-architected

# Output location: outputs/well_architected_report_<timestamp>/
```

## Command Options

```bash
# Custom output directory
uv run atg report well-architected -o my_waf_report

# Skip updating resource descriptions in Neo4j
uv run atg report well-architected --skip-description-updates

# Skip visualizations (faster, no matplotlib required)
uv run atg report well-architected --no-visualizations

# Combine options
uv run atg report well-architected -o reports/waf --no-visualizations
```

## Output Files

The command generates the following files:

### 1. Markdown Report (`well_architected_report.md`)
Human-readable report with:
- Executive summary
- Pattern completeness scores
- WAF pillar mappings
- Specific recommendations
- Links to Microsoft documentation

### 2. Interactive Jupyter Notebook (`well_architected_analysis.ipynb`)
Executable notebook containing:
- Pattern summary table
- Interactive pattern details
- Embedded WAF insights
- Recommendation lists
- Can be opened in Jupyter for further exploration

### 3. JSON Data (`well_architected_insights.json`)
Machine-readable data with:
- Full pattern analysis results
- WAF mappings
- Resource lists
- Recommendations
- Useful for programmatic access or integration

### 4. Visualizations (Optional)
- `architectural_patterns_overview.png` - Pattern relationship diagram
- Other visualizations from pattern analysis

### 5. Summary (`report_summary.json`)
Metadata about the report:
- Generation timestamp
- Patterns detected count
- Resources analyzed/updated
- File paths

## Architectural Patterns Detected

The reporter identifies these common Azure patterns:

### 1. Web Application
**Resources**: App Service, Storage, Application Insights
**WAF Pillars**: Reliability, Performance Efficiency, Cost Optimization
**Learn More**: [App Service Guide](https://learn.microsoft.com/en-us/azure/well-architected/service-guides/app-service-web-apps)

### 2. Virtual Machine Workload
**Resources**: VMs, Disks, NICs, VNets, NSGs
**WAF Pillars**: Reliability, Security, Operational Excellence
**Learn More**: [VM Guide](https://learn.microsoft.com/en-us/azure/well-architected/service-guides/virtual-machines)

### 3. Container Platform
**Resources**: AKS, Container Registry, VNets, Load Balancers
**WAF Pillars**: Reliability, Performance Efficiency, Security
**Learn More**: [AKS Guide](https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-kubernetes-service)

### 4. Data Platform
**Resources**: SQL/PostgreSQL, Private Endpoints, Storage
**WAF Pillars**: Security, Reliability, Performance Efficiency
**Learn More**: [SQL Database Guide](https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-sql-database)

### 5. Serverless Application
**Resources**: Function Apps, Storage, Key Vault, Application Insights
**WAF Pillars**: Cost Optimization, Performance Efficiency, Operational Excellence
**Learn More**: [Functions Guide](https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-functions)

### 6. Data Analytics
**Resources**: Data Explorer, Workspaces, Storage, Event Hubs
**WAF Pillars**: Performance Efficiency, Cost Optimization, Operational Excellence
**Learn More**: [Data Explorer Guide](https://learn.microsoft.com/en-us/azure/well-architected/service-guides/azure-data-explorer)

### 7. Secure Workload
**Resources**: Key Vault, Private Endpoints, Private DNS, NICs
**WAF Pillars**: Security, Reliability
**Learn More**: [Security Pillar](https://learn.microsoft.com/en-us/azure/well-architected/security/)

### 8. Managed Identity Pattern
**Resources**: Managed Identities, App Services, AKS, VMs
**WAF Pillars**: Security, Operational Excellence
**Learn More**: [Identity & Authentication](https://learn.microsoft.com/en-us/azure/well-architected/security/design-identity-authentication)

### 9. Monitoring & Observability
**Resources**: Application Insights, Log Analytics, Data Collection Rules
**WAF Pillars**: Operational Excellence, Reliability
**Learn More**: [Observability](https://learn.microsoft.com/en-us/azure/well-architected/observability/)

### 10. Network Security
**Resources**: NSGs, VNets, Subnets, Bastion
**WAF Pillars**: Security, Reliability
**Learn More**: [Network Security](https://learn.microsoft.com/en-us/azure/well-architected/security/design-network)

## Resource Description Updates

By default, the command updates resource descriptions in Neo4j with WAF insights:

```cypher
// Example updated resource properties
{
  id: "/subscriptions/.../sites/myapp",
  type: "Microsoft.Web/sites",
  name: "myapp",
  llm_description: "Web application... [original description]

  🏗️ **Architectural Pattern**: Web Application
  **WAF Pillars**: Reliability, Performance Efficiency, Cost Optimization
  **Completeness**: 100%
  **Learn More**: https://learn.microsoft.com/...

  **Recommendations**:
  1. Enable auto-scaling based on metrics
  2. Use deployment slots for zero-downtime deployments
  3. Implement Application Insights for monitoring
  ",
  waf_pattern: "Web Application",
  waf_pillars: "Reliability, Performance Efficiency, Cost Optimization",
  waf_url: "https://learn.microsoft.com/...",
  waf_updated_at: "2025-12-09T10:30:00Z"
}
```

These enhanced descriptions:
- Appear in graph visualizations
- Are searchable in Neo4j
- Provide context in IaC generation
- Link to official Microsoft documentation

**To skip updates**: Use `--skip-description-updates` flag

## Viewing the Interactive Notebook

After generation, open the notebook:

```bash
# Navigate to report directory
cd outputs/well_architected_report_20250109_120000/

# Launch Jupyter
jupyter notebook well_architected_analysis.ipynb

# Or use Jupyter Lab
jupyter lab well_architected_analysis.ipynb
```

The notebook contains:
- Interactive pattern summary table
- Drill-down sections for each pattern
- Embedded recommendations
- Links to WAF documentation
- Can be exported to HTML/PDF

## Use Cases

### 1. Architecture Review
Generate a report to understand your current architecture and identify improvement opportunities.

```bash
uv run atg scan --tenant-id <TENANT_ID>
uv run atg report well-architected
```

### 2. Compliance Assessment
Review patterns against WAF pillars for compliance and best practices.

### 3. Migration Planning
Identify patterns before migration to understand architecture and dependencies.

### 4. Cost Optimization
Use pattern insights to identify over-provisioned resources and optimization opportunities.

### 5. Documentation Generation
Use the markdown report and notebook for architecture documentation.

### 6. Continuous Improvement
Run reports periodically to track architectural improvements over time.

## Integration with Other Features

### With `analyze-patterns`
The Well-Architected reporter builds on the pattern analysis:

```bash
# Basic pattern analysis
uv run atg analyze-patterns

# Full WAF report (includes pattern analysis + WAF insights)
uv run atg report well-architected
```

### With Graph Queries
Query resources with WAF annotations:

```cypher
// Find all resources in a specific pattern
MATCH (r:Resource)
WHERE r.waf_pattern = "Web Application"
RETURN r.name, r.type, r.waf_url

// Find resources by WAF pillar
MATCH (r:Resource)
WHERE r.waf_pillars CONTAINS "Security"
RETURN r.name, r.waf_pattern, r.waf_pillars
```

### With Threat Modeling
Combine with threat modeling for security-focused analysis:

```bash
uv run atg report well-architected
uv run atg threat-model
```

## Example Report Excerpt

```markdown
## Web Application

**Completeness**: 100% (4 of 4 resource types)
**Connections**: 456 relationships

### Well-Architected Framework Pillars

**Reliability**, **Performance Efficiency**, **Cost Optimization**

### Description

App Service provides built-in auto-scaling, load balancing, and deployment
slots for high availability.

### Resources in This Pattern

**Present**: `sites`, `serverFarms`, `storageAccounts`, `components`

### Recommendations

1. Enable auto-scaling based on metrics
2. Use deployment slots for zero-downtime deployments
3. Implement Application Insights for monitoring
4. Configure backup and disaster recovery

### Learn More

📚 [Azure Well-Architected Framework: Web Application](https://learn.microsoft.com/...)
```

## Troubleshooting

### "Missing Dependencies" Error

```bash
# Install visualization dependencies
uv pip install matplotlib scipy

# Or run without visualizations
uv run atg report well-architected --no-visualizations
```

### "No patterns detected"

Ensure you've scanned a tenant first:
```bash
uv run atg scan --tenant-id <TENANT_ID>
```

### Notebook Won't Open

Ensure Jupyter is installed:
```bash
uv pip install jupyter

# Or
pip install jupyter
```

### Neo4j Connection Error

Check Neo4j is running:
```bash
docker ps | grep neo4j
```

## Future Enhancements

Planned improvements:
- [ ] Custom pattern definitions via config file
- [ ] Historical trend analysis (compare reports over time)
- [ ] Integration with Azure Advisor recommendations
- [ ] Cost estimation per pattern
- [ ] Security scoring per pattern
- [ ] Export to PowerPoint/Word
- [ ] Email report delivery
- [ ] Webhook notifications for pattern changes

## Related Documentation

- [Architectural Pattern Analysis](./ARCHITECTURAL_PATTERN_ANALYSIS.md)
- [Azure Well-Architected Framework](https://learn.microsoft.com/en-us/azure/well-architected/)
- [Neo4j Query Guide](./NEO4J_SCHEMA_REFERENCE.md)
- [CLI Commands](../CLAUDE.md#running-the-cli)

## API Usage

For programmatic access:

```python
from src.well_architected_reporter import WellArchitectedReporter
from pathlib import Path

# Initialize reporter
reporter = WellArchitectedReporter(
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="password"
)

# Generate report
summary = reporter.generate_full_report(
    output_dir=Path("outputs/my_waf_report"),
    update_descriptions=True,
    generate_visualizations=True
)

print(f"Generated report with {summary['patterns_detected']} patterns")
print(f"Updated {summary['resources_updated']} resources")
```

---

**Questions or Issues?** Please open an issue on GitHub or consult the [main documentation](../README.md).
