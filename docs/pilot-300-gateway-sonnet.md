# Original 300-state gateway reannotation

Started 2026-10-06 at the user's request. This run rebuilds labels for the original
300 states. It preserves their full input prefixes and 210/30/30/30 split assignments.
It leaves `pilot-smoke-v1` and both 1,000-state gateway bundles intact.

| Role | Model |
|---|---|
| FAST candidate | `gemini-3.1-flash-lite` |
| GENERAL candidate | `gpt-5.6-luna` |
| REASONING candidate | `gpt-5.6-sol` |
| Independent judge | `global.anthropic.claude-sonnet-5` |

The prepared records use the gateway task and its `swe-gym-local-v1` success
contracts. Old targets and judge evidence are cleared before annotation. The
candidate prompt and generation settings match the 1,000-state gateway campaign.
The judge receives blinded candidate responses and complete canonical inputs.
One trial per candidate yields independent binary observations. Abstentions and
confidence below 0.8 remain masked unknowns. No candidate tools are executed.

```text
Original 300 inputs -> Gateway candidates -> Sonnet judgments -> Validated bundle
```

Run commands:

```bash
python scripts/rebuild_pilot_300.py plan
python -u scripts/rebuild_pilot_300.py check
python -u scripts/rebuild_pilot_300.py all
python -u scripts/rebuild_pilot_300.py supervise --detach
```

The compatibility check uses one state per candidate. Cached receipts are reused
by the full run. The full run plans 900 candidate and 900 judge calls before
retries. It uses six I/O workers, 10 requests per minute and an estimated $75
ceiling. The Sonnet rate is a provisional $3/$15 input/output allowance per
million tokens, not a verified gateway tariff. The frozen configuration records
that limitation. The ledger excludes cache discounts and retains reservations
when usage is unavailable. Actual gateway billing can differ.

The first compatibility run reached the judge's 1,024-token output limit. Its
receipts remain under `runs/pilot-300-gateway-sonnet-v1-compatibility-1024`.
The corrected judge configuration disables thinking and permits 4,096 output
tokens. It retains failed receipts and reuses successful candidate receipts.
The corrected three-candidate check returned schema-valid judgments.
JSON-object output still occasionally added fields or Markdown fences. Those
responses remain archived under `runs/pilot-300-gateway-sonnet-v1-json-object`.
The final policy uses the fixed strict local-step judgment JSON schema. A real
Sonnet request verified its exact fields. Its confidence was 0.75, so the label
correctly remains unknown under the unchanged 0.8 threshold. Successful
candidate calls are reused; previous raw judgments and cost reservations remain
preserved. No text repair or confidence adjustment occurs.
The first bulk attempt returned HTTP 429 at 30 requests per minute. Successful
receipts were preserved, and the resumed run uses 10 requests per minute.
A second HTTP 429 occurred at that pacing. A diagnostic response confirmed
team-member limits of 150 requests and 500,000 tokens. The resumed run also
spaces calls using a conservative 300,000-token allowance per minute. It counts
request bytes plus output capacity as an upper estimate, rather than relying
only on request count. Successful candidate recovery was verified.

Run state and evidence live under `runs/pilot-300-gateway-sonnet-v1`:
`campaign-state.json`, `progress.json`, frozen inputs, call receipts, attempts,
cost ledger, silver labels, review queue and the final campaign summary.
The final bundle destination is `data/pilot/pilot-300-gateway-sonnet-v1`.
Finalization prohibits network calls and validates bundle hashes and masks.
It also compares every original input and split against `pilot-smoke-v1`.
The initial supervisor used 75-second cooldowns and stopped after six failed
campaign invocations on 2026-10-06. Recovery on 2026-10-07 verified a successful
saved-request retry and a reset shared allowance (149 of 150 requests remaining).
The resumed supervisor uses five requests per minute and progressively longer
cooldowns: 120, 240, 480 and up to 900 seconds. Each physical request retains
its three-attempt limit. The supervisor permits at most 24 campaign invocations;
this does not increase the per-request attempt limit or $75 estimated ceiling.
It records safe rate
metadata and stops on repeated errors or the estimated cost ceiling. After
verified completion, it writes a dated status report and updates the milestone
only when all 900 candidate and 900 judge responses succeeded. Progress remains
available in `supervisor.log` and `supervisor-result.json`.

The candidate mapping now matches the 1,000-state dataset. The judge policy
differs: the 1,000-state labels use Terra/GPT-5.4, while these labels use Sonnet.
Any later combined dataset must retain that per-source annotation provenance.
No combined bundle or training run is created by this command. Source-use
restrictions remain applicable.
