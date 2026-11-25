# IBTINEX review image: observed validation

This record separates executed checks from intended behavior. The product scope
is the existing IBTINEX icon/favicon, the native ERPNext interface, and an
explicitly selected synthetic starter company. It does not qualify customer
rollout or a full ERP/security acceptance program.

## Baseline

- ERPNext 16.60.0 upstream: `886ab6ae187244e7f1b852393384ab6019d56264`.
- Frappe 16.60.2: `2df0425571ebbaed878eabc3edc5b7e7c3327ae0`.
- Frappe Docker reference: `cf568a829790ef658d232daa75457dadf4e1ecc9`.
- Target runtime: Linux amd64 containers. The build runner is GitHub-hosted
  Ubuntu 24.04, with Docker 28.0.4 and Compose 2.38.2 observed in the runner check.

## Executed checks

| Source / run | Observed result |
|---|---|
| Local source before the first full build | 12 focused branding tests, 9 deployment guardrail tests and 9 starter contract/schema tests passed. Pinned Frappe source was used for schema validation. |
| [Runner check](https://github.com/zernova-platform/erpnext/actions/runs/45670747551), commit `b43c0fa680cbfc55449408a2815c0239c5638978` | Passed; Docker Engine and Compose were actually available. |
| [First full build](https://github.com/zernova-platform/erpnext/actions/runs/45673281372), commit `213ce0450a1f4d88eca3b78f0a3a9d3548d35a9c` | All 30 checks and dependency resolution passed. The image build failed before ERP application installation because a direct internal Bench API invocation bypassed the CLI logging setup. Runtime qualification and publication were skipped. |

The initial build failure is corrected by invoking the supported Bench command
through an argument list, while retaining the BuildKit source manifest and exact
commit checks. A subsequent run must establish that the correction works.

## Runtime results

The corrected image's fresh installation, native business workflows, native
reports, normal restart after legitimate sample edits, HTTP/API, worker,
realtime and registry-publication results are pending an observed successful run.
A source test or generated Compose plan is not substituted for those results.

## Review boundary and rollback

The installer uses an isolated Compose project and a loopback HTTP port. The
default review port is 8081. No existing customer host or the user's Windows
Docker installation has been changed by these GitHub-hosted tests.

Normal startup must preserve legitimate edits to an already initialized starter
company. The strict starter diagnostic remains available separately to identify
changes to the original demonstration balances; it is not a normal-start gate.

To stop the review installation, run `docker compose stop` from its generated
installation directory. Preserve that directory and its volumes to preserve the
review. Recreate a pristine walkthrough as a new isolated installation; do not
overwrite an edited site with starter data. Removing disposable CI volumes is
scoped to the CI project after ownership-label verification.

The icon helper can restore settings it still owns. A complete icon rollback
also uses the previous image because the fork's fallback references are part of
the image. This release performs no customer database migration. Downgrading a
future schema migration will require a coordinated database/files/configuration
restore and is not claimed as an image-only rollback here.

## Limitations to retain with the release

- The all-DocType inventory is complete; the synthetic business scenarios are
  finite. The generated report exposes every unseeded area and its reason.
- External bank, payment, email, telephone and EDI services are not configured.
- The training chart and tax are examples, not customer fiscal configuration.
- The complete upstream test suite, SSO, SSL, backup/restore qualification and
  customer acceptance are not included in this small review-image task.
- Linux amd64 runtime proof does not establish a native Windows-engine or arm64
  result. Windows deployment requires Docker Desktop's Linux-container mode.
- The live browser connection to the user's existing ERP was unavailable during
  implementation. Source changes and GitHub runtime checks must not be described
  as an observed deployment into that existing browser session.
