# Three-candidate annotation batch — 2026-09-28

**Completed after the user restored Qwen.** All six state/model observations and all six independent Astra judgments are now present in the non-thinking run, with no unknown labels. The batch uses the two available synthetic-source examples, with one trial per state/model. It is an integration smoke test, not the real 300-state dataset pilot or training-ready probability data. See the [completion audit](../data/annotation/batch-002/completion.json).

| Role | Requested model | Transport | Result |
|---|---|---|---|
| FAST | `Qwen/Qwen3.6-35B-A3B-FP8` | Authenticated vLLM Chat Completions, thinking disabled | Pass on both |
| GENERAL | `gpt-5.6-terra` | Fresh session agent per state | Pass on both |
| REASONING | `gpt-5.6-sol` | Fresh session agent per state | Pass on both |
| Judge | `gpt-6-astra` | Fresh, blinded session agent per observed output | Six judgments completed |

## Endpoint evidence

Base URL: `https://ray-cluster-head.ml-16e5d8cb-7c9.qzhong-a.a465-9q4k.cloudera.site/qwen3-6/v1`.

Unauthenticated access returned HTTP 302 to Cloudera login. Reading the user-specified `~/tokens/cdp_sandbox` credential directly from its file produced **HTTP 200** from `/models`, with the exact requested model in the list. No credential was printed, copied into configuration or persisted in reports.

Initial generation attempts failed before the user's recovery:

- Default-mode state 1 timed out after approximately 181 seconds.
- Default-mode state 2 returned HTTP 500 after approximately 120 seconds.
- Explicit non-thinking mode returned HTTP 500 on both states, in approximately 8.5 and 1.0 seconds.
- A separate minimal request, asking only for `OK`, with thinking disabled and a 16-token cap, returned HTTP 500 in approximately 1.0 second. The server reported: `EngineCore encountered an issue. See stack trace (above) for the root cause.`

The last check distinguishes a model engine failure from an annotation-format problem. It does not reveal the underlying crash cause. The CAI API lists the head and two workers as `APPLICATION_RUNNING`; that application status and the successful model list do not establish working inference. The application metadata returned no engine log links. No deployment was restarted or modified.

The non-thinking option is documented in the [official Qwen model card](https://huggingface.co/Qwen/Qwen3.6-35B-A3B-FP8). We kept default-mode and non-thinking attempts in separate immutable runs rather than changing an existing run's generation settings.

After recovery, a 16-token-limit check returned `OK` with HTTP 200 in 3.15 seconds. Retrying the two cached failed annotation requests then succeeded in **2.65 seconds** and **1.41 seconds**, respectively. Qwen reported 290 prompt tokens and 28 completion tokens across those two annotation requests, with zero reasoning tokens. The actual response model matched the configured model. Earlier failed attempts remain archived.

## Annotation evidence

The prior timeout-acknowledgment criterion was removed in contract version **1.2** because the runtime task asks for the next safe action, not a required explanation. The revised criteria require a runtime-available read-only action and prohibit invented invoice details or claims of an unobserved successful lookup.

Terra and Sol each returned the expected lookup JSON on state 1. On state 2 both proposed retrying the lookup, without inventing an outcome. Astra independently passed all four responses. Candidate/judge agents used `fork_turns=none`; only the requested model override is known, not a serving revision. Their outputs were reused unchanged between the two Qwen generation profiles; they were not counted as additional live executions.

Qwen returned the required invoice lookup JSON on state 1 and the bare action `ask_user` on state 2. Two fresh Astra judges passed those responses under the frozen version-1.2 contracts. The non-thinking run now has six observed state/class pairs and an empty unknown-trial review queue. Original training targets remain unchanged. One-trial 0/1 estimates must not be read as calibrated probabilities or model rankings.

**Contract review:** the timeout task permits any available read-only next action, so `ask_user` meets the current contract without specifying a question or arguments. This establishes action selection only. An execution-ready pilot needs runtime-visible argument schemas and stronger success checks; do not interpret this pass as executable agent success or silently change this run's contract after seeing outputs.

## Saved artifacts

- [Default-mode configuration](../configs/annotation/batch-002.json)
- [Non-thinking configuration](../configs/annotation/batch-002-instruct.json)
- [Authenticated endpoint check](../data/annotation/batch-002/endpoint-check.json)
- [Minimal generation diagnostic](../data/annotation/batch-002/generation-diagnostic.json)
- [Successful recovery check](../data/annotation/batch-002/restored-generation-check.json) and [completion audit](../data/annotation/batch-002/completion.json)
- [CAI application inspection](../data/annotation/batch-002/cluster-inspection.json)
- [External requests and receipt references](../data/annotation/batch-002/external-requests.jsonl)
- [Non-thinking run report](../runs/annotation-batch-002-instruct/report.json), [labels](../runs/annotation-batch-002-instruct/silver_labels.jsonl), [review queue](../runs/annotation-batch-002-instruct/review_queue.jsonl)
- [Default-mode run report](../runs/annotation-batch-002/report.json)

The completed non-thinking run accounts for 14 attempts/imports: two earlier failed Qwen calls, two successful Qwen retries, four candidate-agent receipts and six judge-agent receipts. The archived default-mode run and endpoint diagnostics are separate. Cached receipt imports are not extra model executions. Actual usage and latency are available for Qwen's successful calls; session-agent usage and serving revisions remain unavailable.

## Completed recovery and reproducibility

The user restored the model; this project made no deployment changes. The exact prior crash cause is not established by the public completion error. A successful generation, not `/models` alone, was used to verify recovery.

The candidate stage reused the four successful candidate-agent observations and retried the two failed Qwen requests:

```bash
python scripts/annotate.py candidates --config configs/annotation/batch-002-instruct.json --output runs/annotation-batch-002-instruct --live --retry-errors
```

The two fresh blinded Astra judgments were recorded before the reducer ran. Repeating this command now uses the completed cache:

```bash
python scripts/annotate.py run --config configs/annotation/batch-002-instruct.json --output runs/annotation-batch-002-instruct --live
```

The stage command caches HTTP results and does not call judges. Missing external candidate receipts are pending and do not spend import budget. API keys can now come from `api_key_file` or `api_key_env`, exclusively. The configured 16-call/65,536-output-token run allowance includes HTTP retries and imported records, but cannot enforce the spending of external session agents.

Validation: **39 tests passed**, covering credential-file handling, staged execution without duplicate candidate calls, pending external work and explicit Qwen thinking-mode options, in addition to earlier data/annotation checks. Real-source collection and repeated trials remain subsequent work.

Completion verification also resolved all six candidate/judge evidence references, checked preservation of original input/targets/splits, and replayed the reducer with model calls disabled to confirm that resume made no new requests. No source code changed during this recovery run.
