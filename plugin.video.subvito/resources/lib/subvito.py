# -*- coding: utf-8 -*-
"""
SubVito - core scraper for subvito.eu (South Park magyarul).

Az oldal WordPress-alapú. Minden oldal fejlécében ott a teljes menü
(navbar), amely tartalmazza az összes évadot/kategóriát és azok részeit,
címmel együtt. Ezt egyetlen kéréssel kiolvassuk -> ebből épül a katalógus.

Kategória URL-ek:
    https://subvito.eu/<N>-evad/        (2..29. évad)
    https://subvito.eu/1-evad-2/        (1. évad – eltérő slug!)
    https://subvito.eu/filmek/          (Filmek)
    https://subvito.eu/paramount-plus/  (P+)

Egy rész oldalán a lejátszható videó közvetlen MP4-ként van beágyazva:
    <video ...><source src="http://spdl.subvito.eu/.../xxx.mp4" ...>
                <track  src="https://subvito.eu/Feliratok/.../xxxhun.vtt" ...></video>
Innen nyerjük ki a videót és a magyar/angol feliratot.
"""
import re

try:
    from urllib.parse import urljoin, urlparse, unquote
except ImportError:
    from urlparse import urljoin, urlparse
    from urllib import unquote

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

# Egy futáson belüli memória-gyorsítótár a katalógusnak (a homepage nagy).
_CATALOG_CACHE = None


def log(msg, level=xbmc.LOGINFO):
    xbmc.log('[%s] %s' % (ADDON_ID, msg), level)


def base_url():
    url = (ADDON.getSetting('base_url') or DEFAULT_BASE).strip()
    if not url:
        url = DEFAULT_BASE
    if not url.startswith('http'):
        url = 'https://' + url
    if not url.endswith('/'):
        url += '/'
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
    """Letölti az URL-t, visszaadja a szöveges tartalmat (üres string hiba esetén)."""
    log('GET %s' % url)
    try:
        if HAVE_REQUESTS:
            resp = requests.get(url, headers=_headers(referer), timeout=timeout)
            if resp.status_code != 200:
                log('HTTP %s: %s' % (resp.status_code, url), xbmc.LOGWARNING)
            resp.encoding = resp.apparent_encoding or 'utf-8'
            return resp.text
        req = Request(url, headers=_headers(referer))
        return urlopen(req, timeout=timeout).read().decode('utf-8', 'replace')
    except Exception as exc:  # noqa
        log('Letöltési hiba: %s (%s)' % (exc, url), xbmc.LOGERROR)
        return ''


def _abs(href, base=None):
    return urljoin(base or base_url(), (href or '').strip())


_ENTITIES = (('&amp;', '&'), ('&#8211;', '–'), ('&#8212;', '—'),
             ('&#8217;', "'"), ('&#8216;', "'"), ('&#8230;', '…'),
             ('&nbsp;', ' '), ('&quot;', '"'), ('&#039;', "'"),
             ('&#215;', '×'), ('&hellip;', '…'), ('&amp;#215;', '×'))


def _clean_text(html):
    text = re.sub(r'<[^>]+>', ' ', html or '')
    for a, b in _ENTITIES:
        text = text.replace(a, b)
    return re.sub(r'\s+', ' ', text).strip()


# ---------------------------------------------------------------------------
# Katalógus (navbar) feldolgozás
# ---------------------------------------------------------------------------
def _between(text, start_marker, end_marker):
    i = text.find(start_marker)
    if i < 0:
        return ''
    j = text.find(end_marker, i)
    return text[i:j] if j > 0 else text[i:]


def _pretty_category(label, url):
    m = re.search(r'/(\d{1,2})-evad', url)
    if m:
        return '%s. évad' % int(m.group(1))
    low = url.lower()
    if 'filmek' in low:
        return 'Filmek'
    if 'paramount' in low:
        return 'P+ (Paramount+)'
    label = label.strip()
    if label.isdigit():
        return '%s. évad' % label
    return label or url


def _sort_key(cat):
    """Évadok csökkenő sorrendben elöl, Filmek/P+ a végén."""
    m = re.search(r'/(\d{1,2})-evad', cat['url'])
    if m:
        return (0, -int(m.group(1)))
    return (1, 0)


def _parse_navbar(html):
    """A navbar-menüből kategóriák + részek kiolvasása."""
    nav = _between(html, 'class="main-navbar"', '</nav>') or html
    cats = []
    seen = set()
    chunks = re.split(r'<li class="navbar-item">', nav)[1:]
    for ch in chunks:
        m = re.search(r'<a\s+href="([^"]+)"[^>]*>(.*?)</a>', ch, re.DOTALL | re.IGNORECASE)
        if not m:
            continue
        cat_url = _abs(m.group(1))
        if cat_url in seen:
            continue
        seen.add(cat_url)
        label = _pretty_category(_clean_text(m.group(2)), cat_url)
        episodes = []
        ep_seen = set()
        for em in re.finditer(
                r'<li class="dropdown-item"><a\s+href="([^"]+)"[^>]*>(.*?)</a>',
                ch, re.DOTALL | re.IGNORECASE):
            ep_url = _abs(em.group(1))
            if ep_url in ep_seen:
                continue
            ep_seen.add(ep_url)
            episodes.append({'title': _clean_text(em.group(2)), 'url': ep_url})
        cats.append({'url': cat_url, 'label': label, 'episodes': episodes})
    return cats


def get_catalog(force=False):
    """A teljes katalógus (kategóriák + részek). Futáson belül gyorsítótárazva."""
    global _CATALOG_CACHE
    if _CATALOG_CACHE is not None and not force:
        return _CATALOG_CACHE

    html = fetch(base_url())
    cats = _parse_navbar(html) if html else []

    if not cats and html:
        # Tartalék: legalább a kategória-URL-eket gyűjtsük ki minta alapján.
        urls = {}
        for m in re.finditer(r'href="([^"]*?/(?:\d{1,2}-evad(?:-\d+)?|filmek|paramount-plus)/?)"', html):
            u = _abs(m.group(1))
            urls.setdefault(u, {'url': u, 'label': _pretty_category('', u), 'episodes': []})
        cats = list(urls.values())

    cats.sort(key=_sort_key)
    _CATALOG_CACHE = cats
    log('Katalógus: %d kategória' % len(cats))
    return cats


# ---------------------------------------------------------------------------
# Publikus lekérdezések
# ---------------------------------------------------------------------------
def list_categories():
    return get_catalog()


def list_episodes(category_url):
    for cat in get_catalog():
        if cat['url'].rstrip('/') == (category_url or '').rstrip('/'):
            return cat['episodes']
    # Ha nincs a katalógusban, próbáljuk közvetlenül az oldalról (tartalék).
    html = fetch(category_url)
    if not html:
        return []
    for cat in _parse_navbar(html):
        if cat['url'].rstrip('/') == category_url.rstrip('/'):
            return cat['episodes']
    return []


def list_latest(limit=15):
    """A legfrissebb (legnagyobb sorszámú) évad részei."""
    for cat in get_catalog():
        if re.search(r'/\d{1,2}-evad', cat['url']) and cat['episodes']:
            return list(reversed(cat['episodes']))[:limit]
    return []


def search(query):
    """Helyi keresés a katalógus címei között (ékezet-érzéketlen)."""
    q = _fold(query)
    results = []
    for cat in get_catalog():
        for ep in cat['episodes']:
            if q in _fold(ep['title']):
                results.append({'title': '%s  ·  %s' % (ep['title'], cat['label']),
                                'url': ep['url']})
    log('%d keresési találat: "%s"' % (len(results), query))
    return results


def _fold(text):
    text = (text or '').lower()
    for a, b in (('á', 'a'), ('é', 'e'), ('í', 'i'), ('ó', 'o'), ('ö', 'o'),
                 ('ő', 'o'), ('ú', 'u'), ('ü', 'u'), ('ű', 'u')):
        text = text.replace(a, b)
    return text


# ---------------------------------------------------------------------------
# Lejátszható forrás kinyerése
# ---------------------------------------------------------------------------
_MEDIA_RE = re.compile(r'https?://[^"\'\s<>\\]+?\.(?:m3u8|mp4|mkv)(?:\?[^"\'\s<>\\]*)?',
                       re.IGNORECASE)
_SOURCE_RE = re.compile(r'<source[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
_IFRAME_RE = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
_JSFIELD_RE = re.compile(
    r'(?:file|source|src)\s*[:=]\s*["\']([^"\']+\.(?:m3u8|mp4|mkv)[^"\']*)["\']',
    re.IGNORECASE)
_TRACK_RE = re.compile(
    r'<track[^>]+src=["\']([^"\']+)["\'][^>]*(?:srclang=["\']([^"\']*)["\'])?', re.IGNORECASE)
_SUB_RE = re.compile(r'https?://[^"\'\s<>\\]+?\.(?:srt|vtt|ass)(?:\?[^"\'\s<>\\]*)?',
                     re.IGNORECASE)


def _collect_media(html, base):
    media = []
    for m in _SOURCE_RE.finditer(html):
        media.append(_abs(m.group(1), base))
    for m in _JSFIELD_RE.finditer(html):
        media.append(_abs(m.group(1), base))
    for m in _MEDIA_RE.finditer(html):
        media.append(_abs(m.group(0), base))
    return media


def _collect_subs(html, base):
    """Feliratok, magyar előre sorolva."""
    subs = []
    for m in _TRACK_RE.finditer(html):
        url = _abs(m.group(1), base)
        lang = (m.group(2) or '').lower()
        subs.append((0 if lang.startswith('hu') else 1, url))
    for url in _SUB_RE.findall(html):
        u = _abs(url, base)
        is_hu = 'hun' in u.lower() or '/29/' in u  # 'hun' a fájlnévben
        subs.append((0 if is_hu else 2, u))
    subs.sort(key=lambda t: t[0])
    return _dedup([u for _, u in subs])


def resolve(episode_url):
    """
    Visszaad: {'media': [...], 'iframes': [...], 'subs': [...]}.
    media = közvetlenül lejátszható linkek (mp4/m3u8/mkv).
    """
    html = fetch(episode_url)
    result = {'media': [], 'iframes': [], 'subs': []}
    if not html:
        return result

    media = _collect_media(html, episode_url)
    iframes = [_abs(u, episode_url) for u in _IFRAME_RE.findall(html)]
    subs = _collect_subs(html, episode_url)

    # Iframe beágyazások egy szintű követése, ha nincs közvetlen média.
    if not media:
        for frame in iframes:
            host = urlparse(frame).netloc.lower()
            if any(b in host for b in ('facebook.', 'disqus.', 'google.', 'gravatar.')):
                continue
            if _MEDIA_RE.search(frame):
                media.append(frame)
                continue
            sub_html = fetch(frame, referer=episode_url)
            if sub_html:
                media.extend(_collect_media(sub_html, frame))
                subs.extend(_collect_subs(sub_html, frame))

    def _rank(u):
        ul = u.lower()
        return 0 if '.m3u8' in ul else (1 if '.mp4' in ul else 2)

    result['media'] = sorted(_dedup(media), key=_rank)
    result['iframes'] = _dedup(iframes)
    result['subs'] = _dedup(subs)
    log('resolve(%s) -> media=%s subs=%s iframes=%s'
        % (episode_url, result['media'], result['subs'], result['iframes']))
    return result


def _dedup(seq):
    seen = set()
    out = []
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out
