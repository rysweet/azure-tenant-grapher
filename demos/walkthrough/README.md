# Azure Tenant Grapher Demo Walkthrough

A comprehensive demo and testing system for Azure Tenant Grapher that showcases all features through automated scenarios.

## ✨ Features

- **Automated walkthroughs** of every tab and feature
- **Screenshot capture** at key interaction points
- **Test assertions** to validate functionality
- **Story-based flows** for different use cases
- **HTML gallery generation** for visual documentation
- **Health checks** for comprehensive pre-flight validation
- **Service management** for automatic startup/shutdown
- **Error recovery** with retry logic and graceful degradation
- **Clear error messages** with actionable remediation steps

## 🚀 Quick Start

### Automated Setup (Recommended)

```bash
# Run the setup script to install all prerequisites
cd demos/walkthrough
./setup_demo.sh
```

The setup script will:
- Check all prerequisites (Python, Node.js, Docker, Azure CLI)
- Install Python dependencies
- Install Playwright browsers
- Start Neo4j if not running
- Check Azure authentication
- Install SPA dependencies
- Create default configuration

### Running Your First Demo

```bash
# Run health checks and start services if needed
python orchestrator.py --health-check --start-services

# Run quick demo
python orchestrator.py --story quick_demo

# Generate and view screenshot gallery
python orchestrator.py --gallery
open screenshots/gallery.html
```

## 📋 Prerequisites

### Required Software

- **Python 3.8+** - For orchestrator and utilities
- **Node.js 16+** - For SPA application
- **Docker** - For Neo4j database
- **Azure CLI** - For authentication

### Services Required

- **Neo4j database** (ports 7474/7687)
- **API server** (port 8000)
- **SPA application** (port 3000)

## 📖 Usage

### Health Checks

```bash
# Run comprehensive health checks
python orchestrator.py --health-check

# Run health check with a story
python orchestrator.py --health-check --story quick_demo
```

### Service Management

```bash
# Start all required services
python orchestrator.py --start-services

# Run demo and auto-start services if needed
python orchestrator.py --story quick_demo --start-services

# Stop services after demo
python orchestrator.py --stop-services
```

### Running Scenarios

```bash
# Run a complete story
python orchestrator.py --story full_walkthrough

# Run a specific scenario
python orchestrator.py --scenario 03_scan

# Run in headless mode
python orchestrator.py --story quick_demo --headless

# Enable debug logging
python orchestrator.py --story quick_demo --debug

# List available scenarios and stories
python orchestrator.py --list-scenarios
```

## ⚙️ Configuration

### Configuration Files

- `config.toml` - Main configuration file
- `config.prod.toml` - Production overrides
- Environment variables are expanded in configs

### Configuration Structure

```toml
[default]
app_url = "http://localhost:3000"
api_url = "http://localhost:8000"
timeout = 30
retry_attempts = 3
retry_delay = 2

[services.api]
name = "azure-tenant-grapher-api"
command = "python -m azure_tenant_grapher serve"
working_dir = "../.."
health_endpoint = "http://localhost:8000/health"
startup_timeout = 30
port = 8000

[services.app]
name = "azure-tenant-grapher-spa"
command = "npm start"
working_dir = "../../spa"
health_endpoint = "http://localhost:3000"
startup_timeout = 60
port = 3000

[browser]
headless = false
viewport = { width = 1920, height = 1080 }

[screenshot]
enabled = true
path = "./screenshots"
format = "png"
```

### Environment Variables

- `DEMO_ENV` - Set to 'production' to use config.prod.toml
- `DEMO_HEADLESS` - Set to 'true' for headless mode
- `DEMO_DEBUG` - Set to 'true' for debug logging

## 🏗️ Architecture

### Modular Components

```
orchestrator.py          # Main coordinator
├── modules/
│   ├── config_manager   # Configuration handling
│   ├── error_reporter   # Error messages & remediation
│   ├── health_checker   # Pre-flight validation
│   ├── scenario_runner  # Scenario execution
│   └── service_manager  # Service lifecycle
├── scenarios/           # Individual tab demos
├── stories/            # Combined workflows
└── utils/              # Screenshot & test utilities
```

### Module Responsibilities

- **config_manager**: Load and validate configurations
- **error_reporter**: Format errors with remediation steps
- **health_checker**: Verify all prerequisites
- **scenario_runner**: Execute scenarios with retry logic
- **service_manager**: Start/stop required services

## 📚 Scenarios

| Scenario | Description | Key Features |
|----------|-------------|--------------|
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

## 📖 Stories

### Quick Demo (`quick_demo.yaml`)
- Basic authentication
- Scan existing resources
- Visualize graph
- Generate specification
- **Duration**: ~5 minutes

### Full Walkthrough (`full_walkthrough.yaml`)
- Complete feature tour
- All tabs and functions
- End-to-end workflow
- **Duration**: ~15 minutes

### Security Focus (`security_focus.yaml`)
- Threat modeling emphasis
- Security configurations
- Compliance checks
- **Duration**: ~10 minutes

## 📸 Screenshot Organization

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
├── metadata.json
└── gallery.html
```

## 🧪 Test Assertions

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

## 🔧 Development

### Adding a New Scenario

1. Create YAML file in `scenarios/`
2. Define steps and assertions
3. Add to relevant stories
4. Update documentation

### Custom Assertions

Add to `utils/test_assertions.py`:
```python
async def custom_assertion(page, params):
    # Custom validation logic
    pass
```

## 🚀 CI/CD Integration

```yaml
# .github/workflows/demo.yml
- name: Setup Demo Environment
  run: |
    cd demos/walkthrough
    ./setup_demo.sh

- name: Run Demo Tests
  run: |
    python orchestrator.py --health-check --headless --story full_walkthrough

- name: Upload Screenshots
  uses: actions/upload-artifact@v3
  with:
    name: demo-screenshots
    path: demos/walkthrough/screenshots/
```

## 🐛 Troubleshooting

### Common Issues

1. **Service not available**
   ```
   ✗ API server is not running
   Remediation: Start with: python -m azure_tenant_grapher serve
   ```

2. **Authentication failures**
   ```
   ✗ Not authenticated with Azure
   Remediation: Run: az login --tenant <your-tenant-id>
   ```

3. **Missing dependencies**
   ```
   ✗ playwright not installed
   Remediation: pip install playwright && playwright install chromium
   ```

4. **Port conflicts**
   ```
   ✗ Port 8000 is already in use
   Remediation: Stop conflicting service or change port in config.toml
   ```

### Debug Mode

Enable detailed logging:
```bash
# Via CLI flag
python orchestrator.py --debug --story quick_demo

# Via environment variable
export DEMO_DEBUG=true
python orchestrator.py --story quick_demo
```

## 🖼️ Gallery Generation

The system automatically generates an HTML gallery:

```bash
# Generate gallery from existing screenshots
python orchestrator.py --gallery

# Generate with custom settings
python orchestrator.py --gallery --gallery-title "My Demo" --gallery-template grid

# Open in browser
open screenshots/gallery.html
```

## 📦 Requirements

### Python Dependencies

```txt
playwright>=1.40.0
pyyaml>=6.0
pytest>=7.4.0
pytest-asyncio>=0.21.0
httpx>=0.24.0
psutil>=5.9.0
pydantic>=2.0.0
rich>=13.0.0
tomli>=2.0.0  # Python < 3.11
jinja2>=3.1.2
pillow>=10.0.0
```

### System Requirements

- 4GB RAM minimum
- 1GB free disk space for screenshots
- Network access to Azure services

## 🔒 Security Notes

- Azure credentials are never stored in configs
- Use environment variables for sensitive data
- Screenshots may contain sensitive information
- Clean up screenshots after demo sessions

## 📄 License

See main project LICENSE file.
