"""Validate generation-quality scenarios and versioned run evidence."""
import argparse
import hashlib
import json
import re
import statistics
import sys
from pathlib import Path


QUALITY_DIMENSIONS = (
    'task_scope_correctness',
    'direction_traceability',
    'project_specificity',
    'visual_craft',
    'state_mobile_reopen_resilience',
)
SKILLS = ('site-brief', 'site-design', 'site-builder', 'site-check')
REQUIRED_SCENARIOS = tuple(
    [f'SD-{index:02d}' for index in range(1, 18)]
    + [f'MV-{index:02d}' for index in range(1, 9)]
)
HASH = re.compile(r'^[0-9a-f]{64}$')
ROOT = Path(__file__).resolve().parent.parent


def scenario_metadata(root=ROOT):
    catalog = json.loads((root / 'tests' / 'scenarios.json').read_text(encoding='utf-8'))
    return catalog['suite_version'], {
        row['id']: hashlib.sha256(row['fixed_input'].encode()).hexdigest()
        for row in catalog['scenarios']
    }


def fixture_digest(folder):
    digest = hashlib.sha256()
    for path in sorted(item for item in folder.rglob('*') if item.is_file() and item.name != '.DS_Store'):
        digest.update(path.relative_to(folder).as_posix().encode())
        digest.update(b'\0')
        digest.update(path.read_bytes())
        digest.update(b'\0')
    return digest.hexdigest()


def fixture_lock(root):
    fixture_root = root / 'tests' / 'fixtures'
    return {
        path.name: fixture_digest(path)
        for path in sorted(fixture_root.glob('F-*'))
        if path.is_dir()
    }


def validate_catalog(root):
    errors = []
    scenario_path = root / 'tests' / 'scenarios.json'
    lock_path = root / 'tests' / 'fixtures.lock.json'
    if not scenario_path.is_file():
        return ['tests/scenarios.json is missing']
    if not lock_path.is_file():
        return ['tests/fixtures.lock.json is missing']
    try:
        catalog = json.loads(scenario_path.read_text(encoding='utf-8'))
        locked = json.loads(lock_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as error:
        return [f'evaluation JSON is invalid: {error}']
    scenarios = catalog.get('scenarios') if isinstance(catalog, dict) else None
    if catalog.get('schema_version') != 1 or not isinstance(scenarios, list):
        return ['scenarios.json must contain schema_version=1 and scenarios[]']
    ids = [row.get('id') for row in scenarios]
    if len(ids) != len(set(ids)):
        errors.append('scenario ids must be unique')
    missing = [identifier for identifier in REQUIRED_SCENARIOS if identifier not in ids]
    extra = [identifier for identifier in ids if identifier not in REQUIRED_SCENARIOS]
    if missing: errors.append(f'missing scenarios: {", ".join(missing)}')
    if extra: errors.append(f'unknown scenarios: {", ".join(map(str, extra))}')
    fixtures_used = set()
    for row in scenarios:
        identifier = row.get('id', 'unknown')
        for field in ('title', 'fixture', 'fixed_input', 'coverage', 'observations'):
            if not row.get(field): errors.append(f'{identifier} needs {field}')
        fixture = row.get('fixture')
        if fixture:
            fixtures_used.add(fixture)
            path = root / 'tests' / 'fixtures' / fixture
            if not path.is_dir(): errors.append(f'{identifier} fixture is missing: {fixture}')
    current = fixture_lock(root)
    if locked.get('schema_version') != 1 or not isinstance(locked.get('fixtures'), dict):
        errors.append('fixtures.lock.json must contain schema_version=1 and fixtures{}')
    else:
        expected = locked['fixtures']
        if current != expected: errors.append('fixture lock differs; inspect changes, then run evaluate.py lock-fixtures')
        for fixture in fixtures_used:
            if fixture not in expected: errors.append(f'fixture is not locked: {fixture}')
    return errors


def _evaluation_errors(row, index):
    errors = []
    prefix = f'evaluations[{index}]'
    evaluator = row.get('evaluator') if isinstance(row, dict) else None
    if not isinstance(evaluator, dict) or not evaluator.get('kind') or not evaluator.get('identity'):
        errors.append(f'{prefix} needs evaluator kind and identity')
    core = row.get('core_task') if isinstance(row, dict) else None
    if not isinstance(core, dict) or core.get('status') not in ('passed', 'failed', 'not_run') or not core.get('evidence'):
        errors.append(f'{prefix}.core_task needs status and evidence')
    dimensions = row.get('dimensions') if isinstance(row, dict) else None
    if not isinstance(dimensions, dict):
        errors.append(f'{prefix}.dimensions is required')
        return errors
    for name in QUALITY_DIMENSIONS:
        value = dimensions.get(name)
        if not isinstance(value, dict):
            errors.append(f'{prefix}.dimensions.{name} is required')
            continue
        score = value.get('score')
        if not isinstance(score, int) or not 0 <= score <= 4:
            errors.append(f'{prefix}.dimensions.{name}.score must be an integer 0..4')
        if not value.get('evidence'):
            errors.append(f'{prefix}.dimensions.{name}.evidence is required')
    return errors


def quality_score(record):
    scores = []
    for evaluation in record.get('evaluations') or []:
        if not isinstance(evaluation, dict):
            continue
        for name in QUALITY_DIMENSIONS:
            value = (evaluation.get('dimensions') or {}).get(name) or {}
            if isinstance(value.get('score'), int): scores.append(value['score'])
    return statistics.fmean(scores) if scores else 0.0


def validate_run(record, full=False):
    errors = []
    if not isinstance(record, dict) or record.get('schema_version') != 1:
        return {
            'errors': ['run must be a schema_version=1 object'],
            'evaluation_complete': False,
            'release_ready': False,
            'full_ready': False,
        }
    for field in ('run_id', 'scenario_id', 'suite_version'):
        if not record.get(field): errors.append(f'{field} is required')
    scenario_id = record.get('scenario_id')
    if scenario_id not in REQUIRED_SCENARIOS:
        errors.append('scenario_id is not in the fixed suite')
    try:
        expected_suite, fixed_inputs = scenario_metadata()
    except (OSError, KeyError, json.JSONDecodeError) as error:
        errors.append(f'cannot load fixed scenario metadata: {error}')
        expected_suite, fixed_inputs = None, {}
    if expected_suite and record.get('suite_version') != expected_suite:
        errors.append(f'suite_version must match scenarios.json ({expected_suite})')
    skills = record.get('skills') or {}
    for name in SKILLS:
        value = skills.get(name)
        if not isinstance(value, dict) or not value.get('version') or not value.get('path') or not HASH.match(str(value.get('sha256', ''))):
            errors.append(f'skills.{name} needs version, path, and sha256')
    fixed_input_sha256 = str(record.get('fixed_input_sha256', ''))
    if not HASH.fullmatch(fixed_input_sha256):
        errors.append('fixed_input_sha256 must be a lowercase SHA-256')
    elif scenario_id in fixed_inputs and fixed_input_sha256 != fixed_inputs[scenario_id]:
        errors.append('fixed_input_sha256 does not match the catalog fixed input')
    environment = record.get('environment') or {}
    if not isinstance(environment, dict) or not isinstance(environment.get('model'), str) or not environment['model'].strip():
        errors.append('environment.model must be a non-empty string')
    tools = environment.get('tools') if isinstance(environment, dict) else None
    if not isinstance(tools, dict) or not tools or any(
        not isinstance(name, str) or not name.strip() or not isinstance(version, str) or not version.strip()
        for name, version in (tools or {}).items()
    ):
        errors.append('environment.tools must be a non-empty object of tool names to versions or conditions')
    selection = record.get('selection') or {}
    if not isinstance(selection.get('profile'), dict): errors.append('selection.profile is required')
    for field in ('candidates', 'selected', 'rejected'):
        if not isinstance(selection.get(field), list): errors.append(f'selection.{field} must be a list')
    artifacts = record.get('artifacts') or {}
    for field in ('outputs', 'screenshots'):
        values = artifacts.get(field)
        if not isinstance(values, list) or not values or any(not isinstance(value, str) or not value.strip() for value in values):
            errors.append(f'artifacts.{field} must be a non-empty list of evidence paths')
    cost = record.get('cost') or {}
    for field in ('input_tokens', 'output_tokens', 'duration_ms'):
        if not isinstance(cost.get(field), int) or cost[field] < 0: errors.append(f'cost.{field} must be a non-negative integer')
    evaluations = record.get('evaluations')
    if not isinstance(evaluations, list) or not evaluations:
        errors.append('evaluations must contain at least one evaluator result')
        evaluations = []
    for index, row in enumerate(evaluations): errors.extend(_evaluation_errors(row, index))
    if not isinstance(record.get('vetoes'), list): errors.append('vetoes must be a list')
    if not isinstance(record.get('not_run'), list): errors.append('not_run must be a list')

    human_ids = {
        row.get('evaluator', {}).get('identity')
        for row in evaluations
        if isinstance(row, dict) and row.get('evaluator', {}).get('kind') == 'human'
    }
    human_ids.discard(None)
    zero_dimensions = [
        {'evaluator': row.get('evaluator', {}).get('identity'), 'dimension': name}
        for row in evaluations
        if isinstance(row, dict)
        for name in QUALITY_DIMENSIONS
        if (row.get('dimensions', {}).get(name) or {}).get('score') == 0
    ]
    evaluation_complete = not errors and len(human_ids) >= 2 and not record.get('not_run')
    release_ready = evaluation_complete and all([
        not record.get('vetoes'),
        not zero_dimensions,
        bool(evaluations) and all(row.get('core_task', {}).get('status') == 'passed' for row in evaluations),
        quality_score(record) >= 3,
    ])
    if full and not evaluation_complete:
        if len(human_ids) < 2: errors.append('full evaluation requires two distinct human evaluators')
        if record.get('not_run'): errors.append('full evaluation cannot contain not_run items')
    return {
        'errors': errors,
        'evaluation_complete': evaluation_complete,
        'release_ready': release_ready,
        'full_ready': release_ready,
        'quality_score': round(quality_score(record), 3),
        'zero_dimensions': zero_dimensions,
    }


def compare_run_sets(before, after, target=0.30):
    if not before or not after: raise ValueError('before and after run sets must not be empty')
    errors = []
    indexed = {}
    for label, runs in (('before', before), ('after', after)):
        identifiers = [row.get('scenario_id') if isinstance(row, dict) else None for row in runs]
        duplicates = sorted(
            {identifier for identifier in identifiers if identifiers.count(identifier) > 1},
            key=str,
        )
        if duplicates:
            errors.append(f'{label} contains duplicate scenario ids: {", ".join(map(str, duplicates))}')
        actual = set(identifiers)
        expected = set(REQUIRED_SCENARIOS)
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected, key=str)
            detail = []
            if missing: detail.append(f'missing {", ".join(missing)}')
            if extra: detail.append(f'unknown {", ".join(map(str, extra))}')
            errors.append(f'{label} scenario set must equal the fixed 25-scenario suite ({"; ".join(detail)})')
        indexed[label] = {
            row.get('scenario_id'): row for row in runs
            if isinstance(row, dict) and row.get('scenario_id') in REQUIRED_SCENARIOS
        }
        for index, row in enumerate(runs):
            result = validate_run(row, full=True)
            errors.extend(f'{label}[{index}]: {error}' for error in result['errors'])

    for scenario_id in sorted(set(indexed['before']) & set(indexed['after'])):
        baseline = indexed['before'][scenario_id]
        candidate = indexed['after'][scenario_id]
        for field in ('suite_version', 'fixed_input_sha256', 'environment'):
            if baseline.get(field) != candidate.get(field):
                errors.append(f'{scenario_id}: {field} differs between before and after')

    if errors:
        return {'status': 'failed', 'target': target, 'errors': errors}

    before_tokens = statistics.median(row['cost']['input_tokens'] for row in before)
    after_tokens = statistics.median(row['cost']['input_tokens'] for row in after)
    reduction = 0.0 if before_tokens == 0 else (before_tokens - after_tokens) / before_tokens
    before_quality = statistics.median(quality_score(row) for row in before)
    after_quality = statistics.median(quality_score(row) for row in after)
    new_vetoes = []
    for scenario_id in REQUIRED_SCENARIOS:
        earlier = {json.dumps(value, ensure_ascii=False, sort_keys=True) for value in indexed['before'][scenario_id].get('vetoes') or []}
        for value in indexed['after'][scenario_id].get('vetoes') or []:
            if json.dumps(value, ensure_ascii=False, sort_keys=True) not in earlier:
                new_vetoes.append({'scenario_id': scenario_id, 'veto': value})
    no_new_vetoes = not new_vetoes
    after_release_ready = all(validate_run(row)['release_ready'] for row in after)
    passed = (
        reduction >= target
        and after_quality >= before_quality
        and no_new_vetoes
        and after_release_ready
    )
    return {
        'status': 'passed' if passed else 'failed',
        'target': target,
        'errors': [],
        'before_median_input_tokens': before_tokens,
        'after_median_input_tokens': after_tokens,
        'input_token_reduction': round(reduction, 4),
        'before_median_quality': round(before_quality, 3),
        'after_median_quality': round(after_quality, 3),
        'no_new_vetoes': no_new_vetoes,
        'new_vetoes': new_vetoes,
        'after_release_ready': after_release_ready,
    }


def load_runs(path):
    value = json.loads(path.read_text(encoding='utf-8'))
    return value['runs'] if isinstance(value, dict) and 'runs' in value else value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('validate-catalog')
    validate = commands.add_parser('validate-run')
    validate.add_argument('run', type=Path)
    validate.add_argument('--full', action='store_true')
    compare = commands.add_parser('compare')
    compare.add_argument('before', type=Path)
    compare.add_argument('after', type=Path)
    compare.add_argument('--target', type=float, default=0.30)
    commands.add_parser('lock-fixtures')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent

    if args.action == 'validate-catalog':
        errors = validate_catalog(root)
        output = {'status': 'passed' if not errors else 'failed', 'errors': errors}
    elif args.action == 'validate-run':
        output = validate_run(json.loads(args.run.read_text(encoding='utf-8')), args.full)
        output['status'] = (
            'incomplete' if output['errors']
            else 'failed' if args.full and not output['release_ready']
            else 'passed'
        )
    elif args.action == 'compare':
        output = compare_run_sets(load_runs(args.before), load_runs(args.after), args.target)
    else:
        output = {'schema_version': 1, 'fixtures': fixture_lock(root)}
        (root / 'tests' / 'fixtures.lock.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        output = {'status': 'written', 'count': len(output['fixtures'])}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output.get('status') in ('passed', 'written') else 1


if __name__ == '__main__':
    raise SystemExit(main())
