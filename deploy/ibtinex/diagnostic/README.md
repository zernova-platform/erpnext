# Optional diagnostic runtime workflow

The diagnostic and full source-build workflows run independently on the same candidate branch/SHA. This optional path shortens native fixture/controller debugging; it cannot publish or qualify a release.

The diagnostic uses the exact official amd64 image `frappe/erpnext@sha256:759726db4c3719d8d89f7a3ecb89540286190d65343f25341c3b6c27201ee229`. Its provenance and SBOM were reviewed for ERPNext 16.60.0, Frappe 16.60.2 and Bench 5.31.1; build-time imports recheck these runtime versions. It overlays the complete exact candidate source archive and current installer/helpers/artwork, retaining unchanged upstream compiled assets. A source-diff guard rejects dependency/frontend changes outside this narrow diagnostic assumption.

It runs the existing full `ci.py` runtime qualification with `IBTINEX_PUBLISH=false`. It has no package-write permission or package token, does not push any image, and labels successful evidence `diagnostic-only-passed`. It produces no release manifest or installer bundle. The independent full source-build workflow remains the only publisher and must pass the same end-to-end tests on its own source-built image before delivery.

The official runtime's Framework version is checked, but its exact Framework Git commit has not been independently verified. Diagnostic metadata calls the desired source pin `expected_frappe_commit` and records `frappe_commit_verified=false`; it does not claim the base's source hash was checked.

No diagnostic Docker success is claimed until a runner result is recorded. Its first execution is pending. Different dependency builds or compiled assets between the official runtime and the source-built image remain possible, which is why its success cannot substitute for final qualification.
