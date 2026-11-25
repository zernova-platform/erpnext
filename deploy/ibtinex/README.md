# IBTINEX ERP review image and installer

This recipe packages ERPNext **16.60.0**, Frappe **16.60.2**, the existing IBTINEX Studio mark as the icon/favicon, and an explicitly selected synthetic Ethiopian starter company. It preserves native ERP workflows and package identities. This is a review candidate, not a qualified customer rollout.

## Install the verified candidate

Download the installer ZIP from the successful `IBTINEX / Build, verify and publish candidate` workflow artifact. It contains `release-manifest.json` with the exact app, database and Redis digests, plus these portable Python/Compose files. Failed runs do not produce a verified installer bundle. Python 3.10+ and working Docker Compose v2 are required. Windows uses Docker Desktop with Linux containers; a Linux host uses Docker Engine. The recipe targets `linux/amd64`.

Authenticate Docker to the private organization package using an identity with package-read access:

```text
docker login ghcr.io
```

From the extracted installer directory, initialize a new deployment with the optional synthetic starter company:

```text
python deploy.py init --release-manifest release-manifest.json --directory ibtinex-review --port 8081 --starter-data
```

Omit `--starter-data` for a fresh, unseeded ERP site. That is the default. The choice is recorded before site creation; the installer refuses to seed an existing non-demo site.

Start the prepared deployment:

```text
python deploy.py up --directory ibtinex-review
```

Open **http://localhost:8081**. The existing demo on port 8080 is unaffected. The account is `Administrator`; its generated password is in `ibtinex-review/.secrets/admin-password`. Password values are never printed by the installer or embedded in the image, manifest or report. Store the deployment directory securely; Windows engineers should place it within their protected user profile and retain its access restrictions.

The starter contains synthetic records and connected posted workflows. Review the packaged `erpnext/ibtinex_starter` coverage manifest for which areas contain transactions, configuration or metadata only. Mail is muted, the scheduler is paused for the demo, and outbound integrations remain unconfigured. This sample company must not be mistaken for an Ethiopia regulatory certification or a real customer dataset.

## Scope and repeat operation

The installer creates its own Compose project, ownership labels, bridge network, MariaDB volume, sites volume and queue volume. Only the frontend binds a host port, on loopback. It checks port and project ownership before starting. The repository's deployment studio must still provide its fuller host/subnet/route plan and confirmation process when this recipe is integrated into that tool. No Docker socket is mounted into the ERP containers.

Run `up` again to restart the same deployment. Existing app sets are checked and branding preserves customized settings. A compatible completed starter marker and its Company are recognized without reseeding, resetting site flags or requiring the original stock balances; engineers can continue exploring normal ERP transactions. The explicit seed `verify()` diagnostic still checks the original fixture expectations and may fail after legitimate review edits. This command is not a schema upgrade procedure; upgrades require a separately tested migration and coordinated backup/restore plan.

The generated `.env` contains image references and identifiers only. Passwords live in `.secrets/` and are mounted only into MariaDB and the one-off setup container. On Linux, secret files use mode 0600. The setup container reads them, drops to runtime UID 1000, then creates the site. The application stores its normal database credential in its site configuration.

To stop this one installation, use Compose from its generated directory:

```text
docker compose stop
```

Do not add `--volumes` when removing a review stack unless its data is intentionally disposable. No global prune or engine removal is used by this installer.

## Build and verification

`.github/workflows/ibtinex-image.yml` runs only for `ibtinex/starter-0.1.0` in `zernova-platform/erpnext`, or a manual dispatch of that branch. It prepares exact source/image inputs, builds from the pinned source and resolved inputs, then creates an isolated blank site and a separate explicitly seeded site. It checks native seed assertions, all ERP business-table counts across repeat installation, opt-in and target-site rejection, a real worker job, native HTTP/API login, authenticated Desk setup completion, anonymous access denial, served artwork hashes, realtime handshake and container recreation. It then posts a legitimate stock transfer and proves normal start preserves the edited records, balances and site configuration. Only after these checks pass does it push the same loaded image to GHCR and verify the package is private.

The candidate tag contains the source SHA. Install using the resulting immutable digest, not a moving branch or `latest`. Publication does not prove all upstream tests, security tests, SSO, backups, localization or customer acceptance have passed. Those remain separately reported release gates. The retained artifact contains exact source archives, build inputs, resolved Python/OS packages, verification results and the ready installer bundle; it excludes credentials and site backups.

## Build provenance and licenses

The custom Containerfile is adapted from Frappe Docker commit `cf568a829790ef658d232daa75457dadf4e1ecc9`; vendored nginx/start resources and the upstream MIT license are under `vendor/frappe_docker`. Changes pin Bench 5.31.1 and Frappe 16.60.2, verify both application commit hashes before removing Git metadata, split framework/application build layers, add the required OpenCV libraries, package scoped installer/check scripts and use a non-destructive asset-link entrypoint. `apps.json` is a BuildKit secret. Its source manifest/commit also changes the build cache key.

ERPNext source is GPLv3, Frappe Framework and the Docker build reference use MIT. Upstream notices remain included. The workflow provides matching ERPNext/Frappe source archives and build material. A private registry does not remove recipients' GPL rights. Image/container licenses and a commercial support entitlement are separate concepts.
