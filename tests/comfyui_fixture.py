#!/usr/bin/env python3
# comfyui_fixture.py — Tier-2 ComfyUI HTTP fixture for test_auto_launch_real.sh.
#
# A stdlib http.server that responds to GET /system_stats with a fixed
# JSON payload. Stops when the parent process closes the connection
# (the test sends SIGTERM after each sub-test).
#
# Port: taken from sys.argv[1] (default 8188).
# Mode: "ok" (default) | "flaky" (returns 503 to first /system_stats,
#        then 200 on retry — tests timeout/retry paths) | "dead" (no
#        response at all — tests port-bind timeout).
#
# Exit: 0 on clean shutdown, 1 on port-bind failure.

import sys
import time
import json
import threading
import signal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8188
MODE = sys.argv[2] if len(sys.argv) > 2 else "ok"
START_TIME = time.time()

# "flaky" mode: first /system_stats returns 503, subsequent return 200.
flaky_state = {"hit_count": 0}


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/system_stats":
            self.send_response(404)
            self.end_headers()
            return
        if MODE == "dead":
            # Hold the connection open then close — simulates a
            # server that accepts TCP but never responds.
            time.sleep(60)
            return
        if MODE == "flaky":
            flaky_state["hit_count"] += 1
            if flaky_state["hit_count"] == 1:
                self.send_response(503)
                self.end_headers()
                return
        body = json.dumps({
            "status": "ok",
            "system": {"comfyui_version": "fixture-0.0.1"},
            "devices": [{"name": "fixture-gpu", "vram_total": 8589934592}],
            "uptime_s": int(time.time() - START_TIME),
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args, **kwargs):
        # Silent. The test asserts on stdout / exit code, not logs.
        pass


def main():
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    except OSError as e:
        print(f"[fixture] bind {PORT} failed: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"[fixture] listening on 127.0.0.1:{PORT} (mode={MODE})", flush=True)

    def stop(*_):
        print("[fixture] shutting down", flush=True)
        # Use server.shutdown in a thread to avoid blocking the main
        # thread (which is the one serving requests).
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    server.serve_forever()
    print("[fixture] exited cleanly", flush=True)
    sys.exit(0)


if __name__ == "__main__":
    main()
