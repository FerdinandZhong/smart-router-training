import unittest
from smart_router.data.gateway_dataset import select_states

class GatewayDatasetTests(unittest.TestCase):
    def sample(self, issue, position, repo='repo'):
        return {'group_id':issue,'example_id':f'{issue}-{position}', 'metadata':{'source_repo':repo}, 'input':{'text':f'{issue}-{position}'}}

    def test_selection_preserves_recorded_states_and_is_repeatable(self):
        pool={str(i):[self.sample(str(i),j) for j in range(8)] for i in range(10)}
        first=select_states(pool,20)
        self.assertEqual(first,select_states(pool,20))
        self.assertEqual(len(first),20)
        self.assertEqual(len({r['example_id'] for r in first}),20)
        self.assertTrue(all(r in pool[r['group_id']] for r in first))
        self.assertTrue(all(sum(r['group_id']==g for r in first)<=3 for g in pool))

    def test_duplicate_inputs_are_not_extra_samples(self):
        a=self.sample('a',0);b=self.sample('b',0);b['input']=a['input']
        with self.assertRaises(ValueError):select_states({'a':[a],'b':[b]},2)

    def test_repository_round_robin(self):
        pool={'a':[self.sample('a',i,'A') for i in range(4)],'b':[self.sample('b',i,'B') for i in range(4)]}
        self.assertEqual({r['metadata']['source_repo'] for r in select_states(pool,6)},{'A','B'})
