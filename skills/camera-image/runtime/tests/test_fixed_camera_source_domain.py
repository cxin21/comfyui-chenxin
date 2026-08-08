import json
from pathlib import Path

from runtime.local_orchestrator import _fixed_camera_source_graph


def test_fixed_camera_source_graph_is_in_same_normalized_domain_as_fresh_workflow():
    profile = json.loads(
        (Path(__file__).parents[1] / "profiles" / "camera-anima.json").read_text(encoding="utf-8")
    )

    graph = _fixed_camera_source_graph({}, profile)

    assert graph["26"]["inputs"]["text"]
    assert graph["35"]["inputs"]["images"] == ["111", 0]
    assert graph["490"]["inputs"]["images"] == ["111", 0]
