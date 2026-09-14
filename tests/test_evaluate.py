import hashlib
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('evaluate', ROOT / 'evaluate.py')
evaluate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluate)
CATALOG = json.loads((ROOT / 'scenarios.json').read_text(encoding='utf-8'))
FIXED_INPUTS = {row['id']: row['fixed_input'] for row in CATALOG['scenarios']}


def evaluation(identity='reviewer-a'):
    return {
        'evaluator': {'kind': 'human', 'identity': identity},
        'core_task': {'status': 'passed', 'evidence': ['core-task.json']},
        'dimensions': {
            name: {'score': 3, 'evidence': [f'{name}.md']}
            for name in evaluate.QUALITY_DIMENSIONS
        },
    }


def run_record(evaluations=None, scenario_id='SD-01', input_tokens=1000):
    return {
        'schema_version': 1,
        'run_id': f'run-{scenario_id.lower()}-v1',
        'scenario_id': scenario_id,
        'suite_version': CATALOG['suite_version'],
        'skills': {
            name: {'version': '1.0.0', 'sha256': 'a' * 64, 'path': name}
            for name in ('site-brief', 'site-design', 'site-builder', 'site-check')
        },
        'fixed_input_sha256': hashlib.sha256(FIXED_INPUTS[scenario_id].encode()).hexdigest(),
        'environment': {
            'model': 'test-model-1',
            'tools': {'browser': 'playwright-cli 0.1.17', 'host': 'test-host-1'},
        },
        'selection': {'profile': {}, 'candidates': [], 'selected': [], 'rejected': []},
        'artifacts': {'outputs': ['site/'], 'screenshots': ['desktop.png', 'mobile.png']},
        'cost': {'input_tokens': input_tokens, 'output_tokens': 500, 'duration_ms': 2500},
        'evaluations': evaluations or [evaluation()],
        'vetoes': [],
        'not_run': [],
    }


def full_run_set(input_tokens):
    return [
        run_record([evaluation('reviewer-a'), evaluation('reviewer-b')], scenario_id, input_tokens)
        for scenario_id in evaluate.REQUIRED_SCENARIOS
    ]


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
        self.assertTrue(complete['evaluation_complete'])
        self.assertTrue(complete['release_ready'])

    def test_failed_result_can_still_be_a_complete_evaluation(self):
        record = run_record([evaluation('reviewer-a'), evaluation('reviewer-b')])
        record['vetoes'] = ['generic visual direction']

        result = evaluate.validate_run(record, full=True)

        self.assertEqual(result['errors'], [])
        self.assertTrue(result['evaluation_complete'])
        self.assertFalse(result['release_ready'])

    def test_zero_in_any_quality_dimension_blocks_release_despite_a_high_average(self):
        evaluations = [evaluation('reviewer-a'), evaluation('reviewer-b')]
        for row in evaluations:
            for value in row['dimensions'].values():
                value['score'] = 4
        evaluations[0]['dimensions']['visual_craft']['score'] = 0

        result = evaluate.validate_run(run_record(evaluations), full=True)

        self.assertGreater(result['quality_score'], 3)
        self.assertTrue(result['evaluation_complete'])
        self.assertFalse(result['release_ready'])

    def test_token_comparison_requires_reduction_without_quality_regression(self):
        before = full_run_set(1000)
        after = full_run_set(600)
        result = evaluate.compare_run_sets(before, after, target=0.30)
        self.assertEqual(result['status'], 'passed')
        self.assertAlmostEqual(result['input_token_reduction'], 0.4)

    def test_token_comparison_rejects_different_scenarios_or_execution_conditions(self):
        before = full_run_set(1000)
        missing_scenario = evaluate.compare_run_sets(before, full_run_set(600)[:-1])
        self.assertTrue(any('scenario set' in error for error in missing_scenario['errors']))

        changed_environment = full_run_set(600)
        changed_environment[0]['environment']['model'] = 'different-model'
        environment_result = evaluate.compare_run_sets(before, changed_environment)
        self.assertTrue(any('environment differs' in error for error in environment_result['errors']))

    def test_run_rejects_a_hash_that_does_not_match_the_catalog_fixed_input(self):
        record = run_record()
        record['fixed_input_sha256'] = 'b' * 64

        result = evaluate.validate_run(record)

        self.assertTrue(any('fixed_input_sha256 does not match' in error for error in result['errors']))

    def test_malformed_evaluator_is_reported_instead_of_crashing_validation(self):
        result = evaluate.validate_run(run_record([None]), full=True)

        self.assertTrue(any('evaluations[0]' in error for error in result['errors']))
        self.assertFalse(result['evaluation_complete'])
        self.assertFalse(result['release_ready'])


if __name__ == '__main__':
    unittest.main()
