# Visual and information design

This repository currently has command-line workflows and existing Ray Dashboard,
Swagger and TensorBoard interfaces. It has no custom product frontend or bespoke
brand system. These rules govern project-authored docs, diagrams, metrics and any
future UI; upstream dashboards retain their native appearance.

## Information hierarchy

Present the task, current status and next action first. Separate implemented
behavior from proposals and historical results. Give each run a stable submission
ID, and place its dataset version, model identity, label semantics and evaluation
scope beside its results. Keep operational setup detail in operator views.

Use short headings, plain language, tables for comparable values, and fenced
text diagrams for deployment/data flow. Use exact filenames and copyable commands.
Show placeholders as `<GPU_POD_A>` or `<NAMESPACE>`; never imply they are runnable
values. Display dates on progress snapshots and link to the evidence source.

## Status and metric semantics

| Display | Meaning |
|---|---|
| Created / starting | Resource request accepted; not yet ready |
| Running / alive | State confirmed by the relevant CAI or Ray API |
| Passed | Named validation completed with evidence |
| Failed | Valid evaluated failure or failed operation, with its scope stated |
| Unknown / not verified | Missing observation, unresolved error, or unrun check |

Do not communicate status through color alone. Any future project UI should use
text labels with green for passed/ready, amber for pending/unknown, and red for
failed, with readable contrast and keyboard-accessible controls. Avoid unverified
percentages, decorative charts and animations that obscure operational state.

Probabilities use a documented 0–1 or percentage scale. Routing class probabilities
are independent and need not sum to one. Unknown is displayed as unknown, never
as zero. Show denominators and sample/group counts alongside aggregate results.
Label synthetic fixtures, setup events and controlled diagnostics explicitly.

## Training charts

Use submission ID and stage as the run hierarchy. Keep resumed global step numbers
continuous. Current scalar tags are `diagnostic/loss`, `train/learning_rate` and
`perf/step_seconds`; the last measures rank-zero update plus global-loss reduction,
not pure GPU kernel time. Only rank zero writes the globally reduced loss curve.

Axis labels include units. Do not compare runs without displaying dataset/task
versions and metric definitions. A downward diagnostic loss curve is evidence of
the controlled optimization check, not evidence of router quality.

## Review checklist

- Can a reader distinguish planned work, observed status and verified results?
- Are units, label semantics and the experiment scope explicit?
- Do commands use real supported flags and clearly marked placeholders?
- Are navigation links valid and credentials absent?
- Is customer-specific configuration kept out of general UI assumptions?
