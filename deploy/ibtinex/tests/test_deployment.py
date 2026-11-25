import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from common import IMAGE_REPOSITORY, redact, valid_dependency, valid_image, valid_project, valid_site
from deploy import initialize

class DeploymentSafetyTests(unittest.TestCase):
    def arguments(self):
        return dict(image=IMAGE_REPOSITORY + '@sha256:' + 'a' * 64,
                    mariadb_image='mariadb@sha256:' + 'b' * 64,
                    redis_image='redis@sha256:' + 'c' * 64,
                    project='ibtinex-review-test', site='review.localhost', port=8081)

    def test_release_image_requires_own_digest(self):
        valid_image(self.arguments()['image'])
        for value in [IMAGE_REPOSITORY + ':latest', 'other.invalid/image@sha256:' + 'a' * 64,
                      IMAGE_REPOSITORY + '@sha256:abc', 'ibtinex-ci:' + 'a' * 40]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                valid_image(value)

    def test_no_site_path_or_environment_injection(self):
        for value in ['../customer', 'review\nPASSWORD=bad', '/tmp/site', 'a;touch-file', 'a..b']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                valid_site(value)

    def test_project_scope_is_required(self):
        for value in ['customer', 'ibtinex-a\nOTHER=1', 'ibtinex-../other', '-p-other']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                valid_project(value)

    def test_dependency_cannot_inject_compose_environment(self):
        with self.assertRaises(ValueError):
            valid_dependency('mariadb@sha256:' + 'a' * 64 + '\nPASSWORD=x')

    def test_fresh_deployment_defaults_to_no_seed_and_secret_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'review'
            state = initialize(root, **self.arguments())
            self.assertFalse(state['starter_data'])
            env = (root / '.env').read_text()
            self.assertIn('IBTINEX_STARTER_DATA=none\n', env)
            self.assertNotIn('PASSWORD', env)
            values = [(root / '.secrets' / name).read_text().strip()
                      for name in ('db-password', 'admin-password')]
            self.assertNotEqual(*values)
            self.assertTrue(all(len(value) >= 24 for value in values))
            report = (root / 'installation.json').read_text()
            self.assertTrue(all(value not in report and value not in env for value in values))
            self.assertTrue(all(value not in (root / 'compose.yaml').read_text() for value in values))

    def test_seed_is_an_explicit_installation_choice(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'review'
            state = initialize(root, starter_data=True, **self.arguments())
            self.assertTrue(state['starter_data'])
            self.assertIn('IBTINEX_STARTER_DATA=ethiopia-demo', (root / '.env').read_text())

    def test_existing_directory_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'customer-data').write_text('keep')
            with self.assertRaises(ValueError):
                initialize(root, **self.arguments())
            self.assertEqual((root / 'customer-data').read_text(), 'keep')
            self.assertFalse((root / '.secrets').exists())

    def test_out_of_range_port_rejected_before_files_created(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'review'
            arguments = self.arguments()
            arguments['port'] = 80
            with self.assertRaises(ValueError):
                initialize(root, **arguments)
            self.assertFalse(root.exists())

    def test_overlapping_secret_redaction(self):
        self.assertEqual(redact('token=abcd and abc', ['abc', 'abcd']),
                         'token=[REDACTED] and [REDACTED]')

if __name__ == '__main__':
    unittest.main()
