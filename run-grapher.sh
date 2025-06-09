#!/bin/bash
# Shell script to start Neo4j container and run the Azure Tenant Grapher

set -e

# Default values
NEO4J_URI="bolt://localhost:7688"
NEO4J_USER="neo4j"
NEO4J_PASSWORD="azure-grapher-2024"
CONTAINER_ONLY=false
NO_CONTAINER=false
VISUALIZE=false
VISUALIZE_ONLY=false
VISUALIZATION_PATH=""

# Function to show usage
show_usage() {
    echo "Usage: $0 --tenant-id <tenant-id> [options]"
    echo ""
    echo "Required:"
    echo "  --tenant-id <id>        Azure tenant ID"
    echo ""
    echo "Options:"
    echo "  --neo4j-uri <uri>       Neo4j connection URI (default: bolt://localhost:7688)"
    echo "  --neo4j-user <user>     Neo4j username (default: neo4j)"
    echo "  --neo4j-password <pwd>  Neo4j password (default: azure-grapher-2024)"
    echo "  --container-only        Start Neo4j container only, don't run grapher"
    echo "  --no-container          Skip container management, use existing Neo4j"
    echo "  --visualize             Generate 3D graph visualization after building graph"
    echo "  --visualize-only        Only generate visualization from existing graph data"
    echo "  --visualization-path    Path where to save the visualization HTML file"
    echo "  --help                  Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --tenant-id 12345678-1234-1234-1234-123456789012"
    echo "  $0 --tenant-id 12345678-1234-1234-1234-123456789012 --visualize"
    echo "  $0 --tenant-id 12345678-1234-1234-1234-123456789012 --visualize-only"
    echo "  $0 --tenant-id 12345678-1234-1234-1234-123456789012 --container-only"
    echo "  $0 --tenant-id 12345678-1234-1234-1234-123456789012 --no-container"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --tenant-id)
            TENANT_ID="$2"
            shift 2
            ;;
        --neo4j-uri)
            NEO4J_URI="$2"
            shift 2
            ;;
        --neo4j-user)
            NEO4J_USER="$2"
            shift 2
            ;;
        --neo4j-password)
            NEO4J_PASSWORD="$2"
            shift 2
            ;;
        --container-only)
            CONTAINER_ONLY=true
            shift
            ;;
        --no-container)
            NO_CONTAINER=true
            shift
            ;;
        --visualize)
            VISUALIZE=true
            shift
            ;;
        --visualize-only)
            VISUALIZE_ONLY=true
            shift
            ;;
        --visualization-path)
            VISUALIZATION_PATH="$2"
            shift 2
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            echo "Error: Unknown option $1"
            show_usage
            exit 1
            ;;
    esac
done

# Check required arguments
if [[ -z "$TENANT_ID" ]]; then
    echo "Error: --tenant-id is required"
    show_usage
    exit 1
fi

# Change to script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment variables if .env exists
if [[ -f ".env" ]]; then
    set -a
    source .env
    set +a
fi

# Build arguments array
SCRIPT_ARGS=(
    "run"
    "python"
    "azure_tenant_grapher.py"
    "--tenant-id" "$TENANT_ID"
    "--neo4j-uri" "$NEO4J_URI"
    "--neo4j-user" "$NEO4J_USER"
    "--neo4j-password" "$NEO4J_PASSWORD"
)

if [[ "$CONTAINER_ONLY" == true ]]; then
    SCRIPT_ARGS+=("--container-only")
fi

if [[ "$NO_CONTAINER" == true ]]; then
    SCRIPT_ARGS+=("--no-container")
fi

if [[ "$VISUALIZE" == true ]]; then
    SCRIPT_ARGS+=("--visualize")
fi

if [[ "$VISUALIZE_ONLY" == true ]]; then
    SCRIPT_ARGS+=("--visualize-only")
fi

if [[ -n "$VISUALIZATION_PATH" ]]; then
    SCRIPT_ARGS+=("--visualization-path" "$VISUALIZATION_PATH")
fi

# Check if uv is available
if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed or not in PATH"
    echo "Please install uv: https://docs.astral.sh/uv/"
    exit 1
fi

# Run the application
echo "Starting Azure Tenant Resource Grapher..."
uv "${SCRIPT_ARGS[@]}"
