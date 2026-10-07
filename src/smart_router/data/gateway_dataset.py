"""Freeze fresh recorded pre-call states for a versioned gateway annotation campaign."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path

from smart_router.data.prepare import assign_splits, digest, write_bundle
from smart_router.data.swe_gym import DATASET, REVISION, source_states
from smart_router.schemas import require, canonical_json

SHARDS = {
    'train.raw-00000-of-00003.parquet': '29d038b0c34eb0e50a19730f3cf3daa5a156c2d7e9c871c01b568acbab6aae07',
    'train.raw-00001-of-00003.parquet': '64a5d435b777a47e2544de1cc3bf61e5452bab1237fc43e70220e13f2f901516',
    'train.raw-00002-of-00003.parquet': '1e388384f0dbf65421b53ef37d4f92c10e1e458f597bf61326fa047b8e21b597',
}


def select_states(by_issue, count, seed=43, max_per_issue=3):
    """Round-robin repositories and spread positions; never select by outcomes."""
    repos = defaultdict(list)
    for issue, states in by_issue.items():
        if states:
            repos[states[0]['metadata']['source_repo']].append((issue, states))
    for values in repos.values():
        values.sort(key=lambda pair: digest([seed, pair[0]]))
    selected, hashes = [], set()
    while len(selected) < count:
        progress = False
        for repo in sorted(repos):
            if not repos[repo]:
                continue
            _, states = repos[repo].pop(0)
            size = min(max_per_issue, len(states), count - len(selected))
            positions = [round(i * (len(states) - 1) / max(1, size - 1)) for i in range(size)]
            for index in positions:
                row = states[index]
                key = digest(row['input'])
                if key in hashes:
                    continue
                hashes.add(key); selected.append(row); progress = True
            if len(selected) == count:
                break
        require(progress, 'Insufficient unique states; broaden source coverage rather than duplicating inputs')
    return selected


def construct(source_dir, old_pilot, output, mapping, count=1000, seed=43):
    import pyarrow.parquet as pq
    old = [json.loads(line) for path in Path(old_pilot).glob('*.jsonl') for line in path.read_text().splitlines() if line]
    excluded_issues = {r['group_id'] for r in old}
    excluded_inputs = {digest(r['input']) for r in old}
    require(not Path(output).exists(), 'Use a new dataset output directory')
    by_issue, ranks, sources = {}, {}, []
    for name, expected in SHARDS.items():
        path = Path(source_dir) / name
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        require(checksum == expected, f'Pinned source checksum mismatch: {name}')
        table = pq.ParquetFile(path)
        sources.append({'name': name, 'sha256': checksum, 'rows': table.metadata.num_rows})
        row_index = 0
        for batch in table.iter_batches(batch_size=16):
            for row in batch.to_pylist():
                index = row_index; row_index += 1
                issue = row['instance_id']
                if issue in excluded_issues:
                    continue
                priority = digest([seed, issue, row['run_id']])
                if issue in ranks and priority >= ranks[issue]:
                    continue
                states = [r for r in source_states(row, index) if digest(r['input']) not in excluded_inputs]
                if len(states) < 3:
                    continue
                for record in states:
                    record['metadata']['source_shard'] = name
                    record['provenance']['source_shard'] = name
                by_issue[issue], ranks[issue] = states, priority
    selected = select_states(by_issue, count, seed)
    settings = {'strategy': 'grouped', 'seed': seed, 'train': .7, 'validation': .1, 'calibration': .1, 'test': .1}
    task = {'task_id': 'agent_local_tool_sufficiency_gateway_v1', 'schema_version': '1.0',
            'kind': 'independent_binary', 'unit': 'agent_step', 'classes': [
                {'id': cls, 'description': f'{model} proposes a schema-valid, evidence-supported next tool action.'}
                for cls, model in mapping.items()]}
    for record in selected:
        record['dataset_id'] = 'gateway-pilot-v1'; record['task_id'] = task['task_id']
        record['targets']['values'] = dict.fromkeys(mapping)
        record['metadata']['candidate_mapping_version'] = 'gateway-pilot-v1'
    selected = assign_splits(selected, settings)
    source = {'dataset': DATASET, 'revision': REVISION, 'official_split': 'train.raw', 'shards': sources,
              'selection': 'One seeded eligible run per fresh issue; round-robin repositories; at most three spread-out states per issue; full recorded prefixes <=36000 JSON characters; no outcome-based selection',
              'excluded_prior_pilot_groups': sorted(excluded_issues), 'candidate_mapping': mapping,
              'license': 'Dataset card does not declare a license; upstream code license is not asserted to cover all dataset contents.',
              'release_gate': 'Local annotation research only; clarify dataset/source-code terms before training release or redistribution.'}
    config = {'customer_id': 'public_research', 'task': task, 'dataset': {'dataset_id': 'gateway-pilot-v1', 'split': settings}, 'annotation': {'mode': 'queue_missing'}}
    write_bundle(config, selected, source, Path(output))
    contract = {'version': 'swe-gym-local-v1', 'required_conditions': [
        'Return exactly one JSON object containing tool and arguments. The tool must be present in runtime tools, and its arguments must satisfy the supplied schema.',
        "Choose a useful next step for the user's issue, grounded in the complete supplied prefix. Respect explicit task constraints and recorded tool errors; do not blindly repeat a failed action without a supported change.",
        'Do not invent file contents, tool results, successful tests or task completion. If calling finish, the prefix must support completion or a concrete inability to proceed.',
        'Judge the proposed next action only, not whether an unexecuted command, patch, test, or whole episode will succeed. Abstain when semantic evidence is insufficient.'
    ]}
    root = Path(output)
    for name, rows in [('records.jsonl', selected), ('contracts.jsonl', [contract | {'example_id': r['example_id']} for r in selected])]:
        (root / name).write_text(''.join(canonical_json(r) + '\n' for r in rows))
    manifest = json.loads((root / 'manifest.json').read_text())
    for name in ['records.jsonl', 'contracts.jsonl']:
        manifest['files_sha256'][name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return {'states': len(selected), 'issues': len({r['group_id'] for r in selected}),
            'eligible_fresh_issues': len(by_issue), 'splits': {s: sum(r['split'] == s for r in selected) for s in ['train', 'validation', 'calibration', 'test']}}
