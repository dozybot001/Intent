#!/bin/bash
# After git commit, remind agent to record a checkpoint with itt snap
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null)

if echo "$COMMAND" | grep -qE '^git commit'; then
    echo "[Intent reminder] You just committed code. Consider running 'itt snap \"<what you did>\" -m \"<why>\"' to record this step in semantic history. Skip if trivial."
fi
exit 0
