# -*- coding: utf-8 -*-
"""
Kodi időjárás-szolgáltató (xbmc.python.weather).

A Kodi így hívja a scriptet:
    default.py <n>          -> az n. hely időjárását kell a 12600-as ablak tulajdonságaiba írni
    default.py Location<n>  -> (beállításokból) az n. hely keresése / beállítása
    default.py clearcache   -> (beállításokból) gyorsítótár törlése + napi kérésszám

Adatok: magyar településnél az Időkép oldala (jelenlegi idő, 3 órás és 15 napos előrejelzés,
napkelte / napnyugta), kiegészítve az Open-Meteo méréseivel (pára, szél, UV, csapadék, légnyomás,
harmatpont stb.). Külföldi helynél, vagy ha az Időkép nem elérhető: csak Open-Meteo.
"""
import datetime
import re
import time

import xbmc
import xbmcgui

from resources.lib import common, idokep, openmeteo
from resources.lib.common import L, fmt_speed, fmt_temp, rnd

WINDOW = xbmcgui.Window(12600)
MAX_LOCATIONS = 5
MAX_DAILY = 16
MAX_HOURLY = 48
DEFAULT_LOCATION = ('Budapest', '47.49801|19.03991|Europe/Budapest|HU|Budapest')


def prop(key, value):
    WINDOW.setProperty(key, '' if value is None else str(value))


def clear(key):
    WINDOW.clearProperty(key)


# ---------------------------------------------------------------------------
# Helyek
# ---------------------------------------------------------------------------
def parse_loc_id(value):
    parts = (value or '').split('|')
    parts += [''] * (5 - len(parts))
    try:
        lat, lon = float(parts[0]), float(parts[1])
    except ValueError:
        return None
    return {'lat': lat, 'lon': lon, 'tz': parts[2] or 'auto', 'cc': parts[3].upper(),
            'slug': parts[4]}


def locations():
    out = []
    for i in range(1, MAX_LOCATIONS + 1):
        name = common.ADDON.getSetting('Location%d' % i)
        loc = parse_loc_id(common.ADDON.getSetting('Location%did' % i))
        if name and loc:
            out.append((name, loc))
    if not out:                         # első indítás / minden hely törölve
        loc = parse_loc_id(DEFAULT_LOCATION[1])
        out.append((DEFAULT_LOCATION[0], loc))
    return out


def search_location(arg):
    """Beállításokból: 'Location<n>' - település keresése és mentése."""
    dialog = xbmcgui.Dialog()
    current = common.ADDON.getSetting(arg)
    text = dialog.input(L(32200), current or '')
    if not text:
        if current and arg != 'Location1' and dialog.yesno(L(32200), L(32201) % current):
            common.ADDON.setSetting(arg, '')
            common.ADDON.setSetting(arg + 'id', '')
        return
    m = re.match(r'^\s*(-?\d{1,2}(?:\.\d+)?)\s*[,; ]\s*(-?\d{1,3}(?:\.\d+)?)\s*$', text)
    if m:                               # közvetlen koordináta: "47.5, 19.04"
        common.ADDON.setSetting(arg, text.strip())
        common.ADDON.setSetting(arg + 'id', '%s|%s|auto||' % (m.group(1), m.group(2)))
        return
    try:
        results = openmeteo.geocode(text)
    except Exception as exc:  # noqa
        common.log('keresési hiba: %s' % exc, xbmc.LOGWARNING)
        dialog.notification(L(32000), L(32203), xbmcgui.NOTIFICATION_ERROR)
        return
    if not results:
        dialog.ok(L(32200), L(32202) % text)
        return
    labels = []
    for r in results:
        extra = ', '.join(x for x in (r.get('admin1'), r.get('country')) if x)
        labels.append('%s  [%s]  (%.2f, %.2f)' % (r.get('name', '?'), extra,
                                                  r.get('latitude', 0), r.get('longitude', 0)))
    sel = dialog.select(L(32204), labels)
    if sel < 0:
        return
    r = results[sel]
    cc = (r.get('country_code') or '').upper()
    name = r.get('name', text)
    label = name if cc == 'HU' else '%s, %s' % (name, r.get('country') or cc)
    common.ADDON.setSetting(arg, label)
    common.ADDON.setSetting(arg + 'id', '%s|%s|%s|%s|%s' % (
        r.get('latitude'), r.get('longitude'), r.get('timezone') or 'auto', cc,
        name if cc == 'HU' else ''))


# ---------------------------------------------------------------------------
# Adatok összefésülése
# ---------------------------------------------------------------------------
def local_now(om):
    off = (om or {}).get('utc_offset')
    if off is None:
        return datetime.datetime.now()
    return datetime.datetime.utcnow() + datetime.timedelta(seconds=int(off))


def merge(om, ik, hourly_src):
    """Időkép az alap (amit megad), az Open-Meteo pótolja a hiányzó mezőket."""
    if not ik:
        return om
    om = om or {'current': {}, 'hourly': [], 'daily': []}
    cur = dict(om['current'])
    for k in ('temp', 'text', 'code'):
        if ik['current'].get(k) not in (None, ''):
            cur[k] = ik['current'][k]
    # napok dátum szerint egyesítve: Időkép-mezők felülírnak, Open-Meteo kiegészít / tovább lát
    days = dict((d['date'], dict(d)) for d in om['daily'])
    for d in ik['daily']:
        day = days.setdefault(d['date'], {})
        day.update(dict((k, v) for k, v in d.items() if v not in (None, '', [])))
        day.setdefault('alerts', [])
    daily = [days[k] for k in sorted(days)]
    if daily and ik.get('sunrise'):
        daily[0]['sunrise'], daily[0]['sunset'] = ik['sunrise'], ik.get('sunset', '')
    om_hours = dict((h['dt'][:13], h) for h in om['hourly'])
    if hourly_src == 0 and ik['hourly']:
        hourly = []
        for h in ik['hourly']:
            hour = dict(om_hours.get(h['dt'][:13], {}))
            hour.update(dict((k, v) for k, v in h.items() if v not in (None, '')))
            hourly.append(hour)
    else:
        hourly = om['hourly']
    out = dict(om)
    out.update({'current': cur, 'daily': daily, 'hourly': hourly, 'source': 'ik+om',
                'headline': ik.get('headline', ''), 'description': ik.get('description', ''),
                'summary': ik.get('summary', ''), 'water': ik.get('water', [])})
    return out


# ---------------------------------------------------------------------------
# Kodi tulajdonságok
# ---------------------------------------------------------------------------
def clear_forecast():
    for i in range(MAX_DAILY + 1):
        for k in ('Title', 'HighTemp', 'LowTemp', 'Outlook', 'OutlookIcon', 'FanartCode'):
            clear('Day%d.%s' % (i, k))
    for i in range(1, MAX_DAILY + 1):
        clear('Daily.%d.ShortDay' % i)
        clear('Daily.%d.Outlook' % i)
    for i in range(1, MAX_HOURLY + 1):
        clear('Hourly.%d.Time' % i)
        clear('Hourly.%d.Temperature' % i)
    for k in ('Current.IsFetched', 'Today.IsFetched', 'Daily.IsFetched', 'Hourly.IsFetched',
              'Forecast.IsFetched', '36Hour.IsFetched', 'Weekend.IsFetched', 'Map.IsFetched',
              'Alerts.IsFetched'):
        clear(k)


def set_locations(locs):
    prop('Locations', len(locs))
    for i in range(1, MAX_LOCATIONS + 1):
        if i <= len(locs):
            prop('Location%d' % i, locs[i - 1][0])
        else:
            clear('Location%d' % i)


def _icon(code):
    return '%s.png' % code


def set_current(m, name, loc):
    cur = m['current']
    prop('Current.Location', name)
    prop('Current.Condition', cur.get('text', ''))
    prop('Current.Temperature', rnd(cur.get('temp')))          # °C - a Kodi váltja át
    prop('Current.FeelsLike', rnd(cur.get('feels')))           # °C
    prop('Current.DewPoint', rnd(cur.get('dew')))              # °C
    prop('Current.Wind', rnd(cur.get('wind')))                 # km/h
    prop('Current.WindDirection', common.wind_dir(cur.get('wind_dir')) or 'CALM')
    prop('Current.WindGust', fmt_speed(cur.get('gust')))
    prop('Current.Humidity', rnd(cur.get('humidity')))
    prop('Current.UVIndex', rnd(cur.get('uv')))
    prop('Current.Cloudiness', '' if cur.get('cloud') is None else '%d%%' % cur['cloud'])
    prop('Current.Pressure', '' if cur.get('pressure') is None else '%d hPa' % cur['pressure'])
    prop('Current.Precipitation', '' if cur.get('precip') is None else '%.1f mm' % cur['precip'])
    prop('Current.Visibility', '' if cur.get('visibility') is None
         else '%.0f km' % cur['visibility'])
    prop('Current.OutlookIcon', _icon(cur.get('code', 'na')))
    prop('Current.FanartCode', cur.get('code', 'na'))
    prop('Current.Headline', m.get('headline', ''))
    prop('Current.Description', m.get('description', ''))
    prop('Forecast.Summary', m.get('summary', ''))
    prop('Forecast.City', name)
    prop('Forecast.Country', loc.get('cc', ''))
    prop('Forecast.Latitude', loc['lat'])
    prop('Forecast.Longitude', loc['lon'])
    prop('Current.IsFetched', 'true')


def set_daily(days):
    for i in range(MAX_DAILY + 1):
        clear('Day%d.Title' % i)
    for i, d in enumerate(days[:MAX_DAILY], 1):
        date = common.to_date(d['date'])
        code = d.get('code', 'na')
        alerts = ', '.join(d.get('alerts') or [])
        base = 'Daily.%d.' % i
        prop(base + 'LongDay', common.day_long(date))
        prop(base + 'ShortDay', common.day_short(date))
        prop(base + 'LongDate', common.fmt_date_long(date))
        prop(base + 'ShortDate', common.fmt_date_short(date))
        prop(base + 'Title', common.day_long(date))
        prop(base + 'Outlook', d.get('text', '') + (' - ' + alerts if alerts else ''))
        prop(base + 'OutlookIcon', _icon(code))
        prop(base + 'FanartCode', code)
        prop(base + 'HighTemperature', fmt_temp(d.get('tmax')))
        prop(base + 'LowTemperature', fmt_temp(d.get('tmin')))
        prop(base + 'WindSpeed', fmt_speed(d.get('wind')))
        prop(base + 'WindGust', fmt_speed(d.get('gust')))
        prop(base + 'WindDirection', common.wind_dir(d.get('wind_dir')))
        prop(base + 'Precipitation', '' if d.get('precip') is None else '%.1f mm' % d['precip'])
        prop(base + 'ChancePrecipitation', '' if d.get('pop') is None else '%d%%' % d['pop'])
        prop(base + 'UVIndex', rnd(d.get('uv')))
        prop(base + 'Sunrise', common.fmt_time(d.get('sunrise')))
        prop(base + 'Sunset', common.fmt_time(d.get('sunset')))
        prop(base + 'Alert', alerts)
        if i <= 7:                                   # régi (Day0..Day6) formátum
            day = 'Day%d.' % (i - 1)
            prop(day + 'Title', common.day_long(date))
            prop(day + 'HighTemp', rnd(d.get('tmax')))     # °C - a Kodi váltja át
            prop(day + 'LowTemp', rnd(d.get('tmin')))
            prop(day + 'Outlook', d.get('text', ''))
            prop(day + 'OutlookIcon', _icon(code))
            prop(day + 'FanartCode', code)
    for i in range(len(days) + 1, MAX_DAILY + 1):
        for k in ('LongDay', 'ShortDay', 'Title', 'Outlook', 'OutlookIcon', 'HighTemperature',
                  'LowTemperature'):
            clear('Daily.%d.%s' % (i, k))
    if days:
        today = days[0]
        prop('Today.Sunrise', common.fmt_time(today.get('sunrise')))
        prop('Today.Sunset', common.fmt_time(today.get('sunset')))
        prop('Today.HighTemp', fmt_temp(today.get('tmax')))
        prop('Today.LowTemp', fmt_temp(today.get('tmin')))
        prop('Today.IsFetched', 'true')
        prop('Daily.IsFetched', 'true')
        prop('Forecast.IsFetched', 'true')


def set_hourly(hours):
    for i, h in enumerate(hours[:MAX_HOURLY], 1):
        dt = common.to_dt(h['dt'])
        code = h.get('code', 'na')
        base = 'Hourly.%d.' % i
        prop(base + 'Time', common.fmt_time(h['dt'][11:16]))
        prop(base + 'LongDate', common.fmt_date_long(dt.date()))
        prop(base + 'ShortDate', common.fmt_date_short(dt.date()))
        prop(base + 'Outlook', h.get('text', ''))
        prop(base + 'OutlookIcon', _icon(code))
        prop(base + 'FanartCode', code)
        prop(base + 'Temperature', fmt_temp(h.get('temp')))
        prop(base + 'FeelsLike', fmt_temp(h.get('feels')))
        prop(base + 'DewPoint', fmt_temp(h.get('dew')))
        prop(base + 'Humidity', '' if h.get('humidity') is None else '%d%%' % h['humidity'])
        prop(base + 'WindSpeed', fmt_speed(h.get('wind')))
        prop(base + 'WindDirection', common.wind_dir(h.get('wind_dir')))
        prop(base + 'Precipitation', '' if h.get('precip') is None else '%.1f mm' % h['precip'])
        prop(base + 'ChancePrecipitation', '' if h.get('pop') is None else '%d%%' % h['pop'])
        prop(base + 'UVIndex', rnd(h.get('uv')))
    for i in range(len(hours) + 1, MAX_HOURLY + 1):
        for k in ('Time', 'Outlook', 'OutlookIcon', 'Temperature'):
            clear('Hourly.%d.%s' % (i, k))
    if hours:
        prop('Hourly.IsFetched', 'true')


def refresh(index):
    locs = locations()
    set_locations(locs)
    try:
        idx = min(max(int(index), 1), len(locs)) - 1
    except ValueError:
        idx = 0
    name, loc = locs[idx]
    ttl = max(15, common.setting_int('cache_minutes', 20)) * 60
    om = ik = None
    try:
        om = common.cached('om|%.3f|%.3f' % (loc['lat'], loc['lon']), ttl,
                           lambda: openmeteo.fetch(loc['lat'], loc['lon'], loc['tz']))
    except Exception as exc:  # noqa
        common.log('Open-Meteo hiba: %s' % exc, xbmc.LOGWARNING)
    now = local_now(om)
    if loc.get('slug') and common.setting_bool('use_idokep', True):
        try:
            ik = common.cached('ik|' + loc['slug'], ttl,
                               lambda: idokep.fetch(loc['slug'], local_now(om)))
        except Exception as exc:  # noqa
            common.log('Időkép hiba: %s' % exc, xbmc.LOGWARNING)
    model = merge(om, ik, common.setting_int('hourly_src', 0))
    clear_forecast()
    if not model:
        prop('Current.Location', name)
        prop('Current.Condition', L(32203))
        return
    today = now.date().isoformat()
    model['daily'] = [d for d in model['daily'] if d['date'] >= today]
    hour = now.strftime('%Y-%m-%dT%H')
    model['hourly'] = [h for h in model['hourly'] if h['dt'][:13] >= hour]
    set_current(model, name, loc)
    set_daily(model['daily'])
    set_hourly(model['hourly'])
    src = 'Időkép + Open-Meteo' if model.get('source') == 'ik+om' else 'Open-Meteo'
    prop('WeatherProvider', src)
    prop('WeatherProviderLogo', common.ADDON.getAddonInfo('icon'))
    prop('Forecast.Updated', '%s %s' % (common.fmt_date_short(now.date()),
                                        common.fmt_time(now.strftime('%H:%M'))))
    for i, w in enumerate(model.get('water') or [], 1):
        prop('Water.%d.Name' % i, w['name'])
        prop('Water.%d.Temperature' % i, fmt_temp(w['temp']))


def clear_cache():
    n = common.clear_cache()
    reqs = common.today_requests()
    info = ', '.join('%s: %d' % (k, v) for k, v in sorted(reqs.items())) or '0'
    xbmcgui.Dialog().ok(L(32000), L(32205) % (n, info))


def main(argv):
    arg = argv[0] if argv else '1'
    if arg.startswith('Location') and arg[8:].isdigit():
        search_location(arg)
    elif arg == 'clearcache':
        clear_cache()
    else:
        start = time.time()
        refresh(arg)
        common.log('frissítve (%s) %.1f mp' % (arg, time.time() - start))
