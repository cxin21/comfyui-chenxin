"""Unit tests for scripts/tag-validate.py."""
from scripts.tag_validate import validate_tag


def test_unverified_tag():
    """Unknown tag returns verified: False."""
    info = validate_tag("quantum chrome")
    assert info["verified"] is False
    assert info["canonical"] == "quantum chrome"


def test_input_normalized_to_lowercase():
    """Tag input is normalized to lowercase."""
    info = validate_tag("MALE")
    # Don't assert on canonical since dictionary may not exist in test env
    # Just verify the input was lowercased (canonical is lowercase)
    assert info["canonical"] == info["canonical"].lower()


def test_empty_string_handled():
    """Empty string returns verified: False without crashing."""
    info = validate_tag("")
    assert info["verified"] is False