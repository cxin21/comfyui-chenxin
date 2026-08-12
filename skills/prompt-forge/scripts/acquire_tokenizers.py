"""Acquire repository-pinned tokenizer snapshots for maintainer review.

This script is intentionally not called by installation or runtime code. It
writes complete candidate snapshots to a maintainer-selected staging folder;
promotion into ``knowledge/tokenizers`` is a separate reviewed file operation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from tokenizers import Tokenizer


def _copy_lf(source: Path, destination: Path) -> None:
    data = source.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    destination.write_bytes(data)


@dataclass(frozen=True)
class SnapshotSpec:
    snapshot_id: str
    model_id: str
    repository: str
    revision: str
    hard_limit: int
    acquired_at: str
    license_id: str
    license_url: str
    license_conditions: str | None
    files: tuple[tuple[str, str], ...]
    notice: str | None = None


SPECS = (
    SnapshotSpec(
        snapshot_id="anima-qwen3-0.6b",
        model_id="Qwen/Qwen3-0.6B",
        repository="https://huggingface.co/Qwen/Qwen3-0.6B",
        revision="c1899de289a04d12100db370d81485cdf75e47ca",
        hard_limit=32_768,
        acquired_at="2026-08-12",
        license_id="Apache-2.0",
        license_url=(
            "https://huggingface.co/Qwen/Qwen3-0.6B/blob/"
            "c1899de289a04d12100db370d81485cdf75e47ca/LICENSE"
        ),
        license_conditions=None,
        files=(
            ("tokenizer.json", "tokenizer.json"),
            ("tokenizer_config.json", "tokenizer_config.json"),
            ("LICENSE", "LICENSE"),
        ),
    ),
    SnapshotSpec(
        snapshot_id="h3-qwen3-vl",
        model_id="MiniMaxAI/MiniMax-H3:text_encoder",
        repository="https://huggingface.co/MiniMaxAI/MiniMax-H3",
        revision="939557dc319dd91227e30195a763f272ba7f8765",
        hard_limit=262_144,
        acquired_at="2026-08-12",
        license_id="MiniMax-H3-Community-License-2026-08-02",
        license_url=(
            "https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/"
            "939557dc319dd91227e30195a763f272ba7f8765/LICENSE"
        ),
        license_conditions=(
            "Redistribution and use are limited to the Applicable Territory "
            "defined by the license; LICENSE and NOTICE must accompany the files."
        ),
        files=(
            ("text_encoder/tokenizer.json", "tokenizer.json"),
            ("text_encoder/tokenizer_config.json", "tokenizer_config.json"),
            ("text_encoder/chat_template.json", "chat_template.json"),
            ("LICENSE", "LICENSE"),
        ),
        notice=(
            "MiniMax H3 is licensed under the MiniMax H3 Community License "
            "Agreement, Copyright © 2026 MiniMax. All Rights Reserved.\n"
        ),
    ),
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    installed_root = (Path(__file__).resolve().parents[1] / "knowledge" / "tokenizers").resolve()
    if output_dir == installed_root:
        parser.error("acquisition must use a staging directory, not knowledge/tokenizers")
    if output_dir.exists() and any(output_dir.iterdir()):
        parser.error("output directory must be absent or empty")
    output_dir.mkdir(parents=True, exist_ok=True)

    for spec in SPECS:
        _acquire(spec, output_dir / spec.snapshot_id)
    print(f"candidate snapshots written to {output_dir}")
    print("review manifests and licenses before promoting them into knowledge/tokenizers")
    return 0


def _acquire(spec: SnapshotSpec, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix=f"prompt-forge-{spec.snapshot_id}-") as temp:
        checkout = Path(temp) / "checkout"
        _run("git", "clone", "--filter=blob:none", "--no-checkout", spec.repository, str(checkout))
        _run("git", "sparse-checkout", "init", "--no-cone", cwd=checkout)
        _run(
            "git",
            "sparse-checkout",
            "set",
            *(source for source, _ in spec.files),
            cwd=checkout,
        )
        _run("git", "checkout", spec.revision, cwd=checkout)

        for source_name, destination_name in spec.files:
            source = checkout / source_name
            if not source.is_file():
                raise RuntimeError(f"pinned source file is missing: {source_name}")
            _copy_lf(source, destination / destination_name)

    if spec.notice is not None:
        (destination / "NOTICE").write_text(spec.notice, encoding="utf-8", newline="")

    config = json.loads((destination / "tokenizer_config.json").read_text(encoding="utf-8"))
    if config.get("tokenizer_class") != "Qwen2Tokenizer":
        raise RuntimeError("unexpected tokenizer_class in pinned tokenizer config")
    Tokenizer.from_file(str(destination / "tokenizer.json"))
    if (destination / "chat_template.json").is_file():
        template = json.loads(
            (destination / "chat_template.json").read_text(encoding="utf-8")
        )
        if template.get("chat_template") != config.get("chat_template"):
            raise RuntimeError("chat template files disagree")

    license_record: dict[str, object] = {
        "id": spec.license_id,
        "url": spec.license_url,
        "redistribution_allowed": True,
    }
    if spec.license_conditions is not None:
        license_record["conditions"] = spec.license_conditions
    file_hashes = {
        path.name: _sha256(path)
        for path in sorted(destination.iterdir(), key=lambda item: item.name)
        if path.is_file()
    }
    manifest = {
        "schema_version": 1,
        "snapshot_id": spec.snapshot_id,
        "model_id": spec.model_id,
        "upstream_repository": spec.repository,
        "upstream_revision": spec.revision,
        "acquired_at": spec.acquired_at,
        "tokenizer_class": "Qwen2Tokenizer",
        "model_hard_limit": spec.hard_limit,
        "license": license_record,
        "files": file_hashes,
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
        newline="",
    )


def _run(*command: str, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
