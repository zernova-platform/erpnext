"""CI-only synthetic assertions, invoked explicitly; never an install hook."""
import argparse
import json
import time
from pathlib import Path

import frappe
import erpnext
from erpnext.ibtinex_starter.seed import install, verify

parser = argparse.ArgumentParser()
parser.add_argument('--site', required=True)
parser.add_argument('--mode', choices=('empty', 'starter'), required=True)
args = parser.parse_args()
if not args.site.endswith('.ibtinex-ci.invalid'):
    raise SystemExit('Qualification only operates on the dedicated CI site suffix.')
frappe.init(site=args.site, sites_path='/home/frappe/frappe-bench/sites')
frappe.connect()
frappe.set_user('Administrator')

def counts():
    modules = (Path(erpnext.__file__).parent / 'modules.txt').read_text().splitlines()
    doctypes = frappe.get_all('DocType', filters={'module': ['in', modules], 'issingle': 0},
                             fields=['name', 'is_virtual'])
    return {row.name: frappe.db.count(row.name) for row in doctypes if not row.is_virtual}

def rejection(call):
    try:
        call()
    except (ValueError, frappe.ValidationError, frappe.PermissionError):
        frappe.db.rollback()
        return True
    raise AssertionError('A guarded starter request unexpectedly succeeded.')

try:
    assert frappe.__version__ == '16.60.2' and erpnext.__version__ == '16.60.0'
    assert set(frappe.get_installed_apps()) == {'frappe', 'erpnext'}
    result = {'site': args.site, 'mode': args.mode, 'checks': {}}
    before = counts()
    if args.mode == 'empty':
        assert frappe.db.count('Company') == 0, 'Sample company was inserted without opt-in.'
        assert not frappe.conf.get('ibtinex_starter_demo')
        result['checks']['no_automatic_sample_data'] = True
        result['checks']['missing_opt_in_rejected'] = rejection(
            lambda: install(expected_site=args.site, accept_sample_data=False))
        result['checks']['non_demo_site_rejected'] = rejection(
            lambda: install(expected_site=args.site, accept_sample_data=True))
        assert counts() == before, 'Rejected requests changed business data.'
    else:
        result['verification'] = verify(expected_site=args.site)
        first = install(expected_site=args.site, accept_sample_data=True)
        second = install(expected_site=args.site, accept_sample_data=True)
        assert first['records'] == second['records']
        assert first['coverage'] == second['coverage']
        assert counts() == before, 'Repeated installation changed business table counts.'
        result['checks']['repeat_install_preserves_all_erp_table_counts'] = True
        result['checks']['missing_opt_in_rejected'] = rejection(
            lambda: install(expected_site=args.site, accept_sample_data=False))
        result['checks']['wrong_site_rejected'] = rejection(
            lambda: install(expected_site='wrong.ibtinex-ci.invalid', accept_sample_data=True))
        assert counts() == before, 'Rejected requests changed business data.'
        # Simulate an eligible demo flag on an occupied database without a seed marker.
        # This is entirely within the disposable CI site's transaction; rollback restores it.
        from erpnext.ibtinex_starter.plan import MARKER_KEY
        marker = frappe.db.get_global(MARKER_KEY)
        try:
            frappe.db.set_global(MARKER_KEY, None)
            frappe.clear_cache()
            try:
                install(expected_site=args.site, accept_sample_data=True)
            except ValueError as error:
                assert str(error).startswith('Starter requires a fresh site;'), str(error)
            else:
                raise AssertionError('An occupied site without a marker accepted starter installation.')
        finally:
            frappe.db.rollback()
            frappe.clear_cache()
        assert frappe.db.get_global(MARKER_KEY) == marker, 'The marker was not restored by rollback.'
        assert counts() == before, 'Existing business records changed during the rejection test.'
        result['checks']['occupied_site_rejected_without_mutation'] = True
        verify(expected_site=args.site)
        from frappe.utils.background_jobs import enqueue
        job = enqueue('frappe.utils.now', queue='short', timeout=60)
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            status = job.get_status(refresh=True)
            state = getattr(status, 'value', status)
            if state == 'finished':
                break
            if state in {'failed', 'stopped', 'canceled'}:
                raise AssertionError('The background worker failed its synthetic test job.')
            time.sleep(1)
        else:
            raise AssertionError('The background worker did not complete its test job.')
        result['checks']['real_background_job_completed'] = True
        result['business_record_counts'] = {key: value for key, value in counts().items() if value}
        result['coverage'] = first['coverage']
    from erpnext.ibtinex_branding import LOGO, FAVICON, apply as apply_branding
    assert frappe.db.get_single_value('Website Settings', 'app_logo') == LOGO
    assert frappe.db.get_single_value('Website Settings', 'favicon') == FAVICON
    assert not apply_branding()['changed'], 'Repeated branding changed already-applied settings.'
    result['checks']['branding_idempotent'] = True
    result['checks']['native_versions_retained'] = True
    print(json.dumps(result, default=str, sort_keys=True))
finally:
    frappe.db.rollback()
    frappe.destroy()
