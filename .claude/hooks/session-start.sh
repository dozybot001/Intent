#!/bin/bash
# Run itt inspect at session start, inject workspace state into context
ITT="$(cd "$(dirname "$0")/../.." && pwd)/itt"
if [ -f "$ITT" ]; then
    OUTPUT=$(python3 "$ITT" inspect 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo "[Intent workspace state]"
        echo "$OUTPUT"
    fi
fi
exit 0
