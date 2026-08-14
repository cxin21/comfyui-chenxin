"""Route selection over typed facts and graph complexity."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from ..domain import Fact, PromptBrief
from .relation_graph import VisualRelationGraph

Route = Literal["tag-led", "hybrid", "natural-language-led"]
ModelVariant = Literal["base", "aesthetic", "turbo"]

QUALITY_POLICY: dict[ModelVariant, dict[str, tuple[str, ...]]] = {
    "base": {
        "positive": ("masterpiece", "best quality", "score_7"),
        "negative": ("worst quality", "low quality", "score_1", "score_2", "score_3"),
    },
    "aesthetic": {
        "positive": ("masterpiece", "best quality"),
        "negative": ("worst quality", "low quality"),
    },
    "turbo": {
        "positive": ("masterpiece", "best quality"),
        "negative": ("worst quality", "low quality"),
    },
}
_EXPLICIT_MARKERS = frozenset((
    "explicit", "nude", "nudity", "genitals", "genital", "vulva", "penis",
    "乳头", "乳房", "生殖器", "阴部", "阴茎", "阴道", "隐私部位", "裸露", "露骨", "色情", "pornographic", "nsfw",
))


@dataclass(frozen=True)
class ModelProfile:
    variant: ModelVariant
    tag_preference: str
    natural_language_preference: str
    negative_tolerance: str
    quality_tag_policy: Literal["required"]
    trigger_words: tuple[str, ...] = ()
    token_limit: int | None = None
    source: str = "default"
    evidence_level: str = "default"

    def __post_init__(self) -> None:
        if self.variant not in {"base", "aesthetic", "turbo"}:
            raise ValueError(f"invalid model variant: {self.variant!r}")
        if not isinstance(self.trigger_words, tuple):
            raise ValueError("trigger_words must be a tuple")
        if self.token_limit is not None and (isinstance(self.token_limit, bool) or self.token_limit < 1):
            raise ValueError("token_limit must be positive when provided")


@dataclass(frozen=True)
class RouteDecision:
    route: Route
    reason_codes: tuple[str, ...]
    profile: ModelProfile


def default_model_profile(
    variant: ModelVariant = "base",
    *,
    trigger_words: tuple[str, ...] = (),
    source: str = "default",
    evidence_level: str = "default",
) -> ModelProfile:
    if variant == "base":
        return ModelProfile(variant, "balanced", "balanced", "normal", "required", trigger_words, None, source, evidence_level)
    if variant == "aesthetic":
        return ModelProfile(variant, "balanced", "strong", "normal", "required", trigger_words, None, source, evidence_level)
    if variant == "turbo":
        return ModelProfile(variant, "strong", "concise", "concise", "required", trigger_words, None, source, evidence_level)
    raise ValueError(f"invalid model variant: {variant!r}")


def required_quality_terms(variant: ModelVariant) -> dict[str, tuple[str, ...]]:
    return QUALITY_POLICY[variant]


def seed_quality_policy(brief: PromptBrief, profile: ModelProfile) -> PromptBrief:
    """Materialize the mandatory Anima quality contract at the production seam."""

    facts = list(brief.facts)
    exclusions = list(brief.exclusions)
    used_ids = {fact.fact_id for fact in (*facts, *exclusions)}

    def normalized(value: str) -> str:
        return " ".join(value.lower().replace("_", " ").split())

    def has_value(items: list[Fact], value: str) -> bool:
        target = normalized(value)
        return any(normalized(fact.value) == target for fact in items)

    def new_id(channel: str, value: str) -> str:
        slug = normalized(value).replace(" ", "-")
        candidate = f"quality:{profile.variant}:{channel}:{slug}"
        suffix = 2
        while candidate in used_ids:
            candidate = f"quality:{profile.variant}:{channel}:{slug}:{suffix}"
            suffix += 1
        used_ids.add(candidate)
        return candidate

    policy = QUALITY_POLICY[profile.variant]
    for value in policy["positive"]:
        if not has_value(facts, value):
            facts.append(Fact(
                new_id("positive", value), value, "quality", "explicit", "official",
                notes=("required_by_anima_variant", f"variant:{profile.variant}"),
            ))
    for value in policy["negative"]:
        if not has_value(exclusions, value):
            exclusions.append(Fact(
                new_id("negative", value), value, "quality", "explicit", "official",
                notes=("required_by_anima_variant", f"variant:{profile.variant}"),
            ))
    if not _is_explicit_request(brief) and not has_value(facts, "safe"):
        facts.append(Fact(
            "safety:default:safe", "safe", "safety", "explicit", "official",
            notes=("required_by_anima_safety", "default_for_non_explicit_request"),
        ))
    return replace(brief, facts=tuple(facts), exclusions=tuple(exclusions))


def _is_explicit_request(brief: PromptBrief) -> bool:
    text = " ".join(
        value.lower()
        for fact in (*brief.facts, *brief.exclusions)
        for value in (fact.value, fact.user_text or "", *fact.notes)
    )
    return any(marker in text for marker in _EXPLICIT_MARKERS)


def choose_route(
    brief: PromptBrief,
    graph: VisualRelationGraph,
    *,
    requested: Route | None = None,
    profile: ModelProfile | None = None,
) -> RouteDecision:
    selected_profile = profile or default_model_profile("base")
    if requested is not None:
        if requested not in {"tag-led", "hybrid", "natural-language-led"}:
            raise ValueError(f"invalid route: {requested!r}")
        return RouteDecision(requested, ("user_requested_route",), selected_profile)

    explicit = brief.explicit_facts()
    tag_count = sum(1 for fact in explicit if fact.representation_hint == "tag")
    prose_count = sum(1 for fact in explicit if fact.representation_hint == "prose" or fact.domain in {"action", "scene", "region"})
    relation_complexity = len(graph.subject_ids()) > 1 or any(
        edge.relation in {"interacts_with", "occludes", "faces", "located_at", "performs"}
        for edge in graph.edges
    )
    if selected_profile.natural_language_preference == "strong" and prose_count:
        return RouteDecision("natural-language-led", ("profile_natural_language_preference",), selected_profile)
    if selected_profile.tag_preference == "strong" and tag_count and not prose_count:
        return RouteDecision("tag-led", ("profile_tag_preference",), selected_profile)
    if relation_complexity and prose_count:
        return RouteDecision("natural-language-led", ("typed_relation_and_prose_facts",), selected_profile)
    if tag_count >= 3 and not prose_count:
        return RouteDecision("tag-led", ("typed_tag_density",), selected_profile)
    if relation_complexity or tag_count or prose_count:
        return RouteDecision("hybrid", ("mixed_fact_representation",), selected_profile)
    return RouteDecision("hybrid", ("default_hybrid",), selected_profile)
