"""Bounded, no-tool CLI smoke request for annotation model access."""
import argparse
import json
from pathlib import Path
import subprocess

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["gpt-5.6-terra", "gpt-5.6-sol", "gpt-6-astra"], required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = root / "runs" / "cli-annotation-preflight" / args.model
    out.mkdir(parents=True, exist_ok=True)
    command = ["codex", "--no-daemon", "exec", "--ignore-user-config", "--ephemeral",
               "--skip-git-repo-check", "--sandbox", "read-only", "--model", args.model,
               "--json", "--output-last-message", str(out / "answer.txt"),
               "Reply exactly OK. Do not use any tools."]
    try:
        result = subprocess.run(command, input="", capture_output=True, text=True, timeout=90, cwd=out)
        (out / "events.jsonl").write_text(result.stdout)
        (out / "stderr.txt").write_text(result.stderr)
        answer = (out / "answer.txt").read_text() if (out / "answer.txt").exists() else None
        print(json.dumps({"exit_code": result.returncode, "answer": answer, "stderr_tail": result.stderr[-1200:]}))
        raise SystemExit(result.returncode)
    except subprocess.TimeoutExpired:
        print(json.dumps({"error": "cli_timeout", "model": args.model}))
        raise SystemExit(1)
