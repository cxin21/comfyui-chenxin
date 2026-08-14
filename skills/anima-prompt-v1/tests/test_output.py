import json

from anima_prompt_v1.output import PromptOutput, to_json_output, to_text_output


def test_output_protocol_has_only_copyable_channels_and_metadata_fields():
    output = PromptOutput("woman", "blurry", notes=("catalog:hit",), assumptions=("none",), advisories=("warning",))
    assert to_text_output(output).startswith("POSITIVE:\nwoman\n\nNEGATIVE:\nblurry")
    assert tuple(json.loads(to_json_output(output))) == ("positive", "negative", "notes", "assumptions", "advisories")
