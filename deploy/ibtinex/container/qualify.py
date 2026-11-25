"""CI-only synthetic assertions, invoked explicitly; never an install hook."""
import argparse
import hashlib
import json
import os
import time
from decimal import Decimal
from pathlib import Path

import frappe
import erpnext
from erpnext.ibtinex_starter.seed import install, verify

parser = argparse.ArgumentParser()
parser.add_argument('--site', required=True)
parser.add_argument('--mode', choices=('empty', 'starter', 'explore', 'after-exploration'), required=True)
args = parser.parse_args()
if not args.site.endswith('.ibtinex-ci.invalid'):
    raise SystemExit('Qualification only operates on the dedicated CI site suffix.')
os.chdir('/home/frappe/frappe-bench/sites')
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

def exploration_snapshot():
    from erpnext.ibtinex_starter.plan import COMPANY, MARKER_KEY
    balances = {}
    for row in frappe.get_all('GL Entry', filters={'company': COMPANY, 'is_cancelled': 0},
                              fields=['account', 'debit', 'credit']):
        balances[row.account] = balances.get(row.account, Decimal(0)) + Decimal(str(row.debit)) - Decimal(str(row.credit))
    return {'business_record_counts': counts(),
            'bins': frappe.get_all('Bin', fields=['item_code', 'warehouse', 'actual_qty', 'stock_value'],
                                   order_by='item_code, warehouse'),
            'account_balances': {name: str(value) for name, value in sorted(balances.items())},
            'marker_sha256': hashlib.sha256(frappe.db.get_global(MARKER_KEY).encode()).hexdigest(),
            'site_config_sha256': hashlib.sha256(Path(frappe.get_site_path('site_config.json')).read_bytes()).hexdigest()}

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
    elif args.mode == 'starter':
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
    else:
        from erpnext.ibtinex_starter.plan import COMPANY, MARKER_KEY
        marker = json.loads(frappe.db.get_global(MARKER_KEY))
        records = marker['records']
        transfer_name = 'ISE-CI-REVIEW-TRANSFER'
        snapshot_path = Path(frappe.get_site_path('private', 'ibtinex-ci-exploration.json'))
        if args.mode == 'explore':
            assert not frappe.db.exists('Stock Entry', transfer_name), 'Exploration was already performed.'
            transfer = frappe.get_doc({'doctype': 'Stock Entry', 'stock_entry_type': 'Material Transfer',
                                      'purpose': 'Material Transfer', 'company': COMPANY,
                                      'posting_date': marker['as_of_date'], 'posting_time': '00:39:00',
                                      'set_posting_time': 1,
                                      'items': [{'item_code': records['finished_item']['name'], 'qty': 1,
                                                 's_warehouse': records['finished_warehouse']['name'],
                                                 't_warehouse': records['showroom_warehouse']['name']}]})
            transfer.insert(set_name=transfer_name)
            transfer.submit()
            frappe.db.commit()
            # An engineer may change review-site settings after initialization.
            # Turning off the seeding flag must survive a normal start too.
            from frappe.installer import update_site_config
            update_site_config('ibtinex_starter_demo', 0,
                               site_config_path=frappe.get_site_path('site_config.json'))
            snapshot = exploration_snapshot()
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(json.dumps(snapshot, default=str, sort_keys=True))
            result['checks']['native_review_transfer_submitted'] = True
        else:
            expected = json.loads(snapshot_path.read_text())
            snapshot = exploration_snapshot()
            assert json.loads(json.dumps(snapshot, default=str)) == expected, 'A normal restart changed the explored site.'
            assert not frappe.conf.get('ibtinex_starter_demo'), 'Normal start reset the engineer-selected site flag.'
            result['checks']['restart_preserves_edited_business_state_and_site_config'] = True
        transfer = frappe.get_doc('Stock Entry', transfer_name)
        assert transfer.docstatus == 1 and float(transfer.items[0].qty) == 1
        for key in ('finished_warehouse', 'showroom_warehouse'):
            actual = frappe.db.get_value('Bin', {'item_code': records['finished_item']['name'],
                                                'warehouse': records[key]['name']}, 'actual_qty')
            assert float(actual) == 3, 'The legitimate review stock movement was reset.'
        result['exploration_state'] = snapshot
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
