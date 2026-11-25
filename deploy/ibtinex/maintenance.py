"""Existing-site backup/theme maintenance, sent to container Python over stdin.

Nothing in this helper is a public Frappe method. All operations are local,
scoped by the installer, and require its verified Docker volume ownership.
"""
import contextlib
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import uuid

BENCH = Path('/home/frappe/frappe-bench')
TRANSIENT = ('maintenance_mode', 'pause_scheduler')
EXPECTED = {'erpnext_version': '16.60.0', 'frappe_version': '16.60.2'}


class MaintenanceError(RuntimeError):
    """Controlled, credential-free recovery instructions."""


def atomic_bytes(path, data):
    temporary = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex)
    try:
        temporary.write_bytes(data)
        temporary.chmod(0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_json(path, value):
    atomic_bytes(path, (json.dumps(value, sort_keys=True, indent=2) + '\n').encode())


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def directory_for(site, token):
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,120}[a-z0-9]', site) or '..' in site:
        raise ValueError('Invalid site name.')
    if not re.fullmatch(r'[0-9]{8}T[0-9]{6}Z-[a-f0-9]{12}', token):
        raise ValueError('Invalid backup operation identifier.')
    return BENCH / 'sites' / site / 'private' / '.ibtinex-upgrades' / token


def read_branding(frappe, fields, state_key):
    allowed = {'Website Settings.app_logo', 'Navbar Settings.app_logo', 'Website Settings.favicon',
               'Website Settings.splash_image', 'Website Settings.app_name', 'System Settings.app_name'}
    if not isinstance(fields, list) or not set(fields).issubset(allowed) or state_key != 'ibtinex_branding_v1':
        raise MaintenanceError('Unexpected branding scope; no database value was changed.')
    values = {}
    for key in fields:
        doctype, field = key.split('.', 1)
        if not frappe.get_meta(doctype).has_field(field):
            raise MaintenanceError('The existing site does not expose the expected branding fields.')
        values[key] = frappe.db.get_single_value(doctype, field, cache=False)
    return {'fields': values, 'state_key': state_key, 'state': frappe.db.get_default(state_key)}


def resume_config(config_path, snapshot):
    """Restore bytes exactly, unless a subsequent unrelated setting was edited."""
    original_bytes = (snapshot / 'site_config.original.json').read_bytes()
    original = json.loads(original_bytes)
    current = json.loads(config_path.read_bytes())
    expected = dict(original, maintenance_mode=1, pause_scheduler=1)
    if current == expected or current == original:
        atomic_bytes(config_path, original_bytes)
        return
    for key in TRANSIENT:
        if key in original:
            current[key] = original[key]
        else:
            current.pop(key, None)
    write_json(config_path, current)


def quiesce(frappe, config_path, snapshot, details):
    if snapshot.exists():
        raise MaintenanceError('The backup operation directory already exists.')
    if (frappe.get_system_settings('encrypt_backup') and
            not frappe.conf.get('backup_encryption_key')):
        raise MaintenanceError('Backup encryption is enabled but its key is not configured. '
                           'Complete native backup-encryption setup before upgrading.')
    snapshot.mkdir(parents=True, mode=0o700)
    original_bytes = config_path.read_bytes()
    original = json.loads(original_bytes)
    atomic_bytes(snapshot / 'site_config.original.json', original_bytes)
    values = read_branding(frappe, details['branding_fields'], details['branding_state_key'])
    write_json(snapshot / 'branding-before.json', values)
    try:
        write_json(config_path, dict(original, maintenance_mode=1, pause_scheduler=1))
        frappe.clear_cache()
    except BaseException:
        # The host has not received success yet; restore the original bytes here.
        atomic_bytes(config_path, original_bytes)
        raise
    return {'status': 'quiesced'}


def validate_native_backup(path, kind, *, encrypted=False, passphrase=None):
    temporary = None
    try:
        if encrypted:
            fd, filename = tempfile.mkstemp(prefix='ibtinex-backup-check-')
            os.close(fd)
            temporary = Path(filename)
            result = subprocess.run(['gpg', '--batch', '--yes', '--pinentry-mode', 'loopback',
                                     '--passphrase-fd', '0', '--output', str(temporary),
                                     '--decrypt', str(path)], input=passphrase + '\n',
                                    text=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            if result.returncode:
                raise MaintenanceError('Native encrypted backup failed decryption verification; upgrade stopped.')
            path = temporary
        if kind == 'database':
            count = 0
            found_schema = False
            with gzip.open(path, 'rb') as stream:
                previous = b''
                while chunk := stream.read(1024 * 1024):
                    count += len(chunk)
                    if b'CREATE TABLE' in previous + chunk:
                        found_schema = True
                    previous = chunk[-32:]
            if not count or not found_schema:
                raise MaintenanceError('The database backup does not contain a complete SQL schema.')
        elif kind in ('public', 'private'):
            with tarfile.open(path, 'r:*') as archive:
                for member in archive:
                    if member.isfile():
                        stream = archive.extractfile(member)
                        if stream:
                            while stream.read(1024 * 1024):
                                pass
        elif kind == 'config':
            if not isinstance(json.loads(Path(path).read_bytes()), dict):
                raise MaintenanceError('The site configuration backup is invalid.')
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def backup_site(frappe, snapshot):
    from frappe.utils.backups import BackupGenerator

    original = snapshot / 'site_config.original.json'
    if not original.is_file() or not (snapshot / 'branding-before.json').is_file():
        raise MaintenanceError('The original site snapshot is missing; upgrade stopped.')
    # Use the native generator directly, avoiding new_backup's pruning of unrelated
    # backups. ignore_conf=True prevents a customer partial-backup filter omitting data.
    backup = BackupGenerator(
        frappe.conf.db_name, frappe.conf.db_user, frappe.conf.db_password,
        db_socket=frappe.conf.db_socket, db_host=frappe.conf.db_host,
        db_port=frappe.conf.db_port, db_type=frappe.conf.db_type,
        backup_path=str(snapshot), ignore_conf=True, verbose=False)
    backup.get_backup(ignore_files=False, force=True)
    encrypted = bool(frappe.get_system_settings('encrypt_backup'))
    values = ((backup.backup_path_db, 'database'), (backup.backup_path_files, 'public'),
              (backup.backup_path_private_files, 'private'), (backup.backup_path_conf, 'config'),
              (original, 'original_config'), (snapshot / 'branding-before.json', 'branding'))
    files = {}
    for name, kind in values:
        path = Path(name).resolve()
        if path.parent != snapshot.resolve() or not path.is_file() or path.stat().st_size == 0:
            raise MaintenanceError('A required native backup file was not generated.')
        validate_native_backup(path, kind, encrypted=encrypted and kind in {'database', 'public', 'private'},
                               passphrase=frappe.conf.get('backup_encryption_key'))
        path.chmod(0o600)
        files[path.name] = {'kind': kind, 'size': path.stat().st_size, 'sha256': digest(path)}
    return {'container_directory': str(snapshot), 'files': files,
            'native_backup_verified': True, 'backup_encrypted': encrypted}


def apply_theme(frappe, snapshot):
    from erpnext import ibtinex_branding

    before = json.loads((snapshot / 'branding-before.json').read_text())
    if set(before['fields']) != set(ibtinex_branding._FIELDS):
        raise MaintenanceError('The theme settings differ from the protected pre-upgrade snapshot.')
    result = ibtinex_branding.apply()
    after = read_branding(frappe, sorted(ibtinex_branding._FIELDS), ibtinex_branding.STATE_KEY)
    write_json(snapshot / 'branding-after.json', after)
    frappe.db.commit()
    frappe.clear_cache()
    return {'status': 'branding-applied', 'result': result, 'schema_migrated': False}


def restore_branding(frappe, snapshot, details=None):
    before = json.loads((snapshot / 'branding-before.json').read_text())
    after_path = snapshot / 'branding-after.json'
    if not after_path.is_file():
        return {'restored': [], 'preserved': [], 'status': 'theme-not-applied'}
    after = json.loads(after_path.read_text())
    current = read_branding(frappe, sorted(before['fields']), before['state_key'])
    result = {'restored': [], 'preserved': []}
    next_state = before['state']
    if current['state'] != after['state']:
        next_state = current['state']
        if current['state']:
            try:
                changed_state = json.loads(current['state'])
                original_state = json.loads(before['state']) if before['state'] else {'managed': {}}
                if changed_state.get('version') != 1 or not isinstance(changed_state.get('managed'), dict):
                    raise ValueError
                supported = set((details or {}).get('rollback_fields', before['fields']))
                for key in list(changed_state['managed']):
                    if key not in supported:
                        del changed_state['managed'][key]
                    elif current['fields'].get(key) == after['fields'].get(key):
                        if key in original_state['managed']:
                            changed_state['managed'][key] = original_state['managed'][key]
                        else:
                            del changed_state['managed'][key]
                next_state = json.dumps(changed_state, sort_keys=True)
            except (ValueError, KeyError, TypeError):
                raise MaintenanceError('Branding ownership changed incompatibly; automatic rollback stopped.') from None
    for key, original in before['fields'].items():
        if current['fields'][key] != after['fields'][key]:
            result['preserved'].append(key)
            continue
        if current['fields'][key] != original:
            doctype, field = key.split('.', 1)
            frappe.db.set_single_value(doctype, field, original)
            result['restored'].append(key)
    if next_state != current['state']:
        # Older images understand only their original field set. Preserve applicable
        # intervening ownership while removing fields that runtime cannot parse.
        frappe.db.set_default(before['state_key'], next_state)
    frappe.db.commit()
    frappe.clear_cache()
    return result


def execute(site, action, token, details=None):
    snapshot = directory_for(site, token)
    config_path = BENCH / 'sites' / site / 'site_config.json'
    if not config_path.is_file():
        raise MaintenanceError('The existing site is missing. Maintenance never creates a new site.')
    os.chdir(BENCH / 'sites')
    import frappe
    import erpnext

    if frappe.__version__ != EXPECTED['frappe_version'] or erpnext.__version__ != EXPECTED['erpnext_version']:
        raise MaintenanceError('Application version does not match this visual-upgrade tool.')
    frappe.init(site=site, sites_path=str(BENCH / 'sites'))
    frappe.connect()
    frappe.set_user('Administrator')
    try:
        if set(frappe.get_installed_apps()) != {'frappe', 'erpnext'}:
            raise MaintenanceError('The site has a different application set; use a separately qualified upgrade.')
        if action == 'quiesce':
            return quiesce(frappe, config_path, snapshot, details)
        if action == 'backup':
            return backup_site(frappe, snapshot)
        if action == 'resume':
            resume_config(config_path, snapshot)
            frappe.clear_cache()
            return {'status': 'configuration-restored'}
        if action == 'apply':
            return apply_theme(frappe, snapshot)
        if action == 'rollback':
            return restore_branding(frappe, snapshot, details)
        raise ValueError('Unknown maintenance action.')
    except BaseException:
        frappe.db.rollback()
        raise
    finally:
        frappe.destroy()


def main():
    if len(sys.argv) not in {4, 5}:
        raise ValueError('Expected site, operation, backup identifier, and optional JSON details.')
    # Native backup helpers can print shell failures containing database credentials.
    # Suppress their output; expose only a sanitized operation error and JSON metadata.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        result = execute(*sys.argv[1:4], json.loads(sys.argv[4]) if len(sys.argv) == 5 else None)
    print(json.dumps(result, sort_keys=True, default=str))


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        # Never echo native exception text: it may contain a database command/password.
        if isinstance(error, MaintenanceError):
            print(str(error), file=sys.stderr)
        print(f'Existing-site maintenance failed during {sys.argv[2] if len(sys.argv) > 2 else "validation"} '
              f'({type(error).__name__}). Existing data was preserved; inspect the operation backup '
              'and use the documented recovery command.', file=sys.stderr)
        sys.exit(1)
