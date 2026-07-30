#!/usr/bin/env bash
# tests/test_applications.sh
#
# P1.1 smoke test — verifies each ported application SKILL.md:
#   1. exists at skills/<name>/SKILL.md
#   2. has valid YAML frontmatter (--- delimiters)
#   3. frontmatter has both `name:` and `description:` keys
#   4. description contains the literal substring `chenxin-core`
#      (this is the L4 routing metadata P0.3 + P1.1 contract)
#
# Exits 0 on all pass, non-zero on any failure.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SKILLS_DIR="${REPO_ROOT}/skills"

# 6 ported skills. manga-stage-1-lora is intentionally a stub (see
# application-inventory.md §1, row 2) and is checked separately below.
SKILLS=(
  "manga-orchestrator"
  "manga-stage-2-panels"
  "manga-stage-3-review"
  "manga-stage-4-motion"
  "ffmpeg-pipeline"
  "lora-trainer"
)

pass_count=0
fail_count=0
fail_names=()

for skill in "${SKILLS[@]}"; do
  file="${SKILLS_DIR}/${skill}/SKILL.md"
  line="[test] ${skill}: "

  if [[ ! -f "${file}" ]]; then
    echo "${line}FAIL — file missing: ${file}"
    fail_count=$((fail_count + 1))
    fail_names+=("${skill} (missing)")
    continue
  fi

  # Pull out the frontmatter block (between the first two --- lines).
  frontmatter=$(awk 'BEGIN{found=0} /^---$/{count++; if(count==2){exit} if(count==1)found=1; next} found{print}' "${file}")

  if [[ -z "${frontmatter}" ]]; then
    echo "${line}FAIL — no frontmatter delimited by ---"
    fail_count=$((fail_count + 1))
    fail_names+=("${skill} (no frontmatter)")
    continue
  fi

  has_name=$(echo "${frontmatter}" | grep -c '^name:[[:space:]]' || true)
  has_desc=$(echo "${frontmatter}" | grep -c '^description:' || true)

  if [[ "${has_name}" -lt 1 || "${has_desc}" -lt 1 ]]; then
    echo "${line}FAIL — missing name: and/or description: in frontmatter"
    fail_count=$((fail_count + 1))
    fail_names+=("${skill} (bad frontmatter keys)")
    continue
  fi

  # Extract the description value (single-line or YAML `|` block). We just need
  # the substring check, so concatenate the next 50 lines after `description:`.
  desc_value=$(echo "${frontmatter}" | awk '
    /^description:[[:space:]]*\|/{in_block=1; next}
    in_block && /^[[:space:]]/{print; next}
    in_block && /^[^[:space:]]/{in_block=0}
    /^description:/{ sub(/^description:[[:space:]]*/, ""); print }
  ')

  if echo "${desc_value}" | grep -q 'chenxin-core'; then
    echo "${line}PASS"
    pass_count=$((pass_count + 1))
  else
    echo "${line}FAIL — description does not mention chenxin-core"
    echo "  --- description extracted ---"
    echo "${desc_value}" | head -3 | sed 's/^/    /'
    echo "  -----------------------------"
    fail_count=$((fail_count + 1))
    fail_names+=("${skill} (no chenxin-core pointer)")
  fi
done

# Stub sanity — manga-stage-1-lora must exist as a stub but is NOT expected to
# declare chenxin-core as upstream (it's a gap placeholder).
stub_file="${SKILLS_DIR}/manga-stage-1-lora/SKILL.md"
if [[ -f "${stub_file}" ]]; then
  if grep -q 'deferred' "${stub_file}" || grep -q 'GAP' "${stub_file}"; then
    echo "[test] manga-stage-1-lora: PASS (stub present, gap documented)"
    pass_count=$((pass_count + 1))
  else
    echo "[test] manga-stage-1-lora: FAIL — stub exists but does not document the gap"
    fail_count=$((fail_count + 1))
    fail_names+=("manga-stage-1-lora (stub missing gap marker)")
  fi
else
  echo "[test] manga-stage-1-lora: FAIL — stub file missing"
  fail_count=$((fail_count + 1))
  fail_names+=("manga-stage-1-lora (stub missing)")
fi

echo ""
echo "=============================="
echo "  P1.1 smoke test result"
echo "=============================="
echo "  passed: ${pass_count}"
echo "  failed: ${fail_count}"
if [[ "${fail_count}" -gt 0 ]]; then
  echo "  failed skills:"
  for n in "${fail_names[@]}"; do
    echo "    - ${n}"
  done
  exit 1
fi
echo "  all checks passed."
exit 0
