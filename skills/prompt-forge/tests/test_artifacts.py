from __future__ import annotations

import hashlib
import json

from prompt_forge.artifacts import create_prompt_artifact
from prompt_forge.contracts import Fact


def test_artifact_serialization_has_exact_top_level_shape_and_stable_hash() -> None:
    fact = Fact("hair", "blue hair", "user_explicit", False, "subject_1", "color")
    artifact = create_prompt_artifact(
        status="production_ready",
        task="anima",
        model="circlestone-labs/Anima",
        prompt={"positive": "blue hair", "negative": "blurry"},
        facts=(fact,),
        trace={"hair": ("hair-segment",)},
        token_report={"positive": {"actual": 2}},
        audit={"release_blocking": False},
        compression=(),
        conflict=None,
        token_count_verified=True,
        knowledge_manifest_sha256="a" * 64,
    )
    payload = artifact.to_dict()
    assert list(payload) == [
        "artifact_version",
        "status",
        "task",
        "model",
        "prompt",
        "facts",
        "trace",
        "token_report",
        "audit",
        "compression",
        "conflict",
        "sacrificed_facts",
        "token_count_verified",
        "knowledge_manifest_sha256",
        "artifact_sha256",
    ]
    unhashed = dict(payload)
    digest = unhashed.pop("artifact_sha256")
    canonical = json.dumps(
        unhashed,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert digest == hashlib.sha256(canonical).hexdigest()
    assert artifact.to_json() == json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    assert payload["sacrificed_facts"] == []

