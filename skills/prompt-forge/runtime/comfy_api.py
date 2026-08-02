"""Read-only REST access for ComfyUI capability discovery."""

import json
import urllib.request


class CapabilityError(RuntimeError):
    """Raised when ComfyUI capabilities cannot be safely established."""


class ComfyApi:
    """Narrow GET-only client for the ComfyUI discovery endpoints."""

    def __init__(self, base_url: str = "http://127.0.0.1:8188", timeout: float = 30.0):
        if not isinstance(base_url, str) or not base_url.strip():
            raise CapabilityError("ComfyUI base_url must be a non-empty string")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_json(self, path: str):
        """Fetch one JSON response without changing ComfyUI state."""
        try:
            request = urllib.request.Request(
                self.base_url + path,
                headers={"Accept": "application/json"},
                method="GET",
            )
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.load(response)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise CapabilityError(f"ComfyUI GET {path!r} failed: {exc}") from exc

    def system_stats(self):
        return self.get_json("/system_stats")

    def queue(self):
        return self.get_json("/queue")

    def object_info(self):
        return self.get_json("/object_info")

    def saved_workflows(self):
        result = self.get_json("/userdata?dir=workflows&recurse=true")
        if not isinstance(result, list) or not all(isinstance(item, str) for item in result):
            raise CapabilityError("saved workflow response must be a string list")
        return result
