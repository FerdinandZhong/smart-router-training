# Decision-model adapters and customer training contract

Updated 2026-09-27. Design requirements for implementation plan v2.1; no training has been run. Customer datasets and customer-defined classes are a core requirement, not a later router customization.

## 1. Model comparison and verified integration paths

| Model | Verified architecture/path | Proposed role | Important limit |
|---|---|---|---|
| Laya | Encoder plus option-scoring decision head; options supplied at request time | Compact reference adapter, including multilingual experiments | Default short context; calibrate on the customer's task |
| `Contrastive-LM/CLM-v0.1-8B` | Frozen Qwen3-8B embeddings plus trainable state/action projection heads | Cached-embedding adaptation and candidate-ranking experiment | Tiny trainable heads still require an 8B encoder at inference; scores depend on the candidate set |
| `fastino/GLiNER2.5-Decide` | DeBERTa-v3-large-based classification, runtime label sets and multiple tasks | Compact customer single-/multilabel classification candidate | English checkpoint; neither multilingual coverage nor reliable full long-context understanding follows from the family name |

CLM's [model card](https://huggingface.co/Contrastive-LM/CLM-v0.1-8B) specifies separate state/action heads over a frozen encoder, last-token pooling, and candidate-relative probabilities. Its [repository](https://github.com/Contrastive-LM/CLM) defaults serving to 2,048 tokens and describes increasing both encoder and API limits together. Evaluate 8K explicitly; do not mistake the small head download for the full model footprint or assume quantized embeddings preserve head behavior.

Inspected CLM commit `bb42c6c5bf914fd449bed2f6ca65be80602cb1f7`. [`train/finetune.py`](https://github.com/Contrastive-LM/CLM/blob/bb42c6c5bf914fd449bed2f6ca65be80602cb1f7/train/finetune.py) supports projection-head tuning from embeddings and typed-choice training with InfoNCE or soft cross entropy. [`train/adapters.py`](https://github.com/Contrastive-LM/CLM/blob/bb42c6c5bf914fd449bed2f6ca65be80602cb1f7/train/adapters.py) maps question options and targets. Use soft cross entropy as the first customer classification objective; InfoNCE negative sampling must not turn other valid labels into false negatives. Freeze grouped splits before embedding preparation. The upstream fine-tuning guide is an experiment workflow, not an instruction to run autonomous experiments in this project.

GLiNER's [model card](https://huggingface.co/fastino/GLiNER2.5-Decide) documents arbitrary label sets, label descriptions, and simultaneous tasks. The [release](https://fastino.ai/blog/gliner-2-5-decide-open-weight-decision-model) describes local full/LoRA training. Its benchmark compares against **JevK5, an open reproduction**, not TypeSafe's Jev. Vendor scores and short-input latency are not customer workload results.

Inspected GLiNER2 commit `55656fbfa01d3d4a77485e1a1eeeaf682990ccdf`:

- [`tutorial/8-train_data.md`](https://github.com/fastino-ai/GLiNER2/blob/55656fbfa01d3d4a77485e1a1eeeaf682990ccdf/tutorial/8-train_data.md) supports named classification tasks, candidate labels, `true_label`, multilabel flags, and descriptions. This is a useful customer adapter target, but does not establish generic soft/partial-label support in the public data API.
- [`classification/scoring.py`](https://github.com/fastino-ai/GLiNER2/blob/55656fbfa01d3d4a77485e1a1eeeaf682990ccdf/gliner2/classification/scoring.py) exposes per-label logits and softmax/sigmoid interpretations. Prediction APIs may return selected labels only; the framework needs the full class-aligned score vector. Inference scorers are not automatically differentiable training APIs.
- [`models/span/model.py`](https://github.com/fastino-ai/GLiNER2/blob/55656fbfa01d3d4a77485e1a1eeeaf682990ccdf/gliner2/models/span/model.py) currently uses binary cross entropy for classification training. Do not silently assume this equals our single-label softmax objective. The adapter must implement a differentiable task-aware loss or explicitly declare a native-BCE recipe and evaluate it separately.
- [`classification/long_text.py`](https://github.com/fastino-ai/GLiNER2/blob/55656fbfa01d3d4a77485e1a1eeeaf682990ccdf/gliner2/classification/long_text.py) aggregates chunk logits before constrained decoding. This is a chunked strategy, not proof of cross-chunk comprehension. The checkpoint [config](https://huggingface.co/fastino/GLiNER2.5-Decide/blob/main/config.json) has `max_len: null`; that does not mean unlimited validated context. Record actual token budgets including schema overhead, and distinguish preprocessing word limits from model subword tokens.

All three are experiment candidates. Pin checkpoint/library revisions, compare on identical customer splits, and select on quality, calibration, latency, total training cost, and deployment footprint. Test new label sets and long input directly. A multilingual sibling checkpoint is a separate candidate with its own validation.

## 2. Separate task, data, model, and execution

```text
Customer dataset + TaskSpec + DatasetSpec
    → import / validate / group split
    → optional annotation of missing labels
    → ModelAdapter preparation (tokens or cached embeddings)
    → TrainingRecipe on Ray
    → task-specific evaluation / calibration
    → versioned decision artifact + optional application resolver
```

The shared core owns validation, split isolation, masks/weights, run manifests, checkpoints, metrics, and export. A task specification owns label meaning and decision semantics. A model adapter owns tokenization, schema rendering, tensor preparation, model construction, supported losses, and score extraction. A training recipe owns encoder/head/LoRA parameter selection and optimizer behavior. Ray owns resources and worker execution. No core code hardcodes a customer class list or router tier.

Required adapter contract, conceptual until implemented:

```text
capabilities() -> supported task kinds, label types, train modes, context policy
validate(task_spec, training_recipe) -> explicit compatibility errors
prepare(records, task_spec) -> tokens or cache manifest
build_trainable_model(artifact_spec) -> torch module
collate(records, task_spec) -> inputs, targets, valid masks, weights, class IDs
forward_scores(model, batch) -> class-aligned logits
loss(logits, targets, masks, weights, task_spec) -> numerator, denominator
export() / load() -> reproducible decision artifact
```

Supporting an inference task does not automatically mean its soft-label training path exists. Reject unsupported combinations at preflight; do not discard soft labels, convert missing to negative, or silently select another objective. Use isolated, pinned dependency environments per backend if needed.

## 3. TaskSpec and output semantics

Each task has `task_id`, `schema_version`, `kind`, prompt/rubric, ordered stable class IDs, display names/descriptions, optional aliases, label-completeness policy, and evaluation/abstention settings. Class definitions are not learned from the test labels. For ordinal tasks also supply explicit numeric values/order. Keep business actions in a separate resolver mapping.

| Kind | Target and loss | Probability meaning |
|---|---|---|
| `single_label` | One label or complete soft distribution; softmax cross entropy | Exactly one of the supplied classes; probabilities sum to one |
| `multi_label` | Per-class binary/soft targets with observation masks; sigmoid BCE | Several or no labels can apply; probabilities need not sum to one |
| `independent_binary` | Named yes/no questions with observed targets; BCE or binary softmax CE | Independent propositions, including agent tier sufficiency |
| `ordinal` | Ordered levels or distribution; declared ordinal/distribution objective | Level distribution and optional expectation; no implicit alphabetical order |
| `ranking` | Candidate set plus relevance/pairwise/listwise supervision | Relative preference within candidates; not absolute success probability |

Implement the first three kinds first; gate ordinal/ranking training until the adapter and metrics support them. CLM's native ranking is available for a separate experiment, without forcing it into customer class-probability evaluation.

`other`, an unannotated example, and model abstention are different states. A positive-only multilabel record does not make unlisted labels negative unless the annotation declares completeness. A partial single-label record is not a complete probability distribution; keep unresolved labels out of CE or use an explicitly implemented partial-label objective. Never normalize independent success probabilities across tiers.

The shared result contains task/class-schema versions, stable class IDs, raw scores, calibrated probabilities when available, selected label(s), abstention reason, and artifact ID. Mark uncalibrated scores honestly. Preserve raw probabilities separately from rule-constrained assignments; constraints do not produce calibrated marginals automatically.

Adding/renaming/reordering classes must never silently reinterpret stored indices. Schema-conditioned models can score unseen labels, but new classes/descriptions/candidate sets invalidate previous calibration guarantees and require evaluation. Fixed-class heads require migration/retraining. Keep artifact-to-schema compatibility explicit.

## 4. DatasetSpec and canonical record

Import JSONL, CSV, and Parquet through configurable column mappings. Support plain text and nested structured state, single labels, label arrays, soft-label maps, class observation masks, example/group IDs, supplied splits, timestamps, and label provenance. Plain text customers need no episode/step metadata. Remote stores can be accessed through existing storage connectors later; arbitrary file parsing must not be embedded in model adapters.

Example canonical record after applying the [customer mapping](../configs/examples/customer-support.json):

```json
{
  "schema_version": "1.0",
  "dataset_id": "customer_a_support_v1",
  "task_id": "support_intent",
  "task_schema_version": "1.0",
  "example_id": "ticket-001",
  "group_id": "conversation-001",
  "input": {"text": "Please refund the duplicate subscription charge."},
  "targets": {"kind": "hard", "label_ids": ["billing"]},
  "provenance": {"label_source": "customer_provided"}
}
```

Validate unique IDs, known classes/aliases, finite values, masks, task-specific label cardinality, complete distribution sums, nonempty input, and schema compatibility. Preserve original labels and record any normalization; never silently relabel. Customer-provided labels retain their provenance and quality audit rather than being automatically called executable gold.

Respect supplied splits and validate group/duplicate leakage; otherwise create seeded grouped splits before augmentation/annotation. Report per-class counts, rare/absent classes, language/length coverage, and contradictory labels. Insufficient class coverage produces an explicit evaluation limitation, not an invented score or silent class removal. Mixed-customer training is opt-in; isolate manifests, caches, outputs, and calibration by customer/task by default.

Three ingestion modes: **labeled** (train directly), **partial** (use observed targets; optionally annotate missing ones), **unlabeled** (queue annotation against customer definitions). Annotation is optional for existing labeled data. Generate teacher rubrics from the TaskSpec and restrict outputs to its classes; do not overwrite accepted customer labels. Task-specific review can still reveal ambiguous definitions and disagreement.

## 5. Backend-specific Ray recipes

- **Laya/GLiNER:** tokenize with the selected adapter and train eligible head/encoder/LoRA parameters through Ray Train. Reuse the two-node DDP/resume gates. If an upstream trainer controls DDP itself, adapt its model/loss to Ray rather than nesting distributed launchers. Normalize masked weighted losses across workers.
- **CLM:** Ray GPU workers precompute frozen state/candidate embeddings, then train projection heads on the cache. Cache keys include encoder/tokenizer revision, pooling and serialization, truncation/length, precision/quantization, customer/task namespace, and content hash. Version projected-vector caches separately when heads change. Invalidate caches if the encoder changes. Fit requires no 8B backward pass; embedding computation and online 8B inference still incur cost.
- **Resource choice:** allow CPU or one GPU for small head fits; use two-GPU DDP where measured useful. Do not demand full 8B DDP fine-tuning on the current two GPUs. If later requested, profile PEFT/sharding as a new recipe. Embedding workers and the TP=2 annotation teacher still compete for the same capacity.

For CLM inference, deploy a compatible pooling encoder plus scoring heads; it differs from a generation endpoint. For Laya/GLiNER, use their Python scoring modules behind Ray Serve. Export class definitions/order, preprocessing, weights/adapters, frozen encoder reference if applicable, calibration, thresholds, task/recipe hashes, dependency pins, and split/evaluation manifests.

## 6. Acceptance gates

1. The same customer fixture imports through configured JSONL/CSV/Parquet mappings to equivalent canonical records.
2. Change a three-class customer task to a different five-class task through configuration only. No router labels, dimensions, or application fields leak into the core.
3. Labeled mode makes no teacher calls; partial mode preserves unknown targets. Tests cover unknown classes, duplicate IDs, conflicting definitions, and split leakage.
4. Customer single-label, multilabel, and agent independent-binary tasks use the correct activations, masks, and losses. GLiNER soft-label/custom-loss and CLM candidate mapping are explicit compatibility tests.
5. At least two backend adapters train/evaluate/export the same customer task before the abstraction is considered proven; complete the third adapter before calling the requested model comparison complete.
6. Round-trip export/load preserves class-aligned scores. Reordered labels retain identity; incompatible schema/calibration or stale embedding caches fail clearly.
7. Single-label reports macro-F1, per-class precision/recall, confusion matrix, log loss/Brier and coverage. Multilabel adds per-class/micro/macro metrics and threshold evaluation. Routing adds task success and cost. Test sets never tune thresholds.
8. Benchmark all three candidates on frozen splits, reporting cold/warm latency, schema size, context length, total resource costs, and task quality. Do not select a universal winner from vendor benchmarks.
