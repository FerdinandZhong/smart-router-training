#!/usr/bin/env python3
"""Bounded Ray pilot audit and retrieval diagnostic; never approve or train labels."""
from pathlib import Path
import argparse
from collections import Counter
import importlib.metadata
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))


def verify(output: Path) -> dict:
    from jsonschema import Draft202012Validator
    from smart_router.semantic_intake import digest
    from smart_router.semantic_pilot import checked_bundle, read_jsonl, metadata_units, audit_reviews
    pilot = ROOT / "data/semantic-research/pilot-20261010-v3"
    manifest = checked_bundle(pilot, "semantic-pilot-v1")
    schema_path = ROOT / "data/semantic-research/raw-20261010/ossie-schema.json"
    schema = json.loads(schema_path.read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    derived = []
    for record in read_jsonl(pilot / "catalog_reviews.template.jsonl"):
        path = pilot / record["path"]
        catalog = json.loads(path.read_text())
        validator.validate(catalog)
        derived.extend(metadata_units(record["catalog_id"], catalog))
    units = read_jsonl(pilot / "metadata_units.jsonl")
    assert sorted(derived, key=lambda r: r["unit_id"]) == sorted(units, key=lambda r: r["unit_id"])
    ids = {u["unit_id"] for u in units}
    assert len(ids) == len(units)
    assert all(set(u["dependencies"]) <= ids for u in units)
    episodes = read_jsonl(pilot / "episodes.supervision.jsonl")
    assert len({e["record_id"] for e in episodes}) == len(episodes)
    groups, questions = {}, {}
    for e in episodes:
        assert set(e["input"]) == {"question", "confirmed_history", "catalog_snapshot"}
        assert e["input"]["catalog_snapshot"] == manifest["catalog_snapshot"]
        for mapping, key in [(groups, e["data_group_id"]), (questions, " ".join(e["input"]["question"].casefold().split()))]:
            assert mapping.setdefault(key, e["pilot_split"]) == e["pilot_split"]
        assert set(e["supervision_only"]["weak_table_ids"] or []) <= ids
    reviews = ROOT / "data/semantic-research/review-work-20261010-v2"
    review, _ = audit_reviews(pilot, reviews / "reviews.jsonl", reviews / "catalog-reviews.jsonl")
    result = {"pilot_manifest_sha256": digest((pilot / "manifest.json").read_bytes()),
              "schema_sha256": digest(schema_path.read_bytes()), "checks_passed": ["bundle_checksums", "ossie_json_schema", "metadata_rederived_exactly", "dependency_references", "unique_ids", "input_whitelist", "group_and_duplicate_split_isolation"],
              "episodes": len(episodes), "catalogs": manifest["catalog_count"], "metadata_units": len(units),
              "tables": sum(u["kind"] == "table" for u in units), "connected_groups": len(groups),
              "splits": dict(Counter(e["pilot_split"] for e in episodes)), "review": review}
    output.mkdir(parents=True, exist_ok=True)
    (output / "pilot-audit.json").write_text(json.dumps(result, indent=2))
    return result


def worker(run_id: str) -> dict:
    global ROOT
    ROOT = Path.cwd()
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT))
    from amp.environment import isolated_environment
    output = Path("/home/cdsw/semantic-runs") / run_id
    audit = verify(output)
    # Add missing packages to this run only. Preserve existing training environments.
    dependencies = output / "dependencies"
    pins = {"sentence-transformers": "5.2.3", "scikit-learn": "1.6.1", "scipy": "1.15.3", "joblib": "1.5.1", "threadpoolctl": "3.6.0"}
    missing = []
    for package, version in pins.items():
        try:
            importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            missing.append(f"{package}=={version}")
    env = isolated_environment(ROOT, sys.executable)
    if missing:
        subprocess.run([sys.executable, "-m", "pip", "install", "--no-deps", "--target", str(dependencies), *missing], env=env, check=True, timeout=240)
    config = json.loads((ROOT / "configs/semantic_retrieval/embedding-pilot.json").read_text())
    config["device"] = "cuda"
    config_path = output / "embedding-config.json"
    config_path.write_text(json.dumps(config, indent=2))
    env["PYTHONPATH"] = os.pathsep.join([str(dependencies), env["PYTHONPATH"]])
    env["OMP_NUM_THREADS"] = "4"
    env["HF_HUB_DOWNLOAD_TIMEOUT"] = "60"
    subprocess.run([sys.executable, str(ROOT / "scripts/evaluate_semantic_baselines.py"), "--pilot", str(ROOT / "data/semantic-research/pilot-20261010-v3"), "--config", str(config_path), "--output", str(output / "baselines")], env=env, check=True, timeout=600)
    baseline = json.loads((output / "baselines/manifest.json").read_text())
    import torch
    return {"run_id": run_id, "output": str(output), "node_id": __import__("ray").get_runtime_context().get_node_id(),
            "gpu": torch.cuda.get_device_name(), "audit": audit,
            "baseline": {k: v for k, v in baseline.items() if k != "files"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    import ray
    ray.init(address="auto")
    task = ray.remote(num_cpus=4, num_gpus=1, max_retries=0)(worker)
    result = ray.get(task.remote(args.run_id), timeout=1000)
    print("SEMANTIC_CLUSTER_RESULT=" + json.dumps(result), flush=True)
    ray.shutdown()


if __name__ == "__main__":
    main()
