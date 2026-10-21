"""Scoped selection, leakage and split invariants on invented metadata."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_semantic_pilot import create_fixture
from smart_router.semantic_intake import write_jsonl
from smart_router.semantic_pilot import checked_bundle, finish_bundle, read_jsonl
from smart_router.semantic_scoped_data import prepare


class ScopedDataTests(unittest.TestCase):
    def test_scope_unknowns_and_input_evidence_separation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            intake, _ = create_fixture(root)
            out = root / 'scoped'
            with patch('smart_router.semantic_scoped_data.balanced_queue',
                       return_value=[{'record_id': 'alpha'}, {'record_id': 'beta'}]):
                prepare(intake, out, 1)
            checked_bundle(out, 'semantic-scoped-preparation-v1')
            rows = read_jsonl(out / 'episodes.pending.jsonl')
            self.assertEqual(len(rows), 3)
            for row in rows:
                self.assertNotIn('LEAK_SENTINEL', json.dumps(row['input']))
                self.assertEqual(len(row['input']['candidates']), 1)
                self.assertIn(row['customer_scope_id'], row['input']['candidates'][0]['text'])
                self.assertTrue(all(v is None for v in row['targets'].values()))
                self.assertTrue(all(v == 0 for v in row['observation_mask'].values()))
                self.assertFalse(row['training_eligible'])
            future = next(r for r in rows if r['record_id'] == 'future')
            self.assertEqual(future['split'], 'test')
            self.assertIsNone(future['pilot_split'])
            self.assertIn('LEAK_SENTINEL', (out / 'supervision_only.jsonl').read_text())
            with self.assertRaises(ValueError):
                prepare(intake, out)

    def test_duplicate_question_cannot_cross_splits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            intake, _ = create_fixture(root)
            rows = read_jsonl(intake / 'records.jsonl')
            rows[-1]['input']['question'] = rows[0]['input']['question']
            write_jsonl(intake / 'records.jsonl', rows)
            (intake / 'manifest.json').unlink()
            finish_bundle(intake, {'format': 'semantic-intake-v1', 'source_registry_sha256': 'fixture'})
            with self.assertRaisesRegex(ValueError, 'Cross-split'):
                prepare(intake, root / 'bad')


if __name__ == '__main__':
    unittest.main()
