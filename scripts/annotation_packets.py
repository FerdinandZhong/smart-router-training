"""Export blinded request packets and import externally executed agent responses.

Export private manifests separately from public packet files. Agents read only
one .txt packet, never the manifest, credentials, source evidence or run outputs.
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from smart_router.annotation.backends import external_key, request_body
from smart_router.annotation.pipeline import prepare, digest, read_jsonl
from smart_router.schemas import canonical_json, model_input, require


def export(config, output, role, run_directory=None):
    frozen = prepare(config)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    candidates = {}
    if role == "judge":
        require(run_directory is not None, "Judges need --run with completed candidate_results.jsonl")
        candidates = {(r["example_id"], r["candidate"], r["trial"]): r for r in read_jsonl(Path(run_directory) / "candidate_results.jsonl")}
    manifest = []
    for record in frozen["records"]:
        for candidate in frozen["config"]["candidates"]:
            for trial in range(frozen["config"]["trials_per_candidate"]):
                context = {"role": role, "example_id": record["example_id"], "candidate": candidate["id"], "trial": trial}
                if role == "candidate":
                    if candidate["api"] != "external":
                        continue
                    models, payload = [candidate], model_input(record)
                else:
                    result = candidates.get((record["example_id"], candidate["id"], trial))
                    if not result or result["status"] != "ok":
                        continue
                    contract = {k: v for k, v in frozen["contracts"][record["example_id"]].items() if k != "example_id"}
                    payload = {"runtime_input": model_input(record), "success_contract": contract, "candidate_response": result["text"]}
                    models = frozen["config"]["judges"]
                for model in models:
                    require(model["api"] == "external", "Packet export is for external model executions")
                    ctx = {**context, **({"judge": model["id"]} if role == "judge" else {})}
                    system = frozen["prompts"][role]
                    body = request_body(model, system, canonical_json(payload))
                    key = external_key(model, body, ctx)
                    public = output / (key + ".txt")
                    text = system + "\n\n" + canonical_json(payload) + "\n"
                    if public.exists():
                        require(public.read_text() == text, "Refusing to replace changed public packet")
                    else:
                        public.write_text(text)
                    manifest.append({"request_hash": key, "model": model, "context": ctx,
                                     "body": body, "packet": str(public.resolve()), "packet_hash": digest(text)})
    # Shuffle by hash so judge order does not disclose candidate ordering.
    manifest.sort(key=lambda r: r["request_hash"])
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps([{k: r[k] for k in ("request_hash", "context", "packet")} | {"requested_model": r["model"]["model"]} for r in manifest], indent=2))


def import_result(manifest_path, key, response_path, task_name):
    manifest = json.loads(Path(manifest_path).read_text())
    entry = next(r for r in manifest if r["request_hash"] == key)
    message = Path(entry["packet"]).read_text()
    require(digest(message) == entry["packet_hash"], "Public packet changed after export")
    text = Path(response_path).read_text().strip()
    require(bool(text), "Empty external response")
    model = entry["model"]
    receipt = {"request_hash": key, "requested_model": model["model"], "actual_model": None,
               "text": text, "usage": {}, "execution": {
                   "tool": "collaboration.spawn_agent", "task_name": task_name, "model_override": model["model"],
                   "fork_turns": "none", "reasoning_effort": "inherited_session_setting",
                   "model_identity_source": "requested tool override; serving revision not exposed", "usage_available": False,
                   "message": message, "packet_sha256": entry["packet_hash"]}}
    output = Path(model["response_directory"]) / (key + ".json")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        require(json.loads(output.read_text()) == receipt, "Refusing to overwrite a different external receipt")
    else:
        output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"receipt": str(output), "task_name": task_name}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    exp = sub.add_parser("export")
    exp.add_argument("--config", required=True)
    exp.add_argument("--output", required=True)
    exp.add_argument("--role", choices=["candidate", "judge"], required=True)
    exp.add_argument("--run")
    imp = sub.add_parser("import")
    imp.add_argument("--manifest", required=True)
    imp.add_argument("--request-hash", required=True)
    imp.add_argument("--response", required=True)
    imp.add_argument("--task-name", required=True)
    args = parser.parse_args()
    if args.command == "export":
        export(args.config, args.output, args.role, args.run)
    else:
        import_result(args.manifest, args.request_hash, args.response, args.task_name)
