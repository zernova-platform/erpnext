# IBTINEX ERP 0.1.1 verification record

## Verified release candidate

The qualification workflow completed successfully on **25 November 2026 (America/New_York)**, and the following review candidate was published:

| Record | Observed value |
|---|---|
| Qualified source | `401eb53bcc3417ff0d1fc5c742c45634e6ef5c0c` |
| Qualification run | [45729273817 — SUCCESS](https://github.com/zernova-platform/erpnext/actions/runs/45729273817) |
| Release | [ibtinex-erp-0.1.1-rc.1-g401eb53bcc34](https://github.com/zernova-platform/erpnext/releases/tag/ibtinex-erp-0.1.1-rc.1-g401eb53bcc34) |
| Private image | `ghcr.io/zernova-platform/ibtinex-erpnext@sha256:e4e5677307aa1a585263704210c640b3124d7b5a3a23b2536245cef36486c5d8` |
| Image platform | `linux/amd64` |
| Manifest status | `verified-review-candidate` |
| Customer release qualified | `false` |

The release's `release-manifest.json` and `ibtinex-erp-0.1.1-rc.1-qualification.zip` contain the machine-readable records described below. The successful automated run qualifies this exact review candidate; the open acceptance gates remain listed at the end of this document.

## Source boundary

The implementation branch is `feat/ibtinex-erp-v0.1.1-branding`, based on `429f3ea0cb1421bc8f09dd58dd066ddf92fb975f`. Its application baseline is the previously qualified `28e3808696bf415a3f6a5b66b017870ed794f5a1`; the intervening commit records documentation only. The older planning branch was inspected without merging its outdated companion-app proposal.

The ERPNext/Frappe versions remain **16.60.0 / 16.60.2**. Changes are confined to display hooks, isolated CSS/JavaScript, ownership-aware branding settings, installer/build/qualification code and documentation. No DocType schema, ERP controller, report calculation, API, starter record, permission, auth handler, workflow or external integration configuration is changed.

The built Framework commit is `2df0425571ebbaed878eabc3edc5b7e7c3327ae0`, with Bench **5.31.1** and Node **24.22.3**. `build-inputs.json` records the exact source and base-image digests. The ERP source is fetched and verified at the requested commit before Bench installs its dependencies.

## Focused code checks

The successful qualification run records these results:

| Environment | Tests | Result |
|---|---|---|
| Linux | 57 deployment/build/secret/recovery/upgrade/visual-helper tests, 19 branding tests and 13 starter contract/schema checks | **89 passed** |
| Actual Windows runner, Python 3.12.10 | 57 deployment/build/secret/recovery/upgrade/visual-helper tests and 19 branding tests | **76 reported: 74 passed, 2 symlink tests skipped** |

The branding tests cover 48 light/dark text, focus and control contrast pairs, existing branding ownership migration, customer names/logos and transactional failure handling. The starter contract/schema checks use the pinned Framework source. Windows Python execution verifies the installer code on Windows; it does not perform a Windows Docker Desktop installation.

Additional local checks completed before qualification:

- JavaScript syntax and Python compilation pass.
- Git whitespace checks and workflow parsing pass.
- Actual installer CLI help agrees with the Windows guide's command syntax.

Docker runtime and Chromium browser results below came from the Linux GitHub Actions environment. The local checkout had no Docker daemon or installed Chromium executable.

## Completed automated candidate gates

These results were observed on disposable synthetic installations. `qualification-gates.json` records `passed` for browser, upgrade/rollback and legacy CRLF recovery; `release-manifest.json` records the complete candidate gate summary.

| Gate | Observed result and evidence |
|---|---|
| Windows Python | **Passed**, with the two symlink skips stated above. Binary secret generation, CRLF reader behavior and recovery/backup/upgrade guards ran in the actual `windows-latest` job. |
| Image | **Passed.** The exact source image built with pinned upstream versions and compiled branding bundles; see `build-inputs.json` and `release-manifest.json`. |
| Fresh site | **Passed.** No sample company without opt-in; explicit starter installation, repeat-install count preservation and occupied/wrong-site rejection passed in `empty-verification.json` and `starter-verification.json`. |
| Native operations | **Passed.** Administrator login, authenticated company lookup, anonymous API denial, completed setup state, native ledger/stock assertions, real background work, realtime handshake and container persistence are recorded in `http-verification.json`, `starter-verification.json` and the exploration/restart records. |
| Browser | **Passed.** Chromium exercised native login, Desk, workspace, sales/purchase forms, list, General Ledger, dialog and mobile navigation, with light/dark, focus, contrast, print isolation and text-scaling checks. See the evidence scope and screenshot limitation below. |
| Existing-site upgrade | **Passed on Linux.** A real previous-image installation and posted stock transfer survived the mandatory backup and upgrade with ERP counts, GL balances, bins and site configuration preserved; see `upgrade-verification.json`. |
| Appearance-only rollback | **Passed on Linux.** Rollback and repeat upgrade preserved the current business state for the qualified image pair; see `rolled-back-after-exploration-verification.json` and `reupgraded-after-exploration-verification.json`. |
| CRLF recovery | **Passed on Linux.** The old image reproduced `Access denied`; recovery preserved the existing volumes, repaired the explicitly proven empty partial site and passed native starter checks plus repeat start; see `legacy-password-recovery.json`. |
| Publication | **Completed.** The private GHCR image was published. Its digest is recorded in the manifest; corresponding source archives, the manifest, qualification evidence and the versioned Windows installer ZIP are attached to the release above. |

## Browser evidence and assistant visual review

`visual/visual-verification.json` records **27 passed checks**, **36 before/after pairs (72 PNG screenshots)**, **1,139 rendered text-contrast samples**, **zero sampled numerical contrast failures** and **zero theme contrast regressions**. The browser was Chromium **151.0.7922.34** on Linux. All 22 runtime semantic text/background pairs pass their contrast threshold; the lowest recorded ratio is **5.517:1**.

The screenshot “before” is explicitly the same candidate runtime with its isolated brand stylesheet disabled. The gallery does not mislabel it as the previous release.

The final screenshots received an **assistant visual review** of mobile navigation in light/dark, the light desktop Selling workspace and General Ledger desktop/mobile captures. The previously observed light mobile navigation defect is corrected: ordinary labels now measure **6.4:1** against the white sheet; dark-mode labels measure **9.097:1**. The reviewed final navigation, workspace and populated report surfaces showed no new theme defect. This inspection is not a human acceptance audit.

There are **18 background/opacity cases flagged for manual review**, all with numerically passing sampled ratios of **14.2:1** or **15.924:1**. Those flags remain visible in the report because automated background sampling alone cannot establish full accessibility conformance.

One final screenshot has an evidence limitation: `general-ledger-desktop-light-after-ibtinex.png` captured a transient **Loading...** state. Its native-theme comparison, subsequent desktop-dark and mobile-light screenshots contain populated ledger rows, and the native General Ledger fixture-data check passed. The affected image does not establish a completed desktop-light report visual comparison; it should be recaptured before final human visual acceptance. No screenshot has been replaced or relabeled to conceal this timing limitation.

## Upgrade and recovery scope

The qualified upgrade starts from `ghcr.io/zernova-platform/ibtinex-erpnext@sha256:b825833c5f1a11546a09793aa7346776fa366e2f0d3d9d2a5ce4888fbd73cea9`. On that actual previous image, the workflow installed the starter and posted an additional native stock transfer. A full backup was required before upgrading. The subsequent upgrade, appearance-only rollback and repeat upgrade preserved all recorded ERP table counts, account balances, stock bins and site configuration. Backup contents stayed in the private disposable CI directory and were not published. These observations are recorded in `upgrade-verification.json` and its exploration-state companion files.

`legacy-password-recovery.json` records the reproduced cause of the prior authentication failure: MariaDB retained the carriage return from a CRLF password file while the old Python reader stripped it. The workflow reproduced the old-image failure, preserved the same volumes, performed explicit empty-partial-site recovery, authenticated with the legacy CRLF secret and completed native starter workflows. `crlf-recovered-starter-verification.json` and `crlf-restarted-starter-verification.json` confirm the recovered installation and safe repeat start. This exercise was performed on Linux; Windows Docker Desktop recovery remains an open host-level gate.

## Other pull-request checks

At the time of this verification record, inherited pull-request lint/advisory jobs remained queued on the unavailable **`erpnext-arc-light`** runner. Their queued state is not a successful result and is separate from the completed IBTINEX qualification workflow linked above.

## Open acceptance gates

The successful candidate workflow does not complete these gates:

- Fresh install, failure recovery, upgrade and rollback on an actual Windows Docker Desktop host.
- A complete WCAG 2.2 AA audit, screen-reader testing and human visual acceptance of every ERP surface, including recapture of the desktop-light General Ledger image described above.
- The full upstream ERPNext/Frappe regression suite and every role/portal/optional-app combination.
- General disaster recovery restoring the full backup into replacement volumes. The implemented rollback is only for the qualified appearance-only image pair.
- Safari, Firefox, real touch hardware and operating-system high-contrast testing, which were outside the Chromium suite.

The published artifact is a release candidate with `customer_release_qualified: false`. It must not be described as a final production/customer release while these gates remain unresolved.
