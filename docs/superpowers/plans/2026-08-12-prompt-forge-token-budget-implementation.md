# Prompt Forge Token-Budgeted Model-Native Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Prompt Forge with a source-first, model-native authoring and audit skill that produces high-quality, token-verified prompts for exactly Anima, MiniMax-H3 T2VA, and MiniMax-H3 Ref2VA.

**Architecture:** The LLM owns semantic interpretation, fact extraction, model-native writing, and tradeoff proposals. A small deterministic Python core owns immutable fact records, exact offline tokenizer counts, dynamic budget arithmetic, Anima tag lookup, lossless compression checks, structural audits, and release verification. The three public authoring paths are explicit modules, not profile dispatch. Camera skills consume only a `production_ready`, tokenizer-verified artifact whose model and task match the workflow.

**Tech Stack:** Python 3.10+, standard-library dataclasses/SQLite/JSON/hashlib, Hugging Face `tokenizers` with repository-pinned tokenizer snapshots, pytest, PowerShell installation and cache synchronization, existing ComfyUI camera runtimes.

## Global Constraints

- Implement the approved specification at `docs/superpowers/specs/2026-08-12-prompt-forge-token-budget-design.md` as the source of truth.
- Do not preserve `ForgeRequest`, `profile_id`, `dialect_id`, `draft`, `PromptPackage`, profile JSON dispatch, adapters, or any compatibility parser.
- Support exactly three public paths: `author_anima_prompt`, `author_h3_t2va_prompt`, and `author_h3_ref2va_prompt`.
- Do not add a generic model registry, grammar plugin, base profile, future-model hook, or catch-all request type.
- Do not add a local checkpoint/LoRA knowledge or override layer to Prompt Forge. Existing camera execution controls are outside this refactor and must not leak into prompt authoring artifacts.
- Use exact offline model tokenizers in production. Character count, word count, and estimated token count may never release a production artifact.
- Never truncate a token sequence or prompt tail. A protected fact may not be removed or weakened to satisfy a budget.
- The bundled Anima dictionary must be full, reproducible, source-traceable, and legally redistributable. A release build must fail closed if redistribution evidence is missing.
- Runtime authoring and audit are offline and side-effect free. Network access is permitted only in an explicit maintainer acquisition step that creates pinned source snapshots.
- Tests precede implementation in every task. First capture the expected failure, then add the minimum implementation, then run focused and broader regression tests.
- Preserve unrelated user changes. Do not stage, commit, or push unless the user explicitly authorizes it. Each task ends with a diff checkpoint instead of an automatic commit.

---

## Target Source Tree

```text
skills/prompt-forge/
├── SKILL.md
├── README.md
├── pyproject.toml
├── prompt_forge/
│   ├── __init__.py
│   ├── contracts.py
│   ├── facts.py
│   ├── token_counting.py
│   ├── budgets.py
│   ├── compression.py
│   ├── artifacts.py
│   ├── anima/
│   │   ├── __init__.py
│   │   ├── author.py
│   │   ├── audit.py
│   │   ├── dictionary.py
│   │   └── protocol.py
│   └── h3/
│       ├── __init__.py
│       ├── common.py
│       ├── t2va.py
│       └── ref2va.py
├── knowledge/
│   ├── tokenizers/
│   │   ├── anima-qwen3-0.6b/
│   │   │   ├── tokenizer.json
│   │   │   ├── tokenizer_config.json
│   │   │   └── manifest.json
│   │   └── h3-qwen3-vl/
│   │       ├── tokenizer.json
│   │       ├── tokenizer_config.json
│   │       └── manifest.json
│   └── anima/
│       ├── protocol.json
│       ├── budget-policy.json
│       ├── tags.sqlite
│       ├── manifest.json
│       └── sources.lock.json
├── scripts/
│   ├── acquire_tokenizers.py
│   ├── build_anima_dictionary.py
│   ├── verify_release.py
│   └── run_benchmarks.py
├── benchmarks/
│   ├── cases/
│   │   ├── anima.jsonl
│   │   ├── h3_t2va.jsonl
│   │   └── h3_ref2va.jsonl
│   ├── baselines/
│   │   └── prompt_metrics.json
│   └── README.md
└── tests/
    ├── conftest.py
    ├── test_public_surface.py
    ├── test_facts.py
    ├── test_token_counting.py
    ├── test_budgets.py
    ├── test_compression.py
    ├── test_anima_dictionary.py
    ├── test_anima_author.py
    ├── test_h3_t2va.py
    ├── test_h3_ref2va.py
    ├── test_artifacts.py
    ├── test_benchmarks.py
    └── test_release_verifier.py
```

Deleted without replacement:

```text
skills/prompt-forge/profiles/
skills/prompt-forge/prompt_forge/profiles.py
skills/prompt-forge/prompt_forge/forge.py
skills/prompt-forge/prompt_forge/lint.py
skills/prompt-forge/scripts/verify_profile.py
skills/prompt-forge/scripts/lint_prompt.py
```

Integration files modified:

```text
mcp_server/src/comfyui_chenxin_mcp/engine/prompt_forge.py
mcp_server/src/comfyui_chenxin_mcp/engine/validate.py
skills/camera-image/camera_image/runtime/config_schema.py
skills/camera-image/camera_image/runtime/graph_patcher.py
skills/camera-video/camera_video/runtime/config_schema.py
skills/camera-video/camera_video/runtime/graph_patcher.py
skills/camera-image/SKILL.md
skills/camera-video/SKILL.md
docs/camera-image-flow.md
docs/camera-video-flow.md
docs/MCP_BRIDGE.md
docs/architecture.md
.codex-plugin/plugin.json
scripts/install.ps1
scripts/install.sh
```

---

### Task 1: Freeze the new public surface and prove legacy concepts are absent

**Files:**

- Create: `skills/prompt-forge/tests/test_public_surface.py`
- Replace: `skills/prompt-forge/prompt_forge/contracts.py`
- Replace: `skills/prompt-forge/prompt_forge/__init__.py`
- Delete: `skills/prompt-forge/prompt_forge/profiles.py`
- Delete: `skills/prompt-forge/profiles/anima.miaomiao-harem.anima-1.5.json`
- Delete: `skills/prompt-forge/profiles/minimax-h3.base.t2va.json`
- Delete: `skills/prompt-forge/profiles/minimax-h3.base.ref2va.json`
- Delete: `skills/prompt-forge/tests/test_prompt_forge.py`

- [ ] Add an import-surface test that fails against the current generic implementation:

```python
def test_only_three_authoring_functions_are_public():
    import prompt_forge

    assert prompt_forge.__all__ == [
        "author_anima_prompt",
        "author_h3_t2va_prompt",
        "author_h3_ref2va_prompt",
    ]
    for forbidden in ("ForgeRequest", "forge_prompt", "load_profile", "PromptPackage"):
        assert not hasattr(prompt_forge, forbidden)
```

- [ ] Add a repository-shape test that scans only `skills/prompt-forge` source and rejects `profile_id`, `dialect_id`, `PromptPackage`, `adapter_manifest`, and a `profiles` directory. Exclude tests that intentionally contain forbidden literals from the scan.
- [ ] Run `python -m pytest skills/prompt-forge/tests/test_public_surface.py -q` and record the expected failure caused by the old public API.
- [ ] Replace `contracts.py` with exact, frozen dataclasses and literals:

```python
FactOrigin = Literal[
    "user_locked", "user_explicit", "necessary_inference", "agent_embellishment"
]
ArtifactStatus = Literal["production_ready", "budget_conflict", "quality_rejected"]
TaskKind = Literal["anima", "h3_t2va", "h3_ref2va"]

@dataclass(frozen=True)
class Fact:
    fact_id: str
    value: str
    origin: FactOrigin
    locked: bool
    owner: str
    dimension: str

@dataclass(frozen=True)
class AuthoredSegment:
    segment_id: str
    field: str
    text: str
    fact_ids: tuple[str, ...]
    priority: float
    adherence_risk: float
    source_confidence: float

@dataclass(frozen=True)
class Complexity:
    subjects: int
    explicit_relations: int
    complex_actions: int
    environment_clusters: int
    natural_language_bridges: int
```

- [ ] Define three non-interchangeable request types: `AnimaAuthoringRequest`, `H3T2VAAuthoringRequest`, and `H3Ref2VAAuthoringRequest`. Each carries a fact tuple and its own authored fields; only H3 requests carry duration; only Ref2VA carries ordered reference metadata and resized dimensions.
- [ ] Expose only three functions from `__init__.py`. Initial function bodies may raise `NotImplementedError` so the import contract can pass before authoring logic exists.
- [ ] Delete profile dispatch and old tests rather than translating them.
- [ ] Run the focused test and `rg -n "profile_id|dialect_id|PromptPackage|adapter_manifest" skills/prompt-forge/prompt_forge skills/prompt-forge/SKILL.md skills/prompt-forge/README.md`.
- [ ] Inspect `git diff -- skills/prompt-forge`; do not stage or commit without explicit authorization.

### Task 2: Vendor and verify the exact offline tokenizer snapshots

**Files:**

- Create: `skills/prompt-forge/pyproject.toml`
- Create: `skills/prompt-forge/prompt_forge/token_counting.py`
- Create: `skills/prompt-forge/scripts/acquire_tokenizers.py`
- Create: `skills/prompt-forge/knowledge/tokenizers/anima-qwen3-0.6b/*`
- Create: `skills/prompt-forge/knowledge/tokenizers/h3-qwen3-vl/*`
- Create: `skills/prompt-forge/tests/test_token_counting.py`
- Modify: `scripts/install.ps1`
- Modify: `scripts/install.sh`

- [ ] Add `tokenizers` as Prompt Forge's sole runtime dependency and pytest as a test extra. Use `tokenizers.Tokenizer.from_file()` so runtime never downloads models and never executes remote model code.
- [ ] Write failing tests for exact fixture counts. Fixtures must include ASCII prose, Chinese text, Anima comma-separated tags, score tags with underscores, `@artist`, H3 dialogue, H3 reference labels, and empty text. Store expected token IDs generated from the pinned upstream snapshots, not hand-estimated counts.
- [ ] Add hard-boundary tests:

```python
def test_production_count_requires_verified_snapshot(anima_counter):
    assert anima_counter.verified is True
    assert anima_counter.model_hard_limit == 32_768

def test_unknown_or_modified_snapshot_fails_closed(tmp_path):
    with pytest.raises(TokenizerIntegrityError):
        TokenCounter.load(tmp_path, expected_model="anima-qwen3-0.6b")
```

- [ ] Run the focused test and capture the import/file-not-found failure.
- [ ] Implement `TokenizerManifest` and `TokenCounter` with this exact API:

```python
class TokenCounter:
    @classmethod
    def load(cls, snapshot_dir: Path, expected_model: str) -> "TokenCounter": ...
    def encode(self, text: str) -> tuple[int, ...]: ...
    def count(self, text: str) -> int: ...
    def count_many(self, parts: Sequence[str]) -> int: ...
```

`load()` verifies every file hash, model identifier, upstream revision, tokenizer class, acquisition URL, license identifier, and hard limit from `manifest.json` before returning `verified=True`.
- [ ] Implement `acquire_tokenizers.py` as a maintainer-only, explicit network tool. It accepts exact upstream revisions, writes to a new temporary directory, verifies upstream files, records SHA-256 hashes and license evidence, and then requires a maintainer to promote the complete snapshot. It must never run from Prompt Forge authoring, camera execution, or install scripts.
- [ ] Pin the Anima tokenizer snapshot to the Qwen3-0.6B tokenizer used by ComfyUI Anima and the H3 snapshot to the tokenizer revision named by MiniMax-H3. Record hard limits `32768` and `262144` respectively.
- [ ] For H3, include the exact chat-template/special-token framing fixture and implement `count_h3_text_context()` as `encoded template tokens + encoded authored fields`; do not estimate a template overhead constant.
- [ ] Update installers to install Prompt Forge's declared dependency and copy tokenizer assets. Do not allow an install to omit either manifest or tokenizer file.
- [ ] Run `python -m pytest skills/prompt-forge/tests/test_token_counting.py -q` and verify a one-byte tokenizer mutation fails integrity validation.
- [ ] Inspect the tokenizer manifests and diff; do not stage or commit without explicit authorization.

### Task 3: Implement immutable fact ownership and traceability

**Files:**

- Create: `skills/prompt-forge/prompt_forge/facts.py`
- Create: `skills/prompt-forge/tests/test_facts.py`

- [ ] Write failing tests for unique `fact_id`, valid origins, non-empty owner/dimension/value, lock/origin consistency, segment references to known facts, and full coverage of every authored segment.
- [ ] Add tests proving that two subjects may both have `hair.color` only when their fact IDs and owners differ, and that a segment cannot silently bind one subject's property to another.
- [ ] Run the focused tests and record the missing-module failure.
- [ ] Implement:

```python
@dataclass(frozen=True)
class FactLedger:
    facts: tuple[Fact, ...]

    def get(self, fact_id: str) -> Fact: ...
    def validate_segments(self, segments: Sequence[AuthoredSegment]) -> None: ...
    def protected_fact_ids(self) -> frozenset[str]: ...
    def removable_fact_ids(self) -> frozenset[str]: ...
```

Only `agent_embellishment` facts may be removable. `locked=True` is valid only for `user_locked`; user facts remain protected even if `locked=False`.
- [ ] Add `trace_rendering(segments)` returning an immutable map from every fact ID to the segment IDs that render it. Reject missing protected facts and untraceable text segments.
- [ ] Run focused tests plus `python -m pytest skills/prompt-forge/tests/test_public_surface.py -q`.
- [ ] Inspect the diff; do not stage or commit without explicit authorization.

### Task 4: Encode dynamic budgets and field allocation as explicit policies

**Files:**

- Create: `skills/prompt-forge/prompt_forge/budgets.py`
- Create: `skills/prompt-forge/knowledge/anima/budget-policy.json`
- Create: `skills/prompt-forge/knowledge/h3-t2va-budget-policy.json`
- Create: `skills/prompt-forge/knowledge/h3-ref2va-budget-policy.json`
- Create: `skills/prompt-forge/tests/test_budgets.py`

- [ ] Write table-driven failing tests for every clamp edge and the exact approved formulas:

```python
anima_positive = clamp(
    128 + 48 * max(0, subjects - 1)
    + 24 * explicit_relations
    + 32 * complex_actions
    + 24 * environment_clusters
    + 64 * natural_language_bridges,
    128, 512,
)
anima_negative = clamp(32 + 8 * exclusion_groups, 32, 96)
h3_t2va = clamp(140 + 20 * duration + 70 * max(0, shots - 1) + dialogue_tokens, 180, 900)
h3_ref2va = clamp(420 + 90 * refs + 24 * duration + 80 * max(0, shots - 1) + dialogue_tokens, 650, 1600)
max_shots = 1 + floor((duration - 1) / 3)
```

- [ ] Add tests for `soft_limit = ceil(target * 1.25)`, `quality_limit = min(profile_cap, ceil(target * 1.60))`, integer rounding, duration bounds, illegal negative complexity, and shots exceeding `max_shots`.
- [ ] Add allocation tests for every percentage range and borrowing order in specification sections 9.1–9.4. Identity/count/locked fact buckets cannot lend budget.
- [ ] Run tests and record the missing-module failure.
- [ ] Implement separate `plan_anima_budget`, `plan_h3_t2va_budget`, and `plan_h3_ref2va_budget` functions. Shared arithmetic helpers may be private, but there must be no profile parameter or task dispatch table.
- [ ] Implement utility density exactly as `priority * adherence_risk * source_confidence * non_redundancy / token_cost`; reject zero/negative token cost instead of coercing it.
- [ ] Load three exact policy files by fixed path from their corresponding author module. Policy files contain only calibrated numbers for that task, not model selectors.
- [ ] Run the focused tests and property checks for monotonicity: adding complexity cannot reduce target budget, adding references cannot reduce Ref2VA budget, and increasing duration cannot reduce H3 budget.
- [ ] Inspect the diff; do not stage or commit without explicit authorization.

### Task 5: Build the full, reproducible Anima dictionary with a release license gate

**Files:**

- Create: `skills/prompt-forge/scripts/build_anima_dictionary.py`
- Create: `skills/prompt-forge/knowledge/anima/sources.lock.json`
- Create: `skills/prompt-forge/knowledge/anima/protocol.json`
- Create: `skills/prompt-forge/knowledge/anima/tags.sqlite`
- Create: `skills/prompt-forge/knowledge/anima/manifest.json`
- Create: `skills/prompt-forge/tests/test_anima_dictionary.py`

- [ ] Write failing builder tests using tiny source fixtures. Assert deterministic row ordering, stable IDs, canonical uniqueness, alias many-to-one behavior, precedence `official Anima rule > Gelbooru canonical > Danbooru compatibility alias`, and identical SQLite SHA-256 from identical inputs.
- [ ] Write release-gate tests proving that a source with missing license URL, missing immutable revision, `redistribution_allowed != true`, or mismatched source hash cannot contribute to a bundled database.
- [ ] Add schema tests for exactly these tables and required fields:

```sql
CREATE TABLE tags (
  tag_id INTEGER PRIMARY KEY,
  canonical TEXT NOT NULL UNIQUE,
  anima_form TEXT NOT NULL,
  category TEXT NOT NULL,
  usage_count INTEGER NOT NULL,
  source TEXT NOT NULL,
  source_version TEXT NOT NULL,
  verification_status TEXT NOT NULL
);
CREATE TABLE aliases (
  alias TEXT NOT NULL,
  tag_id INTEGER NOT NULL REFERENCES tags(tag_id),
  source TEXT NOT NULL,
  confidence REAL NOT NULL,
  PRIMARY KEY(alias, tag_id)
);
```

- [ ] Run focused tests and record the missing builder/database failure.
- [ ] Implement deterministic normalization and SQLite construction: fixed collation, explicit sorted inserts, fixed schema/user versions, no wall-clock value inside the database, `VACUUM` before hash, and manifest timestamps derived from the locked acquisition record rather than build time.
- [ ] Encode only Anima protocol transformations in `protocol.json`: ordinary tags use lowercase spaces, score tags retain required underscores, artist names require `@`, and tag ordering is quality/meta/year/safety → count → character → copyright → artist → general.
- [ ] Acquire full source snapshots separately, verify legal redistribution evidence, lock their hashes/revisions, and build the complete `tags.sqlite`. Do not use the old untraceable tag index. If redistribution cannot be established, stop this task and the release; do not ship a partial or provenance-free dictionary.
- [ ] Verify manifest fields: dictionary version, immutable source IDs, source revisions, acquisition dates, precedence, row counts, SQLite hash, builder hash, license URLs, and redistribution decision.
- [ ] Run the builder twice in separate temporary directories and assert byte-identical `tags.sqlite` and manifest content.
- [ ] Inspect database statistics and diff; do not stage or commit without explicit authorization.

### Task 6: Implement Anima dictionary retrieval and protocol audit

**Files:**

- Create: `skills/prompt-forge/prompt_forge/anima/__init__.py`
- Create: `skills/prompt-forge/prompt_forge/anima/dictionary.py`
- Create: `skills/prompt-forge/prompt_forge/anima/protocol.py`
- Create: `skills/prompt-forge/prompt_forge/anima/audit.py`
- Extend: `skills/prompt-forge/tests/test_anima_dictionary.py`

- [ ] Write failing tests for concept lookup, canonical lookup, alias lookup, category filtering, frequency ordering, confidence ordering, and a strict result limit. A query result must include source and verification status; it must never be inserted into authored output automatically.
- [ ] Add protocol audit cases for `canonical`, `known_alias`, `unverified`, `invalid_protocol_tag`, `wrong_underscore_form`, `artist_prefix_missing`, `duplicate_semantics`, and `possible_binding_conflict`.
- [ ] Add tests proving unknown ordinary semantics are advisory `unverified`, while malformed score syntax, malformed artist syntax, and reserved namespace misuse are release-blocking.
- [ ] Run focused tests and capture failures.
- [ ] Implement read-only SQLite access with URI `mode=ro`, immutable result dataclasses, parameterized SQL, and bounded candidate results.
- [ ] Implement `audit_anima_prompt(tags, natural_language, ledger)` without rewriting either field. The audit reports exact spans/tags and associated fact IDs.
- [ ] Reject use of Chinese-to-English lookup tables, prompt templates, checkpoint names, LoRA trigger words, or data from any non-Anima namespace.
- [ ] Run focused tests and a smoke query against the full bundled database.
- [ ] Inspect the diff; do not stage or commit without explicit authorization.

### Task 7: Implement lossless A+B compression and conflict reporting

**Files:**

- Create: `skills/prompt-forge/prompt_forge/compression.py`
- Create: `skills/prompt-forge/tests/test_compression.py`

- [ ] Write failing tests for all five ordered passes: exact dedupe, semantic dedupe, structure extraction, lexical compression, then deletion of agent embellishment.
- [ ] Add protected-content tests for dialogue, visible text, counts, negation, timestamps, subject/reference IDs, position, color, ownership, action result, and all user-origin facts.
- [ ] Add a sentinel test that monkeypatches token sequences so a tail slice would appear attractive; assert compression returns `budget_conflict` instead of truncating.
- [ ] Add trace preservation tests: before/after protected fact sets must be identical and `sacrificed_facts` must always be empty.
- [ ] Run focused tests and record failures.
- [ ] Implement:

```python
def compress_to_budget(
    *, segments: tuple[AuthoredSegment, ...], ledger: FactLedger,
    counter: TokenCounter, soft_limit: int, quality_limit: int,
    structure: Literal["anima", "h3_t2va", "h3_ref2va"],
) -> CompressionResult: ...
```

The `structure` literal selects only one of three private extraction routines; it is not a public model extension point.
- [ ] Every rewrite operation must record `before`, `after`, `reason`, affected fact IDs, and token saving. Semantic dedupe is allowed only when fact-ID sets are equal.
- [ ] Implement `BudgetConflict` with actual tokens, quality limit, mandatory tokens, optional tokens, excess, protected causes, and concrete user choices with estimated savings and affected fact IDs.
- [ ] Run focused tests plus fact and token tests.
- [ ] Inspect the diff; do not stage or commit without explicit authorization.

### Task 8: Implement the Anima authoring compiler and hard quality gates

**Files:**

- Create: `skills/prompt-forge/prompt_forge/anima/author.py`
- Create: `skills/prompt-forge/prompt_forge/artifacts.py`
- Create: `skills/prompt-forge/tests/test_anima_author.py`
- Create: `skills/prompt-forge/tests/test_artifacts.py`

- [ ] Write failing tests for official field order, tag-only output, hybrid output with exactly one necessary natural-language bridge, negative budget, owner binding, duplicate semantics, and malformed protocol tags.
- [ ] Add a high-complexity test where protected facts exceed `768` positive tokens. It must return a conflict artifact with no executable prompt, not a shortened prompt.
- [ ] Add artifact serialization tests for this exact top-level shape:

```json
{
  "artifact_version": 1,
  "status": "production_ready",
  "task": "anima",
  "model": "circlestone-labs/Anima",
  "prompt": {"positive": "...", "negative": "..."},
  "facts": [],
  "trace": {},
  "token_report": {},
  "audit": {},
  "compression": [],
  "conflict": null,
  "sacrificed_facts": [],
  "token_count_verified": true,
  "knowledge_manifest_sha256": "...",
  "artifact_sha256": "..."
}
```

- [ ] Run focused tests and capture missing implementation failures.
- [ ] Implement `author_anima_prompt(request)` as a deterministic compiler over LLM-authored, fact-linked sections: validate ledger → validate selected dictionary candidates → render official ordering → exact count → allocate → compress if above soft limit → hard audit → create artifact.
- [ ] The compiler chooses tag-only when all protected semantics have canonical, unambiguous tags; it permits a hybrid bridge only for complex ownership, spatial relation, causal action, or another fact that stable tags cannot bind. Tags and prose may not render the same fact ID.
- [ ] Implement hard gates for fact completeness, subject/count binding, protocol syntax, duplicate semantics, positive/negative contradiction, token verification, and both positive/negative quality limits.
- [ ] `production_ready` requires all hard gates to pass. `quality_rejected` includes audit findings and no executable prompt. `budget_conflict` includes the conflict report and no executable prompt.
- [ ] Compute `artifact_sha256` from canonical JSON excluding the `artifact_sha256` field itself. Require `sacrificed_facts == []` for every status.
- [ ] Run all Anima-focused tests.
- [ ] Inspect the diff; do not stage or commit without explicit authorization.

### Task 9: Implement MiniMax-H3 shared temporal and multimodal accounting

**Files:**

- Create: `skills/prompt-forge/prompt_forge/h3/__init__.py`
- Create: `skills/prompt-forge/prompt_forge/h3/common.py`
- Create: `skills/prompt-forge/tests/test_h3_t2va.py`
- Create: `skills/prompt-forge/tests/test_h3_ref2va.py`

- [ ] Write failing shared tests for legal timestamps, monotonically ordered shots, duration containment, max-shot density, exact dialogue preservation, reference-label syntax, and sound/music separation.
- [ ] Add visual token tests using `ceil(resized_width / 32) * ceil(resized_height / 32)` after applying H3 processor limits `65,536..16,777,216` pixels, patch size `16`, and merge size `2`.
- [ ] Add context tests for:

```python
available = 262_144 - visual_tokens - chat_template_tokens - special_tokens - runtime_safety_margin
effective = min(text_quality_limit, available)
```

Available context must never increase the text quality limit.
- [ ] Run focused tests and capture failures.
- [ ] Implement strict timestamp parsing and a `Shot` representation with start/end, opening state, actions/state transitions, camera motion, synchronous sound/dialogue, and landing state.
- [ ] Implement exact image resize accounting matching the pinned H3 processor configuration. Use integer arithmetic and tests copied from upstream processor examples.
- [ ] Implement shared hard audits: continuity, action completion, camera feasibility, audio/visual synchronization, reference existence, and final landing state.
- [ ] Run both focused test files.
- [ ] Inspect the diff; do not stage or commit without explicit authorization.

### Task 10: Implement the H3 T2VA authoring path

**Files:**

- Create: `skills/prompt-forge/prompt_forge/h3/t2va.py`
- Extend: `skills/prompt-forge/tests/test_h3_t2va.py`

- [ ] Write failing golden tests for a simple single-shot action, a legal multi-shot sequence, dialogue with synchronized lip/action cues, global soundscape extraction, non-diegetic music extraction, and an over-dense shot plan.
- [ ] Assert exact output field order and labels required by the pinned official H3 T2VA guide. Do not accept alternative legacy labels.
- [ ] Add budget cases at durations 2, 5, 10, and 15 seconds, with and without dialogue and cuts.
- [ ] Run focused tests and capture failures.
- [ ] Implement `author_h3_t2va_prompt(request)` as validate facts → validate shot plan → render official format → exact count → budget/compress → hard audit → artifact.
- [ ] Preserve exact user dialogue and visible text byte-for-byte. Count their tokens into the target formula before allocating optional visual detail.
- [ ] Reject cuts that add no new information, space, viewpoint, state, or time. Reject a shot that begins before the previous shot's landing state is established.
- [ ] Return `budget_conflict` when protected temporal content exceeds `1200` text tokens after lossless compression.
- [ ] Run the full T2VA test file and shared tests.
- [ ] Inspect the diff; do not stage or commit without explicit authorization.

### Task 11: Implement the H3 Ref2VA authoring path

**Files:**

- Create: `skills/prompt-forge/prompt_forge/h3/ref2va.py`
- Extend: `skills/prompt-forge/tests/test_h3_ref2va.py`

- [ ] Write failing golden tests for one reference, three references, stable subject definitions, explicit retention analysis, reference ownership across shots, and a reference collision.
- [ ] Assert exact output field order: `subject_definitions`, `summary`, `retention_analysis`, `detailed_description`, `overall_soundscape`, `non_diegetic_music`.
- [ ] Add tests proving stable appearance is defined once in `subject_definitions`; `retention_analysis` describes what remains tied to each reference; `detailed_description` contains only visible events and changes.
- [ ] Add budget/context cases for one and three resized images, duration boundaries, dialogue, and the `2400` quality cap.
- [ ] Run focused tests and capture failures.
- [ ] Implement `author_h3_ref2va_prompt(request)` with exact reference labels and fact ownership. Every reference use must resolve to an ordered input image and an owner in the fact ledger.
- [ ] Apply exact visual-token accounting before text planning. Reject missing resized dimensions because production context cannot be verified without them.
- [ ] Apply the official detailed-description guidance as a quality target, not a padding mandate. Additional words must survive utility-density ranking and non-redundancy audit.
- [ ] Return conflict/rejection artifacts with no executable prompt when binding, context, or quality gates fail.
- [ ] Run the full Ref2VA and shared H3 tests.
- [ ] Inspect the diff; do not stage or commit without explicit authorization.

### Task 12: Replace the MCP bridge and camera consumption contract

**Files:**

- Replace: `mcp_server/src/comfyui_chenxin_mcp/engine/prompt_forge.py`
- Modify: `mcp_server/src/comfyui_chenxin_mcp/engine/validate.py`
- Modify: `skills/camera-image/camera_image/runtime/config_schema.py`
- Modify: `skills/camera-image/camera_image/runtime/graph_patcher.py`
- Modify: `skills/camera-video/camera_video/runtime/config_schema.py`
- Modify: `skills/camera-video/camera_video/runtime/graph_patcher.py`
- Create/modify corresponding MCP, camera-image, and camera-video tests in their existing test directories.

- [ ] Write failing integration tests proving camera-image accepts only task `anima`, camera-video T2V accepts only `h3_t2va`, I2V/multi-I2V accepts only `h3_ref2va`, and every consumer rejects unverified or non-production artifacts.
- [ ] Add tests that raw `prompt`, `negative`, `evidence`, `profile_id`, `draft`, and `dialect_id` inputs are unknown fields rather than deprecated aliases.
- [ ] Add tamper tests: changing prompt text after artifact creation must invalidate the artifact content hash; changing reference count/dimensions must invalidate H3 context verification.
- [ ] Run focused tests and capture current compatibility-path failures.
- [ ] Replace the bridge with three explicit calls; do not retain `forge_prompt(profile_id=..., operation=...)`. The bridge may deserialize exact request types and serialize artifacts, but may not create prose or infer a task from strings.
- [ ] Replace camera `RunConfig` prompt fields with `prompt_artifact: dict[str, Any]`. Validate artifact version/status/task/model/token verification/content hash, then extract the already-approved prompt for graph patching.
- [ ] Keep Prompt Forge ignorant of workflow nodes, samplers, checkpoints, LoRAs, seeds, and camera runtime options. Existing camera runtime options remain owned and validated by camera skills.
- [ ] Ensure the graph patcher receives only artifact-extracted text and cannot bypass validation through another code path.
- [ ] Run all Prompt Forge, MCP, camera-image, and camera-video tests.
- [ ] Inspect the diff; do not stage or commit without explicit authorization.

### Task 13: Add regression corpora, metamorphic checks, and benchmark reporting

**Files:**

- Create: `skills/prompt-forge/benchmarks/cases/anima.jsonl`
- Create: `skills/prompt-forge/benchmarks/cases/h3_t2va.jsonl`
- Create: `skills/prompt-forge/benchmarks/cases/h3_ref2va.jsonl`
- Create: `skills/prompt-forge/benchmarks/baselines/prompt_metrics.json`
- Create: `skills/prompt-forge/benchmarks/README.md`
- Create: `skills/prompt-forge/scripts/run_benchmarks.py`
- Create: `skills/prompt-forge/tests/test_benchmarks.py`

- [ ] Create at least 30 hand-reviewed cases per path, balanced across simple, boundary, and adversarial inputs. Include multi-subject binding, counts, negation, spatial relations, exact text/dialogue, contradictory facts, maximum durations, multi-reference ownership, and intentionally over-budget cases.
- [ ] Store facts and authored segments, not copyrighted example prompts copied from third-party galleries. Every expected result must identify required facts and expected status.
- [ ] Write failing corpus-schema and determinism tests. Every case must produce byte-identical artifact JSON across two runs.
- [ ] Add metamorphic tests: reorder unrelated facts, add a duplicate segment, add removable embellishment, and vary one complexity dimension. Protected rendered facts and status must remain stable except where the changed dimension intentionally crosses a boundary.
- [ ] Implement benchmark metrics: protected-fact recall, duplicate semantic count, binding violations, token count, compression savings, rejection/conflict rate, and deterministic hash. Do not combine hard failures into a compensating total score.
- [ ] Establish baselines only after all hard gates pass. Baseline changes require a machine-readable reason and per-case diff.
- [ ] Run `python skills/prompt-forge/scripts/run_benchmarks.py --verify-baseline` and all benchmark tests.
- [ ] Inspect the corpus and diff; do not stage or commit without explicit authorization.

### Task 14: Add real-generation calibration without weakening hard gates

**Files:**

- Extend: `skills/prompt-forge/scripts/run_benchmarks.py`
- Create: `skills/prompt-forge/benchmarks/calibration.schema.json`
- Extend: `skills/prompt-forge/benchmarks/README.md`
- Modify only after evidence: the three exact budget policy JSON files.

- [ ] Add a `--prepare-generation-pairs` mode that emits paired experiment manifests for uncompressed, compressed, and expert-authored prompts using fixed seeds and identical workflow settings. It must not execute ComfyUI from Prompt Forge.
- [ ] Define calibration records for Anima fact adherence/binding/technical quality and H3 continuity/action completion/reference retention/audio synchronization/technical quality. Preserve raw artifact hashes, workflow hashes, seeds, and evaluator decisions.
- [ ] Require blind pairwise human review; automated metrics may filter obvious failures but cannot declare final visual quality.
- [ ] Plot or tabulate quality versus token count by path and complexity stratum. Select target as the shortest range within one percentage point of observed maximum fact adherence; soft limit from the 90th percentile; quality limit where added tokens stop improving adherence or begin increasing conflicts.
- [ ] Permit policy-number updates only when the calibration dataset covers Anima tag-only, Anima hybrid, H3 duration strata, H3 one-reference, and H3 three-reference cases. Never alter hard fact-preservation gates from empirical preference scores.
- [ ] Re-run deterministic benchmarks after any calibration edit and attach the per-case metric diff to the review record.
- [ ] Inspect calibration outputs and policy diff; do not stage or commit without explicit authorization.

### Task 15: Rewrite skill methodology and user-facing documentation

**Files:**

- Replace: `skills/prompt-forge/SKILL.md`
- Replace: `skills/prompt-forge/README.md`
- Modify: `skills/camera-image/SKILL.md`
- Modify: `skills/camera-video/SKILL.md`
- Modify: `docs/camera-image-flow.md`
- Modify: `docs/camera-video-flow.md`
- Modify: `docs/MCP_BRIDGE.md`
- Modify: `docs/architecture.md`
- Delete: `docs/prompt-forge-v4-refactor-design.md`

- [ ] Write documentation-lint tests or release-verifier checks that reject legacy names, generic model-extension language, checkpoint/LoRA prompt overlays, approximate token counting, and script-first creative authoring.
- [ ] Rewrite `SKILL.md` around the LLM workflow: identify one of three paths → build fact ledger → calculate complexity → retrieve Anima candidates if applicable → author model-native fields → exact token plan → A+B compression → hard audit → return artifact or explicit tradeoff request.
- [ ] State the script boundary explicitly: scripts count, retrieve, validate, build, and benchmark; they do not infer user intent, select aesthetic concepts, invent shots, or write final prose.
- [ ] Include field-order examples for Anima, H3 T2VA, and H3 Ref2VA; examples must be short original fixtures and must show fact IDs/ownership rather than opaque prose.
- [ ] Document that an unavailable or hash-invalid tokenizer permits an exploratory draft only and forces `token_count_verified=false`; camera skills must reject it.
- [ ] Document dictionary provenance, offline behavior, update procedure, license gate, and why unknown ordinary semantics are advisory while malformed reserved protocol is blocking.
- [ ] Update camera docs to accept only verified Prompt Artifacts and remove all old envelope/profile instructions.
- [ ] Run documentation release checks and inspect the diff; do not stage or commit without explicit authorization.

### Task 16: Build the release verifier, synchronize cache, and perform final acceptance

**Files:**

- Create: `skills/prompt-forge/scripts/verify_release.py`
- Create: `skills/prompt-forge/tests/test_release_verifier.py`
- Modify: `.codex-plugin/plugin.json`
- Modify: `scripts/install.ps1`
- Modify: `scripts/install.sh`

- [ ] Write failing verifier tests for: missing tokenizer asset, tokenizer hash mismatch, missing dictionary source evidence, dictionary hash mismatch, legacy files, legacy symbols, extra model profile, checkpoint/LoRA knowledge entry, non-deterministic artifact, source/cache version mismatch, and source/cache key-file mismatch.
- [ ] Implement one strict verifier that checks the approved release criteria without authoring prompts or accessing the network.
- [ ] Bump the plugin version once, after source tests pass, so the app cannot resolve the old `0.0.0` cache entry as the current build.
- [ ] Run the complete source verification:

```powershell
python -m pytest skills/prompt-forge/tests -q
python -m pytest mcp_server -q
python -m pytest skills/camera-image -q
python -m pytest skills/camera-video -q
python skills/prompt-forge/scripts/run_benchmarks.py --verify-baseline
python skills/prompt-forge/scripts/verify_release.py --source-root .
```

- [ ] Run `powershell -ExecutionPolicy Bypass -File scripts\install.ps1` to synchronize the managed plugin cache. Do not edit the cache directly.
- [ ] Locate the cache directory whose version exactly matches `.codex-plugin/plugin.json`; fail if only the old `0.0.0` directory exists.
- [ ] Run the release verifier in source-versus-cache mode. Compare SHA-256 for `SKILL.md`, all Prompt Forge Python modules, the three policy files, both tokenizer manifests/files, `tags.sqlite`, and the Anima manifest.
- [ ] Assert the active cache contains no `profiles`, `dictionary` legacy tree, `dialects`, `internals`, `PromptPackage`, or old prompt-forge scripts.
- [ ] Re-run the three public smoke cases from the installed cache and verify all artifacts are `production_ready`, exact-token verified, deterministic, and accepted by the matching camera config.
- [ ] Perform a final `git diff --check`, inspect `git status --short`, and classify any failing tests as new regression, pre-existing failure, or environment limitation. Do not claim completion while a release gate is failing.
- [ ] Do not stage, commit, or push unless the user explicitly authorizes it.

---

## Final Acceptance Matrix

| Requirement | Required evidence |
|---|---|
| No backward compatibility | Repository scan and negative integration tests reject every legacy field/path |
| No generic future-model extension | Exactly three public functions; no registry/profile dispatcher |
| Exact token budgets | Pinned tokenizer hashes, fixed token-ID fixtures, verified count in every production artifact |
| Anima full tag dictionary | Deterministic full SQLite build, provenance manifest, legal redistribution gate, row/hash verification |
| High-quality Anima prompts | Official ordering, tag/hybrid decision, binding gates, dictionary audit, paired generation calibration |
| High-quality H3 prompts | Exact official field format, temporal/reference/audio gates, paired generation calibration |
| No fact sacrifice | Protected-fact recall 100%, `sacrificed_facts` absent/empty, explicit conflict artifacts |
| No tail truncation | Sentinel test plus source scan for slicing/truncation shortcuts |
| No Prompt Forge checkpoint/LoRA layer | Artifact/schema/source scan; no adapter/checkpoint/LoRA knowledge fields |
| Offline deterministic runtime | No runtime network path; repeated artifacts and dictionary builds are byte-identical |
| Source/cache consistency | Version equality and SHA-256 equality after installer synchronization |

## Plan Self-Review Checklist

- [ ] Every approved formula and cap appears in an executable test task.
- [ ] Every quality gate has a failing test before implementation.
- [ ] Every created, modified, replaced, and deleted file is named explicitly.
- [ ] No step asks for a compatibility shim, migration, fallback profile, generic adapter, or speculative extension point.
- [ ] No implementation step relies on approximate production token counts.
- [ ] No placeholder marker, hand-waved branch, or omitted implementation decision remains.
- [ ] Public types and artifact fields are consistent across Prompt Forge, MCP, and camera consumers.
- [ ] Dictionary completeness never bypasses licensing or provenance.
- [ ] Real generation calibration changes policy numbers only; it cannot weaken hard gates.
- [ ] Git operations remain unperformed unless the user grants explicit authorization.
