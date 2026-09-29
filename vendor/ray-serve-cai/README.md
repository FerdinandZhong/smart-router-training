# Included Ray cluster implementation

The required `ray_serve_cai/` and `cai_integration/` source files are included at
the project root to preserve upstream imports and launcher-template paths.
`SNAPSHOT.json` identifies the exact source commit and original file hashes.
Local modifications have separate hashes and reasons. AMP validation verifies
the effective hashes before provisioning resources.

To update: inspect a chosen upstream commit, review changes to cluster launch,
management and templates, copy the selected files, reapply the documented AMP
adaptation, update the manifest and run the AMP tests plus a remote smoke.
Do not fetch a moving branch during AMP installation.

The sibling's package metadata declares Apache-2.0; that checkout did not contain
a standalone LICENSE file. Source headers have been preserved. The recorded
metadata does not override terms attached to third-party code or pilot data.
