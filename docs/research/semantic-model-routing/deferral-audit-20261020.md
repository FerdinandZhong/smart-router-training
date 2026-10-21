# Pilot deferral audit — 20 October 2026

The pilot needs evidence repair and a clearer annotation contract before training.
The audit found genuine ambiguity, missing relationships, incomplete judge inputs, and inconsistent approval standards.
Simply accepting more labels would hide these different problems.

The completed Opus run contains 72 successful reviews and eight failures.
Its dispositions are 38 `needs_clarification`, 33 `needs_metadata`, one `approved`, and eight failed.
The approved record belongs to training. There are no approved validation records.
These are automated judgments, not human approvals or execution results.

## Audit method and evidence

We inspected ten deferred cases and one approved control.
The ten cases cover six BIRD questions and four Spider questions.
Selection deliberately covers different failure mechanisms. These counts do not estimate their frequency across the dataset.

The audit compared saved Opus requests, proposals, full metadata units, source SQL, and implementation rules.
No new gateway calls were made. Pilot inputs, labels, and human records were not changed.
This is an agent audit of existing evidence, not another Opus review.

[Machine-readable evidence](../../status/2026-10-20-semantic-deferral-audit.json) includes record IDs, request hashes, and full relevant metadata.
The frozen pilot remains `pilot-20261010-v3`.
The source judge run remains `opus-5-5-review-20261019-v1`.
The dated 19 October status note records an earlier running snapshot; the counts above supersede that snapshot.

## Ten case findings

| Source record | Question or topic | Finding | Required action |
|---|---|---|---|
| BIRD 5165 | Number of female employees | Two catalogs contain employee gender fields. Scope ambiguity is real. | Preserve clarification. Do not infer gender from honorifics. |
| BIRD 6392 | Bitcoin versus Litecoin circulation | Both tables exist, but their join is undeclared. | Obtain independent schema/key evidence. |
| BIRD 4779 | Names of disappeared coins | Full `status` metadata says `extinct` means disappeared. The judge's clipped view omits this. | Supply the full relevant description and rejudge. |
| BIRD 5506 | Students absent over six months | Clipping hides part of the absence definition. The full prose still lacks an explicit duration unit. | Restore text, verify units, and separate retrieval from execution checks. |
| BIRD 4064 | Counties without Bakers Square | SQL finds counties with any other restaurant. The county description says country. The city join is undeclared. | Quarantine the SQL target and repair metadata from independent evidence. |
| BIRD 2750 | Black products that cannot be sold | Salability, sale-end date, and discontinuation imply different field choices within the same table. | Preserve business-definition clarification; label table relevance separately. |
| Spider 3762 | Channels owned by CCTV or HBS | `channel.Name` and `Owner` support retrieval. Deferral also demands execution and human confirmation. | Reassess under a structural retrieval contract with explicit evidence scope. |
| Spider 3752 | Programs never broadcast in the morning | The judge omitted `program`. Its fields and declared join exist in the full catalog. | Retrieve omitted dependency evidence and retain the original retrieval miss. |
| Spider 889 | Albums containing Reggae and Rock tracks | Required tables, fields, and joins exist. Deferral cites physical and whole-catalog checks. | Reassess context sufficiency separately from execution verification. |
| Spider 5676 | Students in PHL aged 20–25 | Eight catalogs contain matching Student structures. Metadata cannot identify the intended population. | Preserve clarification and duplicate-schema grouping. |

The approved control is Spider 903, concerning services used in first notification of loss.
Its independent Opus draft accepts short field descriptions and declared relationships without SQL execution.
The channel and album reviews reject similarly limited evidence.
This suggests inconsistent standards across direct drafting and second-stage critique.
It does not prove that the deferred cases should receive automatic approval.

## Four implementation findings

1. **The judge loses information that exists locally.** `build_input()` clips field descriptions at 180 characters in the current configuration.
   The coins example loses the exact value definition needed for the question.
   Preserve full descriptions for inspected units. Use bounded evidence retrieval instead of truncating their definitions.
2. **The review pool can omit a required table.** The `program` case contains a real candidate miss.
   A metadata lookup can recover the table and its declared Ossie relationship without source SQL.
   Report recall before and after expansion. Do not silently replace baseline candidate rankings with supervision.
3. **BIRD joins are missing systematically from this pilot.** All 38 BIRD catalogs contain zero relationship units.
   The 74 Spider catalogs contain 280 relationship units.
   `bird_catalogs()` currently converts column descriptions and explicitly creates empty relationship lists.
   This describes the imported metadata, not the underlying databases' actual constraints.
4. **The review contract mixes different judgments.** Prompts require human confirmation while the delegated workflow serves an automated review request.
   Approval also requires global unambiguity despite detailed evidence covering only the candidate pool.
   The human exporter requires catalog checks even for unknown candidates.
   Preserve that exporter; define a separate automated structural-training contract with explicit evidence limits.

## Repair plan

```text
Versioned catalog and evidence repairs
                  |
Separated relevance / context / clarification judgments
                  |
Targeted Opus re-review with complete relevant evidence
                  |
Frozen grouped silver train and validation exports
                  |
Matched retrieval baselines, then embedding training
```

1. **Repair the judge evidence builder first.** Preserve complete relevant field definitions and log every omitted unit.
   Add bounded lookup of declared relationship endpoints and potentially competing catalog definitions.
   Set explicit limits on retrieved units, tokens, and lookup rounds. Unresolved evidence remains unknown.
   This annotation workflow runs offline; it does not require Opus in the low-latency serving path.
2. **Version the annotation contract.** Record table relevance independently from complete-context sufficiency and clarification requirements.
   A missing join can block a complete context while leaving a table demonstrably relevant.
   A definition ambiguity can preserve the table choice while leaving field selection unresolved.
   Record physical-schema, value, SQL, and business-definition verification as separate evidence fields.
   An LLM assessment must not assert checks that were never performed.
3. **Keep two explicit task settings.** Use pooled catalogs for open-scope retrieval and clarification evaluation.
   Use supplied domain or workspace context for a separately identified scoped setting.
   A public benchmark's database scope may define a scoped experiment, but disclose that assumption.
   Never present it as observed user context or compare it directly with an unscoped task.
4. **Repair BIRD metadata independently.** Acquire available schema definitions and verify relevant join keys and cardinalities.
   Resolve conflicting descriptions with authoritative metadata. Record unsupported relationships as unresolved.
   Never manufacture joins or business definitions from reference SQL.
   Preserve version 3 and create a new catalog snapshot for actual metadata changes.
5. **Re-review a bounded diagnostic set.** Rejudge these ten cases plus the control under the new contract.
   Require the judge to use recovered evidence, preserve genuine ambiguities, and distinguish candidate misses from catalog defects.
   Compare direct drafting and critique under the same requirements.
   Handle the five rate-limit failures with paced retries; handle three inconsistent approvals through contract validation.
6. **Then prepare training data.** Freeze group assignments and keep related queries and schema duplicates together.
   Export automated labels with judge provenance, evidence scope, and unknown masks through a dedicated silver exporter.
   Audit positive and negative support in both training and validation before running optimization.
   Keep SQL-inconsistent cases out of execution-grounded targets until corrected and verified.

## Acceptance checks before training

- The coins review can inspect the complete `extinct` definition.
- The program review can retrieve `program` and its declared relationship without consulting source SQL.
- Employee and duplicate-Student cases retain explicit ambiguity unless input scope genuinely resolves it.
- Channel, album, and control cases use the same structural evidence standard.
- Missing BIRD relationships remain unknown until independently supported.
- Every observed label has traceable evidence. Unknown labels remain masked.
- Training and validation both contain usable positive and negative examples with documented coverage.
- The export distinguishes automated silver labels from human review and execution verification.

Start with BM25, frozen dense retrieval, and development-tuned fusion on the same repaired snapshot.
Compare table recall, complete-context coverage, clarification performance, and latency separately.
Train the embedding retriever only after those measurements and export checks pass.
GLiNER or Laya reranking remains a later comparison on a shared candidate pool.
