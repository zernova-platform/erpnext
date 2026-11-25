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
BRANCH = 'feat/ibtinex-erp-v0.1.1-branding'
VERSION = '0.1.1-rc.1'
PREVIOUS = json.loads((HERE / 'previous-release.json').read_text(encoding='utf-8'))

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
    if '@sha256:' in image:
        if image not in digests:
            raise RuntimeError('Pulled dependency did not retain its pinned repository digest.')
        return image
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
    if branch != BRANCH:
        raise RuntimeError('Only the explicitly qualified candidate branch can publish.')
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if CONTEXT.exists():
        shutil.rmtree(CONTEXT)
    shutil.copytree(HERE, CONTEXT, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'tests'))
    # A presentation-only release retains the exact tested runtime dependencies.
    # Resolving floating tags here would quietly change the upgrade boundary.
    node = PREVIOUS['node_version']
    if not re.fullmatch(r'24\.\d+\.\d+', node):
        raise RuntimeError('Could not resolve Node 24 LTS.')
    inputs = {'distribution_version': VERSION, 'source_commit': commit,
              'source_repository': 'https://github.com/zernova-platform/erpnext',
              'source_branch': branch, 'erpnext_version': '16.60.0',
              'frappe_version': '16.60.2', 'frappe_commit': FRAPPE_COMMIT,
              'frappe_docker_reference': DOCKER_COMMIT, 'bench_version': '5.31.1',
              'node_version': node, 'platform': 'linux/amd64',
              'python_base_image': pull_digest(PREVIOUS['python_base_image']),
              'mariadb_image': pull_digest(PREVIOUS['mariadb_image']),
              'redis_image': pull_digest(PREVIOUS['redis_image'])}
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

def qualify(directory, site, mode, *, evidence_prefix=''):
    command = ['/home/frappe/frappe-bench/env/bin/python', '/opt/ibtinex/qualify.py',
               '--site', site, '--mode', mode]
    raw = compose(directory, 'run', '--rm', '--no-deps', '-T', '--entrypoint', command[0],
                  'backend', *command[1:])
    # Compose progress is on stderr; function output is the final JSON line.
    payload = json.loads(next(line for line in reversed(raw.splitlines()) if line.startswith('{')))
    write_json(EVIDENCE / f'{evidence_prefix}{mode}-verification.json', payload)
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
    assert boot.get('home_page') != 'setup-wizard', 'Desk still opens the setup-wizard home page.'
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
    destination = f'{IMAGE_REPOSITORY}:{VERSION}-g{inputs["source_commit"][:12]}'
    try:
        run(['docker', 'login', 'ghcr.io', '--username', os.environ['GITHUB_ACTOR'],
             '--password-stdin'], env=env, input=token, secrets=[token])
        probe = subprocess.run(['docker', 'manifest', 'inspect', destination], env=env,
                               text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if probe.returncode == 0:
            raise RuntimeError('This immutable source tag already exists. It was not overwritten. '
                               'Use its existing evidence or create a new candidate source commit.')
        if not any(value in probe.stderr.lower() for value in ('manifest unknown', 'no such manifest', 'not found')):
            raise RuntimeError('Could not verify that the candidate tag is unused; publication stopped.')
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

def pull_previous_image():
    """Pull only the previously qualified private digest, with transient auth."""
    token = os.environ.get('GH_TOKEN', '')
    if not token:
        raise RuntimeError('Registry access is required to rehearse the real existing-installation upgrade.')
    package_visibility(token)
    docker_config = TEMP / 'ibtinex-upgrade-docker-auth'
    docker_config.mkdir(mode=0o700, exist_ok=True)
    env = {**os.environ, 'DOCKER_CONFIG': str(docker_config)}
    try:
        run(['docker', 'login', 'ghcr.io', '--username', os.environ['GITHUB_ACTOR'],
             '--password-stdin'], env=env, input=token, secrets=[token])
        run(['docker', 'pull', '--platform', 'linux/amd64', PREVIOUS['images']['app']],
            env=env, secrets=[token], capture=False)
    finally:
        shutil.rmtree(docker_config, ignore_errors=True)

def upgrade_contract():
    return {'kind': 'appearance-only', 'schema_changed': False,
            'from_images': [PREVIOUS['images']['app']], 'rollback_compatible': True}

def check_upgrade_and_rollback(image, inputs):
    """Rehearse against the actual released image and a persisted stock movement."""
    from deploy import rollback, upgrade
    pull_previous_image()
    directory = TEMP / 'ibtinex-upgrade-installation'
    project = f'ibtinex-upgrade-{os.environ.get("GITHUB_RUN_ID", "local")}-{os.environ.get("GITHUB_RUN_ATTEMPT", "1")}'
    site = 'upgrade.ibtinex-ci.invalid'
    secrets_to_redact = []
    try:
        initialize(directory, image=PREVIOUS['images']['app'],
                   mariadb_image=PREVIOUS['images']['mariadb'], redis_image=PREVIOUS['images']['redis'],
                   project=project, site=site, port=free_port(), starter_data=True)
        secrets_to_redact = [p.read_text().strip() for p in (directory / '.secrets').iterdir()]
        start(directory, skip_pull=True)
        qualify(directory, site, 'starter', evidence_prefix='previous-')
        qualify(directory, site, 'explore', evidence_prefix='previous-')
        # The local exact-commit image is accepted only by the internal CI API.
        # This manifest is a test input, not published qualification evidence.
        candidate = {**inputs, 'schema_version': 1, 'status': 'verified-review-candidate',
                     'package_visibility': 'private', 'customer_release_qualified': False,
                     'upgrade': upgrade_contract(),
                     'images': {'app': image, 'mariadb': inputs['mariadb_image'], 'redis': inputs['redis_image']}}
        upgraded = upgrade(directory, candidate, ci=True)
        qualify(directory, site, 'after-exploration', evidence_prefix='upgraded-')
        rollback(directory, Path(upgraded['backup_directory']), ci=True)
        qualify(directory, site, 'after-exploration', evidence_prefix='rolled-back-')
        upgrade(directory, candidate, ci=True)
        qualify(directory, site, 'after-exploration', evidence_prefix='reupgraded-')
        write_json(EVIDENCE / 'upgrade-verification.json', {
            'status': 'passed', 'host': 'Linux GitHub Actions',
            'from_image': PREVIOUS['images']['app'], 'to_source_commit': inputs['source_commit'],
            'checks': ['real_previous_image_install', 'native_stock_transfer_before_upgrade',
                       'mandatory_full_backup', 'upgrade_preserves_all_erp_counts_gl_bins_and_site_config',
                       'appearance_only_rollback_preserves_business_state', 'repeat_upgrade'],
            'windows_docker_desktop': 'not-executed',
            'backup_contents': 'retained only in private disposable CI directory; never published'})
    except Exception as error:
        raise RuntimeError(redact(f'Upgrade rehearsal failed: {error}', secrets_to_redact)) from None
    finally:
        if (directory / 'installation.json').exists():
            try:
                verify_ownership(directory)
                compose(directory, '--profile', 'setup', 'down', '--volumes', '--remove-orphans', capture=False)
            except Exception as error:
                print(redact(f'Isolated upgrade CI cleanup did not complete: {error}', secrets_to_redact), file=sys.stderr)
        # Site backups include encryption keys and synthetic passwords. They are
        # deliberately outside uploaded evidence and are removed after rehearsal.
        shutil.rmtree(directory, ignore_errors=True)

def check_legacy_password_recovery(image, inputs):
    """Reproduce the old CRLF failure, then recover only its empty partial site."""
    directory = TEMP / 'ibtinex-crlf-installation'
    project = f'ibtinex-crlf-{os.environ.get("GITHUB_RUN_ID", "local")}-{os.environ.get("GITHUB_RUN_ATTEMPT", "1")}'
    site = 'recovery.ibtinex-ci.invalid'
    secrets_to_redact = []
    try:
        state = initialize(directory, image=PREVIOUS['images']['app'],
                           mariadb_image=inputs['mariadb_image'], redis_image=inputs['redis_image'],
                           project=project, site=site, port=free_port(), starter_data=True)
        password_path = directory / '.secrets/db-password'
        password_path.write_bytes(password_path.read_bytes().rstrip(b'\r\n') + b'\r\n')
        secrets_to_redact = [p.read_text().strip() for p in (directory / '.secrets').iterdir()]
        compose(directory, 'up', '-d', '--wait', 'db', 'redis-cache', 'redis-queue', capture=False)
        try:
            compose(directory, '--profile', 'setup', 'run', '--rm', '-T', 'create-site')
        except RuntimeError as error:
            if '1045' not in str(error) and 'Access denied' not in str(error):
                raise AssertionError('Previous-image failure did not reproduce the expected MariaDB authentication error.') from None
        else:
            raise AssertionError('The previous image unexpectedly accepted the CRLF secret; the proposed root cause is unproven.')
        # The new host installer streams the bundled recovery bootstrap into
        # the previous image. Its selected image and all volumes stay unchanged;
        # a subsequent visual upgrade still requires the full backup gate.
        start(directory, skip_pull=True, recover=True)
        qualify(directory, site, 'starter', evidence_prefix='crlf-recovered-')
        start(directory, skip_pull=True)
        qualify(directory, site, 'starter', evidence_prefix='crlf-restarted-')
        write_json(EVIDENCE / 'legacy-password-recovery.json', {
            'status': 'passed', 'host': 'Linux GitHub Actions',
            'root_cause_reproduced': 'CRLF password file; MariaDB retains CR while old Python reader strips it',
            'old_image': PREVIOUS['images']['app'], 'new_source_commit': inputs['source_commit'],
            'checks': ['previous_image_access_denied', 'same_volumes_preserved',
                       'explicit_empty_partial_site_recovery', 'legacy_crlf_authentication',
                       'native_starter_workflows_after_recovery', 'safe_repeat_start'],
            'windows_docker_desktop': 'not-executed'})
    except Exception as error:
        raise RuntimeError(redact(f'Legacy secret recovery rehearsal failed: {error}', secrets_to_redact)) from None
    finally:
        if (directory / 'installation.json').exists():
            try:
                verify_ownership(directory)
                compose(directory, '--profile', 'setup', 'down', '--volumes', '--remove-orphans', capture=False)
            except Exception as error:
                print(redact(f'Isolated CRLF CI cleanup did not complete: {error}', secrets_to_redact), file=sys.stderr)
        shutil.rmtree(directory, ignore_errors=True)

def build_installer(manifest):
    write_json(EVIDENCE / 'release-manifest.json', manifest)
    destination = EVIDENCE / f'ibtinex-erp-{VERSION}-windows-installer.zip'
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as bundle:
        prefix = 'ibtinex-erp-review-installer/'
        for name in ('deploy.py', 'common.py', 'maintenance.py', 'compose.yaml', 'README.md', 'WINDOWS.md'):
            bundle.write(HERE / name, prefix + name)
        bundle.write(HERE / 'container/bootstrap.py', prefix + 'container/bootstrap.py')
        bundle.write(EVIDENCE / 'release-manifest.json', prefix + 'release-manifest.json')
        bundle.write(HERE / 'previous-release.json', prefix + 'previous-release.json')
        bundle.write(ROOT / 'license.txt', prefix + 'ERPNext-LICENSE.txt')
        bundle.write(HERE / 'vendor/frappe_docker/LICENSE', prefix + 'Frappe-Docker-LICENSE.txt')
        bundle.write(ROOT / 'docs/ibtinex/STARTER_WALKTHROUGH.md', prefix + 'STARTER_WALKTHROUGH.md')
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    (EVIDENCE / (destination.name + '.sha256')).write_text(f'{digest}  {destination.name}\n', encoding='utf-8')
    return destination

def release_prerelease(installer, inputs):
    """Publish the requested review release, explicitly retaining open gates."""
    tag = f'ibtinex-erp-{VERSION}-g{inputs["source_commit"][:12]}'
    notes = EVIDENCE / 'RELEASE_NOTES.md'
    notes.write_text(
        f'# IBTINEX ERP {VERSION}\n\n'
        'Calm dark-green/off-white native theme, Windows-safe secret files, and an explicit backed-up upgrade/visual rollback path.\n\n'
        'This is a review candidate. Automated Linux container, native Windows Python, browser, '
        'business-state preservation, upgrade and rollback gates passed for the exact source and image in release-manifest.json.\n\n'
        '**Open gate:** full fresh installation, recovery, upgrade and rollback on Windows Docker Desktop '
        'have not been executed. This release is not production/customer qualified.\n\n'
        'Download the installer ZIP and read WINDOWS.md. Existing sites must use the upgrade command; '
        'do not initialize over an existing deployment. The GHCR package remains private.\n\n'
        'ERPNext GPLv3 and Frappe MIT notices are retained. Exact corresponding source archives accompany this candidate.\n',
        encoding='utf-8')
    qualification = EVIDENCE / f'ibtinex-erp-{VERSION}-qualification.zip'
    with zipfile.ZipFile(qualification, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(EVIDENCE.glob('*.json')):
            if path.name not in {'failure.json', 'release-location.json'}:
                archive.write(path, path.name)
        for path in sorted((EVIDENCE / 'visual').rglob('*')):
            if path.is_file() and path.suffix in {'.png', '.json', '.html'}:
                archive.write(path, str(path.relative_to(EVIDENCE)))
        archive.write(notes, notes.name)
    command = ['gh', 'release', 'create', tag, '--repo', 'zernova-platform/erpnext',
               '--target', inputs['source_commit'], '--title', f'IBTINEX ERP {VERSION}',
               '--prerelease', '--notes-file', str(notes), str(installer),
               str(EVIDENCE / (installer.name + '.sha256')),
               str(EVIDENCE / 'release-manifest.json'),
               str(qualification),
               str(EVIDENCE / 'erpnext-corresponding-source.tar.gz'),
               str(EVIDENCE / 'frappe-corresponding-source.tar.gz')]
    run(command, secrets=[os.environ.get('GH_TOKEN', '')], capture=False)
    return f'https://github.com/zernova-platform/erpnext/releases/tag/{tag}'

def verify_publish():
    inputs = json.loads(STATE.read_text())
    image = f'ibtinex-ci:{inputs["source_commit"]}'
    directory = TEMP / 'ibtinex-ci-installation'
    project = f'ibtinex-ci-{os.environ.get("GITHUB_RUN_ID", "local")}-{os.environ.get("GITHUB_RUN_ATTEMPT", "1")}'
    site = 'starter.ibtinex-ci.invalid'
    secret_values = []
    publication = {'phase': 'not-published', 'image': None, 'tag': None}
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
        print('Checking native desktop/mobile screens, both themes, and visible focus.', flush=True)
        from visual_checks import run_visual_checks
        run_visual_checks(f'http://127.0.0.1:{state["port"]}',
                          directory / '.secrets/admin-password', EVIDENCE / 'visual', site)
        print('Recreating application containers and rechecking the persisted site.', flush=True)
        compose(directory, 'up', '-d', '--no-deps', '--force-recreate', '--wait', '--wait-timeout', '360',
                'backend', 'websocket', 'queue-short', 'queue-long', 'scheduler', 'frontend', capture=False)
        qualify(directory, site, 'starter')
        print('Posting a legitimate review stock transfer and proving a normal start preserves it.', flush=True)
        qualify(directory, site, 'explore')
        start(directory, skip_pull=True)
        qualify(directory, site, 'after-exploration')
        print('Rehearsing an upgrade from the previous private release and visual rollback.', flush=True)
        check_upgrade_and_rollback(image, inputs)
        print('Reproducing the old CRLF password failure and proving guarded recovery.', flush=True)
        check_legacy_password_recovery(image, inputs)
        python_packages = run(['docker', 'run', '--rm', '--entrypoint',
                               '/home/frappe/frappe-bench/env/bin/python', image,
                               '-m', 'pip', 'list', '--format=json'])
        write_json(EVIDENCE / 'python-packages.json', json.loads(python_packages))
        os_packages = run(['docker', 'run', '--rm', '--entrypoint', 'dpkg-query', image,
                           '-W', '-f=${Package}\t${Version}\n'])
        (EVIDENCE / 'os-packages.tsv').write_text(os_packages)
        manifest = {**inputs, 'schema_version': 1, 'status': 'verified-review-candidate',
                    'customer_release_qualified': False,
                    'upgrade': upgrade_contract(),
                    'release_gates': {
                        'native_windows_python_tests': 'passed (separate windows-latest prerequisite job)',
                        'linux_fresh_install_and_native_workflows': 'passed',
                        'native_ui_screenshot_and_focus_checks': 'passed',
                        'linux_previous_release_upgrade_and_rollback': 'passed',
                        'legacy_crlf_failure_reproduction_and_recovery': 'passed',
                        'windows_docker_desktop_end_to_end': 'not-executed',
                        'complete_wcag_22_aa_audit': 'not-executed; automated checks are partial'},
                    'verification': ['fresh_empty_site', 'explicit_starter_install', 'native_business_assertions',
                                     'seed_idempotence', 'opt_in_and_site_guards', 'worker_execution',
                                     'http_icons_login_api', 'authenticated_desk_setup_complete',
                                     'realtime_handshake', 'container_recreation',
                                     'normal_restart_preserves_review_activity', 'browser_theme_checks',
                                     'real_previous_image_upgrade', 'appearance_only_rollback',
                                     'legacy_crlf_recovery',
                                     'native_windows_installer_unit_tests'],
                    'images': {'app': None, 'mariadb': inputs['mariadb_image'], 'redis': inputs['redis_image']}}
        if os.environ.get('IBTINEX_PUBLISH', 'false').lower() == 'true':
            print('All qualification checks passed; publishing the same tested image.', flush=True)
            publication['phase'] = 'publishing'
            tag, digest = publish(image, inputs)
            publication.update(phase='image-published', image=digest, tag=tag)
            manifest.update(package_visibility='private', image_tag=tag)
            manifest['images']['app'] = digest
            installer = build_installer(manifest)
            release_url = release_prerelease(installer, inputs)
            publication['phase'] = 'release-published'
            write_json(EVIDENCE / 'release-location.json', {'url': release_url, 'image': digest})
            if summary := os.environ.get('GITHUB_STEP_SUMMARY'):
                with open(summary, 'a') as stream:
                    stream.write(f'## IBTINEX ERP {VERSION} review candidate\n\n`{digest}`\n\n'
                                 f'[Download the candidate installer]({release_url})\n\n'
                                 'Native Windows Python, Linux container business workflows, browser screenshots/focus, '
                                 'existing-release upgrade and visual rollback checks passed. '
                                 'Windows Docker Desktop end-to-end installation and a full accessibility audit remain '
                                 'open. Customer rollout is not qualified.\n')
        else:
            write_json(EVIDENCE / 'verification-only.json', manifest)
    except Exception as error:
        message = redact(str(error), secret_values + [os.environ.get('GH_TOKEN', '')])
        write_json(EVIDENCE / 'failure.json', {'status': 'failed', 'reason': message,
                                             'publication': publication,
                                             'image_published_as_verified': (
                                                 True if publication['image'] else
                                                 None if publication['phase'] == 'publishing' else False)})
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
