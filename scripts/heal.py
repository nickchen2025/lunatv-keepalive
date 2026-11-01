#!/usr/bin/env python3
"""LunaTV keep-alive + source self-heal loop.

Runs for LOOP_SECONDS (default 5h50m, < the 6h GitHub job limit), pinging Render every
INTERVAL seconds. Each tick: (1) request /api/server-config so the free Render instance
never idles out, (2) log in, (3) if the source list is empty (free Redis restarted), write
the LUNA_CONFIG backup back. All configuration comes from env vars/secrets.
"""
import json, os, time, urllib.request, http.cookiejar

BASE = os.environ.get('BASE', 'https://lunatv-db80.onrender.com')
USER = os.environ.get('LUNA_USER', '')
PASS = os.environ.get('LUNA_PASS', '')
CFG = os.environ.get('LUNA_CONFIG', '')
INTERVAL = int(os.environ.get('INTERVAL', '300'))
LOOP_SECONDS = int(os.environ.get('LOOP_SECONDS', str(5 * 3600 + 50 * 60)))

def req(url, data=None, headers=None, opener=None):
    r = urllib.request.Request(url, data=data, headers=headers or {})
    return (opener.open(r, timeout=120) if opener else urllib.request.urlopen(r, timeout=120))

def wake():
    for i in range(24):
        try:
            req(BASE + '/api/server-config')
            return i
        except Exception:
            time.sleep(5)
    return -1

def tick():
    retries = wake()
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    req(BASE + '/api/login',
        data=json.dumps({'username': USER, 'password': PASS}).encode(),
        headers={'content-type': 'application/json'}, opener=op)
    d = json.load(req(BASE + '/api/admin/config', opener=op))
    c = d.get('Config', d)
    n = len([s for s in (c.get('SourceConfig') or []) if not s.get('disabled')])
    if n == 0:
        req(BASE + '/api/admin/config_file',
            data=json.dumps({'configFile': CFG}).encode(),
            headers={'content-type': 'application/json'}, opener=op)
        print(time.strftime('%H:%M:%S'), 'RESEEDED sources were empty (wake retries=%d)' % retries, flush=True)
    else:
        print(time.strftime('%H:%M:%S'), 'ok sources=%d wake_retries=%d' % (n, retries), flush=True)

deadline = time.time() + LOOP_SECONDS
count = 0
while time.time() < deadline:
    count += 1
    try:
        tick()
    except Exception as e:
        print(time.strftime('%H:%M:%S'), 'ERR', type(e).__name__, str(e)[:160], flush=True)
    time.sleep(min(INTERVAL, max(0, deadline - time.time())))
print('loop finished after %d ticks' % count, flush=True)
