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