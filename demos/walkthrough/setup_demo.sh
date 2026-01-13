#!/bin/bash
# Demo Walkthrough Setup Script
# Ensures all prerequisites are installed and services are ready

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🚀 Azure Tenant Grapher Demo Setup"
echo "=================================="
echo ""

# Function to check command exists
check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}✗ $1 is not installed${NC}"
        echo "  Please install $1: $2"
        return 1
    else
        echo -e "${GREEN}✓ $1 is installed${NC}"
        return 0
    fi
}

# Function to check Python version
check_python_version() {
    python_version=$(python3 --version 2>&1 | awk '{print $2}')
    required_version="3.8.0"

    if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" = "$required_version" ]; then
        echo -e "${GREEN}✓ Python version $python_version meets requirements${NC}"
        return 0
    else
        echo -e "${RED}✗ Python version $python_version is too old (need >= $required_version)${NC}"
        return 1
    fi
}

# Check prerequisites
echo "Checking prerequisites..."
echo ""

errors=0

# Check commands
check_command "python3" "https://www.python.org/downloads/" || ((errors++))
check_command "node" "https://nodejs.org/" || ((errors++))
check_command "npm" "https://nodejs.org/" || ((errors++))
check_command "docker" "https://docs.docker.com/get-docker/" || ((errors++))
check_command "az" "https://docs.microsoft.com/en-us/cli/azure/install-azure-cli" || ((errors++))

# Check Python version
check_python_version || ((errors++))

if [ $errors -gt 0 ]; then
    echo ""
    echo -e "${RED}Please install missing prerequisites before continuing.${NC}"
    exit 1
fi

echo ""
echo "Installing Python dependencies..."
cd "$SCRIPT_DIR"

# Install demo dependencies
if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
fi

# Check if uv is available
if command -v uv &> /dev/null; then
    echo "Using uv to install dependencies..."
    uv pip install -r requirements.txt
else
    echo "Using pip to install dependencies..."
    pip install -r requirements.txt
fi

# Install Playwright browsers
echo ""
echo "Installing Playwright browsers..."
playwright install chromium

# Check if Neo4j is running
echo ""
echo "Checking Neo4j database..."
if docker ps | grep -q neo4j; then
    echo -e "${GREEN}✓ Neo4j is running${NC}"
else
    echo -e "${YELLOW}⚠ Neo4j is not running${NC}"
    echo "  Starting Neo4j..."
    cd "$PROJECT_ROOT"
    docker-compose -f docker/docker-compose.yml up -d neo4j
    echo "  Waiting for Neo4j to be ready..."
    sleep 10
fi

# Check Azure authentication
echo ""
echo "Checking Azure authentication..."
if az account show &> /dev/null; then
    echo -e "${GREEN}✓ Azure CLI is authenticated${NC}"
    tenant_id=$(az account show --query tenantId -o tsv)
    echo "  Tenant ID: $tenant_id"
else
    echo -e "${YELLOW}⚠ Not authenticated with Azure${NC}"
    echo "  Please run: az login"
fi

# Install SPA dependencies if needed
echo ""
echo "Checking SPA dependencies..."
SPA_DIR="$PROJECT_ROOT/spa"
if [ -d "$SPA_DIR" ]; then
    cd "$SPA_DIR"
    if [ ! -d "node_modules" ]; then
        echo "Installing SPA dependencies..."
        npm install
    else
        echo -e "${GREEN}✓ SPA dependencies are installed${NC}"
    fi
else
    echo -e "${RED}✗ SPA directory not found${NC}"
    ((errors++))
fi

# Create config if it doesn't exist
echo ""
echo "Setting up configuration..."
cd "$SCRIPT_DIR"
if [ ! -f "config.toml" ]; then
    if [ -f "config.toml.example" ]; then
        cp config.toml.example config.toml
        echo -e "${GREEN}✓ Created config.toml from example${NC}"
    else
        # Create a basic config
        cat > config.toml << 'EOF'
[default]
app_url = "http://localhost:3000"
api_url = "http://localhost:8000"
timeout = 30
retry_attempts = 3
retry_delay = 2
headless = false

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
fullPage = false

[reporting]
enabled = true
format = "html"
output_dir = "./reports"
include_screenshots = true
EOF
        echo -e "${GREEN}✓ Created default config.toml${NC}"
    fi
else
    echo -e "${GREEN}✓ config.toml exists${NC}"
fi

# Final summary
echo ""
echo "=================================="
echo "Setup Summary"
echo "=================================="

if [ $errors -eq 0 ]; then
    echo -e "${GREEN}✅ All prerequisites are installed!${NC}"
    echo ""
    echo "To run the demo:"
    echo ""
    echo "  1. Start the services (if not running):"
    echo "     cd $SCRIPT_DIR"
    echo "     python orchestrator.py --start-services"
    echo ""
    echo "  2. Run a demo:"
    echo "     python orchestrator.py --story quick_demo"
    echo ""
    echo "  3. Or run with health checks first:"
    echo "     python orchestrator.py --health-check --story quick_demo"
    echo ""
    echo "For more options:"
    echo "  python orchestrator.py --help"
else
    echo -e "${RED}❌ Setup incomplete. Please fix the errors above.${NC}"
    exit 1
fi
