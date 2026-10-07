# Gateway annotation campaign

The next dataset freezes 1,000 recorded pre-call states from 334 fresh SWE-Gym
issues, excluding the original pilot's issue groups and duplicate inputs. The
three pinned source shards produce 702/100/99/99 train/validation/calibration/test
states. Inputs preserve complete prefixes and never include future actions or
judge evidence. The source manifest retains checksums and source-use gates.

Candidate mapping is versioned independently of the old pilot:

| Class | Gateway model |
|---|---|
| FAST | `gemini-3.1-flash-lite` |
| GENERAL | `gpt-5.6-luna` |
| REASONING | `gpt-5.6-sol` |

Run FAST, then GENERAL, then REASONING. These are new observations, not remapped
old labels. A judge must use a different model identifier from every candidate;
using Sol as both a candidate and its judge is rejected by the annotation
pipeline. The approved judge is `gpt-5.6-terra`, distinct from all candidates. Final labels are not available
yet, and training must not consume candidate-only receipts as success labels.

## Discovery and compatibility

```bash
python scripts/list_gateway_models.py \
  --api-key-file ~/tokens/litellm_key_applied_ai \
  --output .amp-state/gateway-models.json
python scripts/check_gateway_candidates.py
```

Discovery only lists IDs. Compatibility checking makes one request per selected
model against one actual recorded state; it is not a quality benchmark. FAST
uses Chat Completions and JSON object output; GENERAL/REASONING use Responses,
JSON object output, low reasoning effort and a 2,048-token output cap, including
reasoning tokens. Receipts preserve requested/actual model and usage.

## Candidate phase

```bash
python scripts/gateway_candidate_stage.py --class-id FAST --retry-errors
python scripts/gateway_candidate_stage.py --class-id GENERAL
python scripts/gateway_candidate_stage.py --class-id REASONING
```

Defaults: six concurrent I/O workers, 30 requests/minute, conservative estimated
campaign ceiling $150. The credential path contains no credential value. Read
`runs/gateway-pilot-v1/candidate-source.json` for frozen identity and budget.
Changing that source/budget in place is rejected. Successful calls are cached
in the annotation runner's receipt format. Transient errors retry only with the
explicit flag, at most three attempts. A new HTTP 429 stops queued work; receipt
and budget reservations survive interruptions. Failed/uncertain calls remain
unknown; no automatic response repair or executable tool calls occur.

The monetary ledger uses the supplied gateway rates, charges reported input and
output tokens without cache discounts, and retains conservative reservations
where usage is missing. It is an estimate, not the gateway's actual bill. Billed
reasoning tokens are included in output totals, not counted twice. It does not
currently account for provider-specific cache-write premiums or gateway margins.
The queued campaign runs all candidates, then blinded Terra judging, then validates a separate `pilot_training` bundle. It does not launch training.

## Current evidence — 2026-10-01

All three one-state compatibility calls succeeded with schema-valid actions:
FAST 3.85 seconds, GENERAL 4.67 seconds, REASONING 10.76 seconds. This single-state
measurement does not establish relative task quality or general latency.

The initial unpaced bulk run encountered 429s after its first 90 successful
responses. Before stopping, it saved 136 successes and 160 rate-limit errors.
Those errors are not task failures. Direct gateway response headers showed a
team-member token limit of 500,000 and request limit of 150. Explicit pacing and
fail-fast cancellation were added; the paced recovery check completed the first 100 states successfully.

## Approved complete workflow

```bash
python -u scripts/gateway_annotation_campaign.py all
```

The workflow waits for an existing FAST phase to finish, reuses its receipts,
runs GENERAL and REASONING in order, and independently judges every successful
candidate response with Terra. The judge uses Responses JSON-object output,
low reasoning effort, a 1,024-token cap and confidence threshold 0.8. Candidate
identifiers are outside judge inputs. Unknowns remain masked.

Progress is written to `runs/gateway-pilot-v1/campaign-state.json`; completed
phase receipts are `*-phase.json`. After judging, the existing annotation
pipeline assembles labels without making new API calls. The exported bundle is
`data/pilot/gateway-pilot-v1`, with purpose `pilot_training`; the original
`pilot-smoke-v1` remains unchanged and stays the default AMP dataset. Neither
the larger bundle nor raw/private annotation receipts are added to the AMP archive.

Estimated costs use configured rates and conservative unresolved reservations,
not actual gateway billing. Budget or rate-limit failures stop the workflow and
leave cached progress for explicit resume. Full workflow completion and
class-support review are not yet verified.

[Started campaign evidence](status/2026-10-01-gateway-campaign.md) records the
completed FAST phase and remaining queued stages.

### Recovery on 2026-10-01

All four HTTP 502 candidate calls recovered using their original models, preserving the frozen route mapping. Judging resumed through `scripts/resume_gateway_campaign.py` with GPT-5.4 for pending or failed Terra judgments at 10 requests per minute. Successful Terra judgments are retained. Logical judge receipts explicitly link to the physical fallback call and identify the actual fallback model; archived attempts remain available. The shared estimated $150 ceiling is retained. Dataset export is pending.

### Interrupted-process recovery, 2026-10-02

The judging process exited after 1,541 successful judgments. Recovery reuses successful receipts and retries transport errors within the existing three-attempt limit. Failed fallback receipts are also resolved explicitly under the logical judge call so finalization preserves unknowns without network access. Physical fallback calls are counted once in the summary; both actual judge models are reported. The estimated $150 ceiling remains unchanged.

## Completed final bundle — 2026-10-03

Use `data/pilot/gateway-pilot-v1-final`. The first `gateway-pilot-v1` export remains
preserved; its pre-recovery annotation/report/summary files are saved under
`runs/gateway-pilot-v1/pre-recovery-20261003`.

All 3,000 candidate responses and judge calls succeeded after transport recovery.
There are 2,968 observed independent binary labels and 32 unknowns, masked rather
than mapped to failure. Splits: 702 train, 100 validation, 99 calibration, 99 test.
Canonical input preservation, checksums, issue/duplicate split isolation and masks
were verified. Total estimated campaign commitment: $113.43; this is not a billing
invoice. Labels are single-trial local-step silver judgments, not executable replay
or calibrated probabilities. Source-use limitations remain in the manifest.

| Route | Pass | Fail | Unknown |
|---|---:|---:|---:|
| FAST | 834 | 150 | 16 |
| GENERAL | 949 | 42 | 9 |
| REASONING | 982 | 11 | 7 |

The low failure counts for GENERAL and REASONING warrant representative manual
review before training. This campaign's completion does not establish production
routing quality. Detailed evidence: `runs/gateway-pilot-v1/campaign-summary.json`.
