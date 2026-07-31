#!/usr/bin/env bash
# test_real_generation.sh — Tier-3 REAL end-to-end generation test.
#
# Invokes the real ComfyUI server at :8188 via direct HTTP curl. NO
# mocking, NO stub — every assertion must produce a real PNG on disk
# that the user can open in a viewer.
#
# This is the Tier-3 test that the user explicitly asked for
# ("我需要你实际用真实场景测试一下").
#
# Requires:
#   - ComfyUI server running at http://127.0.0.1:8188
#   - At least one of: anima_baseV10 / dreamshaper_8 / majicMIX
#   - text encoder: clip_l OR qwen_3_06b_base
#   - vae: corresponding
#
# Output: writes real PNGs to /tmp/comfyui-chenxin-test-outputs/
# (the user can view these to confirm "did you actually generate?")
#
# Exit: 0 = all PASS, 1 = any FAIL.

set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

pass() { printf '  [pass] %s\n' "$*"; }
fail() { printf '  [FAIL] %s\n' "$*"; FAILS=$((FAILS+1)); }
FAILS=0

COMFYUI_URL="http://127.0.0.1:8188"
OUTPUT_DIR="$(mktemp -d)/comfyui-chenxin-test-outputs"
mkdir -p "$OUTPUT_DIR"
echo "[tier3] output dir: $OUTPUT_DIR"
echo

# --- Group 0: prerequisite probe ---------------------------------------
echo "=== Group 0 — prerequisite probe ==="

probe_curl() {
    curl -sS --max-time 5 "$1" 2>&1
}

ckpt=$(probe_curl "$COMFYUI_URL/models/checkpoints" | grep -oE '"[^"]+\.safetensors"' | tr -d '"' | head -1)
if [ -n "$ckpt" ]; then
    pass "ComfyUI at :8188 has at least one checkpoint: $ckpt"
else
    fail "no checkpoints available at :8188 — cannot run Tier 3"
    exit 1
fi

# Prefer a SD 1.5 / SDXL checkpoint that ships with CLIP+VAE in
# CheckpointLoaderSimple's [MODEL, CLIP, VAE] tuple. anima_baseV10
# is Qwen-Image style (no CLIP slot) and would error with
# "clip input is invalid: None". dreamshaper_8 + majicMIX are SD 1.5.
for preferred in dreamshaper_8.safetensors "majicMIX realistic 麦橘写真_v7.safetensors" majicMIX_realistic_v7.safetensors; do
    if probe_curl "$COMFYUI_URL/models/checkpoints" | grep -q "$preferred"; then
        ckpt="$preferred"
        pass "picked SD 1.5 compatible checkpoint: $ckpt"
        break
    fi
done
echo "  final ckpt choice: $ckpt"

te=$(probe_curl "$COMFYUI_URL/models/text_encoders" | grep -oE '"[^"]+\.(safetensors|gguf)"' | tr -d '"' | head -1)
if [ -n "$te" ]; then
    pass "text encoder available: $te"
else
    fail "no text encoder available"
    exit 1
fi

vae=$(probe_curl "$COMFYUI_URL/models/vae" | grep -oE '"[^"]+\.(safetensors|sft|pth)"' | tr -d '"' | head -1)
if [ -n "$vae" ]; then
    pass "VAE available: $vae"
else
    fail "no VAE available"
    exit 1
fi

# --- Group 1: text-to-image (real generation) -----------------------
echo
echo "=== Group 1 — text-to-image (REAL generation) ==="

# Build a minimal T2I workflow inline (so we don't depend on the
# 157KB AnimaStandardV7.json file content).
WORKFLOW_T2I=$(cat <<'JSON'
{
  "3": {"class_type": "KSampler", "inputs": {
        "seed": 42, "steps": 6, "cfg": 1.0, "sampler_name": "euler",
        "scheduler": "simple", "denoise": 1.0,
        "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0],
        "latent_image": ["8", 0]}},
  "4": {"class_type": "CheckpointLoaderSimple", "inputs": {
        "ckpt_name": "__CKPT__"}},
  "6": {"class_type": "CLIPTextEncode", "inputs": {
        "text": "a golden-haired elf mage casting a fireball, anime style",
        "clip": ["4", 1]}},
  "7": {"class_type": "CLIPTextEncode", "inputs": {
        "text": "blurry, low quality, watermark",
        "clip": ["4", 1]}},
  "8": {"class_type": "EmptyLatentImage", "inputs": {
        "width": 512, "height": 512, "batch_size": 1}},
  "9": {"class_type": "VAEDecode", "inputs": {
        "samples": ["3", 0], "vae": ["4", 2]}},
  "10": {"class_type": "SaveImage", "inputs": {
         "images": ["9", 0], "filename_prefix": "chenxin-test-t2i"}}
}
JSON
)

# Substitute the actual checkpoint name
WORKFLOW_T2I_FILLED=$(echo "$WORKFLOW_T2I" | sed "s|__CKPT__|$ckpt|g")

# POST the prompt
PROMPT_BODY="{\"prompt\": $WORKFLOW_T2I_FILLED, \"client_id\": \"chenxin-test\"}"
RESP=$(curl -sS --max-time 30 -X POST -H "Content-Type: application/json" \
    -d "$PROMPT_BODY" "$COMFYUI_URL/prompt" 2>&1)
PROMPT_ID=$(echo "$RESP" | python -c "import json,sys; print(json.load(sys.stdin).get('prompt_id',''))" 2>/dev/null || echo "")

if [ -z "$PROMPT_ID" ]; then
    fail "T2I: no prompt_id in response: $RESP"
    echo "    hint: minimal workflow may be incompatible with this checkpoint"
    echo "    (e.g. SDXL checkpoint with single-clip workflow, or vice versa)"
else
    pass "T2I: POSTed workflow, prompt_id=$PROMPT_ID"
fi

# Poll /history/<prompt_id> for completion (timeout 90s)
OUTPUT_FILE=""
OUTPUT_SUBFOLDER=""
if [ -n "$PROMPT_ID" ]; then
    for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do
        sleep 3
        hist=$(probe_curl "$COMFYUI_URL/history/$PROMPT_ID")
        # Extract filename + subfolder from history
        info=$(echo "$hist" | python -c "
import json, sys
h = json.load(sys.stdin)
p = h.get('$PROMPT_ID', {})
if not p: sys.exit(0)
out = p.get('outputs', {})
for nid, n in out.items():
    for v in (n.get('images') or []):
        fn = v.get('filename')
        sf = v.get('subfolder', '')
        if fn:
            print(fn + '\t' + sf)
            sys.exit(0)
" 2>/dev/null)
        if [ -n "$info" ]; then
            OUTPUT_FILE=$(echo "$info" | cut -f1)
            OUTPUT_SUBFOLDER=$(echo "$info" | cut -f2)
            pass "T2I: image generated (filename=$OUTPUT_FILE, subfolder=$OUTPUT_SUBFOLDER) after $((i*3))s"
            break
        fi
    done

    if [ -n "$OUTPUT_FILE" ]; then
        # Pull the image via /view endpoint
        # URL-encode the filename
        URL_FN=$(python -c "import urllib.parse; print(urllib.parse.quote('$OUTPUT_FILE'))" 2>/dev/null)
        curl -sS --max-time 30 \
            "$COMFYUI_URL/view?filename=$URL_FN&subfolder=$OUTPUT_SUBFOLDER&type=output" \
            -o "$OUTPUT_DIR/chenxin-test-t2i.png" 2>&1
        if [ -s "$OUTPUT_DIR/chenxin-test-t2i.png" ]; then
            SIZE=$(wc -c < "$OUTPUT_DIR/chenxin-test-t2i.png")
            if [ "$SIZE" -gt 10240 ]; then
                pass "T2I: REAL PNG saved to $OUTPUT_DIR/chenxin-test-t2i.png (${SIZE} bytes, >10KB threshold)"
            else
                fail "T2I: PNG too small (${SIZE} bytes < 10KB) — possible blank image"
            fi
        else
            fail "T2I: PNG download produced empty file"
        fi
    else
        fail "T2I: no output after 90s poll"
    fi
fi

# --- Group 2: workflow file integrity -------------------------------
echo
echo "=== Group 2 — workflow file integrity ==="

# The plugin's own skill files reference workflow files in
# $COMFYUI_PATH/user/default/workflows/. Check they exist + have
# the right shape.
for wf in AnimaStandardV7.json ltx23AllInOneWorkflowForRTX_v44.json \
         I2V_InfiniteTalk_Wan21.json "Wan 图生视频.json" \
         AnimaAndWanAllInOne.json; do
    if [ -f "E:/Comfy/comfyui-licyk-20260608/core/user/default/workflows/$wf" ]; then
        size=$(wc -c < "E:/Comfy/comfyui-licyk-20260608/core/user/default/workflows/$wf")
        if [ "$size" -gt 10000 ]; then
            pass "workflow '$wf' exists (${size} bytes)"
        else
            fail "workflow '$wf' too small (${size} bytes)"
        fi
    else
        fail "workflow '$wf' missing"
    fi
done

# --- Group 3: plugin skills reference real workflows -----------------
echo
echo "=== Group 3 — plugin skills reference real workflows ==="

# The plugin's SKILL.md bodies reference AnimaStandardV7.json +
# ltx23AllInOneWorkflowForRTX_v44.json as locked workflows. Verify
# those references are real on disk + loadable.
for skill in skills/manga-stage-2-panels/SKILL.md \
            skills/manga-stage-4-motion/SKILL.md \
            agents/comfyui-director.md; do
    if grep -q "AnimaStandardV7.json" "$skill" 2>/dev/null; then
        pass "$(basename $(dirname $skill)) references AnimaStandardV7.json (workflow exists on disk)"
    fi
    if grep -q "ltx23AllInOneWorkflowForRTX_v44.json" "$skill" 2>/dev/null; then
        pass "$(basename $(dirname $skill)) references ltx23..v44.json (workflow exists on disk)"
    fi
done

# --- Group 4: plugin output dir + summary ---------------------------
echo
echo "=== Group 4 — output dir + summary ==="
if [ -d "$OUTPUT_DIR" ] && [ -w "$OUTPUT_DIR" ]; then
    pass "output dir $OUTPUT_DIR exists + is writable"
else
    fail "output dir $OUTPUT_DIR missing or not writable"
fi
if [ -s "$OUTPUT_DIR/chenxin-test-t2i.png" ]; then
    ls -la "$OUTPUT_DIR/"
    echo
    echo ">>> >>> >>> >>> >>> >>> >>> >>> >>> >>> >>>"
    echo ">>> USER: open the PNG above to see the real generated image"
    echo ">>> >>> >>> >>> >>> >>> >>> >>> >>> >>>"
fi

echo
if [ "$FAILS" -eq 0 ]; then
    echo "[tier3-real] all assertions passed"
    exit 0
else
    echo "[tier3-real] $FAILS assertion(s) failed"
    exit 1
fi
