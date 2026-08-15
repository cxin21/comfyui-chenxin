from __future__ import annotations

from ..cli import catalog_main


def main(argv: list[str] | None = None) -> int:
    """Compatibility entry point for the historical anima-catalog command."""

    return catalog_main(argv)
