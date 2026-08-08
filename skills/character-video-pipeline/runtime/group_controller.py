"""G1/G2 Fast Groups Bypasser emulation for the fixed API graph.

Fast Groups Bypasser (rgthree) is a frontend-only node not registered in
/object_info. Its effect is toggling member node modes between 0 (active)
and 4 (bypassed). This module applies that effect directly to the API graph
node modes.
"""

from __future__ import annotations

import copy
from typing import Any

MODE_ACTIVE = 0
MODE_BYPASS = 4

# Core pipeline nodes that must never be bypassed regardless of group toggles.
# These are the essential render path: sampler, saver, camera, prompts, LoRA,
# VAE decode, image processing that feeds the saver.
_PROTECTED_NODES = frozenset({
    "22", "24", "25", "26", "27", "35", "40", "48", "50", "51",
    "65", "66", "75", "76", "78", "79", "80", "83", "84", "86",
    "87", "88", "89", "96", "111", "490", "550", "557", "583", "585", "587",
})


def apply_group_modes(
    graph: dict[str, Any],
    groups_meta: dict[str, Any],
    enabled_g1: list[str] | None = None,
    enabled_g2: list[str] | None = None,
) -> dict[str, Any]:
    """Apply G1/G2 group enable/disable to the API graph.

    Protected core nodes (sampler, saver, camera, prompts, LoRA, VAE) are
    never bypassed even if their group is not in the enabled set - bypassing
    them would break the render pipeline.
    """
    patched = copy.deepcopy(graph)
    enabled_g1_set = set(enabled_g1 or [])
    enabled_g2_set = set(enabled_g2 or [])

    for controller_key, enabled_set in (("g1", enabled_g1_set), ("g2", enabled_g2_set)):
        groups = groups_meta.get(controller_key, {})
        if not isinstance(groups, dict):
            continue
        for title, member_ids in groups.items():
            if not isinstance(member_ids, list):
                continue
            mode = MODE_ACTIVE if title in enabled_set else MODE_BYPASS
            for node_id in member_ids:
                sid = str(node_id)
                if sid in _PROTECTED_NODES:
                    patched[sid]["mode"] = MODE_ACTIVE
                elif sid in patched and isinstance(patched[sid], dict):
                    patched[sid]["mode"] = mode

    return patched
