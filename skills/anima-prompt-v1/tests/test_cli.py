from __future__ import annotations

import io
import json
import os
from pathlib import Path
import subprocess
import sys

from anima_prompt_v1.cli import main


CATALOG = Path(__file__).parents[1] / "knowledge" / "tag-catalog.sqlite"


def _request() -> dict:
    return {
        "variant": "base",
        "route": "tag-led",
        "facts": [
            {
                "fact_id": "fact:hair",
                "value": "long_hair",
                "domain": "hair",
                "kind": "explicit",
                "source": "user",
                "subject_id": "subject:0",
                "representation_hint": "tag",
                "user_text": "long hair",
            }
        ],
        "subjects": [{"subject_id": "subject:0", "label": "woman"}],
    }


def _invoke(argv: list[str], *, stdin_text: str | None = None):
    stdout = io.StringIO()
    stderr = io.StringIO()
    stdin = io.StringIO(stdin_text) if stdin_text is not None else io.StringIO()
    code = main(argv, stdin=stdin, stdout=stdout, stderr=stderr)
    payload = json.loads(stdout.getvalue())
    return code, payload, stderr.getvalue()


def test_author_runs_every_canonical_phase_and_keeps_provenance_outside_prompt(tmp_path):
    request_path = tmp_path / "brief.json"
    request_path.write_text(json.dumps(_request()), encoding="utf-8")

    code, envelope, stderr = _invoke(
        [
            "author",
            "--database",
            str(CATALOG),
            "--request",
            str(request_path),
            "--json",
        ]
    )

    assert code == 0
    assert stderr == ""
    assert set(envelope) == {
        "ok",
        "command",
        "stage",
        "result",
        "errors",
        "advisories",
    }
    assert envelope["ok"] is True
    assert envelope["command"] == "author"
    assert envelope["stage"] == "author"

    result = envelope["result"]
    assert set(result["prompt"]) == {
        "positive",
        "negative",
        "notes",
        "assumptions",
        "advisories",
    }
    assert "long_hair" in result["prompt"]["positive"]
    assert "masterpiece" in result["prompt"]["positive"]
    assert result["prompt"]["negative"]
    assert result["metadata"]["variant"] == "base"
    assert result["metadata"]["route"] == "tag-led"

    expected_phases = {
        "brief",
        "quality_seed",
        "catalog",
        "relation_graph",
        "route",
        "positive_author",
        "negative_author",
        "plan",
        "draft",
        "inspection",
        "output",
    }
    assert set(result["phase_status"]) == expected_phases
    assert set(result["phase_status"].values()) <= {"PASS", "ADVISORY", "UNVERIFIED"}
    assert all(status != "UNVERIFIED" for status in result["phase_status"].values())

    assert result["catalog_hits"]
    assert all(hit["record_id"] for hit in result["catalog_hits"])
    assert all(hit["provenance"] for hit in result["catalog_hits"])
    assert set(result["relation_record_ids"]).issubset(
        {hit["record_id"] for hit in result["catalog_hits"]}
    )
    prompt_text = result["prompt"]["positive"] + result["prompt"]["negative"]
    assert not any(hit["record_id"] in prompt_text for hit in result["catalog_hits"])
    assert result["brief"]["facts"]
    assert result["draft"]["segments"]


def test_author_rejects_raw_text_as_an_authoritative_request():
    code, envelope, stderr = _invoke(
        [
            "author",
            "--database",
            str(CATALOG),
            "--stdin",
            "--json",
        ],
        stdin_text=json.dumps({"text": "a girl with long hair"}),
    )

    assert code == 3
    assert stderr == ""
    assert envelope["ok"] is False
    assert envelope["result"] is None
    assert envelope["errors"][0]["code"] == "structured_brief_required"
    assert envelope["errors"][0]["details"] == {
        "required": ["facts", "subjects"]
    }


def test_author_rejects_unknown_fields_and_string_booleans():
    unknown = _request()
    unknown["prompt"] = "must not be silently accepted"
    code, envelope, _ = _invoke(
        ["author", "--database", str(CATALOG), "--stdin", "--json"],
        stdin_text=json.dumps(unknown),
    )
    assert code == 3
    assert envelope["errors"][0]["code"] == "unknown_request_fields"
    assert envelope["errors"][0]["details"] == {"fields": ["prompt"]}

    invalid_boolean = _request()
    invalid_boolean["facts"][0]["locked"] = "false"
    code, envelope, _ = _invoke(
        ["author", "--database", str(CATALOG), "--stdin", "--json"],
        stdin_text=json.dumps(invalid_boolean),
    )
    assert code == 3
    assert envelope["errors"][0]["code"] == "request_validation_failed"
    assert "locked must be a boolean" in envelope["errors"][0]["message"]


def test_inspect_is_read_only_and_returns_issues_for_the_serialized_draft(tmp_path):
    request_path = tmp_path / "brief-request.json"
    request_path.write_text(json.dumps(_request()), encoding="utf-8")
    code, authored, _ = _invoke(
        [
            "author",
            "--database",
            str(CATALOG),
            "--request",
            str(request_path),
            "--json",
        ]
    )
    assert code == 0

    draft_path = tmp_path / "draft.json"
    brief_path = tmp_path / "brief.json"
    draft_path.write_text(json.dumps(authored["result"]["draft"]), encoding="utf-8")
    brief_path.write_text(json.dumps(authored["result"]["brief"]), encoding="utf-8")
    before_draft = draft_path.read_bytes()
    before_brief = brief_path.read_bytes()

    code, envelope, stderr = _invoke(
        [
            "inspect",
            "--draft",
            str(draft_path),
            "--brief",
            str(brief_path),
            "--json",
        ]
    )

    assert code == 0
    assert stderr == ""
    assert envelope["ok"] is True
    assert envelope["command"] == "inspect"
    assert envelope["stage"] == "inspection"
    assert isinstance(envelope["result"]["issues"], list)
    assert envelope["result"]["draft_summary"] == {
        "positive": authored["result"]["prompt"]["positive"],
        "negative": authored["result"]["prompt"]["negative"],
        "route": "tag-led",
        "segment_count": len(authored["result"]["draft"]["segments"]),
    }
    assert draft_path.read_bytes() == before_draft
    assert brief_path.read_bytes() == before_brief


def _console_script(name: str) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return Path(sys.executable).parent / f"{name}{suffix}"


def test_installed_console_scripts_expose_help_version_json_and_compatibility_alias():
    command = _console_script("anima-prompt-v1")
    alias = _console_script("anima-catalog")

    version = subprocess.run(
        [command, "--version"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert version.returncode == 0
    assert version.stdout.strip() == "anima-prompt-v1 1.0.0"
    assert version.stderr == ""

    help_result = subprocess.run(
        [command, "--help"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert help_result.returncode == 0
    assert "{author,inspect,catalog,relation}" in help_result.stdout

    invalid = subprocess.run(
        [command, "author", "--stdin", "--json"],
        input="{broken",
        text=True,
        capture_output=True,
        check=False,
    )
    assert invalid.returncode == 2
    assert json.loads(invalid.stdout)["errors"][0]["code"] == "request_invalid"
    assert invalid.stderr == ""

    alias_result = subprocess.run(
        [alias, "stats", "--database", str(CATALOG), "--json"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert alias_result.returncode == 0
    assert json.loads(alias_result.stdout)["command"] == "catalog stats"
    assert alias_result.stderr == ""


def test_argument_errors_use_the_json_envelope_when_json_was_requested():
    command = _console_script("anima-prompt-v1")
    result = subprocess.run(
        [command, "catalog", "search", "--json"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    envelope = json.loads(result.stdout)
    assert envelope["ok"] is False
    assert envelope["command"] == "catalog search"
    assert envelope["errors"][0]["code"] == "argument_error"
    assert result.stderr == ""
