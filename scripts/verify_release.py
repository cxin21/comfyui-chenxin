"""Verify the source tree contains the complete independent skill layout."""
from __future__ import annotations

import argparse
from pathlib import Path


REQUIRED = (
    "skills/anima-prompt-v1/SKILL.md",
    "skills/anima-prompt-v1/agents/openai.yaml",
    "skills/anima-prompt-v1/pyproject.toml",
    "skills/anima-prompt-v1/anima_prompt_v1/__init__.py",
    "skills/anima-prompt-v1/knowledge/manifest.json",
    "skills/anima-prompt-v1/knowledge/tags.sqlite",
    "skills/anima-prompt-v1/knowledge/tag-catalog.sqlite",
    "skills/minimax-h3-prompt/SKILL.md",
    "skills/minimax-h3-prompt/pyproject.toml",
    "skills/minimax-h3-prompt/knowledge/tokenizer.json",
    "mcp_server/pyproject.toml",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path)
    args = parser.parse_args()
    for root in filter(None, (args.source_root, args.cache_root)):
        missing = [path for path in REQUIRED if not (root / path).is_file()]
        if missing:
            parser.error(f"release root {root} is missing: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
