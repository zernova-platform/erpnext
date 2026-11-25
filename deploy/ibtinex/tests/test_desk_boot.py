import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ci import assert_ready_desk

class DeskBootTests(unittest.TestCase):
    def page(self, complete=True, wizard=False, home='workspace'):
        boot = {'sysdefaults': {'setup_complete': complete}, 'user': {'name': 'Administrator'}, 'home_page': home}
        if wizard:
            boot['setup_wizard_url'] = '/app/setup-wizard'
        return '<script>frappe.boot = ' + json.dumps(boot) + '; frappe.csrf_token = "not-exported";</script>'

    def test_native_boot_json_is_parsed_without_exporting_session_material(self):
        result = assert_ready_desk(self.page(), 'http://127.0.0.1:8081/desk')
        self.assertEqual(result, {'native_route': '/desk', 'setup_complete': True, 'setup_wizard_redirect': False})

    def test_incomplete_or_wizard_boot_is_rejected(self):
        for html in (self.page(complete=False), self.page(wizard=True),
                     self.page(home='setup-wizard'), '<html>Login</html>'):
            with self.subTest(html=html), self.assertRaises(AssertionError):
                assert_ready_desk(html, 'http://127.0.0.1:8081/desk')

    def test_native_workspace_or_desktop_home_variants_remain_valid(self):
        for home in ('workspace', 'desktop', 'erpnext'):
            with self.subTest(home=home):
                self.assertTrue(assert_ready_desk(self.page(home=home), 'http://127.0.0.1:8081/desk')['setup_complete'])

    def test_login_or_setup_redirect_is_rejected(self):
        for route in ('/login', '/desk/setup-wizard', '/app/setup-wizard'):
            with self.subTest(route=route), self.assertRaises(AssertionError):
                assert_ready_desk(self.page(), 'http://127.0.0.1:8081' + route)

if __name__ == '__main__':
    unittest.main()
