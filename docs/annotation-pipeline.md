# Annotation pipeline

Implemented 2026-09-28. The first runner evaluates the **local next step**, using actual candidate calls and separate LLM judgments. It does not execute tools or replay downstream tasks. The [first live smoke batch](annotation-batch-001.md) used GPT-5.6 Sol and Terra with Astra judging, on two synthetic-source states. The original offline demonstration still uses canned responses.

## Evaluation design

```text
Prepared records, frozen episode/group splits       Versioned success contracts
               |                                             |
               v                                             |
       Runtime input only                                    |
               |                                             |
      +--------+---------+                                   |
      |        |         |                                   |
    FAST    GENERAL  REASONING                                |
      |        |         |                                   |
      +--------+---------+                                   |
               |                                             |
       Actual next-step outputs, repeated N trials            |
               |                                             |
               +--------------------+------------------------+
                                    |
                      Blinded, pointwise LLM judge(s)
                      Evaluate each response independently
                                    |
                     Unanimous verdict above confidence gate
                       /             |               \
                    PASS            FAIL           UNKNOWN
                                                  error, abstain,
                                                  disagreement
                       \             |               /
                         Evidence + review queue
                                    |
                  Per-class local success frequency + counts
                  Silver labels; original targets unchanged
                                    |
                       NEXT: replay and human audit
                       before downstream-success labels
```

The candidate models perform the task. They do not label themselves or imitate faster/weaker models. The judge assesses each candidate against the same contract, rather than treating the reasoning model's answer as ground truth or choosing only one winner. Several tiers may all pass.

The supplied live template maps `FAST` to `gpt-5.6-luna`, `GENERAL` to `gpt-6-sol`, and `REASONING` to `gpt-6-astra`. These are separate endpoint calls. This interactive assistant is not itself a persistent API endpoint. Account access must be verified before a live run. Official model references: [Astra](https://developers.openai.com/api/docs/models/gpt-6-astra), [Sol](https://developers.openai.com/api/docs/models/gpt-6-sol), [Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna).

Use a separate judge model, selected through `ANNOTATION_JUDGE_MODEL`. The runner rejects the same model identifier in candidate and judge roles, duplicate candidate deployment identities, and repeated copies of the same judge. Operators must still verify that different deployment aliases really refer to different weights. Different model names do not establish statistical independence. Human audit is needed to measure judge reliability.

## Run the offline example

No installation or credentials are needed:

```bash
python scripts/annotate.py plan --config configs/annotation/mock.json
python scripts/annotate.py run --config configs/annotation/mock.json --output runs/annotation-fixture-v2
# Same command resumes without repeating successful calls.
python scripts/annotate.py run --config configs/annotation/mock.json --output runs/annotation-fixture-v2
```

The example has two synthetic states, three candidate tiers, two trials and two judges: 12 candidate calls and 24 judge calls, all mocked. It demonstrates a 0.5 FAST local-success frequency and an unknown REASONING target where a judge abstains. Mock runs are explicitly marked `quality=synthetic`, never silver training data.

The installed entry point is `smart-router-annotate`; the module entry point is `PYTHONPATH=src python -m smart_router.annotation.cli`.

## Input contract and customer classes

Configuration paths resolve relative to the configuration file. Supply:

1. `records`: canonical JSONL from the dataset constructor, with stable IDs, runtime `input`, task identity, frozen split, group and existing targets. A bundle's split file or annotation queue can be used. Each example in this runner is one pre-call decision state, with the prior context needed to make that decision.
2. `task`: its `task.json`. This routing runner accepts `independent_binary` tasks. Class names are configurable; `FAST`, `GENERAL`, `REASONING` are examples, not hard-coded labels. Map exactly one concrete candidate to each class with `class_id`.
3. `contracts`: one JSONL record per example, with `example_id`, `version` and nonempty `required_conditions`. Optional reference material remains annotation-only. A domain expert should author/review these conditions before labeling; this script does not generate trustworthy contracts automatically.
4. `candidates` and `judges`: model endpoint definitions, generation settings and output caps. One or more judges can be configured. All configured judges must agree above the confidence threshold for an observed trial verdict.

Example success contract:

```json
{"example_id":"sample-001","version":"1.0","required_conditions":["Propose lookup_invoice for INV-42.","Do not modify records or claim an unobserved tool result."]}
```

Candidates receive only the canonical `input` projection and the common candidate system prompt. Put all runtime-visible tools, schemas, constraints and task context in that input. Labels, metadata, reference answers and annotation-only success criteria are excluded. The judge receives runtime input, success contract and candidate output, with no explicit tier/provider/model identity or split metadata. A response that names its own model, or identity text inside supplied data, can still reveal identity; blinding is not an anonymity guarantee.

The broader dataset constructor still supports customer single-label and multilabel classification. This particular annotation runner estimates model-route sufficiency; arbitrary category annotation would need a separate annotation strategy, rather than assigning one candidate model to each ordinary category.

## Live endpoint configuration

Copy and edit [models.example.json](../configs/annotation/models.example.json). It initially points to the two synthetic examples so the request format can be inspected. Replace the records, task and contracts with the agreed real pilot before collecting training evidence. The template requests three trials per candidate and one separate judge.

Set credentials in environment variables, not config files. `plan` needs a resolved judge model name but does not need API credentials or make requests. After endpoints and the paid-call budget are agreed:

```bash
python scripts/annotate.py plan --config configs/annotation/models.example.json
python scripts/annotate.py run --config configs/annotation/models.example.json --output runs/annotation-pilot-v1 --live
```

Alternatively set `api_key_file` to an existing credential file path (including `~/...`), exclusively with `api_key_env`. Only the path is frozen; the credential contents are read at request time and never recorded. The [three-candidate batch](annotation-batch-002.md) uses this mechanism for Cloudera authentication, Qwen over HTTP, and Terra/Sol/Astra through external agent receipts.

Use the `candidates` command with the same arguments as `run` to execute/cache candidates before dispatching external judges. It skips missing external candidate receipts without consuming budget. The later `run` command reuses those observations. For Qwen/vLLM, explicit `generation.chat_template_kwargs.enable_thinking` and `preserve_thinking` boolean options are supported; changing them requires a new run directory.

The built-in adapters support the [OpenAI Responses API](https://developers.openai.com/api/docs/guides/text) and a text-based `/v1/chat/completions` interface for local/vLLM serving. Model-specific generation options must be supported by the chosen endpoint; rejected requests become unknown observations. Responses API calls use `store=false`. The runner itself archives inputs and outputs locally, so keep its run directory in the intended customer storage.

To use a served Qwen model for FAST, replace the FAST entry with [qwen-candidate.example.json](../configs/annotation/qwen-candidate.example.json), setting `QWEN_SERVED_MODEL`, `QWEN_BASE_URL` and `QWEN_API_KEY`. The model value must match the server's actual served identifier. This does not assume a particular Qwen checkpoint is installed or deploy it. Use HTTPS or a localhost HTTP tunnel. Model-native tool calls are not yet supported: candidate actions must be rendered as text/JSON and are not executed.

There are no implicit network retries. Set `--retry-errors` on a resume to retry cached transport/provider errors once per invocation, up to `max_attempts_per_call`. Invalid judge text is retained as review evidence; it is not silently retried until a desired verdict appears. Contract/prompt/config/input changes require a new output directory.

## What a probability means

Each route is an independent success target, not an exclusive winner or a difficulty rank. A REASONING failure is recorded exactly like another candidate's failure; its output is not the reference answer. For example, FAST/GENERAL/REASONING observations can be `[1, 1, 0]`, and all three can fail, giving `[0, 0, 0]`. Retain such valid negative observations. Endpoint errors and unresolved judge uncertainty stay null and are masked, not converted to zero. Review all-failure cases for a broken snapshot or contract before promoting them to training.

One failed trial is a binary observation, not evidence that the true success probability is zero. Collect a fixed number of repeated trials per candidate, retaining every result rather than retrying task failures until a pass appears. For example, three passes and two failures give an empirical estimate of 0.6 from five valid trials. Serving retries replace missing observations; they do not count as extra successful trials. Confidence intervals reflect sampling uncertainty, while judge reliability needs separate audit.

For future training, use one sigmoid output per route with a masked independent-binary loss; a softmax would incorrectly force the probabilities to sum to one and cannot represent all routes failing. The serving policy should be able to abstain or escalate when no route meets its required reliability threshold. An all-zero observed vector motivates reviewing that fallback; it does not prove every future attempt will fail. Neither this training loss nor the fallback policy is implemented by the annotation runner.

For each state and candidate class:

```text
p_local_success = passed_trials / (passed_trials + failed_trials)
```

Publish that estimate only when `min_valid_trials` is reached. The default requires all requested trials. An error, judge abstention, low confidence or disagreement is unknown, never a failed task. If you lower the minimum, review missingness bias: the observed subset may not represent all trials.

These independent per-class probabilities **do not sum to one**. A judge confidence of 0.9 is not a 90% candidate-success label. With one trial, the observed label can only be 0 or 1; three trials produce 0, 1/3, 2/3 or 1, not well-calibrated probabilities. Counts and Wilson intervals are retained to show limited evidence. Those intervals assume independent Bernoulli trials and do not measure judge bias or across-task generalization. Repeating a deterministic request does not add independent information. Choose generation settings that reflect production behavior and estimate reliability across more states.

`silver_labels.jsonl` stores these estimates and full trial references. `annotated.jsonl` adds them under `label_evidence.local_step_annotation`; it preserves original `targets`, runtime input and split assignments. This is deliberate: the existing routing target includes downstream success, which a local judge cannot verify. Training on local silver labels requires an explicit task definition and promotion step; that exporter is not implemented yet. Human-adjudicated held-out examples and executable continuations remain necessary before claiming downstream routing quality.

## Run artifacts and limits

For model executions performed through session agent tools, `api=external` imports request-bound JSON receipts from `response_directory`, resolved relative to the configuration file. Receipts include the request hash, requested model, output, tool/task provenance and model override. The importer validates identity and requires `--live`, but needs no HTTP credentials. `external_key(model, body, context)` defines request binding. Prompt text can be set through `candidate_system` and `judge_system` and is frozen into the run hash. See the batch-001 configuration and receipts for a concrete example.

External import is deliberately distinct from `mock`. It records import latency separately and does not invent inference latency, usage or actual serving revision. The usual call/output-token caps limit imports only, not the cost or token usage of agent executions that already happened. This adapter does not itself spawn agents. Synthetic source records remain explicitly marked even when candidate and judge responses are real.

| Artifact | Purpose |
|---|---|
| `run.json`, `inputs.json` | Hash/version and frozen task, records, contracts, config and exact prompts |
| `attempts.jsonl` | Durable pre-call reservations; interrupted calls still count against the budget |
| `calls/*.json` | Candidate/judge outputs, errors, actual/requested model, latency, usage and attempt history |
| `annotated.jsonl` | Original records plus separate local annotation evidence |
| `silver_labels.jsonl` | Local probability estimates, counts, uncertainty and evidence references |
| `review_queue.jsonl` | Unknown trials with reasons and judge/candidate call references |
| `report.json` | Coverage, unknown counts and budget consumption |

Call IDs include model configuration, exact request body, trial identity and pipeline version. A run hash also freezes contracts, source records and mock fixtures. No mock/live mixing is allowed. Successful results are reused on resume. A lock prevents concurrent writers; after a killed process, verify it has stopped before deleting its stale `run.lock`. A crash after a provider receives a request but before local persistence may require a repeat call; the original attempt remains budgeted. This is not an exactly-once network guarantee.

`max_calls` and `max_reserved_output_tokens` are hard run caps, including retries. Reserved output tokens are a conservative request allowance, not actual billed tokens. Input tokens, model prices and reasoning-token billing still need a concrete cost forecast; there is no currency cap or tokenizer/context-fit preflight yet. For 300 states × 3 candidates × 1 trial × 1 judge, allow up to 900 candidate + 900 judge calls before retries. Three trials raise this to 2,700 + 2,700. Begin with 10 real states to inspect judgments and measured usage.

The runner is sequential and in-memory for this pilot. Distributed Ray annotation, executable checks/replay, native tools, automated adjudication, calibrated judge reliability and silver-to-training export remain subsequent work. It does not touch sibling deployments or launch model instances.
