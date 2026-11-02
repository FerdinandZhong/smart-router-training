# Local verification — 30 October 2026

- Five reward contract tests passed: numeric equivalence, invalid final answers, wrong answers, chat completion format and length mismatch.
- All four dataset subsets have the planned counts and mutually disjoint normalized-question IDs.
- Every recorded output checksum matches the downloaded preparation artifacts.
- Chromium passed at 1440, 980 and 390 pixel widths, with no JavaScript errors or horizontal overflow.
- Refresh works and unavailable GPU metrics remain blank.
- The desktop screenshot was visually inspected. Mobile overflow checks passed; detailed mobile visual acceptance remains pending.
- The monitor runs on local loopback port 8096. It is not deployed to Ray Serve.
- No GPU training, cluster networking, model loading, adapter reload or model-quality measurement was performed.

Re-run browser checks while the preview runs: `python tests/browser_training_demo.py`.

## Independent-job UI — 1 November 2026

Chromium passed the redesigned form and history checks at 1440, 980 and 390 pixels.
Checks cover SFT/GRPO fields, LoRA/full visibility, draft save/reload, method filtering, duplication and configuration download.
Launch remains disabled. No JavaScript errors or horizontal page overflow occurred.
These checks cover browser-local drafts, not backend job history or training.

## Mistral Small demo UI polish — 1 November 2026

Chromium passed the extended checks at 1440, 980 and 390 pixels: demo presets, 4-bit toggle visibility, memory estimate, GPU-budget and weight-memory warnings, plus the earlier form, draft and export checks. Reward unit tests (5) passed.
The weight-memory figure is a bytes-per-parameter rule of thumb, not a measurement. The preset model repository id is unconfirmed.
These are local browser checks only. No GPU, Ray, model loading or training was run.

## Training dashboard backend and AMP flow — 1 November 2026 (LOCAL CPU evidence only)

Unit suite `PYTHONPATH=src:. python3 -m unittest discover -s tests -p 'test_*.py'`: 168 tests passed, including `tests/test_training_dashboard.py` (fake Ray client: submit, duplicate ID, SFT/GRPO 409, smoke gate, path rejection, missing key, stop, content-type/same-origin rejection, readiness alive/timeout logic, GPU worker group values, manifest order).
`tests/browser_training_demo.py` passed in Chromium against `monitor.py --port 8097` with no credentials (cluster Not connected, smoke and launch disabled), then against stubbed `/api/cluster` and `/api/jobs` responses (connected state, server job details and logs), at 1440, 980 and 390 pixels with no overflow.
No live CAI import, Ray cluster, GPU, NCCL or training was run. Whether CAI applications receive a usable API key is unverified; without one the dashboard reports 503 and Not connected.

## Review fixes — 2 November 2026

Local CPU evidence only. All 172 unit tests and the Chromium browser test passed after these fixes:
- A smoke `output_dir` that resolves outside the project is rejected before submission.
- Dashboard smoke submissions run under `timeout --kill-after=60 <job_timeout_seconds>`. Untested against live Ray; requires coreutils `timeout` in the head runtime.
- The smoke gate parses `SUCCESS.json` and requires initial worker identities on distinct, currently alive GPU Ray nodes.
- Submission failures return only the exception type; a credential sentinel in the exception text is absent from the response and events.
- A failed job list keeps the last good counts labelled stale, or shows `—` and "Job list unavailable" if none loaded.
