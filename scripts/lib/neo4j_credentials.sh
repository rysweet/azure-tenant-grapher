#!/bin/bash
#
# Neo4j Credentials Validation Library
#
# This script provides functions for validating Neo4j credentials from environment variables.
# Source this file in your bash scripts to use the validation function.
#
# Usage:
#   source "$(dirname "$0")/lib/neo4j_credentials.sh"
#   validate_neo4j_credentials
#

validate_neo4j_credentials() {
    local missing_vars=()

    # Check for required environment variables
    if [ -z "${NEO4J_PASSWORD:-}" ]; then
        missing_vars+=("NEO4J_PASSWORD")
    fi

    # Either NEO4J_URI or NEO4J_PORT must be set
    if [ -z "${NEO4J_URI:-}" ] && [ -z "${NEO4J_PORT:-}" ]; then
        missing_vars+=("NEO4J_URI or NEO4J_PORT")
    fi

    # Report missing variables if any
    if [ ${#missing_vars[@]} -gt 0 ]; then
        echo "ERROR: Missing required Neo4j credentials in environment:" >&2
        for var in "${missing_vars[@]}"; do
            echo "  - $var" >&2
        done
        echo "" >&2
        echo "Please set these variables in your .env file or environment." >&2
        echo "See .env.example for configuration details." >&2
        echo "" >&2
        echo "Example:" >&2
        echo "  export NEO4J_PASSWORD=your-secure-password" >&2
        echo "  export NEO4J_PORT=7687" >&2
        return 1
    fi

    # Validate NEO4J_PORT if provided
    if [ -n "${NEO4J_PORT:-}" ]; then
        if ! [[ "${NEO4J_PORT}" =~ ^[0-9]+$ ]]; then
            echo "ERROR: NEO4J_PORT must be a numeric value, got: ${NEO4J_PORT}" >&2
            return 1
        fi

        if [ "${NEO4J_PORT}" -lt 1 ] || [ "${NEO4J_PORT}" -gt 65535 ]; then
            echo "ERROR: NEO4J_PORT must be between 1 and 65535, got: ${NEO4J_PORT}" >&2
            return 1
        fi
    fi

    # Construct NEO4J_URI if not provided
    if [ -z "${NEO4J_URI:-}" ]; then
        export NEO4J_URI="bolt://localhost:${NEO4J_PORT}"
    fi

    # Set default username if not provided
    if [ -z "${NEO4J_USERNAME:-}" ]; then
        export NEO4J_USERNAME="neo4j"
    fi

    # All validation passed
    return 0
}

# Function to get Neo4j connection string for cypher-shell
get_neo4j_connection_string() {
    if [ -z "${NEO4J_URI:-}" ]; then
        echo "bolt://localhost:${NEO4J_PORT}"
    else
        echo "${NEO4J_URI}"
    fi
}

# Function to get Neo4j username
get_neo4j_username() {
    echo "${NEO4J_USERNAME:-neo4j}"
}

# Function to get Neo4j password
get_neo4j_password() {
    echo "${NEO4J_PASSWORD}"
}
