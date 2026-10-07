# Cross-pod NCCL connectivity: IT review package

**Status:** Bash review draft, checked locally with a fake Kubernetes client.
The underlying two-pod EnvoyFilter/probe recipe was exercised in the development
CAI environment; this new Bash automation has not been applied to a live cluster.
This package is not a certification of compliance or a general production rollout.

## Purpose and scope

Enable the existing tested TCPStore/Gloo/NCCL communication path between two
named GPU worker pods on distinct nodes. Environment selection is configurable:
`--python` names the absolute interpreter present in **both** pods. Default:
`/home/cdsw/.venv-router-train/bin/python`. No packages are installed by the script.

The filter replaces the TLS and HTTP inspectors on inbound `virtualInbound`,
retains the prior 15006–15007 exclusion, and excludes destination ports
**32768–60999** (61000 is exclusive). The selector uses a unique change label on
the two specified pods, in the specified namespace. It retains sidecar injection,
outbound handling and inspection on other inbound ports.

**Security impact:** incoming mesh TLS on the excluded ports is no longer
inspected/terminated by Envoy. Treat these collective connections as plaintext.
Do not approve this workaround where policy requires encryption on this path.
Agree an alternative encrypted/supported network design with the platform and
security teams in that case. The script does not lower PeerAuthentication, modify
NetworkPolicies, open firewalls, expose NodePorts, disable authentication, restart
applications, change cluster RBAC or fetch/install remote code.

## What IT must review

1. Approved change reference, owner, target cluster/namespace/pods, maintenance
   window, exception expiry and rollback owner. The script records the supplied
   change ID; it does not validate your organization's approval system.
2. Existing mesh/root, namespace and workload PeerAuthentication, including
   port overrides, and existing EnvoyFilters. Namespace PERMISSIVE is a prerequisite,
   not proof that the effective policy on every workload is permissive. Explicit
   matching STRICT policies in the namespace are rejected; mesh/root policy and
   all other overrides require platform review. Do not modify STRICT policies
   just to make the script succeed.
3. Actual Istio/Envoy version and listener structure. EnvoyFilter is tied to proxy
   internals and needs validation after upgrades. The reference environment used
   Istio `1.30.3-solo-fips-distroless`; that observation is not a support guarantee
   for other versions. Avoid overlap with the earlier trial filter or other
   listener-filter replacements affecting these pods.
4. CNI enforcement and existing ingress/egress isolation. Both directions must
   allow the intended pod pair's TCP collectives and the existing Ray/rendezvous
   traffic. Rendezvous is TCP 29601; collective ephemeral ports are 32768–60999.
   No namespace-wide or internet-facing allow rule is generated. NetworkPolicy
   rules are additive, so an additional narrow allow rule cannot revoke broader
   existing permissions. IT must inspect the effective policy set.
5. Namespace-scoped operator access. Reads: pods, EnvoyFilters, PeerAuthentication
   and NetworkPolicies (get/list). Apply: patch the two pods, create pods/exec,
   create the scoped EnvoyFilter. Rollback: patch those pods and delete that filter.
   Do not grant cluster-admin for this procedure. Kubernetes RBAC may require
   create on a resource type rather than a named resource; use admission/change
   controls where resource-name restrictions cannot express the required scope.
6. GPU workers must be idle and training/inference stopped before probing or
   rolling back. The flags are operator attestations; they do not detect running
   Ray tasks. Do not execute against an active shared production workload.

## Plan, review, apply

Keep the companion files together. Dependencies: Bash 3.2+, kubectl, jq, mktemp,
grep, and the existing remote Python/PyTorch/CUDA environment.

```bash
bash setup_cross_node_gpu.sh \
  --context '<approved-context>' --namespace '<approved-namespace>' \
  --pod0 '<gpu-pod-a>' --pod1 '<gpu-pod-b>' --change-id chg12345 \
  --python /home/cdsw/.venv-router-train/bin/python \
  --evidence /secure/change-records/chg12345-plan
```

Default `plan` only reads scoped metadata/policies and renders the filter. It does
not execute processes in the pods or mutate Kubernetes resources. The evidence
parent directory must already exist; the chosen leaf must be new. Files are
created under umask 077 and the evidence directory is mode 0700. Review the
rendered filter and baseline with IT before applying. Record mesh-level findings
separately; the script intentionally does not request cluster-wide reads.

```bash
bash setup_cross_node_gpu.sh \
  --context '<approved-context>' --namespace '<approved-namespace>' \
  --pod0 '<gpu-pod-a>' --pod1 '<gpu-pod-b>' --change-id chg12345 \
  --python /home/cdsw/.venv-router-train/bin/python \
  --mode apply --maintenance-confirmed --plaintext-approved \
  --evidence /secure/change-records/chg12345-apply
```

Apply re-reads a fresh baseline, validates the selected GPU environment and port
range, performs server-side dry-run, patches labels with UID/resourceVersion
preconditions, and creates a new filter rather than overwriting an existing one.
It requires two distinct Kubernetes nodes and rejects an existing change label or
resource-name collision. A race/concurrent pod update fails rather than forcing a
patch. No automatic restart or destructive reset is performed.

Then it verifies both inspector exclusions, streams the included probe into each
pod without copying files, and requires both successful process exits and correct
TCPStore/Gloo/NCCL results. The probe has a 180-second native-process alarm and
45-second collective timeouts; kubectl streams have a 240-second timeout. Evidence
contains selected metadata/policy specs, environment versions and probe logs.
A successful apply API call alone is not a successful connectivity test.

**Partial failure:** networking/label changes may already exist. The script stops
and preserves evidence rather than silently continuing or blindly rolling back.
Inspect the baseline, current pods and filter with the platform owner.

## Rollback

Stop any jobs using the connection first. Use the **apply** evidence directory:

```bash
bash rollback_cross_node_gpu.sh '<approved-context>' \
  /secure/change-records/chg12345-apply maintenance-confirmed
```

Rollback removes only the introduced label, testing the original pod UID and
expected label value. It deletes only the named filter if its UID/spec still
match the recorded applied baseline. Changed/replaced resources cause a stop for
manual review. If apply stopped before saving `filter.applied.json`, inspect any
partially created filter manually; the rollback script refuses blind deletion.
These guards do not provide a transaction across Kubernetes resources. Coordinate
with other operators throughout apply/rollback, including the short interval
between filter verification and deletion. No competing writes should occur.

Verify proxy propagation and the prior application's normal behavior after
rollback. Archive evidence under your IT retention/access policy; it contains
internal workload/network identifiers. No Kubernetes Secrets, kubeconfig contents,
full pod environment dumps or full Envoy config dumps are saved. A copied probe
log should still be reviewed before sharing outside the organization.

## References and implementation provenance

- Filter semantics adapted from `ray-serve-cai/deploy/istio/`
  `ray-collective-protocol-inspection-trial.yaml` in the local tested checkout.
- Python collective probe preserved from the existing `../scripts/collective_probe.py`.
- [Istio EnvoyFilter reference](https://istio.io/latest/docs/reference/config/networking/envoy-filter/)
- [Istio security and policy scope](https://istio.io/latest/docs/concepts/security/)
- [Kubernetes NetworkPolicy behavior](https://kubernetes.io/docs/concepts/services-networking/network-policies/)

Use `SHA256SUMS` to verify package contents. Local checks cover default read-only
behavior, context/namespace/selector scope, mandatory apply approval flags, and
shell syntax. Live apply, proxy propagation and rollback require staging validation
by the infrastructure team before approval for the customer environment.
