from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from prompt_forge.token_counting import (
    TokenCounter,
    TokenizerIntegrityError,
    count_h3_text_context,
)


KNOWLEDGE_ROOT = Path(__file__).resolve().parents[1] / "knowledge" / "tokenizers"


@pytest.fixture(scope="module")
def anima_counter() -> TokenCounter:
    return TokenCounter.load(
        KNOWLEDGE_ROOT / "anima-qwen3-0.6b",
        expected_model="anima-qwen3-0.6b",
    )


@pytest.fixture(scope="module")
def h3_counter() -> TokenCounter:
    return TokenCounter.load(
        KNOWLEDGE_ROOT / "h3-qwen3-vl",
        expected_model="h3-qwen3-vl",
    )


@pytest.mark.parametrize(
    ("text", "expected_ids"),
    [
        ("", ()),
        ("A red fox runs through snow.", (32, 2518, 38835, 8473, 1526, 11794, 13)),
        ("一名女孩站在雨中。", (101177, 101339, 104224, 100029, 15946, 1773)),
        (
            "masterpiece, best quality, score_7, safe, 1girl, @artist",
            (13629, 22362, 11, 1850, 4271, 11, 5456, 62, 22, 11, 6092, 11, 220, 16, 28552, 11, 569, 18622),
        ),
    ],
)
def test_anima_exact_token_ids(
    anima_counter: TokenCounter,
    text: str,
    expected_ids: tuple[int, ...],
) -> None:
    assert anima_counter.encode(text) == expected_ids
    assert anima_counter.count(text) == len(expected_ids)


def test_h3_exact_dialogue_and_chat_framing(h3_counter: TokenCounter) -> None:
    prompt = 'integrated_multimodal_description: [0.0s-3.0s] She says, "Wait."'
    expected_ids = (
        151644, 872, 198, 396, 47172, 26290, 318, 57597, 11448, 25,
        508, 15, 13, 15, 82, 12, 18, 13, 15, 82, 60, 2932, 2727, 11,
        330, 14190, 1189, 151645, 198,
    )

    assert count_h3_text_context(h3_counter, prompt) == len(expected_ids)
    assert h3_counter.encode(
        f"<|im_start|>user\n{prompt}<|im_end|>\n"
    ) == expected_ids


def test_h3_reference_framing_uses_official_special_tokens(
    h3_counter: TokenCounter,
) -> None:
    expected_ids = (
        151644, 872, 198, 24669, 220, 16, 25, 220, 151652, 151655,
        151653, 198, 74785, 569, 1906, 16, 13, 151645, 198,
    )
    assert count_h3_text_context(
        h3_counter,
        "Describe @Image1.",
        reference_count=1,
    ) == len(expected_ids)


def test_verified_snapshots_expose_physical_limits(
    anima_counter: TokenCounter,
    h3_counter: TokenCounter,
) -> None:
    assert anima_counter.verified is True
    assert anima_counter.model_hard_limit == 32_768
    assert h3_counter.verified is True
    assert h3_counter.model_hard_limit == 262_144


def test_count_many_counts_the_actual_concatenated_text(
    anima_counter: TokenCounter,
) -> None:
    parts = ("master", "piece", ", 1girl")
    assert anima_counter.count_many(parts) == anima_counter.count("".join(parts))


def test_verified_load_reuses_the_native_tokenizer_without_skipping_integrity() -> None:
    snapshot = KNOWLEDGE_ROOT / "anima-qwen3-0.6b"
    first = TokenCounter.load(snapshot, expected_model="anima-qwen3-0.6b")
    second = TokenCounter.load(snapshot, expected_model="anima-qwen3-0.6b")
    assert first._tokenizer is second._tokenizer


def test_unknown_or_modified_snapshot_fails_closed(tmp_path: Path) -> None:
    source = KNOWLEDGE_ROOT / "anima-qwen3-0.6b"
    snapshot = tmp_path / "snapshot"
    shutil.copytree(source, snapshot)
    config_path = snapshot / "tokenizer_config.json"
    config_path.write_text(
        config_path.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )

    with pytest.raises(TokenizerIntegrityError, match="SHA-256 mismatch"):
        TokenCounter.load(snapshot, expected_model="anima-qwen3-0.6b")
    with pytest.raises(TokenizerIntegrityError, match="snapshot id mismatch"):
        TokenCounter.load(source, expected_model="some-other-model")


def test_manifest_records_revision_class_license_and_every_file() -> None:
    for snapshot_name in ("anima-qwen3-0.6b", "h3-qwen3-vl"):
        snapshot = KNOWLEDGE_ROOT / snapshot_name
        manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
        assert len(manifest["upstream_revision"]) == 40
        assert manifest["tokenizer_class"] == "Qwen2Tokenizer"
        assert manifest["license"]["redistribution_allowed"] is True
        assert manifest["license"]["url"].startswith("https://")
        assert set(manifest["files"]) == {
            path.name for path in snapshot.iterdir() if path.name != "manifest.json"
        }
