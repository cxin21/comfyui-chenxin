#!/usr/bin/env python3
"""check_updates.py — weekly self-update daemon for comfyui-chenxin L3 substrate.

Compares the local knowledge substrate against four upstream sources and
emits a JSON report describing what changed. In `--apply` mode, it also
opens a branch with a fixup commit of the diff'd recipe / template files.

Upstream sources monitored:
  1. SlavaSexton/ComfyUI-Agent-Kit  shared/comfyui/MODELS.md
  2. Comfy-Org/workflow_templates  (git tree, compare SHAs)
  3. Comfy-Org/comfy-skills        (git fetch + diff against docs/, log only)
  4. HuggingFace blog RSS          (titles matching common model names)

CLI:
    python3 scripts/check_updates.py [--dry-run] [--apply] [--json-only]
                                      [--skip RSS] [--timeout SEC]

Output (stdout, machine-readable):
    {
      "schema_version": 1,
      "checked_at_utc": "...",
      "mode": "dry-run" | "apply",
      "sources": {
        "slavasexton_recipes": {"status": "up-to-date"|"drift"|"fetch_failed", "diff": {...}},
        "comfy_org_templates": {"status": ..., "diff": {...}},
        "comfy_org_skills":    {"status": ..., "diff": {...}},
        "hf_blog_rss":         {"status": ..., "items": [...]}
      },
      "recommended_action": "open PR" | "up-to-date" | "manual review"
    }

Stdlib only (Python 3.11). No `pip install` at runtime.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ---------- paths / constants ------------------------------------------------ #

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_RECIPES = REPO_ROOT / "skills" / "chenxin-core" / "recipes" / "MODELS.md"
LOCAL_TEMPLATES_INDEX = REPO_ROOT / "skills" / "chenxin-core" / "templates_index.json"

SLAVA_MODELS_URL = (
    "https://raw.githubusercontent.com/SlavaSexton/ComfyUI-Agent-Kit/main/"
    "shared/comfyui/MODELS.md"
)
HF_RSS_URL = "https://huggingface.co/blog/feed.xml"
COMFY_ORG_TEMPLATES_URL = "https://github.com/Comfy-Org/workflow_templates.git"
COMFY_ORG_SKILLS_URL = "https://github.com/Comfy-Org/comfy-skills.git"
COMFY_ORG_SKILLS_DOCS_SUBDIR = "docs"

# Track names that show up in HF blog titles for our domain.
HF_TRACK_NAMES = ("anima", "wan", "ltx", "hunyuan", "krea", "flux", "sdxl")

USER_AGENT = "comfyui-chenxin-check-updates/1.0 (+python-stdlib)"

SCHEMA_VERSION = 1


# ---------- I/O helpers (mirrors P0.2 mcp/extensions/_shared.py contract) --- #

def emit_json(payload: dict) -> None:
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    sys.stdout.flush()


def emit_human(line: str) -> None:
    sys.stderr.write(line.rstrip() + "\n")
    sys.stderr.flush()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def http_get(url: str, timeout: float = 10.0) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        emit_human(f"[check-updates] network error for {url}: {e}")
        return 0, b""


# ---------- source 1: SlavaSexton recipes ----------------------------------- #

def check_slava_recipes(timeout: float) -> dict:
    if not LOCAL_RECIPES.is_file():
        return {"status": "fetch_failed", "reason": f"local file missing: {LOCAL_RECIPES}"}
    code, body = http_get(SLAVA_MODELS_URL, timeout=timeout)
    if code != 200 or not body:
        return {"status": "fetch_failed", "http_code": code}
    # Lazy import to keep import cost low when other paths run.
    try:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from diff_recipes import parse_recipes, structural_diff
    except Exception as e:  # pragma: no cover
        return {"status": "fetch_failed", "reason": f"diff_recipes import: {e}"}
    local_text = LOCAL_RECIPES.read_text(encoding="utf-8")
    upstream_text = body.decode("utf-8", errors="replace")
    old_r = parse_recipes(local_text)
    new_r = parse_recipes(upstream_text)
    diff = structural_diff(old_r, new_r)
    drift = bool(diff["added"] or diff["removed"] or diff["changed"])
    return {
        "status": "drift" if drift else "up-to-date",
        "upstream_url": SLAVA_MODELS_URL,
        "diff_stats": {
            "old_count": len(old_r),
            "new_count": len(new_r),
            "added": len(diff["added"]),
            "removed": len(diff["removed"]),
            "changed": len(diff["changed"]),
        },
        "diff": diff,
    }


# ---------- source 2: Comfy-Org templates (SHAs only) ---------------------- #

def _git(*args: str, cwd: Path | None = None) -> tuple[int, str, str]:
    try:
        p = subprocess.run(
            ["git", *args],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        return p.returncode, p.stdout, p.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return 1, "", str(e)


def _shas_for_templates(repo: Path) -> dict[str, str]:
    code, out, err = _git("ls-tree", "-r", "HEAD", "--name-only", cwd=repo)
    if code != 0:
        return {}
    out_map: dict[str, str] = {}
    for line in out.splitlines():
        out_map[line] = ""  # path only; SHA below
    # Now fetch SHAs for the JSON templates — these are the ones our index lists.
    code, out, _ = _git("ls-tree", "-r", "HEAD", "--format=%(objectmode) %(objecttype) %(objectname) %(path)", cwd=repo)
    if code != 0:
        # Fallback: just use ls-tree without format
        code, out, _ = _git("ls-tree", "-r", "HEAD", cwd=repo)
        if code != 0:
            return out_map
    for line in out.splitlines():
        # Format: "<mode> <type> <sha> <tab><path>" or "<mode> <type> <sha>\t<path>"
        parts = line.split(None, 3)
        if len(parts) >= 4:
            sha = parts[2]
            path = parts[3].lstrip("\t")
        else:
            # alternate format: "<sha>\t<path>"
            tokens = line.split("\t", 1)
            if len(tokens) != 2:
                continue
            sha, path = tokens[0], tokens[1]
        out_map[path] = sha
    return out_map


def check_comfy_org_templates(timeout: float) -> dict:
    if not shutil.which("git"):
        return {"status": "fetch_failed", "reason": "git not on PATH"}
    if not LOCAL_TEMPLATES_INDEX.is_file():
        return {"status": "fetch_failed", "reason": f"local index missing: {LOCAL_TEMPLATES_INDEX}"}
    try:
        local_idx = json.loads(LOCAL_TEMPLATES_INDEX.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"status": "fetch_failed", "reason": f"local index malformed: {e}"}

    with tempfile.TemporaryDirectory(prefix="comfy_templates_") as td:
        repo = Path(td) / "workflow_templates"
        code, _, err = _git("clone", "--depth=1", "--filter=blob:none", "--sparse",
                            COMFY_ORG_TEMPLATES_URL, str(repo))
        if code != 0:
            return {"status": "fetch_failed", "reason": f"clone failed: {err[:200]}"}
        _git("sparse-checkout", "set", "*.json", cwd=repo)
        # network-bound; we don't honor --timeout here, git handles it.
        # Compare against known category globs.
        upstream_shas = _shas_for_templates(repo)
        if not upstream_shas:
            return {"status": "fetch_failed", "reason": "could not read upstream tree"}

        added: list[str] = []
        removed: list[str] = []
        changed: list[str] = []
        unchanged = 0
        for t in local_idx.get("templates", []):
            p = t.get("path", "")
            upstream_sha = upstream_shas.get(p, "")
            local_sha = t.get("sha", "")
            if not upstream_sha:
                removed.append(p)
            elif upstream_sha != local_sha:
                changed.append(p)
            else:
                unchanged += 1
        # Anything in upstream that's not in our index (sample only — full
        # list is large, so we just report count).
        known_paths = {t.get("path", "") for t in local_idx.get("templates", [])}
        upstream_json = [p for p in upstream_shas if p.endswith(".json")]
        new_count = sum(1 for p in upstream_json if p not in known_paths)

        drift = bool(added or removed or changed or new_count)
        return {
            "status": "drift" if drift else "up-to-date",
            "upstream_url": COMFY_ORG_TEMPLATES_URL,
            "diff_stats": {
                "known": len(local_idx.get("templates", [])),
                "upstream_json_total": len(upstream_json),
                "added_upstream": new_count,
                "removed_missing": len(removed),
                "changed_sha": len(changed),
                "unchanged": unchanged,
            },
            "changed_paths_sample": changed[:10],
            "removed_paths_sample": removed[:10],
        }


# ---------- source 3: Comfy-Org comfy-skills (best-effort) ----------------- #

def check_comfy_org_skills(timeout: float) -> dict:
    if not shutil.which("git"):
        return {"status": "fetch_failed", "reason": "git not on PATH"}
    with tempfile.TemporaryDirectory(prefix="comfy_skills_") as td:
        repo = Path(td) / "comfy-skills"
        code, _, err = _git("clone", "--depth=1", COMFY_ORG_SKILLS_URL, str(repo))
        if code != 0:
            return {"status": "fetch_failed", "reason": f"clone failed: {err[:200]}"}
        # Best-effort: just report file count under docs/.
        docs = repo / COMFY_ORG_SKILLS_DOCS_SUBDIR
        if not docs.is_dir():
            return {"status": "fetch_failed", "reason": "docs/ not present in upstream"}
        file_count = sum(1 for _ in docs.rglob("*.md"))
        return {
            "status": "up-to-date",
            "note": "log-only: no structural diff against local substrate yet",
            "upstream_url": COMFY_ORG_SKILLS_URL,
            "diff_stats": {"upstream_docs_md": file_count},
        }


# ---------- source 4: HuggingFace blog RSS --------------------------------- #

def _parse_rss(xml: bytes) -> list[dict]:
    """Tiny RSS 1.0/2.0 parser — extract <item> title + link + pubDate.

    Avoids xml.etree so we stay stdlib-agnostic to feedparser-less code paths.
    """
    import re as _re
    text = xml.decode("utf-8", errors="replace")
    items: list[dict] = []
    for m in _re.finditer(r"<item\b[^>]*>(.*?)</item>", text, flags=_re.DOTALL):
        block = m.group(1)
        t = _re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", block, flags=_re.DOTALL)
        l = _re.search(r"<link>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>", block)
        d = _re.search(r"<pubDate>(.*?)</pubDate>", block)
        if not t:
            continue
        items.append({
            "title": _re.sub(r"\s+", " ", t.group(1)).strip(),
            "link": (l.group(1).strip() if l else ""),
            "pubDate": (d.group(1).strip() if d else ""),
        })
    return items


def check_hf_blog(timeout: float) -> dict:
    code, body = http_get(HF_RSS_URL, timeout=timeout)
    if code != 200 or not body:
        return {"status": "fetch_failed", "http_code": code}
    items = _parse_rss(body)
    hits = [
        it for it in items
        if any(name in it["title"].lower() for name in HF_TRACK_NAMES)
    ]
    return {
        "status": "ok",
        "upstream_url": HF_RSS_URL,
        "diff_stats": {
            "total_items": len(items),
            "tracked_hits": len(hits),
        },
        "items": hits[:20],
    }


# ---------- aggregation + apply --------------------------------------------- #

def decide_action(sources: dict) -> str:
    """Roll up per-source status into a single recommended action."""
    recipe_drift = sources.get("slavasexton_recipes", {}).get("status") == "drift"
    templates_drift = sources.get("comfy_org_templates", {}).get("status") == "drift"
    skills_failed = sources.get("comfy_org_skills", {}).get("status") == "fetch_failed"
    if recipe_drift or templates_drift:
        return "open PR"
    if skills_failed:
        return "manual review"
    return "up-to-date"


def apply_fixup(sources: dict) -> dict:
    """Create a branch + commit any local-side fixups.

    Today: there is no local-side fixup; we just open a branch with an empty
    commit and a summary, so the cron workflow can show the user a PR
    describing what drifted. Future: actually stage the new MODELS.md and
    bumped templates_index.json here.
    """
    if not shutil.which("git"):
        return {"ok": False, "reason": "git not on PATH"}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    branch = f"phase/P1.2-self-update-{today}"
    code, _, err = _git("checkout", "-b", branch, cwd=REPO_ROOT)
    if code != 0:
        # Branch may already exist; reuse it.
        code, _, err = _git("checkout", branch, cwd=REPO_ROOT)
        if code != 0:
            return {"ok": False, "reason": f"checkout {branch}: {err[:200]}"}
    # Build a report file and commit it (so the PR has actual content).
    report = REPO_ROOT / "scripts" / "check_updates_report.json"
    report.write_text(json.dumps({"checked_at_utc": utc_now(), "sources": sources}, indent=2), encoding="utf-8")
    _git("add", str(report.relative_to(REPO_ROOT)), cwd=REPO_ROOT)
    _git("commit", "-m", f"auto(update): weekly substrate drift report ({today})",
         cwd=REPO_ROOT)
    return {"ok": True, "branch": branch, "report": str(report.relative_to(REPO_ROOT))}


# ---------- entry ----------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", default=True,
                    help="(default) do not commit, do not push")
    ap.add_argument("--apply", action="store_true",
                    help="create fixup branch + commit (cron mode)")
    ap.add_argument("--json-only", action="store_true",
                    help="suppress human status lines on stderr")
    ap.add_argument("--skip", action="append", default=[],
                    choices=("slava", "templates", "skills", "rss"),
                    help="skip a source (repeatable)")
    ap.add_argument("--timeout", type=float, default=10.0,
                    help="HTTP timeout per request (seconds)")
    args = ap.parse_args(argv)

    mode = "apply" if args.apply and not args.dry_run else "dry-run"
    if args.apply:
        mode = "apply"

    if not args.json_only:
        emit_human(f"[check-updates] mode={mode} repo={REPO_ROOT}")

    sources: dict = {}

    if "slava" not in args.skip:
        if not args.json_only:
            emit_human("[check-updates] checking SlavaSexton/ComfyUI-Agent-Kit recipes…")
        sources["slavasexton_recipes"] = check_slava_recipes(args.timeout)

    if "templates" not in args.skip:
        if not args.json_only:
            emit_human("[check-updates] checking Comfy-Org/workflow_templates…")
        sources["comfy_org_templates"] = check_comfy_org_templates(args.timeout)

    if "skills" not in args.skip:
        if not args.json_only:
            emit_human("[check-updates] checking Comfy-Org/comfy-skills…")
        sources["comfy_org_skills"] = check_comfy_org_skills(args.timeout)

    if "rss" not in args.skip:
        if not args.json_only:
            emit_human("[check-updates] checking HuggingFace blog RSS…")
        sources["hf_blog_rss"] = check_hf_blog(args.timeout)

    recommended = decide_action(sources)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "checked_at_utc": utc_now(),
        "mode": mode,
        "sources": sources,
        "recommended_action": recommended,
    }
    if mode == "apply":
        payload["apply_result"] = apply_fixup(sources)
        # Re-roll recommendation: if apply succeeded, the PR IS the action.
        if payload["apply_result"].get("ok"):
            payload["recommended_action"] = "open PR"
    emit_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
