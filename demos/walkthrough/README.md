# Azure Tenant Grapher Demo Walkthrough

A comprehensive demo and testing system for Azure Tenant Grapher that showcases all features through automated scenarios.

## Overview

This demo system provides:
- **Automated walkthroughs** of every tab and feature
- **Screenshot capture** at key interaction points
- **Test assertions** to validate functionality
- **Story-based flows** for different use cases
- **HTML gallery generation** for visual documentation

## Quick Start

```bash
# Run full walkthrough
python orchestrator.py --story full_walkthrough

# Run quick demo
python orchestrator.py --story quick_demo

# Run individual scenario
python orchestrator.py --scenario 03_scan

# Generate screenshot gallery
python orchestrator.py --gallery
```

## Architecture

### Components

1. **Orchestrator** (`orchestrator.py`)
   - Main demo runner
   - Manages scenario execution
   - Handles screenshot organization
   - Generates reports

2. **Scenarios** (`scenarios/`)
   - Individual tab demonstrations
   - Each scenario is self-contained
   - YAML-based configuration
   - Includes test assertions

3. **Stories** (`stories/`)
   - Combinations of scenarios
   - Different user journeys
   - Customizable flows

4. **Utils** (`utils/`)
   - Screenshot management
   - Test assertions
   - Helper functions

## Scenarios

| Scenario | Description | Screenshots |
|----------|-------------|-------------|
| 00_setup | Initial setup and authentication | Login, workspace creation |
| 01_status | Dashboard status overview | System health, metrics |
| 02_config | Configuration management | Settings, options |
| 03_scan | Azure resource scanning | Discovery process |
| 04_visualize | Graph visualization | Interactive network diagram |
| 05_generate_spec | Specification generation | YAML output |
| 06_generate_iac | Infrastructure as Code | Terraform/Bicep generation |
| 07_threat_model | Security threat modeling | Risk analysis |
| 08_agent_mode | AI agent interactions | Chat interface |
| 09_create_tenant | Tenant provisioning | New environment setup |
| 10_cli | Command-line interface | Terminal operations |
| 11_logs | System logging | Debug information |
| 12_docs | Documentation access | Help system |
| 13_undeploy | Resource cleanup | Teardown process |

## Stories

### Quick Demo (`quick_demo.yaml`)
- Basic authentication
- Scan existing resources
- Visualize graph
- Generate specification

### Full Walkthrough (`full_walkthrough.yaml`)
- Complete feature tour
- All tabs and functions
- End-to-end workflow

### Security Focus (`security_focus.yaml`)
- Threat modeling emphasis
- Security configurations
- Compliance checks

## Screenshot Organization

Screenshots are organized by:
- **Timestamp**: `YYYYMMDD_HHMMSS`
- **Scenario**: Grouped by feature
- **Step**: Sequential within scenario

Example structure:
```
screenshots/
├── 20240315_143022_01_status_dashboard.png
├── 20240315_143025_01_status_metrics.png
├── 20240315_143030_02_config_settings.png
└── gallery.html
```

## Test Assertions

Each scenario includes assertions:
- Element visibility
- Data presence
- State transitions
- Error handling

Example:
```yaml
assertions:
  - type: element_visible
    selector: "[data-testid='scan-button']"
  - type: text_contains
    selector: ".status-message"
    value: "Scan complete"
```

## Configuration

### config.yaml

```yaml
app:
  url: "http://localhost:3000"
  timeout: 30000

screenshot:
  enabled: true
  format: "png"
  quality: 90
  fullPage: false

test:
  headless: false
  slowMo: 100
  viewport:
    width: 1920
    height: 1080
```

## Development

### Adding a New Scenario

1. Create YAML file in `scenarios/`
2. Define steps and assertions
3. Add to relevant stories
4. Update documentation

### Custom Assertions

Add to `utils/test_assertions.py`:
```python
def custom_assertion(page, params):
    # Custom validation logic
    pass
```

## CI/CD Integration

```yaml
# .github/workflows/demo.yml
- name: Run Demo Tests
  run: |
    python orchestrator.py --story full_walkthrough --headless
    python orchestrator.py --gallery --upload
```

## Troubleshooting

### Common Issues

1. **Authentication failures**
   - Check credentials in environment
   - Verify Azure AD configuration

2. **Screenshot failures**
   - Ensure write permissions
   - Check disk space

3. **Timeout errors**
   - Increase timeout in config
   - Check network connectivity

## Gallery Generation

The system automatically generates an HTML gallery:

```bash
# Generate gallery from existing screenshots
python orchestrator.py --gallery

# Open in browser
open screenshots/gallery.html
```

## Requirements

- Python 3.11+
- Playwright
- gadugi-agentic-test framework
- Azure CLI (for authentication)

## License

See main project LICENSE file.