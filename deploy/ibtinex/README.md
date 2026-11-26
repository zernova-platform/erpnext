# IBTINEX ERP 0.1.1: installation and visual upgrades

This recipe packages ERPNext **16.60.0**, Frappe **16.60.2**, the approved IBTINEX icon, a screen-only dark-green/off-white theme, and the existing optional fictional Ethiopian starter company. Native ERP business logic, APIs, schemas, permissions, authentication and printed business documents retain their upstream behavior.

**Start with [WINDOWS.md](WINDOWS.md) for CMD commands.** This is a `0.1.1-rc.1` review candidate. The generated `release-manifest.json` is the authority for the exact tested image, source, automated results and open gates. Native Windows Python tests and Linux-container qualification are distinct from full Windows Docker Desktop acceptance.

## Bundle and prerequisites

The release ZIP contains `ibtinex-erp-review-installer/` with `deploy.py`, `common.py`, `maintenance.py`, `container/bootstrap.py`, `compose.yaml`, release manifests, guides and license notices. Python 3.10+ and Docker Compose v2 are required. Windows uses Docker Desktop Linux containers; a Linux host uses Docker Engine. The image is `linux/amd64` and GHCR access is private.

From that extracted folder, authenticate and create an isolated deployment:

```text
docker login ghcr.io -u YOUR_GITHUB_USERNAME
python deploy.py init --release-manifest release-manifest.json --directory ibtinex-review --port 8081 --starter-data
python deploy.py up --directory ibtinex-review
python deploy.py status --directory ibtinex-review
```

Omit `--starter-data` for an empty site. Use the printed URL and the `Administrator` password file identified in the result. The password is generated locally; it is not in the ZIP, image, manifest or logs.

`init` can be repeated with the same arguments without rotating credentials. Different settings in an existing installation are refused. `up` recognizes a completed site and preserves edited transactions and starter flags. The independent seed verification diagnostic still checks the original fixture balances and is not appropriate after arbitrary user activity.

## Operations

Every command accepts `--directory` pointing to the folder containing the actual `installation.json`, `.env`, `compose.yaml` and `.secrets`. Its Compose project, image, site and port are loaded and checked together. The installer explicitly supplies the stored project/environment so an unrelated shell environment cannot redirect the operation.

| Command | Purpose |
|---|---|
| `init` | Prepare a new empty directory or recognize the same initialization without changing secrets. |
| `status` | Show actual paths, project, images, containers, URL, legacy CRLF files and pending recovery state. |
| `up` | Start the existing deployment; create a site only when appropriate. |
| `stop` | Stop this project while retaining containers and volumes. |
| `recover` | Use the corrected bundled bootstrap on the selected image; archive only a proven empty partial site and retry initialization. |
| `backup` | Quiesce writes/workers, create and verify a full private backup, copy it to the host and restart. |
| `resume` | Resume a recorded interrupted backup before any image transition; upgrade/rollback journals use their own recovery commands. |
| `upgrade --release-manifest FILE` | Validate the exact appearance-only image pair, back up first, apply branding to the existing site and start the new image. |
| `rollback --backup-directory DIR` | Reverse the qualified visual update and its owned branding while preserving business data. |

Mutation commands use a local operation lock. A stale lock after a crash is reported; remove it only after confirming its process has ended. The installer verifies ownership labels on this project's containers, volumes and network. It never removes an unrelated Docker project or runs a global prune.

## Windows password failure and bounded recovery

The previous writer used Python text mode with a trailing newline. Windows translates that newline into CRLF. MariaDB's shell password-file reader removes trailing LF but retains CR; the old Python reader removed both. Those readers therefore supplied different passwords.

New secret files are written atomically as ASCII bytes with **no newline or BOM** on every host. Existing secret files are not normalized or rotated. The bootstrap tests the exact bytes MariaDB used; only an authentication rejection permits trying the historical stripped variant. Existing healthy sites connect with their own site credentials and do not depend on changing the root password.

For an old failed initial installation, run from the **new installer folder**:

```text
python deploy.py status --directory PATH_TO_EXISTING_DEPLOYMENT
python deploy.py recover --directory PATH_TO_EXISTING_DEPLOYMENT
```

Recovery streams the new bundled bootstrap into the existing image, so an old image can be repaired without an unbacked image switch. It proves the original database is absent or has zero tables and refuses extra business files, backups, symbolic links or an unreadable configuration. It archives the partial site configuration/logs under `.ibtinex-recovery` inside the sites volume. It does not drop the old database or remove volumes. A site with tables is preserved and requires repair or a verified restore, not automatic recreation.

Once recovery succeeds, apply the normal backed-up visual upgrade below. New installations authenticate against MariaDB before invoking site creation, preventing this specific password mismatch from leaving another half-created site.

## Existing-installation upgrade

Keep the existing deployment folder and extract the new installer separately. The following uses the **new** `deploy.py` and its manifest with the **old** deployment directory:

```text
python deploy.py status --directory PATH_TO_EXISTING_DEPLOYMENT
python deploy.py upgrade --directory PATH_TO_EXISTING_DEPLOYMENT --release-manifest release-manifest.json
```

The manifest names the exact supported previous digest. The tool checks the current/target source metadata, ERPNext/Frappe versions, application set, database/cache digests and ownership. This release keeps upstream versions and database schema unchanged. No `new-site`, starter seed, generic `migrate`, or company reset runs during upgrade.

Before switching images, the installer enters maintenance, pauses the scheduler and stops application/worker services. The native Frappe backup generator creates the complete database dump, public and private files and configuration. SQL gzip integrity/schema content, file-archive readability, copied sizes and SHA-256 hashes are checked. Native backup encryption is honored; if encryption is configured without its required key, the operation stops before mutation.

The private host backup also retains exact deployment configuration, the original secret-file bytes and the original branding ownership state. The target applies only managed presentation settings and clears caches. Application roles are recreated on the target image, then the original site configuration is restored. No new site is required to receive the theme.

The host result contains `backup_directory`; keep a protected off-machine copy of the complete directory. A journal records interrupted upgrade stages. A partial upgrade never silently wipes volumes or restores an old database over subsequent work.

## Visual rollback and disaster recovery

Use the new installer with the backup returned by its upgrade:

```text
python deploy.py rollback --directory PATH_TO_EXISTING_DEPLOYMENT --backup-directory PATH_TO_UPGRADE_BACKUP
```

Rollback verifies checksums, installation ownership, the recorded image pair, compatible application versions and unchanged deployment credentials. A completed visual upgrade also receives a new full safety backup before rollback, protecting subsequent transactions. Only branding values that still match the upgrade's applied values are restored; later customer names/logos remain. The previous application image and matching deployment configuration are selected. Business database records are **not** restored or discarded.

This support applies only to the manifest-qualified appearance-only pair. Arbitrary schema upgrades require a full restore rehearsal using the prior image plus its matching database, files, configuration and encryption keys in replacement volumes. After post-upgrade business writes, reconcile those writes before any full database restore. This release does not claim a generic disaster-recovery restoration test.

## Build and qualification

The existing GitHub workflow is extended on `feat/ibtinex-erp-v0.1.1-branding`. It retains the tested Frappe commit, Bench/Node versions and exact Python/MariaDB/Redis image digests. The distribution version is separate from ERPNext/Frappe's native version identities. The build checks its source commits and includes the compiled theme on both web and Desk pages.

Publication is gated by:

1. Native Windows Python deployment/branding tests, including exact password-file bytes.
2. Linux focused deployment, branding and starter contracts against the pinned Frappe schemas.
3. Source image build and real blank/starter site installation.
4. Native ERP transaction/ledger assertions, API and Administrator login, anonymous-access rejection, worker execution, realtime, restart and recreation persistence.
5. Real Chromium desktop/mobile/light/dark screenshots, required native views, keyboard focus, semantic contrast checks, theme regression checks and print-style isolation.
6. An upgrade from the previously published private image after a real stock transaction; data/configuration comparisons, visual rollback and repeat upgrade.
7. Reproduction of the old CRLF MariaDB authentication failure and explicit recovery on the same image/volumes.

The before/after visual reference disables only the dedicated theme stylesheet on the **same candidate runtime**. It is labeled accordingly and does not pretend to be an old-release screenshot. Human visual acceptance, complete WCAG 2.2 AA conformance, the full upstream regression suite and Windows Docker Desktop end-to-end installation remain separately reported gates.

After automated qualification, the same loaded image is published to a new source-specific GHCR tag and its immutable digest is recorded. Existing candidate tags are not overwritten. The workflow verifies private package visibility and packages a versioned manifest, Windows ZIP, source archives and qualification evidence. Backup contents, credentials and session tokens are excluded from release artifacts.

## Provenance and notices

The Docker recipe derives from Frappe Docker commit `cf568a829790ef658d232daa75457dadf4e1ecc9`; the vendored resources retain its MIT notice. ERPNext's GPLv3 notice and matching source remain included; Frappe's MIT notice remains in its corresponding source archive and image. The original IBTINEX icon is reused. The styling is an isolated presentation layer; no separate Frappe app, replacement dashboard or new authentication policy is introduced.
