"""Fresh-site installer with byte-safe secrets and explicit empty-site recovery."""
from contextlib import contextmanager
import json
import os
import re
import subprocess
import sys
from pathlib import Path
import uuid

BENCH = Path('/home/frappe/frappe-bench')


class SetupError(RuntimeError):
    """An actionable installer message that contains no credentials."""


def secret_values(raw, *, database):
    """Mirror MariaDB's $(cat file), which removes LF but preserves a final CR.

    The old Windows writer emitted CRLF while Python read_text().strip() removed
    both characters. Trying the exact MariaDB bytes first supports existing DBs;
    a stripped fallback recognizes an earlier explicit administrator repair.
    Neither branch edits or rotates a password.
    """
    if b'\x00' in raw:
        raise SetupError('A password file contains a NUL byte; restore the original secret file.')
    try:
        value = raw.decode('utf-8')
    except UnicodeDecodeError:
        raise SetupError('A password file is not UTF-8; restore the original secret file.') from None
    candidates = [value.rstrip('\n'), value.strip()] if database else [value.strip()]
    candidates = list(dict.fromkeys(candidates))
    if any(len(item.strip()) < 24 for item in candidates):
        raise SetupError('Provisioned passwords must be at least 24 characters. '
                         'Do not regenerate secrets for a database that already exists.')
    return candidates


def root_password(candidates, connector):
    for candidate in candidates:
        try:
            connection = connector(host='db', port=3306, user='root', password=candidate,
                                   connect_timeout=15)
        except Exception as error:
            # Only authentication rejection permits trying the historical CRLF variant.
            if getattr(error, 'args', [None])[0] == 1045:
                continue
            raise SetupError('MariaDB is not reachable yet. Check Docker Desktop and this project\'s '
                             'db health, then repeat up; no site files were changed.') from None
        connection.close()
        return candidate
    raise SetupError('MariaDB rejected both the exact secret-file bytes and the legacy newline variant. '
                     'Restore the original .secrets/db-password for these existing database volumes. '
                     'Do not delete the volumes or generate a new password.')


def check_existing_site(config_path, connector):
    """Distinguish a working site from a partial one without using the root account."""
    if not config_path.is_file():
        return False
    try:
        config = json.loads(config_path.read_text(encoding='utf-8'))
        connection = connector(host='db', port=3306, user=config.get('db_user') or config['db_name'],
                               password=config['db_password'], database=config['db_name'],
                               connect_timeout=15)
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s',
                               (config['db_name'],))
                count = cursor.fetchone()[0]
        finally:
            connection.close()
        return bool(count)
    except Exception:
        return False


@contextmanager
def inactive_install_lock(site_path):
    """Use the exact FileLock primitive used by the pinned Frappe installer."""
    path = site_path / 'locks' / 'bench_new_site.lock'
    if site_path.is_symlink() or path.parent.is_symlink() or path.is_symlink():
        raise SetupError('The native installation lock path contains a symbolic link; recovery stopped.')
    if not path.exists():
        yield
        return
    if not path.is_file():
        raise SetupError('The native installation lock is not a regular file; recovery stopped.')
    # Frappe utils/synchronization.py uses filelock.FileLock on this exact path.
    # Do not unlink it: a retained file is normal, while a held lock means another
    # native installer is still active. Hold it throughout validation and archival.
    from filelock import FileLock, Timeout
    lock = FileLock(str(path), timeout=0)
    try:
        lock.acquire(timeout=0)
    except Timeout:
        raise SetupError('The native site installer is still holding its installation lock. '
                         'Wait for it to finish; no files or database were changed.') from None
    try:
        yield
    finally:
        lock.release()


def archive_empty_partial_site(site_path, password, connector):
    """Recover only a proven empty failed install; never drop a DB or delete files."""
    with inactive_install_lock(site_path):
        config_path = site_path / 'site_config.json'
        native_lock = site_path / 'locks' / 'bench_new_site.lock'
        config = {}
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text(encoding='utf-8'))
            except (ValueError, OSError):
                raise SetupError('The partial site configuration is unreadable. Existing files were '
                                 'preserved; recovery requires inspecting that configuration.') from None
        for path in site_path.rglob('*'):
            if path.is_symlink():
                raise SetupError('The partial site contains a symbolic link; automatic recovery stopped.')
            if (path.is_file() and path not in {config_path, native_lock}
                    and path.relative_to(site_path).parts[0] != 'logs'):
                raise SetupError('The partial site contains files beyond its configuration/logs/native '
                                 'installation lock. Recovery stopped to preserve possible customer data.')
        if config:
            name = config.get('db_name')
            if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_]+', name):
                raise SetupError('The partial site has an unrecognized database name; recovery stopped.')
            connection = connector(host='db', port=3306, user='root', password=password, connect_timeout=15)
            try:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s', (name,))
                    if cursor.fetchone()[0] != 0:
                        raise SetupError('This site database contains tables. Automatic recovery refuses '
                                         'to recreate it; use a verified backup or repair the existing site.')
            finally:
                connection.close()
        archive = site_path.parent / '.ibtinex-recovery' / uuid.uuid4().hex
        archive.mkdir(parents=True, mode=0o700)
        destination = archive / site_path.name
        site_path.rename(destination)
        # The old database, configuration, logs, and retained lock remain intact.
        return destination


def run(args, secret_list):
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = result.stdout or ''
    for secret in sorted(set(secret_list), key=len, reverse=True):
        if secret:
            output = output.replace(secret, '[REDACTED]')
    if result.returncode:
        print(output[-16000:], file=sys.stderr)
        raise SetupError('Site setup failed. No database volume was deleted. Repeat up if setup '
                         'can resume; for a proven empty partial site use deploy.py recover '
                         '--directory <the-existing-installation-directory>.')
    return output


def main():
    site = os.environ.get('SITE_NAME', '')
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,120}[a-z0-9]', site) or '..' in site:
        raise SetupError('A valid SITE_NAME is required.')
    starter = os.environ.get('IBTINEX_STARTER_DATA', 'none')
    if starter not in {'none', 'ethiopia-demo'}:
        raise SetupError('IBTINEX_STARTER_DATA must be none or ethiopia-demo.')
    database_passwords = secret_values(Path('/run/secrets/db_password').read_bytes(), database=True)
    administrator_password = secret_values(Path('/run/secrets/admin_password').read_bytes(), database=False)[0]
    redactions = [*database_passwords, administrator_password]
    if os.getuid() == 0:
        os.setgroups([])
        os.setgid(0)
        os.setuid(1000)
    os.chdir(BENCH)
    # Recovery may send this helper over stdin to the previous image.
    sys.path.insert(0, '/opt/ibtinex')
    import pymysql

    site_path = BENCH / 'sites' / site
    config_path = site_path / 'site_config.json'
    present = check_existing_site(config_path, pymysql.connect)
    created = not present
    recovery_archive = None
    if created:
        # Authenticate before bench new-site writes a partial site_config.json.
        password = root_password(database_passwords, pymysql.connect)
        if site_path.exists():
            if os.environ.get('IBTINEX_RECOVER_INCOMPLETE') != '1':
                raise SetupError('A site directory exists but its database is not ready. Run '
                                 'deploy.py recover --directory <existing-installation-directory>. '
                                 'Recovery will proceed only if the database and business files are empty.')
            recovery_archive = archive_empty_partial_site(site_path, password, pymysql.connect)
        run(['bench', 'new-site', '--db-root-username', 'root', '--db-root-password', password,
             '--admin-password', administrator_password, '--mariadb-user-host-login-scope', '%',
             '--install-app', 'erpnext', '--set-default', site], redactions)

    os.chdir(BENCH / 'sites')
    import frappe
    import erpnext
    from frappe.installer import update_site_config
    frappe.init(site=site, sites_path=str(BENCH / 'sites'))
    frappe.connect()
    frappe.set_user('Administrator')
    try:
        if frappe.__version__ != '16.60.2' or erpnext.__version__ != '16.60.0':
            raise SetupError('The application versions do not match this installer.')
        if set(frappe.get_installed_apps()) != {'frappe', 'erpnext'}:
            raise SetupError('Unexpected installed application set; refusing to change this site.')
        summary = {'site': site, 'created': created, 'erpnext': erpnext.__version__,
                   'frappe': frappe.__version__, 'starter_data': starter}
        if recovery_archive:
            summary['preserved_partial_site_directory'] = str(recovery_archive)
        from erpnext.ibtinex_branding import apply as apply_branding
        summary['branding'] = apply_branding()
        if starter == 'ethiopia-demo':
            from erpnext.ibtinex_starter.seed import install
            from erpnext.ibtinex_starter.plan import COMPANY, MARKER_KEY, SEED_VERSION
            from starter_state import completed_starter
            present_starter = completed_starter(frappe.db, marker_key=MARKER_KEY,
                                               seed_version=SEED_VERSION, company=COMPANY)
            if present_starter:
                summary['starter'] = present_starter
            else:
                if not created and not frappe.conf.get('ibtinex_starter_demo'):
                    raise SetupError('Starter data can only initialize a newly created review site.')
                if created:
                    for name in ('ibtinex_starter_demo', 'mute_emails', 'pause_scheduler'):
                        update_site_config(name, 1, site_config_path=str(config_path))
                        frappe.conf[name] = 1
                summary['starter'] = install(expected_site=site, accept_sample_data=True)
        frappe.db.commit()
        print(json.dumps(summary, default=str, sort_keys=True))
    except BaseException:
        frappe.db.rollback()
        raise
    finally:
        frappe.destroy()


if __name__ == '__main__':
    try:
        main()
    except SetupError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    except BaseException as error:
        print(f'Site setup failed ({type(error).__name__}). Existing data and credentials were preserved. '
              'Inspect this project with deploy.py status; do not delete its volumes.', file=sys.stderr)
        sys.exit(1)
