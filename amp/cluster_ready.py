#!/usr/bin/env python3
"""AMP readiness gate: pass only when Ray reports enough alive GPU nodes."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from amp.jobs import cluster_address


def token():
    return (os.environ.get("CDSW_APIV2_KEY") or os.environ.get("CML_API_KEY") or "").strip()


def fetch_nodes(root, api_key, urlopen=urllib.request.urlopen):
    """Ray-observed nodes from the head's management API (ray.nodes() joined with CAI identity)."""
    if not api_key:
        raise RuntimeError("Run inside the CAI project with its injected API credentials")
    url = cluster_address(root).removesuffix("dashboard/") + "api/v1/resources/nodes"
    with urlopen(urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"}), timeout=15) as response:
        return json.load(response)["nodes"]


def gpu_nodes(nodes):
    return [n for n in nodes if n.get("alive") and (n.get("resources") or {}).get("GPU", 0) > 0]


def wait_ready(fetch, need=2, timeout=1200, interval=15, sleep=time.sleep, clock=time.monotonic):
    deadline, nodes = clock() + timeout, []
    while True:
        try:
            nodes = fetch()
        except Exception as error:  # head or management API may still be starting
            print(f"Nodes unavailable: {error}", flush=True)
        else:
            print(f"{len(gpu_nodes(nodes))}/{need} alive GPU nodes", flush=True)
            if len(gpu_nodes(nodes)) >= need:
                return True, nodes
        if clock() >= deadline:
            return False, nodes
        sleep(interval)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout-minutes", type=float, default=20)
    parser.add_argument("--min-gpu-nodes", type=int, default=2)
    args = parser.parse_args()
    ok, nodes = wait_ready(lambda: fetch_nodes(ROOT, token()), args.min_gpu_nodes, args.timeout_minutes * 60)
    summary = [{"node_id": n.get("node_id"), "node_type": n.get("node_type"), "alive": bool(n.get("alive")),
                "gpus": (n.get("resources") or {}).get("GPU", 0), "cml_status": n.get("cml_status")} for n in nodes]
    state = ROOT / ".amp-state"
    state.mkdir(exist_ok=True)
    (state / "cluster-ready.json").write_text(json.dumps(
        {"checked_at": datetime.now(timezone.utc).isoformat(), "ready": ok,
         "required_gpu_nodes": args.min_gpu_nodes, "nodes": summary}, indent=2) + "\n")
    if not ok:
        for node in summary:
            print(f"  node {node['node_id']}: type={node['node_type']} alive={node['alive']} gpus={node['gpus']} cml_status={node['cml_status']}")
        raise SystemExit(f"Ray did not report {args.min_gpu_nodes} alive GPU nodes in time")
    print("Cluster ready: " + ", ".join(n["node_id"] for n in summary if n["alive"] and n["gpus"]))


if __name__ == "__main__":
    main()
