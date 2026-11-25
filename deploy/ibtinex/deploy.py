#!/usr/bin/env python3
"""Scoped IBTINEX ERP installer for Windows Docker Desktop and Linux."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import sys
import uuid

from common import run, valid_dependency, valid_image, valid_project, valid_site, write_json

HERE = Path(__file__).resolve().parent
PYTHON = '/home/frappe/frappe-bench/env/bin/python'
BENCH = '/home/frappe/frappe-bench'
RUNTIME_SERVICES = ('frontend', 'backend', 'websocket', 'queue-short', 'queue-long', 'scheduler')
VERSIONS = {'erpnext_version': '16.60.0', 'frappe_version': '16.60.2'}
ENV_KEYS = ('INSTALLATION_ID', 'COMPOSE_PROJECT_NAME', 'IBTINEX_IMAGE', 'MARIADB_IMAGE',
            'REDIS_IMAGE', 'SITE_NAME', 'HTTP_PORT', 'IBTINEX_STARTER_DATA')


def atomic_bytes(path, value, mode=0o600):
    """No platform newline translation, and no half-written configuration file."""
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex)
    try:
        with temporary.open('xb') as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_json(path, value):
    atomic_bytes(path, (json.dumps(value, sort_keys=True, indent=2) + '\n').encode())


def environment_values(state):
    return dict(INSTALLATION_ID=state['installation_id'], COMPOSE_PROJECT_NAME=state['project'],
                IBTINEX_IMAGE=state['image'], MARIADB_IMAGE=state['mariadb_image'],
                REDIS_IMAGE=state['redis_image'], SITE_NAME=state['site'],
                HTTP_PORT=str(state['port']),
                IBTINEX_STARTER_DATA='ethiopia-demo' if state['starter_data'] else 'none')


def initialize(directory, *, image, mariadb_image, redis_image, project, site,
               port, starter_data=False, ci=False):
    valid_image(image, ci=ci)
    valid_dependency(mariadb_image)
    valid_dependency(redis_image)
    valid_project(project)
    valid_site(site)
    if not 1024 <= int(port) <= 65535:
        raise ValueError('Use a local port from 1024 through 65535.')
    directory = Path(directory).resolve()
    wanted = dict(project=project, site=site, port=int(port), image=image,
                  mariadb_image=mariadb_image, redis_image=redis_image,
                  starter_data=bool(starter_data))
    if (directory / 'installation.json').is_file():
        state = load_state(directory)
        if any(state.get(key) != value for key, value in wanted.items()):
            raise ValueError('An installation already exists here with different settings. '
                             'Use status, up, or upgrade with that installation directory.')
        # Repeating init never rotates secrets or overwrites an existing project.
        return state
    if directory.exists() and any(directory.iterdir()):
        raise ValueError('Deployment directory must be empty. Existing files were preserved; '
                         'locate installation.json and use its directory with status/up.')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    secret_dir = directory / '.secrets'
    secret_dir.mkdir(mode=0o700)
    for name in ('db-password', 'admin-password'):
        # MariaDB's shell entrypoint strips LF, but not CR. Never use write_text
        # here: Windows would turn the old trailing LF into a password-bearing CRLF.
        atomic_bytes(secret_dir / name, secrets.token_urlsafe(36).encode('ascii'))
    shutil.copyfile(HERE / 'compose.yaml', directory / 'compose.yaml')
    state = dict(schema_version=1, installation_id=str(uuid.uuid4()), **wanted)
    atomic_json(directory / 'installation.json', state)
    atomic_bytes(directory / '.env', ''.join(f'{key}={value}\n'
                 for key, value in environment_values(state).items()).encode())
    atomic_bytes(directory / '.gitignore', b'*\n')
    return state


def load_state(directory):
    directory = Path(directory).resolve()
    try:
        state = json.loads((directory / 'installation.json').read_text(encoding='utf-8'))
        if state.get('schema_version') != 1:
            raise ValueError('Unsupported installation schema.')
        valid_project(state['project'])
        valid_site(state['site'])
        # Local CI images can be inspected here, but never supplied by the user CLI.
        valid_image(state['image'], ci=True)
        valid_dependency(state['mariadb_image'])
        valid_dependency(state['redis_image'])
        uuid.UUID(state['installation_id'])
        if not isinstance(state['starter_data'], bool) or not 1024 <= int(state['port']) <= 65535:
            raise ValueError('Invalid installation settings.')
        actual = {}
        for line in (directory / '.env').read_text(encoding='utf-8').splitlines():
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            key, separator, value = line.partition('=')
            if separator and key in ENV_KEYS:
                if key in actual:
                    raise ValueError('Duplicate deployment environment setting.')
                actual[key] = value
        if actual != environment_values(state):
            raise ValueError('installation.json and .env disagree. Restore their matching copies; '
                             'no container or credential was changed.')
        for name in ('db-password', 'admin-password'):
            raw = (directory / '.secrets' / name).read_bytes()
            if len(raw.rstrip(b'\r\n')) < 24 or b'\x00' in raw:
                raise ValueError('A required password file is missing or invalid. Restore its original '
                                 'copy; do not regenerate passwords for an existing database.')
        if not (directory / 'compose.yaml').is_file():
            raise ValueError('The installation compose.yaml is missing.')
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError('Could not read a complete installation. Use the directory containing '
                         'installation.json, .env, compose.yaml, and .secrets.') from error
    return state


def compose(directory, *arguments, **kwargs):
    directory = Path(directory).resolve()
    state = load_state(directory)
    # An unrelated shell COMPOSE_PROJECT_NAME/IBTINEX_IMAGE must not redirect an operation.
    env = {key: value for key, value in os.environ.items()
           if key not in {'COMPOSE_FILE', 'COMPOSE_PROFILES', 'COMPOSE_ENV_FILES'}}
    env.update(kwargs.pop('env', {}) or {})
    env.update(environment_values(state))
    return run(['docker', 'compose', '--project-name', state['project'],
                '--env-file', '.env', '-f', 'compose.yaml', *arguments],
               cwd=directory, env=env, **kwargs)


def verify_ownership(directory):
    state = load_state(directory)
    expected = state['installation_id']
    for kind, listing in (
        ('container', ['docker', 'ps', '-aq']),
        ('volume', ['docker', 'volume', 'ls', '-q']),
        ('network', ['docker', 'network', 'ls', '-q']),
    ):
        ids = run([*listing, '--filter', f'label=com.docker.compose.project={state["project"]}']).split()
        if not ids:
            continue
        objects = json.loads(run(['docker', kind, 'inspect', *ids]))
        for item in objects:
            labels = item.get('Labels') or item.get('Config', {}).get('Labels') or {}
            if labels.get('com.ibtinex.installation') != expected:
                raise RuntimeError(f'The Compose project has a {kind} owned by another installation; stopped.')
    return state


@contextmanager
def operation_lock(directory):
    path = Path(directory) / '.operation.lock'
    try:
        with path.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump({'pid': os.getpid(), 'started_utc': datetime.now(timezone.utc).isoformat()}, stream)
    except FileExistsError:
        raise RuntimeError('Another installer operation holds .operation.lock. If a previous process '
                           'crashed, confirm it has stopped, then remove only this lock file and retry.') from None
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def start(directory, *, skip_pull=False, recover=False):
    directory = Path(directory).resolve()
    state = verify_ownership(directory)
    if any((directory / name).exists() for name in
           ('pending-upgrade.json', 'pending-rollback.json', 'active-maintenance.json')):
        raise RuntimeError('An interrupted operation is recorded. Use status, then rollback for an '
                           'upgrade/rollback or resume for a backup, before restarting.')
    existing = compose(directory, 'ps', '-aq', 'frontend').strip()
    if not existing:
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1', int(state['port'])))
            except OSError as error:
                raise RuntimeError('The selected local port is in use; no deployment was started.') from error
    compose(directory, 'config', '--quiet')
    if not skip_pull:
        print('Pulling the exact installation images...', flush=True)
        compose(directory, '--profile', 'setup', 'pull')
    compose(directory, 'up', '-d', '--wait', 'db', 'redis-cache', 'redis-queue')
    setup = ['--profile', 'setup', 'run', '--rm', '-T']
    if recover:
        setup += ['-e', 'IBTINEX_RECOVER_INCOMPLETE=1', '--entrypoint', PYTHON]
        # Run the fixed helper against the SAME existing image, including 0.1.0.
        # This repairs only a proven empty partial site before the normal backed-up
        # upgrade; no blind image switch or schema migration is necessary.
        script = (HERE / 'container' / 'bootstrap.py').read_text(encoding='utf-8')
        compose(directory, *setup, 'create-site', '-', input=script)
    else:
        compose(directory, *setup, 'create-site')
    compose(directory, 'up', '-d', '--wait', '--wait-timeout', '360')
    return state


def stop(directory):
    state = verify_ownership(directory)
    compose(directory, 'stop', '--timeout', '60')
    return state


def status(directory):
    directory = Path(directory).resolve()
    state = verify_ownership(directory)
    output = {**state, 'directory': str(directory),
              'containers': compose(directory, 'ps', '--format', 'json'),
              'legacy_crlf_secret_files': [name for name in ('db-password', 'admin-password')
                   if b'\r' in (directory / '.secrets' / name).read_bytes()],
              'operation_locked': (directory / '.operation.lock').exists()}
    for name in ('pending-upgrade', 'pending-rollback', 'active-maintenance'):
        if (directory / (name + '.json')).exists():
            pending = json.loads((directory / (name + '.json')).read_text())
            output[name] = {key: pending.get(key) for key in
                           ('stage', 'backup_directory', 'from_image', 'to_image')}
    return output


def release_manifest(value, *, ci=False):
    manifest = value if isinstance(value, dict) else json.loads(Path(value).read_text(encoding='utf-8'))
    if manifest.get('schema_version') != 1 or manifest.get('status') != 'verified-review-candidate':
        raise ValueError('The manifest is not a verified review candidate.')
    if manifest.get('platform') != 'linux/amd64' or manifest.get('package_visibility') != 'private':
        raise ValueError('Unexpected release platform or package visibility.')
    images = manifest.get('images', {})
    valid_image(images.get('app', ''), ci=ci)
    valid_dependency(images.get('mariadb', ''))
    valid_dependency(images.get('redis', ''))
    if not re.fullmatch('[a-f0-9]{40}', manifest.get('source_commit', '')):
        raise ValueError('The release source commit is missing or invalid.')
    return manifest


def image_metadata(image, *, ci=False, pull=True):
    valid_image(image, ci=ci)
    if pull:
        run(['docker', 'pull', '--platform', 'linux/amd64', image])
    script = '''import json, frappe, erpnext
from pathlib import Path
from erpnext import ibtinex_branding as branding
release = json.loads(Path('/opt/ibtinex/release.json').read_text())
release.update(erpnext_version=erpnext.__version__, frappe_version=frappe.__version__,
               branding_fields=sorted(branding._FIELDS), branding_state_key=branding.STATE_KEY)
print(json.dumps(release, sort_keys=True))
'''
    raw = run(['docker', 'run', '--rm', '-i', '--platform', 'linux/amd64',
               '--entrypoint', PYTHON, image, '-'], input=script)
    return json_result(raw)


def json_result(raw):
    try:
        return json.loads(next(line for line in reversed(raw.splitlines()) if line.startswith('{')))
    except (StopIteration, ValueError) as error:
        raise RuntimeError('The container did not return a valid operation result.') from error


def maintenance(directory, action, token, *, details=None):
    state = load_state(directory)
    script = (HERE / 'maintenance.py').read_text(encoding='utf-8')
    args = ['run', '--rm', '--no-deps', '-T', '--entrypoint', PYTHON,
            'backend', '-', state['site'], action, token]
    if details is not None:
        args.append(json.dumps(details, sort_keys=True))
    return json_result(compose(directory, *args, input=script))


def _digest(path):
    checksum = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def verify_backup(directory):
    directory = Path(directory).resolve()
    try:
        record = json.loads((directory / 'backup.json').read_text(encoding='utf-8'))
        for filename, item in record['files'].items():
            if Path(filename).name != filename or filename in {'.', '..'}:
                raise ValueError('Invalid backup filename.')
            path = directory / filename
            if path.is_symlink() or not path.is_file() or path.stat().st_size != item['size']:
                raise ValueError('A required backup file is missing or has changed.')
            if _digest(path) != item['sha256']:
                raise ValueError('A backup checksum does not match.')
        required = {'database', 'public', 'private', 'config', 'original_config', 'branding'}
        if not required.issubset({item['kind'] for item in record['files'].values()}):
            raise ValueError('The backup is incomplete.')
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError('Could not verify the complete backup; no application image was changed.') from error
    return record


def _backup(directory, *, target=None, leave_stopped=False):
    """Quiesce, copy every native backup out of Docker, verify bytes, then resume."""
    directory = Path(directory).resolve()
    state = verify_ownership(directory)
    active = directory / 'active-maintenance.json'
    if active.exists():
        raise RuntimeError('A previous backup needs resume before another operation can start.')
    token = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:12]
    destination = directory / 'backups' / token
    destination.mkdir(parents=True, mode=0o700)
    current_metadata = image_metadata(state['image'], ci=True, pull=False)
    target_metadata = target or current_metadata
    details = {'branding_fields': target_metadata['branding_fields'],
               'branding_state_key': target_metadata['branding_state_key']}
    snapshot_created = False
    services_stopped = False
    atomic_json(active, {'token': token, 'stage': 'snapshot-started', 'from_image': state['image'],
                         'backup_directory': str(destination)})
    try:
        maintenance(directory, 'quiesce', token, details=details)
        snapshot_created = True
        atomic_json(active, {'token': token, 'stage': 'quiesced', 'from_image': state['image'],
                             'backup_directory': str(destination)})
        compose(directory, 'stop', '--timeout', '60', *RUNTIME_SERVICES)
        services_stopped = True
        payload = maintenance(directory, 'backup', token)
        # A stopped backend still exists, and cp reads the persisted named volume.
        compose(directory, 'cp', f'backend:{payload["container_directory"]}/.', str(destination))
        for path in destination.iterdir():
            if path.is_file():
                path.chmod(0o600)
        record = {'schema_version': 1, 'token': token, 'installation_id': state['installation_id'],
                  'site': state['site'], 'project': state['project'], 'image': state['image'],
                  'runtime': current_metadata, 'files': payload['files'],
                  'native_backup_verified': payload['native_backup_verified'],
                  'backup_encrypted': payload['backup_encrypted']}
        atomic_json(destination / 'backup.json', record)
        for name in ('installation.json', '.env', 'compose.yaml'):
            atomic_bytes(destination / ('previous-' + name.lstrip('.')), (directory / name).read_bytes())
        # Root credentials are never logged. Preserve their exact bytes in the private
        # backup so a full recovery does not depend on recreating a password.
        for name in ('db-password', 'admin-password'):
            atomic_bytes(destination / ('previous-' + name), (directory / '.secrets' / name).read_bytes())
        for path in destination.iterdir():
            if path.name.startswith('previous-'):
                record['files'][path.name] = {'kind': 'deployment', 'size': path.stat().st_size,
                                             'sha256': _digest(path)}
        atomic_json(destination / 'backup.json', record)
        verify_backup(destination)
        if not leave_stopped:
            maintenance(directory, 'resume', token)
            compose(directory, 'up', '-d', '--no-deps', '--wait', '--wait-timeout', '360', *RUNTIME_SERVICES)
            active.unlink(missing_ok=True)
        return {**state, 'backup_directory': str(destination), 'backup_token': token,
                'operation': 'backup', 'backup_verified': True}
    except Exception:
        # Before changing the image, restoring the exact original configuration is safe.
        if snapshot_created:
            maintenance(directory, 'resume', token)
        if services_stopped:
            compose(directory, 'up', '-d', '--no-deps', '--wait', '--wait-timeout', '360', *RUNTIME_SERVICES)
        active.unlink(missing_ok=True)
        raise


def backup(directory):
    with operation_lock(directory):
        return _backup(directory)


def validate_upgrade(state, manifest, *, ci=False):
    manifest = release_manifest(manifest, ci=ci)
    policy = manifest.get('upgrade', {})
    if policy.get('kind') != 'appearance-only' or policy.get('schema_changed') is not False:
        raise ValueError('Only an explicitly qualified appearance-only release can use this upgrade command.')
    if policy.get('rollback_compatible') is not True or state['image'] not in policy.get('from_images', []):
        raise ValueError('This exact installed image has no verified upgrade/rollback path in the release manifest.')
    if any(manifest.get(key) != version for key, version in VERSIONS.items()):
        raise ValueError('This upgrade command does not migrate ERPNext or Frappe versions.')
    if (manifest['images']['mariadb'] != state['mariadb_image'] or
            manifest['images']['redis'] != state['redis_image']):
        raise ValueError('Database/Redis image changes require a separately qualified migration.')
    return manifest


def _set_image(directory, image):
    directory = Path(directory)
    state = load_state(directory)
    env = (directory / '.env').read_bytes()
    replaced = re.sub(rb'(?m)^IBTINEX_IMAGE=[^\r\n]*', ('IBTINEX_IMAGE=' + image).encode(), env, count=1)
    # A journal exists before this pair is updated, so interruption is recoverable
    # from the byte-exact previous copies without touching database volumes.
    state['image'] = image
    atomic_bytes(directory / '.env', replaced)
    atomic_json(directory / 'installation.json', state)
    return state


def upgrade(directory, manifest, *, ci=False):
    directory = Path(directory).resolve()
    with operation_lock(directory):
        state = verify_ownership(directory)
        manifest = release_manifest(manifest, ci=ci)
        if any((directory / name).exists() for name in
               ('pending-upgrade.json', 'pending-rollback.json', 'active-maintenance.json')):
            raise RuntimeError('An interrupted operation exists. Use status and its recovery command first.')
        if state['image'] == manifest['images']['app']:
            return {**state, 'operation': 'already-current'}
        manifest = validate_upgrade(state, manifest, ci=ci)
        target = image_metadata(manifest['images']['app'], ci=ci, pull=not ci)
        if any(target.get(key) != manifest.get(key) for key in (*VERSIONS, 'source_commit')):
            raise ValueError('The candidate image source or application versions do not match the manifest.')
        current = image_metadata(state['image'], ci=ci, pull=False)
        if any(current.get(key) != version for key, version in VERSIONS.items()):
            raise ValueError('The existing runtime does not match the qualified application versions.')
        print('Backing up the database, files, settings, and exact deployment configuration...', flush=True)
        saved = _backup(directory, target=target, leave_stopped=True)
        destination = Path(saved['backup_directory'])
        journal = {'schema_version': 1, 'stage': 'backup-verified',
                   'installation_id': state['installation_id'], 'token': saved['backup_token'],
                   'backup_directory': str(destination), 'from_image': state['image'],
                   'to_image': manifest['images']['app'], 'manifest': manifest}
        atomic_json(destination / 'upgrade.json', journal)
        atomic_json(directory / 'pending-upgrade.json', journal)
        (directory / 'active-maintenance.json').unlink(missing_ok=True)
        try:
            _set_image(directory, journal['to_image'])
            journal['stage'] = 'image-selected'
            atomic_json(directory / 'pending-upgrade.json', journal)
            # No new-site, migrate, schema update, or starter-data operation is used.
            result = maintenance(directory, 'apply', journal['token'])
            journal['branding_result'] = result
            journal['stage'] = 'branding-applied'
            atomic_json(directory / 'pending-upgrade.json', journal)
            maintenance(directory, 'resume', journal['token'])
            compose(directory, 'up', '-d', '--no-deps', '--force-recreate', '--wait',
                    '--wait-timeout', '360', *RUNTIME_SERVICES)
            journal['stage'] = 'completed'
            atomic_json(destination / 'upgrade.json', journal)
            atomic_json(directory / 'release-manifest.json', manifest)
            (directory / 'pending-upgrade.json').unlink()
            return {**load_state(directory), 'operation': 'upgrade',
                    'backup_directory': str(destination), 'backup_verified': True}
        except Exception as error:
            # Stop the target before inviting recovery. Do not silently switch images
            # after an unknown failure, or restore a DB over new business activity.
            try:
                compose(directory, 'stop', '--timeout', '60', *RUNTIME_SERVICES)
            except Exception:
                pass  # Preserve recovery guidance even if deployment-file writes were interrupted.
            raise RuntimeError('Upgrade stopped safely. Database volumes and the verified backup are intact. '
                               f'Use rollback --directory "{directory}" --backup-directory "{destination}". '
                               f'Underlying error: {error}') from error


def resume(directory):
    """Recover downtime from an interrupted backup before any image was changed."""
    directory = Path(directory).resolve()
    with operation_lock(directory):
        state = verify_ownership(directory)
        if any((directory / name).exists() for name in ('pending-upgrade.json', 'pending-rollback.json')):
            raise RuntimeError('Use rollback for this recorded image transition.')
        active = json.loads((directory / 'active-maintenance.json').read_text(encoding='utf-8'))
        if active['from_image'] != state['image']:
            raise ValueError('The image changed after the backup; automatic resume refused.')
        maintenance(directory, 'resume', active['token'])
        compose(directory, 'up', '-d', '--no-deps', '--wait', '--wait-timeout', '360', *RUNTIME_SERVICES)
        (directory / 'active-maintenance.json').unlink()
        return {**state, 'operation': 'resumed'}


def rollback(directory, backup_directory, *, ci=False):
    directory = Path(directory).resolve()
    destination = Path(backup_directory).resolve()
    with operation_lock(directory):
        record = verify_backup(destination)
        journal = json.loads((destination / 'upgrade.json').read_text(encoding='utf-8'))
        previous = json.loads((destination / 'previous-installation.json').read_text(encoding='utf-8'))
        if previous['installation_id'] != record['installation_id'] or journal['installation_id'] != record['installation_id']:
            raise ValueError('Backup ownership does not match the recorded upgrade.')
        actual = json.loads((directory / 'installation.json').read_text(encoding='utf-8'))
        if actual.get('installation_id') != record['installation_id']:
            raise ValueError('This backup belongs to another installation.')
        if {**actual, 'image': previous['image']} != previous:
            raise ValueError('Installation settings changed since this upgrade; automatic rollback refused.')
        if actual.get('image') not in {journal['from_image'], journal['to_image']}:
            raise ValueError('The current image is outside this recorded upgrade pair; automatic rollback refused.')
        manifest = validate_upgrade(previous, journal['manifest'], ci=ci)
        if manifest['images']['app'] != journal['to_image'] or previous['image'] != journal['from_image']:
            raise ValueError('The rollback image pair does not match the qualified manifest.')
        original_env = (destination / 'previous-env').read_bytes()
        target_env = re.sub(rb'(?m)^IBTINEX_IMAGE=[^\r\n]*',
                            ('IBTINEX_IMAGE=' + journal['to_image']).encode(), original_env, count=1)
        if (directory / '.env').read_bytes() not in {original_env, target_env}:
            raise ValueError('Deployment environment settings changed since this backup; preserve/reconcile those changes before rollback.')
        if (directory / 'compose.yaml').read_bytes() != (destination / 'previous-compose.yaml').read_bytes():
            raise ValueError('Compose configuration changed since this backup; automatic rollback refused.')
        for name in ('db-password', 'admin-password'):
            if (directory / '.secrets' / name).read_bytes() != (destination / ('previous-' + name)).read_bytes():
                raise ValueError('Passwords changed since this backup; no secrets were overwritten.')
        try:
            load_state(directory)
        except ValueError:
            pending_path = next((directory / name for name in ('pending-upgrade.json', 'pending-rollback.json')
                                 if (directory / name).is_file()), None)
            pending = json.loads(pending_path.read_text()) if pending_path else {}
            if pending.get('token') != journal['token']:
                raise ValueError('Deployment configuration differs from the pending upgrade.') from None
            atomic_bytes(directory / '.env', original_env if actual['image'] == journal['from_image'] else target_env)
        verify_ownership(directory)
        # Download and validate the rollback image before introducing any downtime.
        target = image_metadata(journal['from_image'], ci=ci, pull=not ci)
        if any(target.get(key) != version for key, version in VERSIONS.items()):
            raise ValueError('The rollback image does not match the qualified application versions.')
        pending_path = directory / 'pending-rollback.json'
        if pending_path.exists():
            pending = json.loads(pending_path.read_text())
            if pending.get('token') != journal['token']:
                raise ValueError('A different rollback is already pending.')
            resume_token = pending['resume_token']
        else:
            resume_token = journal['token']
            if journal.get('stage') == 'completed' and actual['image'] == journal['to_image']:
                safety_backup = _backup(directory, leave_stopped=True)
                resume_token = safety_backup['backup_token']
            pending = {'token': journal['token'], 'resume_token': resume_token, 'stage': 'prepared',
                       'backup_directory': str(destination), 'from_image': journal['to_image'],
                       'to_image': journal['from_image']}
            atomic_json(pending_path, pending)
            (directory / 'active-maintenance.json').unlink(missing_ok=True)
        try:
            compose(directory, 'stop', '--timeout', '60', *RUNTIME_SERVICES)
            result = maintenance(directory, 'rollback', journal['token'],
                                 details={'rollback_fields': target['branding_fields']})
            atomic_bytes(directory / '.env', original_env)
            atomic_bytes(directory / 'installation.json', (destination / 'previous-installation.json').read_bytes())
            pending['stage'] = 'previous-image-selected'
            atomic_json(pending_path, pending)
            maintenance(directory, 'resume', resume_token)
            compose(directory, 'up', '-d', '--no-deps', '--force-recreate', '--wait',
                    '--wait-timeout', '360', *RUNTIME_SERVICES)
            (directory / 'pending-upgrade.json').unlink(missing_ok=True)
            pending_path.unlink()
            journal['stage'] = 'rolled-back'
            atomic_json(destination / 'upgrade.json', journal)
            return {**load_state(directory), 'operation': 'rollback', 'backup_directory': str(destination),
                    'business_data_restored': False, 'branding_result': result}
        except Exception as error:
            raise RuntimeError('Rollback is recorded and can be retried with the same --backup-directory. '
                               'Business data was not restored or deleted. ' + str(error)) from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    init = commands.add_parser('init', help='Prepare an isolated installation; starter data is opt-in')
    init.add_argument('--directory', required=True)
    init.add_argument('--release-manifest')
    init.add_argument('--image')
    init.add_argument('--mariadb-image')
    init.add_argument('--redis-image')
    init.add_argument('--project', default='ibtinex-erp-review')
    init.add_argument('--site', default='ibtinex.localhost')
    init.add_argument('--port', type=int, default=8081)
    init.add_argument('--starter-data', action='store_true')
    for action, help_text in (
        ('up', 'Install/start this deployment, preserving existing data'),
        ('recover', 'Recover only a proven empty, incomplete site; never delete a database'),
        ('stop', 'Stop this deployment without deleting containers or volumes'),
        ('status', 'Show the actual installation directory, project, images, port, and containers'),
        ('backup', 'Create and verify a full private backup, then restart'),
        ('resume', 'Resume after an interrupted backup before an image transition'),
        ('upgrade', 'Back up and apply an explicitly qualified appearance-only release'),
        ('rollback', 'Restore a verified compatible image and its owned branding settings'),
    ):
        command = commands.add_parser(action, help=help_text)
        command.add_argument('--directory', required=True)
        if action == 'upgrade':
            command.add_argument('--release-manifest', required=True)
        if action == 'rollback':
            command.add_argument('--backup-directory', required=True)
    args = vars(parser.parse_args())
    action = args.pop('action')
    directory = Path(args.pop('directory')).resolve()
    if action == 'init':
        path = args.pop('release_manifest')
        manifest = release_manifest(path) if path else None
        if manifest:
            for argument, key in (('image', 'app'), ('mariadb_image', 'mariadb'), ('redis_image', 'redis')):
                selected = manifest['images'][key]
                if args[argument] and args[argument] != selected:
                    raise ValueError('A command-line image conflicts with the release manifest.')
                args[argument] = selected
        if not all(args.get(key) for key in ('image', 'mariadb_image', 'redis_image')):
            raise ValueError('Use --release-manifest, or provide all three exact image digests.')
        state = initialize(directory, **args)
        if manifest:
            atomic_json(directory / 'release-manifest.json', manifest)
    elif action == 'upgrade':
        state = upgrade(directory, args['release_manifest'])
    elif action == 'rollback':
        state = rollback(directory, args['backup_directory'])
    elif action == 'backup':
        state = backup(directory)
    elif action == 'resume':
        state = resume(directory)
    elif action == 'status':
        state = status(directory)
    else:
        with operation_lock(directory):
            state = stop(directory) if action == 'stop' else start(directory, recover=action == 'recover')
    result = {key: value for key, value in state.items() if key not in {'installation_id'}}
    result.update(directory=str(directory), url=f'http://localhost:{state["port"]}',
                  administrator_password_file=str(directory / '.secrets' / 'admin-password'))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, KeyError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
