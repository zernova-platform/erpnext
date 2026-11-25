"""Fresh-site installer. Read secrets as root, then drop to the runtime UID."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

BENCH = Path('/home/frappe/frappe-bench')
site = os.environ.get('SITE_NAME', '')
if not re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,120}[a-z0-9]', site) or '..' in site:
    raise SystemExit('A valid SITE_NAME is required.')
starter = os.environ.get('IBTINEX_STARTER_DATA', 'none')
if starter not in {'none', 'ethiopia-demo'}:
    raise SystemExit('IBTINEX_STARTER_DATA must be none or ethiopia-demo.')
secrets = [Path('/run/secrets/db_password').read_text().strip(),
           Path('/run/secrets/admin_password').read_text().strip()]
if any(len(value) < 24 for value in secrets):
    raise SystemExit('Provisioned database and administrator passwords must be at least 24 characters.')
if os.getuid() == 0:
    os.setgroups([])
    os.setgid(0)
    os.setuid(1000)
os.chdir(BENCH)

def run(args):
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = result.stdout
    for secret in secrets:
        output = output.replace(secret, '[REDACTED]')
    if result.returncode:
        print(output[-16000:], file=sys.stderr)
        raise SystemExit('Site setup command failed; existing data has been preserved.')
    return output

config_path = BENCH / 'sites' / site / 'site_config.json'
created = not config_path.exists()
if created:
    # Values are passed directly to the child process, never interpolated into a shell.
    run(['bench', 'new-site', '--db-root-username', 'root',
         '--db-root-password', secrets[0], '--admin-password', secrets[1],
         '--mariadb-user-host-login-scope', '%', '--install-app', 'erpnext',
         '--set-default', site])

# Frappe's direct Python API resolves bench/site logs relative to the sites
# working directory, even when init() receives an absolute sites_path.
os.chdir(BENCH / 'sites')
import frappe
import erpnext
from frappe.installer import update_site_config
frappe.init(site=site, sites_path=str(BENCH / 'sites'))
frappe.connect()
frappe.set_user('Administrator')
try:
    if frappe.__version__ != '16.60.2' or erpnext.__version__ != '16.60.0':
        raise RuntimeError('The running application versions do not match this installer.')
    if set(frappe.get_installed_apps()) != {'frappe', 'erpnext'}:
        raise RuntimeError('Unexpected installed application set; refusing to change this site.')
    summary = {'site': site, 'created': created, 'erpnext': erpnext.__version__,
               'frappe': frappe.__version__, 'starter_data': starter}
    from erpnext.ibtinex_branding import apply as apply_branding
    summary['branding'] = apply_branding()
    if starter == 'ethiopia-demo':
        from erpnext.ibtinex_starter.seed import install
        from erpnext.ibtinex_starter.plan import COMPANY, MARKER_KEY, SEED_VERSION
        from starter_state import completed_starter
        present = completed_starter(frappe.db, marker_key=MARKER_KEY,
                                    seed_version=SEED_VERSION, company=COMPANY)
        if present:
            # A normal start must preserve legitimate review activity and site
            # settings. Strict fixture verification remains an explicit diagnostic.
            summary['starter'] = present
        else:
            if not created and not frappe.conf.get('ibtinex_starter_demo'):
                raise RuntimeError('Starter data can only initialize a newly created review site.')
            if created:
                for name in ('ibtinex_starter_demo', 'mute_emails', 'pause_scheduler'):
                    update_site_config(name, 1, site_config_path=str(config_path))
                    frappe.conf[name] = 1
            summary['starter'] = install(expected_site=site, accept_sample_data=True)
    frappe.db.commit()
    print(json.dumps(summary, default=str, sort_keys=True))
except Exception:
    frappe.db.rollback()
    raise
finally:
    frappe.destroy()
