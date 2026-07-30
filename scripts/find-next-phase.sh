#!/usr/bin/env bash
# find-next-phase.sh — same logic as phase-next.sh; alias kept for clarity.
#
# Usage:
#   bash scripts/find-next-phase.sh

set -u

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SPEC="$REPO_ROOT/SPEC.md"

if [ ! -f "$SPEC" ]; then
  printf "[find-next-phase] no SPEC.md at $SPEC\n" >&2
  exit 1
fi

# Per the spec: `grep -E '^- \[ \]' SPEC.md | head -1 | awk '{print $3}'`.
NEXT="$(grep -E '^- \[ \]' "$SPEC" | head -n 1 | awk '{print $3}' || true)"
if [ -z "$NEXT" ]; then
  printf "(none)\n"
  exit 0
fi

printf "%s\n" "$NEXT"
exit 0