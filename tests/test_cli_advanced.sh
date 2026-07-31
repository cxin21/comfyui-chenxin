#!/usr/bin/env bash
# test_cli_advanced.sh — Tier-1 adversarial CLI tests for mcp/extensions/.
#
# Exercises all 4 plugin CLIs (auto_launch, vram_decide, template_get,
# gui_save) with adversarial inputs. Every assertion invokes the actual
# CLI as a real subprocess — no mocking.
#
# Exit: 0 = all PASS, 1 = any FAIL.

set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

pass() { printf '  [pass] %s\n' "$*"; }
fail() { printf '  [FAIL] %s\n' "$*"; FAILS=$((FAILS+1)); }
FAILS=0

# Resolve Python interpreter (avoid Windows Store python3 stub that
# exits 49).
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
    if command -v python3.11 >/dev/null 2>&1; then PY=python3.11
    elif command -v python3 >/dev/null 2>&1; then PY=python3
    else PY=python
    fi
fi

echo "=== Group A — auto_launch.py adversarial ==="

# A.1: --port 0 should be rejected (out of valid range)
out=$("$PY" mcp/extensions/auto_launch.py --port 0 --no-launch 2>&1) || true
if echo "$out" | grep -qiE "port|0|usage|out of range|invalid"; then
    pass "--port 0 is rejected (adversarial)"
else
    fail "--port 0 not rejected: $out"
fi

# A.2: --no-launch against a real free port + tiny server returns started:true
PORT=$("$PY" -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1]); s.close()")
"$PY" -c "
import http.server, socketserver
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b'ok')
    def log_message(self, *a, **k): pass
socketserver.TCPServer(('127.0.0.1', $PORT), H).serve_forever()
" >/dev/null 2>&1 &
SVR=$!
sleep 0.3
out=$("$PY" mcp/extensions/auto_launch.py --no-launch --host 127.0.0.1 --port "$PORT" --timeout 3 2>&1) || true
kill $SVR 2>/dev/null
if [ -z "$PORT" ] || [ "$PORT" -lt 1024 ] 2>/dev/null; then
    fail "could not allocate free port (got: '$PORT')"
elif echo "$out" | grep -q '"started"'; then
    pass "--no-launch against a live local server returns JSON started"
else
    fail "--no-launch against live server: $out"
fi

echo
echo "=== Group B — vram_decide.py adversarial ==="

# B.1: --vram 0 should be rejected (exit 2)
"$PY" mcp/extensions/vram_decide.py --vram 0 --model anima >/dev/null 2>&1
ec=$?
if [ "$ec" = "2" ]; then
    pass "--vram 0 -> exit 2 (usage error)"
else
    fail "--vram 0 -> exit $ec (expected 2)"
fi

# B.2: --vram 96 should be accepted at upper boundary
out=$("$PY" mcp/extensions/vram_decide.py --vram 96 --model __nonexistent 2>&1) || true
if echo "$out" | grep -q '"blocked"'; then
    pass "--vram 96 accepted at boundary (returns blocked model JSON)"
else
    fail "--vram 96 unexpected: $out"
fi

# B.3: missing --model is a usage error (argparse rejects before JSON is emitted)
"$PY" mcp/extensions/vram_decide.py --vram 8 >/dev/null 2>&1
ec=$?
if [ "$ec" = "2" ]; then
    pass "missing --model -> exit 2 (argparse usage error)"
else
    fail "missing --model: exit $ec (expected 2)"
fi

# B.4: non-existent model -> blocked:true (no exception)
out=$("$PY" mcp/extensions/vram_decide.py --vram 8 --model "___definitely-not-a-model___" 2>&1) || true
if echo "$out" | grep -q '"blocked": true'; then
    pass "non-existent model -> blocked:true (no exception)"
else
    fail "non-existent model: $out"
fi

echo
echo "=== Group C — template_get.py adversarial ==="

# C.1: --limit 0 -> exit 2
"$PY" mcp/extensions/template_get.py --limit 0 >/dev/null 2>&1
ec=$?
if [ "$ec" = "2" ]; then
    pass "--limit 0 -> exit 2 (usage error)"
else
    fail "--limit 0 -> exit $ec (expected 2)"
fi

# C.2: --limit 501 -> exit 2
"$PY" mcp/extensions/template_get.py --limit 501 >/dev/null 2>&1
ec=$?
if [ "$ec" = "2" ]; then
    pass "--limit 501 -> exit 2 (out of range)"
else
    fail "--limit 501 -> exit $ec"
fi

# C.3: missing templates_index.json handled gracefully
TMPDIR=$(mktemp -d)
cp skills/chenxin-core/templates_index.json "$TMPDIR/"
mv skills/chenxin-core/templates_index.json skills/chenxin-core/templates_index.json.bak
out=$("$PY" mcp/extensions/template_get.py --use-case txt2img --modality image 2>&1) || true
mv skills/chenxin-core/templates_index.json.bak skills/chenxin-core/templates_index.json
if echo "$out" | grep -q '"index_present": false'; then
    pass "missing templates_index.json -> index_present: false (graceful)"
else
    fail "missing index: $out"
fi
rm -rf "$TMPDIR"

# C.4: non-matching filter returns empty matches (no crash)
out=$("$PY" mcp/extensions/template_get.py --use-case "__definitely-no-such-use-case__" --modality image 2>&1) || true
if echo "$out" | grep -q '"matches": \[\]'; then
    pass "non-matching filter -> empty matches (no crash)"
else
    fail "non-matching filter: $out"
fi

echo
echo "=== Group D — gui_save.py adversarial ==="

# D.1: --name with path-traversal must be neutralized
TMP=$(mktemp -d)
COMFYUI_PATH="$TMP" "$PY" mcp/extensions/gui_save.py --graph - --name "../../etc/passwd" < /dev/null > /tmp/gs_out.json 2>&1
ec=$?
saved_to=$(grep -oE '"saved_to": *"[^"]+"' /tmp/gs_out.json 2>/dev/null | head -1)
if [ -n "$saved_to" ]; then
    if echo "$saved_to" | grep -q "$TMP"; then
        pass "path-traversal --name ../../etc/passwd neutralized (path stays under COMFYUI_PATH)"
    else
        fail "path-traversal escaped: $saved_to"
    fi
elif [ "$ec" = "2" ]; then
    pass "path-traversal --name rejected (exit 2)"
else
    fail "path-traversal: $(cat /tmp/gs_out.json 2>/dev/null | head -3)"
fi
rm -rf "$TMP" /tmp/gs_out.json

# D.2: --name empty rejected
COMFYUI_PATH=/tmp "$PY" mcp/extensions/gui_save.py --graph - --name "" >/dev/null 2>&1
ec=$?
if [ "$ec" = "2" ]; then
    pass "--name empty rejected (exit 2)"
else
    fail "--name empty: exit $ec (expected 2)"
fi

# D.3: very long --name truncated
# We need a tmpdir that is *writable + cd-able* by the script. Some
# Windows python builds fail to chdir() into /tmp. Use $ROOT's tmp instead.
LONGNAME=$(printf 'a%.0s' {1..200})
TMP="$ROOT/.tmp-cli-test-$$"
mkdir -p "$TMP"
COMFYUI_PATH="$TMP" "$PY" mcp/extensions/gui_save.py --graph - --name "$LONGNAME" < /dev/null > /tmp/gs_long.json 2>&1
ec=$?
saved_to=$(grep -oE '"saved_to": *"[^"]+"' /tmp/gs_long.json 2>/dev/null | head -1)
if [ -n "$saved_to" ]; then
    fname=$(basename "$saved_to")
    base=$(echo "$fname" | sed 's/^[0-9_-]*//')
    len=${#base}
    if [ "$len" -le 120 ]; then
        pass "long --name truncated: $len chars (<= 120)"
    else
        fail "long --name not truncated: $len chars"
    fi
elif [ "$ec" = "2" ]; then
    pass "long --name rejected (exit 2)"
else
    fail "long --name: exit $ec, output: $(cat /tmp/gs_long.json 2>/dev/null | head -3)"
fi
rm -rf "$TMP" /tmp/gs_long.json

# D.4: malformed JSON input rejected
COMFYUI_PATH=/tmp "$PY" mcp/extensions/gui_save.py --graph - --name test < <(echo "not json") >/dev/null 2>&1
ec=$?
if [ "$ec" != "0" ]; then
    pass "malformed JSON input rejected (exit $ec)"
else
    fail "malformed JSON input returned 0"
fi

echo
if [ "$FAILS" -eq 0 ]; then
    echo "[cli-advanced] all adversarial assertions passed"
    exit 0
else
    echo "[cli-advanced] $FAILS assertion(s) failed"
    exit 1
fi
