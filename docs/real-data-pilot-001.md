# Real-data pilot 001

Date: 2026-09-28. Active bundle: `data/prepared/swe-gym-pilot-v2`. Annotation configuration: `configs/annotation/real-pilot-001.json`. This is a data and annotation quality pilot; training has not started.

Later recovery and the remaining-state campaign are documented in [pilot continuation](real-data-pilot-002.md). This page retains the results of the original frozen run; the unknown-only recovery view has Qwen at two passes, seven failures and one unknown.

## Source and sampling

The source is [SWE-Gym/OpenHands-Sampled-Trajectories](https://huggingface.co/datasets/SWE-Gym/OpenHands-Sampled-Trajectories), recorded model rollouts on real GitHub issue tasks. These are public research trajectories, not customer production traces. The [SWE-Gym repository](https://github.com/SWE-Gym/SWE-Gym) documents the source project.

- Pinned dataset revision: `baf3a4e4bff514d48ddc08a93a2ade5c126212c7`.
- Source: first of three shards of the official `train.raw` split, 2,019 rows scanned.
- File: `data/raw/swe-gym-openhands-baf3a4e4/train.raw-00000-of-00003.parquet`.
- SHA-256: `29d038b0c34eb0e50a19730f3cf3daa5a156c2d7e9c871c01b568acbab6aae07`. The adapter rejects mismatched source bytes.
- Selected: 300 decision points, three per recorded episode, 100 distinct issues, ten repositories. Train/validation/calibration/test contain 210/30/30/30 states from 70/10/10/10 issues.
- First annotation subset: ten states from ten different issues and repositories; split coverage 7/1/1/1.

Selection uses seeded identity order, repository round-robin sampling, one recorded run per issue, and three spread-out eligible steps per run. It does not select on the historical resolved outcome. An eligible state has prior tool feedback, at least one past tool observation of 500 characters, and a complete serialized input at most 36,000 characters. These filters favor manageable, tool-rich contexts; the 500-character rule is a heuristic, and this is not a representative long-context benchmark. The initial `v1` extraction included too many empty-directory navigation prefixes and is archived unused; `v2` is active.

One row represents the full recorded prefix immediately before one assistant tool action. Source text is preserved, Arrow null padding is removed, and absent parameters on the no-argument finish tool become an empty-object schema. Historical next actions and later outcomes stay in `label_evidence.source_trace`; candidates and judges do not receive them. All states of an issue remain in one split. Exact source-prefix equality was verified for all 300 rows, along with all eleven bundle file hashes.

The dataset card does not declare a dataset license. The [repository's Apache-2.0 license](https://github.com/SWE-Gym/SWE-Gym/blob/main/LICENSE) is not asserted to cover every included dataset/code artifact. Source-term review remains a training release/redistribution gate. Every record currently has `eligible_for_training: false` and `runtime_replayed: false`.

## Annotation protocol

Candidates receive the frozen prefix, available tool schemas, and an explicit requirement to return exactly `{"tool":"name","arguments":{...}}`. This adapts serialization for comparison; native OpenHands tool-call generation and environment replay are not implemented. Historical commands are input data and are not executed by evaluation agents.

The three configured candidates are Qwen/Qwen3.6-35B-A3B-FP8 (FAST), GPT-5.6 Terra (GENERAL), and GPT-5.6 Sol (REASONING). Each completed candidate response receives an independent, fresh GPT-6 Astra judgment. Judge packets omit candidate identity, routing class, other candidate responses, deterministic-check results and historical outcomes.

Deterministic checks validate JSON, tool membership and arguments against the supplied JSON Schema. A schema failure forces a failed trial. Astra evaluates whether the proposed action is useful and grounded in the supplied evidence, respects prior errors, and avoids unsupported completion. It may abstain. No command, patch or test proposed by a candidate is executed; a local pass does not imply that execution or the whole task succeeds.

Terra, Sol and Astra execute through fresh session agents with `fork_turns: none` and explicit model overrides. Packet hashes and task names are preserved in external receipts. A surrounding file-read/write harness is needed to deliver packets and collect answers; this differs from the Qwen HTTP harness. Actual serving revisions, token usage, inference latency and exact sampling controls are not exposed for these session agents. External token limits in configuration are budget hints, not verified generation caps.

There is one trial per state/model. The saved per-class frequency is therefore 0 or 1 for an observed result, and null for an unknown result. These are initial silver observations with uncertainty intervals, not calibrated success probabilities. Class probabilities are independent and do not need to sum to one. Original training targets remain unknown.

## First ten-state results

| Candidate | Local passes | Local failures | Unknown |
|---|---:|---:|---:|
| FAST / Qwen | 1 | 6 | 3 |
| GENERAL / Terra | 8 | 2 | 0 |
| REASONING / Sol | 9 | 1 | 0 |

After the user rebooted Qwen, twenty-seven actual candidate responses and twenty-seven independent Astra judgments are saved. Twenty responses passed deterministic format/schema checks; seven failed. Astra passed nineteen and failed eight; the deterministic failure overrides one Astra pass, leaving eighteen overall passes and nine failures. These are single-trial local observations, not model capability rankings.

The failures are useful annotation audit cases:

- Terra, `150bc61096a15d853600`: called `finish` after a simplified reproduction without support for issue resolution or inability to continue. Astra marked it failed.
- Terra, `949637f89e967dfcdc8b`: proposed writing a Python module using a quoted printf command; Astra flagged backslash escaping that would produce invalid Python. This remains a judge-based semantic failure, not an observed execution result.
- Sol, `c9554d5a0788412c2937`: emitted an invalid JSON `\|` escape in a grep command. Astra incorrectly described the JSON as valid and passed it with 0.99 confidence. The JSON parser rejected it, so the final trial fails. This directly demonstrates why judge confidence cannot replace executable format checks.

Initially all ten Qwen requests returned HTTP 500, and even a 16-token health request returned `EngineCore encountered an issue`. Those original failed attempts remain archived. After the user's reboot, the short request returned `OK` in 2.61 seconds. All ten candidate requests were retried with unchanged inputs and generation settings. Seven returned complete text (10.11–11.89 seconds each); two timed out at the configured 120-second limit; one was rejected by the adapter with `response_incomplete_or_native_tool_call`. The adapter does not retain the rejected response body, so the last error cannot be narrowed further from saved evidence. These three labels remain null. No cluster changes were performed by this project.

Six Qwen responses failed the explicit JSON contract: prose instead of an action, Markdown fences/prose surrounding JSON, or trailing command tags. Astra independently marked all six failed. One schema-valid directory-view action passed Astra with 0.88 confidence. Raw responses are retained unchanged; no fence stripping or silent repair was applied. The seven complete Qwen responses report 57,812 prompt tokens and 529 completion tokens in total. This excludes failed/incomplete calls and health checks and is not total billed usage.

The run now has 67 recorded attempts: twenty Qwen HTTP attempts and forty-seven external response/judgment imports. Health diagnostics are outside that run ledger. Each Qwen request reached its two-attempt limit; this frozen run will not retry the three unknowns further. Reserved output tokens (109,568) are accounting limits, not observed usage or cost.

Verification: the existing 44-test suite passes; all 300 prefixes match source history; issue groups do not cross splits; all 47 external packet/receipt pairs match; original targets, input, metadata and splits remain unchanged; earlier Terra/Sol annotations are identical; resuming with backend calls disabled succeeds without new calls. `runs/real-pilot-001/verification.json` records these checks. Nine failure cases are in `failure_audit.jsonl` for human review; three unknown FAST trials are in `review_queue.jsonl`. Pre-recovery reports and labels are archived with `.before-qwen-recovery` suffixes. The other 290 states have not been annotated.

For the sample `c9554d5a0788412c2937`, the observed vector is `FAST=0, GENERAL=1, REASONING=0`: Qwen failed the format contract, Terra passed, and Sol emitted invalid JSON. REASONING is a candidate, not a reference answer or a guaranteed upper bound. Keep each candidate's observed label independently; do not force a monotonic tier ordering. If all candidates fail, preserve all three zero observations and review the snapshot/contract before promotion. Further fixed-count trials estimate variability; one failure does not establish a zero true success probability. See [label semantics](annotation-pipeline.md#what-a-probability-means).

## Artifacts and reproduction

Install optional dependencies with `pip install '.[parquet,annotation]'`. Download the pinned shard from the dataset's official repository, then use a new output directory:

```bash
python scripts/prepare_swe_gym_pilot.py \
  --source data/raw/swe-gym-openhands-baf3a4e4/train.raw-00000-of-00003.parquet \
  --output data/prepared/swe-gym-pilot-reproduction

python scripts/annotate.py plan --config configs/annotation/real-pilot-001.json
```

`scripts/annotation_packets.py` exports candidate/judge packets and imports actual external executions. Export manifests contain private request identities and must not be given to evaluation agents. Each agent reads only its designated public text packet. Importing a file records evidence; it does not itself run a model.

- `data/annotation/real-pilot-001/`: frozen ten-state inputs, task, contracts, packet manifests and Qwen diagnostic.
- `responses/real-pilot-001/`: original model answers.
- `receipts/real-pilot-001/`: request-matched external execution provenance.
- `runs/real-pilot-001/`: immutable call evidence, annotated rows, silver labels, unknown-trial review queue and report.

To resume existing evidence without retrying serving errors:

```bash
python scripts/annotate.py run --config configs/annotation/real-pilot-001.json \
  --output runs/real-pilot-001 --live
```

The recovery used `candidates ... --retry-errors`, followed by packet export, fresh Astra judgments, receipt import and reduction. Further retries now require an explicitly revised attempt policy and a new frozen run; the existing per-call limit has been reached. Existing judgments and candidate responses remain cached. Avoid `run --retry-errors` before required external judgment receipts exist: missing judgments would consume attempts.

## Next gate

Investigate Qwen response-format handling and the timeout/incomplete cases in a new versioned integration experiment before expanding annotation to all 300 states. If structured-output decoding or a production JSON repair layer is added, version that execution policy and assess it separately; do not retroactively change this batch's failures. Review semantic failures and audit passing judgments. Add fixed-count repeated trials to estimate variability and executable checks to establish action outcomes. This pilot's inspected holdouts cannot serve as an untouched final benchmark after prompt or contract tuning; reserve new issue groups for the later comparative training evaluation.
