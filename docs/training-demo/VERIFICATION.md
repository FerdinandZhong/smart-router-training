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
