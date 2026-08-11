"""Lint an already-authored Prompt Forge request; never rewrite it."""
from __future__ import annotations

import argparse
import json
import sys

from prompt_forge.contracts import ForgeRequest
from prompt_forge.forge import forge_prompt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=argparse.FileType("r", encoding="utf-8"), default=sys.stdin)
    args = parser.parse_args()
    data = json.load(args.request)
    artifact = forge_prompt(ForgeRequest(**data))
    print(json.dumps(artifact.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
