"""Make Prompt Forge internals importable when tests run in isolation."""

import sys
from pathlib import Path


PROMPT_FORGE_ROOT = Path(__file__).resolve().parents[2]
if str(PROMPT_FORGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PROMPT_FORGE_ROOT))
