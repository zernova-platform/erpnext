"""Install an exact approved source commit through the supported Bench CLI.

Bench 5.31.1 supports local/file git repositories. Fetching the requested commit
first prevents a moving candidate branch from installing different dependencies
and only being rejected by the Containerfile's later source check.
"""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

APP = {'url': 'https://github.com/zernova-platform/erpnext.git',
       'branch': 'feat/ibtinex-erp-v0.1.1-branding'}
BENCH_ROOT = Path('/home/frappe/frappe-bench')
SOURCE_BRANCH = 'ibtinex-build-source'

def install(path, commit):
    apps = json.loads(Path(path).read_text(encoding='utf-8'))
    if apps != [APP]:
        raise ValueError('The build requires exactly the approved ERP fork and candidate branch.')
    if not isinstance(commit, str) or not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('The build requires the exact lowercase 40-character ERP commit SHA.')
    if (BENCH_ROOT / 'apps/erpnext').exists():
        raise RuntimeError('ERPNext already exists in the build bench; refusing to overwrite it.')

    # This location is generated internally and contains no credentials. Bench's
    # supported get-app command clones it (never --soft-link), so cleanup cannot
    # remove its installed source or leave references to missing git objects.
    with tempfile.TemporaryDirectory(prefix='ibtinex-source-') as temporary:
        source = Path(temporary) / 'erpnext'
        subprocess.run(['git', 'init', '--quiet', str(source)], check=True)
        subprocess.run(['git', '-C', str(source), 'remote', 'add', 'origin', APP['url']], check=True)
        subprocess.run(['git', '-C', str(source), 'fetch', '--quiet', '--no-tags', '--depth=1',
                        'origin', commit], check=True)
        subprocess.run(['git', '-C', str(source), 'checkout', '--quiet', '-b', SOURCE_BRANCH,
                        'FETCH_HEAD'], check=True)
        head = subprocess.run(['git', '-C', str(source), 'rev-parse', 'HEAD'],
                              check=True, text=True, capture_output=True).stdout.strip()
        if head != commit:
            raise RuntimeError('Fetched ERP source does not match the requested commit; dependencies were not installed.')

        # The CLI initializes Bench logging and runs dependency setup. Importing
        # install_apps_from_path directly bypasses that initialization. A file URI
        # lets git honor shallow-clone semantics without copying shared objects.
        subprocess.run(['bench', 'get-app', '--skip-assets', '--branch', SOURCE_BRANCH, source.as_uri()],
                       cwd=str(BENCH_ROOT), check=True)
        installed = subprocess.run(['git', '-C', str(BENCH_ROOT / 'apps/erpnext'), 'rev-parse', 'HEAD'],
                                   check=True, text=True, capture_output=True).stdout.strip()
        if installed != commit:
            raise RuntimeError('Bench installed an unexpected ERP commit; the image build is stopped.')

if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: install_apps.py APPROVED_APPS_JSON EXACT_ERP_COMMIT')
    install(sys.argv[1], sys.argv[2])
