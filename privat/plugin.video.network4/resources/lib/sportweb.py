# -*- coding: utf-8 -*-
"""
Sport kategóriák a www.network4.hu/sport/collections oldal szerint.

Az oldal szerkezete (a tulajdonos által küldött HTML alapján):
    <section aria-label="Kiemelt sportok"> ... league-card-ok
    <div class="sport-cat" aria-label="Labdarúgás">
        <h3 class="sport-cat__title">Labdarúgás <span class="sport-cat__count">(12)</span></h3>
        <a href="/sport/collection/details/premier-league" class="league-card ...">
            <img src="https://imagedelivery.net/.../public" alt="Premier League">
        <div class="league-card__name">Premier League</div>
A slug (pl. "premier-league") ugyanaz, mint a mobil API gyűjtemény-azonosítója, így a
videókat a /api/collectionitems/<slug>/11 adja (net4api.collection_items).

Az oldalt legfeljebb naponta egyszer töltjük le; ha nem sikerül, a beépített
pillanatkép (resources/sports.json) szolgál.
"""
import json
import os
import re

try:
    from html import unescape
except ImportError:  # py2
    from HTMLParser import HTMLParser
    unescape = HTMLParser().unescape

from resources.lib import net4api as api

PAGE_URL = 'https://www.network4.hu/sport/collections'
TTL = 24 * 3600
SNAPSHOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'sports.json')

_CARD_RE = re.compile(r'href="/sport/collection/details/([^"/?#]+)"(.*?)'
                      r'<div class="league-card__name">(.*?)</div>', re.S)
_IMG_RE = re.compile(r'<img src="([^"]+)"')


def _txt(s):
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip()


def _cards(chunk):
    out, seen = [], set()
    for slug, body, name in _CARD_RE.findall(chunk):
        if slug in seen:
            continue
        seen.add(slug)
        im = _IMG_RE.search(body)
        out.append({'slug': slug, 'name': _txt(name) or slug, 'img': im.group(1) if im else ''})
    return out


def parse(html):
    """-> [{'title': 'Kiemelt sportok', 'items': [{'slug','name','img'}, ...]}, ...]"""
    html = html or ''
    cats = []
    start = html.find('aria-label="Kiemelt sportok"')
    end = html.find('aria-label="Összes sport"')
    if start >= 0:
        items = _cards(html[start:end if end > start else len(html)])
        if items:
            cats.append({'title': 'Kiemelt sportok', 'items': items})
    parts = html.split('<div class="sport-cat" aria-label="')[1:]
    for part in parts:
        title = _txt(part.split('"', 1)[0])
        items = _cards(part)
        if title and items:
            cats.append({'title': title, 'items': items})
    return cats


def snapshot():
    try:
        with open(SNAPSHOT, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return []


def _fetch():
    resp = api._http(PAGE_URL, {'User-Agent': api.FIREFOX_UA,
                                'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
                                'Accept-Language': 'hu-HU,hu;q=0.9'})
    if resp.status_code != 200:
        raise api.ApiError('HTTP %s: /sport/collections' % resp.status_code)
    cats = parse(resp.text)
    if not cats:
        api._save_debug('last_sport_collections.html', resp.text)
        raise api.ApiError('A sport-oldal szerkezete megváltozott (mentve)')
    return cats


def categories():
    """Friss (napi) lista a weboldalról; hiba esetén a korábbi / beépített pillanatkép."""
    if api.ADDON.getSetting('sport_web') == 'false':
        return snapshot()
    try:
        return api.cached('sport_collections', TTL, _fetch) or snapshot()
    except api.ApiError as exc:
        api.log('sport kategóriák a pillanatképből (%s)' % exc)
        return snapshot()
