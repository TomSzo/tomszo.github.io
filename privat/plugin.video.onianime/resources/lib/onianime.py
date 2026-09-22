# -*- coding: utf-8 -*-
"""
OniAnime (onianime.hu) - nyilvános JSON API kliens.

FONTOS - KÉRÉS-TAKARÉKOSSÁG (az oldal szerverének kímélése):
  Ez az addon KIZÁRÓLAG a lejátszáshoz feltétlenül szükséges 3 végpontot hívja:
    - GET /api/catalog?page=N[&search=...]     (böngészés / keresés)
    - GET /api/anime/{id}/episodes             (epizódlista)
    - GET /api/anime/{id}/parts?episode=N&type=sub|dub&server=karks  (videó-forrás)
  A weboldal által küldött sok egyéb hívást (viewers, watched, comments,
  recommendations, metadata, news, users/*, continue, message, ...) NEM csináljuk,
  és semmilyen POST-ot (watched/viewers) sem küldünk - így nem terheljük feleslegesen
  a szerverüket és nem torzítjuk a statisztikájukat.
  Egy művelet = egy kérés. A lejátszás 0 további kérés (a videa-URL már megvan).

Belépés NEM kell (guest hozzáférés). A videó közvetlen videa.hu MP4 (nincs feloldás).
"""
import json
import re

try:
    from urllib.parse import urljoin, quote
except ImportError:  # Py2
    from urlparse import urljoin
    from urllib import quote

import xbmc
import xbmcaddon

try:
    import requests
    HAVE_REQUESTS = True
except ImportError:  # noqa
    HAVE_REQUESTS = False

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
BASE = 'https://onianime.hu/'
# Alapértelmezett UA: modern Android Firefox (mint a magyaranime addonnál).
DEFAULT_UA = 'Mozilla/5.0 (Android 16; Mobile; rv:156.0) Gecko/156.0 Firefox/156.0'
_SESSION = requests.Session() if HAVE_REQUESTS else None


def log(msg, level=xbmc.LOGINFO):
    xbmc.log('[%s] %s' % (ADDON_ID, msg), level)


def user_agent():
    return (ADDON.getSetting('user_agent') or '').strip() or DEFAULT_UA


def _headers(referer=None):
    h = {'User-Agent': user_agent(),
         'Accept': 'application/json, text/plain, */*',
         'Accept-Language': 'hu-HU,hu;q=0.9,en;q=0.5'}
    if referer:
        h['Referer'] = referer
    return h


def _get_json(path, referer=None, timeout=20):
    """Egyetlen GET kérés JSON-válaszra. Hiba esetén None (nincs agresszív retry)."""
    url = urljoin(BASE, path)
    log('GET %s' % url)
    if not _SESSION:
        return None
    try:
        r = _SESSION.get(url, headers=_headers(referer or BASE), timeout=timeout)
        r.encoding = 'utf-8'
        return r.json()
    except ValueError:
        log('Nem JSON válasz: %s' % url, xbmc.LOGWARNING)
        return None
    except Exception as exc:  # noqa
        log('GET hiba: %s (%s)' % (exc, url), xbmc.LOGERROR)
        return None


def _clean(t):
    t = (t or '')
    for a, b in (('&amp;', '&'), ('&#039;', "'"), ('&quot;', '"'), ('&nbsp;', ' '),
                 ('&lt;', '<'), ('&gt;', '>')):
        t = t.replace(a, b)
    return t.strip()


# ---------------------------------------------------------------------------
# Katalógus / keresés  (1 kérés / oldal)
# ---------------------------------------------------------------------------
def catalog(page=1, search=None):
    """Egy katalógus-oldal (vagy keresés). Visszaad: {items, page, pages}."""
    page = max(1, int(page or 1))
    if search:
        data = _get_json('api/catalog?page=%d&search=%s' % (page, quote(search)))
    else:
        data = _get_json('api/catalog?page=%d' % page)
    if not isinstance(data, dict):
        return {'items': [], 'page': page, 'pages': 1}
    items = [_anime_item(a) for a in (data.get('animes') or []) if isinstance(a, dict)]
    pages = int(data.get('totalPages') or 1)
    log('%d anime (oldal %d/%d)%s'
        % (len(items), page, pages, (' - keresés: %s' % search) if search else ''))
    return {'items': items, 'page': page, 'pages': pages}


def search(term):
    return catalog(1, search=(term or '').strip())


def _anime_item(a):
    title = _clean(a.get('name') or a.get('eng_name') or ('anime %s' % a.get('id')))
    sub = int(a.get('sub_count') or 0)
    dub = int(a.get('dub_count') or 0)
    parts_label = []
    if sub:
        parts_label.append('Felirat')
    if dub:
        parts_label.append('Szinkron')
    return {'aid': str(a.get('id')),
            'title': title,
            'art': a.get('image') or '',
            'plot': _clean(a.get('description') or ''),
            'type': _clean(a.get('type') or ''),
            'year': a.get('release_year') or '',
            'studio': _clean(a.get('studio') or ''),
            'status': _clean(a.get('status') or ''),
            'sub': sub, 'dub': dub,
            'avail': '/'.join(parts_label)}


# ---------------------------------------------------------------------------
# Epizódlista  (1 kérés / anime)
# ---------------------------------------------------------------------------
def episodes(aid):
    """Egy anime epizódlistája. Visszaad: {title, plot, art, episodes:[...]}"""
    data = _get_json('api/anime/%s/episodes' % aid, referer=BASE + 'watch/%s/1' % aid)
    out = []
    title = ''
    art = ''
    if isinstance(data, dict):
        for e in (data.get('episodes') or []):
            if not isinstance(e, dict):
                continue
            try:
                epnum = int(e.get('ep'))
            except (TypeError, ValueError):
                continue
            out.append({'ep': epnum,
                        'title': _clean(e.get('title') or ''),
                        'plot': _clean(e.get('description') or ''),
                        'thumb': e.get('thumbnail') or '',
                        'hasSub': bool(e.get('hasSub')),
                        'hasDub': bool(e.get('hasDub'))})
        meta = data.get('meta') or {}
        title = _clean(meta.get('name') or meta.get('eng_name') or '')
        art = meta.get('image') or ''
    out.sort(key=lambda x: x['ep'])
    log('%d epizód: anime %s' % (len(out), aid))
    return {'title': title, 'art': art, 'episodes': out}


# ---------------------------------------------------------------------------
# Videó-források egy epizódhoz  (1 kérés / epizód+típus)
# ---------------------------------------------------------------------------
def parts(aid, ep, voice='sub', server='karks'):
    """Egy epizód forrásai. A 'sources' KÖZVETLEN videa.hu MP4-ek, minőség-címkével.
    Visszaad: [{'url', 'label'}] (magasabb felbontás elöl)."""
    voice = 'dub' if str(voice).lower().startswith('d') else 'sub'
    data = _get_json('api/anime/%s/parts?episode=%d&type=%s&server=%s'
                     % (aid, int(ep), voice, server),
                     referer=BASE + 'watch/%s/1' % aid)
    out = []
    if isinstance(data, dict):
        for s in (data.get('sources') or []):
            if not isinstance(s, dict):
                continue
            url = s.get('src')
            if not url:
                continue
            out.append({'url': url, 'label': _clean(s.get('label') or '')})
    out.sort(key=lambda x: _res_rank(x['label']), reverse=True)
    log('%d forrás: anime %s ep %s (%s)' % (len(out), aid, ep, voice))
    return out


def _res_rank(label):
    m = re.search(r'(\d{3,4})', label or '')
    return int(m.group(1)) if m else 0
