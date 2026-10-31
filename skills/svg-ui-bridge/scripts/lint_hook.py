#!/usr/bin/env python3
"""Claude Code PostToolUse hook: lint design SVGs right after the agent writes them.

Reads the hook payload from stdin. Does nothing unless the written file is an .svg inside a
`design/` folder. On lint errors exits 2 with the report on stderr (Claude Code shows it to the
agent so it fixes the SVG); warnings alone exit 0.
"""
import json
import subprocess
import sys
from pathlib import Path

# Windows consoles default to a legacy code page; never crash on a non-ASCII character.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass



def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    fp = (payload.get("tool_input") or {}).get("file_path") or ""
    p = Path(fp)
    if p.suffix.lower() != ".svg" or "design" not in [part.lower() for part in p.parts]:
        return 0
    if not p.exists():
        return 0
    lint = Path(__file__).resolve().parent / "svg_lint.py"
    r = subprocess.run([sys.executable, str(lint), str(p)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.stderr.write("svg-ui-bridge lint failed — fix the SVG before continuing:\n" + r.stdout)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
