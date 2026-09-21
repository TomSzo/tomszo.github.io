# -*- coding: utf-8 -*-
"""
SubVito - core scraper for subvito.eu (South Park magyarul).

A subvito.eu egy WordPress-alapú oldal. A linkek felépítése:
    https://subvito.eu/<evad>-evad/<resz-slug>/
Ezért a böngészés URL-minta alapú (nem függ a téma CSS osztályaitól),
így akkor is működik, ha az oldal kinézete változik.

A lejátszáshoz az epizód-oldalról kinyerjük az iframe beágyazásokat és a
közvetlen mp4 / m3u8 linkeket. Minden talált forrást naplózunk (xbmc.log),
hogy a nem működő eseteket a logból finomíthassuk.
"""
import re
import sys

try:
    from urllib.parse import urljoin, quote_plus, urlparse, unquote
except ImportError:  # Python 2 (nem támogatott, csak biztonságból)
    from urlparse import urljoin, urlparse
    from urllib import quote_plus, unquote

import xbmc
import xbmcaddon

try:
    import requests
    HAVE_REQUESTS = True
except ImportError:
    HAVE_REQUESTS = False
    try:
        from urllib.request import Request, urlopen
    except ImportError:
        from urllib2 import Request, urlopen

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')

DEFAULT_BASE = 'https://subvito.eu/'

USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')

# South Park évadok száma – tartalék, ha a főoldalról nem sikerül kiolvasni.
FALLBACK_SEASON_COUNT = 27


def log(msg, level=xbmc.LOGINFO):
    xbmc.log('[%s] %s' % (ADDON_ID, msg), level)


def base_url():
    url = ADDON.getSetting('base_url') or DEFAULT_BASE
    url = url.strip()
    if not url:
        url = DEFAULT_BASE
    if not url.endswith('/'):
        url += '/'
    if not url.startswith('http'):
        url = 'https://' + url
    return url


def _headers(referer=None):
    h = {
        'User-Agent': USER_AGENT,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'hu-HU,hu;q=0.9,en;q=0.5',
    }
    if referer:
        h['Referer'] = referer
    return h


def fetch(url, referer=None, timeout=20):
    """Letölti az URL-t és visszaadja a szöveges tartalmat (üres string hiba esetén)."""
    log('GET %s' % url)
    try:
        if HAVE_REQUESTS:
            resp = requests.get(url, headers=_headers(referer), timeout=timeout)
            if resp.status_code != 200:
                log('HTTP %s a(z) %s címről' % (resp.status_code, url), xbmc.LOGWARNING)
            resp.encoding = resp.apparent_encoding or 'utf-8'
            return resp.text
        else:
            req = Request(url, headers=_headers(referer))
            data = urlopen(req, timeout=timeout).read()
            return data.decode('utf-8', 'replace')
    except Exception as exc:  # noqa
        log('Letöltési hiba: %s (%s)' % (exc, url), xbmc.LOGERROR)
        return ''


def _abs(href, base=None):
    return urljoin(base or base_url(), href)


def _clean_text(html):
    text = re.sub(r'<[^>]+>', ' ', html or '')
    text = re.sub(r'\s+', ' ', text).strip()
    # gyakori HTML entitások
    for a, b in (('&amp;', '&'), ('&#8211;', '–'), ('&#8217;', "'"),
                 ('&#8230;', '…'), ('&nbsp;', ' '), ('&quot;', '"'),
                 ('&#039;', "'"), ('&hellip;', '…')):
        text = text.replace(a, b)
    return text.strip()


def _title_from_slug(slug):
    slug = unquote(slug)
    slug = slug.replace('-', ' ').replace('_', ' ').strip()
    return slug[:1].upper() + slug[1:] if slug else slug


# ---------------------------------------------------------------------------
# Évadok
# ---------------------------------------------------------------------------
def list_seasons():
    """Visszaad egy [(evad_szam, url), ...] listát növekvő sorrendben."""
    html = fetch(base_url())
    seasons = {}
    if html:
        for m in re.finditer(r'href=["\']([^"\']*?/(\d{1,2})-evad/?)["\']', html):
            url = _abs(m.group(1))
            num = int(m.group(2))
            seasons.setdefault(num, url)

    if not seasons:
        log('A főoldalról nem sikerült évadokat kiolvasni, tartalék lista használata.',
            xbmc.LOGWARNING)
        for num in range(1, FALLBACK_SEASON_COUNT + 1):
            seasons[num] = _abs('%d-evad/' % num)

    return [(num, seasons[num]) for num in sorted(seasons)]


# ---------------------------------------------------------------------------
# Részek
# ---------------------------------------------------------------------------
def _parse_episode_anchors(html, base):
    """<a href=.../N-evad/slug/...>...</a> blokkokból (cím, url, kép) hármasok."""
    results = []
    seen = set()
    pattern = re.compile(
        r'<a\b[^>]*?href=["\']([^"\']*?/\d{1,2}-evad/([^"\'/?#]+)/?)["\'][^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL)
    for m in pattern.finditer(html):
        url = _abs(m.group(1), base)
        slug = m.group(2).lower()
        inner = m.group(3)
        if slug in seen:
            continue
        # lapozás / navigáció kiszűrése
        if slug.isdigit() or slug in ('page', 'oldal', 'evad'):
            continue
        seen.add(slug)

        title = _clean_text(inner)
        if not title:
            # próbáljuk az anchoron kívüli címattribútumból vagy a slugból
            title = _title_from_slug(slug)

        img = None
        img_m = re.search(r'<img[^>]+(?:data-src|data-lazy-src|src)=["\']([^"\']+)["\']',
                          inner, re.IGNORECASE)
        if img_m:
            img = _abs(img_m.group(1), base)

        results.append({'title': title, 'url': url, 'thumb': img, 'slug': slug})
    return results


def list_episodes(season_url):
    """Egy évad-oldal részeinek listája."""
    html = fetch(season_url)
    if not html:
        return []
    eps = _parse_episode_anchors(html, season_url)
    log('%d rész találat: %s' % (len(eps), season_url))
    return eps


# ---------------------------------------------------------------------------
# Keresés
# ---------------------------------------------------------------------------
def search(query):
    url = base_url() + '?s=' + quote_plus(query)
    html = fetch(url)
    if not html:
        return []
    eps = _parse_episode_anchors(html, url)
    log('%d keresési találat: "%s"' % (len(eps), query))
    return eps


# ---------------------------------------------------------------------------
# Legfrissebb részek (főoldal)
# ---------------------------------------------------------------------------
def list_latest():
    html = fetch(base_url())
    if not html:
        return []
    eps = _parse_episode_anchors(html, base_url())
    log('%d legfrissebb rész a főoldalon' % len(eps))
    return eps


# ---------------------------------------------------------------------------
# Lejátszható forrás kinyerése
# ---------------------------------------------------------------------------
_MEDIA_RE = re.compile(r'https?://[^"\'\s<>\\]+?\.(?:m3u8|mp4|mkv)(?:\?[^"\'\s<>\\]*)?',
                       re.IGNORECASE)
_IFRAME_RE = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
_SOURCE_RE = re.compile(r'<source[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
# JS lejátszó-konfig mezők: file: "...", source: "...", src: "..."
_JSFIELD_RE = re.compile(r'(?:file|source|src)\s*[:=]\s*["\']([^"\']+\.(?:m3u8|mp4|mkv)[^"\']*)["\']',
                         re.IGNORECASE)
_SUB_RE = re.compile(r'https?://[^"\'\s<>\\]+?\.(?:srt|vtt|ass)(?:\?[^"\'\s<>\\]*)?',
                     re.IGNORECASE)


def _collect_media(html, base):
    media = []
    for rx in (_MEDIA_RE, _JSFIELD_RE, _SOURCE_RE):
        for m in rx.finditer(html):
            media.append(_abs(m.group(m.lastindex or 1) if m.groups() else m.group(0), base))
    return media


def resolve(episode_url):
    """
    Visszaad egy dict-et: {'media': [...], 'iframes': [...], 'subs': [...]}.
    media = közvetlen lejátszható linkek (m3u8/mp4), iframes = beágyazások.
    """
    html = fetch(episode_url)
    result = {'media': [], 'iframes': [], 'subs': []}
    if not html:
        return result

    media = _collect_media(html, episode_url)
    iframes = [_abs(u, episode_url) for u in _IFRAME_RE.findall(html)]
    subs = [_abs(u, episode_url) for u in _SUB_RE.findall(html)]

    # Iframe beágyazások egy szintű követése közvetlen média után.
    for frame in list(iframes):
        if _MEDIA_RE.search(frame):
            media.append(frame)
            continue
        # kihagyjuk a nyilvánvalóan nem lejátszható beágyazásokat (reklám, közösségi)
        host = urlparse(frame).netloc.lower()
        if any(bad in host for bad in ('facebook.', 'disqus.', 'google.', 'youtube.com/embed/subscribe')):
            continue
        sub_html = fetch(frame, referer=episode_url)
        if sub_html:
            media.extend(_collect_media(sub_html, frame))
            subs.extend(_abs(u, frame) for u in _SUB_RE.findall(sub_html))

    # dedup, sorrend: m3u8 elöl, majd mp4/mkv
    def _key(u):
        ul = u.lower()
        if '.m3u8' in ul:
            return 0
        if '.mp4' in ul:
            return 1
        return 2

    media = sorted(_dedup(media), key=_key)
    result['media'] = media
    result['iframes'] = _dedup(iframes)
    result['subs'] = _dedup(subs)

    log('resolve(%s) -> media=%s iframes=%s subs=%s'
        % (episode_url, result['media'], result['iframes'], result['subs']))
    return result


def _dedup(seq):
    seen = set()
    out = []
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out
