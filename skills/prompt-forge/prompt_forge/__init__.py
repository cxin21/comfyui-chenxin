"""Three explicit model-native Prompt Forge authoring paths."""

from __future__ import annotations

from typing import NoReturn

from . import contracts as _contracts
from .artifacts import PromptArtifact

__all__ = [
    "author_anima_prompt",
    "author_h3_t2va_prompt",
    "author_h3_ref2va_prompt",
]


def author_anima_prompt(request: _contracts.AnimaAuthoringRequest) -> PromptArtifact:
    from .anima.author import author_anima_prompt as _author

    return _author(request)


def author_h3_t2va_prompt(request: _contracts.H3T2VAAuthoringRequest) -> NoReturn:
    del request
    raise NotImplementedError("H3 T2VA authoring is implemented in Task 10")


def author_h3_ref2va_prompt(request: _contracts.H3Ref2VAAuthoringRequest) -> NoReturn:
    del request
    raise NotImplementedError("H3 Ref2VA authoring is implemented in Task 11")
