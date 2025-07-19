#!/bin/bash
# Run the full test suite and capture all output artifacts for local review.
# Usage: ./scripts/run_tests_with_artifacts.sh

set -e

echo "Running tests with full output and artifact capture..."
echo "Command: uv run pytest --junitxml=pytest-results.xml --html=pytest-report.html 2>&1 | tee pytest-output.log"
echo

uv run pytest --junitxml=pytest-results.xml --html=pytest-report.html 2>&1 | tee pytest-output.log

echo
echo "Test run complete."
echo "Artifacts generated:"
echo "  - pytest-output.log (raw output)"
echo "  - pytest-results.xml (JUnit XML)"
echo "  - pytest-report.html (HTML report)"
echo
echo "All files are .gitignored and safe to review locally."