#!/bin/bash
# Test script to verify CLI flags for cross-tenant translation

set -e

echo "🧪 Testing CLI Flags for Cross-Tenant Translation"
echo "=================================================="
echo ""

echo "1️⃣ Checking CLI flag help text..."
if uv run atg generate-iac --help 2>&1 | grep -q "source-tenant-id"; then
    echo "   ✅ --source-tenant-id flag present"
else
    echo "   ❌ --source-tenant-id flag missing"
    exit 1
fi

if uv run atg generate-iac --help 2>&1 | grep -q "target-tenant-id"; then
    echo "   ✅ --target-tenant-id flag present"
else
    echo "   ❌ --target-tenant-id flag missing"
    exit 1
fi

if uv run atg generate-iac --help 2>&1 | grep -q "identity-mapping-file"; then
    echo "   ✅ --identity-mapping-file flag present"
else
    echo "   ❌ --identity-mapping-file flag missing"
    exit 1
fi

if uv run atg generate-iac --help 2>&1 | grep -q "strict-translation"; then
    echo "   ✅ --strict-translation flag present"
else
    echo "   ❌ --strict-translation flag missing"
    exit 1
fi

echo ""
echo "2️⃣ Checking Python syntax..."
if uv run python -m py_compile src/iac/cli_handler.py 2>&1 | grep -q "warning" && ! uv run python -m py_compile src/iac/cli_handler.py 2>&1 | grep -q "Error"; then
    echo "   ✅ src/iac/cli_handler.py syntax OK"
else
    echo "   ❌ src/iac/cli_handler.py syntax error"
    exit 1
fi

if uv run python -m py_compile scripts/cli.py 2>&1 | grep -q "warning" && ! uv run python -m py_compile scripts/cli.py 2>&1 | grep -q "Error"; then
    echo "   ✅ scripts/cli.py syntax OK"
else
    echo "   ❌ scripts/cli.py syntax error"
    exit 1
fi

echo ""
echo "3️⃣ Displaying full help text for cross-tenant flags..."
echo "------------------------------------------------------"
uv run atg generate-iac --help 2>&1 | grep -A 20 "Cross-Tenant Translation" | head -15

echo ""
echo "✅ All CLI flag tests passed!"
echo ""
echo "📝 Next steps:"
echo "   1. Review CLI_FLAGS_SUMMARY.md for implementation details"
echo "   2. Test with actual cross-tenant scenario"
echo "   3. Create identity mapping JSON file"
echo "   4. Run: uv run atg generate-iac --target-tenant-id <ID> --identity-mapping-file mappings.json"
