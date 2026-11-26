"""Portable byte, recovery, and destructive-operation guards; no Docker mocks claimed as runtime tests."""
import copy
import gzip
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import deploy
import maintenance
from common import IMAGE_REPOSITORY

spec = importlib.util.spec_from_file_location('bootstrap_safety', HERE / 'container/bootstrap.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


def arguments():
    return dict(image=IMAGE_REPOSITORY + '@sha256:' + 'a' * 64,
                mariadb_image='mariadb@sha256:' + 'b' * 64,
                redis_image='redis@sha256:' + 'c' * 64,
                project='ibtinex-upgrade-test', site='review.localhost', port=8081)


def release():
    args = arguments()
    return dict(schema_version=1, status='verified-review-candidate', platform='linux/amd64',
                package_visibility='private', erpnext_version='16.60.0', frappe_version='16.60.2',
                source_commit='d' * 40,
                images={'app': IMAGE_REPOSITORY + '@sha256:' + 'd' * 64,
                        'mariadb': args['mariadb_image'], 'redis': args['redis_image']},
                upgrade={'kind': 'appearance-only', 'schema_changed': False,
                         'from_images': [args['image']], 'rollback_compatible': True})


class SecretBytesTests(unittest.TestCase):
    def test_windows_writer_bug_is_reproduced_and_correct_reader_matches_mariadb(self):
        token = 'a-long-provisioned-password-123456789'
        raw = io.BytesIO()
        writer = io.TextIOWrapper(raw, encoding='utf-8', newline='\r\n')
        writer.write(token + '\n')
        writer.flush()
        legacy_bytes = raw.getvalue()
        self.assertEqual(legacy_bytes, token.encode() + b'\r\n')
        maria_password = legacy_bytes.rstrip(b'\n').decode()
        old_python_password = legacy_bytes.decode().strip()
        self.assertNotEqual(maria_password, old_python_password)
        candidates = bootstrap.secret_values(legacy_bytes, database=True)
        self.assertEqual(candidates, [maria_password, old_python_password])
        self.assertEqual(bootstrap.secret_values(legacy_bytes, database=False), [token])

    def test_new_credentials_are_exact_ascii_on_every_host_and_repeat_init_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'deployment'
            deploy.initialize(root, **arguments())
            originals = {path.name: path.read_bytes() for path in (root / '.secrets').iterdir()}
            for value in originals.values():
                self.assertEqual(len(value), 48)
                self.assertNotIn(b'\r', value)
                self.assertNotIn(b'\n', value)
                self.assertEqual(value.decode().encode(), value)
            deploy.initialize(root, **arguments())
            self.assertEqual(originals, {path.name: path.read_bytes() for path in (root / '.secrets').iterdir()})

    def test_legacy_password_files_are_never_normalized_when_reading_existing_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'deployment'
            deploy.initialize(root, **arguments())
            path = root / '.secrets/db-password'
            original = path.read_bytes() + b'\r\n'
            path.write_bytes(original)
            deploy.load_state(root)
            self.assertEqual(path.read_bytes(), original)

    def test_already_repaired_database_uses_proven_fallback_without_changing_secret(self):
        connector = MagicMock()
        connector.side_effect = [Exception(1045, 'Access denied'), MagicMock()]
        self.assertEqual(bootstrap.root_password(['password-with-carriage-return\r', 'password-with-carriage-return'], connector),
                         'password-with-carriage-return')
        self.assertEqual(connector.call_count, 2)

    def test_network_failure_does_not_try_other_passwords_or_expose_values(self):
        connector = MagicMock(side_effect=Exception(2003, 'secret-not-for-logs'))
        with self.assertRaises(bootstrap.SetupError) as error:
            bootstrap.root_password(['secret-not-for-logs', 'another-value'], connector)
        self.assertNotIn('secret-not-for-logs', str(error.exception))
        connector.assert_called_once()


class EmptyRecoveryTests(unittest.TestCase):
    def partial(self, root):
        site = root / 'sites/review.localhost'
        site.mkdir(parents=True)
        (site / 'site_config.json').write_text(json.dumps({'db_name': '_failed_install', 'db_password': 'retained'}))
        return site

    def connector(self, table_count):
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value.fetchone.return_value = (table_count,)
        return MagicMock(return_value=connection)

    def test_empty_partial_site_is_archived_and_database_is_never_dropped(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            site = self.partial(root)
            original = (site / 'site_config.json').read_bytes()
            connector = self.connector(0)
            target = bootstrap.archive_empty_partial_site(site, 'not-logged', connector)
            self.assertFalse(site.exists())
            self.assertEqual((target / 'site_config.json').read_bytes(), original)
            cursor = connector.return_value.cursor.return_value.__enter__.return_value
            cursor.execute.assert_called_once_with(
                'SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=%s', ('_failed_install',))

    def test_nonempty_database_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            site = self.partial(Path(temporary))
            with self.assertRaises(bootstrap.SetupError):
                bootstrap.archive_empty_partial_site(site, 'not-logged', self.connector(1))
            self.assertTrue((site / 'site_config.json').is_file())
            self.assertFalse((site.parent / '.ibtinex-recovery').exists())

    def test_existing_business_files_block_recovery_even_when_database_is_empty(self):
        with tempfile.TemporaryDirectory() as temporary:
            site = self.partial(Path(temporary))
            attachment = site / 'private/files/invoice.pdf'
            attachment.parent.mkdir(parents=True)
            attachment.write_bytes(b'customer-data')
            connector = self.connector(0)
            with self.assertRaises(bootstrap.SetupError):
                bootstrap.archive_empty_partial_site(site, 'not-logged', connector)
            self.assertEqual(attachment.read_bytes(), b'customer-data')
            connector.assert_not_called()

    def test_uploaded_logs_subdirectory_is_not_native_site_log_data(self):
        for visibility in ('public', 'private'):
            with self.subTest(visibility=visibility), tempfile.TemporaryDirectory() as temporary:
                site = self.partial(Path(temporary))
                attachment = site / visibility / 'files/logs/customer.txt'
                attachment.parent.mkdir(parents=True)
                attachment.write_bytes(b'customer-file-must-survive')
                connector = self.connector(0)
                with self.assertRaises(bootstrap.SetupError):
                    bootstrap.archive_empty_partial_site(site, 'not-logged', connector)
                connector.assert_not_called()
                self.assertEqual(attachment.read_bytes(), b'customer-file-must-survive')
                self.assertTrue((site / 'site_config.json').is_file())

    def test_retained_native_install_lock_is_acquired_nonblocking_and_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            site = self.partial(Path(temporary))
            path = site / 'locks/bench_new_site.lock'
            path.parent.mkdir()
            path.write_bytes(b'')
            lock = MagicMock()
            factory = MagicMock(return_value=lock)
            module = SimpleNamespace(FileLock=factory, Timeout=type('Timeout', (Exception,), {}))
            with patch.dict(sys.modules, {'filelock': module}):
                destination = bootstrap.archive_empty_partial_site(site, 'not-logged', self.connector(0))
            factory.assert_called_once_with(str(path), timeout=0)
            lock.acquire.assert_called_once_with(timeout=0)
            lock.release.assert_called_once_with()
            self.assertTrue((destination / 'locks/bench_new_site.lock').is_file())

    def test_held_native_install_lock_refuses_recovery_before_database_access(self):
        with tempfile.TemporaryDirectory() as temporary:
            site = self.partial(Path(temporary))
            path = site / 'locks/bench_new_site.lock'
            path.parent.mkdir()
            path.write_bytes(b'')
            timeout = type('Timeout', (Exception,), {})
            lock = MagicMock()
            lock.acquire.side_effect = timeout()
            connector = self.connector(0)
            module = SimpleNamespace(FileLock=MagicMock(return_value=lock), Timeout=timeout)
            with patch.dict(sys.modules, {'filelock': module}), self.assertRaises(bootstrap.SetupError):
                bootstrap.archive_empty_partial_site(site, 'not-logged', connector)
            connector.assert_not_called()
            lock.release.assert_not_called()
            self.assertTrue((site / 'site_config.json').is_file())

    def test_another_lock_filename_is_not_treated_as_empty_installation_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            site = self.partial(Path(temporary))
            path = site / 'locks/customer-operation.lock'
            path.parent.mkdir()
            path.write_bytes(b'preserve')
            with self.assertRaises(bootstrap.SetupError):
                bootstrap.archive_empty_partial_site(site, 'not-logged', self.connector(0))
            self.assertEqual(path.read_bytes(), b'preserve')

    @unittest.skipUnless(sys.platform != 'win32', 'Symlink creation requires special Windows privileges')
    def test_native_install_lock_symlink_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            site = self.partial(Path(temporary))
            path = site / 'locks/bench_new_site.lock'
            path.parent.mkdir()
            path.symlink_to(site / 'site_config.json')
            connector = self.connector(0)
            with self.assertRaises(bootstrap.SetupError):
                bootstrap.archive_empty_partial_site(site, 'not-logged', connector)
            connector.assert_not_called()
            self.assertTrue(path.is_symlink())

    @unittest.skipUnless(sys.platform != 'win32', 'Symlink creation requires special Windows privileges')
    def test_native_lock_parent_symlink_is_refused_before_lock_open(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            site = self.partial(root)
            external = root / 'external-locks'
            external.mkdir()
            target = external / 'bench_new_site.lock'
            target.write_bytes(b'must-not-be-opened-or-truncated')
            (site / 'locks').symlink_to(external, target_is_directory=True)
            factory = MagicMock()
            module = SimpleNamespace(FileLock=factory, Timeout=type('Timeout', (Exception,), {}))
            connector = self.connector(0)
            with patch.dict(sys.modules, {'filelock': module}), self.assertRaises(bootstrap.SetupError):
                bootstrap.archive_empty_partial_site(site, 'not-logged', connector)
            factory.assert_not_called()
            connector.assert_not_called()
            self.assertEqual(target.read_bytes(), b'must-not-be-opened-or-truncated')

    def test_recovery_uses_new_helper_without_switching_existing_image(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'installation'
            original = deploy.initialize(root, **arguments())
            with patch.object(deploy, 'verify_ownership', return_value=original), \
                 patch.object(deploy, 'compose', return_value='existing-container') as compose:
                deploy.start(root, skip_pull=True, recover=True)
            setup = next(call for call in compose.call_args_list if 'create-site' in call.args)
            self.assertIn('--entrypoint', setup.args)
            self.assertEqual(setup.args[-1], '-')
            self.assertIn('archive_empty_partial_site', setup.kwargs['input'])
            self.assertEqual(deploy.load_state(root)['image'], original['image'])


class UpgradeSafetyTests(unittest.TestCase):
    def test_only_exact_qualified_image_pair_and_same_dependencies_are_accepted(self):
        state = arguments()
        deploy.validate_upgrade(state, release())
        for name in ('kind', 'schema_changed', 'rollback_compatible', 'from_images'):
            candidate = release()
            candidate['upgrade'].pop(name)
            with self.subTest(name=name), self.assertRaises(ValueError):
                deploy.validate_upgrade(state, candidate)
        for key in ('frappe_version', 'erpnext_version'):
            candidate = release()
            candidate[key] = 'unqualified'
            with self.subTest(key=key), self.assertRaises(ValueError):
                deploy.validate_upgrade(state, candidate)
        candidate = release()
        candidate['images']['mariadb'] = 'mariadb@sha256:' + 'e' * 64
        with self.assertRaises(ValueError):
            deploy.validate_upgrade(state, candidate)

    def test_local_ci_image_is_unavailable_through_default_manifest_validation(self):
        candidate = release()
        candidate['images']['app'] = 'ibtinex-ci:' + 'd' * 40
        with self.assertRaises(ValueError):
            deploy.release_manifest(candidate)
        deploy.release_manifest(candidate, ci=True)

    def test_configuration_disagreement_and_concurrent_mutation_are_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'deployment'
            deploy.initialize(root, **arguments())
            with deploy.operation_lock(root):
                with self.assertRaises(RuntimeError):
                    with deploy.operation_lock(root):
                        self.fail('Concurrent mutation was allowed')
            self.assertFalse((root / '.operation.lock').exists())
            env = root / '.env'
            env.write_text(env.read_text().replace('HTTP_PORT=8081', 'HTTP_PORT=8082'))
            with self.assertRaises(ValueError):
                deploy.load_state(root)

    def test_failed_backup_cannot_change_image_or_run_theme_application(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'deployment'
            state = deploy.initialize(root, **arguments())
            metadata = {**release(), 'branding_fields': [], 'branding_state_key': 'ibtinex_branding_v1'}
            with patch.object(deploy, 'verify_ownership', return_value=state), \
                 patch.object(deploy, 'image_metadata', return_value=metadata), \
                 patch.object(deploy, '_backup', side_effect=RuntimeError('backup failed')), \
                 patch.object(deploy, '_set_image') as image, patch.object(deploy, 'maintenance') as maintenance_call:
                with self.assertRaises(RuntimeError):
                    deploy.upgrade(root, release())
                image.assert_not_called()
                maintenance_call.assert_not_called()
            self.assertEqual(deploy.load_state(root)['image'], state['image'])
            self.assertFalse((root / 'pending-upgrade.json').exists())

    def test_critical_shell_variables_cannot_redirect_docker_project_or_image(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'deployment'
            state = deploy.initialize(root, **arguments())
            with patch.dict(deploy.os.environ, {'COMPOSE_PROJECT_NAME': 'another-customer',
                                              'IBTINEX_IMAGE': 'unqualified', 'COMPOSE_FILE': 'other.yml'}), \
                 patch.object(deploy, 'run', return_value='') as run:
                deploy.compose(root, 'ps')
            self.assertIn(state['project'], run.call_args.args[0])
            env = run.call_args.kwargs['env']
            self.assertEqual(env['COMPOSE_PROJECT_NAME'], state['project'])
            self.assertEqual(env['IBTINEX_IMAGE'], state['image'])
            self.assertNotIn('COMPOSE_FILE', env)

    def test_restore_preserves_exact_original_configuration_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = b'{\n "db_password": "retained", "encryption_key": "retained-too", "pause_scheduler": 1\n}\n'
            (root / 'site_config.original.json').write_bytes(original)
            current = root / 'site_config.json'
            current.write_text(json.dumps(dict(json.loads(original), maintenance_mode=1)))
            maintenance.resume_config(current, root)
            self.assertEqual(current.read_bytes(), original)

    def test_restore_merges_unrelated_user_edits_without_rewriting_credentials(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original = {'db_password': 'retained', 'pause_scheduler': 0}
            (root / 'site_config.original.json').write_text(json.dumps(original))
            current = root / 'site_config.json'
            current.write_text(json.dumps(dict(original, pause_scheduler=1, maintenance_mode=1, custom_setting='keep')))
            maintenance.resume_config(current, root)
            self.assertEqual(json.loads(current.read_text()), {**original, 'custom_setting': 'keep'})

    def test_backup_integrity_rejects_truncation_missing_files_and_path_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {}
            for kind in ('database', 'public', 'private', 'config', 'original_config', 'branding'):
                path = root / (kind + '.backup')
                path.write_bytes((kind + '-data').encode())
                files[path.name] = {'kind': kind, 'size': path.stat().st_size, 'sha256': deploy._digest(path)}
            deploy.atomic_json(root / 'backup.json', {'files': files})
            deploy.verify_backup(root)
            (root / 'database.backup').write_bytes(b'truncated')
            with self.assertRaises(ValueError):
                deploy.verify_backup(root)
            files['../outside'] = files.pop('database.backup')
            deploy.atomic_json(root / 'backup.json', {'files': files})
            with self.assertRaises(ValueError):
                deploy.verify_backup(root)

    def test_native_database_backup_must_be_readable_and_contain_schema(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / 'database.sql.gz'
            with gzip.open(path, 'wb') as stream:
                stream.write(b'-- metadata\nCREATE TABLE `tabCompany` (name text);\n')
            maintenance.validate_native_backup(path, 'database')
            path.write_bytes(b'not-a-valid-gzip')
            with self.assertRaises((OSError, EOFError)):
                maintenance.validate_native_backup(path, 'database')

    def test_quiesce_cache_failure_restores_original_configuration_before_raising(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = root / 'site_config.json'
            original = b'{"db_password": "preserved", "encryption_key": "preserved-too"}\n'
            config.write_bytes(original)
            frappe = MagicMock()
            frappe.get_system_settings.return_value = False
            frappe.clear_cache.side_effect = RuntimeError('Redis unavailable')
            with patch.object(maintenance, 'read_branding', return_value={'fields': {}, 'state': None}), \
                 self.assertRaises(RuntimeError):
                maintenance.quiesce(frappe, config, root / 'snapshot',
                                    {'branding_fields': [], 'branding_state_key': 'ibtinex_branding_v1'})
            self.assertEqual(config.read_bytes(), original)

    def test_image_change_preserves_windows_environment_bytes_and_unrelated_entries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'installation'
            deploy.initialize(root, **arguments())
            path = root / '.env'
            original = path.read_bytes().replace(b'\n', b'\r\n') + b'CUSTOM_SETTING=keep-me\r\n'
            path.write_bytes(original)
            target = release()['images']['app']
            deploy._set_image(root, target)
            self.assertEqual(path.read_bytes(), original.replace(arguments()['image'].encode(), target.encode()))

    def test_pending_upgrade_never_reports_already_current(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'installation'
            state = deploy.initialize(root, **{**arguments(), 'image': release()['images']['app']})
            (root / 'pending-upgrade.json').write_text('{}')
            with patch.object(deploy, 'verify_ownership', return_value=state), self.assertRaises(RuntimeError):
                deploy.upgrade(root, release())

    def test_rollback_registry_failure_occurs_before_any_backup_or_downtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'installation'
            previous = deploy.initialize(root, **arguments())
            saved = root / 'backups/test'
            saved.mkdir(parents=True)
            for source, target in (('installation.json', 'previous-installation.json'),
                                   ('.env', 'previous-env'), ('compose.yaml', 'previous-compose.yaml'),
                                   ('.secrets/db-password', 'previous-db-password'),
                                   ('.secrets/admin-password', 'previous-admin-password')):
                (saved / target).write_bytes((root / source).read_bytes())
            journal = {'stage': 'completed', 'token': '20261125T120000Z-aaaaaaaaaaaa',
                       'installation_id': previous['installation_id'], 'from_image': previous['image'],
                       'to_image': release()['images']['app'], 'manifest': release()}
            deploy.atomic_json(saved / 'upgrade.json', journal)
            deploy._set_image(root, journal['to_image'])
            with patch.object(deploy, 'verify_backup', return_value={'installation_id': previous['installation_id']}), \
                 patch.object(deploy, 'verify_ownership', return_value=deploy.load_state(root)), \
                 patch.object(deploy, 'image_metadata', side_effect=RuntimeError('Registry unavailable')), \
                 patch.object(deploy, '_backup') as backup, patch.object(deploy, 'compose') as compose:
                with self.assertRaises(RuntimeError):
                    deploy.rollback(root, saved)
                backup.assert_not_called()
                compose.assert_not_called()

    def test_rollback_projects_changed_branding_ownership_to_old_runtime_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fields = {'Website Settings.app_name': 'ERPNext', 'Website Settings.favicon': '/customer.svg'}
            before = {'fields': fields, 'state_key': 'ibtinex_branding_v1',
                      'state': json.dumps({'version': 1, 'managed': {}})}
            after = {'fields': {**fields, 'Website Settings.app_name': 'IBTINEX ERP'},
                     'state_key': before['state_key'],
                     'state': json.dumps({'version': 1, 'managed': {
                         'Website Settings.app_name': {'previous': 'ERPNext', 'applied': 'IBTINEX ERP'}}})}
            current = copy.deepcopy(after)
            current['fields']['Website Settings.favicon'] = '/ibtinex.svg'
            current['state'] = json.dumps({'version': 1, 'managed': {
                'Website Settings.app_name': {'previous': 'ERPNext', 'applied': 'IBTINEX ERP'},
                'Website Settings.favicon': {'previous': '/upstream.svg', 'applied': '/ibtinex.svg'}}})
            maintenance.write_json(root / 'branding-before.json', before)
            maintenance.write_json(root / 'branding-after.json', after)
            frappe = MagicMock()
            with patch.object(maintenance, 'read_branding', return_value=current):
                maintenance.restore_branding(frappe, root, {'rollback_fields': ['Website Settings.favicon']})
            restored = json.loads(frappe.db.set_default.call_args.args[1])
            self.assertEqual(set(restored['managed']), {'Website Settings.favicon'})
            frappe.db.set_single_value.assert_called_once_with('Website Settings', 'app_name', 'ERPNext')

    def test_rollback_branding_preserves_custom_edits_since_upgrade(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = {'fields': {'Website Settings.app_name': 'ERPNext', 'System Settings.app_name': None},
                      'state_key': 'ibtinex_branding_v1', 'state': None}
            after = {'fields': {'Website Settings.app_name': 'IBTINEX ERP', 'System Settings.app_name': 'IBTINEX ERP'},
                     'state_key': 'ibtinex_branding_v1', 'state': '{"version": 1}'}
            current = copy.deepcopy(after)
            current['fields']['Website Settings.app_name'] = 'Customer choice'
            maintenance.write_json(root / 'branding-before.json', before)
            maintenance.write_json(root / 'branding-after.json', after)
            frappe = MagicMock()
            with patch.object(maintenance, 'read_branding', return_value=current):
                result = maintenance.restore_branding(frappe, root)
            self.assertEqual(result, {'restored': ['System Settings.app_name'],
                                      'preserved': ['Website Settings.app_name']})
            frappe.db.set_single_value.assert_called_once_with('System Settings', 'app_name', None)
            frappe.db.set_default.assert_called_once_with('ibtinex_branding_v1', None)


if __name__ == '__main__':
    unittest.main()
