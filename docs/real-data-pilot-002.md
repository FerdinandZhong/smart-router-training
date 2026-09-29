# Real-data pilot continuation

Updated 2026-09-28. The user authorized retrying the initial pilot's unknown Qwen responses and continuing the other pilot data. Source selection, classes, input projection, success contracts, Qwen generation settings and grouped splits are unchanged.

## Initial pilot recovery

`runs/real-pilot-001-retry3` preserves a further attempt on the three previously unknown states. Two returned text and received new blind Astra judgments: one passed and one failed the output contract. The third returned no text and remains unknown. Existing Terra/Sol responses and judgments were imported from their original receipts, without new model calls.

`runs/real-pilot-001-combined/silver_labels.jsonl` is an unknown-only recovery view: only previously unknown FAST observations are replaced, with the evidence's source run recorded per class. It does not overwrite the original run or count serving retries as independent trials. Current initial ten-state counts:

| Candidate | Pass | Fail | Unknown |
|---|---:|---:|---:|
| Qwen | 2 | 7 | 1 |
| Terra | 8 | 2 | 0 |
| Sol | 9 | 1 | 0 |

## Remaining 290 states

`data/annotation/real-pilot-002/manifest.json` freezes 29 batches of ten states each. All 290 IDs are unique and exclude the initial ten. Each record retains its original issue grouping and split. The campaign uses one trial per candidate, at most 870 candidate requests and 870 judgments before serving failures reduce judge coverage. Qwen runs sequentially; fresh CLI sessions run with concurrency three. No training or action replay occurs.

The new `scripts/annotation_campaign.py` prepares the queue, executes requests, validates receipts, and resumes from cached results. Each batch uses the existing annotation runner and produces the same call evidence, silver-label and unknown-review files. Completed batches are collected into `runs/real-pilot-002/silver_labels.jsonl`; these remain local-step silver evidence, not promoted training targets.

## Execution method and comparability

The first pilot used session-agent tools for Terra, Sol and Astra. The larger campaign uses the installed Codex CLI, following its [non-interactive execution documentation](https://learn.chatgpt.com/docs/non-interactive-mode). All three exact requested model names passed separate short access checks. Every candidate and every judge gets a new ephemeral session containing one packet; no prior session is resumed. Tools, apps, agent delegation, hooks and skill discovery are disabled where the CLI exposes those controls, and the sandbox is read-only. Any recorded tool execution causes receipt rejection. The model writes no answer file itself: the CLI captures its final response.

This is a versioned execution-method change, not an identical harness to pilot 001. The campaign manifest freezes its wrapper and execution policy. Receipts record the requested model override, session ID, complete packet hash, CLI event log, available usage and wall duration. Exact serving revision and a hard output-token generation cap are not exposed by this integration. The configured output-token amounts remain reservation hints for external imports, not verified CLI limits or billed costs. CLI wall duration includes startup overhead and is not comparable to Qwen inference latency.

The startup emits a known warning about `skip_host_skill_discovery`. Initially the transcript parser rejected that warning as unexpected activity; it now recognizes that exact warning while rejecting other errors and tool events. Completed responses were recovered from saved transcripts without re-executing the models. For those recovered transcripts, unarchived exit codes and durations remain unknown. New requests archive process status before parsing.

Candidate outputs are retained exactly, including invalid JSON. JSON/schema checks and blind Astra judgments determine observations. Unknown serving results and judge uncertainty remain masked. Task failures are not retried until a pass appears. External process failures stop the campaign with explicit status; a manual resume permits at most two CLI process attempts per packet, retaining the earlier logs.

## Commands and live progress

```bash
# Idempotent construction; refuses changes to frozen inputs/configurations.
python scripts/annotation_campaign.py prepare

# Foreground work; optional bounded verification batch.
python scripts/annotation_campaign.py work --limit-batches 1

# Continue all remaining batches with a detached worker and durable log.
python scripts/annotation_campaign.py work --detach

# Recompute coverage from completed batch artifacts.
python scripts/annotation_campaign.py status
```

Live files:

- `runs/real-pilot-002/worker.json`: current worker status or the error that stopped it.
- `runs/real-pilot-002/worker.log`: detached-worker stage and request progress.
- `runs/real-pilot-002/summary.json`: completed-state and observed/unknown-pair counts.
- `runs/real-pilot-002/batch-NNN/`: each batch's frozen inputs, calls, labels, review queue and report.
- `runs/real-pilot-002/cli-jobs/`: request-bound session transcripts and completion evidence.

An interrupted process can leave a lock. Confirm the recorded process has stopped before removing a stale lock; do not run concurrent campaign workers. A detached worker requires the local machine and network to remain available. It stops on CLI errors rather than silently substituting another model or discarding failed work.

The campaign is prepared for all 290 states. Its live summary distinguishes completed batches from queued work; preparation is not annotation completion. Inspect failures, missingness, judge errors and the changed CLI execution method before any training promotion or model comparison.

## Verified continuation checkpoint

The first continuation batch is complete: ten additional states, 29 observed state/model labels and one unknown. Qwen has two passes, seven failures and one request timeout. Terra and Sol each have ten passes. All 49 external candidate/judge receipts were verified against packet hashes and requested models; source inputs, targets, metadata and splits are unchanged; resuming with backend calls disabled made no new calls. The 51-test suite passes, including CLI event validation, tool-use rejection, completion recovery and frozen-file protection.

Together with the initial ten-state recovery view, this checkpoint covers twenty distinct states and 58 observed labels out of 60 possible pairs. A detached worker was then started for the remaining 28 batches (280 states). Consult the live status files for later progress; this paragraph records the launch checkpoint, not a claim that the full 300-state campaign has finished.
