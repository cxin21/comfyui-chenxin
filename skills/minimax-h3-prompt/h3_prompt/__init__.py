"""Independent MiniMax-H3 prompt skill surface."""
from .t2va import author_h3_t2va_prompt
from .ref2va import author_h3_ref2va_prompt
from .results import PromptResult

__all__ = ["author_h3_t2va_prompt", "author_h3_ref2va_prompt", "PromptResult"]
