#!/usr/bin/env python3
"""Portable, scoped fresh-review installer for Linux and Windows Docker Desktop."""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import sys
import uuid

from common import run, valid_dependency, valid_image, valid_project, valid_site, write_json

HERE = Path(__file__).resolve().parent

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
    if directory.exists() and any(directory.iterdir()):
        raise ValueError('Deployment directory must be empty; existing installations are never overwritten.')
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    secret_dir = directory / '.secrets'
    secret_dir.mkdir(mode=0o700)
    for name in ('db-password', 'admin-password'):
        file = secret_dir / name
        file.write_text(secrets.token_urlsafe(36) + '\n', encoding='utf-8')
        file.chmod(0o600)
    shutil.copyfile(HERE / 'compose.yaml', directory / 'compose.yaml')
    state = dict(schema_version=1, installation_id=str(uuid.uuid4()), project=project,
                 site=site, port=int(port), image=image, mariadb_image=mariadb_image,
                 redis_image=redis_image, starter_data=bool(starter_data))
    write_json(directory / 'installation.json', state)
    values = dict(INSTALLATION_ID=state['installation_id'], COMPOSE_PROJECT_NAME=project,
                  IBTINEX_IMAGE=image, MARIADB_IMAGE=mariadb_image, REDIS_IMAGE=redis_image,
                  SITE_NAME=site, HTTP_PORT=port,
                  IBTINEX_STARTER_DATA='ethiopia-demo' if starter_data else 'none')
    (directory / '.env').write_text(''.join(f'{key}={value}\n' for key, value in values.items()),
                                  encoding='utf-8')
    (directory / '.gitignore').write_text('*\n', encoding='utf-8')
    return state

def compose(directory, *arguments, **kwargs):
    return run(['docker', 'compose', '--env-file', '.env', '-f', 'compose.yaml', *arguments],
               cwd=directory, **kwargs)

def verify_ownership(directory):
    state = json.loads((Path(directory) / 'installation.json').read_text())
    valid_project(state['project'])
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

def start(directory, *, skip_pull=False):
    directory = Path(directory).resolve()
    state = verify_ownership(directory)
    existing = compose(directory, 'ps', '-aq', 'frontend').strip()
    if not existing:
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1', state['port']))
            except OSError as error:
                raise RuntimeError('The selected local port is in use; no deployment was started.') from error
    compose(directory, 'config', '--quiet')
    if not skip_pull:
        compose(directory, '--profile', 'setup', 'pull', capture=False)
    compose(directory, 'up', '-d', '--wait', 'db', 'redis-cache', 'redis-queue', capture=False)
    compose(directory, '--profile', 'setup', 'run', '--rm', '-T', 'create-site', capture=False)
    compose(directory, 'up', '-d', '--wait', '--wait-timeout', '360', capture=False)
    return state

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    init = commands.add_parser('init', help='Prepare a new isolated deployment; starter data is opt-in')
    init.add_argument('--directory', required=True)
    init.add_argument('--release-manifest', help='Use the verified release-manifest.json from the installer bundle')
    init.add_argument('--image')
    init.add_argument('--mariadb-image')
    init.add_argument('--redis-image')
    init.add_argument('--project', default='ibtinex-erp-review')
    init.add_argument('--site', default='ibtinex.localhost')
    init.add_argument('--port', type=int, default=8081)
    init.add_argument('--starter-data', action='store_true')
    up = commands.add_parser('up', help='Install/start the prepared deployment')
    up.add_argument('--directory', required=True)
    args = vars(parser.parse_args())
    action = args.pop('action')
    directory = args.pop('directory')
    if action == 'init':
        manifest_path = args.pop('release_manifest')
        if manifest_path:
            manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
            if manifest.get('schema_version') != 1 or manifest.get('status') != 'verified-review-candidate':
                raise ValueError('The manifest is not a verified review candidate.')
            if manifest.get('platform') != 'linux/amd64' or manifest.get('package_visibility') != 'private':
                raise ValueError('Unexpected release platform or package visibility.')
            for argument, key in (('image', 'app'), ('mariadb_image', 'mariadb'), ('redis_image', 'redis')):
                selected = manifest['images'][key]
                if args[argument] and args[argument] != selected:
                    raise ValueError('A command-line image conflicts with the release manifest.')
                args[argument] = selected
        if not all(args.get(key) for key in ('image', 'mariadb_image', 'redis_image')):
            raise ValueError('Use --release-manifest, or provide all three exact image digests.')
        state = initialize(directory, **args)
    else:
        state = start(directory)
    print(json.dumps({'project': state['project'], 'url': f'http://localhost:{state["port"]}',
                      'starter_data': state['starter_data'],
                      'administrator_password_file': str(Path(directory).resolve() / '.secrets/admin-password')},
                     indent=2))

if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
