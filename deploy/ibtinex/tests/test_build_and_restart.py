import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

build = load('install_apps', HERE / 'build/install_apps.py')
state = load('starter_state', HERE / 'container/starter_state.py')

class BuildCliTests(unittest.TestCase):
    def test_approved_manifest_uses_supported_cli_and_argument_array(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'apps.json'
            path.write_text(json.dumps([build.APP]))
            with patch.object(build.subprocess, 'run') as process:
                build.install(path)
            process.assert_called_once_with(
                ['bench', 'get-app', '--skip-assets', '--branch', build.APP['branch'], build.APP['url']],
                cwd='/home/frappe/frappe-bench', check=True)

    def test_unapproved_or_credential_bearing_manifest_never_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'apps.json'
            path.write_text(json.dumps([dict(build.APP, url='https://token@github.com/other/erpnext')]))
            with patch.object(build.subprocess, 'run') as process, self.assertRaises(ValueError):
                build.install(path)
            process.assert_not_called()

class CompletedStarterTests(unittest.TestCase):
    def manifest(self):
        return {'status': 'installed', 'seed_version': '1.0.0', 'company': 'Synthetic Company',
                'verification': {'status': 'passed'},
                'records': {'company': {'doctype': 'Company', 'name': 'Synthetic Company'}}}

    def check(self, db):
        return state.completed_starter(db, marker_key='marker', seed_version='1.0.0', company='Synthetic Company')

    def test_completed_site_needs_no_stock_check_or_database_write(self):
        db = Mock(spec=['get_global', 'exists'])
        db.get_global.return_value = json.dumps(self.manifest())
        db.exists.return_value = True
        self.assertEqual(self.check(db), {'status': 'already-present', 'seed_version': '1.0.0',
                                         'company': 'Synthetic Company'})
        db.exists.assert_called_once_with('Company', 'Synthetic Company')

    def test_absent_marker_does_not_pretend_seed_completed(self):
        db = Mock(spec=['get_global', 'exists'])
        db.get_global.return_value = None
        self.assertIsNone(self.check(db))
        db.exists.assert_not_called()

    def test_partial_incompatible_or_missing_company_is_rejected(self):
        variants = ['{}', 'null', 'invalid', json.dumps(dict(self.manifest(), status='partial')),
                    json.dumps(dict(self.manifest(), seed_version='2.0.0'))]
        for raw in variants:
            with self.subTest(raw=raw), self.assertRaises(RuntimeError):
                db = Mock(spec=['get_global', 'exists'])
                db.get_global.return_value = raw
                self.check(db)
        db = Mock(spec=['get_global', 'exists'])
        db.get_global.return_value = json.dumps(self.manifest())
        db.exists.return_value = False
        with self.assertRaises(RuntimeError):
            self.check(db)

if __name__ == '__main__':
    unittest.main()
