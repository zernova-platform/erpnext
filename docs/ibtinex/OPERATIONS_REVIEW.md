# ERPNext release, packaging, operations, and licensing review

Review date: 2026-11-25. Read-only source and official-document review. No container was built, no release was pushed, no server was changed, and no restore/migration was executed by this reviewer. The review has separately created the ERPNext fork and observed installed versions in the live UI. Recommendations below are proposed acceptance criteria, not claimed test results.

## Verified baselines

| Component | Observed upstream revision | Implication |
| --- | --- | --- |
| ERPNext first branding baseline | `v16.60.0`, `886ab6ae187244e7f1b852393384ab6019d56264`, release branch `version-16` | Matches ERPNext 16.60.0 observed during the review in the user's Installed Applications UI. |
| Frappe first branding baseline | `v16.60.2`, `2df0425571ebbaed878eabc3edc5b7e7c3327ae0`, `version-16` | Matches Frappe 16.60.2 observed in that UI. ERPNext 16.60.0 manifest requires Frappe `>=16.60.0,<17.0.0`. |
| Later ERPNext upgrade candidate | `v16.61.0`, `d770a3a62e21113b61c0c9fb932ad5ee236b74ef` | Latest published ERPNext stable release observed; qualify separately after the first branding baseline. |
| Later Frappe upgrade candidate | `v16.61.0`, `8b19f8c8e334b48e14ecee7231a1a98774c2ebd5` | Latest published Frappe stable release observed; not the user's installed version. |
| Frappe Docker reviewed source | `cf568a829790ef658d232daa75457dadf4e1ecc9` | Use an immutable builder revision, not a floating `main`. |
| Current upstream demo `pwd.yml` | `frappe/erpnext:v16.60.0`, MariaDB `11.8`, Redis `6.2-alpine` | ERP app version agrees with the UI. The actual host image digest, locally cloned file, and infra versions remain unverified. |
| Current production Compose overrides | MariaDB `11.8`, Redis `8.6-alpine` | Do not silently copy demo infrastructure versions into the release recipe. Inventory licenses and test upgrade compatibility for all pinned dependencies. |
| Runtime requirements in baseline source | Frappe 16.60.2 Python `>=3.14,<3.15`, Node `>=24`; ERPNext 16.60.0 Python `>=3.14` | Verified directly in the selected baseline manifests; not inferred from 16.61. Older v15 runtime recipes do not apply. |

References: [ERPNext baseline manifest](https://github.com/frappe/erpnext/blob/886ab6ae187244e7f1b852393384ab6019d56264/pyproject.toml), [Frappe baseline manifest](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/pyproject.toml), [Frappe baseline Node manifest](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/package.json), [later ERPNext release](https://github.com/frappe/erpnext/releases/tag/v16.61.0), [later Frappe release](https://github.com/frappe/frappe/releases/tag/v16.61.0), [demo Compose](https://github.com/frappe/frappe_docker/blob/cf568a829790ef658d232daa75457dadf4e1ecc9/pwd.yml).

The user's UI displayed an unversioned build; it establishes displayed app versions, not a reproducible OCI or Git identity. Resolve the running digest and build provenance through authorized host inspection before treating the installed demo as identical to the upstream tag sources. The first candidate should change branding on the observed 16.60.0/16.60.2 version pair, then test 16.61 separately as an upgrade.

## Recommended repository and customization boundary

The review created [zernova-platform/erpnext](https://github.com/zernova-platform/erpnext), retaining upstream history and branches. Preserve the Python package name `erpnext`, DocType names, module paths, migrations, API paths, database models, and existing copyright/license material. An IBTINEX display brand does not require renaming these internals.

Put the thin brand/configuration layer in a Frappe custom app, e.g. `ibtinex_branding`: approved visual assets, CSS, documented hooks, selected fixtures, idempotent installation/migration patches, and product metadata. Keep customer-specific configuration out of globally installed fixtures. Fork-only core patches should be small, recorded individually, and justified when a supported extension point cannot do the job. The [branding review](SECURITY_AND_BRANDING_REVIEW.md) identifies the small ERP-owned app metadata patch and the exact UI consumers.

Keep release/deployment configuration separate from business logic, with a manifest recording the ERPNext commit, Frappe commit, branding-app commit, Docker builder revision, dependency versions, base image digests, architecture, tested database/Redis versions, output OCI digest, source bundle, and validation evidence. A release label such as `ibtinex-erp:0.1.0-rc.1` should identify the IBTINEX build; retain underlying ERPNext/Frappe versions in About and the manifest.

The Docker repository can be tracked as a pinned build dependency or maintained as an upstream-following fork. Use Compose overrides for product-specific wiring. Do not turn minimal UI rebranding into a permanent rewrite of the deployment engine or framework.

## Image build: actual upstream behavior

The reviewed `images/custom/Containerfile` builds the framework and apps using `bench init`; `images/layered/Containerfile` uses prebuilt Frappe base/build images. Both read `apps.json` through a BuildKit secret mount. The layered version uses `FRAPPE_BRANCH` both as the framework ref and the base/build image tag, so do not assume that every desired framework release tag also has matching published base/build images.

The release image must contain ERPNext plus `ibtinex_branding` before deployment. Installing the app onto a site is a later site operation; fetching code or rebuilding assets inside an already running production container is not the repeatable build path.

The upstream `apps.json` schema uses repository URL and `branch` fields. The documented values are branches/tags. Do not assume an arbitrary commit SHA works as a `git clone --branch` argument. Use protected release tags resolved and checked against the manifest, or explicitly implement and test a checkout-by-commit build step. Verify resolved source before the Containerfile removes `.git` directories. Upstream tags are not necessarily immutable; release metadata currently reports `immutable: false`.

Secret file contents do not automatically invalidate Docker's cache. Set `CACHE_BUST` from the resolved source/dependency manifest so changing the branding app or an upstream revision really rebuilds the application layer. Build arguments are not a safe channel for private checkout tokens. BuildKit prevents secret-file persistence by default, but the build and log output still need secret-redaction checks.

The upstream recipe includes floating dependency resolution such as `pip install frappe-bench` and OS package installs. Pinning the ERPNext commit alone does not establish reproducible builds. Record resolved packages/base digests and qualify an exact image; do not promise byte-for-byte reproduction until dependency locking is implemented and demonstrated.

References: [custom Containerfile](https://github.com/frappe/frappe_docker/blob/cf568a829790ef658d232daa75457dadf4e1ecc9/images/custom/Containerfile), [layered Containerfile](https://github.com/frappe/frappe_docker/blob/cf568a829790ef658d232daa75457dadf4e1ecc9/images/layered/Containerfile), [build setup](https://github.com/frappe/frappe_docker/blob/cf568a829790ef658d232daa75457dadf4e1ecc9/docs/02-setup/02-build-setup.md), [source refresh guidance](https://github.com/frappe/frappe_docker/blob/cf568a829790ef658d232daa75457dadf4e1ecc9/docs/11-how-to/06-control-source-refreshes-in-ci-builds.md), [container immutability](https://github.com/frappe/frappe_docker/blob/cf568a829790ef658d232daa75457dadf4e1ecc9/docs/13-explanation/01-container-immutability.md).

## Runtime topology and deployment recipe

The base Compose file runs the same app image in seven roles: configurator, backend, frontend/nginx, websocket, queue-short, queue-long, and scheduler. Add the selected MariaDB/Redis overrides and site creation/install/migration jobs. The `sites` volume is shared by application roles; database data and persistent queue data have separate volumes.

All application roles must use the same verified OCI digest. The main entrypoint replaces the shared assets path with a link into the baked image assets. Mixed app revisions therefore risk inconsistent assets and execution, not just differing version labels. The base Compose image expression is `image:tag`; a product override should supply a full `registry/image@sha256:...` reference for every app role rather than trying to squeeze a digest into `CUSTOM_TAG`.

Keep the customer's existing proxy and remote-access design. The upstream Traefik/HTTPS examples mount the host Docker socket; a `:ro` filesystem mount does not turn the Docker API into a read-only API. For the platform recipe, route to the ERP frontend through the established edge proxy and constrain trusted forwarded headers to that path. Do not add a second competing listener on 80/443 or broaden existing VPN/SSO access while installing ERP. Test websocket upgrade, attachment upload/download, PDF delivery, real client IP, redirect URLs, and secure-session behavior behind the actual TLS route.

Use a new Compose project, new sites/database volumes, and an available loopback port for the first IBTINEX review install. Leave the existing Windows ERPNext demo intact. An example project name is `ibtinex-erp-review`; the exact port must be discovered as available rather than asserted in advance. A fresh database and optional synthetic sample data are separate explicit deployment choices.

Windows development/review uses Linux containers through the working Docker Desktop/WSL2 environment. The customer recipe should target the qualified Linux Docker Engine host or a Linux guest on Windows Server. Docker Desktop is not supported on Windows Server. Do not represent a native Windows container as the ERP runtime.

References: [base Compose](https://github.com/frappe/frappe_docker/blob/cf568a829790ef658d232daa75457dadf4e1ecc9/compose.yaml), [MariaDB override](https://github.com/frappe/frappe_docker/blob/cf568a829790ef658d232daa75457dadf4e1ecc9/overrides/compose.mariadb.yaml), [Redis override](https://github.com/frappe/frappe_docker/blob/cf568a829790ef658d232daa75457dadf4e1ecc9/overrides/compose.redis.yaml), [asset entrypoint](https://github.com/frappe/frappe_docker/blob/cf568a829790ef658d232daa75457dadf4e1ecc9/resources/core/main-entrypoint.sh), [nginx template](https://github.com/frappe/frappe_docker/blob/cf568a829790ef658d232daa75457dadf4e1ecc9/resources/core/nginx/nginx-template.conf), [HTTPS example](https://github.com/frappe/frappe_docker/blob/cf568a829790ef658d232daa75457dadf4e1ecc9/overrides/compose.https.yaml), [Docker Windows support](https://docs.docker.com/desktop/setup/install/windows-install/).

## Build, publication, and promotion plan

Keep one release authority. If the existing platform uses Jenkins to build/promote, Jenkins builds and validates the image and publishes to GHCR; ZEDAS installs the qualified image. If the actual canonical pipeline uses Actions, retain that rather than adding a duplicate publisher. Repository ownership and registry ownership are related but distinct settings.

Recommended pipeline order:

1. Resolve and verify all source tags/commits and required license files. Review inherited upstream workflows before enabling publishing on the fork.
2. Lint the branding app and validate configuration/fixtures; build with the exact source manifest and dependency/base-image pins.
3. Create a fresh disposable site, install ERPNext and branding, and run UI/API/role checks plus core transaction flows.
4. Recreate every app container and prove branding/fixtures still work. Exercise queues, websocket notifications, scheduler, mail sandbox, uploaded/private files, and PDF fonts.
5. Test upgrade from the last supported image/site backup; require migration completion and post-migration checks.
6. Generate SBOM, vulnerability results, source bundle, checksums, release manifest, and image signature/attestation. Record the exact digest.
7. Publish the tested artifact once; promote that digest between review, QA, and release without rebuilding it per environment.

The upstream reusable `app-build-image.yml` generates only one application entry in `apps.json` and smoke-tests the presence of framework/app directories. That does not prove ERPNext plus a branding app installs and operates. It can serve as a build reference but is not sufficient acceptance coverage by itself.

For GHCR, GitHub Actions can use its job `GITHUB_TOKEN` with package write permission. A customer's pull identity needs only package-read access; current GHCR documentation supports a classic PAT with `read:packages` plus appropriate package access. Keep checkout/publish and pull credentials distinct. Use credential storage or ephemeral login configuration, not repository files or command output. Signing keys remain in the controlled release system; distribution verification needs public trust material only.

References: [upstream reusable workflow](https://github.com/frappe/frappe_docker/blob/cf568a829790ef658d232daa75457dadf4e1ecc9/.github/workflows/app-build-image.yml), [GHCR authentication](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

## Upgrade, backup, and rollback gates

Before a version change, capture the old digest and source manifest and take a consistent database backup with public/private files plus the necessary site configuration. Preserve the existing site encryption key and any backup encryption key through a secret backup channel; these are required for encrypted stored credentials and encrypted backups respectively. `bench backup` alone does not include uploaded files; add `--with-files` for the full site backup operation.

Rehearse restore of a preliminary full backup on an isolated site using the old image. At the actual update window, first quiesce user writes, scheduler and workers; keep DB/Redis available. Then take a final coordinated database/files/configuration backup and verify completion and integrity before migration. This final backup is the rollback point; the earlier rehearsal backup does not cover intervening writes. Run migration as a required, serialized stage on the intended site, then restart the application roles on the target digest and perform acceptance checks before resuming traffic.

The upstream migrator returns exit code zero when migration is disabled or no sites are found. A release gate must check that the intended site was discovered and migrated, not only that the container exited successfully. Its default command is `bench --site all migrate`; a managed product recipe must deliberately scope the site(s), volumes, networks, and credentials instead of accidentally migrating another bench. Base app services do not wait on the migrator automatically.

If an update fails after database migration, switching only the image tag back is not a general rollback. Restore the matched pre-migration DB/files/configuration into isolated replacement volumes on the previous image, validate, and switch the route back. Preserve the failed volumes for diagnosis. Frappe does not support arbitrary site downgrades. Record the maintenance window, rollback point, and whether writes occurred after cutover.

References: [backup recipe](https://github.com/frappe/frappe_docker/blob/cf568a829790ef658d232daa75457dadf4e1ecc9/docs/11-how-to/04-create-backups.md), [migration procedure](https://github.com/frappe/frappe_docker/blob/cf568a829790ef658d232daa75457dadf4e1ecc9/docs/11-how-to/11-automate-site-migrations.md), [migrator implementation](https://github.com/frappe/frappe_docker/blob/cf568a829790ef658d232daa75457dadf4e1ecc9/overrides/compose.migrator.yaml), [baseline restore command implementation](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/commands/site.py), [baseline backup implementation](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/utils/backups.py), [restore documentation](https://docs.frappe.io/framework/user/en/bench/reference/restore), [site config reference](https://docs.frappe.io/framework/user/en/basics/site_config).

## Commercial distribution and branding

ERPNext is GPLv3; Frappe Framework and the reviewed Docker repository use MIT licenses. Commercial sale/support is permitted. Distributing a modified ERPNext image requires preserving notices, documenting modifications, and supplying the corresponding source under GPL terms through a compliant distribution method. Ship the matching source and build/install material with each release. A private registry does not remove recipients' GPL rights. Review separately developed apps and all image dependencies under their actual licenses; do not assume everything becomes proprietary merely because it lives in another repository.

Use the distinct IBTINEX name and approved original assets. Keep truthful upstream attribution and an accessible license/source view. The current Frappe trademark policy permits descriptive references but prohibits implying endorsement and recoloring or combining its logos as the vendor's own identity. Software-image signing is a release-authenticity mechanism; do not repurpose the Odoo signed-term licensing scheme to impose incompatible restrictions on GPL ERPNext.

References: [baseline ERPNext license](https://github.com/frappe/erpnext/blob/886ab6ae187244e7f1b852393384ab6019d56264/license.txt), [baseline Frappe license](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/LICENSE), [Docker repository license](https://github.com/frappe/frappe_docker/blob/cf568a829790ef658d232daa75457dadf4e1ecc9/LICENSE), [GNU GPLv3](https://www.gnu.org/licenses/gpl-3.0.html), [current Frappe license/trademark policy](https://docs.frappe.io/legal/others/license-and-trademark).

## Remaining proof before an IBTINEX release

- Observe the user's real running image digest and provenance, full installed app list, project name, and site identity through an authorized host session. The displayed ERPNext/Frappe versions have already been observed by the review in the live UI.
- Verify approved IBTINEX assets and exact package/repository destinations; avoid inventing a new visual identity.
- Build the proposed combined image and record dependency/image/source provenance.
- Demonstrate fresh install, required business workflows, Keycloak authentication and role isolation, private-file protection, PDF/email branding, queue/scheduler operation, container recreation, backup/restore, and one supported upgrade path on isolated synthetic data.
- Validate the deployment recipe through ZEDAS separately; source review cannot establish actual host/network behavior.

The fork creation is recorded in README.md. This source review provides no evidence that a release image exists or a customer deployment is ready.
