#!/usr/bin/env python3
"""
Enhanced CLI wrapper for Azure Tenant Grapher

This script provides an improved command-line interface with better error handling,
configuration validation, and progress tracking.
"""

import logging
import os


def print_cli_env_block(context: str = ""):
    print(f"[CLI ENV DUMP]{'[' + context + ']' if context else ''}")
    for k in [
        "NEO4J_CONTAINER_NAME",
        "NEO4J_DATA_VOLUME",
        "NEO4J_PASSWORD",
        "NEO4J_PORT",
        "NEO4J_URI",
    ]:
        print(f"[CLI ENV] {k}={os.environ.get(k)}")


print_cli_env_block("STARTUP")

# Set Azure logging levels early
for name in [
    "azure",
    "azure.core",
    "azure.core.pipeline",
    "azure.core.pipeline.policies",
    "azure.core.pipeline.policies.http_logging_policy",
    "azure.core.pipeline.policies.HttpLoggingPolicy",
    "msrest",
    "urllib3",
    "http.client",
]:
    logging.getLogger(name).setLevel(logging.WARNING)

# (rest of file unchanged)
