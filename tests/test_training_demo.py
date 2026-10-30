import unittest
from smart_router.training_demo.rewards import correctness_reward,numeric_answer
class DemoTests(unittest.TestCase):
 def test_correctness(self):
  self.assertEqual(correctness_reward(['reason\n#### 1,200','#### -2.50'],['1200','-2.5']),[1.,1.])
 def test_invalid_answers(self):
  for value in ['42','#### 4,2','#### 42 or 43','#### NaN','#### 1e3','#### 42 extra']:
   self.assertIsNone(numeric_answer(value),value)
 def test_wrong_and_missing(self):
  self.assertEqual(correctness_reward(['#### 3','no answer'],['2','2']),[0.,0.])
 def test_chat_completion(self):
  self.assertEqual(correctness_reward([[{'role':'assistant','content':'#### 7'}]],['7']),[1.])
 def test_length_mismatch(self):
  with self.assertRaises(ValueError):correctness_reward(['#### 1'],[])
if __name__=='__main__':unittest.main()
