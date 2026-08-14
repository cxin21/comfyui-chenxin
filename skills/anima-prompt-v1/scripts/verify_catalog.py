from __future__ import annotations

import argparse
import json
from contextlib import closing
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from anima_prompt_v1.catalog.builder import verify_manifest
from anima_prompt_v1.catalog.storage import CatalogStore


def verify(database: Path, manifest: Path | None = None) -> list[str]:
    issues: list[str] = []
    issues.extend(CatalogStore.schema_errors(database))
    if CatalogStore.integrity_check(database) != ("ok",):
        issues.append("sqlite integrity check failed")
    with closing(CatalogStore.connect_readonly(database)) as connection:
        required = ("sources", "records", "names", "relations", "concepts", "facets", "record_facets", "catalog_fts")
        present = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        issues.extend(f"missing schema object: {name}" for name in required if name not in present)
        if connection.execute("SELECT COUNT(*) FROM catalog_fts").fetchone()[0] != connection.execute("SELECT COUNT(*) FROM names").fetchone()[0]:
            issues.append("FTS row count differs from names")
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            issues.append("foreign key check failed")
    if manifest is not None:
        if not verify_manifest(manifest):
            issues.append("manifest checksum or artifact validation failed")
        elif json.loads(manifest.read_text(encoding="utf-8")).get("content_filters") is not False:
            issues.append("content_filters must be false")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    issues = verify(args.database, args.manifest)
    if issues:
        print("\n".join(issues))
        return 1
    print("catalog verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
