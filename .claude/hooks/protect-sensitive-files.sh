#!/bin/bash
# Hook: Block edits to sensitive files (.env, keys, certs)
# Runs as PreToolUse hook on Edit/Write tools
# Exit 0 = allow, Exit 2 = block

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Normalize path - extract just the filename/relative portion
BASENAME=$(basename "$FILE_PATH")
LOWERCASE=$(echo "$BASENAME" | tr '[:upper:]' '[:lower:]')

# Block patterns: exact matches and extensions
BLOCKED_EXACT=(".env" ".env.local" ".env.production" ".env.development" ".env.staging")
BLOCKED_EXTENSIONS=("key" "secret" "pem" "crt" "p12" "pfx" "keystore" "jks")

# Check exact filename matches
for pattern in "${BLOCKED_EXACT[@]}"; do
  if [[ "$LOWERCASE" == "$pattern" ]]; then
    echo "BLOCKED: Cannot edit sensitive file '$BASENAME' (matches protected pattern '$pattern')" >&2
    exit 2
  fi
done

# Check .env.* pattern (e.g. .env.anything)
if [[ "$LOWERCASE" == .env.* ]]; then
  echo "BLOCKED: Cannot edit sensitive file '$BASENAME' (matches .env.* pattern)" >&2
  exit 2
fi

# Check blocked extensions
for ext in "${BLOCKED_EXTENSIONS[@]}"; do
  if [[ "$LOWERCASE" == *."$ext" ]]; then
    echo "BLOCKED: Cannot edit sensitive file '$BASENAME' (has protected extension .$ext)" >&2
    exit 2
  fi
done

# Check if path contains sensitive directories
LOWER_PATH=$(echo "$FILE_PATH" | tr '[:upper:]' '[:lower:]' | tr '\\' '/')
if [[ "$LOWER_PATH" == *"/.ssh/"* ]] || [[ "$LOWER_PATH" == *"/.aws/"* ]] || [[ "$LOWER_PATH" == *"/.azure/"* ]]; then
  echo "BLOCKED: Cannot edit files in sensitive directory" >&2
  exit 2
fi

exit 0
