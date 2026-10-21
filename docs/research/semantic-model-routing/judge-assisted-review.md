# Judge-assisted human review

The UI at **http://127.0.0.1:8765** now shows a filled LLM proposal for each completed draft.
The judge is the gateway model ID `claude-sonnet-5`. A live probe confirmed that model ID in the response.
The active method is `ossie-review-draft-v2`, configured in `configs/semantic_retrieval/review-judge.json`.

## Human workflow

1. Save existing unsaved work, then refresh the UI.
2. Enter your reviewer identity once.
3. Read the proposed disposition and summary above the candidate tables.
4. Inspect any metadata needed to check the proposal.
5. Click **Agree & save** to accept the filled decision and reasons.
6. Click **Disagree** to record rejection without inventing replacement labels.
7. Use **Use / edit proposal** to correct specific fields, then save.
8. Export examples after saving your responses.

Table reasons, review checks, clarification options, context sets and catalog assessments are filled by the judge.
Unknown is a valid proposed value. The judge does not invent identities, execution results or physical-schema verification.
An approval recommendation remains pending until the existing human and catalog approval requirements are met.
One click does not fabricate a second reviewer. Saved human reviews are not overwritten by background draft generation.

Drafts appear as the bounded first-80 batch finishes. The header displays batch progress every 15 seconds.
When a blank, untouched sample gets a ready draft, the UI fills it automatically.
If you have unsaved edits, the UI preserves them. You can refresh the proposal explicitly.

## Judge method and evidence

```text
Question + retrieved metadata + table-name inventory
                      |
        Fixed judge + separate reference SQL evidence
                      |
       Validated, cached proposal with model provenance
                      |
          Human agreement / rejection / correction
                      |
        Review history + paired-example export
```

The judge sees all catalog table names and detailed metadata for the review pool.
It receives reference SQL as supervision, not as user context.
Source database identity cannot resolve ambiguity on behalf of the user.
Long descriptions have explicit clipping flags. Relationships are restricted to candidate-table endpoints.
These proposals therefore do not constitute exhaustive semantic validation of the entire catalog.
The prompt separates value-dependent table identification from ordinary SQL filters or aggregation.

Generation requires all candidate judgments, reasons and decision fields.
Validation checks candidate IDs, known labels, context dependencies, option values and catalog coverage.
Invalid or truncated responses remain failures. Truncation receives one bounded retry with a larger output cap.
Missing catalog assessments receive explicitly recorded software-generated unknown placeholders.
These repairs never invent verified checks or negative training labels.
The first protocol produced a truncated first-question response; v2 removes repeated metadata and limits reason length.
The first-question v2 draft completed and recommended organizational clarification.

## Persistence

Files live in `data/semantic-research/review-work-20261010-v2/`:

| File / directory | Content |
|---|---|
| `judge-drafts/` | Current per-question drafts and response receipts |
| `judge-draft-archive/` | Superseded draft receipts |
| `judge-requests/` | Exact prompts and input evidence keyed by request hash |
| `judge-batch-status.json` | Current bounded-batch progress |
| `review-events.jsonl` | Human saves, disagreement events, before/after decisions and judge provenance |
| `human-review-examples.jsonl` | Human decisions paired with the original judge proposal |
| `human-judge-feedback.jsonl` | Standalone disagreement and other feedback events |

The fixed model ID and actual returned model ID remain in receipts.
The gateway alias does not expose an immutable provider checkpoint; preserve run dates and actual response identities.
Each draft records its protocol, prompt hash, input hash, raw complete response and token usage.
Human identities and decisions remain distinct from LLM text. Generated reasons are not falsely attributed as independently written human reasons.
Exports keep reference SQL and judge assistance outside retrieval-model inputs.

Future LLM review adaptation can use accepted proposals, rejected proposals and human corrections.
Keep revisions of each connected sample group in one split. Evaluate on independently reviewed groups.
Do not use raw drafts or simple agreement as proof of downstream SQL correctness.

## Batch commands

```bash
# Cached ready drafts are reused. Failed drafts can be retried.
python scripts/prefill_semantic_reviews.py --limit 80

# Same configured judge and protocol for all current pilot records, when requested.
python scripts/prefill_semantic_reviews.py --scope pilot --limit 240
```

The CLI runs two workers. Each request has a timeout and an output-token cap.
Run one batch at a time. Resume after interruption using the same command.
The full-dataset path can reuse the same method on a new checked pilot-format bundle.
No full-dataset campaign or LLM adaptation is launched by the first-80 command.

Verification: 38 semantic test cases passed, including cached-proposal preservation and judge-provenance export.
An isolated browser workspace verified automatic filling, one-click agreement, disagreement and example export with no JavaScript errors.
