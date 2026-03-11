#!/bin/bash
# Hook: Remind to review before git push
# Type: PreToolUse (Bash) - advisory, non-blocking

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

if echo "$COMMAND" | grep -q "git push"; then
  echo "REMINDER: Review 'git status' and 'git log --oneline -5' before pushing." >&2
fi

exit 0
