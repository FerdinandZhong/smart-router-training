# Implementation history

> Historical checkpoints through 2026-09-28. For current progress, read
> [TODO.md](../TODO.md) and [the project overview](../project-overview.md).
> Statements below describe their original checkpoint, not the current deployment.

Updated: 2026-09-28.

Latest checkpoint: [pilot continuation](real-data-pilot-002.md) recovered two more initial Qwen observations and completed ten additional states. Twenty states now have 58 observed state/model labels and two unknowns. A resumable CLI campaign worker was launched for the remaining 280 states. The 51-test suite passes; earlier sections below retain historical implementation checkpoints. Current campaign progress is in `runs/real-pilot-002/summary.json` and `worker.json`.

## Phase 0 — task/data contracts and offline construction

Status: in progress. Dataset construction and recorded-source extraction are implemented and verified; environment replay and model compatibility checks remain.

Implemented:

- Python package and CLI with JSON-configured customer classes and input mappings.
- JSONL/CSV/optional Parquet import, including nested structured state and hard/soft/partial labels.
- Single-label, multilabel and independent-binary validation; explicit unknown targets and class aliases.
- Episode identity checks, structural future-evidence rejection, separate metadata/evidence, and model-input projection.
- Deterministic grouped splits with transitive duplicate-input merging; validation of supplied splits.
- Audit reports, optional missing-label queue, exclusive output directories, split manifests and file checksums.
- Customer classification fixture and 24 synthetic unlabeled agent-step records in 12 fictional episodes.

Files: `pyproject.toml`, `src/smart_router/`, `tests/test_dataset.py`, `configs/examples/`, `data/examples/`, `docs/data-pilot.md`, README and implementation plan updates. `.gitignore` excludes raw/prepared datasets and generated Python files if Git is initialized later.

Validation:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m smart_router.cli prepare --config configs/examples/agent-steps.json --output data/prepared/agent-fixture-v1
```

Results: 17 tests passed, including actual Parquet/CSV/JSONL parity in the available environment. The synthetic bundle has 18/2/2/2 states in train/validation/calibration/test, with 9/1/1/1 episodes respectively; all labels are unknown. PyArrow emitted nonfatal sandbox CPU-feature probe warnings; its test passed.

Known limits: import is in memory; duplicate detection is not semantic; no class-stratified grouping; audit lengths are characters, not tokens; no automatic append-to-frozen-manifest workflow; semantic/timestamp leakage audits require real source material. The importer retains outcome evidence but does not derive success labels from raw episodes.

Current source: 300 pre-call states from 100 SWE-Gym issues have been collected. Exact prefix fidelity is verified; environment replay is not implemented. See [real-data pilot](real-data-pilot-001.md). Complete the ten-state annotation audit before expanding labels across the pool or toward the first 2K–5K-state comparative training pilot.

## Local-step annotation runner

Implemented and tested offline. See [annotation pipeline](annotation-pipeline.md).

- Separate configurable candidate and judge model calls; customer-defined routing classes.
- OpenAI Responses and text-based Chat Completions HTTP adapters; no new dependencies.
- Blinded pointwise judging, repeated trials, unanimous verdicts, unknown/error handling and review queue.
- Per-class local success frequencies with counts and uncertainty, kept separate from original downstream-success targets.
- Run hashes, cached results, explicit bounded retries, durable call/output-token reservations and exclusive run locks.
- Synthetic demonstration with two states, three candidates, two trials and two judges: 36 mocked calls, five observed state/class estimates and two review trials.

Validation: 32 unit tests passed, including the existing 17 data tests and 15 annotation tests. No live API or GPU calls were made. HTTP adapters are covered offline; account/model access and actual endpoint behavior still require a live smoke run. Actual agent action execution, downstream replay, dollar-budget enforcement, human adjudication and promotion of silver labels into a training task are not implemented.

Current annotation action: review the ten-state comparison with 27 observed labels and three Qwen unknowns after recovery. Qwen has six format failures and one pass; Terra has eight passes and Sol nine. Investigate format handling and timeout/incomplete cases before expansion. The historical offline validation above describes the initial runner, not its current live status.

## First live smoke batch

Completed on 2026-09-28: two synthetic-source states, GPT-5.6 Sol and Terra as candidates, GPT-6 Astra as a separate judge, one trial per state/candidate. Four candidate executions and four judgments were performed through fresh session agents. See [batch report](annotation-batch-001.md).

Sol passed both local contracts. Terra passed the lookup and failed the timeout-acknowledgment criterion; that criterion is flagged for runtime/contract alignment review. This batch is excluded from training and does not establish calibrated probabilities or model rankings.

The runner now imports real external execution receipts with request hashes and provenance. HTTP credentials were not needed; no standalone HTTP API inference was performed. Actual serving revision, usage/cost and inference latency were not exposed. All 35 tests pass, including the recorded batch import and external receipt validation.

## Later phases

Three-candidate batch update: [batch 002](annotation-batch-002.md) is complete after the user restored Qwen. All six state/model observations and six Astra judgments passed the current local contracts. The two successful Qwen calls took 2.65 and 1.41 seconds with thinking disabled; prior serving failures remain archived. No cluster mutation was performed by this project. Credential-file support and staged execution have 39 passing tests; completion verification confirmed all evidence links, unchanged training targets/splits and resume without new calls. The two states are synthetic, with one trial per model; real-source collection, executable contracts and calibrated probability estimation remain outstanding.

- Real dataset collection: 300 recorded public SWE-Gym states, 100 independent issues, ten repositories; exact pre-call prefixes and grouped splits verified.
- Live LLM annotation: synthetic smoke batches complete; first ten real states have 27 completed candidate/judge pairs. Qwen recovery produced one pass, six format failures, two timeouts and one parser-rejected response. Its three unknowns reached the configured attempt limit. Earlier Terra/Sol results are unchanged.
- Deterministic tool-name/JSON Schema checks and request-packet export/import are implemented. The 44-test suite passes, including source leakage boundaries and deterministic checks overriding judge passes.
- Real records remain ineligible for training pending evidence and source-term review. No proposed actions or downstream continuations were executed; probabilities are not calibrated.
- Laya/CLM/GLiNER model adapters and calibration: not started.
- Ray DDP training and recovery gates: not started.
- No sibling repository or live deployment was changed.
