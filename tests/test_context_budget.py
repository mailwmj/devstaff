import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('context_budget', ROOT / 'scripts' / 'context_budget.py')
context_budget = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(context_budget)


class ContextBudgetTests(unittest.TestCase):
    def test_new_project_runtime_path_stays_below_proxy_budget(self):
        result = context_budget.evaluate(ROOT)

        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['metric'], 'utf8_bytes_proxy_not_model_tokens')
        self.assertEqual(result['baseline_ref'], '681c43c')
        self.assertEqual(result['baseline_bytes'], 121_411)
        self.assertGreaterEqual(result['reduction'], 0.30)
        self.assertEqual(result['current_bytes'], sum(row['bytes'] for row in result['files']))
        paths = {row['path'] for row in result['files']}
        self.assertIn('templates/AGENTS.md', paths)
        self.assertNotIn('AGENTS.md', paths)


if __name__ == '__main__':
    unittest.main()
