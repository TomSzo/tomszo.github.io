# -*- coding: utf-8 -*-
"""
Network4 / Arena4+ - a hivatalos mobilalkalmazás API-ja (net4plus.network4.hu/api).

A plugin.video.arena4plus (heg, vargalex) alapján feltérképezve:
    GET /api/login?email=..&password=..      -> {"access_token": "..."}   (Bearer)
    GET /api/collections                       -> [{title, slug, photo_thumbnail}, ...]
    GET /api/collectionitems/<slug>/<n>        -> [{vodsavail: [{title, short_desc,
                                                   poster_remote, vodviewer}, ...]}]
    GET /api/collectionitemslive/live/0        -> [{liveeventsavail: [{title, slug, status
                                                   (live/pre), expected_start, ...}]}]
    GET /api/watch/<slug>/live                 -> {src, replaysrc}
    GET /api/search/<szó>                      -> [{title, short_desc, vodviewer, ...}]
    VOD: a "vodviewer" oldalban: playbackUrl ... "https://...uplynk..."

Nem a weboldalt (www.network4.hu) használjuk - az Cloudflare-kihívás mögött van.
Cloudflare-kihívást NEM kerülünk meg: ha az API kihívást ad, jelezzük.
Kímélet: 1 mp szünet a kérések között, gyorsítótár (gyűjtemények / listák 6 óra),
a token lemezen, 401-nél egyszeri újrabelépés, sikertelen belépés után 10 perc szünet.
"""
import json
import os
import re
import time

try:
    from urllib.parse import quote
except ImportError:  # py2
    from urllib import quote

import xbmc
import xbmcaddon
import xbmcvfs

try:
    import requests
except ImportError:  # noqa
    requests = None

ADDON = xbmcaddon.Addon('plugin.video.network4')
ADDON_ID = 'plugin.video.network4'
API = 'https://net4plus.network4.hu/api'
STORAGE = 'https://net4plus.network4.hu/storage/'
FIREFOX_UA = 'Mozilla/5.0 (Android 16; Mobile; rv:156.0) Gecko/156.0 Firefox/156.0'
APP_UA = 'Dart/3.6 (dart:io)'
MIN_GAP = 1.0
LOGIN_COOLDOWN = 600
TOKEN_FILE = 'token.json'     # (a 0.1.x session.json-ja süti-lista volt)
LIST_TTL = 6 * 3600

_SESSION = requests.Session() if requests else None
_LAST = [0.0]


class ApiError(Exception):
    pass


class ChallengeError(ApiError):
    """Cloudflare-kihívás - nem kerüljük meg."""


class LoginError(ApiError):
    pass


def log(msg, level=xbmc.LOGINFO):
    xbmc.log('[%s] %s' % (ADDON_ID, msg), level)


def api_user_agent():
    return APP_UA if ADDON.getSetting('api_ua') == '1' else FIREFOX_UA


def profile(name=''):
    prof = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
    if not os.path.isdir(prof):
        try:
            os.makedirs(prof)
        except OSError:
            pass
    return os.path.join(prof, name)


def _read_json(name, default=None):
    """JSON a profil-mappából. Csak objektumot (dict) fogad el - a régi (0.1.x)
    verzió más szerkezetű fájljai (pl. süti-lista) így nem okoznak hibát."""
    try:
        with open(profile(name), 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (IOError, OSError, ValueError):
        return default
    return data if isinstance(data, dict) else default


def _write_json(name, data):
    try:
        with open(profile(name), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
    except (IOError, OSError) as exc:
        log('%s mentési hiba: %s' % (name, exc), xbmc.LOGWARNING)


# ---------------------------------------------------------------------------
# Számláló + HTTP
# ---------------------------------------------------------------------------
def _bump():
    today = time.strftime('%Y-%m-%d')
    data = _read_json('requests.json', {}) or {}
    if data.get('date') != today:
        data = {'date': today, 'count': 0}
    data['count'] = int(data.get('count', 0)) + 1
    _write_json('requests.json', data)


def today_requests():
    data = _read_json('requests.json', {}) or {}
    return int(data.get('count', 0)) if data.get('date') == time.strftime('%Y-%m-%d') else 0


def is_challenge(resp):
    if resp is None:
        return False
    if resp.headers.get('cf-mitigated', '').lower() == 'challenge':
        return True
    if resp.status_code in (403, 503) and 'text/html' in resp.headers.get('content-type', ''):
        body = resp.text[:4000]
        return '_cf_chl_opt' in body or 'Just a moment' in body or 'challenge-platform' in body
    return False


def _http(url, headers, params=None, timeout=25):
    if _SESSION is None:
        raise ApiError('Hiányzik a script.module.requests')
    gap = time.time() - _LAST[0]
    if gap < MIN_GAP:
        time.sleep(MIN_GAP - gap)
    _LAST[0] = time.time()
    _bump()
    log('GET %s' % url.split('?')[0])
    resp = _SESSION.get(url, params=params, headers=headers, timeout=timeout)
    if is_challenge(resp):
        _save_debug('challenge.html', resp.text)
        raise ChallengeError('Cloudflare-kihívás (%s)' % resp.status_code)
    return resp


def _save_debug(name, text):
    try:
        with open(profile(name), 'w', encoding='utf-8') as f:
            f.write(text or '')
    except (IOError, OSError):
        pass


def _api_headers(token=None):
    h = {'User-Agent': api_user_agent(), 'Accept': 'application/json, text/plain, */*'}
    if token:
        h['Authorization'] = 'Bearer %s' % token
    return h


# ---------------------------------------------------------------------------
# Belépés / token
# ---------------------------------------------------------------------------
def credentials():
    return ADDON.getSetting('email').strip(), ADDON.getSetting('password')


def have_credentials():
    e, p = credentials()
    return bool(e and p)


def saved_token():
    return (_read_json(TOKEN_FILE, {}) or {}).get('token')


def clear_token():
    try:
        os.remove(profile(TOKEN_FILE))
    except OSError:
        pass


def login():
    email, password = credentials()
    if not (email and password):
        raise LoginError('Add meg az email címet és a jelszót a beállításokban')
    last_fail = (_read_json(TOKEN_FILE, {}) or {}).get('failed', 0)
    if time.time() - last_fail < LOGIN_COOLDOWN:
        raise LoginError('Az előző belépés nem sikerült - 10 perc múlva próbálkozom újra '
                         '(vagy: Munkamenet törlése)')
    resp = _http(API + '/login', _api_headers(), params={'email': email, 'password': password})
    token = None
    try:
        token = resp.json().get('access_token')
    except ValueError:
        pass
    if resp.status_code == 200 and token:
        _write_json(TOKEN_FILE, {'token': token, 'ts': int(time.time())})
        log('Bejelentkezés sikeres.')
        return token
    _write_json(TOKEN_FILE, {'failed': int(time.time())})
    log('Bejelentkezés SIKERTELEN (HTTP %s): %s' % (resp.status_code, resp.text[:200]),
        xbmc.LOGWARNING)
    raise LoginError('Sikertelen belépés (HTTP %s) - ellenőrizd az email címet / jelszót'
                     % resp.status_code)


def token():
    return saved_token() or login()


def api_get(path, auth=True):
    """JSON a /api alól; 401/403-nál egyszer újra belép."""
    url = API + path
    tok = token() if auth else None
    resp = _http(url, _api_headers(tok))
    if auth and resp.status_code in (401, 403):
        log('Lejárt token (HTTP %s) - újrabelépés' % resp.status_code)
        clear_token()
        resp = _http(url, _api_headers(login()))
    if resp.status_code != 200:
        raise ApiError('HTTP %s: %s' % (resp.status_code, path))
    try:
        return resp.json()
    except ValueError:
        _save_debug('last_response.txt', resp.text)
        raise ApiError('Nem JSON válasz: %s' % path)


def cached(key, ttl, fetch):
    name = 'cache_%s.json' % re.sub(r'[^\w.-]', '_', key)[:80]
    data = _read_json(name)
    if data and time.time() - data.get('ts', 0) < ttl:
        return data['data']
    try:
        fresh = fetch()
    except ApiError:
        if data:
            log('hálózati hiba - a korábbi (%s) adat marad' % key, xbmc.LOGWARNING)
            return data['data']
        raise
    if fresh:
        _write_json(name, {'ts': time.time(), 'data': fresh})
    return fresh


def clear_cache():
    n = 0
    for name in os.listdir(profile()):
        if name.startswith('cache_'):
            try:
                os.remove(profile(name))
                n += 1
            except OSError:
                pass
    return n


# ---------------------------------------------------------------------------
# Tartalom
# ---------------------------------------------------------------------------
EXCLUDED = ('Élő közvetítések', 'Előzmények', 'Kedvenceim', 'Leading Articles',
            'Opinion Articles', 'Podcasts')


def image(item):
    if item.get('poster_remote'):
        return item['poster_remote']
    if item.get('thumbnail_remote'):
        return item['thumbnail_remote']
    if item.get('photo_thumbnail'):
        return STORAGE + item['photo_thumbnail']
    return ''


def collections():
    data = cached('collections', LIST_TTL, lambda: api_get('/collections'))
    out = []
    for c in data if isinstance(data, list) else []:
        if c.get('title') and c.get('slug') and c['title'] not in EXCLUDED:
            out.append({'title': c['title'], 'slug': c['slug'], 'thumb': image(c)})
    return out


def _vod(item):
    return {'title': item.get('title') or '', 'desc': (item.get('short_desc') or '').strip(),
            'thumb': image(item), 'url': item.get('vodviewer') or '',
            'plot': (item.get('long_desc') or item.get('description') or
                     item.get('short_desc') or '').strip()}


def collection_items(slug):
    # az alkalmazás a 11-es "oldal" paraméterrel kéri le a teljes listát
    data = cached('items_' + slug, LIST_TTL,
                  lambda: api_get('/collectionitems/%s/11' % quote(slug, ''), auth=False))
    if not isinstance(data, list) or not data:
        return []
    return [v for v in (_vod(i) for i in data[0].get('vodsavail') or []) if v['url']]


def search(term):
    data = api_get('/search/%s' % quote(term, ''), auth=False)
    return [v for v in (_vod(i) for i in (data if isinstance(data, list) else [])) if v['url']]


def live_events():
    data = api_get('/collectionitemslive/live/0')
    if not isinstance(data, list) or not data:
        return []
    out = []
    for e in data[0].get('liveeventsavail') or []:
        if e.get('slug'):
            out.append({'title': e.get('title') or '', 'desc': (e.get('short_desc') or '').strip(),
                        'slug': e['slug'], 'status': e.get('status') or '',
                        'start': e.get('expected_start') or '', 'stop': e.get('expected_stop') or '',
                        'thumb': image(e)})
    return out


def live_sources(slug):
    data = api_get('/watch/%s/live' % quote(slug, ''))
    return {'live': data.get('src'), 'replay': data.get('replaysrc')}


_PLAYBACK_RE = re.compile(r'playbackUrl.{0,40}?(https:[^"\'\s<>]*uplynk[^"\'\s<>]*)', re.S)


def vod_stream(viewer_url):
    """A vodviewer oldalból az Uplynk lejátszási URL."""
    resp = _http(viewer_url, {'User-Agent': FIREFOX_UA,
                              'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8'})
    m = _PLAYBACK_RE.search(resp.text)
    if not m:
        _save_debug('last_vodviewer.html', resp.text)
        raise ApiError('Nem található lejátszási URL (mentve: last_vodviewer.html)')
    return m.group(1).replace('\\/', '/')
