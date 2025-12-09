#!/bin/bash
# Technical Debt Scanner
# Comprehensive search for stubs, TODOs, swallowed exceptions, fakes, and unimplemented code
# Usage: ./scripts/scan_technical_debt.sh [--json|--markdown|--summary]

set -euo pipefail

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TIMESTAMP=$(date -u +%Y%m%d_%H%M%S)
OUTPUT_DIR="${PROJECT_ROOT}/output"
REPORT_FILE="${OUTPUT_DIR}/technical_debt_report_${TIMESTAMP}.md"
JSON_FILE="${OUTPUT_DIR}/technical_debt_report_${TIMESTAMP}.json"
SUMMARY_FILE="${OUTPUT_DIR}/technical_debt_summary.txt"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Color codes for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
TOTAL_ISSUES=0
CRITICAL_COUNT=0
HIGH_COUNT=0
MEDIUM_COUNT=0
LOW_COUNT=0

# Arrays to store results
declare -a STUB_RESULTS=()
declare -a TODO_RESULTS=()
declare -a EXCEPTION_RESULTS=()
declare -a FAKE_RESULTS=()
declare -a UNIMPL_RESULTS=()

# Function to print section header
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

# Function to check if ripgrep is available
check_dependencies() {
    if ! command -v rg &> /dev/null; then
        echo -e "${RED}Error: ripgrep (rg) is not installed${NC}"
        echo "Install with: brew install ripgrep"
        exit 1
    fi
}

# Function to count and categorize results
process_results() {
    local category=$1
    local severity=$2
    local count=$3

    TOTAL_ISSUES=$((TOTAL_ISSUES + count))

    case $severity in
        CRITICAL)
            CRITICAL_COUNT=$((CRITICAL_COUNT + count))
            ;;
        HIGH)
            HIGH_COUNT=$((HIGH_COUNT + count))
            ;;
        MEDIUM)
            MEDIUM_COUNT=$((MEDIUM_COUNT + count))
            ;;
        LOW)
            LOW_COUNT=$((LOW_COUNT + count))
            ;;
    esac
}

# Function to scan for Python stubs
scan_python_stubs() {
    print_header "Scanning for Python Stubs"

    local count=0

    # PY-STUB-002: NotImplementedError in production
    echo -e "${YELLOW}[PY-STUB-002]${NC} Checking for NotImplementedError in production code..."
    if rg "raise\s+NotImplementedError" \
        --type py \
        --glob '!tests/**' \
        --glob '!test_*.py' \
        --glob '!*_test.py' \
        --glob '!conftest.py' \
        -n "${PROJECT_ROOT}/src" 2>/dev/null; then
        count=$((count + $(rg "raise\s+NotImplementedError" --type py --glob '!tests/**' --glob '!test_*.py' -c "${PROJECT_ROOT}/src" 2>/dev/null | awk '{s+=$1} END {print s}')))
    fi

    # PY-STUB-001: Functions with pass-only bodies
    echo -e "${YELLOW}[PY-STUB-001]${NC} Checking for pass-only function bodies..."
    if rg --multiline "def\s+\w+\([^)]*\):\s*\n\s*pass" \
        --type py \
        --glob '!tests/**' \
        -n "${PROJECT_ROOT}/src" 2>/dev/null; then
        count=$((count + $(rg --multiline "def\s+\w+\([^)]*\):\s*\n\s*pass" --type py --glob '!tests/**' -c "${PROJECT_ROOT}/src" 2>/dev/null | awk '{s+=$1} END {print s}')))
    fi

    # PY-STUB-004: Ellipsis stubs
    echo -e "${YELLOW}[PY-STUB-004]${NC} Checking for ellipsis (...) stubs..."
    if rg "^\s*\.\.\.\s*$" \
        --type py \
        --glob '!*.pyi' \
        --glob '!tests/**' \
        -n "${PROJECT_ROOT}/src" 2>/dev/null; then
        count=$((count + $(rg "^\s*\.\.\.\s*$" --type py --glob '!*.pyi' --glob '!tests/**' -c "${PROJECT_ROOT}/src" 2>/dev/null | awk '{s+=$1} END {print s}')))
    fi

    echo -e "${GREEN}Found ${count} stub issues${NC}"
    process_results "stubs" "HIGH" "$count"

    return "$count"
}

# Function to scan for TypeScript stubs
scan_typescript_stubs() {
    print_header "Scanning for TypeScript Stubs"

    local count=0

    # TS-STUB-001: Empty function bodies
    echo -e "${YELLOW}[TS-STUB-001]${NC} Checking for empty TypeScript functions..."
    if rg --multiline "function\s+\w+\([^)]*\)\s*\{\s*\}" \
        --type ts \
        --glob '!*.test.ts' \
        --glob '!*.spec.ts' \
        -n "${PROJECT_ROOT}/spa" 2>/dev/null; then
        count=$((count + $(rg --multiline "function\s+\w+\([^)]*\)\s*\{\s*\}" --type ts --glob '!*.test.ts' -c "${PROJECT_ROOT}/spa" 2>/dev/null | awk '{s+=$1} END {print s}')))
    fi

    # TS-STUB-002: Arrow functions returning undefined
    echo -e "${YELLOW}[TS-STUB-002]${NC} Checking for arrow functions returning undefined..."
    if rg "=>\s*undefined" \
        --type ts \
        --glob '!*.test.ts' \
        -n "${PROJECT_ROOT}/spa" 2>/dev/null; then
        count=$((count + $(rg "=>\s*undefined" --type ts --glob '!*.test.ts' -c "${PROJECT_ROOT}/spa" 2>/dev/null | awk '{s+=$1} END {print s}')))
    fi

    echo -e "${GREEN}Found ${count} stub issues${NC}"
    process_results "stubs" "HIGH" "$count"

    return "$count"
}

# Function to scan for TODO comments
scan_todos() {
    print_header "Scanning for TODO Comments"

    local count=0

    # TODO-002: FIXME comments (CRITICAL)
    echo -e "${RED}[TODO-002]${NC} Checking for FIXME comments..."
    if rg -i "FIXME:" \
        --type py --type ts --type js \
        -n "${PROJECT_ROOT}/src" "${PROJECT_ROOT}/spa" 2>/dev/null; then
        count=$((count + $(rg -i "FIXME:" --type py --type ts --type js -c "${PROJECT_ROOT}/src" "${PROJECT_ROOT}/spa" 2>/dev/null | awk '{s+=$1} END {print s}')))
        CRITICAL_COUNT=$((CRITICAL_COUNT + 1))
    fi

    # TODO-001: Standard TODO comments
    echo -e "${YELLOW}[TODO-001]${NC} Checking for TODO comments..."
    if rg -i "TODO:" \
        --type py --type ts --type js \
        -n "${PROJECT_ROOT}/src" "${PROJECT_ROOT}/spa" 2>/dev/null; then
        count=$((count + $(rg -i "TODO:" --type py --type ts --type js -c "${PROJECT_ROOT}/src" "${PROJECT_ROOT}/spa" 2>/dev/null | awk '{s+=$1} END {print s}')))
    fi

    # TODO-003: HACK comments
    echo -e "${YELLOW}[TODO-003]${NC} Checking for HACK comments..."
    if rg -i "HACK:" \
        --type py --type ts --type js \
        -n "${PROJECT_ROOT}/src" "${PROJECT_ROOT}/spa" 2>/dev/null; then
        count=$((count + $(rg -i "HACK:" --type py --type ts --type js -c "${PROJECT_ROOT}/src" "${PROJECT_ROOT}/spa" 2>/dev/null | awk '{s+=$1} END {print s}')))
    fi

    # TODO-004: XXX comments
    echo -e "${YELLOW}[TODO-004]${NC} Checking for XXX comments..."
    if rg -i "XXX:" \
        --type py --type ts --type js \
        -n "${PROJECT_ROOT}/src" "${PROJECT_ROOT}/spa" 2>/dev/null; then
        count=$((count + $(rg -i "XXX:" --type py --type ts --type js -c "${PROJECT_ROOT}/src" "${PROJECT_ROOT}/spa" 2>/dev/null | awk '{s+=$1} END {print s}')))
    fi

    # TODO-005: TEMPORARY comments
    echo -e "${RED}[TODO-005]${NC} Checking for TEMPORARY comments..."
    if rg -i "TEMPORARY:|TEMP:" \
        --type py --type ts --type js \
        -n "${PROJECT_ROOT}/src" "${PROJECT_ROOT}/spa" 2>/dev/null; then
        local temp_count=$(rg -i "TEMPORARY:|TEMP:" --type py --type ts --type js -c "${PROJECT_ROOT}/src" "${PROJECT_ROOT}/spa" 2>/dev/null | awk '{s+=$1} END {print s}')
        count=$((count + temp_count))
        CRITICAL_COUNT=$((CRITICAL_COUNT + temp_count))
    fi

    echo -e "${GREEN}Found ${count} TODO/comment issues${NC}"
    process_results "todos" "HIGH" "$count"

    return "$count"
}

# Function to scan for swallowed exceptions (Python)
scan_python_exceptions() {
    print_header "Scanning for Swallowed Exceptions (Python)"

    local count=0

    # PY-EXCEPT-002: Bare except clause
    echo -e "${RED}[PY-EXCEPT-002]${NC} Checking for bare except clauses..."
    if rg "^\s*except\s*:" \
        --type py \
        --glob '!tests/**' \
        --glob '!test_*.py' \
        -n "${PROJECT_ROOT}/src" 2>/dev/null; then
        local bare_count=$(rg "^\s*except\s*:" --type py --glob '!tests/**' -c "${PROJECT_ROOT}/src" 2>/dev/null | awk '{s+=$1} END {print s}')
        count=$((count + bare_count))
        CRITICAL_COUNT=$((CRITICAL_COUNT + bare_count))
    fi

    # PY-EXCEPT-001: Except with pass
    echo -e "${RED}[PY-EXCEPT-001]${NC} Checking for exceptions with pass..."
    if rg --multiline "except[^:]*:\s*\n\s*pass" \
        --type py \
        --glob '!tests/**' \
        -n "${PROJECT_ROOT}/src" 2>/dev/null; then
        local pass_count=$(rg --multiline "except[^:]*:\s*\n\s*pass" --type py --glob '!tests/**' -c "${PROJECT_ROOT}/src" 2>/dev/null | awk '{s+=$1} END {print s}')
        count=$((count + pass_count))
        CRITICAL_COUNT=$((CRITICAL_COUNT + pass_count))
    fi

    # PY-EXCEPT-004: Exception with TODO
    echo -e "${RED}[PY-EXCEPT-004]${NC} Checking for exceptions with TODO comments..."
    if rg --multiline "except[^:]*:\s*\n\s*#.*TODO" \
        --type py \
        -n "${PROJECT_ROOT}/src" 2>/dev/null; then
        local todo_except_count=$(rg --multiline "except[^:]*:\s*\n\s*#.*TODO" --type py -c "${PROJECT_ROOT}/src" 2>/dev/null | awk '{s+=$1} END {print s}')
        count=$((count + todo_except_count))
        CRITICAL_COUNT=$((CRITICAL_COUNT + todo_except_count))
    fi

    echo -e "${GREEN}Found ${count} exception handling issues${NC}"
    process_results "exceptions" "CRITICAL" "$count"

    return "$count"
}

# Function to scan for swallowed exceptions (TypeScript)
scan_typescript_exceptions() {
    print_header "Scanning for Swallowed Exceptions (TypeScript)"

    local count=0

    # TS-EXCEPT-001: Empty catch blocks
    echo -e "${RED}[TS-EXCEPT-001]${NC} Checking for empty catch blocks..."
    if rg --multiline "catch\s*\([^)]*\)\s*\{\s*\}" \
        --type ts \
        --glob '!*.test.ts' \
        --glob '!*.spec.ts' \
        -n "${PROJECT_ROOT}/spa" 2>/dev/null; then
        local empty_catch=$(rg --multiline "catch\s*\([^)]*\)\s*\{\s*\}" --type ts --glob '!*.test.ts' -c "${PROJECT_ROOT}/spa" 2>/dev/null | awk '{s+=$1} END {print s}')
        count=$((count + empty_catch))
        CRITICAL_COUNT=$((CRITICAL_COUNT + empty_catch))
    fi

    # TS-EXCEPT-003: Catch with TODO
    echo -e "${RED}[TS-EXCEPT-003]${NC} Checking for catch blocks with TODO..."
    if rg --multiline "catch\s*\([^)]*\)\s*\{[^}]*TODO" \
        --type ts \
        -n "${PROJECT_ROOT}/spa" 2>/dev/null; then
        local todo_catch=$(rg --multiline "catch\s*\([^)]*\)\s*\{[^}]*TODO" --type ts -c "${PROJECT_ROOT}/spa" 2>/dev/null | awk '{s+=$1} END {print s}')
        count=$((count + todo_catch))
        CRITICAL_COUNT=$((CRITICAL_COUNT + todo_catch))
    fi

    echo -e "${GREEN}Found ${count} exception handling issues${NC}"
    process_results "exceptions" "CRITICAL" "$count"

    return "$count"
}

# Function to scan for fake/mock APIs
scan_fakes() {
    print_header "Scanning for Fake/Mock APIs in Production"

    local count=0

    # PY-FAKE-001: Mock decorators outside tests
    echo -e "${RED}[PY-FAKE-001]${NC} Checking for mock decorators in production..."
    if rg "@(mock\.|patch)" \
        --type py \
        --glob '!tests/**' \
        --glob '!test_*.py' \
        --glob '!conftest.py' \
        -n "${PROJECT_ROOT}/src" 2>/dev/null; then
        local mock_dec=$(rg "@(mock\.|patch)" --type py --glob '!tests/**' --glob '!test_*.py' -c "${PROJECT_ROOT}/src" 2>/dev/null | awk '{s+=$1} END {print s}')
        count=$((count + mock_dec))
        CRITICAL_COUNT=$((CRITICAL_COUNT + mock_dec))
    fi

    # PY-FAKE-002: Hardcoded test/mock data
    echo -e "${YELLOW}[PY-FAKE-002]${NC} Checking for MOCK_/FAKE_/DUMMY_ constants..."
    if rg "(MOCK_|FAKE_|DUMMY_|TEST_DATA)" \
        --type py \
        --glob '!tests/**' \
        --glob '!test_*.py' \
        --glob '!examples/**' \
        -n "${PROJECT_ROOT}/src" 2>/dev/null; then
        count=$((count + $(rg "(MOCK_|FAKE_|DUMMY_|TEST_DATA)" --type py --glob '!tests/**' --glob '!examples/**' -c "${PROJECT_ROOT}/src" 2>/dev/null | awk '{s+=$1} END {print s}')))
    fi

    # PY-FAKE-003: Functions with fake/mock/stub names
    echo -e "${YELLOW}[PY-FAKE-003]${NC} Checking for fake/mock/stub function names..."
    if rg "def\s+(fake|mock|stub)_\w+" \
        --type py \
        --glob '!tests/**' \
        --glob '!test_*.py' \
        -n "${PROJECT_ROOT}/src" 2>/dev/null; then
        count=$((count + $(rg "def\s+(fake|mock|stub)_\w+" --type py --glob '!tests/**' -c "${PROJECT_ROOT}/src" 2>/dev/null | awk '{s+=$1} END {print s}')))
    fi

    # TS-FAKE-001: Mock/fake function names in TypeScript
    echo -e "${YELLOW}[TS-FAKE-001]${NC} Checking for mock/fake in TypeScript production..."
    if rg "(function|const|let)\s+(mock|fake)\w+" \
        --type ts \
        --glob '!*.test.ts' \
        --glob '!*.spec.ts' \
        -n "${PROJECT_ROOT}/spa/main" "${PROJECT_ROOT}/spa/backend" "${PROJECT_ROOT}/spa/renderer" 2>/dev/null; then
        count=$((count + $(rg "(function|const|let)\s+(mock|fake)\w+" --type ts --glob '!*.test.ts' -c "${PROJECT_ROOT}/spa/main" "${PROJECT_ROOT}/spa/backend" "${PROJECT_ROOT}/spa/renderer" 2>/dev/null | awk '{s+=$1} END {print s}')))
    fi

    echo -e "${GREEN}Found ${count} fake/mock issues${NC}"
    process_results "fakes" "HIGH" "$count"

    return "$count"
}

# Function to generate summary
generate_summary() {
    print_header "Technical Debt Summary"

    cat > "$SUMMARY_FILE" << EOF
Technical Debt Scan Summary
Generated: $(date -u +%Y-%m-%d" "%H:%M:%S" UTC")
Project: Azure Tenant Grapher
Commit: $(git rev-parse HEAD 2>/dev/null || echo "N/A")
Branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "N/A")

========================================
OVERALL SUMMARY
========================================
Total Issues Found: ${TOTAL_ISSUES}

By Severity:
  CRITICAL: ${CRITICAL_COUNT}
  HIGH:     ${HIGH_COUNT}
  MEDIUM:   ${MEDIUM_COUNT}
  LOW:      ${LOW_COUNT}

========================================
SEVERITY BREAKDOWN
========================================

CRITICAL Issues (${CRITICAL_COUNT}):
  - Bare except clauses
  - Exceptions with pass (no logging)
  - Empty catch blocks
  - FIXME comments
  - TEMPORARY comments
  - Mock decorators in production

HIGH Issues (${HIGH_COUNT}):
  - NotImplementedError in production
  - TODO comments
  - HACK comments
  - Fake/mock function names
  - Swallowed exceptions

MEDIUM Issues (${MEDIUM_COUNT}):
  - Empty function implementations
  - Placeholder return values

========================================
NEXT STEPS
========================================

1. Review all CRITICAL issues immediately
2. Create GitHub issues for all HIGH priority items
3. Schedule remediation in current sprint
4. Set up pre-commit hooks to prevent new debt
5. Add CI/CD checks to fail builds with critical issues

========================================
DETAILED REPORTS
========================================

Markdown Report: ${REPORT_FILE}
JSON Report:     ${JSON_FILE}

For detailed findings with file locations and code snippets,
review the markdown or JSON reports above.

EOF

    cat "$SUMMARY_FILE"

    if [ "$TOTAL_ISSUES" -gt 0 ]; then
        echo -e "\n${RED}========================================${NC}"
        echo -e "${RED}WARNING: ${TOTAL_ISSUES} technical debt issues found!${NC}"
        echo -e "${RED}========================================${NC}"

        if [ "$CRITICAL_COUNT" -gt 0 ]; then
            echo -e "${RED}CRITICAL: ${CRITICAL_COUNT} issues require immediate attention!${NC}"
            exit 1
        fi
    else
        echo -e "\n${GREEN}========================================${NC}"
        echo -e "${GREEN}SUCCESS: No technical debt found!${NC}"
        echo -e "${GREEN}========================================${NC}"
    fi
}

# Function to generate markdown report
generate_markdown_report() {
    cat > "$REPORT_FILE" << EOF
# Technical Debt Report

**Generated**: $(date -u +%Y-%m-%d" "%H:%M:%S" UTC")
**Project**: Azure Tenant Grapher
**Commit**: $(git rev-parse HEAD 2>/dev/null || echo "N/A")
**Branch**: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "N/A")

---

## Executive Summary

| Metric | Count |
|--------|-------|
| **Total Issues** | ${TOTAL_ISSUES} |
| **Critical** | ${CRITICAL_COUNT} |
| **High** | ${HIGH_COUNT} |
| **Medium** | ${MEDIUM_COUNT} |
| **Low** | ${LOW_COUNT} |

---

## Findings by Category

### 1. Stub Implementations

Run the following command to see details:
\`\`\`bash
# Python stubs
rg "raise\s+NotImplementedError" --type py --glob '!tests/**' -n src/

# TypeScript empty functions
rg --multiline "function\s+\w+\([^)]*\)\s*\{\s*\}" --type ts --glob '!*.test.ts' -n spa/
\`\`\`

### 2. TODO Comments

Run the following command to see details:
\`\`\`bash
rg -i "TODO:|FIXME:|HACK:|XXX:|TEMPORARY:" --type py --type ts --type js -n src/ spa/
\`\`\`

### 3. Swallowed Exceptions

Run the following command to see details:
\`\`\`bash
# Python
rg "^\s*except\s*:" --type py --glob '!tests/**' -n src/
rg --multiline "except[^:]*:\s*\n\s*pass" --type py --glob '!tests/**' -n src/

# TypeScript
rg --multiline "catch\s*\([^)]*\)\s*\{\s*\}" --type ts --glob '!*.test.ts' -n spa/
\`\`\`

### 4. Fake/Mock APIs in Production

Run the following command to see details:
\`\`\`bash
# Python
rg "(MOCK_|FAKE_|DUMMY_|def\s+(mock|fake|stub)_)" --type py --glob '!tests/**' -n src/

# TypeScript
rg "(function|const|let)\s+(mock|fake)\w+" --type ts --glob '!*.test.ts' -n spa/
\`\`\`

---

## Remediation Priority

### Priority 1: CRITICAL (Fix Immediately)

1. **Bare except clauses** - Specify exception types
2. **Empty catch blocks** - Add proper error handling and logging
3. **FIXME comments** - These indicate broken code
4. **Mock decorators in production** - Remove all mocking from production code

### Priority 2: HIGH (Fix This Sprint)

1. **NotImplementedError** - Implement missing functionality
2. **TODO comments** - Convert to GitHub issues or implement
3. **HACK comments** - Replace with proper implementations
4. **Fake/mock data** - Replace with real implementations

### Priority 3: MEDIUM (Schedule Next Sprint)

1. **Empty function implementations** - Implement or document why empty
2. **Placeholder return values** - Return proper values or raise appropriate errors

---

## Action Items

- [ ] Assign CRITICAL issues to developers
- [ ] Create GitHub issues for all HIGH priority findings
- [ ] Schedule remediation in sprint planning
- [ ] Set up pre-commit hooks to prevent new technical debt
- [ ] Add CI/CD checks to fail builds with critical issues
- [ ] Review and update technical debt metrics weekly

---

## Detailed Scan Commands

For complete details, run:

\`\`\`bash
# Full scan
./scripts/scan_technical_debt.sh

# View specific category
rg "raise\s+NotImplementedError" --type py --glob '!tests/**' -n src/
\`\`\`

---

**Report Location**: ${REPORT_FILE}
**Summary**: ${SUMMARY_FILE}

EOF

    echo -e "${GREEN}Markdown report generated: ${REPORT_FILE}${NC}"
}

# Main execution
main() {
    check_dependencies

    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║         Technical Debt Scanner                            ║${NC}"
    echo -e "${BLUE}║         Azure Tenant Grapher                               ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"

    # Run all scans
    scan_python_stubs
    scan_typescript_stubs
    scan_todos
    scan_python_exceptions
    scan_typescript_exceptions
    scan_fakes

    # Generate reports
    generate_summary
    generate_markdown_report

    echo -e "\n${BLUE}Reports generated:${NC}"
    echo -e "  Summary:  ${SUMMARY_FILE}"
    echo -e "  Markdown: ${REPORT_FILE}"
}

# Run main function
main "$@"
