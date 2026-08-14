from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from anima_prompt_v1.catalog.builder import CatalogBuilder, verify_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a deterministic Anima tag catalog.")
    parser.add_argument("source", type=Path, nargs="?")
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--verify-manifest", action="store_true")
    arguments = parser.parse_args()
    if arguments.verify_manifest:
        if arguments.manifest is None:
            parser.error("--verify-manifest requires --manifest")
        return 0 if verify_manifest(arguments.manifest) else 1
    if arguments.source is None or arguments.output is None:
        parser.error("source and output are required when building")
    print(CatalogBuilder(arguments.source, arguments.output).build(manifest_path=arguments.manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
