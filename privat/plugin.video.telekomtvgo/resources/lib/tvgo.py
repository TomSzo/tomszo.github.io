# -*- coding: utf-8 -*-
"""
Telekom TV GO (Magyar Telekom) - a player.telekomtvgo.hu webes kliens API-ja.

A webes kliens (W02.0.1470) kódjából feltérképezve (új kód):

Bejelentkezés (natív login, "centralauth"):
    POST {NL}/onboarding/login           body: alap + device + telekomLogin{username,
                                          password = base64(RSA-OAEP-SHA1(jelszó))}
                                          -> {accessToken, refreshToken, accessExpiresIn,
                                              deviceLimitExceed, tvAccountIds}
    POST {NL}/onboarding/authenticate?legacyFlow=false   (ha több TV-előfizetés van;
                                          fejléc: ms_access_token, body: tvAccountId)
    POST {NL}/onboarding/refreshtoken    fejléc: refresh_token, channel: Tv
    NL = https://external-gateway.oa.yo-digital.com/centralauth-prod/hu/P

Tartalom (bifrost, fejléc: bff_token = accessToken):
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
token lemezen (lejárat előtt frissítés), sikertelen belépés után 10 perc szünet.
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

from resources.lib import rsa_oaep

ADDON_ID = 'plugin.video.telekomtvgo'
ADDON = xbmcaddon.Addon(ADDON_ID)

NL_BASE = 'https://external-gateway.oa.yo-digital.com/centralauth-prod/hu/P'
BFF = 'https://tv-hu-prod.yo-digital.com/bifrost'
IMG = 'https://ottapp-akamai-client-a.proda.dtp.tv3cloud.com/images/images'
ORIGIN = 'https://player.telekomtvgo.hu'

NATCO_KEY = 'Tydx7H7fJO6HxgjvJok0ZhVWFmX3om0P'
APP_KEY = 'exSJHBiSAN6wAAeqdWLdTUfdTi2PNark'       # CMS_CONFIGURATION_API_KEY
APP_VERSION = '02.0.1470'
COUNTRY = 'hu'
LANG = 'hu'
DEVICE_TYPE = 'WEB'
# modules.auth.rsaPublicKey a webes CMS-konfigurációból
RSA_KEY = ('MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAxOnrC7x6UFJ1Z0HGDRUI4qWfCaid33Xgqal9'
           '/aSHc9RxmwgS8F65VDp3BGNmdm+6MO2/PhO6Khg90YQUHaUxtlseqKQP8Kc0w1IhdDHt6B+wabXZpi'
           '/zjI+b9JJFvOo6f1GwuTA6+aO9jxEGbGU2XPHSe/6x7FkEAa/83T1QIfdJZlHY3Cz9eWrQEUL4Unc'
           'GMLonufNj4LfUMCE6BO84Oo53YM1BrUmzJt4xDCNm+8hTkEklK8ZWrYrYQM2rxY1uYgQmf8rvfhWci'
           'k2R8reD5vDOSfvcYYwEAB+BRhl0pw9KzUhoaDe0SI5RQ2TeLiomdGHwy+8lfDwbo0wDRWA7vQIDAQAB')
AZUKI_IMC = 'IMC7.6.0_XX_Dx.x.x_Sx'

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/140.0.0.0 Safari/537.36')
OS_NAME = 'Windows'
BROWSER = 'Chrome'

MIN_GAP = 0.5
LOGIN_COOLDOWN = 600
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


class DeviceLimitError(LoginError):
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
        if fn.startswith('cache_') or fn.startswith('debug_'):
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
        'X-User-Agent': '',
        'x-request-trackingid': tracking,
        'x-txn-id': txn,
        'x-call-time': call_time,
        'x-request-session-id': sid,
        'Device-Name': '%s - %s' % (OS_NAME, BROWSER),
        'Pragma': 'akamai-x-cache-on,akamai-x-checkcacheable,akamai-x-get-cache-key',
        'tenant': 'tv',
        'requestId': str(uuid.uuid4()),
    }


# ---------------------------------------------------------------------------
# Bejelentkezés
# ---------------------------------------------------------------------------
def have_credentials():
    return bool(ADDON.getSetting('email') and ADDON.getSetting('password'))


def saved_token():
    return _read_json(TOKEN_FILE, {}) or {}


def clear_token():
    try:
        os.remove(profile(TOKEN_FILE))
    except OSError:
        pass
    for fn in ('cache_account.json',):
        try:
            os.remove(profile(fn))
        except OSError:
            pass


def _device_body():
    return {'id': device_id(), 'model': DEVICE_TYPE, 'os': OS_NAME, 'deviceName': DEVICE_TYPE,
            'manageDevice': False, 'deviceType': DEVICE_TYPE, 'deviceOS': OS_NAME,
            'deviceModel': '', 'deviceManufacturer': '%s 10' % OS_NAME,
            'concurrencyLimitParam': None, 'broadcastingStreamLimitationApplies': False}


def _base_body():
    return {'appVersion': APP_VERSION, 'channel': {'id': 'Tv'}, 'natco': COUNTRY,
            'type': 'telekom', 'forceRegister': False, 'context': 'login'}


def _nl_post(path, body, extra_headers=None):
    h = _common_headers()
    h['Content-Type'] = 'application/json'
    h['X-Call-Type'] = 'GUEST_USER'
    if extra_headers:
        h.update(extra_headers)
    return _request('POST', NL_BASE + path, headers=h, data=json.dumps(body))


def _save_tokens(data, extra=None):
    tok = saved_token()
    if data.get('accessToken'):
        tok['access'] = data['accessToken']
    if data.get('refreshToken'):
        tok['refresh'] = data['refreshToken']
    try:
        exp = int(data.get('accessExpiresIn') or 0)
    except (TypeError, ValueError):
        exp = 0
    # accessExpiresIn: másodperc (ha ezredmásodpercnek tűnik, átváltjuk)
    if exp > 10 ** 7:
        exp //= 1000
    tok['expires'] = time.time() + (exp or 3600) - 120
    if extra:
        tok.update(extra)
    _write_json(TOKEN_FILE, tok)
    return tok


def login():
    """Email + jelszó belépés. Siker esetén a tokent menti és visszaadja."""
    if not have_credentials():
        raise LoginError('Add meg a Telekom-fiókod email címét és jelszavát a beállításokban.')
    state = _read_json('login_state.json', {}) or {}
    if time.time() - state.get('failed', 0) < LOGIN_COOLDOWN:
        raise LoginError('Az előző belépés nem sikerült (%s). Várj pár percet, vagy ellenőrizd '
                         'az adataidat.' % state.get('reason', ''))
    body = _base_body()
    body['device'] = _device_body()
    body['telekomLogin'] = {'username': ADDON.getSetting('email').strip(),
                            'password': rsa_oaep.encrypt(ADDON.getSetting('password'), RSA_KEY)}
    resp = _nl_post('/onboarding/login', body, {'x-tvflow': 'USERNAME_PASSWORD_LOGIN',
                                                'x-tv-step': 'GET_ACCESS_TOKEN'})
    if resp.status_code >= 400:
        reason = _err_text(resp)
        _write_json('login_state.json', {'failed': time.time(), 'reason': reason})
        raise LoginError('Sikertelen belépés (%s). Ellenőrizd az email címet és a jelszót.'
                         % reason)
    data = _json(resp, 'Belépés')
    _debug_dump('login', {k: ('***' if 'oken' in k else v) for k, v in data.items()}
                if isinstance(data, dict) else data)
    if data.get('deviceLimitExceed'):
        raise DeviceLimitError('Elérted a Telekom-fiókhoz tartozó eszközök számának '
                               'korlátját. Távolíts el egy eszközt (telekomtvgo.hu -> '
                               'Beállítások -> Eszközök), majd próbáld újra.')
    accounts = data.get('tvAccountIds') or []
    if len(accounts) > 1:
        data = _choose_account(data, accounts)
    if not data.get('accessToken'):
        raise LoginError('A belépés nem adott vissza tokent.')
    _write_json('login_state.json', {})
    log('Belépés sikeres')
    return _save_tokens(data, {'email': ADDON.getSetting('email').strip()})


def _choose_account(data, accounts):
    """Több TV-előfizetés: a beállításban megadott sorszámú (vagy az első)."""
    try:
        idx = max(0, int(ADDON.getSetting('account_index') or 1) - 1)
    except ValueError:
        idx = 0
    acc = accounts[min(idx, len(accounts) - 1)]
    acc_id = acc.get('id') if isinstance(acc, dict) else acc
    body = _base_body()
    body.update({'tvAccountId': acc_id, 'concurrencyLimitParam': None})
    body['device'] = _device_body()
    resp = _nl_post('/onboarding/authenticate?legacyFlow=false', body,
                    {'ms_access_token': data.get('accessToken', '')})
    if resp.status_code >= 400:
        raise LoginError('TV-előfizetés kiválasztása sikertelen (%s)' % _err_text(resp))
    return _json(resp, 'Előfizetés kiválasztása')


def refresh():
    tok = saved_token()
    if not tok.get('refresh'):
        return None
    body = {'clientVersion': APP_VERSION, 'deviceId': device_id(), 'concurrencyLimitParam': None}
    resp = _nl_post('/onboarding/refreshtoken', body,
                    {'refresh_token': tok['refresh'], 'channel': 'Tv'})
    if resp.status_code >= 400:
        log('Tokenfrissítés sikertelen: %s' % _err_text(resp), xbmc.LOGWARNING)
        return None
    data = _json(resp, 'Tokenfrissítés')
    if not data.get('accessToken'):
        return None
    log('Token frissítve')
    return _save_tokens(data)


def access_token(force=False):
    tok = saved_token()
    if tok.get('email') and tok.get('email') != ADDON.getSetting('email').strip():
        clear_token()
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
