"""Host-neutral MCP invocation and evidence boundary.

The runtime never depends on Claude, Codex, or a particular MCP SDK.  A host
provides one invoker callable and maps Prompt Forge logical tool names to its
actual MCP names.  This module adapts that host surface into the callable map
consumed by workflow discovery and records a bounded, hash-based receipt for
every successful call.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

from .contracts import (
    ContractError,
    canonical_json,
    content_hash,
    validate_json_compatible,
)
from .workflow_discovery import REQUIRED_WORKFLOW_TOOLS


class McpBridgeError(RuntimeError):
    """Raised when a host MCP surface cannot satisfy a runtime contract."""


ToolInvoker = Callable[[str, dict], object]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class McpBridge:
    """Adapt any host's MCP tool surface to Prompt Forge callables.

    ``invoker`` is deliberately the only host-specific dependency.  It may be
    backed by a Codex MCP call, Claude MCP call, a local MCP client, or a test
    harness.  The bridge itself never performs UI-to-API conversion and does
    not permit side effects unless explicitly enabled by the caller after the
    runtime approval/consumption boundary has been crossed.
    """

    def __init__(
        self,
        invoker: ToolInvoker,
        *,
        tool_names: Mapping[str, str] | None = None,
        host_id: str = "unknown",
        host_version: str = "unknown",
        allow_side_effects: bool = False,
    ) -> None:
        if not callable(invoker):
            raise McpBridgeError("MCP bridge invoker must be callable")
        if not isinstance(host_id, str) or not host_id.strip():
            raise McpBridgeError("MCP bridge host_id must be a non-empty string")
        if not isinstance(host_version, str) or not host_version.strip():
            raise McpBridgeError("MCP bridge host_version must be a non-empty string")
        mapping = dict(tool_names or {})
        if any(
            not isinstance(logical, str)
            or not logical.strip()
            or not isinstance(actual, str)
            or not actual.strip()
            for logical, actual in mapping.items()
        ):
            raise McpBridgeError("MCP bridge tool names must be non-empty strings")
        self._invoker = invoker
        self._tool_names = mapping
        self._host = {"id": host_id, "version": host_version}
        self._allow_side_effects = allow_side_effects is True
        self._calls: list[dict[str, Any]] = []

    @property
    def available_tools(self) -> frozenset[str]:
        """Return logical tools explicitly negotiated by the host."""
        return frozenset(self._tool_names)

    def require_tools(self, names: Iterable[str]) -> None:
        required = tuple(names)
        if any(not isinstance(name, str) or not name.strip() for name in required):
            raise McpBridgeError(
                "MCP bridge required tool names must be non-empty strings"
            )
        missing = sorted(set(required).difference(self._tool_names))
        if missing:
            raise McpBridgeError(
                "MCP bridge is missing required tools: " + ", ".join(missing)
            )

    def require_workflow_tools(self) -> None:
        self.require_tools(REQUIRED_WORKFLOW_TOOLS)

    def fixed_workflow_tools(self) -> dict[str, Callable[[dict], object]]:
        """Return the reduced MCP surface needed for bundled fixed assets."""
        required = ("validate_workflow", "check_workflow_runtime")
        self.require_tools(required)
        return {
            name: (lambda arguments, logical=name: self.call(logical, arguments))
            for name in required
        }

    def workflow_tools(self) -> dict[str, Callable[[dict], object]]:
        """Return the callable map expected by ``workflow_discovery``."""
        self.require_workflow_tools()
        return {
            name: (lambda arguments, logical=name: self.call(logical, arguments))
            for name in REQUIRED_WORKFLOW_TOOLS
        }

    def call(
        self, logical_tool: str, arguments: dict, *, side_effect: bool = False
    ) -> object:
        """Invoke one negotiated tool and retain only hash-based call evidence."""
        if not isinstance(logical_tool, str) or not logical_tool.strip():
            raise McpBridgeError("MCP bridge logical tool name is invalid")
        actual_tool = self._tool_names.get(logical_tool)
        if actual_tool is None:
            raise McpBridgeError(f"MCP bridge tool is unavailable: {logical_tool}")
        if not isinstance(arguments, dict):
            raise McpBridgeError(
                f"MCP bridge arguments for {logical_tool} must be an object"
            )
        if side_effect is True and not self._allow_side_effects:
            raise McpBridgeError(
                f"MCP bridge side effect is disabled for {logical_tool}; "
                "enable it only after runtime approval and consumption"
            )
        safe_arguments = copy.deepcopy(arguments)
        try:
            validate_json_compatible(safe_arguments, f"MCP {logical_tool} arguments")
            response = self._invoker(actual_tool, safe_arguments)
            validate_json_compatible(response, f"MCP {logical_tool} response")
        except ContractError as exc:
            raise McpBridgeError(str(exc)) from exc
        except McpBridgeError:
            raise
        except Exception as exc:
            raise McpBridgeError(
                f"MCP bridge call failed for {logical_tool}: {exc.__class__.__name__}"
            ) from exc

        self._calls.append(
            {
                "logical_tool": logical_tool,
                "actual_tool": actual_tool,
                "arguments_hash": content_hash(safe_arguments),
                "response_hash": content_hash(response),
                "side_effect": side_effect is True,
                "called_at": _utc_now(),
            }
        )
        return copy.deepcopy(response)

    def receipt(self) -> dict:
        """Return a stable, hash-addressable observation receipt."""
        calls = copy.deepcopy(self._calls)
        receipt = {
            "schema_version": "1.0",
            "receipt_type": "camera-image-mcp-bridge",
            "host": copy.deepcopy(self._host),
            "tool_names": dict(sorted(self._tool_names.items())),
            "calls": calls,
        }
        receipt["receipt_hash"] = content_hash(receipt)
        # Ensure the receipt remains safe to persist before returning it.
        canonical_json(receipt)
        return receipt
