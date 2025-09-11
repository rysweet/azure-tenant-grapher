# Gadugi Agentic Test Framework Migration Guide

## Overview

This document describes the migration from the previous Python-based agentic testing system to the new **Gadugi Agentic Test Framework** - a dedicated npm package for AI-powered UI testing.

## What Changed

### Before (Python-based system)
- Custom Python implementation in `agentic_testing/` directory
- Multiple agent classes for different testing scenarios
- Tight coupling with the main project codebase
- Manual orchestration and configuration

### After (Gadugi Framework)
- External npm package: `@gadugi/agentic-test`
- Standardized AI testing framework
- Reusable across multiple projects
- Simple integration via npm dependency

## Migration Steps Completed

1. **Dependency Addition**: Added `@gadugi/agentic-test` to `spa/package.json` devDependencies
   ```json
   "@gadugi/agentic-test": "github:rysweet/gadugi-agentic-test#main"
   ```

2. **Test Runner Script**: Created `spa/test-with-gadugi.js` for easy test execution
   - Configures environment variables
   - Spawns the Gadugi test runner
   - Handles process lifecycle

3. **NPM Script**: Added `test:ui` script to package.json
   ```bash
   npm run test:ui
   ```

## Benefits of Migration

### 🚀 **Improved Maintainability**
- External package reduces codebase complexity
- Framework updates happen independently
- Clear separation of testing concerns

### 🔄 **Reusability**
- Same testing framework can be used across different projects
- Standardized testing patterns and approaches
- Community-driven improvements

### 🛠 **Simplified Integration**
- Single npm install instead of complex Python setup
- Standard Node.js toolchain integration
- Consistent development workflow

### 🎯 **Enhanced Features**
- Dedicated AI testing capabilities
- Smart UI interaction detection
- Improved test reporting and analytics

## Usage

### Running UI Tests
```bash
cd spa
npm run test:ui
```

### Environment Configuration
The test runner automatically configures:
- `APP_NAME`: Set to "Azure Tenant Grapher"
- Inherits all existing environment variables
- Uses current working directory context

## Legacy Cleanup

The following Python-based files have been removed/deprecated:
- `agentic_testing/` directory and all contents
- `test_agentic_testing.py`
- Associated Python dependencies

## Future Enhancements

With Gadugi in place, future improvements can include:
- Custom test scenarios for Azure Tenant Grapher workflows
- Integration with existing Playwright e2e tests
- Automated UI regression testing in CI/CD pipeline
- Performance testing capabilities

## Support

For issues with the Gadugi framework itself, refer to:
- Repository: https://github.com/rysweet/gadugi-agentic-test
- Issues: Create issues in the Gadugi repository

For integration issues within Azure Tenant Grapher, create issues in this project.
