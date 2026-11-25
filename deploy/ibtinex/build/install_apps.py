"""Invoke the supported Bench CLI for the one approved public fork."""
import json
from pathlib import Path
import subprocess
import sys

APP = {'url': 'https://github.com/zernova-platform/erpnext.git',
       'branch': 'ibtinex/starter-0.1.0'}

def install(path):
    apps = json.loads(Path(path).read_text())
    if apps != [APP]:
        raise ValueError('The build requires exactly the approved ERP fork and candidate branch.')
    # The CLI initializes Bench logging and runs dependency setup. Importing its
    # internal install_apps_from_path() directly bypasses that initialization.
    subprocess.run(['bench', 'get-app', '--skip-assets', '--branch', APP['branch'], APP['url']],
                   cwd='/home/frappe/frappe-bench', check=True)

if __name__ == '__main__':
    install(sys.argv[1])
