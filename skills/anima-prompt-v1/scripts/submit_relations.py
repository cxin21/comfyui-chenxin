from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from anima_prompt_v1.cli import relation_main as main


if __name__ == "__main__":
    raise SystemExit(main())
