# -*- coding: utf-8 -*-
"""
Telekom TV GO (Magyar Telekom) - a player.telekomtvgo.hu webes kliens API-ja.

A webes kliens (W02.0.1470) kódjából feltérképezve (új kód):

Bejelentkezés (webes / SSO mód, mint a böngésző):
    GET  {BFF}/tenant/config?is_sso_enabled=true -> login_url (MediaKind STS) -> Telekom
         belépőoldal (email + jelszó) -> visszairányítás access_token + refresh_token-nel
    POST {BFF}/oauth/token?is_sso_enabled=true   grant_type=refresh_token (frissítés)
    Tartalék: a böngészőből kimásolt refreshToken a beállításokban.

Tartalom (bifrost, fejléc: bff_token = access_token):
    GET {BFF}/user/account               -> channelMap_id, request_url (MediaKind szerver)
    GET {BFF}/epg/channel                -> csatornák
    GET {BFF}/epg/channel/schedules      -> műsorújság (3 órás sávok)
    GET {BFF}/player/playinfo/channel/v3 -> élő adás lejátszási adatai
    GET {BFF}/player/playinfo/catchup    -> visszanézés
    BFF = https://tv-hu-prod.yo-digital.com/bifrost

Lejátszás (MediaKind "Azuki" szerver = user/account request_url):
    POST {srv}/v1/client/registrations?ownerUid=..        (eszköz-regisztráció)
    POST {srv}/v1/client/roll?mediaId=..&ownerUid=..&sessionId=..&enablelowlatency=false
                                          -> manifest_uri + cdns -> DASH (.mpd)
    POST {srv}/v1/client/get-widevine-license?...         (Widevine licenc)
    POST {srv}/v1/client/beacons?...                      (életjel lejátszás közben)
    Fejlécek: AzukiIMC, AuthorizationToken (= accessToken), ApplicationToken
    (= service_collection_id), DeviceProfile (base64 JSON).

Kímélet: 0,5 mp szünet a kérések között, csatornalista / műsorújság gyorsítótár,
token lemezen (lejárat előtt frissítés), sikertelen belépés után 3 perc szünet.
"""
import base64
import hashlib
import json
import os
import time
import uuid

from urllib.parse import quote, unquote

import xbmc
import xbmcaddon
import xbmcvfs

try:
    import requests
except ImportError:  # noqa
    requests = None

ADDON_ID = 'plugin.video.telekomtvgo'
ADDON = xbmcaddon.Addon(ADDON_ID)

BFF = 'https://tv-hu-prod.yo-digital.com/bifrost'
IMG = 'https://ottapp-akamai-client-a.proda.dtp.tv3cloud.com/images/images'
ORIGIN = 'https://player.telekomtvgo.hu'

NATCO_KEY = 'Tydx7H7fJO6HxgjvJok0ZhVWFmX3om0P'
APP_KEY = 'exSJHBiSAN6wAAeqdWLdTUfdTi2PNark'       # CMS_CONFIGURATION_API_KEY
APP_VERSION = '02.0.1470'
COUNTRY = 'hu'
LANG = 'hu'
DEVICE_TYPE = 'WEB'
AZUKI_IMC = 'IMC7.6.0_XX_Dx.x.x_Sx'

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/140.0.0.0 Safari/537.36')
OS_NAME = 'Windows'
BROWSER = 'Chrome'
BROWSER_MAJOR = '140'
# a webes kliens induláskor így tölti ki (react-device-detect: browserName-browserVersion);
# üresen a bifrost (AWS ELB) üres HTTP 500-zal válaszol
X_USER_AGENT = 'web|web|%s-%s|%s|1' % (BROWSER, BROWSER_MAJOR, APP_VERSION)

MIN_GAP = 0.5
LOGIN_COOLDOWN = 180
TOKEN_FILE = 'token.json'
CHANNEL_TTL = 6 * 3600
SCHEDULE_TTL = 3600
ACCOUNT_TTL = 12 * 3600

_SESSION = None
_LAST = [0.0]
_SESSION_ID = [None]


class ApiError(Exception):
    pass


class LoginError(ApiError):
    pass


def log(msg, level=xbmc.LOGINFO):
    xbmc.log('[%s] %s' % (ADDON_ID, msg), level)


# ---------------------------------------------------------------------------
# Profil-mappa, JSON
# ---------------------------------------------------------------------------
def profile(name=''):
    prof = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
    if not os.path.isdir(prof):
        try:
            os.makedirs(prof)
        except OSError:
            pass
    return os.path.join(prof, name)


def _read_json(name, default=None):
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


def _debug_dump(name, data):
    """Nyers válasz mentése a profil-mappába (Beállítások -> Hibakeresés)."""
    if ADDON.getSetting('debug_dump') != 'true':
        return
    try:
        with open(profile('debug_%s.json' % name), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
    except (IOError, OSError, TypeError, ValueError):
        pass


def clear_cache():
    n = 0
    for fn in os.listdir(profile()):
        if fn.startswith(('cache_', 'debug_', 'error_', 'login_steps', 'login_page')):
            try:
                os.remove(profile(fn))
                n += 1
            except OSError:
                pass
    return n


def _cache_get(key, ttl):
    data = _read_json('cache_%s.json' % key)
    if data and time.time() - data.get('t', 0) < ttl:
        return data.get('v')
    return None


def _cache_set(key, value):
    _write_json('cache_%s.json' % key, {'t': time.time(), 'v': value})


# ---------------------------------------------------------------------------
# Eszköz-azonosító (állandó, hogy a Telekom-fiókban egy eszköznek látsszon)
# ---------------------------------------------------------------------------
def device_id():
    dev = _read_json('device.json', {}) or {}
    if not dev.get('id'):
        dev['id'] = str(uuid.uuid4())
        # MediaKind eszköz-UUID: getUUID().replace('-', '') - csak az első kötőjelet cseréli
        dev['mk_uuid'] = str(uuid.uuid4()).replace('-', '', 1)
        _write_json('device.json', dev)
    return dev['id']


def _mk_uuid():
    device_id()
    return (_read_json('device.json', {}) or {}).get('mk_uuid') or ''


def _session_id():
    if not _SESSION_ID[0]:
        _SESSION_ID[0] = str(uuid.uuid4())
    return _SESSION_ID[0]


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def session():
    global _SESSION
    if _SESSION is None:
        if requests is None:
            raise ApiError('Hiányzik a script.module.requests')
        _SESSION = requests.Session()
        _SESSION.headers.update({'User-Agent': UA, 'Origin': ORIGIN, 'Referer': ORIGIN + '/',
                                 'Accept': 'application/json, text/plain, */*',
                                 'Accept-Language': 'hu-HU,hu;q=0.9'})
    return _SESSION


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


def _request(method, url, params=None, headers=None, data=None, timeout=25):
    gap = time.time() - _LAST[0]
    if gap < MIN_GAP:
        time.sleep(MIN_GAP - gap)
    _LAST[0] = time.time()
    _bump()
    log('%s %s' % (method, url.split('?')[0]))
    try:
        return session().request(method, url, params=params, headers=headers, data=data,
                                 timeout=timeout)
    except requests.exceptions.RequestException as exc:
        raise ApiError('Hálózati hiba: %s' % exc)


def _json(resp, what):
    try:
        return resp.json()
    except ValueError:
        raise ApiError('%s: nem JSON válasz (HTTP %d)' % (what, resp.status_code))


def _err_text(resp):
    try:
        data = resp.json()
    except ValueError:
        return 'HTTP %d' % resp.status_code
    if isinstance(data, dict):
        for k in ('displayMessage', 'message', 'error_description', 'errorMessage', 'error',
                  'hal_code', 'code'):
            v = data.get(k)
            if v and isinstance(v, (str, int)):
                return 'HTTP %d: %s' % (resp.status_code, v)
    return 'HTTP %d' % resp.status_code


def _common_headers():
    """A webes kliens axios-interceptorának fejlécei (natív login és bifrost)."""
    tracking = str(uuid.uuid4())
    call_time = str(int(time.time() * 1000))
    sid = _session_id()
    txn = hashlib.sha256((tracking + sid + device_id() + call_time).encode()).hexdigest()[:32]
    return {
        'DeviceId': device_id(),
        'app_key': APP_KEY,
        'app_version': APP_VERSION,
        'X-User-Agent': X_USER_AGENT,
        'x-request-trackingid': tracking,
        'x-txn-id': txn,
        'x-call-time': call_time,
        'x-request-session-id': sid,
        'Device-Name': '%s - %s' % (OS_NAME, BROWSER),
        'Pragma': 'akamai-x-cache-on,akamai-x-checkcacheable,akamai-x-get-cache-key',
        'tenant': 'tv',
    }


# ---------------------------------------------------------------------------
# Bejelentkezés - webes (SSO) mód, mint a player.telekomtvgo.hu (LOGIN_TYPE = "web")
#
#   1. GET  {BFF}/tenant/config?is_sso_enabled=true      -> login_url (MediaKind STS)
#   2. a login_url átirányít a Telekom belépőoldalára; email + jelszó beküldése után a
#      visszairányítás a player.telekomtvgo.hu-ra megy, access_token + refresh_token
#      paraméterekkel (a böngészőben ezek lesznek a "bffToken" / "refreshToken" sütik)
#   3. POST {BFF}/oauth/token?is_sso_enabled=true   grant_type=refresh_token (frissítés)
#
# Tartalék: a böngészőből kimásolt refreshToken beilleszthető a beállításokba.
# ---------------------------------------------------------------------------
LOGIN_STEPS = 14
USER_FIELD_HINTS = ('email', 'user', 'login', 'name', 'identifier', 'msisdn', 'account',
                    'azonosito', 'felhasznalo')


def have_credentials():
    return bool((ADDON.getSetting('email') and ADDON.getSetting('password')) or
                ADDON.getSetting('refresh_token').strip() or
                os.path.exists(profile('refresh_token.txt')))


def _cred_key():
    raw = '\n'.join((ADDON.getSetting('email').strip(), ADDON.getSetting('password'),
                     ADDON.getSetting('refresh_token').strip()))
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()


def _version():
    try:
        return ADDON.getAddonInfo('version')
    except Exception:  # noqa
        return ''


def saved_token():
    return _read_json(TOKEN_FILE, {}) or {}


def clear_token():
    for fn in (TOKEN_FILE, 'cache_account.json', 'login_state.json'):
        try:
            os.remove(profile(fn))
        except OSError:
            pass


def save_error(name, resp=None, note='', attempts=None):
    """Hibás válasz mentése (mindig, titkok nélkül): error_<név>.json a profil-mappában."""
    data = {'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'note': note}
    if resp is not None:
        data.update(_resp_info(resp))
    if attempts:
        data['attempts'] = attempts
    _write_json('error_%s.json' % name, data)


def _resp_info(resp):
    secret = ('bff_token', 'authorizationtoken', 'refresh_token', 'cookie', 'set-cookie',
              'ms_access_token')
    req = getattr(resp, 'request', None)
    return {'url': resp.url.split('?')[0], 'status': resp.status_code,
            'content_type': resp.headers.get('content-type', ''),
            'response_headers': dict((k, v) for k, v in resp.headers.items()
                                     if k.lower() not in secret),
            'request_headers': dict((k, v) for k, v in (req.headers.items() if req else [])
                                    if k.lower() not in secret),
            'body': _redact((resp.text or '')[:6000])}


def _redact(text):
    import re
    return re.sub(r'((?:access|refresh|id)_?[Tt]oken["\'=:\s]+)[A-Za-z0-9._\-]{12,}',
                  r'\1***', text or '')


def _save_tokens(access, refresh_tok, expires_in=None, extra=None):
    tok = saved_token()
    if access:
        tok['access'] = access
    if refresh_tok:
        tok['refresh'] = refresh_tok
    try:
        exp = int(expires_in or 0)
    except (TypeError, ValueError):
        exp = 0
    if exp > 10 ** 7:          # ezredmásodperc
        exp //= 1000
    tok['expires'] = time.time() + (exp or 3600) - 120
    tok['cred'] = _cred_key()
    if extra:
        tok.update(extra)
    _write_json(TOKEN_FILE, tok)
    return tok


def _tokens_from(obj):
    """access/refresh token + lejárat JSON-ból vagy URL-ből (query és # rész)."""
    if isinstance(obj, dict):
        acc = _first(obj, 'access_token', 'accessToken', 'bff_token', 'bffToken')
        ref = _first(obj, 'refresh_token', 'refreshToken')
        exp = _first(obj, 'expires_in', 'accessExpiresIn', 'expiresIn')
        if not acc:
            for v in obj.values():
                if isinstance(v, dict):
                    r = _tokens_from(v)
                    if r[0]:
                        return r
        return acc, ref, exp
    if isinstance(obj, str) and obj:
        from urllib.parse import urlsplit, parse_qs
        parts = urlsplit(obj.strip())
        q = {}
        for chunk in (parts.query, parts.fragment):
            for k, v in parse_qs(chunk).items():
                q[k] = v[0]
            if '?' in chunk:      # pl. "#/?access_token=..."
                for k, v in parse_qs(chunk.split('?', 1)[1]).items():
                    q[k] = v[0]
        return (_first(q, 'access_token', 'accessToken', 'bffToken'),
                _first(q, 'refresh_token', 'refreshToken'), _first(q, 'expires_in'))
    return None, None, None


def _guest_headers():
    h = _common_headers()
    h['X-Call-Type'] = 'GUEST_USER'
    h['DeviceDensity'] = 'xhdpi'
    return h


def refresh():
    tok = saved_token()
    if not tok.get('refresh'):
        return None
    h = _common_headers()
    h['bff_token'] = tok.get('access', '')
    h['X-Call-Type'] = 'AUTH_USER' if tok.get('access') else 'GUEST_USER'
    h['DeviceDensity'] = 'xhdpi'
    h['Content-Type'] = 'application/x-www-form-urlencoded'
    params = {'is_sso_enabled': 'true', 'app_language': LANG, 'natco_code': COUNTRY}
    from urllib.parse import urlencode
    resp = _request('POST', BFF + '/oauth/token', params=params, headers=h,
                    data=urlencode({'grant_type': 'refresh_token',
                                    'refresh_token': tok['refresh']}))
    if resp.status_code >= 400:
        save_error('refresh', resp)
        log('Tokenfrissítés sikertelen: %s' % _err_text(resp), xbmc.LOGWARNING)
        return None
    try:
        data = resp.json()
    except ValueError:
        save_error('refresh', resp, 'nem JSON')
        return None
    acc, ref, exp = _tokens_from(data)
    if not acc:
        save_error('refresh', resp, 'nincs access_token')
        return None
    log('Token frissítve')
    return _save_tokens(acc, ref, exp)


def _import_manual_token():
    """A beállításokba beillesztett refreshToken (vagy a teljes visszairányítási URL).
    Távirányítóval kényelmetlen, ezért a profil-mappába tett refresh_token.txt is jó."""
    raw = ADDON.getSetting('refresh_token').strip()
    if not raw:
        try:
            with open(profile('refresh_token.txt'), 'r', encoding='utf-8-sig') as f:
                raw = ''.join(f.read().split())
        except (IOError, OSError):
            raw = ''
    if not raw:
        return None
    acc, ref, exp = _tokens_from(raw) if ('=' in raw or '://' in raw) else (None, raw, None)
    if not ref and not acc:
        raise LoginError('A beillesztett szövegben nem találtam refresh tokent.')
    tok = saved_token()
    if tok.get('manual') == hashlib.sha1(raw.encode()).hexdigest():
        return None            # ezt már felhasználtuk (és azóta lejárt)
    _write_json(TOKEN_FILE, {'refresh': ref, 'access': acc or '', 'expires': 0,
                             'manual': hashlib.sha1(raw.encode()).hexdigest(),
                             'cred': _cred_key()})
    new = refresh()
    if new and new.get('access'):
        new['manual'] = hashlib.sha1(raw.encode()).hexdigest()
        _write_json(TOKEN_FILE, new)
        return new
    if acc:
        return _save_tokens(acc, ref, exp, {'manual': hashlib.sha1(raw.encode()).hexdigest()})
    raise LoginError('A beillesztett refresh token nem érvényes (lejárt vagy hibás). '
                     'Részletek: error_refresh.json a profil-mappában.')


# --- automatikus webes belépés ------------------------------------------------
def _tenant_variants():
    """A webes kliens fejlécei (token nélkül, START_UP / CONFIG lépés), majd egyszerűbb
    változatok - ha a szerver egy fejlécre 500-zal felel."""
    web = _guest_headers()
    web['x-tvflow'] = 'START_UP'
    web['x-tv-step'] = 'CONFIG'
    lite = dict((k, web[k]) for k in ('DeviceId', 'app_key', 'app_version', 'tenant', 'X-User-Agent',
                                      'X-Call-Type', 'DeviceDensity'))
    return (('web', web), ('lite', lite), ('bare', {}))


def _tenant_login_url():
    q = {'is_sso_enabled': 'true', 'app_language': LANG, 'natco_code': COUNTRY}
    attempts = []
    resp = None
    for name, headers in _tenant_variants():
        resp = _request('GET', BFF + '/tenant/config', params=q, headers=headers)
        attempts.append(dict(_resp_info(resp), variant=name))
        if resp.status_code < 400:
            if name != 'web':
                log('tenant/config csak "%s" fejlécekkel ment' % name, xbmc.LOGWARNING)
            break
    if resp.status_code >= 400:
        save_error('tenant_config', note='minden változat sikertelen', attempts=attempts)
        raise LoginError('A belépési beállítás nem tölthető le (%s). Részletek: '
                         'error_tenant_config.json' % _err_text(resp))
    data = _json(resp, 'Belépési beállítás')
    _debug_dump('tenant_config', data)
    d = _find_dict(data, 'login_url') or {}
    url = (d.get('login_url') or '').replace('%s&amp;', '&').replace('&amp;', '&')
    if not url:
        save_error('tenant_config', resp, 'nincs login_url')
        raise LoginError('A belépési beállításban nincs login_url')
    redirect = quote('%s/?redirectUrl=/?end=1' % ORIGIN, safe='')
    url = url.replace('${redirectUri}', redirect)
    for k, v in (('${deviceId}', device_id()), ('${deviceType}', DEVICE_TYPE),
                 ('${deviceTypeV2}', DEVICE_TYPE), ('${tenantName}', 'hu')):
        url = url.replace(k, quote(v, safe=''))
    return url


class _FormParser(object):
    """Egyszerű <form>/<input> gyűjtő (html.parser alapon)."""

    def __init__(self, html):
        from html.parser import HTMLParser
        forms = self.forms = []
        meta = self.meta = []

        class P(HTMLParser):
            def handle_starttag(self, tag, attrs):
                a = dict((k.lower(), v or '') for k, v in attrs)
                if tag == 'form':
                    forms.append({'action': a.get('action', ''),
                                  'method': (a.get('method') or 'post').lower(),
                                  'id': a.get('id', ''), 'inputs': []})
                elif tag in ('input', 'button', 'select') and forms and a.get('name'):
                    forms[-1]['inputs'].append({'name': a['name'],
                                                'type': (a.get('type') or 'text').lower(),
                                                'value': a.get('value', ''),
                                                'id': a.get('id', ''),
                                                'tag': tag})
                elif tag == 'meta' and a.get('http-equiv', '').lower() == 'refresh':
                    meta.append(a.get('content', ''))
        p = P()
        try:
            p.feed(html or '')
        except Exception:  # noqa - hibás HTML
            pass


def _pick_form(forms):
    def has(form, types):
        return any(i['type'] in types for i in form['inputs'])
    # a Telekom belépőoldalán: <form id="login-form"> (mellette egy "vissza" űrlap is van)
    for f in forms:
        if f['id'] == 'login-form':
            return f
    for types in (('password',), ('email', 'text', 'tel')):
        for f in forms:
            if has(f, types):
                return f
    return forms[0] if forms else None


def _login_type(ident):
    """A belépőoldal getLoginType()-ja: email / telefonszám -> "TF", különben "MTID"."""
    import re
    x = ident.replace(' ', '')
    if '@' in x or re.match(r'^(\+?36|06)?(20|30|31|50|70)\d{7}$', x):
        return 'TF'
    return 'MTID'


def _fill_form(form, email, password):
    data = {}
    used_user = used_pw = False
    submit = None
    for i in form['inputs']:
        t, name = i['type'], i['name']
        low = (name + ' ' + i['id']).lower()
        if t == 'password':
            data[name] = password
            used_pw = True
        elif t in ('email', 'text', 'tel') and not i['value'] and \
                any(h in low for h in USER_FIELD_HINTS):
            data[name] = email
            used_user = True
        elif t in ('checkbox', 'radio'):
            if 'remember' in low or 'stay' in low:
                data[name] = i['value'] or 'on'
        elif t in ('submit', 'button', 'image', 'reset') or i['tag'] == 'button':
            # a "Belépés" gomb értéke (button=default) kell; a "vissza" / SMS / egyszer
            # használatos kód gombokat nem nyomjuk meg
            if i['value'] in ('default', 'stayLoggedIn') or (submit is None and i['value'] and
                                           i['value'].lower() not in ('back',) and
                                           not i['value'].lower().startswith('loginwith')):
                if submit is None or i['value'] in ('default', 'stayLoggedIn'):
                    submit = (name, i['value'])
            continue
        elif t == 'hidden' and name.lower() == 'logintype' and not i['value']:
            data[name] = _login_type(email)
        else:
            data[name] = i['value']
    if not used_user and not used_pw:
        # nincs felismert mező: az első üres szövegmezőbe az email
        for i in form['inputs']:
            if i['type'] in ('email', 'text') and not i['value']:
                data[i['name']] = email
                used_user = True
                break
    if submit and (used_pw or submit[1] in ('default', 'stayLoggedIn')):
        data[submit[0]] = submit[1]
    return data, used_user, used_pw


def _sts_login():
    import re
    from urllib.parse import urljoin
    email = ADDON.getSetting('email').strip()
    password = ADDON.getSetting('password')
    url = _tenant_login_url()
    s = requests.Session()
    s.headers.update({'User-Agent': UA, 'Accept-Language': 'hu-HU,hu;q=0.9',
                      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,'
                                '*/*;q=0.8'})
    method, data, referer = 'GET', None, ORIGIN + '/'
    steps = []
    pw_sent = user_sent = 0
    captcha = False
    for step in range(LOGIN_STEPS):
        _LAST[0] = time.time()
        _bump()
        try:
            resp = s.request(method, url, data=data, allow_redirects=False, timeout=25,
                             headers={'Referer': referer})
        except requests.exceptions.RequestException as exc:
            raise LoginError('Hálózati hiba a belépésnél: %s' % exc)
        loc = resp.headers.get('Location', '')
        steps.append({'n': step, 'method': method, 'url': url.split('?')[0],
                      'status': resp.status_code, 'location': _redact(loc.split('?')[0]),
                      'fields': sorted((data or {}).keys())})
        log('belépés %d: %s %s -> %d' % (step, method, url.split('?')[0], resp.status_code))
        for cand in (loc, resp.url):
            acc, ref, exp = _tokens_from(cand) if cand else (None, None, None)
            if acc:
                _write_json('login_steps.json', {'steps': steps, 'result': 'ok'})
                return acc, ref, exp
        if loc:
            referer, url = url, urljoin(url, loc)
            method, data = 'GET', None
            continue
        html = resp.text or ''
        m = re.search(r'[?&#](access_token=[^"\'\s<>]+)', html)
        if m:
            acc, ref, exp = _tokens_from('https://x/?' + m.group(1).replace('&amp;', '&'))
            if acc:
                _write_json('login_steps.json', {'steps': steps, 'result': 'ok (html)'})
                return acc, ref, exp
        fp = _FormParser(html)
        if resp.status_code >= 400 and not fp.forms:
            break
        nxt = None
        for c in fp.meta:
            if 'url=' in c.lower():
                nxt = c.split('=', 1)[1].strip(' \'"')
        if not nxt:
            m = re.search(r'(?:window\.)?location(?:\.href)?\s*=\s*["\']([^"\']+)["\']', html)
            if m and not fp.forms:
                nxt = m.group(1)
        if nxt:
            referer, url = url, urljoin(url, nxt)
            method, data = 'GET', None
            continue
        form = _pick_form(fp.forms)
        if not form:
            break
        fields, used_user, used_pw = _fill_form(form, email, password)
        if used_user and not used_pw:
            user_sent += 1
            if user_sent > 1:
                # az azonosító-oldal újra megjelent: a láthatatlan reCAPTCHA nélkül nem enged
                steps[-1]['note'] = 'az azonosító-oldal újra megjelent' + (
                    ' (reCAPTCHA)' if captcha else '')
                _write_json('login_steps.json', {'steps': steps, 'result': 'captcha?'})
                with open(profile('login_page.html'), 'w', encoding='utf-8') as f:
                    f.write(_redact(html))
                raise LoginError(
                    'A Telekom belépőoldala robotellenőrzést (reCAPTCHA) kér, ezért az '
                    'automatikus belépés nem megy. Jelentkezz be egyszer böngészőben a '
                    'player.telekomtvgo.hu-n, és a "refreshToken" süti értékét illeszd be: '
                    'Beállítások -> Belépés -> Refresh token.')
            captcha = captcha or 'g-recaptcha' in html
        if used_pw:
            pw_sent += 1
            if pw_sent > 1:
                steps[-1]['note'] = 'a jelszóűrlap újra megjelent'
                _write_json('login_steps.json', {'steps': steps, 'result': 'hibás adatok?'})
                with open(profile('login_page.html'), 'w', encoding='utf-8') as f:
                    f.write(_redact(html))
                raise LoginError('A Telekom belépőoldala nem fogadta el az email címet / '
                                 'jelszót. Ellenőrizd őket (ugyanazok, mint a '
                                 'player.telekomtvgo.hu-n).')
        referer = url
        url = urljoin(url, form['action'] or url)
        method = 'POST' if form['method'] != 'get' else 'GET'
        data = fields
        if method == 'GET':
            from urllib.parse import urlencode
            url = url.split('?')[0] + '?' + urlencode(fields)
            data = None
    _write_json('login_steps.json', {'steps': steps, 'result': 'sikertelen'})
    try:
        with open(profile('login_page.html'), 'w', encoding='utf-8') as f:
            f.write(_redact(resp.text or ''))
    except (IOError, OSError, NameError):
        pass
    raise LoginError('Az automatikus belépés nem sikerült. Küldd el a login_steps.json és '
                     'login_page.html fájlt, vagy használd a beállításokban a refresh token '
                     'beillesztését.')


def login():
    """Belépés: kézi refresh token, különben automatikus webes (SSO) belépés."""
    if not have_credentials():
        raise LoginError('Add meg a Telekom-fiókod email címét és jelszavát a beállításokban '
                         '(vagy illeszd be a böngészőből a refresh tokent).')
    manual = _import_manual_token()
    if manual:
        return manual
    if not (ADDON.getSetting('email') and ADDON.getSetting('password')):
        raise LoginError('A beillesztett refresh token lejárt. Illessz be újat, vagy add meg '
                         'az email címet és a jelszót.')
    state = _read_json('login_state.json', {}) or {}
    if state.get('cred') == _cred_key() and state.get('ver') == _version() and \
            time.time() - state.get('failed', 0) < LOGIN_COOLDOWN:
        raise LoginError('Az előző belépés nem sikerült (%s). Várj pár percet, vagy módosítsd '
                         'az adataidat.' % state.get('reason', ''))
    try:
        acc, ref, exp = _sts_login()
    except LoginError as exc:
        _write_json('login_state.json', {'failed': time.time(), 'reason': str(exc)[:120],
                                         'cred': _cred_key(), 'ver': _version()})
        raise
    _write_json('login_state.json', {})
    log('Belépés sikeres')
    return _save_tokens(acc, ref, exp)


def access_token(force=False):
    tok = saved_token()
    if tok.get('cred') and tok.get('cred') != _cred_key():
        clear_token()          # megváltoztak a belépési adatok
        tok = {}
    if not force and tok.get('access') and time.time() < tok.get('expires', 0):
        return tok['access']
    if tok.get('refresh'):
        new = refresh()
        if new and new.get('access'):
            return new['access']
    return login()['access']


# ---------------------------------------------------------------------------
# bifrost
# ---------------------------------------------------------------------------
def _bff_headers(token, account=None):
    h = _common_headers()
    h['bff_token'] = token
    h['DeviceDensity'] = 'xhdpi'
    h['X-Call-Type'] = 'AUTH_USER'
    if account:
        if account.get('channelMap_id'):
            h['X-Channel-Map-Id'] = str(account['channelMap_id'])
        if account.get('user_id'):
            h['x-user-id'] = str(account['user_id'])
        h['x-account-details'] = json.dumps({
            'accountType': account.get('account_type'), 'userId': account.get('user_id'),
            'recordingEnabledDVR': account.get('is_recording_enabled'),
            'channelMapId': account.get('channelMap_id'),
            'rightsGroupIds': account.get('rightsGroup_ids'),
            'releaseSlot': account.get('release_slot'),
            'accountId': account.get('account_id')}, separators=(',', ':'))
    return h


def bff_get(path, params=None, account=None, what='API'):
    q = dict(params or {})
    q['app_language'] = LANG
    q['natco_code'] = COUNTRY
    for attempt in (0, 1):
        token = access_token(force=bool(attempt))
        resp = _request('GET', BFF + path, params=q, headers=_bff_headers(token, account))
        if resp.status_code == 401 and not attempt:
            log('401 - új token', xbmc.LOGWARNING)
            continue
        if resp.status_code >= 400:
            raise ApiError('%s: %s' % (what, _err_text(resp)))
        return _json(resp, what)
    raise ApiError('%s: nincs jogosultság (401)' % what)


def account(force=False):
    if not force:
        cached = _cache_get('account', ACCOUNT_TTL)
        if cached:
            return cached
    data = bff_get('/user/account', what='Fiókadatok')
    _debug_dump('account', data)
    acc = _find_dict(data, 'channelMap_id') or _find_dict(data, 'request_url') or data
    if not isinstance(acc, dict):
        raise ApiError('Ismeretlen fiókadat-válasz')
    _cache_set('account', acc)
    return acc


# ---------------------------------------------------------------------------
# Segédek a (nem dokumentált) JSON-válaszokhoz
# ---------------------------------------------------------------------------
def _walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            for x in _walk(v):
                yield x
    elif isinstance(obj, list):
        for v in obj:
            for x in _walk(v):
                yield x


def _find_dict(obj, key):
    for d in _walk(obj):
        if key in d:
            return d
    return None


def _first(d, *keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, '', [], {}):
            return v
    return None


def _img_url(v):
    if isinstance(v, dict):
        v = _first(v, 'url', 'href', 'src', 'image_url', 'logo')
    if isinstance(v, list) and v:
        return _img_url(v[0])
    if isinstance(v, str) and v:
        if v.startswith('//'):
            return 'https:' + v
        if v.startswith('/'):
            return IMG + v
        return v
    return ''


def station_logo(station_id):
    return '%s/station/%s/4x3/logomedium.png' % (IMG, station_id) if station_id else ''


def program_image(program_id):
    return '%s/program/%s/16x9/keyartxxlarge.jpg' % (IMG, program_id) if program_id else ''


# ---------------------------------------------------------------------------
# Csatornák, műsorújság
# ---------------------------------------------------------------------------
def channels(force=False):
    if not force:
        cached = _cache_get('channels', CHANNEL_TTL)
        if cached:
            return cached
    acc = account()
    params = {'natco_key': NATCO_KEY, 'channelMap_id': acc.get('channelMap_id') or '',
              'includeVirtualChannels': 'true', 'includeSyntheticChannels': 'true'}
    data = bff_get('/epg/channel', params, acc, 'Csatornalista')
    _debug_dump('channels', data)
    out = []
    seen = set()
    for d in _walk(data):
        num = d.get('channel_number')
        if num in (None, '') or not _first(d, 'title', 'name', 'channel_name', 'call_letters',
                                           'station_id'):
            continue
        if num in seen:
            continue
        seen.add(num)
        station = _first(d, 'station_id', 'stationId', 'id')
        name = _first(d, 'title', 'name', 'channel_name', 'display_name', 'call_letters') or \
            'Csatorna %s' % num
        logo = _img_url(_first(d, 'channel_logo', 'logo', 'logo_url', 'image', 'images')) or \
            station_logo(station)
        out.append({'number': num, 'station': str(station or ''), 'name': name, 'logo': logo,
                    'is_audio': bool(d.get('is_audio')),
                    'catchup': d.get('is_catchup_enabled')})
    try:
        out.sort(key=lambda c: int(c['number']))
    except (TypeError, ValueError):
        pass
    if not out:
        raise ApiError('Üres csatornalista (a nyers válasz a hibakeresési mentésben)')
    _cache_set('channels', out)
    return out


def _schedule_block(date, hour_offset, acc):
    key = 'sched_%s_%02d' % (date, hour_offset)
    cached = _cache_get(key, SCHEDULE_TTL)
    if cached is not None:
        return cached
    params = {'natco_key': NATCO_KEY, 'date': date, 'hour_offset': hour_offset,
              'hour_range': 3, 'channelMap_id': acc.get('channelMap_id') or '',
              'filler': 'true', 'img_required': 'true', 'includeSyntheticChannels': 'true',
              'isFullDescriptionRequired': 'true'}
    data = bff_get('/epg/channel/schedules', params, acc, 'Műsorújság')
    _debug_dump('schedules', data)
    progs = []
    _collect_programs(data, None, None, progs)
    _cache_set(key, progs)
    return progs


def _collect_programs(obj, chan, station, out):
    """A programokat (start_time + program_id / title) a legközelebbi csatorna-adattal."""
    if isinstance(obj, list):
        for v in obj:
            _collect_programs(v, chan, station, out)
        return
    if not isinstance(obj, dict):
        return
    chan = obj.get('channel_number', chan)
    station = obj.get('station_id', station)
    if obj.get('start_time') and obj.get('end_time') and _first(obj, 'program_id', 'title',
                                                                 'name'):
        out.append({
            'channel': chan, 'station': str(station or ''),
            'program_id': obj.get('program_id') or '',
            'title': _first(obj, 'title', 'name', 'episode_name') or '',
            'episode': _first(obj, 'episode_name', 'episode_title') or '',
            'desc': _first(obj, 'description', 'long_description', 'short_description',
                           'synopsis') or '',
            'start': obj.get('start_time'), 'end': obj.get('end_time'),
            'image': _img_url(_first(obj, 'image_url', 'images', 'image', 'poster')) or
            program_image(obj.get('program_id')),
            'catchup': _first(obj, 'is_catchup_enabled', 'catchup_enabled', 'is_catchup'),
        })
        return
    for v in obj.values():
        if isinstance(v, (list, dict)):
            _collect_programs(v, chan, station, out)


def parse_time(value):
    """ISO UTC ('2026-09-26T16:29:00Z') vagy epoch (s / ms) -> epoch másodperc."""
    if value in (None, ''):
        return 0
    if isinstance(value, (int, float)):
        return value / 1000.0 if value > 10 ** 11 else float(value)
    s = str(value).strip()
    if s.isdigit():
        return parse_time(int(s))
    import calendar
    s = s.replace('Z', '').split('+')[0]
    for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S'):
        try:
            return calendar.timegm(time.strptime(s, fmt))
        except ValueError:
            continue
    return 0


def schedule_day(channel_number, day_epoch):
    """Egy csatorna egy (helyi) napja: 8 db 3 órás sáv, időrendben."""
    acc = account()
    lt = time.localtime(day_epoch)
    date = time.strftime('%Y-%m-%d', lt)
    progs = []
    for off in range(0, 24, 3):
        for p in _schedule_block(date, off, acc):
            if str(p['channel']) == str(channel_number):
                progs.append(p)
    uniq = {}
    for p in progs:
        uniq[(p['program_id'], p['start'])] = p
    return sorted(uniq.values(), key=lambda p: parse_time(p['start']))


def now_playing(channel_number):
    now = time.time()
    lt = time.localtime(now)
    date = time.strftime('%Y-%m-%d', lt)
    off = (lt.tm_hour // 3) * 3
    try:
        for p in _schedule_block(date, off, account()):
            if str(p['channel']) == str(channel_number) and \
                    parse_time(p['start']) <= now < parse_time(p['end']):
                return p
    except ApiError as exc:
        log('Műsoradat hiba: %s' % exc, xbmc.LOGWARNING)
    return None


# ---------------------------------------------------------------------------
# Lejátszás: bifrost playinfo -> MediaKind registrations / roll
# ---------------------------------------------------------------------------
def playinfo_live(channel_number, program_id=None):
    params = {'natco_key': NATCO_KEY, 'device_type': DEVICE_TYPE,
              'channel_number': channel_number}
    if program_id:
        params['program_id'] = program_id
    data = bff_get('/player/playinfo/channel/v3', params, account(), 'Élő adás')
    _debug_dump('playinfo_live', data)
    return data


def playinfo_catchup(program_id, station_id, start, end):
    params = {'program_id': program_id, 'natco_key': NATCO_KEY, 'device_type': DEVICE_TYPE,
              'station_id': station_id or '', 'start_time': start or '', 'end_time': end or ''}
    data = bff_get('/player/playinfo/catchup', params, account(), 'Visszanézés')
    _debug_dump('playinfo_catchup', data)
    return data


def _mk_url(base, path, params=None):
    url = '%s/%s' % (base, path)          # a webes SDK is így fűzi ("...com//v1/...")
    if params:
        url += ('&' if '?' in url else '?') + '&'.join(
            '%s=%s' % (quote(str(k), ''), quote('' if v is None else str(v), ''))
            for k, v in params.items())
    return url


def device_profile():
    prof = {'model': 'Desktop', 'osVersion': '10', 'vendorName': 'Microsoft',
            'osName': 'HTML5', 'deviceUUID': _mk_uuid(), 'wvLevel': 'L3',
            'supportsHevcDecode': False}
    return base64.b64encode(json.dumps(prof, separators=(',', ':')).encode()).decode()


class Playback(object):
    """Egy MediaKind lejátszási munkamenet (registrations + roll + beacons)."""

    def __init__(self, info):
        pb = _find_dict(info, 'service_items') or {}
        items = pb.get('service_items') or [{}]
        item = items[0] if isinstance(items, list) and items else {}
        self.media_id = item.get('media_id') or ''
        self.owner = item.get('owner_id') or 'hu001'
        self.app_token = pb.get('service_collection_id') or ''
        self.asset_type = (pb.get('type') or 'live').lower()
        self.start_time = pb.get('start_time')
        self.program = pb
        acc = account()
        self.server = (acc.get('request_url') or '').strip()
        self.inhome = 'yes' if str(acc.get('account_type_in_home')).lower() in (
            'true', 'yes', '1') else 'no'
        self.session_id = str(uuid.uuid4())
        self.token = access_token()
        self.is_live = self.asset_type in ('live', 'event')
        self.beacon_interval = 0
        if not self.media_id:
            raise ApiError('A lejátszási adatokban nincs media_id (lehet, hogy a csatorna nem '
                           'része az előfizetésednek).')
        if not self.server:
            raise ApiError('A fiókadatokban nincs MediaKind szervercím (request_url).')

    def headers(self):
        h = {'AzukiIMC': AZUKI_IMC, 'Content-Type': 'text/plain',
             'AuthorizationToken': self.token, 'DeviceProfile': device_profile(),
             'User-Agent': UA, 'Origin': ORIGIN, 'Referer': ORIGIN + '/'}
        if self.app_token:
            h['ApplicationToken'] = str(self.app_token)
        return h

    def _post(self, path, params, body, what):
        url = _mk_url(self.server, path, params)
        resp = _request('POST', url, headers=self.headers(), data=json.dumps(body))
        # az SDK a 200-at és a 466-499 közötti (hibaleíró JSON-t adó) válaszokat dolgozza fel
        if resp.status_code != 200 and not 466 <= resp.status_code < 500:
            raise ApiError('%s: HTTP %d' % (what, resp.status_code))
        return _json(resp, what)

    def register(self):
        data = self._post('v1/client/registrations', {'ownerUid': self.owner}, {},
                          'Eszköz-regisztráció')
        _debug_dump('mk_registration', data)
        if data.get('result') != 'success':
            r = data.get('response') or {}
            raise ApiError('Eszköz-regisztráció: %s %s' % (r.get('code', ''),
                                                           r.get('message', '')))
        dev = _read_json('device.json', {}) or {}
        dev['registered'] = hashlib.sha1(self.token.encode()).hexdigest()
        _write_json('device.json', dev)

    def _registered(self):
        dev = _read_json('device.json', {}) or {}
        return dev.get('registered') == hashlib.sha1(self.token.encode()).hexdigest()

    def roll(self):
        params = {'mediaId': self.media_id, 'ownerUid': self.owner,
                  'sessionId': self.session_id, 'enablelowlatency': 'false'}
        roll = {'isLive': self.is_live, 'rightsMode': 'LIVE' if self.is_live else
                'VOD_STREAMING', 'inhome': self.inhome}
        if self.start_time and self.asset_type in ('catchup',):
            roll['startTime'] = self.start_time
        data = self._post('v1/client/roll', params, {'roll': roll}, 'Stream-kérés (roll)')
        _debug_dump('mk_roll', data)
        return data

    def start(self):
        """-> (manifest_url, license_url, headers, drm_type)"""
        # mint az SDK: új tokennel előbb regisztráció, lejárt regisztrációnál egyszer újra
        if not self._registered():
            self.register()
        data = self.roll()
        if data.get('result') != 'success':
            log('roll sikertelen (%s) - újraregisztrálás' % (data.get('response') or {}),
                xbmc.LOGWARNING)
            self.register()
            data = self.roll()
        if data.get('result') != 'success':
            r = data.get('response') or {}
            raise ApiError('Stream-kérés: %s %s' % (r.get('code', ''), r.get('message', '')))
        r = data.get('response') or {}
        self.beacon_interval = int(r.get('beacon_interval') or 0)
        manifest = r.get('manifest_uri') or ''
        extra = {'sessionId': self.session_id}
        if r.get('personal_info'):
            try:
                extra.update(json.loads(base64.b64decode(r['personal_info']).decode()))
            except (ValueError, TypeError):
                pass
        if r.get('platform'):
            extra['devicetype'] = r['platform']
        manifest = _update_query(manifest, extra)
        cdns = ((r.get('cdns') or {}).get('cdn')) or []
        if isinstance(cdns, dict):
            cdns = [cdns]
        cdns = sorted(cdns, key=lambda c: c.get('priority', 99))
        if not cdns or not manifest:
            raise ApiError('A stream-válaszban nincs manifest / CDN')
        url = '%s/%s' % (cdns[0].get('base_uri', '').rstrip('/'), manifest.lstrip('/'))
        lic = _mk_url(self.server, 'v1/client/get-widevine-license',
                      {'mediaId': self.media_id, 'ownerUid': self.owner,
                       'sessionId': self.session_id, 'enablelowlatency': 'false'}) + '/'
        log('Stream: %s (drm: %s, beacon: %ss)' % (url.split('?')[0], r.get('drm_type'),
                                                   self.beacon_interval))
        return url, lic, self.headers(), r.get('drm_type')

    def beacon(self, complete=False):
        try:
            self._post('v1/client/beacons', {'mediaId': self.media_id, 'ownerUid': self.owner,
                                             'sessionId': self.session_id},
                       {'beacon': {'isLive': self.is_live, 'complete': complete,
                                   'inhome': self.inhome}}, 'Életjel')
        except ApiError as exc:
            log('Beacon hiba: %s' % exc, xbmc.LOGWARNING)


def _update_query(url, params):
    """A MediaKind SDK updateURLQueryParams-a: meglévő + új paraméterek, URI-kódolva."""
    base, _, qs = url.partition('?')
    items = []
    keys = {}
    for part in qs.split('&') if qs else []:
        k, _, v = part.partition('=')
        k, v = unquote(k), unquote(v)
        keys[k] = len(items)
        items.append([k, v])
    for k, v in params.items():
        v = '' if v is None else str(v)
        if k in keys:
            items[keys[k]][1] = v
        else:
            keys[k] = len(items)
            items.append([k, v])
    return base + ('?' + '&'.join('%s=%s' % (quote(k, safe="-_.!~*'()"),
                                             quote(v, safe="-_.!~*'()"))
                                  for k, v in items) if items else '')
