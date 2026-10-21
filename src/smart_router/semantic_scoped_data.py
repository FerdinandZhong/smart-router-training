"""Prepare customer-scoped selector episodes without approving weak supervision."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from smart_router.semantic_intake import digest, encoded, model_input, write_jsonl
from smart_router.semantic_pilot import (
    BM25, balanced_queue, checked_bundle, finish_bundle, metadata_units,
    read_jsonl, structure_stratum, unique, unit_id,
)


def prepare(intake: Path, output: Path, k: int = 32) -> dict:
    manifest = checked_bundle(intake, 'semantic-intake-v1')
    if output.exists() or k < 1:
        raise ValueError('Use a new output directory and positive candidate k')
    records = unique(read_jsonl(intake / 'records.jsonl'), 'record_id')
    evidence = unique(read_jsonl(intake / 'supervision_only.jsonl'), 'record_id')
    catalogs = unique(read_jsonl(intake / 'catalog_index.jsonl'), 'catalog_id')
    if set(records) != set(evidence):
        raise ValueError('Record and supervision coverage differ')
    groups, questions = {}, {}
    for row in records.values():
        for mapping, key in [(groups, row['data_group_id']),
                             (questions, ' '.join(row['input']['question'].casefold().split()))]:
            if key in mapping and mapping[key] != row['proposed_split']:
                raise ValueError('Cross-split group or duplicate question')
            mapping[key] = row['proposed_split']
    pilot = balanced_queue(records, evidence)
    pilot_ids = {r['record_id'] for r in pilot}
    pilot_groups = sorted({records[r]['data_group_id'] for r in pilot_ids},
                          key=lambda x: digest(x.encode()))
    dev = set(pilot_groups[:max(1, len(pilot_groups) // 5)])
    models, units, indices, snapshots = {}, {}, {}, {}
    for cid, catalog in catalogs.items():
        path = (intake / catalog['path']).resolve()
        if not path.is_relative_to(intake.resolve()):
            raise ValueError('Catalog path escapes intake')
        models[cid] = json.loads(path.read_text())
        units[cid] = metadata_units(cid, models[cid])
        snapshots[cid] = digest(encoded(models[cid]))
        indices[cid] = BM25([u for u in units[cid] if u['kind'] == 'table'])
    episodes, supervision, excluded = [], [], []
    for rid, row in sorted(records.items()):
        cid = row['episode_group']
        if cid not in models:
            excluded.append({'record_id': rid, 'reason': 'catalog_missing'})
            continue
        hits = indices[cid].rank(row['input']['question'], k)
        lookup = unique(units[cid], 'unit_id')
        projected = model_input(row)
        projected['catalog_snapshot'] = snapshots[cid]
        # No source SQL, source evidence, gold IDs, or gold-based candidate injection.
        projected['high_level_domain'] = None
        projected['candidates'] = [{key: lookup[h['unit_id']][key]
                                     for key in ('unit_id', 'kind', 'name', 'text', 'definition', 'dependencies')}
                                    for h in hits]
        episodes.append({'record_id': rid, 'data_group_id': row['data_group_id'],
                         'customer_scope_id': cid, 'split': row['proposed_split'],
                         'pilot_split': ('validation' if row['data_group_id'] in dev else 'train')
                             if rid in pilot_ids else None,
                         'input': projected, 'training_eligible': False,
                         'targets': {h['unit_id']: None for h in hits},
                         'observation_mask': {h['unit_id']: 0 for h in hits},
                         'acceptable_context_sets': None})
        names = evidence[rid]['observed_sql_tables']
        weak = None if names is None else [unit_id(cid, 'table', n) for n in names]
        if weak is not None and any(uid not in lookup for uid in weak):
            raise ValueError('Source SQL table absent from scoped metadata')
        found = {h['unit_id'] for h in hits}
        supervision.append({'record_id': rid, 'source': row['source'],
            'catalog_snapshot': snapshots[cid], 'source_evidence': evidence[rid],
            'structure_stratum': structure_stratum(evidence[rid]),
            'weak_sql_table_ids': weak,
            'missing_weak_table_ids': None if weak is None else sorted(set(weak)-found),
            'weak_complete_at_k': None if not weak else set(weak).issubset(found),
            'review_status': 'pending', 'label_scope': 'unreviewed_structural',
            'candidate_judgments': [{'unit_id': h['unit_id'], 'label': None, 'reason': None} for h in hits],
            'answerability': None, 'acceptable_context_sets': None,
            'conflicting_definition_ids': None, 'clarification_options': None,
            'model_input_allowed': False})
    output.mkdir(parents=True)
    (output / 'catalogs').mkdir()
    index = []
    for cid, model in sorted(models.items()):
        name = f'catalogs/{digest(cid.encode())[:20]}.json'
        (output / name).write_bytes(encoded(model))
        index.append({'customer_scope_id': cid, 'path': name, 'snapshot': snapshots[cid],
                      'scope_basis': 'source_database_proxy_not_verified_customer',
                      'high_level_domain': None, 'source_catalog': catalogs[cid]})
    write_jsonl(output / 'catalog_index.jsonl', index)
    write_jsonl(output / 'metadata_units.jsonl', [u for cid in sorted(units) for u in units[cid]])
    write_jsonl(output / 'episodes.pending.jsonl', episodes)
    write_jsonl(output / 'supervision_only.jsonl', supervision)
    write_jsonl(output / 'pilot.pending.jsonl', [e for e in episodes if e['record_id'] in pilot_ids])
    write_jsonl(output / 'excluded.jsonl', excluded)
    diagnostics = [s for s in supervision if s['weak_complete_at_k'] is not None]
    report = {'format': 'semantic-scoped-preparation-v1', 'status': 'pending_annotation_not_training_ready',
        'intake_manifest_sha256': digest((intake / 'manifest.json').read_bytes()),
        'source_registry_sha256': manifest['source_registry_sha256'],
        'episode_count': len(episodes), 'catalog_count': len(models), 'excluded_count': len(excluded),
        'pilot_count': sum(e['pilot_split'] is not None for e in episodes),
        'splits': dict(Counter(e['split'] for e in episodes)),
        'pilot_splits': dict(Counter(e['pilot_split'] for e in episodes if e['pilot_split'])),
        'candidate_k': k, 'candidate_method': 'within_catalog_bm25',
        'candidate_pairs': sum(len(e['targets']) for e in episodes),
        'training_eligible_count': 0,
        'weak_diagnostic': {'count': len(diagnostics),
            'complete_count': sum(s['weak_complete_at_k'] for s in diagnostics),
            'quality_claim_allowed': False},
        'limitations': ['Source databases approximate customers; no verified business-domain labels',
            'No dense/hybrid retrieval yet in this package', 'No gold candidate injection or negative labels inferred from SQL absence',
            'No reviewed semantic labels, metrics, SQL execution or physical schema verification',
            'Original group splits preserved; semantic aliases still require review',
            'Pilot development uses only formal-train reserved groups',
            'Existing source-use restrictions remain applicable; no new redistribution license']}
    return finish_bundle(output, report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--intake', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--candidate-k', type=int, default=32)
    args = parser.parse_args()
    result = prepare(args.intake, args.output, args.candidate_k)
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}, indent=2))


if __name__ == '__main__':
    main()
