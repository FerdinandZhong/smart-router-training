import json
from pathlib import Path
import tempfile
import unittest

from smart_router.semantic_intake import (
    bird_catalogs, checked_assets, digest, model_input, observed_tables,
    select_pilot, spider_catalog, propose_splits,
)


def schema():
    return {"db_id": "example", "table_names_original": ["items", "groups"],
            "table_names": ["items", "groups"],
            "column_names_original": [[-1, "*"], [0, "id"], [0, "group_id"], [1, "id"], [1, "part"]],
            "column_names": [[-1, "*"], [0, "id"], [0, "group id"], [1, "id"], [1, "part"]],
            "column_types": ["text", "number", "number", "number", "number"],
            "primary_keys": [1, 3], "foreign_keys": [[2, 3]]}


class SemanticIntakeTests(unittest.TestCase):
    def test_projection_excludes_oracle_even_if_accidentally_placed_in_input(self):
        record = {"input": {"question": "Which groups?", "confirmed_history": [], "catalog_snapshot": "v1",
                            "db_id": "oracle", "SQL": "SECRET", "evidence": "SECRET"},
                  "source": {"database_id": "oracle"}, "labels": {"gold": "SECRET"}}
        actual = model_input(record)
        self.assertEqual(set(actual), {"question", "confirmed_history", "catalog_snapshot"})
        self.assertNotIn("SECRET", json.dumps(actual))

    def test_composite_uniqueness_is_not_invented(self):
        model, _ = spider_catalog(schema())
        self.assertEqual(len(model["relationships"]), 1)
        composite = schema()
        composite["primary_keys"].append(4)
        model, audit = spider_catalog(composite)
        self.assertEqual(model["relationships"], [])
        self.assertEqual(len(audit["unresolved_relationships"]), 1)
        self.assertEqual(model["metrics"], [])

    def test_nested_tables_include_subqueries_and_set_operations(self):
        ast = {"from": {"table_units": [["table_unit", 0], ["sql", {"from": {"table_units": [["table_unit", 2]]}}]]},
               "except": {"from": {"table_units": [["table_unit", 1]]}}}
        self.assertEqual(observed_tables(ast), {0, 1, 2})

    def test_column_metadata_does_not_invent_keys_or_metrics(self):
        models = bird_catalogs({'kept|things|a"b': 'Source description', 'held_out|other|x': 'Do not import'}, {'kept'})
        self.assertEqual(set(models), {'kept'})
        self.assertEqual(models['kept']['relationships'], [])
        self.assertEqual(models['kept']['metrics'], [])
        self.assertNotIn('primary_key', models['kept']['datasets'][0])
        expr = models['kept']['datasets'][0]['fields'][0]['expression']['dialects'][0]['expression']
        self.assertEqual(expr, '"a""b"')

    def test_pilot_is_deterministic_and_cannot_become_approved(self):
        rows = []
        for source in ['a', 'b']:
            for index, db in enumerate(['db1', 'db1', 'db2']):
                rows.append({'record_id': f'{source}{index}', 'source': {'source_id': source, 'database_id': db},
                             'catalog_status': 'draft_available', 'proposed_split': 'train',
                             'input': {'question': source + ('duplicate' if db == 'db1' else 'different')}})
        selected = select_pilot(rows, 2)
        self.assertEqual(selected, select_pilot(list(reversed(rows)), 2))
        self.assertEqual(len(selected), 4)
        self.assertTrue(all(r['review_status'] == 'pending' and not r['training_eligible'] for r in selected))
        with self.assertRaises(ValueError):
            select_pilot(rows, 3)

    def test_changed_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            content = b'{"approved":false}'
            (root/'data.json').write_bytes(content)
            lock = {'assets': [{'name': 'data.json', 'sha256': digest(content), 'bytes': len(content)}]}
            self.assertEqual(set(checked_assets(lock, root)), {'data.json'})
            (root/'data.json').write_bytes(b'{"approved":true}')
            with self.assertRaises(ValueError):
                checked_assets(lock, root)

    def test_malformed_public_metadata_is_quarantined_with_evidence(self):
        issues = []
        models = bird_catalogs({'db|table|': 'missing name', 'db|table|id': 'identifier'}, {'db'}, issues)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]['source_key'], 'db|table|')
        self.assertEqual([f['name'] for f in models['db']['datasets'][0]['fields']], ['id'])

    def test_duplicate_inputs_across_sources_cannot_cross_splits(self):
        rows = [{'episode_group': group, 'source': {'database_id': group}, 'input': {'question': question}}
                for group, question in [('a', 'How many?'), ('b', ' how MANY? '), ('c', 'Different')]]
        propose_splits(rows, {})
        self.assertEqual(rows[0]['data_group_id'], rows[1]['data_group_id'])
        self.assertEqual(rows[0]['proposed_split'], rows[1]['proposed_split'])

    def test_review_quota_does_not_count_cross_source_duplicate_questions(self):
        rows = []
        for source, questions in [('a', ['shared', 'a_unique']), ('b', ['shared', 'b_unique', 'b_other'])]:
            for i, question in enumerate(questions):
                rows.append({'record_id': source+str(i), 'source': {'source_id': source, 'database_id': source},
                             'catalog_status': 'draft_available', 'proposed_split': 'train', 'input': {'question': question}})
        selected = select_pilot(rows, 2)
        by_id = {r['record_id']: r['input']['question'] for r in rows}
        self.assertEqual(len({by_id[r['record_id']] for r in selected}), 4)


if __name__ == '__main__':
    unittest.main()
