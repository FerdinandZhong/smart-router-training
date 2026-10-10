# Current work and priorities

## Isolated semantic-context research — 2026-10-10

This section belongs to `research/semantic-model-routing`.
The remaining implementation status reflects the committed branch base.
Current unfinished router experiments remain in the original `main` checkout.

- [x] Review recent schema retrieval, semantic-layer, and clarification literature.
- [x] Extend the [focused review](docs/research/semantic-model-routing/focused-literature-review.md)
  with trained embeddings, learned graph traversal, pooled catalogs, and benchmark construction.
- [x] Organize the [training and experiment brief](docs/research/semantic-model-routing/training-and-experiments-zh.md)
  and verify the pinned GLiNER2.5-Decide and Laya scoring paths.
- [x] Inspect Helios and UOB source boundaries and record evidence hashes.
- [x] Prepare a benchmark-first [research proposal](docs/research/semantic-model-routing/README.md)
  and [return handoff](docs/research/semantic-model-routing/return-to-main.md).
- [ ] Review the proposed annotation contract and independent evaluation families.
- [ ] Build deterministic retrieval baselines before training a semantic selector.
- [x] Consolidate the [no-graph, low-latency execution proposal](docs/research/semantic-model-routing/research-plan-zh.md)
  with annotation effort, staged decision gates, and separate context/end-to-end latency measurements.
- [ ] Compare trained embeddings and optional rerankers at equal semantic-context and latency budgets.
- [ ] Build a shared candidate pool and compare a conventional reranker, GLiNER2.5-Decide, and Laya with encoder adaptation.
- [ ] Evaluate newly added tables with frozen model weights; a new cost-aware loss remains outside scope.

## Original pilot gateway reannotation — 2026-10-06

- [x] Prepare all 300 original states with unchanged canonical inputs and splits;
  clear old labels and use the gateway candidate mapping and success contracts.
- [x] Verify Flash Lite, Luna and Sol with independent
  `global.anthropic.claude-sonnet-5` judgments on one state each.
- [ ] Complete 900 candidate responses and 900 Sonnet judgments; validate a new
  `pilot-300-gateway-sonnet-v1` bundle. Run started with resumable receipts.
- Recovery 2026-10-07: shared gateway allowance reset and a saved candidate retry
  succeeded. Resume at five requests/minute with increasing cooldowns; retain
  the three-attempt request limit and $75 estimated campaign ceiling.
- [ ] Review annotation quality and compare judge policies before combining with
  the 1,000-state gateway dataset. [Run guide](docs/pilot-300-gateway-sonnet.md).

Updated: 2026-10-07. This is the current milestone record. Older batch reports and
[implementation history](docs/IMPLEMENTATION_STATUS.md) retain historical evidence.
Live application states must be rechecked before operating the cluster.

## Completed

- [x] Management API Ray Jobs routes and Swagger submission example implemented;
  authenticated reads and admin-only submission/stop. Deployed in place; live
  submission/status/logs passed a CPU diagnostic. See
  [dated deployment evidence](docs/status/2026-09-30-management-jobs-api.md).
- [x] Training dependency extra includes Ray Jobs SDK dependencies; setup checks
  their availability before declaring the environment ready.

- [x] Configurable customer classes; JSONL/CSV/optional Parquet ingestion,
  hard/soft/partial labels, audits and grouped splits.
- [x] Candidate/judge annotation with deterministic action checks, resumable
  receipts, bounded retries, unknown handling and review artifacts.
- [x] Frozen 300-state pilot: 100 issue groups, 846 observed targets, 54 unknowns;
  split sizes 210/30/30/30. See the [manifest](data/pilot/pilot-smoke-v1/manifest.json).
- [x] Self-contained AMP with pinned Ray code, isolated environments and
  notebook-safe setup wrappers.
- [x] CPU Ray head running in the training CAI project.
- [x] TensorBoard CAI application running, confirmed by application API and user;
  loopback binding, built training venv and AMP launch job implemented.
- [x] TorchTrainer infrastructure diagnostic, checkpoint resume and per-step
  TensorBoard events implemented. Local two-process CPU/Gloo validation passed.
- [x] Local verification on 2026-10-07: 104 pytest tests and 36 subtests passed
  on Python 3.13.9. AMP dataset/vendor validation and archive build passed.
  Earlier real local TensorBoard HTTP/scalar verification remains dated evidence.
- [x] Networking scripts accept a virtualenv Python path, use isolated Python and
  check PyTorch, CUDA and collective backends on both pods before network changes.
  Live two-node GPU/NCCL training passed on 2026-09-30.
- [x] Two L40S GPU workers running, each exposing 12 CPUs and one GPU in Ray;
  live TorchTrainer initial/resume smoke passed.

## P0 — live distributed infrastructure validation

- [x] Both GPU workers joined Ray and expose one GPU each. Verified 2026-09-30:

  | Worker | CAI application ID | Pod |
  |---|---|---|
  | training-l40s-01 | he32-tc8t-yfw0-nyau | 3dum97s5gbv0vfk7 |
  | training-l40s-02 | uaar-s9qw-y267-c13y | 2tjmee7powvhaqea |

- [x] User applied the scoped networking patch; the actual training run confirmed
  cross-node NCCL Socket collectives. Standalone TCPStore/Gloo/NCCL probe reports
  were not independently retrieved.
- [x] `cluster-smoke-gpu-001` SUCCEEDED: distinct Ray nodes, matching dataset hashes,
  synchronized finite updates, checkpoint resume from step 20 to 22,
  reload checkpoint and `SUCCESS.json` verified.
- [x] TensorBoard lists the actual smoke's initial/resume loss, learning-rate and
  step-time tags, separate from the synthetic setup event.
- [ ] Archive the administrator's namespace/context and standalone networking
  probe/rollback evidence. Pod names are recorded above; namespace/context were
  not returned by the management API.

See [live GPU evidence](docs/status/2026-09-30-gpu-smoke.md). The validated model
is the controlled linear diagnostic; decision-model training remains P1.

## P1 — first decision-model training trial

- [x] Pinned differentiable Laya typed-binary head verified on two L40S workers;
  finite nonzero gradients, changed/synchronized weights and BF16 confirmed.
- [x] Independent-binary heads/losses and class order derive from task configuration;
  five-class CPU fixture passes. Single-label/multilabel training recipes remain
  outside this adapter's supported scope.
- [x] Short real pilot trial `laya-first-trial-20261001-001` SUCCEEDED: 20 steps,
  full validation split, fresh head reload and resume to step 22. Calibration/test
  were held out from training and selection. Both GPUs were released afterward.
  See [dated Laya evidence](docs/status/2026-10-01-laya-first-trial.md).
- [x] Full Laya pilot `laya-pilot-20261001-001` SUCCEEDED on 2026-10-01: three
  complete epochs / 474 updates, 2,048-token views, full coverage and synchronized
  weights, validation-selected epoch 1, fresh reload and exported head.
  [Dated results](docs/status/2026-10-01-laya-pilot.md) and
  [operator guide](docs/laya-pilot-training.md). Both GPUs released.
- [ ] Investigate FAST degradation and improve quality before claiming a useful
  router. The full pilot still underperformed training priors for every class;
  median retained tokens increased to 22–26%, but all views remain truncated.
  Validation support is small and imbalanced.
- [ ] Exercise full-pilot epoch-checkpoint resume live; the short trial resume
  and full-pilot fresh reload are verified separately.
- [ ] Expand independent task diversity and audit annotation quality, especially
  GENERAL/REASONING separation and unknown missingness.
- [ ] Add executable replay and human-reviewed evaluation evidence before claiming
  downstream success. Resolve the source-use gate recorded in the pilot manifest
  before model release or dataset redistribution.

## P2 — comparative quality and operations

- [ ] Implement CLM-8B and GLiNER2.5-Decide adapters behind a common contract.
- [ ] Add learning curves, calibration, abstention and routing-cost evaluation.
- [ ] Add configurable metric cadence and sampled per-rank CPU/CUDA profiling.
- [ ] Evaluate Prometheus/Grafana integration for sustained resource monitoring;
  the training AMP does not currently provision those applications.
- [ ] Exercise failure recovery beyond the controlled checkpoint-resume diagnostic.

Update this file with the date, evidence and remaining limitation whenever an item
is completed. Do not mark a live GPU gate complete based on a local CPU test.

## Gateway data expansion — 2026-10-01

- [x] Gateway model discovery and one-state compatibility checks for Flash Lite,
  Luna and Sol. All three calls succeeded; this is not a quality benchmark.
- [x] Freeze 1,000 new states across 334 fresh issues from three pinned shards,
  excluding the old pilot groups; preserve full prefixes and grouped splits.
- [x] Complete 3,000 candidate responses and 3,000 independent judge calls;
  retain successful Terra judgments and use GPT-5.4 fallback with provenance.
- [x] Export and validate `data/pilot/gateway-pilot-v1-final`: 1,000 states,
  2,968 observed labels, 32 masked unknowns; grouped splits and canonical inputs checked.
- [ ] Manually review representative judge evidence and class imbalance before
  the next training experiment. [Campaign guide](docs/gateway-annotation-campaign.md).

- [x] Recover all four gateway candidate HTTP 502 errors without changing route model identities (3,000 successful candidate calls).
- [x] Finish independent judging and export; all transport failures recovered. Estimated campaign commitment $113.43 against $150 cap.

- [ ] Reconcile and archive primary `longer-pilot` evidence. The customer training
  summary reports a successful 10-epoch run / 1,580 updates, but the current
  milestone record lacks its dated primary logs and artifact verification.

- [x] Recover interrupted gateway judging and final four transport failures; preserve the first export and create the verified final bundle.

- [x] Prepare 15-slide vibe coding session deck and locally tested demo; moved to the standalone [vibe-coding-demo project](../vibe-coding-demo/README.md), using DBS polished masters and Plus Jakarta Sans typography.
- [ ] Select a standalone demo GitHub repository and isolated CAI project; rehearse Claude Code Messages/tool compatibility and the proposed CI/CD deployment before presenting.

- [x] Prepare customer follow-up draft, Ray training summary, Helios implementation note and a Bash NCCL IT-review package. Default read-only planning, explicit apply acknowledgments, scoped labels/filter, evidence and rollback; four local contract tests passed. Live staging apply/rollback and customer IT approval remain pending.
