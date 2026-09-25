# -*- coding: utf-8 -*-
"""
Időkép (www.idokep.hu) - a település-oldal (/idojaras/<Település>) feldolgozása.

Egy frissítés = egyetlen oldal-letöltés. Ebből kinyerjük:
  - jelenlegi idő:   <div class="current-weather">Közepesen felhős</div>,
                     forecast-bigicon ... /assets/forecastIcons/022.svg, current-temperature 19℃
  - címsor / leírás: shortWeatherTitle, scTextDescription, <meta name="Description">
  - napkelte/nyugta: "Napkelte: 6:35", "Napnyugta: 18:36"
  - 3 órás előrejelzés (hourly-forecast-card): óra, ikon, alt-szöveg, "Várható hőmérséklet: 20°C"
  - 15 napos előrejelzés (dailyForecastCol): title="Péntek<br>2026. szeptember 25.",
    fc-line ikon + leírás, figyelmeztetés (alertIcons), max / min
  - vízhőmérsékletek (Balaton, Velencei-tó, ...)

Az Időkép ikonkódjai: 0xx nappali, 3xx éjszakai változat (pl. 021 / 321 gyengén felhős).
"""
import datetime
import re

try:
    from urllib.parse import quote
except ImportError:  # py2
    from urllib import quote

from resources.lib.common import http_get

BASE = 'https://www.idokep.hu'
HU_MONTHS = ('január', 'február', 'március', 'április', 'május', 'június', 'július',
             'augusztus', 'szeptember', 'október', 'november', 'december')

# (kulcsszó, Kodi ikon nappal, éjjel) - a sorrend számít (az első találat nyer)
_TEXT_RULES = (
    ('jégeső', 17, 17), ('jég', 17, 17),
    ('ónos', 10, 10),
    ('havas eső', 5, 5), ('havaseső', 5, 5),
    ('hózápor', 46, 46), ('hófúvás', 15, 15), ('hószállingózás', 13, 13),
    ('erős havazás', 41, 41), ('havazás', 16, 16),
    ('zivatar', 4, 47),
    ('gyenge zápor', 40, 40), ('zápor', 11, 11),
    ('szitálás', 9, 9),
    ('gyenge eső', 11, 11), ('eső', 12, 12),
    ('köd', 20, 20), ('pára', 21, 21), ('füst', 22, 22), ('por', 19, 19),
    ('borult', 26, 26),
    ('erősen felhős', 28, 27), ('közepesen felhős', 30, 29),
    ('gyengén felhős', 34, 33), ('fátyolfelhős', 34, 33), ('felhős', 30, 29),
    ('derült', 32, 31), ('napos', 32, 31), ('tiszta', 32, 31),
    ('szeles', 24, 24), ('viharos', 23, 23), ('hó', 16, 16),
)
# Tartalék, ha a szöveg ismeretlen: az ikonkód két utolsó jegye alapján
_ICON_RULES = {'10': (32, 31), '21': (34, 33), '22': (30, 29), '23': (28, 27), '30': (26, 26),
               '81': (11, 11)}


def page_url(slug):
    return '%s/idojaras/%s' % (BASE, quote(slug))


def kodi_code(text, icon=''):
    night = bool(icon) and icon.startswith('3')
    t = (text or '').lower()
    for key, day_code, night_code in _TEXT_RULES:
        if key in t:
            return night_code if night else day_code
    pair = _ICON_RULES.get((icon or '')[-2:])
    if pair:
        return pair[1] if night else pair[0]
    return 'na'


def _clean(s):
    s = re.sub(r'<[^>]+>', ' ', s or '')
    s = s.replace('&nbsp;', ' ').replace('&deg;', '°').replace('&amp;', '&')
    return re.sub(r'\s+', ' ', s).strip()


def _num(s):
    try:
        return float(s.replace(',', '.'))
    except (AttributeError, ValueError):
        return None


def _first(pattern, html, flags=re.S):
    m = re.search(pattern, html, flags)
    return m.group(1) if m else ''


def _hhmm(s):
    m = re.match(r'(\d{1,2}):(\d{2})', s or '')
    return '%02d:%s' % (int(m.group(1)), m.group(2)) if m else ''


def parse(html, now=None):
    """Az oldal HTML-jéből a közös modell. now: helyi idő (a 3 órás kártyák dátumához)."""
    now = now or datetime.datetime.now()
    out = {'source': 'ik', 'current': {}, 'hourly': [], 'daily': [], 'water': []}

    # --- jelenlegi idő
    text = _clean(_first(r'class="current-weather">(.*?)</div>', html))
    icon = _first(r'forecast-bigicon"[^>]*?src="[^"]*?forecastIcons/(\d+)\.svg"', html)
    temp = _num(_first(r'current-temperature">\s*(-?\d+(?:[.,]\d+)?)', html))
    if temp is None and not text:
        raise ValueError('Időkép: nem található a jelenlegi idő (változott az oldal?)')
    out['current'] = {'temp': temp, 'text': text, 'code': kodi_code(text, icon), 'icon': icon}
    out['city'] = _clean(_first(r'id="currentCity">(.*?)</span>', html))
    out['headline'] = _clean(_first(r'class="shortWeatherTitle[^"]*">(.*?)</div>', html))
    out['description'] = _clean(_first(r'class="scTextDescription">(.*?)</div>', html))
    out['summary'] = _clean(_first(r'<meta name="Description"[^>]*content="([^"]*)"', html))
    out['sunrise'] = _hhmm(_first(r'Napkelte:\s*(\d{1,2}:\d{2})', html))
    out['sunset'] = _hhmm(_first(r'Napnyugta:\s*(\d{1,2}:\d{2})', html))

    # --- 3 órás előrejelzés
    day = now.date()
    prev_h = None
    for i, card in enumerate(html.split('class="ik hourly-forecast-card"')[1:]):
        m = re.search(r'hourly-forecast-hour">\s*(\d{1,2}):(\d{2})', card)
        if not m:
            continue
        hour, minute = int(m.group(1)), int(m.group(2))
        if prev_h is None:
            if hour < now.hour - 2:          # késő este az első kártya már holnapi
                day += datetime.timedelta(days=1)
        elif hour < prev_h:
            day += datetime.timedelta(days=1)
        prev_h = hour
        ic = _first(r'forecast-icon"[^>]*?src="[^"]*?forecastIcons/(\d+)\.svg"', card)
        alt = _clean(_first(r'<img class="ik forecast-icon"[^>]*?alt="([^"]*)"', card))
        t = _num(_first(r'Várható hőmérséklet:\s*(-?\d+(?:[.,]\d+)?)', card))
        if t is None:
            t = _num(_first(r'temperature-circled[^>]*>\s*(-?\d+)', card))
        out['hourly'].append({
            'dt': '%sT%02d:%02d' % (day.isoformat(), hour, minute),
            'temp': t, 'text': alt[:1].upper() + alt[1:], 'code': kodi_code(alt, ic),
        })

    # --- napi (15 napos) előrejelzés
    for col in html.split('class="ik dailyForecastCol"')[1:]:
        m = re.search(r'title="[^"<]*<br>\s*(\d{4})\.\s*([^\s\d]+)\s+(\d{1,2})\.', col)
        if not m or m.group(2).lower() not in HU_MONTHS:
            continue
        date = datetime.date(int(m.group(1)), HU_MONTHS.index(m.group(2).lower()) + 1,
                             int(m.group(3)))
        fm = re.search(r"forecastIcons/(\d+)\.svg'\s+alt='([^']*)'", col)
        ic, dtext = (fm.group(1), _clean(fm.group(2))) if fm else ('', '')
        alerts = [_clean(a) for a in
                  re.findall(r"alertIcons/[^']+'\s+alt='[^']*'>([^<]+)", col)]
        tmax = _num(_first(r'class="ik max".*?">\s*(-?\d+)\s*</a>', col))
        tmin = _num(_first(r'class="ik min".*?">\s*(-?\d+)\s*</a>', col))
        out['daily'].append({
            'date': date.isoformat(), 'tmax': tmax, 'tmin': tmin,
            'text': dtext[:1].upper() + dtext[1:], 'code': kodi_code(dtext, ic),
            'alerts': [a for a in alerts if a],
        })

    # --- vízhőmérsékletek (extra)
    for name, wt in re.findall(r'<div class="title">([^<]+)</div>\s*<div class="pill background '
                               r'identityBlue">\s*(-?\d+)(?:&deg;|°)C', html):
        out['water'].append({'name': _clean(name), 'temp': _num(wt)})
    return out


def fetch(slug, now=None):
    return parse(http_get(page_url(slug)), now)
