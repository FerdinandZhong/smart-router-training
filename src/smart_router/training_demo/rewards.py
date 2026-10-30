"""Strict final-answer reward; no eval(), judge calls, or answer in prompts."""
from decimal import Decimal, InvalidOperation
import re

def numeric_answer(text):
    match = re.search(r'####\s*([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\s*$',text)
    if not match:
        return None
    try:
        return Decimal(match.group(1).replace(',',''))
    except InvalidOperation:
        return None

def correctness_reward(completions, answer, **kwargs):
    if len(completions)!=len(answer):
        raise ValueError('Completion and answer counts differ')
    result=[]
    for completion,gold in zip(completions,answer):
        text=completion if isinstance(completion,str) else completion[-1]['content']
        predicted=numeric_answer(text)
        target=numeric_answer('#### '+str(gold))
        result.append(float(predicted is not None and target is not None and predicted==target))
    return result
