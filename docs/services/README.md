# Azure Name Sanitizer Documentation

**Status**: [PLANNED - Implementation Pending]

This directory contains documentation for the Azure Name Sanitizer service, a centralized solution for transforming abstracted resource names into Azure-compliant names for globally unique resources.

---

## Documentation Overview

### 📘 Service Specification
**[AZURE_NAME_SANITIZER.md](AZURE_NAME_SANITIZER.md)**

Complete service specification including:
- Public API documentation
- All 36 supported globally unique resource types
- Character set rules and length constraints
- Before/after transformation examples
- Testing strategy
- Module philosophy

**Target Audience**: Developers implementing or maintaining the sanitizer service

---

### 🏗️ Architecture Document
**[../architecture/IaC_Name_Sanitization.md](../architecture/IaC_Name_Sanitization.md)**

High-level architecture covering:
- Five-phase name transformation pipeline
- Component responsibilities
- Resource type categories
- Character set rules
- Cross-tenant uniqueness strategy
- Migration path

**Target Audience**: Architects and developers understanding the system design

---

### 💡 Usage Examples
**[../examples/azure_name_sanitizer_usage.md](../examples/azure_name_sanitizer_usage.md)**

Concrete code examples showing:
- Basic usage pattern for handlers
- Storage Account handler (lowercase alphanumeric only)
- Key Vault handler (alphanumeric + hyphens)
- Container Registry handler (alphanumeric only, no hyphens)
- SQL Server handler (lowercase with hyphens)
- PostgreSQL handler (new handler pattern)
- Helper functions for tenant suffix generation
- Complete transformation flow from discovery to Terraform

**Target Audience**: Developers writing or updating Terraform handlers

---

### 🔍 Investigation Report
**[../../.claude/docs/INVESTIGATION_globally_unique_names_20260113.md](../../.claude/docs/INVESTIGATION_globally_unique_names_20260113.md)**

Detailed investigation findings:
- Root cause analysis (two-stage name transformation mismatch)
- Complete inventory of 36 globally unique resource types
- Current handler coverage (5 of 36 = 13.9%)
- Identified bugs and their impact
- Historical context and evolution
- Recommended fix approach (hybrid architecture)

**Target Audience**: Developers understanding the problem being solved

---

## Quick Navigation

### For Implementers
1. Read the [Investigation Report](../../.claude/docs/INVESTIGATION_globally_unique_names_20260113.md) to understand the problem
2. Review the [Architecture Document](../architecture/IaC_Name_Sanitization.md) for system design
3. Follow the [Service Specification](AZURE_NAME_SANITIZER.md) for API details
4. Reference [Usage Examples](../examples/azure_name_sanitizer_usage.md) while coding

### For Maintainers
1. Consult the [Service Specification](AZURE_NAME_SANITIZER.md) for API contracts
2. Check [Usage Examples](../examples/azure_name_sanitizer_usage.md) for handler patterns
3. Review [Architecture Document](../architecture/IaC_Name_Sanitization.md) for design rationale

### For Architects
1. Start with the [Investigation Report](../../.claude/docs/INVESTIGATION_globally_unique_names_20260113.md) for context
2. Study the [Architecture Document](../architecture/IaC_Name_Sanitization.md) for design decisions
3. Review the [Service Specification](AZURE_NAME_SANITIZER.md) for constraints and rules

---

## Key Concepts

### The Problem
Azure resources with globally unique DNS names have strict, resource-specific naming constraints. Only 5 of 36 globally unique resource types had proper sanitization logic, causing cross-tenant deployment failures.

### The Solution
A centralized `AzureNameSanitizer` service that:
- Knows all 36 resource types and their constraints
- Transforms abstracted names (with hyphens) into Azure-compliant names
- Handles character set rules, length limits, and format validation
- Provides single source of truth for Azure naming rules

### The Architecture
Five-phase pipeline:
1. **Discovery**: Azure API → Neo4j graph
2. **Abstraction**: IDAbstractionService → generic names with hyphens
3. **Sanitization**: AzureNameSanitizer → Azure-compliant names
4. **Global Uniqueness**: Add tenant suffix for cross-tenant deployments
5. **IaC Generation**: Terraform handlers → .tf files

---

## Resource Type Categories

The sanitizer handles **36 globally unique Azure resource types**:

| Category | Count | Examples |
|----------|-------|----------|
| **CRITICAL** | 10 | Storage, KeyVault, AppService, SQL, ACR, PostgreSQL, MySQL, APIM, CDN, AppConfig |
| **Integration/Messaging** | 4 | ServiceBus, EventHub, EventGrid, SignalR |
| **API/Networking** | 5 | FrontDoor, TrafficManager, AppGateway, Firewall, Bastion |
| **Data/Analytics** | 8 | DataFactory, Synapse, Databricks, HDInsight, CosmosDB, Redis, Search, Analysis |
| **AI/ML/IoT** | 4 | Cognitive, MachineLearning, IoTHub, IoTCentral |
| **Specialized** | 5 | BotService, Communication, SpringCloud, Grafana, StaticWebApps |

---

## Character Set Rules

Different resource types have different character requirements:

| Rule | Resource Types | Transformation |
|------|----------------|----------------|
| `lowercase_alphanum` | Storage, PostgreSQL, MySQL | Remove hyphens, lowercase |
| `alphanum_only` | Container Registry | Remove hyphens |
| `alphanum_hyphen` | Key Vault, App Service | Preserve hyphens, validate format |
| `lowercase_alphanum_hyphen` | SQL Server | Lowercase, preserve hyphens |

---

## Implementation Status

**Current State**: Documentation complete, implementation pending

**Next Steps**:
1. Implement `src/services/azure_name_sanitizer.py` following specification
2. Update 5 existing handlers to use sanitizer
3. Add sanitizer calls to 31 remaining handlers
4. Write comprehensive tests (unit, integration, E2E)

---

## Related Resources

- **Azure Naming Rules**: [Microsoft Learn - Naming rules and restrictions](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/resource-name-rules)
- **PSRule for Azure**: [Azure.Storage.Name](https://azure.github.io/PSRule.Rules.Azure/en/rules/Azure.Storage.Name/)
- **Historical Commits**: `3a66f1d` (research), `3b0cda9` (storage/acr), `80194fd` (cross-tenant)

---

## Document-Driven Development

This documentation was created **BEFORE** implementation following Document-Driven Development (DDD) principles:

- **Documentation IS the specification**: Code must match these docs exactly
- **[PLANNED] markers**: Indicate features not yet implemented
- **Concrete examples**: Show actual usage patterns, not placeholders
- **Complete coverage**: All 36 resource types documented upfront

When implementation begins, remove `[PLANNED]` markers as features are completed.

---

*All documentation in this directory follows amplihack's "The Eight Rules of Good Documentation" and the Diataxis framework.*
