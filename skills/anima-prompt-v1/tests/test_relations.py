import json
import inspect
from pathlib import Path
from tempfile import TemporaryDirectory

from anima_prompt_v1 import attach_relation_submission
from anima_prompt_v1.authoring.relation_submission import (
    RelationValidator,
    relation_record_ids_from_hits,
    submit_relation_payload,
)
from anima_prompt_v1.authoring.workflow import run_authoring_workflow
from anima_prompt_v1.catalog import Catalog, RelationOverlay
from anima_prompt_v1.domain import Fact, PromptBrief, Subject


def _brief():
    return PromptBrief(
        facts=(
            Fact("fact:hair", "long_hair", "hair", "explicit", "user", representation_hint="tag"),
            Fact("fact:eyes", "blue_eyes", "appearance", "explicit", "user", representation_hint="tag"),
        ),
        subjects=(Subject("subject:0", "woman"),),
    )


def _payload(hair_id: str, eyes_id: str, relation_type: str = "related", evidence=("same request",)):
    return {
        "catalog_record_ids": [hair_id, eyes_id],
        "relations": [{
            "from_record_id": hair_id,
            "to_record_id": eyes_id,
            "relation_type": relation_type,
            "confidence": 0.8,
            "rationale": "both are explicit appearance context",
            "evidence": list(evidence),
        }],
    }


def _hits(catalog: Catalog):
    return tuple(catalog.search(value, mode="exact", limit=1)[0] for value in ("long_hair", "blue_eyes"))


def test_validator_rejects_unsupported_or_unsupported_evidence_without_calling_a_model():
    catalog = Catalog()
    hits = _hits(catalog)
    ids = relation_record_ids_from_hits(hits)

    result = RelationValidator().validate(
        _payload(*ids, relation_type="cooccurrence"),
        known_record_ids=ids,
    )
    assert not result.proposals
    assert "cooccurrence" in result.issues[0]

    result = RelationValidator().validate(
        _payload(*ids, evidence=()),
        known_record_ids=ids,
    )
    assert not result.proposals
    assert "evidence" in result.issues[0]

    conflict = {
        "catalog_record_ids": list(ids),
        "relations": [
            {**_payload(*ids)["relations"][0], "relation_type": "parent"},
            {
                **_payload(*ids)["relations"][0],
                "from_record_id": ids[1],
                "to_record_id": ids[0],
                "relation_type": "related",
            },
        ],
    }
    result = RelationValidator().validate(conflict, known_record_ids=ids)
    assert len(result.proposals) == 1
    assert "conflicting" in result.issues[0]


def test_submission_validates_catalog_endpoints_and_persists_candidates():
    catalog = Catalog()
    hair, eyes = _hits(catalog)
    with TemporaryDirectory() as directory:
        overlay = RelationOverlay(Path(directory) / "relation-overlay.sqlite", record_exists=catalog.has_record)
        result = submit_relation_payload(
            _payload(hair.record_id, eyes.record_id),
            catalog=catalog,
            overlay=overlay,
            model="test-model",
        )
        assert result.proposals[0].status == "candidate"
        assert overlay.list(status="candidate")[0].proposal_id == result.proposals[0].proposal_id

        invalid = submit_relation_payload(
            {"catalog_record_ids": ["missing"], "relations": []},
            catalog=catalog,
            overlay=overlay,
        )
        assert not invalid.proposals
        assert "unknown" in invalid.issues[0]


def test_prompt_workflow_finishes_before_relation_submission():
    catalog = Catalog()
    assert "relation_analyzer" not in inspect.signature(run_authoring_workflow).parameters
    result = run_authoring_workflow(_brief(), catalog=catalog)
    assert result.catalog_hits
    assert not hasattr(result, "relation_analysis")
    assert result.output.positive

    payload = _payload(*(hit.record_id for hit in result.catalog_hits[:2]))
    with TemporaryDirectory() as directory:
        overlay = RelationOverlay(Path(directory) / "relation-overlay.sqlite", record_exists=catalog.has_record)
        submission = submit_relation_payload(payload, catalog=catalog, overlay=overlay)
        output = attach_relation_submission(result.output, submission)
        assert output.positive == result.output.positive
        assert any(item.startswith("relation_candidate:") for item in output.assumptions)
        assert not any("relation_candidate" in item for item in output.notes)


def test_submission_accepts_json_text_as_the_script_protocol():
    catalog = Catalog()
    hair, eyes = _hits(catalog)
    with TemporaryDirectory() as directory:
        overlay = RelationOverlay(Path(directory) / "relation-overlay.sqlite", record_exists=catalog.has_record)
        result = submit_relation_payload(
            json.dumps(_payload(hair.record_id, eyes.record_id)),
            catalog=catalog,
            overlay=overlay,
        )
        assert len(result.proposals) == 1
