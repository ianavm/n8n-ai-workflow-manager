#!/bin/bash
# Hook: Remind to review before git push
# Type: PreToolUse (Bash) - advisory, non-blocking

INPUT=$(cat)
if command -v jq >/dev/null 2>&1; then
  COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
else
  COMMAND=$(echo "$INPUT" | node -e "let d='';process.stdin.on('data',c=>d+=c).on('end',()=>{try{const j=JSON.parse(d);const v=j.tool_input&&j.tool_input.command;process.stdout.write(v==null?'':String(v))}catch(e){}})" 2>/dev/null)
fi

if echo "$COMMAND" | grep -q "git push"; then
  echo "REMINDER: Review 'git status' and 'git log --oneline -5' before pushing." >&2
fi

exit 0
