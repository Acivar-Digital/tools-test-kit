#!/bin/bash
# ==============================================================================
# Tier 7 - Mutation Testing Runner (Mutmut)
# Target: src2/engine/
# ==============================================================================

echo "🚀 Starting Mutation Testing via Mutmut..."
echo "This will deliberately inject bugs into the engine to see if tests fail."
echo "Note: This may take a few minutes depending on CPU."
echo "----------------------------------------------------------------------"

# Run the mutations
uv run mutmut run

echo ""
echo "📊 Mutation testing complete! Summary of results:"
# Show summary in terminal
uv run mutmut results

echo ""
echo "🌐 Generating interactive HTML report..."
uv run mutmut browse

echo ""
echo "✅ Done! You can view the full report with: uv run mutmut browse"
echo ""
echo "🛠️  DEBUGGING COMMANDS:"
echo " - To inspect a surviving mutant: uv run mutmut show <ID>"
echo " - To apply a mutant to your code: uv run mutmut apply <ID>"
