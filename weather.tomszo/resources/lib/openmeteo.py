# -*- coding: utf-8 -*-
"""
Open-Meteo (open-meteo.com) - ingyenes, kulcs nélküli időjárás API (adatok: CC BY 4.0).

Egy frissítés = egyetlen kérés (aktuális + 48 óra óránként + 16 nap naponta).
Településkeresés: geocoding-api.open-meteo.com (magyar nevekkel).
"""
from resources.lib.common import http_json

FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'
GEOCODE_URL = 'https://geocoding-api.open-meteo.com/v1/search'

_CURRENT = ('temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,'
            'weather_code,cloud_cover,pressure_msl,wind_speed_10m,wind_direction_10m,'
            'wind_gusts_10m,dew_point_2m,uv_index,visibility')
_HOURLY = ('temperature_2m,apparent_temperature,relative_humidity_2m,dew_point_2m,'
           'precipitation_probability,precipitation,weather_code,wind_speed_10m,'
           'wind_direction_10m,uv_index,is_day')
_DAILY = ('weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_sum,'
          'precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,'
          'wind_direction_10m_dominant,uv_index_max')

# WMO időjáráskód -> (Kodi ikon nappal, Kodi ikon éjjel, magyar leírás)
WMO = {
    0: (32, 31, 'Derült'),
    1: (34, 33, 'Többnyire derült'),
    2: (30, 29, 'Közepesen felhős'),
    3: (26, 26, 'Borult'),
    45: (20, 20, 'Köd'),
    48: (20, 20, 'Zúzmarás köd'),
    51: (9, 9, 'Gyenge szitálás'),
    53: (9, 9, 'Szitálás'),
    55: (9, 9, 'Erős szitálás'),
    56: (8, 8, 'Gyenge ónos szitálás'),
    57: (8, 8, 'Ónos szitálás'),
    61: (11, 11, 'Gyenge eső'),
    63: (12, 12, 'Eső'),
    65: (12, 12, 'Erős eső'),
    66: (10, 10, 'Gyenge ónos eső'),
    67: (10, 10, 'Ónos eső'),
    71: (14, 14, 'Gyenge havazás'),
    73: (16, 16, 'Havazás'),
    75: (41, 41, 'Erős havazás'),
    77: (13, 13, 'Hódara'),
    80: (40, 40, 'Gyenge zápor'),
    81: (11, 11, 'Zápor'),
    82: (12, 12, 'Heves zápor'),
    85: (14, 14, 'Gyenge hózápor'),
    86: (43, 43, 'Erős hózápor'),
    95: (4, 4, 'Zivatar'),
    96: (3, 3, 'Zivatar jégesővel'),
    99: (3, 3, 'Heves zivatar jégesővel'),
}


def wmo(code, is_day=True):
    try:
        day, night, text = WMO[int(code)]
    except (KeyError, TypeError, ValueError):
        return 'na', ''
    return (day if is_day else night), text


def _at(block, key, i):
    try:
        return block[key][i]
    except (KeyError, IndexError, TypeError):
        return None


def fetch(lat, lon, tz='auto'):
    data = http_json(FORECAST_URL, {
        'latitude': lat, 'longitude': lon, 'timezone': tz or 'auto',
        'current': _CURRENT, 'hourly': _HOURLY, 'daily': _DAILY,
        'forecast_days': 16, 'forecast_hours': 72,
    })
    if 'current' not in data:
        raise ValueError(data.get('reason') or 'hiányos Open-Meteo válasz')
    return normalize(data)


def normalize(data):
    """A nyers API-válaszból a közös (JSON-barát) modell."""
    c = data.get('current') or {}
    code, text = wmo(c.get('weather_code'), c.get('is_day', 1) == 1)
    vis = c.get('visibility')
    current = {
        'time': c.get('time', ''), 'temp': c.get('temperature_2m'),
        'feels': c.get('apparent_temperature'), 'humidity': c.get('relative_humidity_2m'),
        'dew': c.get('dew_point_2m'), 'uv': c.get('uv_index'),
        'wind': c.get('wind_speed_10m'), 'wind_dir': c.get('wind_direction_10m'),
        'gust': c.get('wind_gusts_10m'), 'pressure': c.get('pressure_msl'),
        'precip': c.get('precipitation'), 'cloud': c.get('cloud_cover'),
        'visibility': (vis / 1000.0) if vis is not None else None,
        'code': code, 'text': text,
    }
    h = data.get('hourly') or {}
    hourly = []
    for i, t in enumerate(h.get('time') or []):
        hcode, htext = wmo(_at(h, 'weather_code', i), _at(h, 'is_day', i) != 0)
        hourly.append({
            'dt': t[:16], 'temp': _at(h, 'temperature_2m', i),
            'feels': _at(h, 'apparent_temperature', i),
            'humidity': _at(h, 'relative_humidity_2m', i), 'dew': _at(h, 'dew_point_2m', i),
            'pop': _at(h, 'precipitation_probability', i), 'precip': _at(h, 'precipitation', i),
            'wind': _at(h, 'wind_speed_10m', i), 'wind_dir': _at(h, 'wind_direction_10m', i),
            'uv': _at(h, 'uv_index', i), 'code': hcode, 'text': htext,
        })
    d = data.get('daily') or {}
    daily = []
    for i, t in enumerate(d.get('time') or []):
        dcode, dtext = wmo(_at(d, 'weather_code', i), True)
        daily.append({
            'date': t[:10], 'tmax': _at(d, 'temperature_2m_max', i),
            'tmin': _at(d, 'temperature_2m_min', i), 'code': dcode, 'text': dtext,
            'precip': _at(d, 'precipitation_sum', i),
            'pop': _at(d, 'precipitation_probability_max', i),
            'wind': _at(d, 'wind_speed_10m_max', i), 'gust': _at(d, 'wind_gusts_10m_max', i),
            'wind_dir': _at(d, 'wind_direction_10m_dominant', i),
            'uv': _at(d, 'uv_index_max', i),
            'sunrise': (_at(d, 'sunrise', i) or '')[11:16],
            'sunset': (_at(d, 'sunset', i) or '')[11:16],
            'alerts': [],
        })
    return {'source': 'om', 'current': current, 'hourly': hourly, 'daily': daily,
            'utc_offset': data.get('utc_offset_seconds'), 'timezone': data.get('timezone')}


def geocode(name, count=15):
    data = http_json(GEOCODE_URL, {'name': name, 'count': count,
                                   'language': 'hu', 'format': 'json'})
    return data.get('results') or []
