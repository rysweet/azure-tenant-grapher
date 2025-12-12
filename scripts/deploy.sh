#!/bin/bash
# Manual deployment script for ATG Remote Service
# Usage: ./scripts/deploy.sh [dev|integration] [tag]

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REGISTRY="ghcr.io"
REPO_OWNER="${GITHUB_REPOSITORY_OWNER:-your-org}"
IMAGE_NAME="${REPO_OWNER}/atg-service"

# Parse arguments
ENVIRONMENT="${1:-}"
TAG="${2:-$(git describe --tags --abbrev=0 2>/dev/null || echo 'latest')}"

# Validate environment
if [[ -z "$ENVIRONMENT" ]]; then
    echo -e "${RED}❌ Error: Environment not specified${NC}"
    echo "Usage: $0 [dev|integration] [tag]"
    echo "Example: $0 dev v1.0.0-dev"
    exit 1
fi

if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "integration" ]]; then
    echo -e "${RED}❌ Error: Invalid environment. Use 'dev' or 'integration'${NC}"
    exit 1
fi

# Validate tag format
if [[ "$ENVIRONMENT" == "dev" && ! "$TAG" =~ -dev$ ]]; then
    echo -e "${YELLOW}⚠️  Warning: Tag '$TAG' doesn't end with '-dev' for dev environment${NC}"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

if [[ "$ENVIRONMENT" == "integration" && ! "$TAG" =~ -int$ ]]; then
    echo -e "${YELLOW}⚠️  Warning: Tag '$TAG' doesn't end with '-int' for integration environment${NC}"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🚀 ATG Remote Service Deployment${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "Environment: ${GREEN}${ENVIRONMENT}${NC}"
echo -e "Tag: ${GREEN}${TAG}${NC}"
echo -e "Image: ${BLUE}${REGISTRY}/${IMAGE_NAME}:${TAG}${NC}"
echo ""

# Check prerequisites
echo -e "${BLUE}🔍 Checking prerequisites...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker.${NC}"
    exit 1
fi

if ! command -v az &> /dev/null; then
    echo -e "${RED}❌ Azure CLI not found. Please install Azure CLI.${NC}"
    exit 1
fi

# Check Azure login
if ! az account show &> /dev/null; then
    echo -e "${RED}❌ Not logged in to Azure. Run 'az login' first.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites met${NC}"
echo ""

# Build Docker image
echo -e "${BLUE}🏗️  Building Docker image...${NC}"
docker build -t "${IMAGE_NAME}:${TAG}" -f docker/Dockerfile .

# Tag for registry
echo -e "${BLUE}🏷️  Tagging image for registry...${NC}"
docker tag "${IMAGE_NAME}:${TAG}" "${REGISTRY}/${IMAGE_NAME}:${TAG}"

# Push to registry
echo -e "${BLUE}📤 Pushing to container registry...${NC}"
echo "This requires authentication. Make sure you're logged in to ${REGISTRY}"
echo "Run: echo \$GITHUB_TOKEN | docker login ${REGISTRY} -u \$GITHUB_USER --password-stdin"
read -p "Press Enter to continue or Ctrl+C to abort..."

if ! docker push "${REGISTRY}/${IMAGE_NAME}:${TAG}"; then
    echo -e "${RED}❌ Failed to push image. Check your registry authentication.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Image pushed successfully${NC}"
echo ""

# Deploy with Azure CLI
echo -e "${BLUE}☁️  Deploying to Azure Container Instances...${NC}"

RESOURCE_GROUP="atg-${ENVIRONMENT}"

# Check if resource group exists
if ! az group show --name "$RESOURCE_GROUP" &> /dev/null; then
    echo -e "${YELLOW}⚠️  Resource group '$RESOURCE_GROUP' not found.${NC}"
    read -p "Create it? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        LOCATION="${AZURE_LOCATION:-eastus}"
        az group create --name "$RESOURCE_GROUP" --location "$LOCATION"
    else
        exit 1
    fi
fi

# Load secrets from environment or prompt
echo -e "${BLUE}🔐 Loading deployment secrets...${NC}"

# Check for required environment variables
REQUIRED_VARS=(
    "NEO4J_URI"
    "NEO4J_PASSWORD"
    "API_KEY"
    "TARGET_TENANT_ID"
)

for var in "${REQUIRED_VARS[@]}"; do
    if [[ -z "${!var:-}" ]]; then
        echo -e "${RED}❌ Required environment variable $var is not set${NC}"
        echo "Set it with: export $var='your-value'"
        exit 1
    fi
done

# Deploy
az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file infrastructure/aci.bicep \
  --parameters \
    environment="$ENVIRONMENT" \
    containerImage="${REGISTRY}/${IMAGE_NAME}:${TAG}" \
    neo4jUri="$NEO4J_URI" \
    neo4jPassword="$NEO4J_PASSWORD" \
    apiKey="$API_KEY" \
    targetTenantId="$TARGET_TENANT_ID"

echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""

# Verify deployment
echo -e "${BLUE}🔍 Verifying deployment...${NC}"
sleep 10

FQDN=$(az container show \
    --resource-group "$RESOURCE_GROUP" \
    --name "atg-${ENVIRONMENT}" \
    --query ipAddress.fqdn -o tsv)

if [[ -z "$FQDN" ]]; then
    echo -e "${RED}❌ Failed to get container FQDN${NC}"
    exit 1
fi

echo -e "${BLUE}🏥 Checking health endpoint...${NC}"

# Retry health check
for i in {1..5}; do
    if curl -f "http://${FQDN}:8000/api/v1/health"; then
        echo ""
        echo -e "${GREEN}✅ Service is healthy!${NC}"
        break
    fi
    if [[ $i -eq 5 ]]; then
        echo ""
        echo -e "${RED}❌ Health check failed after 5 attempts${NC}"
        exit 1
    fi
    echo -e "${YELLOW}⏳ Attempt $i/5 failed, retrying in 10s...${NC}"
    sleep 10
done

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🎉 Deployment Successful!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "Environment: ${BLUE}${ENVIRONMENT}${NC}"
echo -e "Tag: ${BLUE}${TAG}${NC}"
echo -e "Service URL: ${BLUE}http://${FQDN}:8000${NC}"
echo -e "Health Check: ${BLUE}http://${FQDN}:8000/api/v1/health${NC}"
echo -e "API Docs: ${BLUE}http://${FQDN}:8000/docs${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
