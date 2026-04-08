#!/bin/bash
# PostToolUse hook: auto-format Python files after Write/Edit
# Reads JSON from stdin, extracts file_path, runs ruff format + fix

FILE=$(cat | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null)

case "$FILE" in
  *.py)
    RUFF="/Users/sri/Documents/ss-factory/s_control/.venv/bin/ruff"
    if [ -x "$RUFF" ]; then
      "$RUFF" format "$FILE" 2>/dev/null
      "$RUFF" check --fix "$FILE" 2>/dev/null
    fi
    ;;
esac
exit 0
