# Return to the current router work

Recorded: 9 October 2026.

The original checkout remains at:

```text
/Users/zhongqishuai/Projects/cldr_projects/smart_router_training
branch: main
HEAD: 2b7eecf37d0053951576bca654f6efd204e07950
```

The isolated research worktree is:

```text
/tmp/smart-router-semantic-research-20261009
branch: research/semantic-model-routing
```

The side branch contains research documents only.
It starts from committed HEAD and does not include the original checkout's unfinished GLiNER, dataset, or experiment changes.
No stash, reset, branch switch, deployment, or training submission was required in the original checkout.

## Resume priorities

1. Recheck the current GLiNER continuation job and retrieve its final metrics.
2. Audit label quality, route disagreement, dataset difficulty, and grouped split integrity.
3. Extend controlled model and training comparisons before selecting a new loss.
4. Report validation accuracy alongside balanced accuracy, calibration, and actual quality–cost routing outcomes.

The last recorded continuation submission was `gliner-gateway-1300-continuation-20261008-01`.
This research review did not query its live status.
Consult the original checkout's current comparison notes before resuming experiments.

The original tracked changes were checked against the patch recorded before this side work.
The comparison excludes `data/`; data files were not modified by this task.
The patch SHA-256 was:

```text
349a80377f0ae247efc4535dbc535a627d476d16eab9c2869e39c86c991ffae7
```

Return by using the original checkout; it is already on `main`.
Keep the research worktree available for review.
Merge or cherry-pick the research commit only when this direction should enter the main project history.
