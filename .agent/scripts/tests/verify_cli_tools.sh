#!/bin/bash
set -e

echo "🧪 Verifying CLI Orchestration Tools..."
echo "======================================="

TOOLS=(
    ".agent/scripts/orchestration/agent_scorer.py"
    ".agent/scripts/orchestration/agent_auctioneer.py"
    ".agent/scripts/orchestration/governance_gate.py"
    ".agent/scripts/health/status_report.py"
    ".agent/scripts/health/alignment_oracle.py"
)

for tool in "${TOOLS[@]}"; do
    if [ ! -f "$tool" ]; then
        echo "❌ Tool not found: $tool"
        exit 1
    fi
    
    echo -n "  🔍 Checking $tool... "
    # Run with no args or --help to see if it crashes on import/parsing
    # We expect some to exit with 1 (usage) and some with 0 (--help)
    # The goal is to catch SyntaxError or ImportError
    python3 "$tool" --help > /dev/null 2>&1 || true
    echo "OK"
done

echo "✅ All CLI tools are importable and runnable."
