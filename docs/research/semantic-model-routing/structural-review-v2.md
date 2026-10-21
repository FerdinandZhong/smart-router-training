# Automated structural review v2

This protocol separates table relevance from complete-context sufficiency.
It runs as an offline diagnostic with `claude-opus-5-5` at the existing gateway.
It does not change the original human exporter or first-80 review records.

```text
Frozen retrieval rankings
          |
Full field definitions + one declared-relationship expansion
          |
Bounded evidence with omission log
          |
Opus structural judgment
          |
Validated receipts with independent relevance and context fields
```

## Evidence contract

`semantic_structural_review.evidence_input()` reads query inputs and saved retrieval rankings.
It does not read reference SQL or earlier judge proposals into model input.
The first 24 ranked candidates receive priority.
Expansion examines up to 96 original candidates and resolves relationship field IDs to parent tables.
New relationship endpoints precede the remaining candidates.
The final view contains at most 96 tables and 240,000 bytes of metadata JSON.
These are byte limits, not tokenizer-specific token limits or production latency guarantees.
Descriptions remain complete. Tables that exceed the budget are omitted as whole units.
Relationships enter only when their dependency units are visible and budget remains.
The request archive records every omitted catalog unit and all added tables.
The original retrieval rankings remain unchanged.

This is a bounded evidence view. It cannot certify whole-catalog uniqueness.
The diagnostic tests evidence recovery, not retrieval quality on an independent test set.
It uses the ten purposively selected audit cases and one approved control.

## Judgment contract

`table_judgments` assigns each supplied table a relevance label, rationale, and evidence IDs.
One means a defensible relevant candidate, zero means demonstrably irrelevant, and null means unknown.
A positive relevance label does not establish a uniquely intended table or a complete SQL context.
These labels therefore cannot be substituted for the previous required-table labels without adapting training and evaluation.

`context_status` is one of:

- `sufficient_within_evidence`: at least one complete context within the supplied evidence.
- `needs_clarification`: a concrete unresolved scope or definition ambiguity.
- `needs_metadata`: required information is unavailable.
- `unresolved`: no supported decision.

`context_sets` include required tables, fields, and declared relationships with dependency closure.
Multi-table contexts require declared connecting relationships.
Conditional alternatives can accompany clarification; they are not unconditional sufficient answers.
Every context table must have relevance one. Positive relevance can also exist without a context set.
The validator rejects unseen IDs, missing judgments, unsupported label values, and incomplete dependencies.
It checks structural consistency; it cannot prove the model's semantic judgments correct.

Physical-schema verification, SQL execution, and business-definition certification remain null in every receipt.
All receipts declare automated review and `human_approved=false`.
No training export or optimization starts from this diagnostic.

## Run and resume

```bash
python scripts/review_semantic_diagnostic.py --dry-run
python scripts/review_semantic_diagnostic.py
```

Configuration: `configs/semantic_retrieval/structural-reviewer-v2.json`.
Default output: `data/semantic-research/structural-diagnostic-20261020-v2c/`.
The date in the directory identifies preparation; the live run can complete later.
Earlier `v2` and `v2b` directories contain dry-run evidence from debugging, not completed judgments.

The runner issues requests sequentially with ten-second spacing.
Each sample has at most two attempts per invocation.
Transport failures wait thirty seconds before retry. Invalid JSON or schema output receives one correction request.
The runner verifies the returned model ID and saves exact attempts and responses.
Successful receipts are reusable. Failed receipts are archived before another invocation.
Changed prompt, configuration, or evidence requires a new output directory.

Outputs include `run.json`, exact requests with coverage logs, per-sample receipts, `status.json`, and final `automated-reviews.jsonl`.
Credentials are loaded through the existing backend and never written into these artifacts.

## Verification

Fixture tests cover full descriptions, field-endpoint expansion, unknown labels, evidence references, dependency closure, and whole-unit budget omission.
Actual dry-run checks confirm the full `coins.status` definition and the recovered `program` table with its declared relationship.
These are local CPU checks. No GPU training or live serving-latency claim follows.
