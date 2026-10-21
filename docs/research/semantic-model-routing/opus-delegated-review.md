# Delegated Opus review — 2026-10-19

The user delegated the first-80 review to `claude-opus-5-5` at the existing Cloudera gateway.
A live probe returned that exact model ID. The first full review also returned `claude-opus-5-5`.
The first-80 Sonnet campaign contained 69 valid proposals and 11 failed drafts at intake.

```text
Sonnet proposals + catalog evidence
               |
Opus critique / direct draft when Sonnet failed
               |
Schema, references and context validation
               |
Automated silver records + exact model provenance
```

Opus reviews valid Sonnet proposals and returns accept, revise or abstain.
It produces a direct draft for samples without a valid Sonnet proposal.
These direct drafts do not constitute agreement between two models.
Both judges belong to the same model family; their errors may be correlated.

The user does not need to complete the manual review UI for this automated campaign.
Each result records `reviewer_type=llm`, `delegated_by_user=true` and `human_approved=false`.
No result is signed using the user's identity. Existing human review files remain unchanged.
The original human-approved training-export contract remains separate from this silver-label artifact.
No training job is started by this campaign.

## Configuration and execution

Configuration: `configs/semantic_retrieval/opus-reviewer.json`.
Gateway: `https://ai-gateway.cloudops.cloudera.com`.
Endpoint: `/chat/completions`. Credentials are read from the existing credential file.
The protocol is `ossie-opus-delegated-review-v1`.

```bash
python scripts/review_semantic_with_opus.py --limit 80
```

The campaign uses two workers and persists each completed receipt.
Reusing this command resumes the same run and skips successful cached reviews.
`python scripts/finish_opus_reviews.py` waits for the current campaign, validates cached decisions, and retries unresolved samples once.
Changing frozen model, prompt or source proposal identities requires a new `--output` directory.
Generation failures remain explicit. They never become negative table labels.
Abstentions mask all table labels in the silver export. They retain the original proposal in the receipt.
Ordinary uncertainty remains null. No SQL execution, physical-schema audit or business-owner certification is inferred.

## Outputs

Run directory:
`data/semantic-research/review-work-20261010-v2/opus-5-5-review-20261019-v1/`.

| Artifact | Content |
|---|---|
| `run.json` | Frozen model configuration, prompt hashes and selected record IDs |
| `status.json` | Reviewed, failed and total counts; current campaign state |
| `requests/` | Exact critique inputs and any format-repair requests |
| `receipts/` | Requested/actual model IDs, reasons, patches and final proposals |
| `judge-drafts/`, `judge-requests/` | Direct Opus drafts when Sonnet was unavailable |
| `automated-reviews.jsonl` | Incremental machine-review evidence for completed samples |
| `silver-labels.jsonl` | Canonical query inputs, metadata-derived candidate text, labels, dispositions and receipt hashes |

The copied `reviews.jsonl` and `catalog-reviews.jsonl` are input snapshots for direct drafting, not new human approvals.
The local UI displays the active Opus decision and progress through `delegated-review-active.json`.
It labels these results as delegated automated review.

## Verification and limits

41 semantic test cases passed. Tests covered cache reuse, unchanged human files, unknown labels,
invalid patches, incomplete approval evidence and separation of reference SQL from model inputs.
A read-only browser check displayed the actual first Opus review with no JavaScript errors.

The first review preserved organizational ambiguity, changed an unsupported negative to unknown,
and replaced unsupported catalog description-verification claims with unknown checks.
This is evidence that the adjudication path runs. It does not establish Opus label accuracy.
The completed campaign contains 72 reviewed records and eight failures.
It produced 38 clarification dispositions, 33 metadata deferrals and one approval.
The approval belongs to training; no validation record was approved.
The [20 October audit](deferral-audit-20261020.md) documents ten deferrals, one control, and the required repairs.
Consult `status.json` for any later campaign changes.
