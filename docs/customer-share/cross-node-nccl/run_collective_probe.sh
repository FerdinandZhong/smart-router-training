#!/usr/bin/env bash
set -euo pipefail
umask 077
[[ $# == 7 ]] || { echo 'Usage: run_collective_probe.sh CONTEXT NAMESPACE POD0 POD1 PYTHON EVIDENCE' >&2; exit 2; }
context=$1; ns=$2; pod0=$3; pod1=$4; python=$5; evidence=$6
# Last argument is an explicit idle-worker confirmation, required for direct use.
[[ $7 == maintenance-confirmed ]] || { echo 'Idle GPU workers must be confirmed' >&2; exit 2; }
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
master=$(kubectl --context "$context" --request-timeout=30s -n "$ns" get pod "$pod0" -o jsonpath='{.status.podIP}')
[[ -n $master ]] || exit 1
pids=()
cleanup() { for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done; }
trap cleanup EXIT
for rank in 0 1; do
  pod=$pod0; [[ $rank == 0 ]] || pod=$pod1
  kubectl --context "$context" --request-timeout=240s -n "$ns" exec -i "$pod" -c engine -- \
    env NCCL_DEBUG=INFO NCCL_DEBUG_SUBSYS=INIT,NET,ENV NCCL_IB_DISABLE=1 \
    NCCL_SOCKET_IFNAME=eth0 GLOO_SOCKET_IFNAME=eth0 TORCH_DISTRIBUTED_DEBUG=DETAIL \
    "$python" -I -u - --rank "$rank" --master "$master" \
    < "$script_dir/collective_probe.py" > "$evidence/rank$rank.log" 2>&1 &
  pids+=("$!")
done
result=0
for pid in "${pids[@]}"; do wait "$pid" || result=1; done
pids=()
for rank in 0 1; do
  for marker in 'PASS TCPStore exchange' 'PASS Gloo all_reduce = 3' 'PASS NCCL all_reduce = 3' 'DONE'; do
    grep -Fq "RANK $rank: $marker" "$evidence/rank$rank.log" || result=1
  done
done
[[ $result == 0 ]] || { echo "Probe failed; review protected logs in $evidence" >&2; exit 1; }
echo 'PASS: both ranks, correct CPU/GPU all-reduce result, both process exit statuses.'
