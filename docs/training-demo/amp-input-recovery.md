# Browser AMP input recovery

The observed browser import stored event-shaped objects for three edited subdomain inputs.
Project Settings > Environment Variables preserved the same inputs as strings.
This is deployment evidence of an import serialization problem, not proof of a specific frontend source defect.

Setup now detects this event shape and directs the operator to repair the existing project's variables.
It validates stored subdomains as DNS labels, then refreshes these three process variables from the project API.
This avoids stale inherited values after repair. It never recovers values from null event fields or substitutes defaults.
The API preflight remains GET-only. Other process variables, including credentials, are not refreshed.

For the existing deployment:

1. Update the checkout to the patched training-demo revision.
2. Retain the corrected strings in Project Settings > Environment Variables.
3. Start a new execution of the failed environment setup job.

For a new import, the API importer bypasses the affected browser form:

```bash
python -m cai_integration.create_amp --name training-demo \
  --runtime <runtime-id> --git-ref training-demo --env-file <string-inputs.json>
```

This command validates inputs without creating a project. Supply --host, --token-file and --apply for an intentional new import.
The default Git URL now targets smart-router-training, not the vendored ray-serve-cai repository.
Do not use --apply to repair an existing project: it creates a new project and runs import steps.
The browser frontend itself is outside this repository and is not patched by this change.

Verification: test_amp_project_inputs.py covers string preservation, event rejection, DNS validation, process refresh,
no mutation after invalid input, GET-only retrieval and safe-import payload construction. Live CAI rerun remains pending.
