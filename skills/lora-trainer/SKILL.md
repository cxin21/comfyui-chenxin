---
name: lora-trainer
description: "Anima LoRA 璁粌缂栨帓 (v2.2) 鈥?鍗曡矾寰勶細gazingstars123/Anima-Standalone-Trainer 鐙珛 venv銆?GB VRAM 鍙嬪ソ锛屾棤闇€ ComfyUI 鍦ㄧ嚎銆侫lso load prompt-forge first for VRAM/recipe context."
version: 2.3.0
author: Claude Code
triggers:
  - "璁粌 LoRA"
  - "璁?LoRA"
  - "璁?Anima LoRA"
  - "train LoRA"
  - "lora training"
  - "璁鑹?
  - "璁満鏅?
allowed-tools: Bash, Read, Write, "mcp__comfyui-mcp__*"
---

# Lora Trainer 鈥?Anima LoRA 璁粌缂栨帓 (v2.3, ported)

> **Plugin path**: `skills/lora-trainer/SKILL.md`
> **Upstream**: L5 application skill. Load `prompt-forge` (L4) first for VRAM/recipe context 鈥?> this skill targets Anima 1.0 (~2B Cosmos DiT) so VRAM/quant choices from
> `hardware/8gb.json` directly affect training defaults.

## 1. 宸ュ叿姒傝

| 缁村害 | 鍊?|
|------|-----|
| **宸ュ叿** | [gazingstars123/Anima-Standalone-Trainer](https://github.com/gazingstars123/Anima-Standalone-Trainer) |
| **璺緞** | `E:/Comfy/Anima-Standalone-Trainer` |
| **venv** | `E:/Comfy/Anima-Standalone-Trainer/venv`锛圥ython 3.12 + torch 2.7 + CUDA 12.8锛?|
| **鍏ュ彛鑴氭湰** | `skills/lora-trainer/scripts/train-anima-standalone.sh` |
| **璁粌鍏ュ彛** | `accelerate launch anima_train_network.py --config_file <toml>` |
| **VRAM** | < 6GB锛圓nima 灏忔ā鍨?+ fused QKV + TP/SP 浼樺寲锛?|
| **ComfyUI 渚濊禆** | **涓嶉渶瑕?*锛堢嫭绔?venv锛?|
| **閰嶇疆鏂瑰紡** | toml 鏂囦欢锛堣缁?+ 鏁版嵁闆嗗垎绂伙級 |
| **Web UI** | `training-ui/start_training_ui_anima.bat` 鈫?`http://localhost:3000` |

## 2. 瑙﹀彂璇?
```
"璁粌 LoRA" / "璁?LoRA" / "train LoRA" / "lora training" / "璁?Anima LoRA" / "璁鑹? / "璁満鏅?
```

## 3. 蹇呴渶妯″瀷

| 妯″瀷 | 璺緞 | 澶у皬 |
|------|------|------|
| DiT | `E:/Comfy/comfyui-licyk-20260608/core/models/checkpoints/anima_baseV10.safetensors` | 4.18GB |
| Qwen3 TE | `E:/Comfy/comfyui-licyk-20260608/core/models/text_encoders/qwen_3_06b_base.safetensors` | 1.19GB |
| VAE | `E:/Comfy/comfyui-licyk-20260608/core/models/vae/qwen_image_vae.safetensors` | 254MB |

## 4. 鍏ュ彛鍛戒护

```bash
# 鏈€灏忓彲鐢?bash skills/lora-trainer/scripts/train-anima-standalone.sh \
  --name <name> --refs "<refs_dir>"

# 鑷畾涔夊弬鏁?+ deploy 鍒?ComfyUI loras/
bash skills/lora-trainer/scripts/train-anima-standalone.sh \
  --name ninghongye --refs "E:/Comfy/LoRA/姘稿姭-瀹佺孩澶? \
  --epochs 10 --lr 3e-5 --resolution 768,768 --deploy

# 澶嶇敤宸叉湁 toml锛堜笉瑕嗙洊锛?bash skills/lora-trainer/scripts/train-anima-standalone.sh \
  --name <name> --refs <dir> --train-toml <path> --no-auto-toml
```

瀹屾暣鍙傛暟锛歚--help` 鏌ョ湅锛堟敮鎸?`--name` / `--refs` / `--output` / `--train-toml` / `--dataset-toml` / `--epochs` / `--lr` / `--dim` / `--alpha` / `--resolution` / `--seed` / `--deploy` / `--log-dir` / `--no-auto-toml` / `--dry-run`锛夈€?
## 5. 杈撳叆鍙傛暟

| 鍙傛暟 | 蹇呴渶 | 榛樿 | 璇存槑 |
|------|------|------|------|
| `--name` | 鉁?| - | LoRA 鍚嶇О锛堢敤浜庢枃浠跺懡鍚?+ trigger word锛?|
| `--refs` | 鉁?| - | 鍙傝€冨浘鐩綍 |
| `--output` | 鉂?| `<tool>/output/<name>` | 杈撳嚭鐩綍 |
| `--train-toml` | 鉂?| `<tool>/train_<name>.toml` | 璁粌 toml锛堥粯璁よ嚜鍔ㄧ敓鎴愶級 |
| `--dataset-toml` | 鉂?| `<tool>/dataset_<name>.toml` | 鏁版嵁闆?toml锛堥粯璁よ嚜鍔ㄧ敓鎴愶級 |
| `--epochs` | 鉂?| 5 | 璁粌杞暟 |
| `--lr` | 鉂?| 5e-5 | 瀛︿範鐜?|
| `--dim` | 鉂?| 16 | LoRA dim |
| `--alpha` | 鉂?| 16 | LoRA alpha |
| `--resolution` | 鉂?| 1024,1024 | 鍒嗚鲸鐜囷紙8GB VRAM 鍙嬪ソ闄嶅埌 768,768锛?|
| `--seed` | 鉂?| 42 | 闅忔満绉嶅瓙 |
| `--deploy` | 鉂?| false | 璁粌瀹屽悗 deploy 鍒?ComfyUI loras/ |
| `--log-dir` | 鉂?| `<tool>/output/<name>/logs` | 鏃ュ織鐩綍 |
| `--no-auto-toml` | 鉂?| false | 涓嶈嚜鍔ㄧ敓鎴?toml锛堜粎鐢ㄥ凡鏈夌殑锛?|
| `--dry-run` | 鉂?| false | 鍙樉绀鸿璺戠殑鍛戒护 |

## 6. 鍓嶇疆妫€鏌?
- 鍙傝€冨浘 鈮?5 寮狅紙**瀹炴祴 2 寮犱篃鑳借窇锛屼粎渚涙祦绋嬮獙璇?*锛?0+ 寮犳墠鏄敓浜ц川閲忛棬妲涳級
- venv 瀹屾暣锛坄E:/Comfy/Anima-Standalone-Trainer/venv/Scripts/python.exe` + `accelerate.exe`锛?- 涓変釜妯″瀷鏂囦欢瀛樺湪锛圖iT + Qwen3 + VAE锛?
## 7. 鑷姩 caption

缂哄け `.txt` 鏃惰嚜鍔ㄧ敤妯℃澘鐢熸垚锛坱rigger word + 閫氱敤鎻忚堪锛夛細

```bash
"{name}, 1girl, detailed face, high quality, intricate detail"
```

鍙墜鍔ㄧ紪杈?`<image_basename>.txt` 鑷畾涔夈€?
## 8. 鑷姩 toml

缂哄け `train_<name>.toml` + `dataset_<name>.toml` 鏃惰嚜鍔ㄧ敓鎴愶細

- `train_<name>.toml`锛歚[model_arguments]` + `[dataset_arguments]` + `[training_arguments]` + `[anima_arguments]` + `[network_arguments]`
- `dataset_<name>.toml`锛歚[general]` (enable_bucket, min/max_bucket_reso) + `[[datasets]]` subsets (image_dir, num_repeats=10, caption_extension=".txt")

## 9. 娴嬭瘯鍥剧敓鎴?
5 涓満鏅紙鑷姩鐢?`templates/test-prompts.yaml`锛夛細

| 搴忓彿 | 椋庢牸 | filename_prefix |
|------|------|----------------|
| 001 | realistic | `<name>_test_001_realistic` |
| 002 | anime | `<name>_test_002_anime` |
| 003 | cinematic | `<name>_test_003_cinematic` |
| 004 | oilpaint | `<name>_test_004_oilpaint` |
| 005 | digitalart | `<name>_test_005_digitalart` |

姣忎釜 prompt 鏇挎崲 `{trigger_word}` 鍗犱綅绗︺€?
## 10. 璇勫垎涓庨獙璇?
```bash
# 鐢?manga-stage-3-review 鍐呴儴 6 缁寸畻娉曡瘎鍒?# 5 寮犲浘锛?#   鎬诲垎 鈮?7/10 鈫?lora_verified: true
#   鎬诲垎 < 7/10 鈫?璋冩暣 LoRA 寮哄害/閲嶈/鎹?trigger_word
```

**lora_verified** 蹇呴』鍐欏叆 `02_assets/<target>/04_metadata.yaml.lora_verified`銆?
## 11. 杈撳嚭 metadata 绀轰緥

```yaml
# 02_assets/<target>/04_metadata.yaml
name: ninghongye
arch: anima
trigger_word: ninghongye
lora_path: E:/Comfy/Anima-Standalone-Trainer/output/ninghongye/ning_hong_ye_v1.safetensors
lora_strength: 0.8
lora_verified: true
trained_at: 2026-07-28
training_tool: anima-standalone-trainer
training_params:
  epochs: 5
  network_dim: 16
  network_alpha: 16
  learning_rate: 5e-5
  min_refs: 5
test_generations: 02_assets/<target>/05_test_generations/
  - file: ninghongye_test_001_realistic.png
    score: 7.5
    verified: true
```

## 12. 鏋舵瀯

| 闃舵 | 璋佸仛 | 宸ュ叿 |
|------|------|------|
| 妫€鏌ュ弬鑰冨浘 | bash | `scripts/validate-refs.sh` |
| Caption 鑷姩鐢熸垚 | bash | 缂哄け鏃剁敤 trigger word 妯℃澘 |
| Toml 鑷姩鐢熸垚 | bash | 缂哄け鏃剁敓鎴愯缁?+ 鏁版嵁闆?toml |
| 璁粌 | bash | `scripts/train-anima-standalone.sh` 鈫?`accelerate-launch` |
| 娴嬭瘯鍥?| Agent | `mcp__comfyui-mcp__generate_image` 脳 5 |
| 璇勫垎 | Agent | manga-stage-3-review 鍐呴儴 6 缁寸畻娉?skill |
| deploy | bash | ⚠ TODO(P3.x) `scripts/train-anima-standalone.sh --deploy`（脚本未补） |

## 13. 宸茬煡 Caveats

1. **鏁版嵁閲忓奖鍝嶈川閲?*锛? 5 寮犲浘璁粌鏁堟灉寮憋紙浠呬緵娴佺▼楠岃瘉锛夛紱30+ 寮犲浘鎵嶈兘浜у嚭鍙敤 LoRA
2. **Web UI 涓?ComfyUI 涓嶅啿绐?*锛歐eb UI (3000) vs ComfyUI (8188) 绔彛鐙珛
3. **VRAM 鍏变韩**锛氱嫭绔?venv锛屼絾 ComfyUI 鍦ㄧ嚎鏃朵粛鍏变韩 GPU锛?GB 闄愬埗涓嬮渶娉ㄦ剰锛?4. **lora_verified 蹇呰**锛氭湭閫氳繃璇勫垎涓嶈兘杩涘叆 Stage 2
5. **caption 妯℃澘鍙敼**锛氳嚜鍔ㄧ敓鎴愮殑 .txt 鏄ā鏉匡紝澶嶆潅鍦烘櫙搴旀墜鍔ㄧ紪杈戞垨鐢?WD14 Tagger

## 14. 鐗堟湰

- **v2.3.0**锛?026-07-30锛夛細P1.1 ported 鈥?frontmatter 澹版槑 prompt-forge 涓婃父锛涜矾寰勫叏閮ㄦ敼涓?plugin 鍐?- v2.2.0锛?026-07-28锛夛細鍗曡矾寰勶紙Anima Standalone Trainer only锛夛紱鍒犻櫎璺緞 A/B/C 鐩稿叧 helper锛坄train-sd.sh`銆乣train-anima.sh`銆乣convert-anima.sh`銆乣deploy-lora.sh`銆乣path-detector.sh`锛夛紱SKILL.md 澶у箙绠€鍖?- v2.1.0锛?026-07-27锛夛細鏂板璺緞 D锛? 璺緞骞惰锛夛紱榛樿鎺ㄨ崘浠?B 鏀?D
- v2.0.0锛?026-07-27锛夛細3 璺緞骞惰锛坙ora-scripts / anima-lora-trainer / ai-toolkit-trainer锛?- v1.0.0锛堟棫锛夛細浠?lora-scripts锛坘ohya-ss锛夊崟璺緞

## 15. 鐩稿叧寮曠敤

- **涓婃父**: `skills/prompt-forge/SKILL.md`锛圠4 鈥?蹇呴』鍏堝姞杞?for VRAM/recipe锛?- 宸ュ叿锛歔gazingstars123/Anima-Standalone-Trainer](https://github.com/gazingstars123/Anima-Standalone-Trainer)
- 涓婃父: `skills/manga-orchestrator/SKILL.md` (Stage 0)
- 涓嬫父: `skills/manga-stage-2-panels/SKILL.md` (Stage 2)
- 璇勫垎鍣? manga-stage-3-review 鍐呴儴 6 缁寸畻娉?skill
