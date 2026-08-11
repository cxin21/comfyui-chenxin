"""Deep Prompt Forge implementation behind the small public interface."""
from __future__ import annotations

from .contracts import ForgeRequest, PromptArtifact
from .lint import lint_prompt
from .profiles import load_profile, validate_request


def forge_prompt(request: ForgeRequest) -> PromptArtifact:
    """Validate an authored prompt for one exact model-native profile."""
    profile = load_profile(request.profile_id)
    validate_request(profile, request)
    lint = lint_prompt(request, profile)
    if not lint["passed"]:
        details = "; ".join(item["message"] for item in lint["errors"])
        from .contracts import PromptForgeError

        raise PromptForgeError(f"prompt lint failed for {request.profile_id}: {details}")
    return PromptArtifact(
        artifact_version=1,
        profile_id=profile.profile_id,
        operation=request.operation,
        positive=request.positive.strip(),
        negative=request.negative.strip() if isinstance(request.negative, str) and request.negative.strip() else None,
        regional={key: value.strip() for key, value in request.regional.items()},
        asset_bindings=request.asset_bindings,
        constraints=request.constraints,
        assumptions=request.assumptions,
        workflow_sha256=request.workflow_sha256,
        adapter_manifest_sha256=request.adapter_manifest_sha256,
        lint=lint,
        review={"semantic_passed": None, "source": "caller-authored-review"},
        provenance=profile.sources,
    )
