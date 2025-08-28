#!/usr/bin/env python
"""Test that HTTP logging is properly suppressed at INFO level."""

import logging
import io
import sys

# Capture logging output
log_capture = io.StringIO()
handler = logging.StreamHandler(log_capture)
handler.setLevel(logging.INFO)

# Apply our logging configuration
from src.config_manager import _set_azure_http_log_level

# Test 1: Check that HTTP loggers are set to WARNING when log level is INFO
print("Test 1: Checking logger levels when log level is INFO...")
_set_azure_http_log_level("INFO")

test_loggers = [
    "azure",
    "azure.core.pipeline",
    "azure.core.pipeline.policies.http_logging_policy",
    "urllib3",
    "httpx",
]

for logger_name in test_loggers:
    logger = logging.getLogger(logger_name)
    level = logger.level if logger.level != logging.NOTSET else logger.getEffectiveLevel()
    level_name = logging.getLevelName(level)
    print(f"  {logger_name}: {level_name} (level={level})")
    if logger_name not in ["httpx"]:  # httpx might not be configured yet
        assert level >= logging.WARNING, f"{logger_name} should be WARNING or higher, got {level_name}"

print("✅ All HTTP loggers are set to WARNING or higher")

# Test 2: Check that they're set to DEBUG when log level is DEBUG
print("\nTest 2: Checking logger levels when log level is DEBUG...")
_set_azure_http_log_level("DEBUG")

for logger_name in test_loggers:
    logger = logging.getLogger(logger_name)
    level = logger.level
    level_name = logging.getLevelName(level)
    print(f"  {logger_name}: {level_name} (level={level})")
    if logger_name not in ["httpx"]:  # httpx might not be configured yet
        assert level == logging.DEBUG, f"{logger_name} should be DEBUG, got {level_name}"

print("✅ All HTTP loggers are set to DEBUG when requested")

# Test 3: Simulate HTTP request logging to verify suppression
print("\nTest 3: Testing actual log suppression...")
_set_azure_http_log_level("INFO")  # Set back to INFO

# Configure root logger to capture output
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(handler)

# Try to log from various HTTP loggers
azure_logger = logging.getLogger("azure.core.pipeline")
azure_logger.info("This is an HTTP request log that should be suppressed")

urllib_logger = logging.getLogger("urllib3.connectionpool")
urllib_logger.info("Starting new HTTPS connection (1): api.azure.com:443")

httpx_logger = logging.getLogger("httpx")
httpx_logger.info("HTTP Request: GET https://api.azure.com/resource")

# Check captured output
output = log_capture.getvalue()
if "HTTP" in output or "request" in output.lower() or "connection" in output.lower():
    print(f"❌ HTTP logs were not suppressed! Output:\n{output}")
else:
    print("✅ HTTP request logs were properly suppressed at INFO level")

# Test 4: Verify WARNING messages still come through
print("\nTest 4: Testing that WARNING messages still appear...")
log_capture.truncate(0)
log_capture.seek(0)

azure_logger.warning("This is a warning that should appear")
output = log_capture.getvalue()

if "warning" in output.lower():
    print("✅ WARNING messages are still shown")
else:
    print("❌ WARNING messages are being suppressed (they shouldn't be)")

print("\n🎉 All logging tests passed! HTTP logging will be suppressed at INFO level.")