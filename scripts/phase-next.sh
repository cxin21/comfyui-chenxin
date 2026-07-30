#!/usr/bin/env bash
# phase-next.sh — print the next unchecked phase from SPEC.md.
#
# Usage:
#   bash scripts/phase-next.sh
#
# Output:
#   P0.3     (just the phase id; the next unchecked phase)

set -u

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SPEC="$REPO_ROOT/SPEC.md"

if [ ! -f "$SPEC" ]; then
  printf "[phase-next] no SPEC.md at $SPEC\n" >&2
  exit 1
fi

NEXT="$(grep -E '^- \[ \]' "$SPEC" | head -n 1 | awk '{print $3}' || true)"
if [ -z "$NEXT" ]; then
  printf "(none — all phases checked off)\n"
  exit 0
fi

printf "%s\n" "$NEXT"
exit 0