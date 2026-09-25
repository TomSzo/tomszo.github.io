# -*- coding: utf-8 -*-
"""
Közös segédfüggvények: HTTP (fix UA, 1 mp szünet, napi számláló), lemez-gyorsítótár,
mértékegységek és a Kodi területi beállításai szerinti dátum/idő formázás.
"""
import datetime
import hashlib
import json
import os
import time

try:
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
except ImportError:  # py2 - Kodi 19+ alatt nem fordul elő
    from urllib import urlencode
    from urllib2 import Request, urlopen

import xbmc
import xbmcaddon
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
USER_AGENT = 'Mozilla/5.0 (Android 16; Mobile; rv:156.0) Gecko/156.0 Firefox/156.0'
MIN_GAP = 1.0            # másodperc két kérés között
STALE_MAX = 6 * 3600     # hálózati hibánál ennyi idős adatot még elfogadunk

_LAST = [0.0]


def log(msg, level=xbmc.LOGINFO):
    xbmc.log('[%s] %s' % (ADDON_ID, msg), level)


def L(string_id):
    return ADDON.getLocalizedString(string_id)


def setting(key, default=''):
    val = ADDON.getSetting(key)
    return val if val != '' else default


def setting_int(key, default):
    try:
        return int(float(ADDON.getSetting(key)))
    except (TypeError, ValueError):
        return default


def setting_bool(key, default=True):
    val = ADDON.getSetting(key)
    if val == '':
        return default
    return val.lower() == 'true'


def profile_path(name=''):
    prof = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
    try:
        if not xbmcvfs.exists(prof):
            xbmcvfs.mkdirs(prof)
    except Exception:  # noqa
        pass
    return os.path.join(prof, name)


def _read_json(name, default):
    try:
        path = profile_path(name)
        if not xbmcvfs.exists(path):
            return default
        f = xbmcvfs.File(path)
        try:
            return json.loads(f.read() or 'null') or default
        finally:
            f.close()
    except Exception as exc:  # noqa
        log('%s olvasási hiba: %s' % (name, exc), xbmc.LOGWARNING)
        return default


def _write_json(name, data):
    try:
        f = xbmcvfs.File(profile_path(name), 'w')
        try:
            f.write(json.dumps(data, ensure_ascii=False))
        finally:
            f.close()
    except Exception as exc:  # noqa
        log('%s mentési hiba: %s' % (name, exc), xbmc.LOGWARNING)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def _count_request(host):
    today = time.strftime('%Y-%m-%d')
    data = _read_json('requests.json', {})
    if data.get('date') != today:
        data = {'date': today}
    data[host] = int(data.get(host, 0)) + 1
    _write_json('requests.json', data)


def today_requests():
    data = _read_json('requests.json', {})
    if data.get('date') != time.strftime('%Y-%m-%d'):
        return {}
    return dict((k, v) for k, v in data.items() if k != 'date')


def http_get(url, params=None, timeout=15):
    if params:
        url += ('&' if '?' in url else '?') + urlencode(params)
    gap = time.time() - _LAST[0]
    if gap < MIN_GAP:
        time.sleep(MIN_GAP - gap)
    req = Request(url, headers={'User-Agent': USER_AGENT,
                                'Accept-Language': 'hu-HU,hu;q=0.9,en;q=0.5'})
    _LAST[0] = time.time()
    host = url.split('/')[2] if '//' in url else url
    _count_request(host)
    log('GET %s' % url, xbmc.LOGDEBUG)
    resp = urlopen(req, timeout=timeout)
    try:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or 'utf-8'
    finally:
        resp.close()
    return raw.decode(charset, 'replace')


def http_json(url, params=None, timeout=15):
    return json.loads(http_get(url, params, timeout))


# ---------------------------------------------------------------------------
# Gyorsítótár
# ---------------------------------------------------------------------------
def _cache_name(key):
    return 'cache_%s.json' % hashlib.md5(key.encode('utf-8')).hexdigest()[:16]


def cached(key, ttl, fetch):
    """Friss (ttl-en belüli) adat a lemezről, különben letöltés.
    Hálózati/feldolgozási hibánál a legfeljebb STALE_MAX idős régi adat marad."""
    old = _read_json(_cache_name(key), {})
    age = time.time() - float(old.get('ts', 0))
    if old.get('data') is not None and 0 <= age < ttl:
        return old['data']
    try:
        data = fetch()
    except Exception as exc:  # noqa
        log('%s letöltési hiba: %s' % (key, exc), xbmc.LOGWARNING)
        if old.get('data') is not None and age < STALE_MAX:
            return old['data']
        raise
    _write_json(_cache_name(key), {'ts': time.time(), 'key': key, 'data': data})
    return data


def clear_cache():
    prof = profile_path()
    n = 0
    for name in os.listdir(prof):
        if name.startswith('cache_') and name.endswith('.json'):
            try:
                os.remove(os.path.join(prof, name))
                n += 1
            except OSError:
                pass
    return n


# ---------------------------------------------------------------------------
# Mértékegységek (a Kodi Területi beállításai szerint)
# ---------------------------------------------------------------------------
def temp_unit():
    unit = xbmc.getRegion('tempunit') or '°C'
    return unit if unit.replace('°', '').strip() in ('C', 'F', 'K') else '°C'


def temp_value(celsius):
    unit = temp_unit().replace('°', '').strip()
    if unit == 'F':
        return celsius * 9.0 / 5.0 + 32
    if unit == 'K':
        return celsius + 273.15
    return celsius


def fmt_temp(celsius):
    if celsius is None:
        return ''
    return '%d%s' % (int(round(temp_value(celsius))), temp_unit())


_SPEED = {'km/h': 1.0, 'kmh': 1.0, 'm/s': 1 / 3.6, 'mph': 1 / 1.609344,
          'kts': 1 / 1.852, 'kt': 1 / 1.852, 'ft/s': 1 / 1.09728}
_BEAUFORT = (1, 6, 12, 20, 29, 39, 50, 62, 75, 89, 103, 118)


def fmt_speed(kmh):
    if kmh is None:
        return ''
    unit = xbmc.getRegion('speedunit') or 'km/h'
    if unit.lower().startswith('beaufort'):
        return '%d Bft' % next((i for i, lim in enumerate(_BEAUFORT) if kmh < lim), 12)
    factor = _SPEED.get(unit.lower())
    if factor is None:
        unit, factor = 'km/h', 1.0
    return '%d %s' % (int(round(kmh * factor)), unit)


def wind_dir(deg):
    """Égtáj a Kodi saját (lokalizált) szövegeivel: 71 = É ... 86 = ÉÉNy."""
    if deg is None:
        return ''
    return xbmc.getLocalizedString(71 + int((float(deg) + 11.25) / 22.5) % 16)


def rnd(value):
    return '' if value is None else str(int(round(value)))


# ---------------------------------------------------------------------------
# Dátum / idő
# ---------------------------------------------------------------------------
def to_date(iso):
    return datetime.date(int(iso[0:4]), int(iso[5:7]), int(iso[8:10]))


def to_dt(iso):
    return datetime.datetime(int(iso[0:4]), int(iso[5:7]), int(iso[8:10]),
                             int(iso[11:13]), int(iso[14:16]))


def day_long(d):
    return xbmc.getLocalizedString(11 + d.weekday())


def day_short(d):
    return xbmc.getLocalizedString(41 + d.weekday())


def month_long(d):
    return xbmc.getLocalizedString(21 + d.month - 1)


def month_short(d):
    return xbmc.getLocalizedString(51 + d.month - 1)


def _hungarian():
    try:
        return xbmc.getLanguage(xbmc.ISO_639_1) == 'hu'
    except Exception:  # noqa
        return True


def fmt_date_long(d):
    return ('%s %d.' if _hungarian() else '%s %d') % (month_long(d), d.day)


def fmt_date_short(d):
    try:
        return d.strftime(xbmc.getRegion('dateshort') or '%Y-%m-%d')
    except Exception:  # noqa
        return d.isoformat()


def fmt_time(hhmm):
    """'06:35' -> a Kodi időformátuma szerint (másodperc nélkül)."""
    if not hhmm:
        return ''
    try:
        h, m = [int(x) for x in hhmm.split(':')[:2]]
        fmt = (xbmc.getRegion('time') or '%H:%M:%S').replace(':%S', '')
        return datetime.datetime(2000, 1, 1, h, m).strftime(fmt)
    except Exception:  # noqa
        return hhmm
