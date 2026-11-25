#!/usr/bin/env python3
"""Build inputs and real, isolated qualification before publishing a review image."""
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from common import IMAGE_REPOSITORY, redact, run, write_json
from deploy import compose, initialize, start, verify_ownership

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
TEMP = Path(os.environ.get('RUNNER_TEMP', '/tmp/ibtinex-ci')).resolve()
EVIDENCE = TEMP / 'ibtinex-evidence'
CONTEXT = TEMP / 'ibtinex-build'
STATE = TEMP / 'ibtinex-state.json'
FRAPPE_COMMIT = '2df0425571ebbaed878eabc3edc5b7e7c3327ae0'
DOCKER_COMMIT = 'cf568a829790ef658d232daa75457dadf4e1ecc9'

def output(name, value):
    if '\n' in str(value):
        raise ValueError('Unexpected newline in workflow output.')
    if path := os.environ.get('GITHUB_OUTPUT'):
        with open(path, 'a') as stream:
            stream.write(f'{name}={value}\n')

def pull_digest(image):
    run(['docker', 'pull', '--platform', 'linux/amd64', image], capture=False)
    digests = json.loads(run(['docker', 'image', 'inspect', '--format', '{{json .RepoDigests}}', image]))
    if not digests or not re.fullmatch(r'.+@sha256:[0-9a-f]{64}', digests[0]):
        raise RuntimeError('Docker did not resolve an immutable dependency digest.')
    return digests[0]

def fetch_json(url, token=None):
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'IBTINEX-release'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=90) as response:
        return json.load(response)

def prepare():
    if os.environ.get('GITHUB_REPOSITORY') != 'zernova-platform/erpnext':
        raise RuntimeError('This pipeline is scoped to the organization ERP fork.')
    commit = run(['git', 'rev-parse', 'HEAD'], cwd=ROOT).strip()
    if commit != os.environ['GITHUB_SHA']:
        raise RuntimeError('Checked-out commit does not match the workflow event.')
    branch = os.environ['GITHUB_REF_NAME']
    if branch != 'ibtinex/starter-0.1.0':
        raise RuntimeError('Only the explicitly qualified candidate branch can publish.')
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if CONTEXT.exists():
        shutil.rmtree(CONTEXT)
    shutil.copytree(HERE, CONTEXT, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'tests'))
    versions = fetch_json('https://nodejs.org/dist/index.json')
    node = next(row['version'].removeprefix('v') for row in versions
                if row['version'].startswith('v24.') and row.get('lts'))
    if not re.fullmatch(r'24\.\d+\.\d+', node):
        raise RuntimeError('Could not resolve Node 24 LTS.')
    inputs = {'distribution_version': '0.1.0-rc.1', 'source_commit': commit,
              'source_repository': 'https://github.com/zernova-platform/erpnext',
              'source_branch': branch, 'erpnext_version': '16.60.0',
              'frappe_version': '16.60.2', 'frappe_commit': FRAPPE_COMMIT,
              'frappe_docker_reference': DOCKER_COMMIT, 'bench_version': '5.31.1',
              'node_version': node, 'platform': 'linux/amd64',
              'python_base_image': pull_digest('python:3.14-slim-trixie'),
              'mariadb_image': pull_digest('mariadb:11.8'),
              'redis_image': pull_digest('redis:8.6-alpine')}
    write_json(CONTEXT / 'release.json', inputs)
    write_json(EVIDENCE / 'build-inputs.json', inputs)
    write_json(STATE, inputs)
    write_json(TEMP / 'ibtinex-apps.json', [
        {'url': 'https://github.com/zernova-platform/erpnext.git', 'branch': branch}])
    with (EVIDENCE / 'erpnext-corresponding-source.tar.gz').open('wb') as archive:
        result = subprocess.run(['git', 'archive', '--format=tar.gz', '--prefix=erpnext/', commit],
                                cwd=ROOT, stdout=archive, stderr=subprocess.PIPE)
        if result.returncode:
            raise RuntimeError('Could not archive the candidate source.')
    framework_source = EVIDENCE / 'frappe-corresponding-source.tar.gz'
    with urllib.request.urlopen(f'https://codeload.github.com/frappe/frappe/tar.gz/{FRAPPE_COMMIT}',
                                timeout=120) as remote, framework_source.open('wb') as archive:
        shutil.copyfileobj(remote, archive)
    output('python_base_image', inputs['python_base_image'])
    output('node_version', node)
    print('Exact source, dependency image digests and source archives prepared.', flush=True)

def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]

def qualify(directory, site, mode):
    command = ['/home/frappe/frappe-bench/env/bin/python', '/opt/ibtinex/qualify.py',
               '--site', site, '--mode', mode]
    raw = compose(directory, 'run', '--rm', '--no-deps', '-T', '--entrypoint', command[0],
                  'backend', *command[1:])
    # Compose progress is on stderr; function output is the final JSON line.
    payload = json.loads(next(line for line in reversed(raw.splitlines()) if line.startswith('{')))
    write_json(EVIDENCE / f'{mode}-verification.json', payload)
    return payload

def assert_ready_desk(html, final_url):
    # Frappe 16.60.2 routes /desk to www/desk.py and embeds a JSON object
    # directly in `frappe.boot = ...` (www/desk.html). Never evaluate page JS.
    assert urllib.parse.urlsplit(final_url).path.rstrip('/') == '/desk', 'Desk redirected away from its native route.'
    match = re.search(r'frappe\.boot\s*=\s*', html)
    assert match, 'The authenticated Desk did not return its native boot payload.'
    boot, _ = json.JSONDecoder().raw_decode(html[match.end():])
    assert boot.get('sysdefaults', {}).get('setup_complete') in (1, True), 'Desk still requires setup.'
    assert not boot.get('setup_wizard_url'), 'Desk boot still advertises a setup-wizard redirect.'
    return {'native_route': '/desk', 'setup_complete': True, 'setup_wizard_redirect': False}

def http_checks(port, admin_password):
    base = f'http://127.0.0.1:{port}'
    result = {}
    for file in ('ibtinex-logo.svg', 'ibtinex-favicon.svg'):
        with urllib.request.urlopen(f'{base}/assets/erpnext/images/{file}', timeout=20) as response:
            actual = response.read()
        expected = (ROOT / 'erpnext/public/images' / file).read_bytes()
        if hashlib.sha256(actual).digest() != hashlib.sha256(expected).digest():
            raise AssertionError('Served IBTINEX artwork does not match the candidate source.')
        result[file] = hashlib.sha256(actual).hexdigest()
    with urllib.request.urlopen(f'{base}/login', timeout=30) as response:
        html = response.read().decode()
        assert 'ibtinex-logo.svg' in html and 'ibtinex-favicon.svg' in html
    result['login_displays_packaged_artwork'] = True
    try:
        urllib.request.urlopen(f'{base}/api/resource/Company', timeout=20)
    except urllib.error.HTTPError as error:
        assert error.code in (401, 403), 'Unexpected anonymous API response.'
    else:
        raise AssertionError('Anonymous Company access unexpectedly succeeded.')
    result['anonymous_company_access_denied'] = True
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    payload = urllib.parse.urlencode({'usr': 'Administrator', 'pwd': admin_password}).encode()
    with opener.open(f'{base}/api/method/login', payload, timeout=30) as response:
        assert json.load(response).get('message') == 'Logged In'
    with opener.open(f'{base}/api/resource/Company', timeout=20) as response:
        companies = json.load(response)['data']
    assert any(row['name'] == 'IBTINEX Starter Ethiopia' for row in companies)
    result['authenticated_native_company_api'] = True
    with opener.open(f'{base}/desk', timeout=60) as response:
        result['authenticated_desk_boot'] = assert_ready_desk(response.read().decode(), response.geturl())
    with opener.open(f'{base}/socket.io/?EIO=4&transport=polling', timeout=30) as response:
        assert response.read().startswith(b'0{'), 'Realtime handshake did not succeed.'
    result['engine_io_handshake'] = True
    write_json(EVIDENCE / 'http-verification.json', result)
    return result

def package_visibility(token, allow_missing=False):
    url = 'https://api.github.com/orgs/zernova-platform/packages/container/ibtinex-erpnext'
    try:
        package = fetch_json(url, token)
    except urllib.error.HTTPError as error:
        if error.code == 404 and allow_missing:
            return None
        raise RuntimeError(f'Could not verify GHCR package visibility (HTTP {error.code}).') from None
    visibility = package.get('visibility')
    if visibility != 'private':
        raise RuntimeError(f'GHCR package must be private; observed {visibility!r}.')
    return visibility

def publish(image, inputs):
    token = os.environ.get('GH_TOKEN', '')
    if not token:
        raise RuntimeError('The workflow package token is unavailable.')
    package_visibility(token, allow_missing=True)
    docker_config = TEMP / 'ibtinex-docker-auth'
    docker_config.mkdir(mode=0o700, exist_ok=True)
    env = {**os.environ, 'DOCKER_CONFIG': str(docker_config)}
    destination = f'{IMAGE_REPOSITORY}:0.1.0-rc.1-g{inputs["source_commit"][:12]}'
    try:
        run(['docker', 'login', 'ghcr.io', '--username', os.environ['GITHUB_ACTOR'],
             '--password-stdin'], env=env, input=token, secrets=[token])
        run(['docker', 'tag', image, destination])
        run(['docker', 'push', destination], env=env, secrets=[token], capture=False)
        digests = json.loads(run(['docker', 'image', 'inspect', '--format', '{{json .RepoDigests}}', destination]))
        digest = next(value for value in digests if value.startswith(IMAGE_REPOSITORY + '@sha256:'))
        package_visibility(token)
    finally:
        shutil.rmtree(docker_config, ignore_errors=True)
    output('published_digest', digest.split('@', 1)[1])
    output('published_image', IMAGE_REPOSITORY)
    return destination, digest

def verify_publish():
    inputs = json.loads(STATE.read_text())
    image = f'ibtinex-ci:{inputs["source_commit"]}'
    directory = TEMP / 'ibtinex-ci-installation'
    project = f'ibtinex-ci-{os.environ.get("GITHUB_RUN_ID", "local")}-{os.environ.get("GITHUB_RUN_ATTEMPT", "1")}'
    site = 'starter.ibtinex-ci.invalid'
    secret_values = []
    try:
        initialize(directory, image=image, mariadb_image=inputs['mariadb_image'],
                   redis_image=inputs['redis_image'], project=project, site=site,
                   port=free_port(), starter_data=True, ci=True)
        secret_values = [p.read_text().strip() for p in (directory / '.secrets').iterdir()]
        compose(directory, 'config', '--quiet')
        print('Creating blank baseline site and proving sample data is opt-in.', flush=True)
        compose(directory, '--profile', 'setup', 'run', '--rm', '-T',
                '-e', 'SITE_NAME=empty.ibtinex-ci.invalid', '-e', 'IBTINEX_STARTER_DATA=none',
                'create-site', capture=False)
        qualify(directory, 'empty.ibtinex-ci.invalid', 'empty')
        print('Creating the explicitly selected synthetic starter company.', flush=True)
        state = start(directory, skip_pull=True)
        qualify(directory, site, 'starter')
        http_checks(state['port'], (directory / '.secrets/admin-password').read_text().strip())
        print('Recreating application containers and rechecking the persisted site.', flush=True)
        compose(directory, 'up', '-d', '--no-deps', '--force-recreate', '--wait', '--wait-timeout', '360',
                'backend', 'websocket', 'queue-short', 'queue-long', 'scheduler', 'frontend', capture=False)
        qualify(directory, site, 'starter')
        print('Posting a legitimate review stock transfer and proving a normal start preserves it.', flush=True)
        qualify(directory, site, 'explore')
        start(directory, skip_pull=True)
        qualify(directory, site, 'after-exploration')
        python_packages = run(['docker', 'run', '--rm', '--entrypoint',
                               '/home/frappe/frappe-bench/env/bin/python', image,
                               '-m', 'pip', 'list', '--format=json'])
        write_json(EVIDENCE / 'python-packages.json', json.loads(python_packages))
        os_packages = run(['docker', 'run', '--rm', '--entrypoint', 'dpkg-query', image,
                           '-W', '-f=${Package}\t${Version}\n'])
        (EVIDENCE / 'os-packages.tsv').write_text(os_packages)
        manifest = {**inputs, 'schema_version': 1, 'status': 'verified-review-candidate',
                    'customer_release_qualified': False,
                    'verification': ['fresh_empty_site', 'explicit_starter_install', 'native_business_assertions',
                                     'seed_idempotence', 'opt_in_and_site_guards', 'worker_execution',
                                     'http_icons_login_api', 'authenticated_desk_setup_complete',
                                     'realtime_handshake', 'container_recreation',
                                     'normal_restart_preserves_review_activity'],
                    'images': {'app': None, 'mariadb': inputs['mariadb_image'], 'redis': inputs['redis_image']}}
        if os.environ.get('IBTINEX_PUBLISH', 'false').lower() == 'true':
            print('All qualification checks passed; publishing the same tested image.', flush=True)
            tag, digest = publish(image, inputs)
            manifest.update(package_visibility='private', image_tag=tag)
            manifest['images']['app'] = digest
            write_json(EVIDENCE / 'release-manifest.json', manifest)
            with zipfile.ZipFile(EVIDENCE / 'ibtinex-erp-review-installer.zip', 'w', zipfile.ZIP_DEFLATED) as bundle:
                for file in ('deploy.py', 'common.py', 'compose.yaml', 'README.md'):
                    bundle.write(HERE / file, file)
                bundle.write(EVIDENCE / 'release-manifest.json', 'release-manifest.json')
                walkthrough = ROOT / 'docs/ibtinex/STARTER_WALKTHROUGH.md'
                if walkthrough.exists():
                    bundle.write(walkthrough, 'STARTER_WALKTHROUGH.md')
            if summary := os.environ.get('GITHUB_STEP_SUMMARY'):
                with open(summary, 'a') as stream:
                    stream.write(f'## Verified private review candidate\n\n`{digest}`\n\n'
                                 'Fresh install, synthetic workflows, guarded repeat seed, real HTTP and '
                                 'container recreation checks passed. Normal start preserves a subsequent native '
                                 'stock transfer and site configuration. Customer rollout is not qualified.\n')
        else:
            write_json(EVIDENCE / 'verification-only.json', manifest)
    except Exception as error:
        message = redact(str(error), secret_values + [os.environ.get('GH_TOKEN', '')])
        write_json(EVIDENCE / 'failure.json', {'status': 'failed', 'reason': message,
                                             'image_published_as_verified': False})
        if directory.exists():
            try:
                logs = compose(directory, 'logs', '--no-color', '--tail', '120')
                (EVIDENCE / 'sanitized-container-logs.txt').write_text(redact(logs, secret_values))
            except Exception:
                pass
        raise RuntimeError(message) from None
    finally:
        if (directory / 'installation.json').exists():
            try:
                verify_ownership(directory)
                compose(directory, '--profile', 'setup', 'down', '--volumes', '--remove-orphans', capture=False)
            except Exception as cleanup_error:
                print(redact(f'CI cleanup did not complete: {cleanup_error}', secret_values), file=sys.stderr)
        shutil.rmtree(directory / '.secrets', ignore_errors=True)

if __name__ == '__main__':
    try:
        {'prepare': prepare, 'verify-publish': verify_publish}[sys.argv[1]]()
    except Exception as error:
        print(redact(str(error), [os.environ.get('GH_TOKEN', '')]), file=sys.stderr)
        sys.exit(1)
