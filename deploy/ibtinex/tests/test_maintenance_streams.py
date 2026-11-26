"""Exercise real faulthandler/file-descriptor behavior in isolated processes."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]


class MaintenanceStreamsTests(unittest.TestCase):
    def run_python(self, script):
        return subprocess.run([sys.executable, '-c', script], text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)

    def test_original_stringio_suppression_reproduces_framework_import_failure(self):
        result = self.run_python('''
import contextlib, faulthandler, io
with contextlib.redirect_stderr(io.StringIO()):
    try:
        # Pinned frappe._optimizations.register_fault_handler() calls this
        # without an explicit file while importing frappe.
        faulthandler.enable()
    except io.UnsupportedOperation:
        print('UnsupportedOperation reproduced')
    else:
        raise AssertionError('The original failure was not reproduced')
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'UnsupportedOperation reproduced')

    def test_main_keeps_faulthandler_fds_and_suppresses_python_native_and_child_output(self):
        result = self.run_python(f'''
import faulthandler, json, os, subprocess, sys
sys.path.insert(0, {str(HERE)!r})
import maintenance

def fake_execute(*args):
    faulthandler.enable()
    assert sys.stderr.fileno() == 2
    print('python-stdout-secret')
    print('python-stderr-secret', file=sys.stderr)
    os.write(1, b'native-stdout-secret\\n')
    os.write(2, b'native-stderr-secret\\n')
    subprocess.run([sys.executable, '-c',
                    'import sys; print("child-stdout-secret"); print("child-stderr-secret", file=sys.stderr)'],
                   check=True)
    return {{'status': 'quiesced'}}

maintenance.execute = fake_execute
sys.argv = ['-', 'review.localhost', 'quiesce', '20261125T120000Z-aaaaaaaaaaaa']
maintenance.main()
assert faulthandler.is_enabled()
os.fstat(1)
os.fstat(2)
print('standard-error-restored', file=sys.stderr)
faulthandler.disable()
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'status': 'quiesced'})
        self.assertEqual(result.stderr.strip(), 'standard-error-restored')
        self.assertNotIn('secret', result.stdout + result.stderr)

    def test_native_output_is_suppressed_and_descriptors_restored_on_exception(self):
        result = self.run_python(f'''
import os, sys
sys.path.insert(0, {str(HERE)!r})
import maintenance
try:
    with maintenance.suppress_native_output():
        os.write(1, b'database-password-must-stay-hidden\\n')
        os.write(2, b'database-password-must-stay-hidden\\n')
        raise RuntimeError('database-password-must-stay-hidden')
except RuntimeError:
    print('failure-handled')
    print('stderr-restored', file=sys.stderr)
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'failure-handled')
        self.assertEqual(result.stderr.strip(), 'stderr-restored')
        self.assertNotIn('database-password', result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
