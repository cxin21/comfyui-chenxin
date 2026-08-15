from __future__ import annotations

import io
import json
from pathlib import Path

from h3_prompt.cli import main


KNOWLEDGE = Path(__file__).parents[1] / "knowledge"


def t2va_request() -> dict:
    return {
        "facts": [
            {
                "fact_id": "fact:subject",
                "value": "woman",
                "origin": "user_explicit",
                "locked": True,
                "owner": "Subject 1",
                "dimension": "identity",
            }
        ],
        "duration_seconds": 4,
        "shot_count": 1,
        "integrated_multimodal_description": [
            {
                "segment_id": "shot:1",
                "field": "integrated_multimodal_description",
                "text": "[Shot 1] A woman stands by a window. The camera pans left. She sits on a chair.",
                "fact_ids": ["fact:subject"],
            }
        ],
        "overall_soundscape": [
            {
                "segment_id": "sound:1",
                "field": "overall_soundscape",
                "text": "Soft room tone and distant footsteps.",
                "fact_ids": [],
            }
        ],
        "non_diegetic_music": [],
    }


def ref2va_request() -> dict:
    request = t2va_request()
    return {
        "facts": request["facts"],
        "duration_seconds": 4,
        "shot_count": 1,
        "references": [
            {
                "reference_id": "Picture 1",
                "owner": "woman",
                "resized_width": 512,
                "resized_height": 512,
            }
        ],
        "subject_definitions": [
            {
                "segment_id": "subject:1",
                "field": "subject_definitions",
                "text": "<Picture 1> is the woman in a blue coat.",
                "fact_ids": ["fact:subject"],
            }
        ],
        "summary": [
            {
                "segment_id": "summary:1",
                "field": "summary",
                "text": "The woman crosses the quiet room.",
                "fact_ids": ["fact:subject"],
            }
        ],
        "retention_analysis": [
            {
                "segment_id": "retain:1",
                "field": "retention_analysis",
                "text": "Retain <Picture 1> face, blue coat, and body proportions.",
                "fact_ids": ["fact:subject"],
            }
        ],
        "detailed_description": [
            {
                "segment_id": "shot:1",
                "field": "detailed_description",
                "text": "[Shot 1] <Picture 1> walks across the room. The camera tracks her. She stops beside the window.",
                "fact_ids": ["fact:subject"],
            }
        ],
        "overall_soundscape": [],
        "non_diegetic_music": [],
    }


def invoke(argv: list[str], request: dict | None = None):
    stdout = io.StringIO()
    stderr = io.StringIO()
    stdin = io.StringIO(json.dumps(request)) if request is not None else io.StringIO()
    code = main(argv, stdin=stdin, stdout=stdout, stderr=stderr)
    return code, json.loads(stdout.getvalue()), stderr.getvalue()


def test_author_t2va_returns_audited_copyable_text_without_visual_budget():
    code, envelope, stderr = invoke(
        ["author", "--stage", "t2va", "--stdin", "--json"], t2va_request()
    )
    assert code == 0
    assert stderr == ""
    assert envelope["result"]["text"].startswith("integrated_multimodal_description:")
    assert envelope["result"]["findings"] == []
    assert envelope["result"]["budget"] == {
        "verified": True,
        "visual_budget_applicable": False,
        "reference_count": 0,
        "text_tokens": envelope["result"]["budget"]["text_tokens"],
        "model_hard_limit": 262144,
    }


def test_author_ref2va_wires_verified_context_plan_into_output():
    code, envelope, stderr = invoke(
        [
            "author",
            "--stage",
            "ref2va",
            "--stdin",
            "--tokenizer-dir",
            str(KNOWLEDGE),
            "--json",
        ],
        ref2va_request(),
    )
    assert code == 0
    assert stderr == ""
    result = envelope["result"]
    assert result["findings"] == []
    assert result["budget"]["verified"] is True
    assert result["budget"]["visual_budget_applicable"] is True
    assert result["budget"]["context_plan"]["visual_tokens"] == 256
    assert result["budget"]["text_tokens"] <= result["budget"]["context_plan"][
        "effective_quality_limit"
    ]


def test_audit_reports_temporal_and_reference_findings_without_rewriting():
    invalid = ref2va_request()
    invalid["references"][0]["reference_id"] = "Picture 2"
    original = json.loads(json.dumps(invalid))
    code, envelope, _ = invoke(
        ["audit", "--stage", "ref2va", "--stdin", "--json"], invalid
    )
    assert code == 3
    assert envelope["errors"][0]["code"] == "h3_audit_failed"
    assert "reference IDs must match" in envelope["errors"][0]["details"]["findings"][0]
    assert invalid == original

