"""Exercise actual browser rendering, failure reports and packaged HTML source."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills' / 'svg-ui-bridge'
sys.path.insert(0, str(SKILL / 'scripts'))
from html_review import review


class HtmlReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.source = self.work / 'design'
        shutil.copytree(SKILL / 'templates' / 'html-design', self.source)
        self.html = self.source / 'review.html'

    def capture(self, size=(1280, 800), name='capture'):
        return review(self.html, self.work / name, *size)

    def test_responsive_screens_and_coordinates(self):
        desktop = self.capture(name='desktop')
        mobile = self.capture((390, 844), 'mobile')
        for report, folder in [(desktop, 'desktop'), (mobile, 'mobile')]:
            self.assertEqual(report['status'], 'PASS', report['errors'])
            self.assertEqual(report['blocked'], [])
            self.assertEqual(report['failed'], [])
            self.assertEqual([s['state'] for s in report['screens']], ['default', 'saving'])
            for screen in report['screens']:
                self.assertEqual(len(screen['components']), 4)
                self.assertEqual(screen['components'][0]['bbox'][:2], [0, 0])
                for component in screen['components'][1:]:
                    self.assertEqual(component['parent'], screen['id'])
                    x, y, w, h = component['bbox']
                    self.assertGreaterEqual(x, 0)
                    self.assertGreaterEqual(y, 0)
                    self.assertLessEqual(x + w, screen['size'][0] + 1)
                    self.assertLessEqual(y + h, screen['size'][1] + 1)
                with Image.open(self.work / folder / screen['screenshot']) as img:
                    for actual, expected in zip(img.size, screen['size']):
                        # Browser raster crops round both fractional box edges outward.
                        self.assertLessEqual(abs(actual - expected), 2)
            saved = json.loads((self.work / folder / 'report.json').read_text(encoding='utf-8'))
            self.assertEqual(saved, report)
        self.assertGreater(desktop['screens'][0]['size'][0], mobile['screens'][0]['size'][0])
        self.assertGreater(mobile['screens'][0]['components'][1]['bbox'][3],
                           desktop['screens'][0]['components'][1]['bbox'][3])
        self.assertNotEqual((self.work / 'desktop/SettingsDefault.png').read_bytes(),
                            (self.work / 'desktop/SettingsSaving.png').read_bytes())

    def test_errors_prevent_captures(self):
        original = self.html.read_text(encoding='utf-8')
        cases = [
            ('duplicate', original.replace('id="SavingSave"', 'id="DefaultSave"'), 'Duplicate id'),
            ('missing', original.replace('id="DefaultSave"', ''), 'Component needs id'),
            ('overflow', original.replace('</html>', '<style>.screen {width:100px} input {width:800px}</style></html>'), 'Overflow'),
            ('script', original.replace('</html>', '<script>document.body.remove()</script></html>'), 'Non-static'),
            ('remote', original.replace('</html>', '<img src="https://example.com/test.png"></html>'), 'Blocked external'),
            ('missing-css', original.replace('theme.css', 'absent.css'), 'Failed resource'),
            ('no-screen', '<!doctype html><p>Only commentary</p>', 'No [data-screen]'),
            ('hidden', original.replace('</html>', '<style>#SettingsDefault {display:none}</style></html>'), 'Hidden/empty'),
        ]
        for name, source, error in cases:
            with self.subTest(name=name):
                self.html.write_text(source, encoding='utf-8')
                result = self.capture(name=name)
                self.assertEqual(result['status'], 'FAIL')
                self.assertTrue(any(error in e for e in result['errors']), result['errors'])
                self.assertFalse(list((self.work / name).glob('*.png')))
                if name == 'script':
                    self.assertEqual(len(result['screens']), 2, 'Page script must not execute')

    def test_cli_exit_codes(self):
        script = str(SKILL / 'scripts/html_review.py')
        base = [sys.executable, script, str(self.html), '--out', str(self.work / 'cli')]
        self.assertEqual(subprocess.run(base, capture_output=True).returncode, 0)
        self.html.write_text('<p>No screen</p>', encoding='utf-8')
        self.assertEqual(subprocess.run(base, capture_output=True).returncode, 1)
        self.assertEqual(subprocess.run(base + ['--size', '0x800'], capture_output=True).returncode, 2)

    def script(self, name, *args):
        return subprocess.run([sys.executable, str(SKILL / 'scripts' / name), *map(str, args)], capture_output=True,
                              text=True, encoding='utf-8', errors='replace', cwd=self.work)

    def test_standalone_manifest_and_visual_diff(self):
        out = self.work / 'baseline'
        report = review(self.html, out, 390, 844, standalone=True)
        self.assertEqual(report['status'], 'PASS', report['errors'])
        screen = report['screens'][0]
        self.assertEqual(round(screen['size'][0]), 390, 'a standalone screen spans the viewport width')
        manifest = json.loads((out / screen['manifest']).read_text(encoding='utf-8'))
        self.assertEqual([c['id'] for c in manifest['components']],
                         ['SettingsDefault', 'DefaultDescription', 'DefaultEmail', 'DefaultSave'])
        self.assertEqual([c['depth'] for c in manifest['components']], [0, 1, 1, 1])
        self.assertIn('color-primary', manifest['tokens'])

        png = out / screen['screenshot']
        same = self.work / 'same.png'
        Image.open(png).save(same)
        result = self.script('visual_diff.py', png, same, '--manifest', out / screen['manifest'])
        self.assertEqual(result.returncode, 0, result.stdout)
        broken = Image.open(png).convert('RGB')
        x, y, w, h = next(c for c in manifest['components'] if c['id'] == 'DefaultSave')['bbox']
        from PIL import ImageDraw
        ImageDraw.Draw(broken).rectangle((x, y, x + w, y + h), fill=(255, 255, 255))
        broken.save(self.work / 'broken.png')
        result = self.script('visual_diff.py', png, self.work / 'broken.png', '--manifest', out / screen['manifest'])
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('DefaultSave', result.stdout)

    def test_render_job_matches_the_screen(self):
        report = review(self.html, self.work / 'm', 390, 844, standalone=True)
        screen = report['screens'][0]
        button = next(c for c in screen['components'] if c['id'] == 'DefaultSave')
        bbox = [round(v) for v in button['bbox']]
        job = {'input': 'design/review.html', 'format': 'html', 'screen': screen['id'], 'state': 'default',
               'view': {'zoom': 1, 'width': 390, 'visible': [0, 0, 390, round(screen['size'][1])]},
               'selection': [{'ref': 'DefaultSave', 'kind': 'Button', 'path': 'SettingsDefault>DefaultSave', 'bbox': bbox}],
               'outputs': [{'path': str(self.work / 'job.png'), 'scale': 1, 'highlight': True}]}
        result = self.script('svg_render.py', '--job', json.dumps(job))
        self.assertEqual(result.returncode, 0, result.stderr)
        with Image.open(self.work / 'job.png') as img:
            self.assertEqual(img.size, (390, round(screen['size'][1])))
            edge = img.convert('RGB').getpixel((bbox[0] + bbox[2] // 2, bbox[1]))
        self.assertEqual(edge, (255, 0, 170), 'the selection is outlined')

    def test_tokens_from_html_and_css(self):
        for source in (self.html, self.source / 'theme.css'):
            with self.subTest(source=source.name):
                result = self.script('tokens_export.py', source, '--format', 'json')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)['color-primary'], '#17634f')


if __name__ == '__main__':
    unittest.main(verbosity=2)
