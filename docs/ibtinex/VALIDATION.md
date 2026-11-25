# IBTINEX review image: observed validation

**Result: the source-built review candidate passed installation/runtime qualification and was published to private GHCR on 25 November 2026.** Customer rollout remains unqualified. The scope is the existing IBTINEX icon/favicon, native ERPNext interface, and explicitly selected synthetic starter company.

## Exact candidate and evidence

| Field | Observed value |
|---|---|
| Image source commit | [`28e3808696bf415a3f6a5b66b017870ed794f5a1`](https://github.com/zernova-platform/erpnext/commit/28e3808696bf415a3f6a5b66b017870ed794f5a1) |
| Candidate tag | `ghcr.io/zernova-platform/ibtinex-erpnext:0.1.0-rc.1-g28e3808696bf` |
| Immutable image | `ghcr.io/zernova-platform/ibtinex-erpnext@sha256:b825833c5f1a11546a09793aa7346776fa366e2f0d3d9d2a5ce4888fbd73cea9` |
| Full source workflow | [Run 45689963522](https://github.com/zernova-platform/erpnext/actions/runs/45689963522), job `139472472777`: **success** |
| Evidence / installer artifact | [Artifact 15057833877](https://github.com/zernova-platform/erpnext/actions/runs/45689963522/artifacts/15057833877), 69,684,371 bytes |
| Artifact SHA-256 | `b164c62a4f4374e7c14e6e2b766cd5f2630daf8fc5bd7cbe03e390823e33886e` |
| Installer ZIP | `ibtinex-erp-review-installer.zip`, 11,111 bytes |
| Installer SHA-256 | `b837c3c6e71087b88ff032befa03f7239d8be0fa38d0beadffe8a8899cacad42` |
| Visibility | Post-push package API check verified **private**; complete package grants/ACLs were not independently audited |
| Customer release status | `customer_release_qualified: false` |

Qualification passed at 20:07:00 UTC; GHCR returned the image digest at 20:09:29 UTC. The subsequent visibility check, manifest/installer creation, evidence upload and scoped cleanup succeeded. The downloaded artifact hash was checked and its actual release manifest/runtime reports inspected; the exact installer ZIP was extracted and preserved. GitHub artifact retention ends on **25 December 2026**, so preserve a release copy.

**Commit distinction:** the image was built and tested from `28e3808696bf415a3f6a5b66b017870ed794f5a1`. This record is a subsequent documentation-only update. A later documentation commit or branch HEAD does not replace the image's tested source identity or digest.

## Baseline and execution environment

- ERPNext **16.60.0** upstream: `886ab6ae187244e7f1b852393384ab6019d56264`.
- Frappe **16.60.2**: `2df0425571ebbaed878eabc3edc5b7e7c3327ae0`.
- Frappe Docker recipe/resource reference: `cf568a829790ef658d232daa75457dadf4e1ecc9`; Bench **5.31.1**.
- The full build asserted the application source hashes and versions. The artifact retains build inputs, corresponding-source archives, and resolved Python/OS package inventories; its manifest pins the app, MariaDB and Redis images.
- Runtime proof used **Linux amd64 containers on a GitHub-hosted Ubuntu 24.04 runner**. The initial [runner check](https://github.com/zernova-platform/erpnext/actions/runs/45670747551) observed Docker 28.0.4 and Compose 2.38.2.

The final workflow passed **43 focused checks** before building: 18 deployment/build/Desk, 12 branding, and 13 starter contract/schema checks using pinned Framework source. Real container installation and runtime checks followed. The complete upstream suite was not run.

## Actual native results

The workflow created separate blank and seeded sites in its own ownership-labelled Compose project. Both reported ERPNext 16.60.0 and Frappe 16.60.2.

| Area | Observed result |
|---|---|
| Fresh site without samples | Created successfully; no sample Company inserted; missing opt-in and non-demo seed requests rejected without changing ERP table counts |
| Explicit starter | `IBTINEX Starter Ethiopia`, seed `1.0.0`: **100 tracked scenario records across 21 modules** |
| Native transaction chains | Mapped purchase order/receipt/invoice/payment and quotation/order/delivery/invoice/payment links passed; both invoices had **zero outstanding balance** |
| Native GL | **17 GL entries**, imbalance **0.0** |
| Native General Ledger report | **20 report rows**, bank balance **433,280 ETB** |
| Native Stock Balance report | **4 report rows**, inventory value **72,000 ETB** |
| Initial stock quantities | Raw material **90**, hardware **90**, finished goods **4**, showroom **2** |
| Manufacturing / assets | Work order produced **10**; asset register/opening GL reconciled at **12,000 ETB** |
| Subcontracting | Submitted order/link and source-material/reserve-warehouse assertions passed; dispatch/receipt remains a separate review exercise |
| Repeat installation / guards | Repeated seed preserved all checked ERP business-table counts; missing opt-in, wrong site and occupied site without marker were rejected; rollback restored marker and existing records |
| Native setup / Desk | Installed Application setup flags and home defaults completed; authenticated `/desk` boot had setup complete and no setup-wizard URL/home |
| HTTP / artwork | Served SVG hashes matched source; login artwork, Administrator login and Company API passed; anonymous Company access denied |
| Workers / realtime | Real queued job completed; Engine.IO handshake succeeded |
| Persistence | Application containers were recreated; the persisted site passed qualification again |
| Normal restart after review activity | A real one-unit Finished Goods → Showroom transfer produced balances **3 and 3**. Normal startup preserved business counts, stock/account balances, marker and site-config hash after that edit and a demo-flag change; it returned `created: false`, `already-present` |
| External delivery | Mail muted, scheduler paused, sample portal user disabled, external integrations inert |
| Publication / cleanup | The same tested image was pushed and checked private; only the owned disposable CI project/volumes were removed |

The artifact includes `empty-verification.json`, `starter-verification.json`, `http-verification.json`, `explore-verification.json` and `after-exploration-verification.json`, plus the manifest and build/source inventories. No generated password files or site backups are in the installer.

## Honest coverage of 534 DocTypes

The inventory covers every DocType schema in the pinned **ERPNext** source, including child tables and technical/settings types. Framework-only and optional-app schemas are outside this inventory. A disposition is evidence of data/configuration presence, not proof of every action, variant or report.

| Disposition | DocTypes | Meaning |
|---|---:|---|
| `created` | 69 | Explicit starter documents with native validation |
| `generated-child` | 60 | Rows through native parents or fixtures |
| `generated-native` | 21 | Native setup/workflows generated records such as accounts, ledgers or schedules |
| `default-fixture` | 13 | Native reference data present |
| `native-default-configuration` | 27 | Singleton defaults/settings; not business-record counts |
| `inert-external` | 9 | External-service areas left inert/unconfigured |
| `not-seeded` | **335** | No sample scenario claimed; each gap has a recorded reason |
| **Total** | **534** | Complete source-schema inventory |

The 100 tracked scenario documents are not the total database row count: native fixtures, charts, ledgers and child rows add records. POS Profile/showroom setup is present, but no POS cash session/checkout was fabricated. Serial/batch variants, subcontracting receipt and other gaps remain deliberate review exercises. See the [walkthrough](STARTER_WALKTHROUGH.md) and generated coverage report.

## Separate diagnostic success

[Diagnostic run 45689963543](https://github.com/zernova-platform/erpnext/actions/runs/45689963543), job `139472472877`, also passed for the same candidate; [artifact 15058931488](https://github.com/zernova-platform/erpnext/actions/runs/45689963543/artifacts/15058931488) contains its diagnostic-only evidence. It used the pinned official amd64 runtime with the exact candidate ERP source overlay and unchanged compiled assets, with publication disabled and no package-write permission.

That path checked runtime versions, but did not independently prove the base's exact Framework Git commit; its metadata explicitly records `expected_frappe_commit` and `frappe_commit_verified: false`. **The independent full source-built run remains the published image's qualification authority.**

## Material failures and corrections

| Attempt | Observed problem and correction |
|---|---|
| [Run 45673281372](https://github.com/zernova-platform/erpnext/actions/runs/45673281372), `213ce045…` | Direct internal Bench installation bypassed CLI logger initialization. Replaced with supported `bench get-app`; exact source/version assertions retained. Runtime/publication skipped. |
| [Run 45675363152](https://github.com/zernova-platform/erpnext/actions/runs/45675363152), `ce0e11eb…` | Image build passed. Docker export/import finished 18:35:54 UTC, but optional cache export continued until superseding cancellation at 18:53:13 UTC. Removed remote cache transfer from qualification; runtime/publication had not started. |
| [Run 45680250467](https://github.com/zernova-platform/erpnext/actions/runs/45680250467), `9881439e…` | Fresh-site command passed; direct Python connection attempted `/home/frappe/logs/database.log`. Corrected bootstrap and qualification cwd to the sites directory required by Frappe logging. |
| [Run 45682253430](https://github.com/zernova-platform/erpnext/actions/runs/45682253430), `b0b9c16d…` | Freshness guard misclassified Frappe's disabled `Error Log` / `Integration Request` templates, which intentionally have `is_standard=0`. Added exact native-field/recipient comparison; custom, changed or enabled variants remain rejected. |
| [Run 45686228572](https://github.com/zernova-platform/erpnext/actions/runs/45686228572), `ce6ddbee…` | Guard passed; native Employee insertion rejected missing `Gender: Female`. Added the pinned Framework's `update_genders()` reference-fixture call, retaining link validation. |
| [Final run 45689963522](https://github.com/zernova-platform/erpnext/actions/runs/45689963522), `28e38086…` | All 43 checks, source build, actual native qualification, publication, evidence and cleanup passed. |

Source review additionally corrected normal restart after legitimate edits, native setup/home flags and subcontracting prerequisites before their successful final checks. Those were source-found issues, not separate failed host tests. `bench build --production --force` avoids an optional upstream asset-download path without a request timeout; that was a distinct reliability correction, not the observed cache-delay cause. Superseded candidates were unpublished; no customer installation was changed.

## Concrete rollback and recovery

This installer creates a fresh isolated review project, not an in-place upgrade. Defaults are project `ibtinex-erp-review`, site `ibtinex.localhost`, loopback port **8081**. Use the actual generated directory/project when different values were selected.

**Stop while retaining data.** From the generated `ibtinex-review` directory:

```text
docker compose --env-file .env -f compose.yaml stop
```

To remove this project's containers/network while retaining its named volumes:

```text
docker compose --env-file .env -f compose.yaml down
```

Keep that directory, `.secrets`, site configuration and named volumes. From the extracted installer bundle, restart with:

```text
python deploy.py up --directory ibtinex-review
```

Normal start preserves completed starter data and legitimate edits. Strict `seed.verify()` checks the original fixture expectations and can fail after deliberate edits; it is not a normal-start gate. Container recreation and restart after a real stock edit were exercised. Complete backup/restore was not.

**Get a pristine walkthrough without resetting the edited site.** From the installer bundle:

```text
python deploy.py init --release-manifest release-manifest.json --directory ibtinex-review-clean --project ibtinex-erp-review-clean --site review-clean.localhost --port 8082 --starter-data
python deploy.py up --directory ibtinex-review-clean
```

Do not delete the marker to force reseeding; occupied sites are rejected. For intentionally disposable review data only, `docker compose --env-file .env -f compose.yaml down --volumes` from its generated directory deletes that project's named data. Inspect the project first. No global prune/engine removal is part of rollback; CI removed only its owned disposable project after label verification.

**Icon settings / future upgrades.** The branding restore helper preserves later customizations and restores only settings it owns. For the default site:

```text
docker compose exec -T backend bench --site ibtinex.localhost execute erpnext.ibtinex_branding.restore
```

This is a settings-level operation. Image-level icon references remain, and normal installer startup may reapply eligible settings. Full return to an earlier edition requires its known compatible image/configuration; this first candidate asserts no previous qualified IBTINEX image. The helper has focused unit coverage; a live full icon rollback was not exercised.

No customer database migration occurred. Future schema-changing upgrades need writes quiesced and a coordinated database/files/configuration restore with the compatible image; an image-only downgrade is not a qualified rollback method.

## Remaining limits

- **Review candidate only:** no customer rollout, Ethiopian fiscal certification or customer acceptance. The Standard chart and training tax are illustrative.
- Proof is from **Linux amd64 containers on a GitHub Linux runner**, not the user's Windows PC or existing ERP browser session. Windows requires Docker Desktop Linux-container mode; that Windows installation and arm64 were not tested here.
- Package **visibility was verified private**, but collaborators/inherited grants and the complete ACL were not independently audited. Organization-only pull access is not claimed.
- Full upstream tests, broad security/permission testing, SSO/Keycloak, VPN, public HTTPS/SSL, backup/restore, performance/load, localization and wider ZEDAS integration remain separate qualification work.
- Native GL and Stock Balance reports ran; all 194 source report schemas were not individually exercised. The 335 unseeded DocTypes remain explicit coverage gaps.
- Live bank/payment/email/telephone/EDI integrations remain unconfigured; separately installed HRMS/Payroll, Webshop and other apps are outside this image's qualification.
- Supplied source/installer/evidence excludes customer data, generated deployment credentials, signing keys and site backups. Build inventories do not establish a broader security certification.
