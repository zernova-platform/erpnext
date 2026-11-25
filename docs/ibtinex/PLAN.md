# IBTINEX ERP: minimal rebranding and deployment plan

## 1. Decision and deliverable

Build **IBTINEX ERP** as a lightly branded ERPNext distribution. Preserve the native Desk, modules, forms, business rules, permissions, reports, APIs and upgrade mechanisms. Use a small presentation patch in the ERPNext fork and a companion Frappe application for brand assets, settings and styling.

The fork exists at [zernova-platform/erpnext](https://github.com/zernova-platform/erpnext). This planning branch starts at upstream ERPNext `v16.60.0`. Its application source is unchanged. Frappe and Frappe Docker were cloned and inspected as pinned dependencies; no additional remote fork was created for them.

The first proposed distribution version is `0.1.0-rc.1`, clearly distinguished from underlying ERPNext/Frappe versions. It is a future review candidate, not a release created by this task. Use a distinct image/package name such as `ghcr.io/zernova-platform/ibtinex-erpnext`; do not overwrite an existing Odoo product image or use its installer/license protocol.

## 2. Freeze the baseline before implementation

| Component | Version or source snapshot | Commit |
|---|---|---|
| ERPNext | 16.60.0 | `886ab6ae187244e7f1b852393384ab6019d56264` |
| Frappe Framework | 16.60.2 | `2df0425571ebbaed878eabc3edc5b7e7c3327ae0` |
| Frappe Docker reference | Reviewed snapshot | `cf568a829790ef658d232daa75457dadf4e1ecc9` |

The live evaluation UI confirms the application version pair. Capture the actual running image digest, architecture, Compose project, site name and installed app list through the authorized host connection before implementation. A matching version label is not proof of an identical build. The Docker reference snapshot is a reviewed build input, not a claim about the clone currently on that host.

The source manifests require Python 3.14 for Frappe (`>=3.14,<3.15`), Node `>=24`, and ERPNext's Frappe constraint `>=16.60.0,<17.0.0`. Qualify and pin exact patches and base-image digests. Do not reuse a v15 runtime recipe. See [source evidence](source_evidence.json) and [operations review](OPERATIONS_REVIEW.md).

Upstream 16.61 releases were observed during the review. Treat that upgrade as a separate tested change. Baseline matching is not a reason to ship a known vulnerable version: assess current security advisories before each release and qualify any required update first.

## 3. Exact branding boundary

| Surface | First implementation | Boundary |
|---|---|---|
| Product title and ERP app tile | Change display metadata in `erpnext/hooks.py`: `app_title`, `app_logo_url`, and the ERP-owned app-screen logo. | Keep `app_name = "erpnext"`, route, setup and permission callbacks. |
| Product artwork | Add approved original IBTINEX logo, favicon and splash assets at versioned paths. | Do not recolor or repurpose upstream trademark artwork as our logo. |
| Login, site title and portal | Set Website Settings and bounded template/context hooks through the companion app. | Preserve login, redirect and portal authorization behavior. |
| Navbar and light/dark appearance | Navbar Settings plus a small namespaced style bundle using the existing UI tokens. | Keep native layout, navigation, controls, spacing conventions and accessible contrast. |
| Help, support and About | Add our support entry and distribution version while retaining upstream product versions, licenses and source attribution. | Keep useful upstream documentation links; do not replace them with nonexistent IBTINEX pages. |
| Emails | Supply versioned welcome/reset templates and an approved software footer. | Preserve recipient logic, customer sender identity and authentication links. |
| PDF and document printing | Test font/layout compatibility and optional product footer. | Customer company name, logo, tax information and letterhead remain customer-owned. |
| Legacy desktop icon | Review the exported `Desktop Icon` record and its consumers; change label/logo only if the selected UI needs it. | Preserve the record name `ERPNext`, `app`, and parent-icon relationships. |
| Setup and navigation text | Change only clearly brand-bearing presentation labels. | Preserve schema names, IDs, package imports, API names and document routes. |

The app tile cannot be fully rebranded by adding a second app-screen entry. In this baseline, `frappe.apps.get_apps`, `frappe.boot.get_app_data`, and version metadata read hooks specifically for `app_name="erpnext"`. A companion app's title does not replace that entry. A narrow ERP-owned metadata patch avoids duplicate tiles and a framework-wide override. [Source analysis](SECURITY_AND_BRANDING_REVIEW.md)

Proposed companion app: `ibtinex_branding`, maintained in a separate repository under the existing organization. Its deliverables are approved assets, `hooks.py`, scoped CSS, bounded templates, install/migrate logic, tests and product version metadata. It has no independent app-screen tile and no replacement ERP API or UI. A Frappe-core fork is not justified for the first branding scope.

Keep this ownership contract in the installer: on a fresh site, initialize only approved fields; record prior values and the values this app owns; on update, change an owned field only if it still equals the previous managed value. Report customer edits as drift instead of overwriting them. Never blanket-export credentials or entire live settings records as fixtures. Use framework document APIs and run normal validation/cache clearing.

`System Settings.app_name` is present but hidden in this version. Use the actual visible Website Settings controls and the inspected consumers; do not document an imaginary visible System Settings field. Full settings and consumer paths are in the review documents.

## 4. Functional scope and coverage

Retain all native modules in the selected ERPNext release. Customer blueprints choose navigation visibility and enabled workflows; visibility alone never grants or removes authorization. The [functional review](FUNCTIONAL_REVIEW.md) covers all 21 modules: Accounts, CRM, Buying, Projects, Selling, Setup, Manufacturing, Stock, Support, Utilities, Assets, Portal, Maintenance, Regional, ERPNext Integrations, Quality Management, Communication, Telephony, Bulk Transaction, Subcontracting and EDI.

This baseline includes Dock, Workspace Sidebar, Desktop Icon and Report Center configuration as well as traditional Workspaces. The first release preserves those navigation structures. Banking and the embedded frontend islands remain their upstream applications; build and smoke-test them with the rest of the ERP assets. Banking's page title already reads Website Settings, so inspect that behavior before adding CSS or code patches.

Frappe's framework inventory covers 17 modules and its shared UI, Studio and Flow source trees. Studio's reviewed README marks it as early development, and Flow describes a separately managed agent harness. Their presence in the source or navigation does not establish an operational AI or visual-builder service. Retain the upstream source, keep access/configuration deliberate, and qualify those capabilities separately if selected. The first branding release does not require a new Studio application or AI provider.

Keep optional products explicit. HR/payroll (`frappe/hrms`), Frappe CRM, Webshop and Helpdesk are separate apps; ERPNext's Employee master, native CRM and Support are not evidence those apps are installed. Add one only after compatibility, licensing and deployment qualification.

Ethiopia is a deployment/localization qualification stream. The source includes an Ethiopia chart in `chart_of_accounts/unverified/` and setup tax defaults, but no dedicated Ethiopia regional implementation was found. A complete Amharic UI was not found in the reviewed ERPNext locale files. Validate customer accounting requirements, chart mapping, taxes/reporting, invoice content/numbering, payment/fiscal integrations and fonts before a customer release. Keep this work versioned separately from cosmetic branding. Source observations are not tax-law conclusions.

## 5. Keycloak and integration configuration

Frappe 16.60.2 contains a native Keycloak Social Login Key provider and callback. Reuse that supported integration first. Configure the exact public HTTPS origin, issuer/realm, callback, client credentials and controlled user provisioning through the installation profile. Keep secrets outside source, logs and reports. Verify trusted identity claims and explicit user-role assignment; authentication is not ERP authorization.

The first branding implementation must not quietly change authentication. The enterprise profile separately validates Keycloak login, logout, session expiration, disabled accounts, MFA at the issuer, existing-user linking and denied signup. Define what happens to already-active ERP sessions when an identity is disabled; do not claim immediate revocation without a test.

The baseline's `disable_user_pass_login` blocks password authentication before selecting a user. It cannot implement “SSO for staff, local Administrator recovery” by itself. Engineer and test a server-enforced policy for ordinary users and a restricted, auditable administrator recovery route before enabling mandatory SSO. Hiding a form, a query parameter or a navbar button is not enforcement. The exact design remains an implementation gate. [Security review](SECURITY_AND_BRANDING_REVIEW.md)

Keep native REST APIs, whitelisted methods and webhook facilities. Integration identities receive only their required roles and company/record access. Browser SSO does not automatically make a Keycloak bearer token valid for Frappe REST APIs. Use a separately qualified native API authentication flow. Test direct API/report/file access as well as the UI, and preserve customer/supplier portal scoping.

## 6. Source and release ownership

- Keep upstream branches/tags intact. Work on an IBTINEX release branch based on the verified stable tag, with small reviewed changes and a recorded upstream base.
- Preserve the `erpnext` package and upstream version identity. Record the distribution version and the exact fork/framework/branding/build commits separately.
- Maintain one authoritative build and promotion pipeline. The platform's established Jenkins pipeline is the planned owner; integrate with the actual existing pipeline when implementation begins. Do not introduce a second competing image publisher in Actions.
- The fork inherits upstream CI files, but they are not immediately reusable: the inspected server-test workflow refers to Frappe-specific runner labels such as `erpnext-arc-setup` and an upstream CI image. Port only the required test/build steps onto qualified organization runners.
- Do not enable inherited release workflows before reviewing publishing destinations, credentials and triggers. No workflow, secret or publish permission was enabled in this review.

## 7. Build one qualified image

Use the pinned Frappe Docker custom-image approach. Bake the ERPNext fork and `ibtinex_branding` into the image before deployment; install them onto the selected site as a separate, scoped site operation. Do not install new application code into running production containers.

The reviewed Containerfile consumes `apps.json` as a BuildKit secret. Keep checkout credentials out of build arguments, logs and final layers. Derive a cache key from the resolved source/dependency manifest because secret-file changes alone do not invalidate build cache. Use tags verified against expected commits, or implement and test explicit commit checkout; a raw SHA cannot simply be assumed valid for every `--branch` consumer. Verify the commits before `.git` metadata is removed by the builder.

Pin and record Python/Node patches, base images, MariaDB/Redis versions and digests, build tools and resolved dependencies. The upstream recipe has floating dependencies, so commit pinning alone does not prove byte-for-byte reproducibility. The deliverable is a qualified immutable image with honest provenance; deterministic rebuild claims require a separate demonstrated check.

Publish the tested candidate once to the selected GHCR package. Promote that digest across environments. The image is shared across frontend, backend, websocket, short/long workers, scheduler and setup/migration jobs; every application role must use the same digest. Use explicit full digest references in the product Compose override.

Release artifacts: image digest/signature, source and dependency manifest, SBOM, vulnerability review, corresponding source/build material, changes, test evidence and restore instructions. Registry signing keys and publisher credentials remain in the controlled release system. Installation needs only an appropriately scoped pull identity and public verification material.

## 8. Isolated review deployment and ZEDAS integration

First deploy beside the existing evaluation system with a new Compose project, dedicated database/sites volumes and a discovered available loopback port. Proposed project identifier: `ibtinex-erp-review`; the installer must still verify ownership/name collisions before use. The deployment plan must show actual host, digest, architecture, volumes, networks, subnet/route conflicts, published ports and proxy routes.

Windows review uses the already working Linux-container environment. Customer hosting targets a qualified Linux Docker Engine host, or a Linux VM when the customer host is Windows Server. Do not design a native Windows ERPNext container. Docker Desktop is not supported on Windows Server. [Docker documentation](https://docs.docker.com/desktop/setup/install/windows-install/)

Create a product-specific ERPNext recipe in the existing deployment studio. Reuse its connection, inventory, credentials, confirmation, progress, report and rollback mechanisms after inspecting the current source. Identify this recipe separately from Odoo. Its required services are the ERP roles, MariaDB and Redis; attach existing approved identity/proxy services where the selected enterprise profile requires them. Optional HR, storefront, iPaaS and other products remain explicit selections.

Fresh site creation offers a clear sample-data choice. Synthetic review data is a versioned, rerunnable fixture set with stable identifiers; it is not silently inserted into a real customer site. Require an empty/eligible target before seeding. Inspect application state after every stage and report the actual accepted app versions/site, not only the exit code of a shell command.

Reuse the existing TLS/Let's Encrypt proxy recipe for customer FQDNs. Local loopback review can use a local review route. Do not obtain a public certificate for `localhost`, start a competing listener on ports 80/443, or copy the upstream Traefik Docker-socket mount without a separate design decision. Validate forwarded headers, host routing, WebSockets, attachments, PDF responses and callback URLs through the actual proxy.

## 9. Required acceptance evidence

These are planned tests, not observed passes. Store outcomes against the exact image digest and source revisions, with synthetic data and no credentials or private license material in exported evidence.

| Test group | Required proof |
|---|---|
| Build/install | Fresh site installs the exact app set; repeat provisioning is safe; recreation preserves behavior; no missing assets. |
| Branding | Login, reset, apps screen, dock, forms, dialogs, Banking, POS, portal, emails and PDFs; light/dark and a narrow viewport; one ERP tile; readable approved assets and accurate attribution. |
| Sales/accounts | Quotation through order/delivery/invoice/payment; expected stock, GL and receivable balances; return/cancellation; rounding and multi-currency when selected. |
| Buying/stock | Purchase order/receipt/invoice/payment; transfer and reconciliation; valuation; serial/batch and warehouse restrictions. |
| Selected modules | Manufacturing BOM/work order/consumption/completion; asset depreciation; project/timesheet billing; native support workflow where enabled. |
| Permissions | Staff roles, auditor, approver, restricted-company users and portal customers; direct route, REST, report export and private-file denials. |
| IAM | Keycloak success/failure, MFA, logout, disabled user, controlled linking/signup and tested administrator recovery. |
| Runtime | Queue and scheduler work, WebSocket delivery, mail sandbox, fonts/PDF, uploads, restart, volume permissions and disk checks. |
| Upgrade | Supported migration of the intended site, branding ownership/drift behavior, unchanged customer letterhead/company settings, no duplicate navigation. |
| Network | Existing ports/subnets/routes remain intact; injected conflict yields a blocked plan; actual listeners and reverse-proxy route match the confirmed plan. |
| Recovery | Full backup restored on the prior image into isolated volumes; app/site versions and business balances checked; route cutover and recovery time recorded. |

Run appropriate upstream tests for preserved behavior and focused tests for our actual changes. The presence of 550 upstream Python test files is not a pass result. Record skipped/unavailable suites and reasons.

## 10. Upgrade and rollback procedure

Before a supported update, record the old digest/source manifest and rehearse restoration of a preliminary full backup into an isolated target. At the actual update window, quiesce user writes and background work, then take the final coordinated database, public/private files and required configuration/encryption-key backup. Verify its completion and integrity before migration. This final snapshot is the rollback point; an earlier rehearsal backup does not cover writes made before the maintenance window. Serialize migration for the named site, then start all application roles on the new digest and verify before admitting traffic.

The inspected generic migrator can exit zero when no site is found or migration is disabled. A successful job exit is insufficient: require the expected site and migration evidence. Do not migrate every bench site by accident.

After a schema migration, rolling back the image alone is not a general recovery strategy. Restore the matching prior database/files/configuration on the prior digest into replacement volumes, verify, and switch the route back. Keep failed volumes for diagnosis. If writes occurred after cutover, stop and reconcile them rather than silently discarding them. See [operations review](OPERATIONS_REVIEW.md).

## 11. Commercial release boundary

Use our original IBTINEX brand with clear upstream attribution. ERPNext is GPLv3; Frappe and the reviewed Docker repository are MIT. Preserve notices, identify modifications and provide matching corresponding source through a GPL-compliant distribution method. A private image registry is compatible with controlled delivery, but does not cancel recipients' license rights. Do not transfer the older Odoo product's signed-term licensing design to ERPNext without an independent license-compatible design.

Review extension dependencies under their actual licenses. Keep support/subscription entitlement separate from false ownership claims over upstream code. Refer to the [source license](https://github.com/frappe/erpnext/blob/886ab6ae187244e7f1b852393384ab6019d56264/license.txt) and [current trademark policy](https://docs.frappe.io/legal/others/license-and-trademark); this engineering plan is not a substitute for legal review of distribution terms.

## 12. Implementation sequence and completion criteria

| Milestone | Concrete output | Exit condition |
|---|---|---|
| 0 — Baseline and brand inputs | Recorded live digest/topology, source pins, approved artwork and token values | Exact baseline and assets established without inventing a new identity. |
| 1 — Small rebrand | ERP metadata patch and `ibtinex_branding` app | Native functionality retained; no duplicate tile; settings reapply safely; branding screenshots reviewed. |
| 2 — Review image | CI build, dependency/provenance record and immutable candidate digest | Fresh install and core UI/API/business tests pass. |
| 3 — Managed deployment | ERPNext-specific studio recipe and isolated review site | Host plan matches observed resources; conflict tests pass; progress/reporting work. |
| 4 — Enterprise profile | Qualified Keycloak/proxy/TLS, operating documentation and restore evidence | IAM, roles, proxy behavior, backup/restore and upgrade gates pass. |
| 5 — Release decision | Signed artifact, corresponding source, evidence and known limitations | Explicitly qualified customer scope; no unproved claims about localization or optional apps. |

The fork and review are completed by this task. Milestones 0–5 are the planned implementation work. A branded image, new deployment and customer release have not been created by this planning branch.
