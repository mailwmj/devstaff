import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('verify_skills', ROOT / 'scripts' / 'verify_skills.py')
verify_skills = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_skills)


class VerifySkillsTests(unittest.TestCase):
    def test_runtime_python_cache_is_not_treated_as_a_packaged_asset(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            skills = {}
            for name in verify_skills.EXPECTED_SKILLS:
                skill = root / name
                (skill / 'agents').mkdir(parents=True)
                (skill / '__pycache__').mkdir()
                skill_md = skill / 'SKILL.md'
                skill_md.write_text(
                    f'---\nname: {name}\ndescription: Use when testing {name}.\n---\n',
                    encoding='utf-8',
                )
                agent_yaml = skill / 'agents' / 'openai.yaml'
                agent_yaml.write_text('interface:\n  display_name: Test\n', encoding='utf-8')
                (skill / '__pycache__' / 'runtime.cpython-314.pyc').write_bytes(b'cache')
                files = {
                    path.relative_to(skill).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in (skill_md, agent_yaml)
                }
                (skill / 'manifest.json').write_text(
                    json.dumps({'name': name, 'version': '1.0.0', 'files': files}),
                    encoding='utf-8',
                )
                skills[name] = {'version': '1.0.0', 'dependencies': []}

            (root / 'skills.json').write_text(
                json.dumps({'version': '1.0.0', 'skills': skills}),
                encoding='utf-8',
            )

            self.assertEqual(verify_skills.Verification(root).run('skills.json'), 0)


if __name__ == '__main__':
    unittest.main()
