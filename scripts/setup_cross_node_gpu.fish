#!/usr/bin/env fish
# Configure the tested Istio exception and probe two GPU worker pods using a selected virtualenv.
# Run from an administrator workstation before starting the training job.

function fail --argument-names message
    echo "ERROR: $message" >&2
    exit 1
end

if test (count $argv) -lt 3; or test (count $argv) -gt 4
    echo 'Usage: fish scripts/setup_cross_node_gpu.fish POD0 POD1 NAMESPACE [PYTHON_EXECUTABLE]' >&2
    exit 2
end

set pod0 $argv[1]
set pod1 $argv[2]
set ns $argv[3]
set python /home/cdsw/.venv-router-train/bin/python
if test (count $argv) -eq 4
    set python $argv[4]
end
string match -q '/*' -- "$python"; or fail 'PYTHON_EXECUTABLE must be an absolute path inside both pods.'
test "$pod0" != "$pod1"; or fail 'Choose two distinct GPU-host pods.'

for tool in kubectl jq mktemp sed fish realpath seq
    command -q $tool; or fail "Missing command: $tool"
end

set script_dir (realpath (dirname (status filename)))
set repo_dir (realpath "$script_dir/..")
set cluster_dir "$repo_dir/vendor/ray-serve-cai"
if not test -r "$cluster_dir/deploy/istio/ray-collective-protocol-inspection-trial.yaml"
    if test -r "$repo_dir/deploy/istio/ray-collective-protocol-inspection-trial.yaml"
        set cluster_dir "$repo_dir"
    else
        set cluster_dir "$repo_dir/ray-serve-cai"
    end
end
set manifest "$cluster_dir/deploy/istio/ray-collective-protocol-inspection-trial.yaml"
set probe "$script_dir/run_collective_probe.fish"
test -r "$manifest"; or fail "Missing tested EnvoyFilter: $manifest"
test -r "$probe"; or fail "Missing probe runner: $probe"
test -r "$script_dir/collective_probe.py"; or fail 'Missing collective_probe.py'

set filter ray-collective-http-inspection-trial
set label ray-collective-inspection-trial
set work_dir (mktemp -d /tmp/ray-cross-node.XXXXXX); or fail 'Cannot create evidence directory.'
echo "Kubernetes context: "(kubectl config current-context)
echo "Evidence and rollback baseline: $work_dir"
echo "Namespace: $ns; rank 0: $pod0; rank 1: $pod1"
echo "Remote Python: $python (isolated mode)"

kubectl -n "$ns" get pods "$pod0" "$pod1" -o json > "$work_dir/pods.before.json"; or fail 'Cannot read both pods.'
kubectl -n "$ns" get envoyfilter "$filter" --ignore-not-found -o yaml > "$work_dir/filter.before.yaml"; or fail 'Cannot read existing filter.'
kubectl get peerauthentication.security.istio.io -A -o yaml > "$work_dir/peerauth.before.yaml"; or fail 'Cannot read PeerAuthentication policies.'

for pod in $pod0 $pod1
    set pod_json (kubectl -n "$ns" get pod "$pod" -o json); or fail "Cannot read $pod"
    echo "$pod_json" | jq -e --arg pod "$pod" '.status.phase == "Running" and .status.podIP != null and (([.spec.containers[]?.name, .spec.initContainers[]?.name] | index("istio-proxy")) != null)' > /dev/null
    or fail "$pod must be Running with an Istio proxy and a pod IP."
    kubectl -n "$ns" exec "$pod" -c engine -- nvidia-smi -L; or fail "GPU check failed on $pod."
    # Fail before changing networking if the selected environment is not ready.
    # -I excludes CAI add-on paths, PYTHONHOME, and user site packages.
    kubectl -n "$ns" exec "$pod" -c engine -- "$python" -I -c 'import sys, torch; assert torch.cuda.is_available(), "Selected environment cannot access CUDA"; assert torch.distributed.is_gloo_available(), "Gloo unavailable"; assert torch.distributed.is_nccl_available(), "NCCL unavailable"; print("Environment:", sys.executable, "Python", sys.version.split()[0], "Torch", torch.__version__, "CUDA", torch.version.cuda, "GPU", torch.cuda.get_device_name(0))'
    or fail "Environment preflight failed on $pod using $python. Check PyTorch, CUDA and collective backends."
    set port_range (kubectl -n "$ns" exec "$pod" -c engine -- cat /proc/sys/net/ipv4/ip_local_port_range); or fail "Cannot read port range on $pod."
    string match -qr '32768\s+60999' -- "$port_range"; or fail "$pod has unexpected ephemeral range: $port_range"
end

set auth_policy "auth-policy-$ns"
set mode (kubectl -n "$ns" get peerauthentication "$auth_policy" -o jsonpath='{.spec.mtls.mode}' 2>/dev/null)
if test "$mode" != PERMISSIVE
    fail "Expected namespace PeerAuthentication $auth_policy=PERMISSIVE; got '$mode'. Review $work_dir/peerauth.before.yaml."
end
echo 'Check the saved PeerAuthentication policies for any stricter workload-specific selector.'

sed "s/namespace: mlx-user-2/namespace: $ns/" "$manifest" > "$work_dir/collective-filter.yaml"; or fail 'Cannot render EnvoyFilter.'
kubectl apply --dry-run=server -f "$work_dir/collective-filter.yaml"; or fail 'EnvoyFilter server validation failed.'
kubectl -n "$ns" label pods "$pod0" "$pod1" "$label=true" --overwrite; or fail 'Pod labeling failed.'
kubectl apply -f "$work_dir/collective-filter.yaml"; or fail 'EnvoyFilter apply failed. See baseline for rollback.'

# Istio propagates the filter asynchronously. Require both inspectors on both pods.
set inspection_query '[.. | objects | select(.name? == "envoy.filters.listener.tls_inspector" or .name? == "envoy.filters.listener.http_inspector") | select(any(.filter_disabled?.or_match?.rules[]?; .destination_port_range?.start == 32768 and .destination_port_range?.end == 61000)) | .name] | unique | length == 2'
for pod in $pod0 $pod1
    set verified 0
    for attempt in (seq 1 12)
        kubectl -n "$ns" exec "$pod" -c engine -- "$python" -I -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:15000/config_dump", timeout=10).read().decode())' > "$work_dir/$pod-envoy.json" 2> "$work_dir/$pod-envoy-error.txt"
        and jq -e "$inspection_query" "$work_dir/$pod-envoy.json" > /dev/null
        if test $status -eq 0
            set verified 1
            echo "$pod: both inbound inspectors exclude ports 32768-60999"
            break
        end
        sleep 5
    end
    test $verified -eq 1; or fail "Envoy inspection was not confirmed on $pod. See $work_dir."
end

echo 'Running TCPStore, Gloo, and NCCL probe. Training jobs must be stopped first.'
pushd "$work_dir" > /dev/null; or fail "Cannot enter $work_dir"
fish "$probe" "$pod0" "$pod1" "$ns" "$python"
set probe_status $status
popd > /dev/null
test $probe_status -eq 0; or fail "Collective probe failed. Inspect logs in $work_dir."
echo "PASS: cross-pod TCPStore, Gloo, and NCCL on $pod0 and $pod1"
echo "Keep $work_dir for rollback; see $cluster_dir/docs/CROSS_NODE_GPU_DEPLOYMENT.md."
