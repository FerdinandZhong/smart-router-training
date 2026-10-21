# Local pilot review UI

Open **http://127.0.0.1:8765**. Start it from the project folder when needed:

```bash
python scripts/review_semantic_pilot.py --port 8765
```

The UI uses the v3 pilot and editable `review-work-20261010-v2` workspace.
It uses Python's standard library, binds only to localhost and loads the first 80 questions.
Use the [judge-assisted workflow](judge-assisted-review.md) to agree, disagree or edit prefilled proposals without typing every reason.

## Review a question

1. Enter your reviewer name. Enter a second name only after that person reviews the sample.
2. Select a question. Click “View metadata →” beside a table name to inspect its exact Ossie definition.
3. Mark tables positive, negative or unknown. Explain each known judgment.
4. Search the whole catalog for missed tables or fields.
5. Add required units to context sets. Record valid alternatives as separate sets.
6. Use “Add with dependencies” to include declared dependencies explicitly.
7. Reveal reference SQL when useful. Treat it as supervision, not user context.
8. Record your disposition, checks, clarification options and reasons.
9. Save the review and validate the workspace.

Catalog review opens the whole catalog definition and saves its checks independently.
The existing approval validator requires two query reviewers and reviewed catalogs for every retained candidate.
Drafts and deferrals can be saved while those requirements remain incomplete.
Adding context does not infer positive labels. Unknowns remain unknown.
Frozen catalogs and baseline rankings remain unchanged. Definition corrections require a new snapshot outside this UI.

## Saved human behavior

```text
Evidence opened + judgments + reasons
                  |
          Version-checked save
                  |
       Current review + revision history
                  |
         Export LLM examples
                  |
    Inputs / separate decision supervision
```

All output files are in `data/semantic-research/review-work-20261010-v2/`:

| File | Meaning |
|---|---|
| `reviews.jsonl` | Current query judgments and dispositions |
| `catalog-reviews.jsonl` | Current catalog checks |
| `review-events.jsonl` | Saved before/after decisions, identities, timestamps and evidence opened |
| `ui-backups/` | Backups made before each review-file replacement |
| `human-review-examples.jsonl` | Explicit export of saved query-review revisions |
| `human-catalog-review-examples.jsonl` | Explicit export of saved catalog-review revisions |

“Export LLM examples” rebuilds example files from saved revision history.
It includes drafts, deferrals and corrections without treating them as approved retrieval labels.
Each example separates question and metadata inputs from human decisions and reference SQL.
It records whether the reviewer opened SQL. It cannot capture unspoken reasoning or evidence read outside this UI.
Write why a table is required, a candidate is unsuitable, or clarification is needed.

For future LLM review training, split examples by the existing connected sample groups.
Keep all revisions of each sample in one split. Use reviewed decisions and reasoned deferrals first.
Keep drafts and corrections as separate process examples. Evaluate against independent human review.
If the LLM receives SQL as reviewer evidence, declare that task explicitly; exclude it from retrieval-model inputs.
This UI records evidence. It does not train or certify an LLM reviewer.

## Persistence and verification

Saves reject stale row versions, replace review files atomically, and flush revision history to disk.
The browser warns before leaving a question with unsaved edits. Exports include only saved revisions.
Do not edit JSONL files concurrently with the UI; external editors do not use its process lock.

Verification: 25 semantic tests passed. An isolated browser workspace verified catalog saves,
query saves, reload persistence, deferral, example export and validation with zero JavaScript errors.
No actual pilot review was approved or changed by these tests.
