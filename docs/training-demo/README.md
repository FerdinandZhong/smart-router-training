# Training workspace

Read [the current independent-job plan](PLAN.md) and [verification evidence](VERIFICATION.md).

Run the local preview:

```bash
python amp/training_demo/monitor.py --port 8096
```

Open http://127.0.0.1:8096. Create local drafts, inspect their details, and download configurations.
Without CAI credentials and `ray_cluster_info.json` the cluster shows Not connected and Launch is disabled.
In the AMP the same server runs as the authenticated training dashboard application and submits Ray Jobs.
The UI supports independent jobs and has no mandatory model or training sequence.

The [30 October proposal](INITIAL-DEMO-20261030.md) is historical.
