#!/usr/bin/env bash
# Explicit scoped rollback; requires idle workers and an intact protected baseline.
set -euo pipefail
umask 077
[[ $# == 3 && $3 == maintenance-confirmed ]] || { echo 'Usage: rollback_cross_node_gpu.sh CONTEXT EVIDENCE_DIRECTORY maintenance-confirmed' >&2; exit 2; }
context=$1; evidence=$2
[[ $(jq -r .context "$evidence/plan.json") == "$context" ]] || { echo 'Context mismatch' >&2; exit 1; }
ns=$(jq -r .namespace "$evidence/plan.json"); change=$(jq -r .change_id "$evidence/plan.json")
[[ $ns =~ ^[a-z0-9-]+$ && $change =~ ^[a-z0-9-]+$ ]] || exit 1
k() { kubectl --context "$context" --request-timeout=30s -n "$ns" "$@"; }
filter="ray-collective-$change"
# Remove only the label we added, guarded by baseline UID and expected value.
for pod in $(jq -r '.pods[]' "$evidence/plan.json"); do
  k get pod "$pod" -o json | jq '{metadata:{uid:.metadata.uid,labels:.metadata.labels}}' > "$evidence/$pod-rollback-current.json"
  expected=$(jq -r --arg pod "$pod" '.items[]|select(.name==$pod)|.uid' "$evidence/pods.before.json")
  [[ $(jq -r .metadata.uid "$evidence/$pod-rollback-current.json") == "$expected" ]] || { echo 'Pod was replaced; stop and review current workload' >&2; exit 1; }
  current=$(jq -r '.metadata.labels["ray-collective-change"] // ""' "$evidence/$pod-rollback-current.json")
  [[ -n $current ]] || continue
  [[ $current == "$change" ]] || { echo 'Label changed by another operator; refusing overwrite' >&2; exit 1; }
  patch=$(jq -nc --arg uid "$expected" --arg value "$change" \
    '[{op:"test",path:"/metadata/uid",value:$uid},{op:"test",path:"/metadata/labels/ray-collective-change",value:$value},{op:"remove",path:"/metadata/labels/ray-collective-change"}]')
  k patch pod "$pod" --type=json -p "$patch" >/dev/null
done
k get envoyfilter "$filter" --ignore-not-found -o json > "$evidence/filter.rollback-current.json"
if [[ -s "$evidence/filter.rollback-current.json" ]]; then
  [[ -f "$evidence/filter.applied.json" ]] || { echo 'No applied-filter baseline; inspect partial apply manually' >&2; exit 1; }
  jq -e --slurpfile baseline "$evidence/filter.applied.json" \
    '.metadata.uid==$baseline[0].uid and .spec==$baseline[0].spec' "$evidence/filter.rollback-current.json" >/dev/null || { echo 'Filter changed; refusing deletion' >&2; exit 1; }
  k delete envoyfilter "$filter" >/dev/null
fi
echo 'Rollback changes submitted. Verify proxy propagation and prior service behavior; do not infer success from API status alone.'
