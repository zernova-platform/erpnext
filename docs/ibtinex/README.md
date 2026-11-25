# IBTINEX ERP: source, starter company and review image

Review date: 25 November 2026.

**Status: icon changes, opt-in starter company and container pipeline implemented.**
The first full container build is being qualified. A successful release manifest
and its recorded image digest establish publication; the presence of a recipe
alone does not. Customer rollout remains outside this review release.

The candidate uses ERPNext 16.60.0 and Frappe 16.60.2, matching the versions observed in the evaluation system. It preserves the native interface and replaces the main icon and favicon using the existing IBTINEX Studio mark. A later upstream version upgrade is a separate qualification step.

## Use this edition

- [Container build and portable installer](../../deploy/ibtinex/README.md)
- [Starter company walkthrough](STARTER_WALKTHROUGH.md)
- [Icon provenance and adaptation](BRANDING_ASSET_SOURCE.md)
- [Complete DocType inventory](../../erpnext/ibtinex_starter/doctype_inventory.json)

Starter data is an explicit choice for a fresh review site. The installer also
supports an empty site, preserves unrelated Compose workloads, and refuses to
seed an occupied database without its valid starter marker. The generated
coverage report records the actual disposition of every one of the 534 source
DocTypes; it does not pretend that every feature variant has been exercised.

## Original source review and plan

1. [Implementation and release plan](PLAN.md): decisions, precise change boundaries, milestones, tests, deployment and rollback.
2. [Functional review](FUNCTIONAL_REVIEW.md): all 21 ERPNext modules, navigation, reports, optional apps and regional gaps.
3. [Security and branding review](SECURITY_AND_BRANDING_REVIEW.md): actual branding consumers, authentication, APIs, permissions and extension boundaries.
4. [Operations review](OPERATIONS_REVIEW.md): image builds, Compose, CI, licensing, upgrades and restore behavior.
5. [Baseline](baseline.json), [module inventory](module_inventory.json), and [source evidence](source_evidence.json): exact revisions, counts and source paths.

## What was verified

- GitHub fork: [zernova-platform/erpnext](https://github.com/zernova-platform/erpnext), forked from `frappe/erpnext`, with upstream branches and tags.
- Live Installed Applications screen: ERPNext **16.60.0**, Frappe **16.60.2**. Both displayed `UNVERSIONED` in the Git branch column. This proves the displayed versions, not the running image digest or source provenance.
- Live Apps, ERP navigation, POS Profile, Installed Applications and System Settings surfaces inspected without saving configuration or business documents.
- Complete tracked-file inventories for the pinned ERPNext, Frappe and Docker source snapshots; representative deeper source inspection across the application and runtime layers.
- Original upstream ERPNext inventory: **5,774 tracked files, 21 modules, 534 DocType schemas, 194 report schemas, 15 workspace schemas, 550 Python test files**. Schema counts include child tables. The complete upstream suite has not been executed by this project.
- Implementation checks: 12 focused branding tests, 9 deployment tests and 9 starter contract/schema tests passed locally before the first container build. These do not substitute for the pipeline's real installation and runtime checks.

The original review is a structural source and architecture review. Follow the
release manifest and observed validation record for the subsequent implementation
and runtime results. Customer acceptance, a full security review and wider
platform integration are separate from this small review edition.

The public fork and reports contain no credentials, customer data or signing
material. The icon source and its exact adaptation are recorded in the linked
provenance document.
