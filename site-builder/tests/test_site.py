import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'site.py'


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        text=True,
        capture_output=True,
        check=False,
    )


class TemplateCliTests(unittest.TestCase):
    def test_list_templates_exposes_selection_metadata(self):
        result = run('list-templates')
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual({row['id'] for row in output['templates']}, {'static', 'browse', 'form', 'tool'})
        for row in output['templates']:
            self.assertTrue(row['semantic']['tasks'])
            self.assertTrue(row['strengths'])
            self.assertTrue(row['tradeoffs'])
            self.assertTrue(row['reject_conditions'])
            self.assertTrue(row['states'])
            self.assertTrue(row['validation_commands'])
            self.assertTrue(
                any('check-render.mjs' in command and '--contract' in command for command in row['validation_commands']),
                f"{row['id']} must declare a rendered task contract",
            )
            self.assertTrue((ROOT / 'tests' / 'contracts' / f"{row['id']}.json").is_file())

    def test_inspect_template_returns_one_complete_card(self):
        result = run('inspect-template', 'tool')
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output['id'], 'tool')
        self.assertIn('local-persistence', output['patterns'])
        self.assertIn('error', output['states'])

    def test_every_template_initializes_without_skipping_discovery(self):
        for template in ('static', 'browse', 'form', 'tool'):
            with self.subTest(template=template), tempfile.TemporaryDirectory() as folder:
                destination = Path(folder) / 'project'
                result = run('init', destination, '--template', template, '--title', '测试项目')
                self.assertEqual(result.returncode, 0, result.stderr)
                state = json.loads((destination / '.site' / 'state.json').read_text(encoding='utf-8'))
                self.assertEqual(state['stage'], 'discovering')
                self.assertTrue(state['visual_required'])
                self.assertFalse(state['development_authorized'])
                self.assertTrue((destination / 'web' / 'index.html').is_file())


if __name__ == '__main__':
    unittest.main()
