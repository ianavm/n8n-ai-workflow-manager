#!/bin/bash
# Hook: Log all Bash commands to audit file
# Runs as PostToolUse hook on Bash tool
# Logs to ~/.claude/audit-YYYY-MM-DD.log

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [ -z "$COMMAND" ]; then
  exit 0
fi

# Ensure log directory exists
LOG_DIR="$HOME/.claude"
mkdir -p "$LOG_DIR"

# Log with timestamp
LOG_FILE="$LOG_DIR/audit-$(date +%Y-%m-%d).log"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] $COMMAND" >> "$LOG_FILE"

exit 0
