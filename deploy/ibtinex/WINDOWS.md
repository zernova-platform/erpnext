# IBTINEX ERP 0.1.1 — Windows quick guide

This guide is for the `0.1.1-rc.1` review candidate, ERPNext 16.60.0 and Frappe 16.60.2. Use Docker Desktop in **Linux containers** mode, Python 3.10 or newer, and CMD. The release manifest records the exact image tested by the automated pipeline. Full installation on a Windows Docker Desktop host remains a separate acceptance gate; a Linux container pass is not a Windows installation pass.

**Already have ERP running? Go to “Upgrade your existing installation.”** Keep its current deployment directory, passwords, and Docker volumes.

## 1. Download and open the installer

Download the Windows installer ZIP from the GitHub release linked with this candidate. Extract it. The ZIP contains a folder named `ibtinex-erp-review-installer`; `deploy.py` is **inside** that folder.

For the existing working-folder convention, open CMD and run:

```bat
cd /d C:\work-space\IBTINEX-ERP\ibtinex-erp-review-installer
dir deploy.py
python --version
docker version
docker compose version
```

If `dir deploy.py` reports that the file is missing, open the extracted folder containing that file and run CMD there. Do not run `python deploy.py` from its parent folder.

Sign in to GHCR with a GitHub account that can read the private package:

```bat
docker login ghcr.io -u YOUR_GITHUB_USERNAME
```

When Docker asks for the password, paste your GitHub PAT with package-read access. The password prompt keeps it out of your command history.

## 2. Fresh installation

Choose a new deployment folder. This example uses a sibling of the installer folder:

```bat
set "ERP_DIR=C:\work-space\IBTINEX-ERP\ibtinex-review"
python deploy.py init --release-manifest release-manifest.json --directory "%ERP_DIR%" --project ibtinex-erp-review --site ibtinex.localhost --port 8081 --starter-data
python deploy.py up --directory "%ERP_DIR%"
python deploy.py status --directory "%ERP_DIR%"
```

`--starter-data` includes the fictional Ethiopian demonstration company. Omit it for an empty ERP site. The installer does not overwrite an occupied folder or another installation's Docker project.

Open the **URL printed by the installer**, for example `http://localhost:8081`. Sign in as `Administrator`.

Read your generated Administrator password locally:

```bat
type "%ERP_DIR%\.secrets\admin-password"
```

Keep this password and the deployment folder private. Changing the password file later does not reset an already-created Administrator account.

## 3. Stop and restart safely

From the installer folder:

```bat
python deploy.py stop --directory "%ERP_DIR%"
python deploy.py up --directory "%ERP_DIR%"
```

These commands preserve your persistent volumes and business records. `up` recognizes an existing installation and does not replace a completed starter with a fresh one.

## 4. Find the existing installation, project and port

If you used an earlier installer, its deployment folder may be **inside** the old installer folder, for example:

```text
C:\work-space\IBTINEX-ERP\ibtinex-erp-review-installer\ibtinex-review
```

Find the existing `installation.json` and list your Docker projects:

```bat
dir /s /b C:\work-space\IBTINEX-ERP\installation.json
docker compose ls
```

Set `ERP_DIR` to the folder that contains your real `installation.json`, `.env`, `compose.yaml`, and `.secrets`. For example:

```bat
set "ERP_DIR=C:\work-space\IBTINEX-ERP\ibtinex-erp-review-installer\ibtinex-review"
python deploy.py status --directory "%ERP_DIR%"
```

Check that the reported project and URL match your running ERP. The configured port may differ from 8081. The installer checks ownership labels before changing containers; it does not adopt unrelated projects.

## 5. Upgrade your existing installation

Extract the new installer into a **separate folder** so you retain the old installer and deployment directory. Open CMD in the new folder containing the new `deploy.py` and `release-manifest.json`. Keep `ERP_DIR` pointing to the **old, existing deployment folder**.

```bat
docker login ghcr.io -u YOUR_GITHUB_USERNAME
python deploy.py status --directory "%ERP_DIR%"
python deploy.py upgrade --directory "%ERP_DIR%" --release-manifest release-manifest.json
python deploy.py status --directory "%ERP_DIR%"
```

The upgrade validates the exact supported old image, matching ERPNext/Frappe versions and database/cache images. It stops application activity, takes a full backup of the database, public/private files and required configuration, verifies copied file hashes, applies the presentation settings on your existing site, and starts the new application image. It does not create a new company or site. Your port, passwords, business records, and volumes remain the same.

Save the reported `backup_directory`. Store a secure copy of that complete backup outside the machine before treating it as disaster-recovery protection. Backup files include sensitive configuration/encryption material and must not be attached to a public issue.

If the installer reports an unsupported old digest or a version mismatch, stop there. A different upstream version needs a separately qualified upgrade; editing the manifest to suppress the check would remove its compatibility protection.

After successful upgrade, refresh your browser with **Ctrl+F5**. The native ERP screens should use the new dark-green/off-white theme.

## 6. Roll back this visual update

Use the **new installer** and the exact backup directory returned by its upgrade command:

```bat
python deploy.py rollback --directory "%ERP_DIR%" --backup-directory "C:\FULL\PATH\RETURNED\BY\UPGRADE"
python deploy.py status --directory "%ERP_DIR%"
```

This operation is limited to the qualified appearance-only image pair. It restores the previous image/configuration and branding settings still owned by that upgrade. It preserves business transactions, including changes made after the visual upgrade; it does not rewind the database. Customer branding edited after the upgrade is retained.

This is **not** a general schema-version rollback. If a different release changes schemas, restore its matching database, files, configuration and previous image into a separately verified recovery installation. An old image by itself is not sufficient proof of compatibility.

## 7. Common problems

| What you see | What to do |
|---|---|
| `can't open file ... deploy.py` | Run `dir deploy.py`; change into the extracted folder containing it. |
| Docker daemon unavailable | Start Docker Desktop, wait until ready, and verify Linux containers mode with `docker version`. |
| GHCR denied/unauthorized | Repeat `docker login ghcr.io -u YOUR_GITHUB_USERNAME`; check that this account/PAT can read the private image. |
| Port already in use on a fresh install | Choose a free port during `init`, such as `--port 8082`; do not change an unrelated stack. |
| Folder already contains files | For an existing installation use `up` or `upgrade`. For a genuinely new one choose an empty folder and unique project. |
| Another installation owns the project | Check `docker compose ls` and use the matching `ERP_DIR`; the guard is preserving someone else's resources. |
| Old MariaDB `Access denied` / incomplete site | Keep `.secrets` and all volumes. The new reader handles legacy CRLF without rotating the database password. Use the explicit recovery command below only for a failed, empty installation. |
| A standalone backup was interrupted before changing the image | Run `python deploy.py status --directory "%ERP_DIR%"`, then the reported `resume` recovery command; keep its backup/journal. |
| Upgrade fails after maintenance starts | Read the actionable stage error and keep its backup/journal. Use the supported rollback with that backup; do not initialize over the site or remove volumes. |
| Old colors remain after success | Use Ctrl+F5 and confirm `status` reports the new image. The asset bundle is baked into the image. |

For an incomplete initial setup with **no business data**, use:

```bat
python deploy.py recover --directory "%ERP_DIR%"
```

Recovery verifies that the partial database is absent or empty and that no user files/backups exist, then archives the incomplete site configuration and retries setup. It refuses an occupied database and never silently deletes a database or volume. Use the **new installer folder** for this command. It supplies the corrected recovery bootstrap even when the failed installation still selects the previous supported image. After recovery succeeds, use the normal `upgrade` command above to receive the new theme with a verified backup.

Do not hand-edit passwords, delete the database volume, or run a global Docker prune to fix an authentication error. Those actions are unnecessary for the corrected fresh-install path and may destroy a working installation.
