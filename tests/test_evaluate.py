import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('evaluate', ROOT / 'evaluate.py')
evaluate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluate)


def evaluation(identity='reviewer-a'):
    return {
        'evaluator': {'kind': 'human', 'identity': identity},
        'core_task': {'status': 'passed', 'evidence': ['core-task.json']},
        'dimensions': {
            name: {'score': 3, 'evidence': [f'{name}.md']}
            for name in evaluate.QUALITY_DIMENSIONS
        },
    }


def run_record(evaluations=None):
    return {
        'schema_version': 1,
        'run_id': 'run-sd01-v1',
        'scenario_id': 'SD-01',
        'suite_version': '1.0.0',
        'skills': {
            name: {'version': '1.0.0', 'sha256': 'a' * 64, 'path': name}
            for name in ('site-brief', 'site-design', 'site-builder', 'site-check')
        },
        'fixed_input_sha256': 'b' * 64,
        'selection': {'profile': {}, 'candidates': [], 'selected': [], 'rejected': []},
        'artifacts': {'outputs': ['site/'], 'screenshots': ['desktop.png', 'mobile.png']},
        'cost': {'input_tokens': 1000, 'output_tokens': 500, 'duration_ms': 2500},
        'evaluations': evaluations or [evaluation()],
        'vetoes': [],
        'not_run': [],
    }


class EvaluationTests(unittest.TestCase):
    def test_catalog_and_fixture_lock_are_complete(self):
        self.assertEqual(evaluate.validate_catalog(ROOT.parent), [])

    def test_partial_run_is_valid_but_not_full(self):
        result = evaluate.validate_run(run_record())
        self.assertEqual(result['errors'], [])
        self.assertFalse(result['full_ready'])

    def test_full_run_requires_two_distinct_human_evaluators(self):
        incomplete = evaluate.validate_run(run_record(), full=True)
        self.assertTrue(any('two distinct human' in error for error in incomplete['errors']))
        complete = evaluate.validate_run(run_record([evaluation('reviewer-a'), evaluation('reviewer-b')]), full=True)
        self.assertEqual(complete['errors'], [])
        self.assertTrue(complete['full_ready'])

    def test_token_comparison_requires_reduction_without_quality_regression(self):
        before = [run_record([evaluation('a'), evaluation('b')])]
        after_run = run_record([evaluation('a'), evaluation('b')])
        after_run['cost']['input_tokens'] = 600
        after = [after_run]
        result = evaluate.compare_run_sets(before, after, target=0.30)
        self.assertEqual(result['status'], 'passed')
        self.assertAlmostEqual(result['input_token_reduction'], 0.4)


if __name__ == '__main__':
    unittest.main()
