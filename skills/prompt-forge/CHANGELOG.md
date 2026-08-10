# Changelog

This file tracks the evolution of prompt-forge. The skill itself
(SKILL.md) is versionless; only this file carries the timeline.

## 2026-08-10 - v3 redesign, virgin-principle rewrite (continued)

Following the first v3 release, an audit showed the v3 release
covered only 8 of v2's 15 tracked `internals/` modules. This release
completes the v3 design by replacing the remaining 5 tracked modules
plus the v2 tests, and explicitly resolving the
`package.py` / `prompt_package.py` naming/philosophy clash.

### Modules

- **`dialect.py` rewritten**: absorbed v2 `dialect_lookup.py`'s
  semantics. v3 keeps the single `registry/dialects.json` source
  (v2 split data into `dialects/index.json` + `image.json` +
  `video.json`) but inherits v2's exact-match logic verbatim:

  - case-insensitive + separator-agnostic matching
    (whitespace, dash, underscore collapse)
  - approved-alias resolution (canonical id first, then registry
    `aliases` array, then caller-supplied `extra_aliases`)
  - modality check (when caller passes `modality=`)
  - ambiguity detection (multiple canonicals matching the same
    alias -> ValueError)
  - fail-closed on unknown / empty / non-string / modality mismatch
  - registry integrity check: any forbidden-metadata key in
    `dialects.json` raises at load time

- **`evidence.py` rewritten**: absorbed v2 `intent_normalize.py`'s
  full normalisation rules. v3 keeps the typed `CreativeEvidence`
  dataclass but inherits:

  - four-quadrant normalisation (shared_known / user_known_agent_unknown
    / assistant_known_user_unknown / joint_unknown)
  - `dimensions` field routing by origin
  - `joint_unknown` experiment validation
    (hypothesis / single_variable / success_signal / failure_signal
    required, non-empty; `next_data` optional)
  - `locked_facts ∩ prohibited_expansion` overlap detection
  - `continuity_locks` also feed into the conflict check
  - forbidden metadata strip at any depth (workflow / node / hash
    / gpu / execution / mode / runtime) including camelCase and
    snake_case variants
  - `sha256` is preserved only inside `source_provenance`
  - `provenance` sanitisation
  - CLI: `python -m internals.evidence --stdin` (v2 invocation
    pattern preserved)

- **`prompt_compile.py` added (NEW)**: CLI entry that consumes
  a v3 envelope `{evidence, spec, dialect_id}` and emits a
  `PromptPackage` JSON. This is what `_mcp/engine/prompt_forge.py`
  expects to invoke via `python -m internals.prompt_compile --stdin`.
  The MCP bridge reference is no longer stale: the module exists
  and the contract is documented.

  v2's `prompt_compile.py` was the same CLI surface but took a
  v2-style draft envelope and only validated. v3 takes a
  v3-style concept-object spec and synthesises prose.

### Naming / philosophy resolution

v2 had `prompt_package.py` (validator) and `prompt_compile.py` (CLI).
v3 has `package.py` (envelope), `validate.py` (validator), and
`prompt_compile.py` (CLI). The names do not collide:

- `package.py` is the `PromptPackage` envelope (serialisation,
  forbidden-metadata strip, `to_dict` round-trip).
- `validate.py` is the P1-P5 proposition checker (visibility,
  causality, continuity, completeness, density).
- `prompt_compile.py` is the CLI.

v2's `prompt_package.py` role (validate caller-authored draft) is
**discarded** under the virgin principle: v3 abandons the
"validate-only" philosophy in favour of "project-then-validate".
The caller now authors concept objects; the projector synthesises
prose. v3's `validate.py` is the validator.

### Tests

- `internals/tests/` populated with 9 test files + conftest, 212
  tests, all passing:

  | File | Tests | Coverage |
  |---|---|---|
  | test_spec.py | 28 | concept-object instantiations, frozen enforcement |
  | test_dialect.py | 26 | alias resolution, ambiguity, modality, fail-closed |
  | test_evidence.py | 30 | normalisation, conflict detection, sanitisation, CLI |
  | test_validate.py | 20 | P1-P5 happy + sad paths |
  | test_project.py | 56 | 31 canonicals × image + video, dialect-specific renderers |
  | test_package.py | 40 | envelope serialisation, forbidden-metadata guard, negative bug fix |
  | test_compile.py | 10 | full pipeline, evidence integration |
  | test_prompt_compile.py | 15 | CLI envelope parsing, forbidden-metadata walk |

  v2 had 9 test files + conftest covering validate-draft and
  tag-lookup. v3's tests cover the v3 architecture; v2's
  `test_prompt_package.py` would be inapplicable (validate-draft is
  no longer a v3 concept).

### Validation behaviour change

- `P3-2` (gap in timeline) now fires on **gap or overlap**, not
  just overlap. v2 only checked overlap. Updated validate.py
  accordingly.

### `_compute_missing_facts` updated

- v2 walked flat string fields. v3 walks the concept-object
  structure (subjects, costumes, props, environment, atmosphere,
  lighting, frame, transitions, result states).

### Reverted / unchanged

- `registry/dialects.json` unchanged.
- `dialect.py` (v3) does NOT add the auxiliary v2 modules
  (`evaluate.py`, `style_lookup.py`, `tag_lookup.py`). Those are
  ad-hoc CLIs that prompt-forge's v3 architecture does not need.
  They live in git history (`38c6c5d`) and can be re-introduced
  if a downstream tool requires them.
- `dictionary/`, `aesthetics/`, `evals/`, `references/`, `styles/`
  v2 data directories: not replaced. v3's project-then-validate
  architecture does not depend on these data tables.

## 2026-08-10 - v3 redesign, virgin-principle rewrite (initial)

The first v3 release replaced the v2 flat-string schema with
typed concept objects (Subject / Costume / Prop / Environment /
Atmosphere / Lighting / Frame) and rewrote the per-dialect
projectors to compose those concepts into dialect-appropriate
prose. The Schema rewrite was true virgin; this release completes
the rest of the v2 module surface.