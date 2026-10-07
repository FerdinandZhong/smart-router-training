#!/usr/bin/env bash
# IT-review draft. Tested filter semantics; this Bash automation is not live-certified.
set -euo pipefail
umask 077
export LC_ALL=C
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
usage() {
  cat <<'USAGE'
Usage: bash setup_cross_node_gpu.sh --context CONTEXT --namespace NAMESPACE \
  --pod0 POD --pod1 POD --change-id CHANGE [--python ABSOLUTE_PATH] \
  [--mode plan|apply] [--evidence NEW_DIRECTORY] [--maintenance-confirmed] \
  [--plaintext-approved]
Default mode: plan. Plan reads scoped Kubernetes metadata and renders a manifest;
it does not patch pods, apply networking changes or run GPU processes.
Apply requires an approved change ID, both approval flags, and idle GPU workers.
USAGE
}
mode=plan; context=; ns=; pod0=; pod1=; change=; evidence=
python=/home/cdsw/.venv-router-train/bin/python
maintenance=false; plaintext=false
while (($#)); do
  case "$1" in
    --context|--namespace|--pod0|--pod1|--change-id|--python|--mode|--evidence)
      (($#>=2)) || fail "Missing value for $1"
      case "$1" in
        --context) context=$2;; --namespace) ns=$2;; --pod0) pod0=$2;;
        --pod1) pod1=$2;; --change-id) change=$2;; --python) python=$2;;
        --mode) mode=$2;; --evidence) evidence=$2;;
      esac; shift 2;;
    --maintenance-confirmed) maintenance=true; shift;;
    --plaintext-approved) plaintext=true; shift;;
    --help|-h) usage; exit 0;;
    *) fail "Unknown argument: $1";;
  esac
done
[[ $mode == plan || $mode == apply ]] || fail 'Mode must be plan or apply'
[[ -n $context && -n $ns && -n $pod0 && -n $pod1 && -n $change ]] || { usage; exit 2; }
for value in "$ns" "$pod0" "$pod1" "$change"; do
  [[ $value =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ && ${#value} -le 63 ]] || fail 'Use lowercase DNS-label identifiers (max 63 characters)'
done
[[ ${#change} -le 40 ]] || fail 'Change ID must be at most 40 characters'
[[ $pod0 != "$pod1" ]] || fail 'Specify distinct pods'
[[ $python == /* && $python != *$'\n'* ]] || fail 'Python must be an absolute in-pod path'
for tool in kubectl jq mktemp bash grep; do command -v "$tool" >/dev/null || fail "Missing command: $tool"; done
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
for file in collective-filter.template.json collective_probe.py run_collective_probe.sh; do
  [[ -r "$script_dir/$file" ]] || fail "Missing companion: $file"
done
k() { kubectl --context "$context" --request-timeout=30s -n "$ns" "$@"; }
label=ray-collective-change; filter="ray-collective-$change"
if [[ -z $evidence ]]; then evidence=$(mktemp -d "${TMPDIR:-/tmp}/ray-cross-node.XXXXXX");
else [[ ! -e $evidence ]] || fail 'Evidence directory must not already exist'; mkdir -m 700 -- "$evidence"; fi
chmod 700 "$evidence"
trap 'rc=$?; if ((rc)); then printf "Stopped; inspect protected evidence and rollback instructions: %s\n" "$evidence" >&2; fi' EXIT
printf 'Mode: %s; context: %s; namespace: %s; change: %s\nEvidence: %s\n' "$mode" "$context" "$ns" "$change" "$evidence"
# Only bounded permissions; do not read Secrets or cluster-wide pod inventories.
for resource in pods envoyfilters.networking.istio.io peerauthentications.security.istio.io networkpolicies.networking.k8s.io; do
  [[ $(k auth can-i get "$resource") == yes ]] || fail "Cannot read $resource in $ns"
done
k get pods "$pod0" "$pod1" -o json | jq --arg label "$label" \
  '{items:[.items[] | {name:.metadata.name,uid:.metadata.uid,resourceVersion:.metadata.resourceVersion,node:.spec.nodeName,phase:.status.phase,ip:.status.podIP,label_present:(.metadata.labels|has($label)),label_value:.metadata.labels[$label],labels:.metadata.labels,containers:[.spec.containers[]?.name,.spec.initContainers[]?.name]}]}' > "$evidence/pods.before.json"
jq -e '.items|length==2 and all(.[]; .phase=="Running" and .ip!=null and (.containers|index("engine"))!=null and (.containers|index("istio-proxy"))!=null and .label_present==false)' "$evidence/pods.before.json" >/dev/null || fail 'Require two Running engine/Istio pods with no existing change label'
[[ $(jq '[.items[].node]|unique|length' "$evidence/pods.before.json") == 2 ]] || fail 'Require distinct Kubernetes nodes'
# Reject name collisions, including unrelated resources. Never overwrite a prior filter.
k get envoyfilter "$filter" --ignore-not-found -o json > "$evidence/filter.before.json"
[[ ! -s "$evidence/filter.before.json" ]] || fail 'Filter already exists; use a new change ID or review rollback'
k get pods -l "$label=$change" -o json | jq -e '.items|length==0' >/dev/null || fail 'Selector would include other pods'
k get peerauthentication -o json | jq '{items:[.items[]|{name:.metadata.name,spec:.spec}]}' > "$evidence/namespace-peer-auth.json"
k get networkpolicy -o json | jq '{items:[.items[]|{name:.metadata.name,spec:.spec}]}' > "$evidence/namespace-network-policies.json"
k get envoyfilter -o json | jq '{items:[.items[]|{name:.metadata.name,spec:.spec}]}' > "$evidence/namespace-envoy-filters.json"
jq --arg ns "$ns" --arg name "$filter" --arg change "$change" \
  '.metadata={name:$name,namespace:$ns,annotations:{"ray-collective-change-reference":$change}} | .spec.workloadSelector.labels={"ray-collective-change":$change}' \
  "$script_dir/collective-filter.template.json" > "$evidence/collective-filter.json"
jq -n --arg context "$context" --arg namespace "$ns" --arg pod0 "$pod0" --arg pod1 "$pod1" \
  --arg change "$change" --arg python "$python" --arg mode "$mode" \
  '{context:$context,namespace:$namespace,pods:[$pod0,$pod1],change_id:$change,python:$python,mode:$mode,plaintext_exception:"inbound 32768-60999",rendezvous_port:29601}' > "$evidence/plan.json"
printf 'Rendered %s\nReview mesh/root and workload PeerAuthentication, existing EnvoyFilters, network isolation and rollback before apply.\n' "$evidence/collective-filter.json"
[[ $mode == apply ]] || exit 0
[[ $maintenance == true && $plaintext == true ]] || fail 'Apply requires --maintenance-confirmed and --plaintext-approved'
for pair in 'patch pods' 'create pods/exec' 'create envoyfilters.networking.istio.io' 'delete envoyfilters.networking.istio.io'; do
  read -r verb resource <<< "$pair"
  [[ $(k auth can-i "$verb" "$resource") == yes ]] || fail "Missing $verb $resource permission"
done
# Namespace PERMISSIVE is necessary for this recipe, not proof of effective policy.
jq -e '[.items[]|select((.spec.selector.matchLabels // {}|length)==0 and .spec.mtls.mode=="PERMISSIVE")]|length==1' "$evidence/namespace-peer-auth.json" >/dev/null || fail 'Require one explicit namespace PERMISSIVE policy; do not change policies automatically'
# Reject explicit STRICT namespace/workload policies matching either selected pod.
jq -e --slurpfile pods "$evidence/pods.before.json" --arg change "$change" '
  [.items[] as $policy | $pods[0].items[] |
   (.labels + {"ray-collective-change":$change}) as $labels |
   select(all(($policy.spec.selector.matchLabels // {} | to_entries[]); $labels[.key]==.value)) |
   select($policy.spec.mtls.mode=="STRICT" or any($policy.spec.portLevelMtls[]?; .mode=="STRICT"))] | length==0
' "$evidence/namespace-peer-auth.json" >/dev/null || fail 'A matching explicit STRICT policy exists; review with IT instead of weakening it'
for pod in "$pod0" "$pod1"; do
  k exec "$pod" -c engine -- "$python" -I -c 'import sys,torch; assert torch.cuda.is_available(); assert torch.distributed.is_gloo_available(); assert torch.distributed.is_nccl_available(); print(sys.executable,torch.__version__,torch.version.cuda,torch.cuda.get_device_name(0))' > "$evidence/$pod-environment.txt"
  range=$(k exec "$pod" -c engine -- cat /proc/sys/net/ipv4/ip_local_port_range)
  [[ $range =~ ^32768[[:space:]]+60999$ ]] || fail 'Unexpected ephemeral port range'
done
k create --dry-run=server -f "$evidence/collective-filter.json" > "$evidence/server-validation.txt"
# UID/resourceVersion preconditions prevent patching replaced or concurrently changed pods.
for pod in "$pod0" "$pod1"; do
  jq --arg pod "$pod" --arg value "$change" \
    '[.items[]|select(.name==$pod)|{op:"test",path:"/metadata/uid",value:.uid},{op:"test",path:"/metadata/resourceVersion",value:.resourceVersion},{op:"add",path:"/metadata/labels/ray-collective-change",value:$value}]' \
    "$evidence/pods.before.json" > "$evidence/$pod-patch.json"
  k patch pod "$pod" --type=json --patch-file "$evidence/$pod-patch.json" > "$evidence/$pod-patched.txt"
done
k create -f "$evidence/collective-filter.json" > "$evidence/filter-created.txt"
k get envoyfilter "$filter" -o json | jq '{uid:.metadata.uid,spec:.spec}' > "$evidence/filter.applied.json"
# Store only the relevant inspector result, not the full Envoy admin configuration.
query='[.. | objects | select(.name? == "envoy.filters.listener.tls_inspector" or .name? == "envoy.filters.listener.http_inspector") | select(any(.filter_disabled?.or_match?.rules[]?; .destination_port_range?.start == 32768 and .destination_port_range?.end == 61000)) | .name] | unique'
for pod in "$pod0" "$pod1"; do
  verified=false
  for ((attempt=0; attempt<12; attempt++)); do
    if k exec "$pod" -c engine -- "$python" -I -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:15000/config_dump",timeout=10).read().decode())' \
      2> "$evidence/$pod-inspection-error.txt" | jq "$query" > "$evidence/$pod-inspectors.json" && \
      jq -e 'length==2' "$evidence/$pod-inspectors.json" >/dev/null; then verified=true; break; fi
    sleep 5
  done
  [[ $verified == true ]] || fail "Inspector exception not confirmed on $pod"
done
bash "$script_dir/run_collective_probe.sh" "$context" "$ns" "$pod0" "$pod1" "$python" "$evidence" maintenance-confirmed
printf 'PASS: both ranks completed TCPStore, Gloo and NCCL. Keep protected evidence; use reviewed rollback after the change window.\n'
