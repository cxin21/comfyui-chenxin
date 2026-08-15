from __future__ import annotations

import io
import json
import sqlite3
from pathlib import Path

from anima_prompt_v1.cli import catalog_main, main


ROOT = Path(__file__).parents[1]
CATALOG = ROOT / "knowledge" / "tag-catalog.sqlite"
FIXTURES = Path(__file__).parent / "fixtures"


def _invoke(argv: list[str]):
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = main(argv, stdin=io.StringIO(), stdout=stdout, stderr=stderr)
    return code, json.loads(stdout.getvalue()), stderr.getvalue()


def _write_raw_catalog(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE tags (
                tag_id INTEGER PRIMARY KEY,
                canonical TEXT NOT NULL,
                anima_form TEXT NOT NULL,
                category TEXT NOT NULL,
                usage_count INTEGER NOT NULL,
                source TEXT NOT NULL,
                source_version TEXT NOT NULL
            );
            CREATE TABLE aliases (
                alias TEXT NOT NULL,
                tag_id INTEGER NOT NULL,
                source TEXT NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO tags VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, "long_hair", "long_hair", "general", 10, "fixture", "v1"),
        )
        connection.execute(
            "INSERT INTO aliases VALUES (?, ?, ?)",
            ("longhair", 1, "fixture"),
        )


def test_catalog_search_browse_stats_and_compatibility_alias_return_provenance():
    code, envelope, stderr = _invoke(
        [
            "catalog",
            "search",
            "long_hair",
            "--database",
            str(CATALOG),
            "--mode",
            "exact",
            "--json",
        ]
    )
    assert code == 0
    assert stderr == ""
    hit = envelope["result"]["hits"][0]
    assert hit["canonical_name"] == "long_hair"
    assert hit["match_type"] == "canonical"
    assert hit["provenance"]
    assert hit["candidate"] is False

    code, fuzzy, _ = _invoke(
        [
            "catalog",
            "search",
            "long_hair",
            "--database",
            str(CATALOG),
            "--mode",
            "fuzzy",
            "--json",
        ]
    )
    assert code == 0
    assert fuzzy["result"]["hits"][0]["candidate"] is True

    code, browse, _ = _invoke(
        [
            "catalog",
            "browse",
            "--database",
            str(CATALOG),
            "--category",
            "general",
            "--limit",
            "2",
            "--json",
        ]
    )
    assert code == 0
    assert len(browse["result"]["hits"]) == 2

    code, stats, _ = _invoke(
        ["catalog", "stats", "--database", str(CATALOG), "--json"]
    )
    assert code == 0
    assert stats["result"]["stats"]["records"] >= 1_000_000

    alias_stdout = io.StringIO()
    alias_code = catalog_main(
        ["stats", "--database", str(CATALOG), "--json"],
        stdout=alias_stdout,
        stderr=io.StringIO(),
    )
    assert alias_code == 0
    assert json.loads(alias_stdout.getvalue())["command"] == "catalog stats"

    legacy_stdout = io.StringIO()
    legacy_code = catalog_main(
        ["--database", str(CATALOG), "search", "long_hair", "--json"],
        stdout=legacy_stdout,
        stderr=io.StringIO(),
    )
    assert legacy_code == 0
    assert json.loads(legacy_stdout.getvalue())["result"]["hits"][0][
        "canonical_name"
    ] == "long_hair"


def test_catalog_build_export_and_verify_report_absolute_artifacts(tmp_path):
    source = tmp_path / "source.sqlite"
    _write_raw_catalog(source)
    output = tmp_path / "catalog.sqlite"
    manifest = tmp_path / "manifest.json"
    code, built, _ = _invoke(
        [
            "catalog",
            "build",
            "--source",
            str(source),
            "--output",
            str(output),
            "--manifest",
            str(manifest),
            "--json",
        ]
    )
    assert code == 0
    assert built["result"]["output"] == str(output.resolve())
    assert built["result"]["manifest"] == str(manifest.resolve())
    assert built["result"]["stats"]["records"] > 0

    code, verified, _ = _invoke(
        [
            "catalog",
            "verify",
            "--database",
            str(output),
            "--manifest",
            str(manifest),
            "--json",
        ]
    )
    assert code == 0
    assert verified["result"] == {
        "database": str(output.resolve()),
        "manifest": str(manifest.resolve()),
        "issues": [],
    }

    exported = tmp_path / "hits.jsonl"
    code, export, _ = _invoke(
        [
            "catalog",
            "export",
            "--database",
            str(output),
            "--query",
            "long_hair",
            "--mode",
            "exact",
            "--format",
            "jsonl",
            "--output",
            str(exported),
            "--json",
        ]
    )
    assert code == 0
    assert export["result"]["output"] == str(exported.resolve())
    assert export["result"]["count"] >= 1
    assert len(export["result"]["sha256"]) == 64
    assert json.loads(exported.read_text(encoding="utf-8").splitlines()[0])[
        "canonical_name"
    ] == "long_hair"

    manifest.write_text("{}", encoding="utf-8")
    code, invalid, _ = _invoke(
        [
            "catalog",
            "verify",
            "--database",
            str(output),
            "--manifest",
            str(manifest),
            "--json",
        ]
    )
    assert code == 4
    assert invalid["errors"][0]["code"] == "catalog_integrity_failed"


def test_missing_catalog_is_an_integrity_error_not_an_internal_error(tmp_path):
    missing = tmp_path / "missing.sqlite"
    code, envelope, stderr = _invoke(
        ["catalog", "stats", "--database", str(missing), "--json"]
    )
    assert code == 4
    assert envelope["errors"][0]["code"] == "resource_unavailable"
    assert stderr == ""


def test_relation_commands_keep_candidates_separate_from_acceptance(tmp_path):
    overlay = tmp_path / "relations.sqlite"
    payload = tmp_path / "relation.json"
    payload.write_text(
        (FIXTURES / "relation_submission.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    code, submitted, _ = _invoke(
        [
            "relation",
            "submit",
            "--database",
            str(CATALOG),
            "--overlay",
            str(overlay),
            "--payload",
            str(payload),
            "--json",
        ]
    )
    assert code == 0
    proposal = submitted["result"]["proposals"][0]
    assert proposal["status"] == "candidate"

    code, candidates, _ = _invoke(
        [
            "relation",
            "list",
            "--overlay",
            str(overlay),
            "--status",
            "candidate",
            "--json",
        ]
    )
    assert code == 0
    assert [item["proposal_id"] for item in candidates["result"]["proposals"]] == [
        proposal["proposal_id"]
    ]

    code, candidate_search, _ = _invoke(
        [
            "catalog",
            "search",
            "long_hair",
            "--database",
            str(CATALOG),
            "--overlay",
            str(overlay),
            "--mode",
            "related",
            "--json",
        ]
    )
    assert code == 0
    assert candidate_search["result"]["hits"] == []

    code, accepted, _ = _invoke(
        [
            "relation",
            "accept",
            "--overlay",
            str(overlay),
            proposal["proposal_id"],
            "--json",
        ]
    )
    assert code == 0
    assert accepted["result"]["status"] == "accepted"

    code, accepted_search, _ = _invoke(
        [
            "catalog",
            "search",
            "long_hair",
            "--database",
            str(CATALOG),
            "--overlay",
            str(overlay),
            "--mode",
            "related",
            "--json",
        ]
    )
    assert code == 0
    assert accepted_search["result"]["hits"][0]["match_type"] == "related"

    code, accepted_related, _ = _invoke(
        [
            "catalog",
            "related",
            proposal["from_record_id"],
            "--database",
            str(CATALOG),
            "--overlay",
            str(overlay),
            "--json",
        ]
    )
    assert code == 0
    assert accepted_related["result"]["relations"][0]["status"] == "accepted"

    code, accepted_list, _ = _invoke(
        [
            "relation",
            "list",
            "--overlay",
            str(overlay),
            "--status",
            "accepted",
            "--json",
        ]
    )
    assert code == 0
    assert accepted_list["result"]["proposals"][0]["status"] == "accepted"

    code, rejected, _ = _invoke(
        [
            "relation",
            "reject",
            "--overlay",
            str(overlay),
            proposal["proposal_id"],
            "--json",
        ]
    )
    assert code == 0
    assert rejected["result"]["status"] == "rejected"


def test_relation_submit_rejects_cooccurrence_without_persisting(tmp_path):
    overlay = tmp_path / "relations.sqlite"
    payload_data = json.loads(
        (FIXTURES / "relation_submission.json").read_text(encoding="utf-8")
    )
    payload_data["relations"][0]["relation_type"] = "cooccurrence"
    payload = tmp_path / "cooccurrence.json"
    payload.write_text(json.dumps(payload_data), encoding="utf-8")

    code, envelope, _ = _invoke(
        [
            "relation",
            "submit",
            "--database",
            str(CATALOG),
            "--overlay",
            str(overlay),
            "--payload",
            str(payload),
            "--json",
        ]
    )
    assert code == 3
    assert envelope["errors"][0]["code"] == "relation_validation_failed"

    code, listed, _ = _invoke(
        [
            "relation",
            "list",
            "--overlay",
            str(overlay),
            "--status",
            "all",
            "--json",
        ]
    )
    assert code == 0
    assert listed["result"]["proposals"] == []


def test_relation_submit_is_atomic_when_one_item_is_invalid(tmp_path):
    overlay = tmp_path / "relations.sqlite"
    payload_data = json.loads(
        (FIXTURES / "relation_submission.json").read_text(encoding="utf-8")
    )
    invalid = dict(payload_data["relations"][0])
    invalid["relation_type"] = "cooccurrence"
    payload_data["relations"].append(invalid)
    payload = tmp_path / "mixed.json"
    payload.write_text(json.dumps(payload_data), encoding="utf-8")

    code, envelope, _ = _invoke(
        [
            "relation",
            "submit",
            "--database",
            str(CATALOG),
            "--overlay",
            str(overlay),
            "--payload",
            str(payload),
            "--json",
        ]
    )
    assert code == 3
    assert envelope["errors"][0]["code"] == "relation_validation_failed"

    code, listed, _ = _invoke(
        [
            "relation",
            "list",
            "--overlay",
            str(overlay),
            "--status",
            "all",
            "--json",
        ]
    )
    assert code == 0
    assert listed["result"]["proposals"] == []
