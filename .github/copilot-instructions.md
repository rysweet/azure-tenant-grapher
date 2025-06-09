# Copilot Instructions

<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

This is a Python project that walks Azure tenant resources and builds a Neo4j graph database of those resources.

## Project Context
- This project uses Azure SDK for Python to interact with Azure resources
- It uses py2neo or neo4j-python-driver to interact with Neo4j
- The main goal is to exhaustively discover and map Azure resources and their relationships
- Focus on proper error handling and rate limiting when making Azure API calls
- Use async/await patterns where possible for better performance

## Key Components
- Azure authentication and resource discovery
- Neo4j graph database operations
- Resource relationship mapping
- Configuration management
