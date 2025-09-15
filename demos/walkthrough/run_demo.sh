#!/bin/bash

# Azure Tenant Grapher Demo Runner Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
STORY="quick_demo"
HEADLESS=false
DEBUG=false

# Function to display usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -s, --story STORY      Story to run (quick_demo, full_walkthrough, security_focus)"
    echo "  -c, --scenario NAME    Run individual scenario"
    echo "  -h, --headless         Run in headless mode"
    echo "  -d, --debug            Enable debug logging"
    echo "  -g, --gallery          Generate gallery only"
    echo "  --help                 Display this help message"
    echo ""
    echo "Examples:"
    echo "  $0                     # Run quick demo"
    echo "  $0 -s full_walkthrough # Run full walkthrough"
    echo "  $0 -c 03_scan          # Run scan scenario only"
    echo "  $0 -g                  # Generate screenshot gallery"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -s|--story)
            STORY="$2"
            shift 2
            ;;
        -c|--scenario)
            SCENARIO="$2"
            shift 2
            ;;
        -h|--headless)
            HEADLESS=true
            shift
            ;;
        -d|--debug)
            DEBUG=true
            shift
            ;;
        -g|--gallery)
            GALLERY_ONLY=true
            shift
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            exit 1
            ;;
    esac
done

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is required but not installed.${NC}"
    exit 1
fi

# Check if Playwright is installed
if ! python3 -c "import playwright" &> /dev/null; then
    echo -e "${YELLOW}Installing Playwright...${NC}"
    pip install playwright
    playwright install chromium
fi

# Check if application is running
if ! curl -s http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${YELLOW}Warning: Application not running on http://localhost:3000${NC}"
    echo "Please start the application first with: npm run dev"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Build command
CMD="python3 orchestrator.py"

if [ "$GALLERY_ONLY" = true ]; then
    CMD="$CMD --gallery"
elif [ ! -z "$SCENARIO" ]; then
    CMD="$CMD --scenario $SCENARIO"
else
    CMD="$CMD --story $STORY"
fi

if [ "$HEADLESS" = true ]; then
    CMD="$CMD --headless"
fi

if [ "$DEBUG" = true ]; then
    CMD="$CMD --debug"
fi

# Create necessary directories
mkdir -p screenshots logs reports

# Run the demo
echo -e "${GREEN}Starting Azure Tenant Grapher Demo...${NC}"
echo "Command: $CMD"
echo ""

# Execute the command
$CMD

# Check exit status
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Demo completed successfully!${NC}"

    # Open gallery if generated
    if [ -f "screenshots/gallery.html" ]; then
        echo -e "${GREEN}Opening screenshot gallery...${NC}"
        if command -v open &> /dev/null; then
            open screenshots/gallery.html
        elif command -v xdg-open &> /dev/null; then
            xdg-open screenshots/gallery.html
        else
            echo "Gallery available at: screenshots/gallery.html"
        fi
    fi
else
    echo -e "${RED}Demo failed with errors.${NC}"
    exit 1
fi