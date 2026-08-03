"""Pure evidence validators for the pinned local Flux multiview workflow."""

from __future__ import annotations

import copy
import hashlib
import re
import zlib
from datetime import datetime
from pathlib import Path

from .adapters.flux_multiview import FluxAdapterError, patch_base_images
from .capabilities import report_is_fresh
from .contracts import content_hash
from .workflow_profile import ProfileError, structure_fingerprint


class MultiviewEvidenceError(ValueError):
    """Raised when Stage 2 evidence is stale, mixed, or outside the pinned policy."""


PROFILE_ID_V1 = "flux2-klein-multiview-v1"
FINGERPRINT_V1 = "fff6236efa6727ac6584d61f640a63f9602b2d07a545d216b96a870a681e6faf"
PROFILE_DIGEST_V1 = "cbed1b2969b6e0b13ae1f0b2e8d9a284371ce1aa010d6deecb3385c51be1e7f6"
PROFILE_ID = "flux2-klein-multiview-flat-v2"
WORKFLOW_ID = "prompt-forge-flat-v2"
WORKFLOW_NAME = "PromptForge-Flux2-Klein-multiview-flat-v2.json"
FINGERPRINT = "9dc2b01e2aea0b051113b187b134d007f452df6c83cfcbbd8d325eaa4c29e4da"
SOURCE_API_GRAPH_HASH = "450e6e6570a7c21aee6bc2bd32d19ac579e3460de9ccc1eca456b0dd960eec36"
PROMOTION_RECEIPT_HASH = "f6bb0a07c6d0f25723a2c139d76cb2c710a04b77ebeb2a08672ec41009564ba0"
PROFILE_DIGEST_V2 = "828f2f40c62fc7a4331fed7f3c077061971cce32629a10231012a27e306999d1"
OUTPUTS = ["image/png"]
SLOTS = {"base_image_primary": 111, "base_image_secondary": 667}
SELECTORS = {
    "base_image_primary": {"id": 111, "type": "LoadImage"},
    "base_image_secondary": {"id": 667, "type": "LoadImage"},
}
POSE_IDS = [368, 151, 152, 154, 360, 364, 148, 149, 147, 373, 150, 367]
OUTPUT_NODES = {
    "524": {"artifact_type": "CharacterAngleView", "view_label": "front_closeup"},
    "663": {"artifact_type": "CharacterAngleView", "view_label": "front"},
    "761": {"artifact_type": "CharacterAngleView", "view_label": "right_45"},
    "565": {"artifact_type": "CharacterAngleView", "view_label": "side_unknown"},
    "609": {"artifact_type": "CharacterAngleView", "view_label": "side_unknown"},
    "224": {"artifact_type": "CharacterSheet", "view_label": "sheet"},
    "338": {"artifact_type": "CharacterSheet", "view_label": "sheet"},
    "201": {"artifact_type": "CharacterSheet", "view_label": "sheet"},
}
MCP_TOOLS = {
    "load": "get_workflow",
    "convert": "get_workflow",
    "strip": "strip_workflow",
    "validate": "validate_workflow",
    "runtime": "check_workflow_runtime",
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_png_file(path: Path) -> None:
    """Validate a bounded, non-interlaced PNG including chunk CRCs and scanlines."""
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise MultiviewEvidenceError("PNG artifact bytes cannot be read") from exc
    if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise MultiviewEvidenceError("artifact bytes are not a structurally valid PNG")
    offset = 8
    chunks: list[tuple[bytes, bytes]] = []
    while offset < len(payload):
        if offset + 12 > len(payload):
            raise MultiviewEvidenceError("PNG chunk is truncated")
        length = int.from_bytes(payload[offset : offset + 4], "big")
        chunk_type = payload[offset + 4 : offset + 8]
        data_start = offset + 8
        data_end = data_start + length
        crc_end = data_end + 4
        if crc_end > len(payload):
            raise MultiviewEvidenceError("PNG chunk is truncated")
        chunk_data = payload[data_start:data_end]
        expected_crc = int.from_bytes(payload[data_end:crc_end], "big")
        if zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF != expected_crc:
            raise MultiviewEvidenceError("PNG chunk CRC is invalid")
        chunks.append((chunk_type, chunk_data))
        offset = crc_end
        if chunk_type == b"IEND":
            break
    if offset != len(payload) or not chunks or chunks[-1] != (b"IEND", b""):
        raise MultiviewEvidenceError("PNG IEND/trailing bytes are invalid")
    if chunks[0][0] != b"IHDR" or len(chunks[0][1]) != 13:
        raise MultiviewEvidenceError("PNG IHDR is invalid")
    ihdr = chunks[0][1]
    width = int.from_bytes(ihdr[0:4], "big")
    height = int.from_bytes(ihdr[4:8], "big")
    bit_depth, color_type, compression, filtering, interlace = ihdr[8:13]
    valid_depths = {
        0: {1, 2, 4, 8, 16},
        2: {8, 16},
        3: {1, 2, 4, 8},
        4: {8, 16},
        6: {8, 16},
    }
    if (
        width <= 0
        or height <= 0
        or width > 32768
        or height > 32768
        or bit_depth not in valid_depths.get(color_type, set())
        or compression != 0
        or filtering != 0
        or interlace != 0
    ):
        raise MultiviewEvidenceError("PNG IHDR uses unsupported or invalid values")
    if any(kind == b"IHDR" for kind, _ in chunks[1:]):
        raise MultiviewEvidenceError("PNG contains multiple IHDR chunks")
    compressed = b"".join(data for kind, data in chunks if kind == b"IDAT")
    if not compressed:
        raise MultiviewEvidenceError("PNG requires IDAT bytes")
    try:
        scanlines = zlib.decompress(compressed)
    except zlib.error as exc:
        raise MultiviewEvidenceError("PNG IDAT stream is invalid") from exc
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    row_bytes = (width * channels * bit_depth + 7) // 8
    if len(scanlines) != (row_bytes + 1) * height:
        raise MultiviewEvidenceError("PNG scanline length is invalid")
    if any(scanlines[row * (row_bytes + 1)] > 4 for row in range(height)):
        raise MultiviewEvidenceError("PNG scanline filter is invalid")


def validate_profile(profile: object, profile_id: object) -> None:
    if not isinstance(profile, dict):
        raise MultiviewEvidenceError("a versioned Flux workflow profile is required")
    if profile_id == PROFILE_ID_V1 and profile.get("profile_id") == profile_id:
        if profile.get("schema_version") != "1.0":
            raise MultiviewEvidenceError("a versioned Flux workflow profile is required")
        expected_fingerprint = FINGERPRINT_V1
        expected_digest = PROFILE_DIGEST_V1
    elif profile_id == PROFILE_ID and profile.get("profile_id") == profile_id:
        if profile.get("schema_version") != "2.0":
            raise MultiviewEvidenceError("a versioned Flux workflow profile is required")
        if (
            profile.get("workflow_id") != WORKFLOW_ID
            or profile.get("workflow_name") != WORKFLOW_NAME
        ):
            raise MultiviewEvidenceError("Flux v2 profile does not match the promoted flat workflow")
        if profile.get("source_api_graph_hash") != SOURCE_API_GRAPH_HASH:
            raise MultiviewEvidenceError("Flux v2 profile API graph pin is invalid")
        if profile.get("promotion_receipt_hash") != PROMOTION_RECEIPT_HASH:
            raise MultiviewEvidenceError("Flux v2 profile promotion receipt pin is invalid")
        expected_fingerprint = FINGERPRINT
        expected_digest = PROFILE_DIGEST_V2
    else:
        raise MultiviewEvidenceError(
            "character-multiview requires a trusted Flux multiview profile"
        )
    if profile.get("workflow_fingerprint") != expected_fingerprint:
        raise MultiviewEvidenceError("Flux profile fingerprint is not the verified fingerprint")
    if profile.get("runtime_classification") != "local":
        raise MultiviewEvidenceError("Flux profile must be local")
    if profile.get("expected_outputs") != OUTPUTS:
        raise MultiviewEvidenceError("Flux profile must expect only image/png")
    if profile.get("slots") != SELECTORS:
        raise MultiviewEvidenceError("Flux profile requires the verified nodes 111/667 selectors")
    if profile.get("immutable_roles") != {"pose_references": POSE_IDS}:
        raise MultiviewEvidenceError("Flux profile requires the exact immutable pose references")
    if profile.get("output_nodes") != OUTPUT_NODES:
        raise MultiviewEvidenceError("Flux profile requires the exact trusted output-node map")
    if content_hash(profile) != expected_digest:
        raise MultiviewEvidenceError("Flux profile does not match the trusted digest")


def validate_promotion_receipt(
    *,
    promotion_receipt: object,
    profile: object,
    actual_ui_workflow: object,
    converted_api_graph: object,
    stripped_api_graph: object,
    validation: object,
    runtime: object,
) -> dict:
    """Validate the immutable v2 normalization bridge and current flat evidence."""
    validate_profile(profile, PROFILE_ID)
    expected_keys = {
        "schema_version",
        "receipt_type",
        "source_run",
        "flat_workflow",
        "normalization",
        "response_digests",
        "orchestrator",
    }
    if not isinstance(promotion_receipt, dict) or set(promotion_receipt) != expected_keys:
        raise MultiviewEvidenceError("promotion receipt schema is invalid")
    if (
        promotion_receipt.get("schema_version") != "2.0"
        or promotion_receipt.get("receipt_type") != "comfyui-mcp-multiview-promotion"
        or content_hash(promotion_receipt) != profile.get("promotion_receipt_hash")
    ):
        raise MultiviewEvidenceError("promotion receipt does not match the trusted profile pin")
    if promotion_receipt.get("orchestrator") != {
        "name": "prompt-forge",
        "trust_model": "trusted-local-orchestrator",
    }:
        raise MultiviewEvidenceError("promotion receipt orchestrator provenance is not trusted")

    source_run = promotion_receipt.get("source_run")
    source_keys = {
        "prompt_id",
        "output_png_sha256",
        "embedded_api_graph_hash",
        "embedded_ui_fingerprint",
        "embedded_ui_metadata",
    }
    if not isinstance(source_run, dict) or set(source_run) != source_keys:
        raise MultiviewEvidenceError("promotion receipt source provenance is invalid")
    if not isinstance(source_run.get("prompt_id"), str) or not source_run["prompt_id"].strip():
        raise MultiviewEvidenceError("promotion receipt requires the historical prompt_id")
    if any(
        not isinstance(source_run.get(field), str)
        or not _SHA256_RE.fullmatch(source_run[field])
        for field in {"output_png_sha256", "embedded_api_graph_hash"}
    ):
        raise MultiviewEvidenceError("promotion receipt historical hashes are invalid")
    if (
        source_run.get("embedded_ui_fingerprint") is not None
        or source_run.get("embedded_ui_metadata") != "absent"
    ):
        raise MultiviewEvidenceError("promotion receipt must not infer absent embedded UI metadata")
    normalization = promotion_receipt.get("normalization")
    if (
        not isinstance(normalization, dict)
        or set(normalization)
        != {
            "policy",
            "source_embedded_api_graph_hash",
            "promoted_api_graph_hash",
            "normalized_graph_hash",
            "difference_count",
            "allowed_difference_kinds",
        }
        or normalization.get("policy")
        != "drop-meta-empty-switch-text-integral-float-v1"
        or normalization.get("source_embedded_api_graph_hash")
        != source_run["embedded_api_graph_hash"]
        or normalization.get("promoted_api_graph_hash")
        != profile.get("source_api_graph_hash")
        or not isinstance(normalization.get("normalized_graph_hash"), str)
        or not _SHA256_RE.fullmatch(normalization["normalized_graph_hash"])
        or not isinstance(normalization.get("difference_count"), int)
        or isinstance(normalization.get("difference_count"), bool)
        or normalization["difference_count"] <= 0
        or normalization.get("allowed_difference_kinds")
        != ["metadata", "empty-widget", "integral-float"]
    ):
        raise MultiviewEvidenceError("promotion receipt normalization provenance is invalid")

    try:
        actual_fingerprint = structure_fingerprint(actual_ui_workflow)
    except (ProfileError, TypeError, ValueError) as exc:
        raise MultiviewEvidenceError(f"promoted flat UI workflow is invalid: {exc}") from exc
    if not isinstance(converted_api_graph, dict) or not isinstance(stripped_api_graph, dict):
        raise MultiviewEvidenceError("promotion receipt requires flat API graph objects")
    converted_hash = content_hash(converted_api_graph)
    stripped_hash = content_hash(stripped_api_graph)
    if (
        converted_hash != profile.get("source_api_graph_hash")
        or stripped_hash != profile.get("source_api_graph_hash")
    ):
        raise MultiviewEvidenceError("promoted API graph does not match the v2 profile pin")

    flat = promotion_receipt.get("flat_workflow")
    if flat != {
        "workflow_id": profile.get("workflow_id"),
        "workflow_name": profile.get("workflow_name"),
        "ui_fingerprint": profile.get("workflow_fingerprint"),
        "source_api_graph_hash": profile.get("source_api_graph_hash"),
    }:
        raise MultiviewEvidenceError("promotion receipt flat workflow identity is invalid")
    if (
        not isinstance(actual_ui_workflow, dict)
        or actual_ui_workflow.get("id") != profile.get("workflow_id")
        or actual_fingerprint != profile.get("workflow_fingerprint")
    ):
        raise MultiviewEvidenceError("promotion receipt does not match the current flat UI workflow")

    digests = promotion_receipt.get("response_digests")
    expected_digests = {
        "ui": content_hash(actual_ui_workflow),
        "api": converted_hash,
        "strip": stripped_hash,
        "validate": content_hash(validation),
        "runtime": content_hash(runtime),
    }
    if digests != expected_digests:
        raise MultiviewEvidenceError("promotion receipt response digests do not match current evidence")
    return copy.deepcopy(promotion_receipt)


def immutable_inputs(api_graph: dict, profile: dict) -> list[dict]:
    result = []
    for node_id in profile["immutable_roles"]["pose_references"]:
        node = api_graph.get(str(node_id))
        image = node.get("inputs", {}).get("image") if isinstance(node, dict) else None
        if (
            not isinstance(node, dict)
            or node.get("class_type") != "LoadImage"
            or not isinstance(image, str)
            or not image
        ):
            raise MultiviewEvidenceError(f"immutable pose node {node_id} must be a configured LoadImage")
        result.append({"node_id": node_id, "input": "image", "value": image})
    return result


def _require_idle_local_capability(report: object, now: datetime) -> None:
    if not isinstance(report, dict) or report.get("schema_version") != "1.0":
        raise MultiviewEvidenceError("a current CapabilityReport is required")
    if not report_is_fresh(report, now):
        raise MultiviewEvidenceError("CapabilityReport must be fresh")
    try:
        classification = report["adapter"]["runtime_classification"]
        reachable = report["comfyui"]["reachable"]
        running = report["queue"]["running"]
        pending = report["queue"]["pending"]
    except (KeyError, TypeError) as exc:
        raise MultiviewEvidenceError("CapabilityReport is incomplete") from exc
    if classification != "local" or reachable is not True:
        raise MultiviewEvidenceError("execution requires a reachable local runtime")
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in (running, pending)):
        raise MultiviewEvidenceError("CapabilityReport queue counts must be non-negative integers")
    if running or pending:
        raise MultiviewEvidenceError("one ComfyUI job at a time is allowed")


def validate_mcp_preflight(
    *,
    conversion_receipt: object,
    capability_report: object,
    profile: object,
    actual_ui_workflow: object,
    api_graph: object,
    now: datetime,
    promotion_receipt: object = None,
    converted_api_graph: object = None,
) -> dict:
    profile_id = profile.get("profile_id") if isinstance(profile, dict) else None
    validate_profile(profile, profile_id)
    is_v2 = profile_id == PROFILE_ID
    if converted_api_graph is None:
        converted_api_graph = api_graph
    _require_idle_local_capability(capability_report, now)
    if not isinstance(api_graph, dict) or not isinstance(converted_api_graph, dict):
        raise MultiviewEvidenceError("MCP-converted API graph must be an object")
    if not isinstance(actual_ui_workflow, dict):
        raise MultiviewEvidenceError("saved UI workflow must be an object")
    expected_receipt_keys = {
        "schema_version", "receipt_type", "adapter", "saved_workflow",
        "conversion", "validation", "runtime", "invocations", "orchestrator",
    }
    if not isinstance(conversion_receipt, dict) or set(conversion_receipt) != expected_receipt_keys:
        raise MultiviewEvidenceError("MCP conversion receipt schema is invalid")
    if conversion_receipt.get("schema_version") != "1.0" or conversion_receipt.get("receipt_type") != "comfyui-mcp-ui-to-api":
        raise MultiviewEvidenceError("MCP conversion receipt type/version is invalid")
    adapter = conversion_receipt.get("adapter")
    if adapter != {"name": "comfyui-mcp", "version": "0.49.0", "tools": MCP_TOOLS}:
        raise MultiviewEvidenceError("MCP adapter/tool/version evidence is not trusted")
    try:
        report_adapter = capability_report["adapter"]
    except (KeyError, TypeError) as exc:
        raise MultiviewEvidenceError("CapabilityReport adapter evidence is incomplete") from exc
    if (
        not isinstance(report_adapter, dict)
        or report_adapter.get("name") != adapter["name"]
        or report_adapter.get("version") != adapter["version"]
        or report_adapter.get("runtime_classification") != "local"
    ):
        raise MultiviewEvidenceError("MCP receipt does not match CapabilityReport adapter identity")
    if conversion_receipt.get("orchestrator") != {
        "name": "prompt-forge", "trust_model": "trusted-local-orchestrator"
    }:
        raise MultiviewEvidenceError("MCP receipt orchestrator provenance is not trusted")
    try:
        actual_fingerprint = structure_fingerprint(actual_ui_workflow)
    except (ProfileError, TypeError, ValueError) as exc:
        raise MultiviewEvidenceError(f"saved UI workflow is invalid: {exc}") from exc
    saved = conversion_receipt.get("saved_workflow")
    if not isinstance(saved, dict) or set(saved) != {"workflow_id", "workflow_name", "ui_fingerprint"}:
        raise MultiviewEvidenceError("saved workflow receipt is invalid")
    if (
        not isinstance(saved.get("workflow_id"), str)
        or not saved["workflow_id"]
        or (is_v2 and saved["workflow_id"] != profile.get("workflow_id"))
        or actual_ui_workflow.get("id") != saved["workflow_id"]
        or saved.get("workflow_name") != profile.get("workflow_name")
        or saved.get("ui_fingerprint")
        != (FINGERPRINT if is_v2 else FINGERPRINT_V1)
        or actual_fingerprint != saved["ui_fingerprint"]
    ):
        raise MultiviewEvidenceError("MCP receipt does not match the exact saved UI workflow identity")
    conversion = conversion_receipt.get("conversion")
    if not isinstance(conversion, dict) or set(conversion) != {"source_ui_fingerprint", "api_graph_hash"}:
        raise MultiviewEvidenceError("MCP conversion binding is invalid")
    if conversion.get("source_ui_fingerprint") != actual_fingerprint:
        raise MultiviewEvidenceError("MCP conversion source UI fingerprint does not match")
    if (
        conversion.get("api_graph_hash") != content_hash(api_graph)
        or content_hash(converted_api_graph) != content_hash(api_graph)
    ):
        raise MultiviewEvidenceError("MCP conversion API graph hash does not match")
    validation = conversion_receipt.get("validation")
    if (
        not isinstance(validation, dict)
        or set(validation) != {"valid", "errors", "warnings"}
        or validation.get("valid") is not True
        or validation.get("errors") != []
        or not isinstance(validation.get("warnings"), list)
    ):
        raise MultiviewEvidenceError("MCP workflow validation must be valid with zero errors")
    runtime = conversion_receipt.get("runtime")
    if not isinstance(runtime, dict) or set(runtime) != {"runtime", "usesApiNodes", "apiNodes", "remoteNodes", "unknownNodes"}:
        raise MultiviewEvidenceError("MCP runtime evidence schema is invalid")
    if (
        runtime.get("runtime") != "local"
        or runtime.get("usesApiNodes") is not False
        or runtime.get("apiNodes") != []
        or runtime.get("remoteNodes") != []
        or runtime.get("unknownNodes") != []
    ):
        raise MultiviewEvidenceError("MCP runtime must be local with no remote/API nodes")
    if any(
        isinstance(node, dict)
        and isinstance(node.get("class_type"), str)
        and ("api" in node["class_type"].casefold() or "remote" in node["class_type"].casefold())
        for node in api_graph.values()
    ):
        raise MultiviewEvidenceError("MCP-converted graph contains remote/API nodes")
    if is_v2:
        validate_promotion_receipt(
            promotion_receipt=promotion_receipt,
            profile=profile,
            actual_ui_workflow=actual_ui_workflow,
            converted_api_graph=converted_api_graph,
            stripped_api_graph=api_graph,
            validation=validation,
            runtime=runtime,
        )
    workflow_ref = (
        {"filename": profile["workflow_name"]}
        if is_v2
        else {"workflow_id": saved["workflow_id"]}
    )
    expected_invocations = {
        "load": {
            "name": "get_workflow",
            "arguments": {**workflow_ref, "format": "ui"},
            "response_digest": content_hash(actual_ui_workflow),
        },
        "convert": {
            "name": "get_workflow",
            "arguments": {**workflow_ref, "format": "api"},
            "response_digest": content_hash(converted_api_graph),
        },
        "strip": {
            "name": "strip_workflow",
            "arguments": (
                {"filename": profile["workflow_name"], "format": "api"}
                if is_v2
                else {"workflow_id": saved["workflow_id"]}
            ),
            "response_digest": content_hash(api_graph),
        },
        "validate": {
            "name": "validate_workflow",
            "arguments": {"workflow": api_graph},
            "response_digest": content_hash(validation),
        },
        "runtime": {
            "name": "check_workflow_runtime",
            "arguments": {"graph" if is_v2 else "workflow": api_graph},
            "response_digest": content_hash(runtime),
        },
    }
    if conversion_receipt.get("invocations") != expected_invocations:
        raise MultiviewEvidenceError("MCP invocation receipt does not bind exact tools, arguments, and response digests")
    immutable_inputs(api_graph, profile)
    try:
        patch_base_images(api_graph, "prompt-forge/preflight.png", SLOTS)
    except FluxAdapterError as exc:
        raise MultiviewEvidenceError(f"MCP-converted API graph is invalid: {exc}") from exc
    return copy.deepcopy(conversion_receipt)


def upload_name(lineage_id: str, artifact_hash: str) -> str:
    return f"prompt-forge/{lineage_id}/character-base-{artifact_hash}.png"


def validate_upload_receipt(value: object, artifact: dict) -> dict:
    expected_keys = {
        "schema_version", "receipt_type", "adapter", "source_artifact_hash",
        "requested_filename", "stored_filename", "server_input_root",
        "server_input_path", "server_content_hash",
    }
    if not isinstance(value, dict) or set(value) != expected_keys:
        raise MultiviewEvidenceError("MCP upload receipt schema is invalid")
    if value.get("schema_version") != "1.0" or value.get("receipt_type") != "comfyui-mcp-image-upload":
        raise MultiviewEvidenceError("MCP upload receipt type/version is invalid")
    if value.get("adapter") != {"name": "comfyui-mcp", "version": "0.49.0", "tool": "upload_image"}:
        raise MultiviewEvidenceError("MCP upload receipt adapter/tool/version is invalid")
    expected_name = upload_name(artifact["lineage_id"], artifact["content_hash"])
    if (
        value.get("source_artifact_hash") != artifact["content_hash"]
        or value.get("requested_filename") != expected_name
        or value.get("stored_filename") != expected_name
        or value.get("server_content_hash") != artifact["content_hash"]
    ):
        raise MultiviewEvidenceError("MCP upload receipt is not content-derived from the Stage 1 artifact")
    root_text = value.get("server_input_root")
    path_text = value.get("server_input_path")
    if not isinstance(root_text, str) or not isinstance(path_text, str):
        raise MultiviewEvidenceError("MCP upload receipt server paths are required")
    try:
        root = Path(root_text).resolve(strict=True)
        path = Path(path_text).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise MultiviewEvidenceError("MCP upload receipt server paths must exist") from exc
    expected_path = root.joinpath(*expected_name.split("/"))
    if (
        str(root) != root_text
        or str(path) != path_text
        or not root.is_dir()
        or not path.is_file()
        or not path.is_relative_to(root)
        or path != expected_path
    ):
        raise MultiviewEvidenceError("MCP upload receipt server path is not canonical for the stored filename")
    if file_sha256(path) != artifact["content_hash"]:
        raise MultiviewEvidenceError("MCP upload server content hash does not match the source artifact")
    validate_png_file(path)
    return copy.deepcopy(value)
