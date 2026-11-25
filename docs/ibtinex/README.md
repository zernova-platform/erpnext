# IBTINEX ERP: ERPNext fork and release plan

Review date: 25 November 2026.

**Status: fork created; source and live UI inspected; implementation and deployment planned.** This branch contains review documents only. It does not contain a branded application, a published image, or a qualified customer release.

The first candidate will use ERPNext 16.60.0 and Frappe 16.60.2, matching the versions observed in the evaluation system. Keep the native ERP experience and make a small, maintained presentation change. A later upstream version upgrade is a separate qualification step.

## Read in this order

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
- ERPNext inventory: **5,774 tracked files, 21 modules, 534 DocType schemas, 194 report schemas, 15 workspace schemas, 550 Python test files**. Schema counts include child tables. Tests present in source were not executed.

This is an architecture, customization and release review. It is not a line-by-line audit, a penetration test, a completed business acceptance run, or proof of deployment readiness. The implementation gates in the plan are outstanding work.

The public fork and these documents contain no credentials, customer data, private network details or signing material. Exact brand artwork must come from the approved IBTINEX asset set during implementation.
