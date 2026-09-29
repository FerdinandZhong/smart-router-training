# First live annotation batch — 2026-09-28

Completed **eight real model executions** through this session's agent tools: four candidate responses and four independent Astra judgments. The underlying two examples are synthetic fixtures, not customer traces. This is a pipeline smoke batch and is **not eligible for training**.

## Models and execution

| Role | Requested model | Executions |
|---|---|---:|
| Candidate | `gpt-5.6-sol` | 2 |
| Candidate | `gpt-5.6-terra` | 2 |
| Judge | `gpt-6-astra` | 4 |

Only Sol and Terra were available as GPT-5.6 candidates through the exposed agent tool. GPT-5.6 Luna was not listed, and no API credentials were configured. This batch therefore used two candidates, rather than silently substituting a third model. Class IDs name the actual candidates; no speed/cost ranking was measured.

Every response and judgment used a fresh agent with `fork_turns=none`. Candidates received only the runtime task; judges received the runtime task, contract and one candidate output, with no candidate model identity. The common system/developer harness remains part of agent execution. No tools were invoked by those agents. Serving revisions, actual token usage, cost and inference latency were not exposed; requested model overrides and task identities are recorded, with `actual_model=null` rather than an invented server identifier.

## Observations

| Synthetic state | GPT-5.6 Sol | GPT-5.6 Terra |
|---|---|---|
| Read-only lookup of invoice INV-42 | Pass | Pass |
| Next safe action after lookup timeout | Pass | Fail under the current acknowledgment criterion |

Both candidates produced the requested lookup JSON on the first state. On the second state, both proposed another read-only lookup. Sol also explained that this was a retry after the timeout. Terra returned only the action and arguments. Astra marked Terra as failing the explicit contract requirement to acknowledge the timeout, with judge confidence 0.99.

**Review finding:** the runtime task asks for the next safe action, but does not explicitly request a timeout acknowledgment. Requiring acknowledgment may penalize an operationally correct action. Keep the original observed verdict, review the criterion, then version the contract and rejudge if it changes. Do not train on this example until that mismatch is resolved. The finding is recorded separately in [review.json](../data/annotation/batch-001/review.json); it is not an unknown/error verdict and therefore does not enter the runner's automatic unknown-trial queue.

The old synthetic fixture contained a note hinting that a judge should abstain. That mock-only note was removed before the live judgments; contract version `1.1` records the change. No pass/fail reference responses were shown to candidates or judges.

Each state/model combination has **one trial**. Exported 0/1 values are observed local success frequencies, not calibrated success probabilities. For a single pass, the Wilson 95% interval is approximately [0.207, 1]; for a single failure it is [0, 0.793]. Nothing here establishes a model ranking, downstream success or generalization to real tasks.

## Artifacts and reproduction

- [Batch configuration](../configs/annotation/batch-001.json)
- [Canonical records](../data/annotation/batch-001/records.jsonl), [task](../data/annotation/batch-001/task.json) and [contracts](../data/annotation/batch-001/contracts.jsonl)
- [Requests and receipt references](../data/annotation/batch-001/requests.jsonl)
- [Contract review](../data/annotation/batch-001/review.json)
- [Run report](../runs/annotation-batch-001/report.json), [labels](../runs/annotation-batch-001/silver_labels.jsonl) and [records with evidence](../runs/annotation-batch-001/annotated.jsonl)

Real tool responses are archived in `receipts/annotation-batch-001/`. The new `external` adapter imports these request-bound receipts through the same judge parsing, reduction, evidence and resume logic as HTTP runs. It never calls those receipts mock responses. Exact orchestration prompts and task names are retained. Receipt hashes provide integrity and request binding, not independent attestation of execution.

```bash
python scripts/annotate.py plan --config configs/annotation/batch-001.json
python scripts/annotate.py run --config configs/annotation/batch-001.json --output runs/annotation-batch-001 --live
```

These commands reimport/resume the completed observations. They do **not** spawn new agents or consume new model calls. For external execution, the runner's call/token reservations account for imports only; they cannot enforce spending or token limits on already completed agent calls.

Validation: **35 tests passed**, including receipt/request binding, model identity mismatch rejection, external import without API credentials, synthetic-source marking, preservation of unmeasured inference latency, and replay of this batch's recorded evidence.

Next data milestone: obtain real pre-call snapshots and runtime-visible success criteria, review the timeout criterion, then run a 10-state real-source batch with repeated trials. The 300-state pilot has not begun.
