import json
import os
import urllib.request

request = urllib.request.Request('http://127.0.0.1:8000/api/method/ping',
                                 headers={'Host': os.environ['SITE_NAME']})
with urllib.request.urlopen(request, timeout=5) as response:
    if json.load(response).get('message') != 'pong':
        raise SystemExit(1)
