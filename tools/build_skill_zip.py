#!/usr/bin/env python3
"""Build dist/svg-ui-bridge-skill.zip, the package uploaded in Customize > Skills on claude.ai.

The zip holds one svg-ui-bridge/ folder with SKILL.md, scripts/, references/ and templates/.
SKILL.md is checked first and the build fails on any problem. The same sources give the same file
contents everywhere, and the same bytes on the same Python build (zlib compresses differently
between builds).

  python tools/build_skill_zip.py
  python tools/build_skill_zip.py --out somewhere/skill.zip
  python tools/build_skill_zip.py --expect-version 0.2.0     # release workflow: tag must match
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "svg-ui-bridge"
SKILL = ROOT / "skills" / NAME
INCLUDE_DIRS = ("scripts", "references", "templates")
EXCLUDE_DIR_NAMES = {"__pycache__"}
EXCLUDE_SUFFIXES = {".pyc", ".png", ".html"}

# Agent Skills specification and claude.ai upload rules
ALLOWED_KEYS = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}
RESERVED_WORDS = ("anthropic", "claude")
NAME_MAX = 64
# The specification allows 1024 characters but the Claude help center says 200; meet both.
DESCRIPTION_MAX = 200


def frontmatter(text: str) -> dict[str, str] | None:
    """Parse the top-level keys of a SKILL.md frontmatter block."""
    m = re.match(r"---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not m:
        return None
    fields: dict[str, str] = {}
    key = None
    for line in m.group(1).splitlines():
        top = re.match(r"([A-Za-z][\w-]*):\s*(.*)$", line)
        if top:
            key = top.group(1)
            fields[key] = top.group(2).strip()
        elif key and line.startswith((" ", "\t")):
            fields[key] += " " + line.strip()
    return fields


def check_skill(text: str, version: str) -> list[str]:
    """Return every rule SKILL.md breaks."""
    fields = frontmatter(text)
    if fields is None:
        return ["SKILL.md has no YAML frontmatter"]
    problems = [f"frontmatter key '{k}' is not allowed" for k in sorted(set(fields) - ALLOWED_KEYS)]

    name = fields.get("name", "")
    if name != NAME:
        problems.append(f"name must match its folder '{NAME}', got '{name}'")
    if len(name) > NAME_MAX or not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name):
        problems.append(f"name '{name}' is not valid: lowercase letters, digits and single hyphens")
    problems += [f"name contains reserved word '{w}'" for w in RESERVED_WORDS if w in name]

    description = fields.get("description", "").strip("\"'")
    if not description:
        problems.append("description is empty")
    if len(description) > DESCRIPTION_MAX:
        problems.append(f"description is {len(description)} characters, max {DESCRIPTION_MAX}")
    if "<" in description or ">" in description:
        problems.append("description cannot contain angle brackets")

    body = text.split("---", 2)[-1]
    if f"Version: {version}" not in body:
        problems.append(f"SKILL.md body has no 'Version: {version}' line")
    return problems


def skill_files() -> list[Path]:
    def wanted(p: Path) -> bool:
        return (p.is_file() and p.suffix.lower() not in EXCLUDE_SUFFIXES
                and not p.name.endswith(".pyc") and ".components." not in p.name
                and not EXCLUDE_DIR_NAMES & set(p.parts))

    files = [SKILL / "SKILL.md"]
    for d in INCLUDE_DIRS:
        files += sorted((p for p in (SKILL / d).rglob("*") if wanted(p)), key=lambda p: p.as_posix())
    return files


def build(out: Path) -> int:
    files = skill_files()
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            arc = f"{NAME}/{p.relative_to(SKILL).as_posix()}"
            info = zipfile.ZipInfo(arc, date_time=(1980, 1, 1, 0, 0, 0))  # fixed, for repeatable builds
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, p.read_bytes())
    return len(files)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT / "dist" / f"{NAME}-skill.zip"))
    ap.add_argument("--expect-version", help="fail unless plugin.json has this version")
    a = ap.parse_args()

    manifest = ROOT / ".claude-plugin" / "plugin.json"
    version = json.loads(manifest.read_text(encoding="utf-8"))["version"]
    if a.expect_version and a.expect_version != version:
        print(f"plugin.json is {version}, expected {a.expect_version}", file=sys.stderr)
        return 1

    problems = check_skill((SKILL / "SKILL.md").read_text(encoding="utf-8"), version)
    extra = [p for p in SKILL.rglob("SKILL.md") if p != SKILL / "SKILL.md"]
    problems += [f"extra SKILL.md: {p}" for p in extra]
    if problems:
        print("SKILL.md failed validation:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    out = Path(a.out)
    n = build(out)
    print(f"wrote {out}: {n} files, {out.stat().st_size / 1024:.1f} KB, version {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
