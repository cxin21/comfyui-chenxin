"""Thin CLI for character-video-pipeline camera runs.

Single mandatory entry for image stages: `run-t2i` and `run-i2i`. Both read a
prompt-forge envelope (--envelope) and feed the validated positive/negative
into the corresponding RunConfig -> patch_graph flow. The prompt-forge gate
lives inside runtime.t2i_camera.run_t2i / runtime.i2i_camera.run_i2i (cannot
be bypassed by this CLI).

Other commands (`describe-config`, `list-loras`) are read-only inspection
and do not produce images.

Single-entry-point rule (2026-08-07): all prompt text destined for ComfyUI
must come through --envelope. There is intentionally no --positive or
--negative flag.
"""

from __future__ import annotations

import argparse
import inspect
import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config_schema import (
    CameraConfig,
    GroupsConfig,
    ImageSizeConfig,
    RunConfig,
    SamplingConfig,
    STAGES,
)
from .graph_patcher import describe_config
from .lora_resolver import (
    default_lora_plan,
    filter_anima_loras,
    parse_lora_inventory,
    render_stack_text,
)


def _parse_kv_list(value: str) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def _parse_kv_dict(value: str) -> dict:
    result = {}
    if not value:
        return result
    for pair in value.split(","):
        pair = pair.strip()
        if "=" in pair:
            k, v = pair.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def _resolve_mcp_launch() -> tuple[str, list[str]]:
    cmd = os.environ.get("CHENXIN_MCP_CMD")
    args_str = os.environ.get("CHENXIN_MCP_ARGS")
    if cmd and args_str:
        try:
            return cmd, json.loads(args_str)
        except json.JSONDecodeError:
            pass
    npx = shutil.which("npx.cmd") or shutil.which("npx")
    if not npx:
        raise RuntimeError("npx not found on PATH; install Node.js or set CHENXIN_MCP_CMD/CHENXIN_MCP_ARGS")
    comfy_url = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
    return npx, ["-y", "comfyui-mcp@0.49.8", "--full", "--comfyui-url", comfy_url]


@dataclass(frozen=True)
class ConfigFlag:
    flag: str
    dest_path: str          # dot-path into RunConfig
    applies_to: str         # "both" | "t2i" | "i2i"
    kind: str = "scalar"    # "scalar" | "csv" | "kv_csv" | "path" | "envelope"
    help: str = ""


CONFIG_FLAGS: tuple[ConfigFlag, ...] = (
    ConfigFlag("--envelope",                "envelope",                "both", kind="envelope",
               help="path to prompt-forge envelope JSON (required; prompt-forge is the only path to write positive/negative)"),
    ConfigFlag("--camera",                  "camera",                  "both", kind="kv_csv",
               help="k=v pairs: direction,elevation,distance,roll"),
    ConfigFlag("--camera-extra",            "camera_extra",            "both", kind="kv_csv",
               help="k=v pairs for any of the 13 CameraExtraConfigNode fields"),
    ConfigFlag("--lora",                    "lora",                    "both", kind="csv",
               help="comma-separated short LoRA names; CLI bridge wraps as {\"selections\": [...]} before RunConfig"),
    ConfigFlag("--g1",                      "groups.g1",               "both", kind="csv",
               help="comma-separated G1 group titles to enable"),
    ConfigFlag("--g2",                      "groups.g2",               "both", kind="csv",
               help="comma-separated G2 group titles to enable"),
    ConfigFlag("--sampling-steps-first",    "sampling.steps_first",    "both",
               help="node 50.steps (first-pass KSampler)"),
    ConfigFlag("--sampling-cfg",            "sampling.cfg",            "both",
               help="node 50.cfg"),
    ConfigFlag("--sampling-sampler",        "sampling.sampler",        "both",
               help="node 50.sampler (e.g. dpmpp_2m)"),
    ConfigFlag("--sampling-scheduler",      "sampling.scheduler",      "both",
               help="node 50.scheduler (e.g. karras)"),
    ConfigFlag("--sampling-denoise-first",  "sampling.denoise_first",  "both",
               help="node 50.denoise (t2i default 1.0; i2i forced via WORKFLOW_CONVENTIONS)"),
    ConfigFlag("--sampling-steps-refine",   "sampling.steps_refine",   "both",
               help="node 51.steps (refine KSampler)"),
    ConfigFlag("--sampling-denoise-refine", "sampling.denoise_refine", "both",
               help="node 51.denoise"),
    ConfigFlag("--seed",                    "seed",                    "both",
               help="node 65 seed (omit for random)"),
    ConfigFlag("--image-size",              "image_size",              "both", kind="kv_csv",
               help="k=v: width,height for nodes 68/71 (default 1216x832)"),
    ConfigFlag("--controlnet-image",        "controlnet_image",        "both", kind="path",
               help="path to ControlNet image (requires group ControlNet LLLite)"),
    ConfigFlag("--reference",               "reference_image",         "i2i-camera",  kind="path",
               help="reference image for img2img (run-i2i only)"),
)


def _add_flags_to_parser(parser: argparse.ArgumentParser, subcommand: str) -> None:
    """Bind every CONFIG_FLAGS entry (filtered by applies_to) to argparse."""
    for cf in CONFIG_FLAGS:
        if cf.applies_to not in ("both", subcommand):
            continue
        kwargs: dict[str, Any] = {"help": cf.help, "default": ""}
        if cf.kind == "envelope":
            kwargs["required"] = True
        parser.add_argument(cf.flag, **kwargs)


def _kwargs_to_run_config(
    *,
    envelope_json: str,
    camera: str = "",
    camera_extra: str = "",
    lora: str = "",
    g1: str = "",
    g2: str = "",
    sampling_steps_first: str = "",
    sampling_cfg: str = "",
    sampling_sampler: str = "",
    sampling_scheduler: str = "",
    sampling_denoise_first: str = "",
    sampling_steps_refine: str = "",
    sampling_denoise_refine: str = "",
    seed: str = "",
    image_size: str = "",
    controlnet_image: str = "",
    reference: str = "",
    strict: bool = False,
) -> RunConfig:
    """Build a RunConfig from CLI kwargs.

    Accepts envelope_json as the raw JSON content of a prompt-forge envelope
    (not a path); all other kwargs are flat strings that this function
    packs into the appropriate dataclass / nested dict shape.
    """
    try:
        envelope = json.loads(envelope_json)
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"envelope not valid JSON: {exc}"}), file=sys.stderr)
        sys.exit(2)

    evidence = envelope.get("evidence") or {}
    draft = envelope.get("draft") or {}
    if not draft.get("positive") or not draft.get("negative"):
        print(
            json.dumps({"error": "envelope.draft.positive and .negative are required"}),
            file=sys.stderr,
        )
        sys.exit(2)
    dialect_id = envelope.get("dialect_id") or "anima"

    # CameraConfig (kv string -> dataclass).
    camera_cfg: CameraConfig | None = None
    if camera:
        kv = _parse_kv_dict(camera)
        camera_cfg = CameraConfig(
            direction=kv.get("direction"),
            elevation=kv.get("elevation"),
            distance=kv.get("distance"),
            roll=float(kv["roll"]) if "roll" in kv else None,
        )

    # lora (csv short names -> {"selections": [...]}).
    lora_dict: dict | None = None
    if lora:
        lora_dict = {"selections": _parse_kv_list(lora)}

    # GroupsConfig (csv titles -> dataclass).
    groups_cfg: GroupsConfig | None = None
    if g1 or g2:
        groups_cfg = GroupsConfig(
            g1=_parse_kv_list(g1) or None,
            g2=_parse_kv_list(g2) or None,
        )

    # SamplingConfig (per-field string -> typed value).
    sampling_cfg_obj: SamplingConfig | None = None
    sampling_kwargs: dict[str, Any] = {}
    if sampling_steps_first:    sampling_kwargs["steps_first"]    = int(sampling_steps_first)
    if sampling_cfg:            sampling_kwargs["cfg"]            = float(sampling_cfg)
    if sampling_sampler:        sampling_kwargs["sampler"]        = sampling_sampler
    if sampling_scheduler:      sampling_kwargs["scheduler"]      = sampling_scheduler
    if sampling_denoise_first:  sampling_kwargs["denoise_first"]  = float(sampling_denoise_first)
    if sampling_steps_refine:   sampling_kwargs["steps_refine"]   = int(sampling_steps_refine)
    if sampling_denoise_refine: sampling_kwargs["denoise_refine"] = float(sampling_denoise_refine)
    if sampling_kwargs:
        sampling_cfg_obj = SamplingConfig(**sampling_kwargs)

    # ImageSizeConfig.
    image_size_cfg: ImageSizeConfig | None = None
    if image_size:
        kv = _parse_kv_dict(image_size)
        image_size_cfg = ImageSizeConfig(
            width=int(kv["width"]) if "width" in kv else None,
            height=int(kv["height"]) if "height" in kv else None,
        )

    # Seed.
    seed_val: int | None = int(seed) if seed else None

    # camera_extra is a free-form kv dict.
    camera_extra_dict = _parse_kv_dict(camera_extra) or None

    return RunConfig(
        evidence=evidence,
        draft=draft,
        dialect_id=dialect_id,
        strict_prompt=strict,
        camera=camera_cfg,
        camera_extra=camera_extra_dict,
        lora=lora_dict,
        groups=groups_cfg,
        sampling=sampling_cfg_obj,
        seed=seed_val,
        image_size=image_size_cfg,
        controlnet_image=controlnet_image or None,
        reference_image=reference or None,
    )


def cmd_describe_config(args):
    config = describe_config(args.stage)
    print(json.dumps(config, ensure_ascii=False, indent=2))
    return 0


def cmd_list_loras(args):
    from .mcp_client import McpClient
    command, server_args = _resolve_mcp_launch()
    with McpClient.from_subprocess(command, server_args, timeout=60.0) as mcp:
        raw = mcp.list_loras()
    inventory = parse_lora_inventory(raw)
    anima = filter_anima_loras(inventory)
    print(f"Available Anima LoRAs ({len(anima)}):")
    for name in anima:
        print(f"  {name}")
    print(f"\nDefault stack: {render_stack_text(default_lora_plan())}")
    return 0


def _load_envelope_json(args) -> str:
    """Read --envelope file content for passing into _kwargs_to_run_config.

    _kwargs_to_run_config expects raw JSON content, not a path.
    """
    envelope_path = Path(args.envelope)
    if not envelope_path.exists():
        print(json.dumps({"error": f"envelope file not found: {envelope_path}"}), file=sys.stderr)
        sys.exit(2)
    return envelope_path.read_text(encoding="utf-8")


def _build_run_config_kwargs(args, envelope_content: str) -> dict[str, Any]:
    """Filter argparse Namespace down to kwargs _kwargs_to_run_config accepts.

    `_kwargs_to_run_config`'s signature is the single source of truth — we
    only forward parameters it knows about (filtering out `command`, `func`,
    `output_dir`, the raw `--envelope` path, etc.).
    """
    accepted = inspect.signature(_kwargs_to_run_config).parameters
    config_kwargs: dict[str, Any] = {
        k: getattr(args, k)
        for k in accepted
        if k not in ("envelope_json", "strict") and hasattr(args, k)
    }
    config_kwargs["envelope_json"] = envelope_content
    config_kwargs["strict"] = args.strict
    return config_kwargs


def cmd_run_t2i(args):
    from .mcp_client import McpClient
    from .t2i_camera import run_t2i

    envelope_content = _load_envelope_json(args)
    config_kwargs = _build_run_config_kwargs(args, envelope_content)
    config = _kwargs_to_run_config(**config_kwargs)
    command, server_args = _resolve_mcp_launch()
    with McpClient.from_subprocess(command, server_args, timeout=600.0) as mcp:
        payload, code = run_t2i(
            mcp=mcp,
            output_dir=Path(args.output_dir),
            config=config,
            timeout=600.0,
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


def cmd_run_i2i(args):
    from .mcp_client import McpClient
    from .i2i_camera import run_i2i

    envelope_content = _load_envelope_json(args)
    config_kwargs = _build_run_config_kwargs(args, envelope_content)
    config = _kwargs_to_run_config(**config_kwargs)
    command, server_args = _resolve_mcp_launch()
    with McpClient.from_subprocess(command, server_args, timeout=600.0) as mcp:
        payload, code = run_i2i(
            mcp=mcp,
            output_dir=Path(args.output_dir),
            config=config,
            timeout=600.0,
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


def main(argv=None):
    parser = argparse.ArgumentParser(prog="character-video-pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p_dc = sub.add_parser("describe-config", help="show all configurable slots (workflow-bound)")
    p_dc.add_argument("--stage", default=STAGES.T2I, choices=[STAGES.T2I, STAGES.I2I])
    p_dc.set_defaults(func=cmd_describe_config)

    p_ll = sub.add_parser("list-loras", help="list available Anima LoRAs (read-only)")
    p_ll.set_defaults(func=cmd_list_loras)

    p_t2i = sub.add_parser(
        "run-t2i",
        help="t2i-camera: prompt-forge + RunConfig + patch_graph (single entry, prompt-forge mandatory)",
    )
    p_t2i.add_argument("--output-dir", default="outputs")
    p_t2i.add_argument("--strict", action="store_true",
                       help="abort if prompt-forge marks prompt not ready_for_review")
    _add_flags_to_parser(p_t2i, STAGES.T2I)
    p_t2i.set_defaults(func=cmd_run_t2i)

    p_i2i = sub.add_parser(
        "run-i2i",
        help="i2i-camera: prompt-forge + RunConfig + patch_graph + reference upload",
    )
    p_i2i.add_argument("--output-dir", default="outputs")
    p_i2i.add_argument("--strict", action="store_true",
                       help="abort if prompt-forge marks prompt not ready_for_review")
    _add_flags_to_parser(p_i2i, STAGES.I2I)
    p_i2i.set_defaults(func=cmd_run_i2i)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())