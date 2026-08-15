"""Standalone Anima Prompt v1 command line interface."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
import traceback
from dataclasses import asdict
from pathlib import Path
from typing import Any, TextIO

from .authoring.routing import ModelProfile, default_model_profile
from .authoring.relation_submission import submit_relation_payload
from .authoring.workflow import run_authoring_workflow
from .catalog import Catalog, RelationOverlay
from .catalog.builder import CatalogBuilder, sha256_file
from .catalog.verification import verify_catalog
from .cli_protocol import (
    RequestInputError,
    emit_failure,
    emit_success,
    exit_code_for_error,
    load_json_request,
    write_json,
)
from .domain import Fact, LockedSegment, PromptBrief, RelationClaim, Subject
from .draft import PromptDraft, PromptSegment
from .inspection import inspect_draft
from .output import to_text_output


class CliError(Exception):
    def __init__(
        self,
        category: str,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.code = code
        self.message = message
        self.details = details or {}

    def record(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


class ArgumentParsingError(ValueError):
    pass


class CliArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ArgumentParsingError(message)


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout
    stderr = stderr if stderr is not None else sys.stderr
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    parser = _build_parser()
    try:
        args = parser.parse_args(raw_argv)
    except ArgumentParsingError as error:
        command, stage = _command_from_tokens(raw_argv)
        cli_error = CliError("request", "argument_error", str(error))
        if "--json" in raw_argv:
            write_json(emit_failure(command, stage, [cli_error.record()]), stream=stdout)
        else:
            stderr.write(f"argument_error: {error}\n")
        return exit_code_for_error("request")
    command = _command_name(args)
    stage = _stage_name(args)

    try:
        if args.command == "author":
            result, advisories = _author(args, stdin)
            envelope = emit_success("author", "author", result, advisories)
            if args.json:
                write_json(envelope, stream=stdout)
            else:
                stdout.write(to_text_output(_prompt_output(result["prompt"])) + "\n")
            return 0
        if args.command == "inspect":
            result, advisories = _inspect(args)
        elif args.command == "catalog":
            result, advisories = _catalog(args)
        else:
            result, advisories = _relation(args)
        envelope = emit_success(command, stage, result, advisories)
        if args.json:
            write_json(envelope, stream=stdout)
        else:
            stdout.write(json.dumps(result, ensure_ascii=False, default=list) + "\n")
        return 0
    except RequestInputError as error:
        cli_error = CliError("request", "request_invalid", str(error))
    except CliError as error:
        cli_error = error
    except (TypeError, ValueError) as error:
        cli_error = CliError("validation", "request_validation_failed", str(error))
    except (KeyError, OSError, sqlite3.Error) as error:
        cli_error = CliError("integrity", "resource_unavailable", str(error))
    except Exception as error:  # pragma: no cover - defensive process boundary
        traceback.print_exc(file=stderr)
        cli_error = CliError("unexpected", "unexpected_error", str(error))

    envelope = emit_failure(command, stage, [cli_error.record()])
    if getattr(args, "json", False):
        write_json(envelope, stream=stdout)
    else:
        stderr.write(f"{cli_error.code}: {cli_error.message}\n")
    return exit_code_for_error(cli_error.category)


def _build_parser() -> argparse.ArgumentParser:
    parser = CliArgumentParser(prog="anima-prompt-v1")
    parser.add_argument("--version", action="version", version="%(prog)s 1.0.0")
    subcommands = parser.add_subparsers(dest="command", required=True)

    author = subcommands.add_parser("author")
    _add_request_source(author)
    author.add_argument("--database", type=Path)
    author.add_argument("--json", action="store_true")

    inspect = subcommands.add_parser("inspect")
    inspect.add_argument("--draft", type=Path, required=True)
    inspect.add_argument("--brief", type=Path, required=True)
    inspect.add_argument("--json", action="store_true")

    catalog = subcommands.add_parser("catalog")
    catalog_commands = catalog.add_subparsers(dest="catalog_command", required=True)
    _add_catalog_search(catalog_commands)
    _add_catalog_related(catalog_commands)
    _add_catalog_browse(catalog_commands)
    stats = catalog_commands.add_parser("stats")
    stats.add_argument("--database", type=Path)
    stats.add_argument("--json", action="store_true")
    build = catalog_commands.add_parser("build")
    build.add_argument("--source", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--manifest", type=Path)
    build.add_argument("--json", action="store_true")
    export = catalog_commands.add_parser("export")
    export.add_argument("--database", type=Path, required=True)
    export.add_argument("--query", default="")
    export.add_argument(
        "--mode",
        choices=("auto", "exact", "prefix", "alias", "fuzzy", "related"),
        default="auto",
    )
    export.add_argument("--category", action="append", default=[])
    export.add_argument("--facet", action="append", default=[])
    export.add_argument("--source", action="append", default=[])
    export.add_argument("--limit", type=_positive_limit, default=1000)
    export.add_argument("--format", choices=("jsonl", "csv"), required=True)
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--json", action="store_true")
    verify = catalog_commands.add_parser("verify")
    verify.add_argument("--database", type=Path, required=True)
    verify.add_argument("--manifest", type=Path)
    verify.add_argument("--json", action="store_true")

    relation = subcommands.add_parser("relation")
    relation_commands = relation.add_subparsers(dest="relation_command", required=True)
    submit = relation_commands.add_parser("submit")
    submit.add_argument("--database", type=Path, required=True)
    submit.add_argument("--overlay", type=Path, required=True)
    submit.add_argument("--payload", type=Path, required=True)
    submit.add_argument("--model", default="current-llm")
    submit.add_argument("--source", default="llm")
    submit.add_argument("--json", action="store_true")
    list_command = relation_commands.add_parser("list")
    list_command.add_argument("--overlay", type=Path, required=True)
    list_command.add_argument(
        "--status",
        choices=("candidate", "accepted", "rejected", "all"),
        default="all",
    )
    list_command.add_argument("--record-id")
    list_command.add_argument("--limit", type=_positive_limit, default=100)
    list_command.add_argument("--json", action="store_true")
    for action in ("accept", "reject"):
        action_parser = relation_commands.add_parser(action)
        action_parser.add_argument("--overlay", type=Path, required=True)
        action_parser.add_argument("proposal_id")
        action_parser.add_argument("--json", action="store_true")
    return parser


def _add_catalog_search(commands) -> None:
    search = commands.add_parser("search")
    search.add_argument("query")
    search.add_argument("--database", type=Path)
    search.add_argument("--overlay", type=Path)
    search.add_argument(
        "--mode",
        choices=("auto", "exact", "prefix", "alias", "fuzzy", "related"),
        default="auto",
    )
    _add_catalog_filters(search)
    search.add_argument("--limit", type=_positive_limit, default=20)
    search.add_argument("--json", action="store_true")


def _add_catalog_related(commands) -> None:
    related = commands.add_parser("related")
    related.add_argument("record_id")
    related.add_argument("--database", type=Path)
    related.add_argument("--overlay", type=Path)
    related.add_argument("--relation-type")
    related.add_argument("--limit", type=_positive_limit, default=50)
    related.add_argument("--json", action="store_true")


def _add_catalog_browse(commands) -> None:
    browse = commands.add_parser("browse")
    browse.add_argument("--database", type=Path)
    _add_catalog_filters(browse)
    browse.add_argument("--limit", type=_positive_limit, default=20)
    browse.add_argument("--json", action="store_true")


def _add_catalog_filters(parser) -> None:
    parser.add_argument("--category", action="append", default=[])
    parser.add_argument("--facet", action="append", default=[])
    parser.add_argument("--source", action="append", default=[])


def _positive_limit(value: str) -> int:
    limit = int(value)
    if limit < 1:
        raise argparse.ArgumentTypeError("limit must be at least 1")
    return limit


def _add_request_source(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--request", type=Path)
    source.add_argument("--stdin", action="store_true")


def _author(args: argparse.Namespace, stdin: TextIO):
    request = load_json_request(
        request_path=args.request,
        stdin=stdin if args.stdin else None,
    )
    missing = [field for field in ("facts", "subjects") if field not in request]
    if missing:
        raise CliError(
            "validation",
            "structured_brief_required",
            "author requires a structured PromptBrief; raw text is not authoritative",
            {"required": ["facts", "subjects"]},
        )
    allowed = {
        "variant",
        "route",
        "facts",
        "subjects",
        "relations",
        "exclusions",
        "locked_segments",
        "source_priority",
        "trigger_words",
    }
    unknown = sorted(set(request) - allowed)
    if unknown:
        raise CliError(
            "validation",
            "unknown_request_fields",
            "author request contains unknown fields",
            {"fields": unknown},
        )
    brief = _coerce_brief(request)
    profile = default_model_profile(
        request.get("variant", "base"),
        trigger_words=tuple(
            _string(value, f"trigger_words[{index}]")
            for index, value in enumerate(
                _items(request.get("trigger_words", ()), "trigger_words")
            )
        ),
        source="cli",
        evidence_level="caller_declared",
    )
    result = run_authoring_workflow(
        brief,
        catalog=Catalog(args.database),
        requested_route=request.get("route"),
        profile=profile,
    )
    inspection_status = "ADVISORY" if result.inspection.issues else "PASS"
    phase_status = {
        "brief": "PASS",
        "quality_seed": "PASS",
        "catalog": "PASS" if result.catalog_hits else "ADVISORY",
        "relation_graph": "PASS",
        "route": "PASS",
        "positive_author": "PASS",
        "negative_author": "PASS",
        "plan": "PASS",
        "draft": "PASS",
        "inspection": inspection_status,
        "output": "PASS",
    }
    hits = [asdict(hit) for hit in result.catalog_hits]
    relation_record_ids = [
        hit.record_id
        for hit in result.catalog_hits
        if hit.match_type in {"canonical", "exact", "alias"}
    ]
    issues = [asdict(issue) for issue in result.inspection.issues]
    prompt = asdict(result.output)
    advisories = [
        {"code": issue["code"], "message": issue["message"], "details": issue}
        for issue in issues
    ]
    return {
        "prompt": prompt,
        "phase_status": phase_status,
        "catalog_hits": hits,
        "relation_record_ids": relation_record_ids,
        "inspection": {
            "issues": issues,
            "token_estimate": result.inspection.token_estimate,
        },
        "metadata": {
            "variant": result.decision.profile.variant,
            "route": result.decision.route,
            "route_reasons": list(result.decision.reason_codes),
        },
        "brief": asdict(result.brief),
        "draft": asdict(result.draft),
    }, advisories


def _inspect(args: argparse.Namespace):
    draft_payload = load_json_request(request_path=args.draft)
    brief_payload = load_json_request(request_path=args.brief)
    draft = _coerce_draft(draft_payload)
    brief = _coerce_brief(brief_payload)
    report = inspect_draft(draft, brief=brief)
    issues = [asdict(issue) for issue in report.issues]
    advisories = [
        {"code": issue["code"], "message": issue["message"], "details": issue}
        for issue in issues
    ]
    return {
        "issues": issues,
        "token_estimate": report.token_estimate,
        "draft_summary": {
            "positive": draft.positive_text,
            "negative": draft.negative_text,
            "route": draft.route,
            "segment_count": len(draft.segments),
        },
    }, advisories


def _catalog(args: argparse.Namespace):
    action = args.catalog_command
    if action == "build":
        output = args.output.resolve()
        manifest = args.manifest.resolve() if args.manifest is not None else None
        stats = CatalogBuilder(args.source.resolve(), output).build(manifest_path=manifest)
        return {
            "output": str(output),
            "manifest": str(manifest) if manifest is not None else None,
            "stats": asdict(stats),
        }, []

    if action == "verify":
        database = args.database.resolve()
        manifest = args.manifest.resolve() if args.manifest is not None else None
        issues = verify_catalog(database, manifest)
        if issues:
            raise CliError(
                "integrity",
                "catalog_integrity_failed",
                "Catalog verification failed",
                {"issues": issues},
            )
        return {
            "database": str(database),
            "manifest": str(manifest) if manifest is not None else None,
            "issues": [],
        }, []

    catalog = Catalog(args.database, relation_overlay=getattr(args, "overlay", None))
    if action == "search":
        hits = catalog.search(
            args.query,
            mode=args.mode,
            categories=tuple(args.category),
            facets=tuple(args.facet),
            sources=tuple(args.source),
            limit=args.limit,
        )
        return {"hits": [_tag_hit(item) for item in hits]}, []
    if action == "related":
        hits = catalog.related(
            args.record_id,
            relation_type=args.relation_type,
            limit=args.limit,
        )
        return {"relations": [asdict(item) for item in hits]}, []
    if action == "browse":
        hits = catalog.browse(
            categories=tuple(args.category),
            facets=tuple(args.facet),
            sources=tuple(args.source),
            limit=args.limit,
        )
        return {"hits": [_tag_hit(item) for item in hits]}, []
    if action == "stats":
        return {"stats": catalog.stats()}, []
    if action == "export":
        hits = _export_hits(
            catalog,
            query=args.query,
            mode=args.mode,
            categories=args.category,
            facets=args.facet,
            sources=args.source,
            limit=args.limit,
        )
        output = args.output.resolve()
        if output == args.database.resolve():
            raise CliError(
                "validation",
                "output_overwrites_input",
                "export output must not overwrite the Catalog database",
                {"output": str(output)},
            )
        output.parent.mkdir(parents=True, exist_ok=True)
        rows = [_tag_hit(item) for item in hits]
        if args.format == "jsonl":
            output.write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                encoding="utf-8",
            )
        else:
            fields = sorted({key for row in rows for key in row})
            with output.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
        return {
            "output": str(output),
            "format": args.format,
            "count": len(rows),
            "sha256": sha256_file(output),
        }, []
    raise CliError("request", "unknown_catalog_command", f"unknown catalog command: {action}")


def _relation(args: argparse.Namespace):
    action = args.relation_command
    overlay = RelationOverlay(args.overlay)
    if action == "submit":
        payload = load_json_request(request_path=args.payload)
        submission = submit_relation_payload(
            payload,
            catalog=Catalog(args.database),
            overlay=args.overlay,
            model=args.model,
            source=args.source,
        )
        if submission.issues:
            raise CliError(
                "validation",
                "relation_validation_failed",
                "relation submission failed validation",
                {"issues": list(submission.issues)},
            )
        return {
            "record_ids": list(submission.record_ids),
            "proposals": [asdict(item) for item in submission.proposals],
            "issues": [],
        }, []
    if action == "list":
        proposals = overlay.list(
            status=args.status,
            record_id=args.record_id,
            limit=args.limit,
        )
        return {"proposals": [asdict(item) for item in proposals]}, []
    if action == "accept":
        overlay.accept(args.proposal_id)
        return {"proposal_id": args.proposal_id, "status": "accepted"}, []
    if action == "reject":
        overlay.reject(args.proposal_id)
        return {"proposal_id": args.proposal_id, "status": "rejected"}, []
    raise CliError("request", "unknown_relation_command", f"unknown relation command: {action}")


def _tag_hit(hit) -> dict[str, Any]:
    payload = asdict(hit)
    payload["candidate"] = hit.match_type == "fuzzy"
    return payload


def _export_hits(
    catalog: Catalog,
    *,
    query: str,
    mode: str,
    categories,
    facets,
    sources,
    limit: int,
):
    if limit > 100_000:
        raise CliError(
            "validation",
            "export_limit_invalid",
            "export limit must not exceed 100000",
            {"limit": limit},
        )
    if not query.strip() and not (categories or facets or sources):
        raise CliError(
            "validation",
            "export_scope_required",
            "export requires a query or an explicit category, facet, or source scope",
        )
    if query.strip():
        return catalog.search(
            query,
            mode=mode,
            categories=tuple(categories),
            facets=tuple(facets),
            sources=tuple(sources),
            limit=limit,
        )
    return catalog.browse(
        categories=tuple(categories),
        facets=tuple(facets),
        sources=tuple(sources),
        limit=limit,
    )


def _command_name(args: argparse.Namespace) -> str:
    if args.command == "catalog":
        return f"catalog {args.catalog_command}"
    if args.command == "relation":
        return f"relation {args.relation_command}"
    return args.command


def _command_from_tokens(argv: list[str]) -> tuple[str, str | None]:
    words = [value for value in argv if not value.startswith("-")]
    if not words:
        return "unknown", None
    if words[0] in {"catalog", "relation"}:
        command = " ".join(words[:2]) if len(words) > 1 else words[0]
        return command, None
    if words[0] == "author":
        return "author", "author"
    if words[0] == "inspect":
        return "inspect", "inspection"
    return words[0], None


def _stage_name(args: argparse.Namespace) -> str | None:
    if args.command == "author":
        return "author"
    if args.command == "inspect":
        return "inspection"
    return None


def catalog_main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    arguments = list(argv) if argv is not None else sys.argv[1:]
    if len(arguments) >= 3 and arguments[0] == "--database":
        database = arguments[1]
        arguments = [arguments[2], "--database", database, *arguments[3:]]
    return main(
        ["catalog", *arguments],
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
    )


def relation_main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    return main(
        ["relation", *(argv if argv is not None else sys.argv[1:])],
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
    )


def _coerce_brief(request: dict[str, Any]) -> PromptBrief:
    for field in ("facts", "subjects"):
        if field not in request:
            raise ValueError(f"request requires {field!r}")
    return PromptBrief(
        facts=tuple(
            _coerce_fact(item, "facts", index)
            for index, item in enumerate(_items(request["facts"], "facts"))
        ),
        subjects=tuple(
            _coerce_subject(item, index)
            for index, item in enumerate(_items(request["subjects"], "subjects"))
        ),
        relations=tuple(
            _coerce_relation(item, index)
            for index, item in enumerate(_items(request.get("relations", ()), "relations"))
        ),
        exclusions=tuple(
            _coerce_fact(item, "exclusions", index)
            for index, item in enumerate(_items(request.get("exclusions", ()), "exclusions"))
        ),
        locked_segments=tuple(
            _coerce_locked(item, index)
            for index, item in enumerate(
                _items(request.get("locked_segments", ()), "locked_segments")
            )
        ),
        source_priority=tuple(
            _items(
                request.get(
                    "source_priority",
                    ("user", "local_model", "official", "community", "default"),
                ),
                "source_priority",
            )
        ),
    )


def _coerce_draft(payload: dict[str, Any]) -> PromptDraft:
    profile_payload = _object(payload.get("model_profile"), "model_profile")
    profile = ModelProfile(
        variant=profile_payload["variant"],
        tag_preference=profile_payload["tag_preference"],
        natural_language_preference=profile_payload["natural_language_preference"],
        negative_tolerance=profile_payload["negative_tolerance"],
        quality_tag_policy=profile_payload["quality_tag_policy"],
        trigger_words=tuple(profile_payload.get("trigger_words", ())),
        token_limit=profile_payload.get("token_limit"),
        source=profile_payload.get("source", "default"),
        evidence_level=profile_payload.get("evidence_level", "default"),
    )
    segments = []
    for index, value in enumerate(_items(payload.get("segments"), "segments")):
        item = dict(_object(value, f"segments[{index}]"))
        for field in ("fact_notes", "relation_ids", "catalog_provenance"):
            item[field] = tuple(item.get(field, ()))
        segments.append(PromptSegment(**item))
    return PromptDraft(
        tuple(segments),
        str(payload["positive_text"]),
        str(payload["negative_text"]),
        payload["route"],
        profile,
        tuple(payload.get("provenance", ())),
    )


def _items(value: Any, field: str) -> list[Any]:
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"{field} must be an array")
    return list(value)


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{field} must be an object")
    return value


def _required(item: dict[str, Any], fields: tuple[str, ...], label: str) -> None:
    missing = [field for field in fields if field not in item]
    if missing:
        raise ValueError(f"{label} missing required fields: {', '.join(missing)}")


def _coerce_fact(value: Any, field: str, index: int) -> Fact:
    label = f"{field}[{index}]"
    item = _object(value, label)
    _required(item, ("fact_id", "value", "domain", "kind", "source"), label)
    return Fact(
        fact_id=_string(item["fact_id"], f"{label}.fact_id"),
        value=_string(item["value"], f"{label}.value"),
        domain=item["domain"],
        kind=item["kind"],
        source=item["source"],
        locked=_boolean(item.get("locked", False), f"{label}.locked"),
        confidence=item.get("confidence"),
        user_text=item.get("user_text"),
        subject_id=item.get("subject_id"),
        representation_hint=item.get("representation_hint", "auto"),
        notes=tuple(item.get("notes", ())),
    )


def _coerce_subject(value: Any, index: int) -> Subject:
    label = f"subjects[{index}]"
    item = _object(value, label)
    _required(item, ("subject_id", "label"), label)
    return Subject(
        _string(item["subject_id"], f"{label}.subject_id"),
        _string(item["label"], f"{label}.label"),
    )


def _coerce_relation(value: Any, index: int) -> RelationClaim:
    label = f"relations[{index}]"
    item = _object(value, label)
    _required(item, ("relation_id", "relation_type", "from_id", "to_id", "explicit"), label)
    return RelationClaim(
        relation_id=_string(item["relation_id"], f"{label}.relation_id"),
        relation_type=item["relation_type"],
        from_id=_string(item["from_id"], f"{label}.from_id"),
        to_id=_string(item["to_id"], f"{label}.to_id"),
        explicit=_boolean(item["explicit"], f"{label}.explicit"),
        source_fact_id=item.get("source_fact_id"),
    )


def _coerce_locked(value: Any, index: int) -> LockedSegment:
    label = f"locked_segments[{index}]"
    item = _object(value, label)
    _required(item, ("segment_id", "text"), label)
    return LockedSegment(
        _string(item["segment_id"], f"{label}.segment_id"),
        _string(item["text"], f"{label}.text"),
        item.get("representation", "text"),
    )


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{field} must be a non-empty string")
    return value


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{field} must be a boolean")
    return value


def _prompt_output(payload: dict[str, Any]):
    from .output import PromptOutput

    return PromptOutput(
        payload["positive"],
        payload["negative"],
        tuple(payload.get("notes", ())),
        tuple(payload.get("assumptions", ())),
        tuple(payload.get("advisories", ())),
    )


if __name__ == "__main__":
    raise SystemExit(main())
