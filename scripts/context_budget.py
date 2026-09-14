#!/usr/bin/env python3
"""Measure the conservative new-project context path as a byte proxy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


BASELINE_BYTES = 130_729
TARGET_REDUCTION = 0.30
RUNTIME_PATHS = (
    'AGENTS.md',
    'site-builder/SKILL.md',
    'site-brief/SKILL.md',
    'site-design/SKILL.md',
    'site-check/SKILL.md',
    'site-brief/references/discovery.md',
    'site-brief/references/brief.md',
    'site-brief/references/research.md',
    'site-brief/references/state.md',
    'site-design/references/design-context.md',
    'site-design/references/surface-brief.md',
    'site-design/references/prototype.md',
    'site-design/references/review-protocol.md',
    'site-builder/references/runtime.md',
    'site-builder/references/implementation.md',
    'site-check/references/verification.md',
)


def evaluate(root: Path) -> dict[str, object]:
    files = []
    for relative in RUNTIME_PATHS:
        path = root / relative
        if not path.is_file():
            raise ValueError(f'missing runtime context file: {relative}')
        files.append({'path': relative, 'bytes': len(path.read_bytes())})
    current = sum(row['bytes'] for row in files)
    reduction = (BASELINE_BYTES - current) / BASELINE_BYTES
    return {
        'status': 'passed' if reduction >= TARGET_REDUCTION else 'failed',
        'metric': 'utf8_bytes_proxy_not_model_tokens',
        'baseline_bytes': BASELINE_BYTES,
        'current_bytes': current,
        'maximum_bytes': int(BASELINE_BYTES * (1 - TARGET_REDUCTION)),
        'target_reduction': TARGET_REDUCTION,
        'reduction': round(reduction, 4),
        'files': files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', nargs='?', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        output = evaluate(args.root.resolve())
    except (OSError, ValueError) as error:
        print(json.dumps({'status': 'failed', 'error': str(error)}))
        return 2
    print(json.dumps(output, indent=2))
    return 0 if output['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
