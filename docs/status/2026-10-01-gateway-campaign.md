# 2026-10-01 — gateway campaign started

User approved a 1,000-state campaign with Flash Lite / Luna / Sol candidates and
Terra as independent judge. The mapping is different from the original pilot;
old labels are not reused. Sol is last among candidate phases.

- Three pinned SWE-Gym shards were verified against SHA256 checksums.
- 1,000 complete recorded pre-call states, 334 issues and 11 repositories.
- Original pilot issue groups and duplicate inputs excluded.
- Frozen splits: 702 train, 100 validation, 99 calibration, 99 test.
- One-state candidate compatibility checks succeeded for all three models.
- Initial FAST concurrency encountered 429s. Receipts were preserved and pacing
  added at 30 requests/minute, with cancellation on new rate-limit errors.
- FAST phase completed: 997 successful responses and three HTTP 502 errors.
  These errors remain unknown and are not negative routing labels.
- GENERAL is running. REASONING, Terra judgments and validated export are queued.
- Candidate output caps: 2,048; Terra judge cap: 1,024, low reasoning effort,
  JSON-object output, confidence threshold 0.8, blinded candidate identities.
- Estimated monetary guard: $150, using the supplied gateway prices without
  cache discounts and retaining conservative reservations for missing usage.
  This is not a guarantee of actual gateway charges.
- Local verification: 98 tests and 36 subtests passed. Annotation format guards
  allow only explicit JSON-object generation. Both engineering smoke and pilot
  training bundles retain checksum, target and mask validation.

Current process/phase: `runs/gateway-pilot-v1/campaign-state.json`. Results and
provenance accumulate in that run directory. The final bundle is planned at
`data/pilot/gateway-pilot-v1`; it is not yet available. The default AMP dataset
and original pilot are unchanged. No new training job has been launched.

See [campaign guide](../gateway-annotation-campaign.md). Final class support,
unknowns, judged quality, export integrity and actual token usage still need
review after collection. Source-use limitations remain in the source manifest.
