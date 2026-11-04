"""Build the TSX example and check the SVG tool contract. Needs Node.js and npm.

  python tests/test_tsx_design.py
"""
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'examples' / 'tsx-design'
sys.path.insert(0, str(ROOT / 'skills' / 'svg-ui-bridge' / 'scripts'))
from svg_lint import lint


def main():
    npm = shutil.which('npm.cmd' if sys.platform == 'win32' else 'npm')
    if not npm:
        raise RuntimeError('Node.js and npm are required for the TSX example test')
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / 'system'
        shutil.copytree(EXAMPLE, source, ignore=shutil.ignore_patterns('node_modules'))
        subprocess.run([npm, 'ci', '--no-audit', '--no-fund'], cwd=source, check=True)
        subprocess.run([npm, 'run', 'typecheck'], cwd=source, check=True)

        def build():
            subprocess.run([npm, 'run', 'build'], cwd=source, check=True)
            return [(Path(tmp) / f'settings.{state}.svg').read_bytes()
                    for state in ('default', 'disabled')]

        first = build()
        assert build() == first, 'Unchanged source must produce identical SVG'
        assert first[0] != first[1], 'States must have distinct appearances'
        for state in ('default', 'disabled'):
            path = Path(tmp) / f'settings.{state}.svg'
            errors, warnings, _ = lint(path)
            assert not errors and not warnings, (errors, warnings)
            svg = ET.parse(path).getroot()
            groups = [e.get('id') for e in svg.iter() if e.get('data-component')]
            assert groups == ['SettingsPanel', 'SaveButton', 'ResetButton']
            assert not any(e.tag.endswith('script') or any(k.lower().startswith('on')
                           for k in e.attrib) for e in svg.iter())
        theme = source / 'theme.ts'
        theme.write_text(theme.read_text(encoding='utf-8').replace('#4f8cff', '#ff8800'),
                         encoding='utf-8')
        changed = build()
        assert all(a != b and b'#ff8800' in b for a, b in zip(first, changed)), \
            'Shared theme changes must propagate to every generated view'

        broken = source / 'pages' / 'settings.tsx'
        broken.write_text(broken.read_text(encoding='utf-8').replace("x: 24 }", "x: '24' }"), encoding='utf-8')
        typecheck = subprocess.run([npm, 'run', 'typecheck'], cwd=source, capture_output=True)
        assert typecheck.returncode != 0, 'A wrong prop type must fail the type check'
    print('TSX example: npm ci, type check, deterministic build, static variants, ids, lint, '
          'theme propagation and type errors PASS')


if __name__ == '__main__':
    main()
