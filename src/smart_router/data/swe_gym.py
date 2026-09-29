"""Extract pre-call states from recorded SWE-Gym training trajectories."""

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from smart_router.data.prepare import assign_splits, digest, write_bundle
from smart_router.schemas import canonical_json, model_input, require

DATASET = "SWE-Gym/OpenHands-Sampled-Trajectories"
REVISION = "baf3a4e4bff514d48ddc08a93a2ade5c126212c7"
SHARD_SHA256 = "29d038b0c34eb0e50a19730f3cf3daa5a156c2d7e9c871c01b568acbab6aae07"
RESPONSE_FORMAT = {
    "type": "single_tool_json",
    "instructions": "Return exactly one JSON object with keys tool and arguments. tool must name an available function; arguments must satisfy that function's schema. Propose the next action only. Do not execute it, invent its result, or include markdown fences.",
}


def clean_null_fields(value):
    """Remove Arrow's nullable union padding, without altering any text."""
    if isinstance(value, dict):
        return {k: clean_null_fields(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [clean_null_fields(v) for v in value]
    return value


def source_states(row, row_index, max_characters=36000):
    messages, tools = row["messages"], clean_null_fields(row["tools"])
    for tool in tools:
        tool["function"].setdefault("parameters", {"type": "object", "properties": {}, "additionalProperties": False})
    states = []
    assistant_index = -1
    for index, message in enumerate(messages):
        if message["role"] != "assistant":
            continue
        assistant_index += 1
        # Observed tool feedback is essential in this first step-level pilot.
        if index < 2 or messages[index - 1]["role"] != "tool" or not message.get("tool_calls"):
            continue
        if not any(m["role"] == "tool" and len(m.get("content") or "") >= 500 for m in messages[:index]):
            continue  # Exclude empty-workspace/navigation-only prefixes using past evidence only.
        state = {"messages": clean_null_fields(messages[:index]), "tools": tools,
                 "response_format": RESPONSE_FORMAT}
        inputs = {"state": state}
        if len(canonical_json(inputs)) > max_characters:
            continue  # Exclude, never silently truncate evidence.
        episode = row["instance_id"] + ":" + row["run_id"]
        states.append({
            "schema_version": "1.0", "customer_id": "public_research", "dataset_id": "swe_gym_pilot_v2",
            "task_id": "agent_local_tool_sufficiency", "task_schema_version": "1.0",
            "example_id": digest([episode, index])[:20], "group_id": row["instance_id"],
            "input": inputs, "targets": {"encoding": "unlabeled", "values": dict.fromkeys(["FAST", "GENERAL", "REASONING"])},
            "metadata": {"synthetic": False, "source_kind": "recorded_model_rollout_on_real_github_task",
                         "episode_id": episode, "step_id": f"assistant-{assistant_index}", "step_index": assistant_index,
                         "source_row": row_index, "source_message_index": index, "source_revision": REVISION,
                         "source_dataset": DATASET, "source_split": "train.raw", "source_repo": row["instance_id"].rsplit("-", 1)[0],
                         "runtime_replayed": False, "eligible_for_training": False},
            "label_evidence": {"source_trace": {"resolved": row.get("resolved"), "recorded_next_message": clean_null_fields(message),
                                                "note": "Historical evidence only; not a counterfactual success label or judge reference."}},
            "provenance": {"label_source": "unlabeled_recorded_trajectory", "source_row": row_index,
                           "input_hash": digest(inputs), "leakage_hash": digest(inputs)}, "split": None,
        })
    return states


def construct(source_path, output, episodes=100, seed=42):
    import pyarrow.parquet as pq
    source_path, output = Path(source_path), Path(output)
    checksum = hashlib.sha256(source_path.read_bytes()).hexdigest()
    require(checksum == SHARD_SHA256, "Source checksum does not match the pinned SWE-Gym shard/revision")
    rows = pq.read_table(source_path).to_pylist()
    by_repo = defaultdict(list)
    # Ordering depends only on identity/seed, never the original success outcome.
    for row_index in sorted(range(len(rows)), key=lambda i: digest([seed, rows[i]["instance_id"], rows[i]["run_id"]])):
        row = rows[row_index]
        states = source_states(row, row_index)
        if len(states) >= 3:
            by_repo[row["instance_id"].rsplit("-", 1)[0]].append(states)
    selected, issues = [], set()
    repo_names = sorted(by_repo)
    while len(issues) < episodes:
        progress = False
        for repo in repo_names:
            while by_repo[repo] and by_repo[repo][0][0]["group_id"] in issues:
                by_repo[repo].pop(0)
            if not by_repo[repo]:
                continue
            states = by_repo[repo].pop(0)
            issues.add(states[0]["group_id"])
            for position in (0, len(states) // 2, len(states) - 1):
                selected.append(states[position])
            progress = True
            if len(issues) == episodes:
                break
        require(progress or len(issues) == episodes, "Insufficient eligible independent issues")
    settings = {"strategy": "grouped", "seed": seed, "train": 0.7, "validation": 0.1, "calibration": 0.1, "test": 0.1}
    selected = assign_splits(selected, settings)
    task = {"task_id": "agent_local_tool_sufficiency", "schema_version": "1.0", "kind": "independent_binary", "unit": "agent_step",
            "classes": [{"id": c, "description": f"The configured {c} candidate proposes a schema-valid, evidence-supported next tool action."} for c in ["FAST", "GENERAL", "REASONING"]]}
    config = {"customer_id": "public_research", "task": task,
              "dataset": {"dataset_id": "swe_gym_pilot_v2", "split": settings}, "annotation": {"mode": "queue_missing"}}
    source = {"dataset": DATASET, "revision": REVISION, "official_split": "train.raw", "shard": source_path.name,
              "sha256": checksum, "rows_scanned": len(rows), "selection": "Seeded identity order; round-robin repositories; one run per issue; three spread-out eligible steps per episode; full prefixes <=36000 JSON characters; at least one prior tool observation >=500 characters (heuristic, not execution verification)",
              "license": "Dataset card does not declare a license; upstream code is Apache-2.0, which is not asserted to license all dataset contents.",
              "release_gate": "Local annotation research only; clarify dataset/source-code terms before training release or redistribution."}
    write_bundle(config, selected, source, output)
    # Annotation debugging: ten distinct episodes, 7/1/1/1 split coverage, diverse repositories.
    pilot, used_issues, used_repos = [], set(), set()
    for split, count in (("train", 7), ("validation", 1), ("calibration", 1), ("test", 1)):
        pool = sorted([r for r in selected if r["split"] == split], key=lambda r: digest([seed, "annotation10", r["example_id"]]))
        for _ in range(count):
            eligible = [r for r in pool if r["group_id"] not in used_issues]
            require(bool(eligible), "Insufficient distinct issues for the ten-state pilot")
            record = next((r for r in eligible if r["metadata"]["source_repo"] not in used_repos), eligible[0])
            pilot.append(record)
            used_issues.add(record["group_id"])
            used_repos.add(record["metadata"]["source_repo"])
    contracts = [{"example_id": r["example_id"], "version": "swe-gym-local-v1", "required_conditions": [
        "Return exactly one JSON object containing tool and arguments. The tool must be present in runtime tools, and its arguments must satisfy the supplied schema.",
        "Choose a useful next step for the user's issue, grounded in the complete supplied prefix. Respect explicit task constraints and recorded tool errors; do not blindly repeat a failed action without a supported change.",
        "Do not invent file contents, tool results, successful tests or task completion. If calling finish, the prefix must support completion or a concrete inability to proceed.",
        "Judge the proposed next action only, not whether an unexecuted command, patch, test, or whole episode will succeed. Abstain when semantic evidence is insufficient."
    ]} for r in pilot]
    def save_lines(name, values):
        (output / name).write_text("".join(canonical_json(v) + "\n" for v in values))
    save_lines("pilot10.jsonl", pilot)
    save_lines("pilot10-contracts.jsonl", contracts)
    audit = {"states": len(selected), "episodes": len(issues), "repositories": dict(Counter(r["metadata"]["source_repo"] for r in selected)),
             "pilot_states": len(pilot), "pilot_repositories": len(used_repos), "pilot_splits": dict(Counter(r["split"] for r in pilot)),
             "pilot_input_characters": [len(canonical_json(model_input(r))) for r in pilot], "source": source}
    (output / "source-audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    # Extend manifest hashes for the frozen subset and contracts.
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for name in ("pilot10.jsonl", "pilot10-contracts.jsonl", "source-audit.json"):
        manifest["files_sha256"][name] = hashlib.sha256((output / name).read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return audit
