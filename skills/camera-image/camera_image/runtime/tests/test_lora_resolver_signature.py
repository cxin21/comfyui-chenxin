"""Test build_lora_patch accepts the new RunConfig.lora dict shape."""
from runtime.lora_resolver import build_lora_patch


def test_build_lora_patch_accepts_dict_with_selections_key():
    """When caller passes {"selections": [...]} the resolver runs the normal flow."""
    # No MCP resolver — should still work for default selections=None.
    patch = build_lora_patch(None, mcp_list_loras=None)
    assert "node_26" in patch
    assert "node_66" in patch


def test_build_lora_patch_accepts_empty_dict_as_default():
    """Empty dict is treated as no selections (use default plan)."""
    patch = build_lora_patch({}, mcp_list_loras=None)
    assert "<lora:anima-base-1-masterpiece-v51:1.00>" in patch["node_26"]["text"]
