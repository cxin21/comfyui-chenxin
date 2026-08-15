from __future__ import annotations

import importlib
import io
import json

import pytest


PROTOCOL_MODULES = (
    "anima_prompt_v1.cli_protocol",
    "h3_prompt.cli_protocol",
    "camera_image.cli_protocol",
    "camera_video.cli_protocol",
    "camera_multiview.cli_protocol",
)


@pytest.fixture(params=PROTOCOL_MODULES)
def protocol(request):
    return importlib.import_module(request.param)


def test_success_envelope_has_the_stable_machine_contract(protocol):
    envelope = protocol.emit_success(
        command="author",
        stage="t2va",
        result={"text": "camera pans left"},
        advisories=[{"code": "budget_near_limit", "message": "Review token budget."}],
    )

    assert envelope == {
        "ok": True,
        "command": "author",
        "stage": "t2va",
        "result": {"text": "camera pans left"},
        "errors": [],
        "advisories": [
            {"code": "budget_near_limit", "message": "Review token budget."}
        ],
    }


def test_failure_envelope_keeps_diagnostics_out_of_result(protocol):
    envelope = protocol.emit_failure(
        command="validate",
        stage="i2i-camera",
        errors=[
            {
                "code": "reference_required",
                "message": "reference_image is required",
                "details": {"field": "reference_image"},
            }
        ],
    )

    assert envelope == {
        "ok": False,
        "command": "validate",
        "stage": "i2i-camera",
        "result": None,
        "errors": [
            {
                "code": "reference_required",
                "message": "reference_image is required",
                "details": {"field": "reference_image"},
            }
        ],
        "advisories": [],
    }


def test_failure_envelope_rejects_empty_or_unstructured_errors(protocol):
    with pytest.raises(ValueError, match="at least one"):
        protocol.emit_failure("validate", None, [])

    with pytest.raises(ValueError, match="code, message, and details"):
        protocol.emit_failure(
            "validate",
            None,
            [{"message": "missing machine-readable fields"}],
        )


def test_load_json_request_accepts_exactly_one_utf8_object_source(protocol, tmp_path):
    request_path = tmp_path / "request.json"
    request_path.write_text('{"name":"测试"}', encoding="utf-8")

    assert protocol.load_json_request(request_path=request_path) == {"name": "测试"}
    assert protocol.load_json_request(stdin=io.StringIO('{"name":"stdin"}')) == {
        "name": "stdin"
    }

    with pytest.raises(protocol.RequestInputError, match="exactly one"):
        protocol.load_json_request()
    with pytest.raises(protocol.RequestInputError, match="exactly one"):
        protocol.load_json_request(
            request_path=request_path,
            stdin=io.StringIO("{}"),
        )


@pytest.mark.parametrize("payload", ("[]", "null", '"text"', "{broken"))
def test_load_json_request_rejects_non_object_or_invalid_json(protocol, payload):
    with pytest.raises(protocol.RequestInputError):
        protocol.load_json_request(stdin=io.StringIO(payload))


def test_exit_codes_depend_on_error_category_not_message_contents(protocol):
    assert protocol.exit_code_for_error("request") == 2
    assert protocol.exit_code_for_error("validation") == 3
    assert protocol.exit_code_for_error("integrity") == 4
    assert protocol.exit_code_for_error("runtime") == 5
    assert protocol.exit_code_for_error("unexpected") == 70

    with pytest.raises(ValueError, match="unknown error category"):
        protocol.exit_code_for_error("validation failed while connecting")


def test_write_json_emits_one_parseable_object_and_a_trailing_newline(protocol):
    stream = io.StringIO()
    envelope = protocol.emit_success("catalog stats", None, {"records": 42})

    protocol.write_json(envelope, stream=stream)

    rendered = stream.getvalue()
    assert rendered.endswith("\n")
    assert rendered.count("\n") == 1
    assert json.loads(rendered) == envelope
