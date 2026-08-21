#!/usr/bin/env python3
"""Validate Agent Skills packages without third-party dependencies."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterable

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FRONTMATTER_RE = re.compile(r"\A---\n(?P<body>.*?)\n---\n", re.DOTALL)
LOCAL_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
RESOURCE_RE = re.compile(
    r"(?<![A-Za-z0-9_./~$<>-])((?:scripts|references|templates|assets)/[A-Za-z0-9_./-]+)"
)
ABSOLUTE_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:tmp|Users|home|var|opt|workspace|repo|private|Volumes)(?:/[^\s`'\"<>()]*)?")
SECRET_PATTERNS = (
    re.compile(r"\b(?:sk|rk)-[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~-]{20,}\b"),
)
INJECTION_RE = re.compile(r"<\s*(?:system|assistant|user|instruction|prompt|tool)\b", re.I)
CAPABILITY_WORDS = re.compile(
    r"\b(?:run|manage|generate|audit|build|create|validate|control|design|implement|add|compute|write|inspect|configure)\b",
    re.I,
)
TRIGGER_WORDS = re.compile(r"\b(?:use when|when users|apply during|triggers? on|trigger(?:s)? when)\b", re.I)


def parse_frontmatter(text: str) -> tuple[dict[str, str], str | None]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, "missing YAML frontmatter"
    values: dict[str, str] = {}
    current: str | None = None
    folded = False
    for raw in match.group("body").splitlines():
        if not raw.strip():
            if folded and current:
                values[current] += " "
            continue
        if raw[:1].isspace():
            if folded and current:
                values[current] += " " + raw.strip()
            continue
        if ":" not in raw:
            return {}, f"invalid frontmatter line: {raw.strip()}"
        key, value = raw.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value in {">", ">-", "|", "|-"}:
            values[key] = ""
            current, folded = key, value.startswith(">")
        else:
            values[key] = value.strip('"\'')
            current, folded = key, False
    return values, None


def iter_local_references(skill_dir: Path, text: str) -> Iterable[tuple[str, Path]]:
    seen: set[str] = set()
    for match in LOCAL_LINK_RE.finditer(text):
        raw = match.group(1).split("#", 1)[0].strip()
        if not raw or raw.startswith(("http://", "https://", "mailto:", "#", "<")):
            continue
        candidate = raw[2:] if raw.startswith("./") else raw
        if candidate.startswith(("/", "~", "$")):
            continue
        if candidate not in seen:
            seen.add(candidate)
            yield candidate, skill_dir / candidate
    for match in RESOURCE_RE.finditer(text):
        candidate = match.group(1)
        if candidate not in seen:
            seen.add(candidate)
            yield candidate, skill_dir / candidate


def find_bad_absolute_paths(text: str) -> list[str]:
    without_urls = re.sub(r"https?://[^\s)]+", "", text)
    paths: list[str] = []
    for match in ABSOLUTE_PATH_RE.finditer(without_urls):
        value = match.group(0).rstrip(".,:;)")
        if value and value not in paths:
            paths.append(value)
    return paths


def find_secrets(text: str) -> list[str]:
    hits: list[str] = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            hits.append(pattern.pattern)
    return hits


def error(skill: str, code: str, message: str) -> dict[str, str]:
    return {"skill": skill, "code": code, "message": message}


def validate(root: Path) -> dict[str, object]:
    skills_root = root / "skills"
    result: dict[str, object] = {"ok": True, "skills": [], "errors": [], "warnings": []}
    errors: list[dict[str, str]] = result["errors"]  # type: ignore[assignment]
    warnings: list[dict[str, str]] = result["warnings"]  # type: ignore[assignment]
    skills: list[str] = result["skills"]  # type: ignore[assignment]
    if not skills_root.is_dir():
        errors.append(error("", "SKILLS_ROOT_MISSING", f"missing skills directory: {skills_root}"))
        result["ok"] = False
        return result

    for skill_dir in sorted(p for p in skills_root.iterdir() if p.is_dir()):
        skill = skill_dir.name
        skills.append(skill)
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            errors.append(error(skill, "SKILL_MISSING", "SKILL.md is missing"))
            continue
        try:
            text = skill_file.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(error(skill, "SKILL_UNREADABLE", str(exc)))
            continue
        frontmatter, frontmatter_error = parse_frontmatter(text)
        if frontmatter_error:
            errors.append(error(skill, "FRONTMATTER_INVALID", frontmatter_error))
            continue
        if frontmatter.get("name") != skill:
            errors.append(error(skill, "NAME_MISMATCH", f"frontmatter name is {frontmatter.get('name')!r}"))
        if not NAME_RE.fullmatch(frontmatter.get("name", "")):
            errors.append(error(skill, "NAME_INVALID", "name must contain lowercase letters, numbers, and hyphens"))
        description = frontmatter.get("description", "")
        if not CAPABILITY_WORDS.search(description) or not TRIGGER_WORDS.search(description):
            errors.append(error(skill, "DESCRIPTION_INVALID", "description must state capability and trigger conditions"))
        if len(text.splitlines()) >= 500:
            errors.append(error(skill, "SKILL_TOO_LONG", f"SKILL.md has {len(text.splitlines())} lines; maximum is 499"))
        if INJECTION_RE.search("\n".join(f"{k}: {v}" for k, v in frontmatter.items())):
            errors.append(error(skill, "UNSAFE_FRONTMATTER", "frontmatter contains prompt-injection-like XML"))
        if find_secrets("\n".join(f"{k}: {v}" for k, v in frontmatter.items())):
            errors.append(error(skill, "SECRET_IN_FRONTMATTER", "frontmatter contains a secret-looking value"))
        for relative, path in iter_local_references(skill_dir, text):
            if not path.exists():
                errors.append(error(skill, "MISSING_REFERENCE", f"referenced resource does not exist: {relative}"))
            elif relative.startswith("scripts/") and not os.access(path, os.X_OK):
                errors.append(error(skill, "SCRIPT_NOT_EXECUTABLE", f"referenced script is not executable: {relative}"))
        for path in skill_dir.rglob("*.md"):
            try:
                doc_text = path.read_text(encoding="utf-8")
            except OSError as exc:
                errors.append(error(skill, "RESOURCE_UNREADABLE", f"{path.relative_to(skill_dir)}: {exc}"))
                continue
            for absolute in find_bad_absolute_paths(doc_text):
                errors.append(error(skill, "ABSOLUTE_LOCAL_PATH", f"invalid absolute local path: {absolute}"))
            if find_secrets(doc_text):
                warnings.append({"skill": skill, "code": "SECRET_LOOKING_TEXT", "message": f"review {path.relative_to(skill_dir)}"})
    result["ok"] = not errors
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Agent Skills packages")
    parser.add_argument("--root", default=Path(__file__).resolve().parents[1], type=Path)
    args = parser.parse_args(argv)
    result = validate(args.root.resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
