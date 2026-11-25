import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlsplit
from urllib.request import url2pathname

HERE = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

build = load('install_apps', HERE / 'build/install_apps.py')
state = load('starter_state', HERE / 'container/starter_state.py')

class BuildCliTests(unittest.TestCase):
    def test_pinned_source_is_verified_before_dependencies_even_when_branch_advances(self):
        """Real git history; replace only Bench dependency installation in this unit test."""
        real_run = subprocess.run
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            remote, bench = directory / 'remote', directory / 'bench'
            (bench / 'apps').mkdir(parents=True)
            def git(*args, cwd=None):
                return real_run(['git', *args], cwd=cwd, check=True, text=True,
                                capture_output=True).stdout.strip()
            git('init', '--quiet', '-b', build.APP['branch'], str(remote))
            (remote / 'source.txt').write_text('the pinned source')
            git('add', 'source.txt', cwd=remote)
            git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'first', cwd=remote)
            pinned = git('rev-parse', 'HEAD', cwd=remote)
            (remote / 'source.txt').write_text('a newer branch head')
            git('add', 'source.txt', cwd=remote)
            git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'second', cwd=remote)
            self.assertNotEqual(git('rev-parse', 'HEAD', cwd=remote), pinned)
            manifest = directory / 'apps.json'
            manifest.write_text(json.dumps([build.APP]))
            fetched_source = []

            def run(args, **kwargs):
                if args[:2] == ['bench', 'get-app']:
                    self.assertEqual(args[2:5], ['--skip-assets', '--branch', build.SOURCE_BRANCH])
                    source = Path(url2pathname(urlsplit(args[5]).path))
                    fetched_source.append(source)
                    self.assertEqual(git('rev-parse', 'HEAD', cwd=source), pinned)
                    self.assertEqual((source / 'source.txt').read_text(), 'the pinned source')
                    return real_run(['git', 'clone', '--quiet', '--depth=1', '--branch', build.SOURCE_BRANCH,
                                     args[5], str(bench / 'apps/erpnext')], check=True)
                if len(args) == 7 and args[3:6] == ['remote', 'add', 'origin']:
                    self.assertEqual(args[-1], build.APP['url'])
                    args = [*args[:-1], remote.as_uri()]
                return real_run(args, **kwargs)

            with patch.object(build, 'BENCH_ROOT', bench), patch.object(build.subprocess, 'run', side_effect=run):
                build.install(manifest, pinned)
            self.assertEqual(git('rev-parse', 'HEAD', cwd=bench / 'apps/erpnext'), pinned)
            self.assertEqual(len(fetched_source), 1)
            self.assertFalse(fetched_source[0].parent.exists(), 'Temporary checkout was not removed.')

    def test_unapproved_or_credential_bearing_manifest_never_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'apps.json'
            path.write_text(json.dumps([dict(build.APP, url='https://token@github.com/other/erpnext')]))
            with patch.object(build.subprocess, 'run') as process, self.assertRaises(ValueError):
                build.install(path, 'a' * 40)
            process.assert_not_called()

    def test_invalid_commit_is_rejected_before_any_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'apps.json'
            path.write_text(json.dumps([build.APP]))
            for commit in ('', 'main', 'A' * 40, 'a' * 39, 'a' * 40 + ';echo unsafe', None):
                with self.subTest(commit=commit), patch.object(build.subprocess, 'run') as process:
                    with self.assertRaises(ValueError):
                        build.install(path, commit)
                    process.assert_not_called()

    def test_mismatched_fetch_never_installs_dependencies_and_cleans_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'apps.json'
            path.write_text(json.dumps([build.APP]))
            with patch.object(build, 'BENCH_ROOT', Path(directory) / 'bench'), \
                    patch.object(build.subprocess, 'run', return_value=Mock(stdout='b' * 40 + '\n')) as process:
                with self.assertRaisesRegex(RuntimeError, 'dependencies were not installed'):
                    build.install(path, 'a' * 40)
            self.assertFalse(any(call.args[0][0] == 'bench' for call in process.call_args_list))
            temporary_source = Path(process.call_args_list[0].args[0][-1])
            self.assertFalse(temporary_source.parent.exists())

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
