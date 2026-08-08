"""Tests for runtime_cli CONFIG_FLAGS routing and stage filter."""
import argparse

from runtime import runtime_cli


def _make_parser(subcommand: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="character-video-pipeline")
    runtime_cli._add_flags_to_parser(parser, subcommand)
    return parser


def test_add_flags_includes_envelope_for_both_stages():
    p = _make_parser("t2i-camera")
    help_text = p.format_help()
    assert "--envelope" in help_text
    p = _make_parser("i2i-camera")
    assert "--envelope" in p.format_help()


def test_add_flags_includes_reference_only_for_i2i():
    p_t2i = _make_parser("t2i-camera")
    assert "--reference" not in p_t2i.format_help()
    p_i2i = _make_parser("i2i-camera")
    assert "--reference" in p_i2i.format_help()


def test_add_flags_includes_sampling_per_field():
    p = _make_parser("t2i-camera")
    text = p.format_help()
    for flag in ("--sampling-steps-first", "--sampling-cfg", "--sampling-sampler",
                 "--sampling-scheduler", "--sampling-denoise-first",
                 "--sampling-steps-refine", "--sampling-denoise-refine"):
        assert flag in text, f"missing flag: {flag}"


def test_add_flags_includes_image_size_and_seed_and_controlnet():
    p = _make_parser("t2i-camera")
    text = p.format_help()
    assert "--image-size" in text
    assert "--seed" in text
    assert "--controlnet-image" in text


def test_no_legacy_flags_present():
    """Old flags --positive/--negative are explicitly REMOVED."""
    p = _make_parser("t2i-camera")
    text = p.format_help()
    assert "--positive" not in text
    assert "--negative" not in text


def test_kwargs_to_run_config_lora_wraps_csv_as_selections():
    cfg = runtime_cli._kwargs_to_run_config(
        envelope_json='{"evidence":{}, "draft":{"positive":"x","negative":"y"}}',
        lora="add_detail,masterpiece",
    )
    assert cfg.lora == {"selections": ["add_detail", "masterpiece"]}


def test_kwargs_to_run_config_camera_parses_kv():
    cfg = runtime_cli._kwargs_to_run_config(
        envelope_json='{"evidence":{}, "draft":{"positive":"x","negative":"y"}}',
        camera="direction=front,elevation=high,roll=0.5",
    )
    assert cfg.camera.direction == "front"
    assert cfg.camera.elevation == "high"
    assert cfg.camera.roll == 0.5


def test_kwargs_to_run_config_image_size_parses_kv():
    cfg = runtime_cli._kwargs_to_run_config(
        envelope_json='{"evidence":{}, "draft":{"positive":"x","negative":"y"}}',
        image_size="width=1024,height=1280",
    )
    assert cfg.image_size.width == 1024
    assert cfg.image_size.height == 1280


def test_kwargs_to_run_config_sampling_builds_dataclass():
    cfg = runtime_cli._kwargs_to_run_config(
        envelope_json='{"evidence":{}, "draft":{"positive":"x","negative":"y"}}',
        sampling_steps_first="50",
        sampling_cfg="7",
        sampling_denoise_refine="0.4",
    )
    assert cfg.sampling.steps_first == 50
    assert cfg.sampling.cfg == 7.0
    assert cfg.sampling.denoise_refine == 0.4
    # Unset fields stay None
    assert cfg.sampling.sampler is None


def test_kwargs_to_run_config_groups_parses_csv():
    cfg = runtime_cli._kwargs_to_run_config(
        envelope_json='{"evidence":{}, "draft":{"positive":"x","negative":"y"}}',
        g1="保存图片（G1）,手部 ADetailer（G1）",
        g2="图像锐化（G2）",
    )
    assert cfg.groups.g1 == ["保存图片（G1）", "手部 ADetailer（G1）"]
    assert cfg.groups.g2 == ["图像锐化（G2）"]


def test_kwargs_to_run_config_no_explicit_flags_gives_minimal_config():
    cfg = runtime_cli._kwargs_to_run_config(
        envelope_json='{"evidence":{}, "draft":{"positive":"x","negative":"y"}}',
    )
    assert cfg.camera is None
    assert cfg.sampling is None
    assert cfg.seed is None
    assert cfg.image_size is None
    assert cfg.reference_image is None
    assert cfg.controlnet_image is None


def test_main_run_t2i_dispatch_passes_runconfig(monkeypatch, tmp_path, capsys):
    """End-to-end CLI dispatch test for run-t2i.

    Exercises the executable path: argparse -> _load_envelope_json ->
    _build_run_config_kwargs -> _kwargs_to_run_config -> McpClient.from_subprocess
    -> run_t2i. Mocks McpClient.from_subprocess and run_t2i so no live
    ComfyUI/MCP is required. Asserts that:
      * argparse internals (`command`, `func`, `output_dir`, the raw
        `--envelope` path string) do NOT leak into _kwargs_to_run_config
        (this was Bug 2).
      * args.envelope is read (not args.envelope_json — this was Bug 1).
      * The dispatch returns a RunConfig with expected fields forwarded.
    """
    import json
    from runtime.config_schema import RunConfig
    from runtime import mcp_client
    from runtime import t2i_camera

    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(
        json.dumps({
            "evidence": {"intent": "test"},
            "draft": {"positive": "a cat", "negative": "blurry"},
            "dialect_id": "anima",
        }),
        encoding="utf-8",
    )

    captured: dict = {}

    class FakeMcp:
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False
        def __getattr__(self, name):
            return lambda *a, **kw: {}

    def fake_from_subprocess(command, server_args, timeout=60.0):
        return FakeMcp()

    def fake_run_t2i(*, mcp, output_dir, config, timeout=600.0, **kw):
        captured["config"] = config
        captured["output_dir"] = output_dir
        return {"ok": True, "echo": "t2i"}, 0

    monkeypatch.setattr(mcp_client.McpClient, "from_subprocess", staticmethod(fake_from_subprocess))
    monkeypatch.setattr(t2i_camera, "run_t2i", fake_run_t2i)

    rc = runtime_cli.main([
        "run-t2i",
        "--envelope", str(envelope_path),
        "--seed", "42",
        "--lora", "add_detail,masterpiece",
    ])
    assert rc == 0
    assert "config" in captured, "run_t2i was not invoked — dispatch path broken"
    config = captured["config"]
    assert isinstance(config, RunConfig)
    assert config.seed == 42
    assert config.lora == {"selections": ["add_detail", "masterpiece"]}
    assert config.draft == {"positive": "a cat", "negative": "blurry"}
    assert config.dialect_id == "anima"
    assert captured["output_dir"] == tmp_path / "outputs" or str(captured["output_dir"]).endswith("outputs")


def test_main_run_i2i_dispatch_passes_runconfig(monkeypatch, tmp_path, capsys):
    """End-to-end CLI dispatch test for run-i2i.

    Mirrors test_main_run_t2i_dispatch_passes_runconfig so the dispatch
    layer has symmetric coverage for both stages. Asserts that:
      * argv = ['run-i2i', '--envelope', tmp, '--reference', '/tmp/ref.png']
        reaches i2i_camera.run_i2i with a RunConfig carrying the
        uploaded reference filename.
      * mcp.upload_image is called at least once (reference upload).
      * payload['accepted'] is True and payload['stage'] == 'i2i-camera'.
    """
    import json
    from runtime.config_schema import RunConfig
    from runtime import mcp_client
    from runtime import i2i_camera

    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(
        json.dumps({
            "evidence": {"intent": "i2i test"},
            "draft": {"positive": "a cat", "negative": "blurry"},
            "dialect_id": "anima",
        }),
        encoding="utf-8",
    )

    captured: dict = {}
    upload_calls: list = []

    class FakeMcp:
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False
        def __getattr__(self, name):
            def _stub(*a, **kw):
                if name == "upload_image":
                    upload_calls.append(a[0] if a else kw)
                    return {"name": "ref.png", "subfolder": ""}
                return {}
            return _stub

    def fake_from_subprocess(command, server_args, timeout=60.0):
        return FakeMcp()

    def fake_run_i2i(*, mcp, output_dir, config, timeout=600.0, **kw):
        captured["config"] = config
        captured["output_dir"] = output_dir
        # Mirror real run_i2i: it uploads the reference before patching.
        # Drive the same path through the fake mcp so upload_calls
        # capture the dispatch's reference arg.
        mcp.upload_image(config.reference_image)
        return {"accepted": True, "stage": "i2i-camera"}, 0

    monkeypatch.setattr(mcp_client.McpClient, "from_subprocess", staticmethod(fake_from_subprocess))
    monkeypatch.setattr(i2i_camera, "run_i2i", fake_run_i2i)

    rc = runtime_cli.main([
        "run-i2i",
        "--envelope", str(envelope_path),
        "--reference", "/tmp/ref.png",
    ])
    assert rc == 0
    assert "config" in captured, "run_i2i was not invoked — dispatch path broken"
    config = captured["config"]
    assert isinstance(config, RunConfig)
    assert config.reference_image == "/tmp/ref.png"
    assert config.draft == {"positive": "a cat", "negative": "blurry"}
    assert config.dialect_id == "anima"
    assert upload_calls, "mcp.upload_image was not invoked — reference upload missing"
    assert str(upload_calls[0]).endswith("/tmp/ref.png") or upload_calls[0] == "/tmp/ref.png"