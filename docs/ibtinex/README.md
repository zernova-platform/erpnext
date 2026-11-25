# IBTINEX ERP: source, starter company and verified review image

Review date: **25 November 2026**.

**Status: the source-built review image passed real installation/runtime qualification and was published to private GHCR.** It retains the native ERPNext interface/workflows, replaces the main icon/favicon using the existing IBTINEX Studio mark, and offers an explicitly selected synthetic Ethiopian starter company. Customer rollout remains unqualified.

The candidate uses **ERPNext 16.60.0 / Frappe 16.60.2**, matching the versions previously observed in the evaluation system. An upstream version upgrade is a separate qualification step.

## Exact image and download

| Item | Value |
|---|---|
| Image source commit | [`28e3808696bf415a3f6a5b66b017870ed794f5a1`](https://github.com/zernova-platform/erpnext/commit/28e3808696bf415a3f6a5b66b017870ed794f5a1) |
| Candidate tag | `ghcr.io/zernova-platform/ibtinex-erpnext:0.1.0-rc.1-g28e3808696bf` |
| Immutable image | `ghcr.io/zernova-platform/ibtinex-erpnext@sha256:b825833c5f1a11546a09793aa7346776fa366e2f0d3d9d2a5ce4888fbd73cea9` |
| Successful source workflow | [Run 45689963522](https://github.com/zernova-platform/erpnext/actions/runs/45689963522) |
| Installer and complete evidence | [Artifact 15057833877](https://github.com/zernova-platform/erpnext/actions/runs/45689963522/artifacts/15057833877) |

The artifact contains `ibtinex-erp-review-installer.zip`, its release manifest with exact app/database/Redis image references, corresponding-source archives, package inventories and runtime reports. Artifact/installer hashes are in [VALIDATION.md](VALIDATION.md). GitHub artifact retention ends on **25 December 2026**; preserve the release files.

The image's source commit above is fixed. Later documentation-only commits record evidence and do not rebuild or replace it. Install using the manifest/digest rather than a moving branch HEAD.

## Install and explore

- [Portable Python/Compose installation instructions](../../deploy/ibtinex/README.md)
- [Starter company walkthrough](STARTER_WALKTHROUGH.md)
- [Observed validation, limits, failures/corrections and rollback](VALIDATION.md)
- [Icon provenance](BRANDING_ASSET_SOURCE.md)
- [Complete DocType source inventory](../../erpnext/ibtinex_starter/doctype_inventory.json)

Authenticate Docker to the private package and follow the bundled-manifest instructions. The default review installation uses its own project and loopback port **8081**. `--starter-data` explicitly selects the samples; omitting it creates a fresh business site without the sample company. Generated passwords stay in local secret files, outside the image/installer archive.

Normal startup recognizes a completed starter without reseeding or resetting review activity. An occupied site without a compatible marker is rejected. Create another isolated project for a pristine walkthrough. The [rollback instructions](VALIDATION.md#concrete-rollback-and-recovery) cover stopping/removing the review containers, retained data, pristine recreation and future upgrade limits.

## What the actual source-built run proved

All **43 focused checks** passed: 18 deployment/build/Desk, 12 branding and 13 starter contract/schema checks. Real blank/seeded sites and native ERP controllers/reports were then exercised before the same tested image was published.

| Result | Observed value |
|---|---|
| Starter company | `IBTINEX Starter Ethiopia`, seed `1.0.0` |
| Tracked scenario records / modules | **100 / 21** |
| General Ledger | **17 GL entries**, zero imbalance; native report **20 rows**, bank **433,280 ETB** |
| Stock Balance | Native report **4 rows**, inventory **72,000 ETB** |
| Manufacturing / fixed assets | Produced **10**; asset register/opening GL **12,000 ETB** |
| Sales / purchase invoices | Both outstanding balances **0** |
| Running services | Worker job, HTTP login/API, anonymous-access denial, served artwork, native Desk setup completion and realtime passed |
| Persistence / repeat operation | Seed guards/idempotence, container recreation and normal restart after a real stock/configuration edit passed |

The [diagnostic workflow](https://github.com/zernova-platform/erpnext/actions/runs/45689963543) independently passed using an official runtime plus the exact ERP source overlay, with publication disabled. The separate full source-built workflow is the published candidate's qualification authority.

## Honest coverage

Every one of the pinned ERPNext source's **534 DocType schemas** has a recorded disposition: **69 created, 60 generated child, 21 generated native, 13 default fixture, 27 native default configuration, 9 inert external, and 335 not seeded**. This includes child tables and technical/settings types; it does not claim 534 populated business features or every feature variant tested. The 100 tracked scenario documents are not the total database row count.

The starter offers representative connected scenarios across 21 modules. POS cash sessions, serial/batch variants, subcontracting receipt and other gaps remain deliberate review exercises, with per-DocType reasons in the report. HRMS/Payroll, Webshop and other separate apps are outside this image's qualification.

## Practical boundary

Runtime proof is from **Linux amd64 containers on a GitHub-hosted Linux runner**, not an installation on the user's Windows PC or its existing ERP session. Windows requires Docker Desktop Linux-container mode; that machine and arm64 remain untested.

The post-push API check verified package **private visibility**. Complete package grants/inherited permissions were not independently audited, so organization-only pull access is not claimed. Upstream licensing/notices remain in the public source fork; a private image does not remove recipients' applicable source-license rights.

This is a review candidate, not Ethiopian fiscal compliance, customer acceptance, full upstream/security qualification or platform readiness. SSO/VPN/HTTPS, backup/restore and performance remain separate work. The training chart/tax and inert external services are described in the walkthrough and [validation limits](VALIDATION.md#remaining-limits).

## Original source review and plan

1. [Implementation and release plan](PLAN.md): original decisions, change boundaries, milestones and operational gates.
2. [Functional review](FUNCTIONAL_REVIEW.md): all 21 modules, navigation, reports, optional apps and regional gaps.
3. [Security and branding review](SECURITY_AND_BRANDING_REVIEW.md): branding consumers, authentication, APIs, permissions and extension boundaries.
4. [Operations review](OPERATIONS_REVIEW.md): builds, Compose, CI, licensing, upgrades and restore behavior.
5. [Baseline](baseline.json), [module inventory](module_inventory.json) and [source evidence](source_evidence.json): exact revisions, counts and paths.

The original review covered the [fork](https://github.com/zernova-platform/erpnext), the live Installed Applications/Apps/navigation/POS Profile/System Settings surfaces and inventories of pinned ERPNext/Frappe/Docker sources. Upstream ERPNext contained **5,774 tracked files, 21 modules, 534 DocType schemas, 194 report schemas, 15 workspace schemas and 550 Python test files**. The full upstream suite was not run. The earlier live `UNVERSIONED` display established the shown application versions, not the existing image digest/provenance.

Use this index and [VALIDATION.md](VALIDATION.md) for the implemented candidate's observed status; earlier planning documents retain their planning context. Supplied source/artifacts contain no customer data, generated deployment credentials or private signing material.
