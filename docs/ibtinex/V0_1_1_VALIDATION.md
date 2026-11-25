# IBTINEX ERP 0.1.1 verification record

## Source boundary

The implementation branch is `feat/ibtinex-erp-v0.1.1-branding`, based on `429f3ea0cb1421bc8f09dd58dd066ddf92fb975f`. Its application baseline is the previously qualified `28e3808696bf415a3f6a5b66b017870ed794f5a1`; the intervening commit records documentation only. The older planning branch was inspected without merging its outdated companion-app proposal.

The ERPNext/Frappe versions remain **16.60.0 / 16.60.2**. Changes are confined to display hooks, isolated CSS/JavaScript, ownership-aware branding settings, installer/build/qualification code and documentation. No DocType schema, ERP controller, report calculation, API, starter record, permission, auth handler, workflow or external integration configuration is changed.

## Local checks before CI

- Deployment/build/secret/recovery/upgrade focused tests pass.
- All 19 branding tests pass, including 48 measured light/dark text/focus/control contrast pairs, existing branding ownership migration, customer names/logos and transactional failure handling.
- All 13 starter contract/schema checks pass against the pinned Framework source.
- JavaScript syntax and Python compilation pass.
- Git whitespace checks and workflow parsing pass.
- Actual installer CLI help agrees with the Windows guide's command syntax.

These local results are not Docker runtime or Windows-host results. This checkout has no Docker daemon and no installed Chromium browser executable. The native Windows and Linux source-build workflow supplies those automated environments.

## Automated candidate gates

The workflow and generated `release-manifest.json` record the observed outcome. At this source checkpoint the following are implemented and awaiting execution:

| Gate | Required evidence |
|---|---|
| Windows Python | Actual `windows-latest` job; binary secret generation, CRLF reader behavior, safe recovery/backup/upgrade guards. |
| Image | Exact source checkout before dependency installation, pinned Framework/source versions, compiled branding bundles. |
| Fresh site | Empty company list without opt-in, native seeded workflows with opt-in, idempotence and occupied-site rejection. |
| Native operations | Administrator login, anonymous API denial, company lookup, ledger/stock invariants, real background work, realtime and container persistence. |
| Browser | Login, Desk, workspace, sales/purchase forms, list, General Ledger, dialogs, mobile navigation, light/dark, focus, contrast regressions, print isolation and text scaling. |
| Existing-site upgrade | Previous private release plus a real posted stock transfer; verified backup before mutation; unchanged ERP counts, GL, bins and site configuration. |
| Visual rollback | Same compatible upstream versions, matching exact image pair, current business state preserved, subsequent branding edits retained. |
| Recovery | Old image reproduces CRLF `Access denied`; new recovery helper repairs only a proven empty partial site on the same image/volumes. |
| Publication | Newly named private GHCR image/digest, source archives, versioned manifest and installer ZIP; existing tags untouched. |

The screenshot “before” is explicitly the same candidate runtime with its isolated brand stylesheet disabled. The gallery does not mislabel it as the previous release.

## Open acceptance gates

Even if the automated workflow passes, the following are not claimed complete:

- Fresh install, failure recovery, upgrade and rollback on an actual Windows Docker Desktop host.
- A complete WCAG 2.2 AA audit, screen-reader testing and human visual acceptance of every ERP surface.
- The full upstream ERPNext/Frappe regression suite and every role/portal/optional-app combination.
- General disaster recovery restoring the full backup into replacement volumes. The implemented rollback is only for the qualified appearance-only image pair.

A release candidate may be published after the automated gates pass, with `customer_release_qualified: false`. It must not be described as a final production/customer release while these gates are unresolved.
