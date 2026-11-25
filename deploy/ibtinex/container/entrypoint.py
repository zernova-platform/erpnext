"""Keep baked assets available without racing other roles on the shared volume."""
import os
import sys
from pathlib import Path

assets = Path('/home/frappe/frappe-bench/sites/assets')
target = '/home/frappe/frappe-bench/assets'
assets.parent.mkdir(parents=True, exist_ok=True)
try:
    assets.symlink_to(target, target_is_directory=True)
except FileExistsError:
    if not assets.is_symlink() or os.readlink(assets) != target:
        raise SystemExit('Unexpected sites/assets contents; refusing to replace existing files.')
if len(sys.argv) < 2:
    raise SystemExit('An application command is required.')
os.execvp(sys.argv[1], sys.argv[1:])
