"""Validate caller-authored prompt drafts without producing execution metadata."""
from __future__ import annotations
import copy, re

SCHEMA_VERSION="2.0"
_BAD={"workflow","node","hash","gpu","execution","mode","runtime"}
_PLACEHOLDERS=(re.compile(r"\[(?:todo|tbd|unset|placeholder)\]",re.I),re.compile(r"\{\{[^{}]+\}\}"),re.compile(r"<placeholder>",re.I))

def _text(v): return isinstance(v,str) and bool(v.strip())
def _execution_key(key):
    separated=re.sub(r"([a-z0-9])([A-Z])",r"\1_\2",str(key))
    tokens={x for x in re.split(r"[^a-z0-9]+",separated.casefold()) if x}
    normalized="".join(tokens)
    return "mode" in tokens or any(x in normalized for x in _BAD-{"mode"})
def _reject(v,path="payload"):
    if isinstance(v,dict):
        for k,child in v.items():
            if _execution_key(k): raise ValueError(f"execution field is not allowed: {path}.{k}")
            _reject(child,f"{path}.{k}")
    elif isinstance(v,list):
        for i,child in enumerate(v): _reject(child,f"{path}[{i}]")

def lint_prompt_text(text,forbidden_patterns):
    if not isinstance(text,str): raise ValueError("prompt text must be a string")
    if not isinstance(forbidden_patterns,list) or not all(isinstance(x,str) for x in forbidden_patterns):
        raise ValueError("forbidden_patterns must be a list of strings")
    out=[]
    for regex in _PLACEHOLDERS:
        for match in regex.finditer(text):
            msg=f"placeholder: {match.group(0)}"
            if msg not in out: out.append(msg)
    folded=text.casefold()
    for pattern in forbidden_patterns:
        msg=f"forbidden pattern: {pattern}"
        if pattern and pattern.casefold() in folded and msg not in out: out.append(msg)
    return out

def _negative_supported(policy):
    value=str(policy or "").casefold()
    return not any(x in value for x in ("instead of supplying negative","separate negative prompt is not used","no separate negative","without a separate negative","rather than a separate negative"))

def _facts(evidence):
    out=[]
    for fact in evidence.get("locked_facts",[]):
        if _text(fact) and fact not in out: out.append(fact)
    for row in evidence.get("shared_known",[]):
        if isinstance(row,dict) and row.get("origin")=="explicit" and _text(row.get("value")) and row["value"] not in out: out.append(row["value"])
    return out

def _image(draft,dialect,out,errors):
    texts=[]
    if _text(draft.get("positive")): out["positive"]=draft["positive"]; texts.append(draft["positive"])
    else: errors.append("missing required prompt field: positive")
    if any(k in draft for k in ("positive_zh","positive_en","global_prompt","timeline_segments")): errors.append("video-only fields are not allowed for an image dialect")
    if "negative" in draft:
        if not _text(draft["negative"]): errors.append("negative must be a non-empty string when supplied")
        elif not _negative_supported(dialect.get("negative_policy")): errors.append("negative prompt is not supported by this dialect")
        else: out["negative"]=draft["negative"]; texts.append(draft["negative"])
    return texts,True

def _video(draft,out,errors):
    texts=[]; temporal=True
    for key in ("positive_zh","positive_en","global_prompt"):
        if _text(draft.get(key)): out[key]=draft[key]; texts.append(draft[key])
        else: errors.append(f"missing required prompt field: {key}")
    if any(k in draft for k in ("positive","negative")): errors.append("image-only fields are not allowed for a video dialect")
    segs=draft.get("timeline_segments"); previous=None
    if not isinstance(segs,list) or not segs: errors.append("timeline_segments must be a non-empty list"); temporal=False
    else:
        out["timeline_segments"]=copy.deepcopy(segs)
        for i,seg in enumerate(segs):
            if not isinstance(seg,dict): errors.append(f"timeline segment {i} must be an object"); temporal=False; continue
            start,end=seg.get("start"),seg.get("end")
            valid=type(start) in (int,float) and type(end) in (int,float) and end>start
            if not valid: errors.append(f"timeline segment {i} has invalid time range"); temporal=False
            elif (i==0 and start!=0) or (previous is not None and start!=previous): errors.append(f"timeline segment {i} is not contiguous"); temporal=False
            if valid: previous=end
            if not _text(seg.get("zh")) or not _text(seg.get("en")): errors.append(f"timeline segment {i} requires zh and en text"); temporal=False
            else: texts.extend((seg["zh"],seg["en"]))
    dialogue=draft.get("dialogue_attribution")
    if not isinstance(dialogue,list): errors.append("dialogue_attribution must be a list"); temporal=False
    else:
        out["dialogue_attribution"]=copy.deepcopy(dialogue)
        for i,item in enumerate(dialogue):
            if not isinstance(item,dict): errors.append(f"dialogue item {i} must be an object"); temporal=False; continue
            if not _text(item.get("speaker")) or not _text(item.get("text")): errors.append(f"dialogue item {i} requires speaker and text"); temporal=False
            else: texts.append(item["text"])
            start,end=item.get("start"),item.get("end")
            if not(type(start) in (int,float) and type(end) in (int,float) and end>start and previous is not None and 0<=start<end<=previous): errors.append(f"dialogue item {i} has invalid time range"); temporal=False
    locks=draft.get("continuity_locks")
    if not isinstance(locks,list) or not locks or not all(_text(x) for x in locks): errors.append("continuity_locks must be a non-empty list of strings"); temporal=False
    else: out["continuity_locks"]=copy.deepcopy(locks); texts.extend(locks)
    return texts,temporal

def validate_draft(draft,evidence,dialect):
    if not all(isinstance(x,dict) for x in (draft,evidence,dialect)): raise ValueError("draft, evidence, and dialect must be objects")
    _reject(draft,"draft"); _reject(evidence,"evidence"); _reject(dialect,"dialect")
    modality=dialect.get("modality")
    if modality not in {"image","video"}: raise ValueError("dialect modality must be image or video")
    if not _text(dialect.get("id")): raise ValueError("dialect id must be a non-empty string")
    errors=[]; warnings=[]; out={"schema_version":SCHEMA_VERSION,"target":modality,"dialect":dialect["id"]}
    texts,temporal=_image(draft,dialect,out,errors) if modality=="image" else _video(draft,out,errors)
    forbidden=dialect.get("forbidden_patterns",[])
    if not isinstance(forbidden,list): raise ValueError("dialect forbidden_patterns must be a list")
    for text in texts:
        for error in lint_prompt_text(text,forbidden):
            if error not in errors: errors.append(error)
    combined=" ".join(" ".join(x.casefold().split()) for x in texts)
    missing=[fact for fact in _facts(evidence) if " ".join(fact.casefold().split()) not in combined]
    warnings.extend(f"missing explicit fact: {fact}" for fact in missing)
    out["evidence"]=copy.deepcopy(evidence)
    out["locked_facts"]=copy.deepcopy(_facts(evidence))
    out["uncertainty"]=copy.deepcopy(evidence.get("uncertainty", []))
    out["source_provenance"]=copy.deepcopy(evidence.get("source_provenance", []))
    out["warnings"]=warnings; out["errors"]=errors
    out["quality"]={"facts_preserved":not missing,"no_unsupported_invention":not any("not supported" in x for x in errors),"style_coherent":not any(x.startswith("forbidden pattern:") for x in errors),"dialect_valid":not any("not supported" in x or "-only fields" in x or "required prompt field" in x for x in errors),"temporal_logic_valid":temporal,"ready_for_review":not errors and not missing}
    return out
