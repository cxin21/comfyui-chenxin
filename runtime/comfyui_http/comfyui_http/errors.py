"""Typed exception hierarchy for the neutral ComfyUI HTTP transport."""

from __future__ import annotations


class ComfyUIHTTPError(RuntimeError):
    """Base class for all neutral-transport errors."""


class ComfyUIConnectionError(ComfyUIHTTPError):
    """The transport could not reach ComfyUI at all (DNS, TCP, refused)."""


class ComfyUIInvalidResponseError(ComfyUIHTTPError):
    """ComfyUI replied with a status, payload shape, or Content-Type we cannot use."""


class ComfyUIIntegrityError(ComfyUIHTTPError):
    """A downloaded artifact failed its expected SHA-256."""


class ComfyUITimeoutError(ComfyUIHTTPError):
    """``wait_for_success`` exceeded the supplied timeout without completion."""
