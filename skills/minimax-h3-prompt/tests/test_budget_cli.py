from __future__ import annotations

import io
import json
from pathlib import Path
import shutil

from h3_prompt.cli import main

from test_cli import KNOWLEDGE, invoke, ref2va_request


def test_tokenizer_verify_and_exact_count_report_manifest_identity(tmp_path):
    code, verified, _ = invoke(
        ["tokenizer", "verify", "--tokenizer-dir", str(KNOWLEDGE), "--json"]
    )
    assert code == 0
    assert verified["result"]["verified"] is True
    assert verified["result"]["snapshot_id"] == "h3-qwen3-vl"
    assert verified["result"]["model_id"] == "MiniMaxAI/MiniMax-H3:text_encoder"
    assert len(verified["result"]["files"]) == 5

    text_path = tmp_path / "prompt.txt"
    text_path.write_text("A camera pans left.", encoding="utf-8")
    code, counted, _ = invoke(
        [
            "count",
            "--text",
            str(text_path),
            "--references",
            "1",
            "--tokenizer-dir",
            str(KNOWLEDGE),
            "--json",
        ]
    )
    assert code == 0
    assert counted["result"]["verified"] is True
    assert counted["result"]["tokens"] > 0
    assert counted["result"]["reference_count"] == 1


def test_tokenizer_hash_mismatch_is_integrity_exit_4(tmp_path):
    snapshot = tmp_path / "knowledge"
    shutil.copytree(KNOWLEDGE, snapshot)
    config = snapshot / "tokenizer_config.json"
    config.write_text(config.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    code, envelope, stderr = invoke(
        ["tokenizer", "verify", "--tokenizer-dir", str(snapshot), "--json"]
    )
    assert code == 4
    assert stderr == ""
    assert envelope["errors"][0]["code"] == "tokenizer_integrity_failed"
    assert "SHA-256 mismatch" in envelope["errors"][0]["message"]


def test_context_plan_uses_reference_dimensions_and_rejects_overflow():
    request = ref2va_request()
    request["text_quality_limit"] = 2400
    request["special_tokens"] = 32
    request["runtime_safety_margin"] = 256
    code, envelope, _ = invoke(
        [
            "context-plan",
            "--stdin",
            "--tokenizer-dir",
            str(KNOWLEDGE),
            "--json",
        ],
        request,
    )
    assert code == 0
    plan = envelope["result"]["context_plan"]
    assert plan["visual_tokens"] == 256
    assert plan["special_tokens"] == 32
    assert plan["runtime_safety_margin"] == 256
    assert plan["effective_quality_limit"] == 2400

    request["runtime_safety_margin"] = 300_000
    code, overflow, _ = invoke(
        [
            "context-plan",
            "--stdin",
            "--tokenizer-dir",
            str(KNOWLEDGE),
            "--json",
        ],
        request,
    )
    assert code == 3
    assert overflow["errors"][0]["code"] == "context_overflow"
