"""Configure this Compose bench; credentials are site-specific and untouched."""
import json
import os
from pathlib import Path

sites = Path('/home/frappe/frappe-bench/sites')
path = sites / 'common_site_config.json'
config = json.loads(path.read_text()) if path.exists() else {}
config.update(db_host='db', db_port=3306,
              redis_cache='redis://redis-cache:6379',
              redis_queue='redis://redis-queue:6379',
              redis_socketio='redis://redis-queue:6379', socketio_port=9000,
              chromium_path='/usr/lib/chromium/chromium-headless-shell')
temporary = path.with_suffix('.tmp')
temporary.write_text(json.dumps(config, indent=2) + '\n')
temporary.chmod(0o660)
os.replace(temporary, path)
(sites / 'apps.txt').write_text('frappe\nerpnext\n')
print('Bench endpoints configured.')
