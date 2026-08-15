import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from anima_prompt_v1.cli import catalog_main as main

if __name__ == "__main__":
    raise SystemExit(main())
