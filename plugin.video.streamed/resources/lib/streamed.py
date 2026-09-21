# -*- coding: utf-8 -*-
"""
Streamed - kliens a streamed.pk nyilvános API-jához.

Dokumentált végpontok (base = https://streamed.pk/):
    GET api/sports                      -> [{id, name}, ...]
    GET api/matches/live                -> élő most
    GET api/matches/all                 -> minden meccs
    GET api/matches/all-today           -> mai meccsek
    GET api/matches/all/popular         -> népszerűek
    GET api/matches/<sport>             -> egy sportág meccsei
    GET api/matches/<sport>/popular     -> egy sportág népszerű meccsei
    GET api/stream/<source>/<id>        -> [{id, streamNo, language, hd, source, embedUrl?}, ...]

Meccs-objektum:
    {id, title, category, date(ms), popular, poster?, finished,
     teams?: {home:{name,badge}, away:{name,badge}}, sources:[{source,id}, ...]}

Lejátszás: a stream embed-oldaláról próbáljuk kinyerni az m3u8-at
(a player reklám-/adblock-védett, ezért ez best-effort és a Kodin élesítendő).
"""
import json
import re
import time

try:
    from urllib.parse import urljoin, urlparse
except ImportError:
    from urlparse import urljoin, urlparse

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

DEFAULT_BASE = 'https://streamed.pk/'
DEFAULT_EMBED = 'https://embed.st/'

USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')

# Munkamenet a sütik (Set-Cookie) elkapásához, hogy a lejátszónak átadhassuk.
_SESSION = requests.Session() if HAVE_REQUESTS else None


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


def embed_base():
    return DEFAULT_EMBED


def _headers(referer=None, json_accept=False):
    h = {
        'User-Agent': USER_AGENT,
        'Accept': 'application/json, text/plain, */*' if json_accept
        else 'text/html,application/xhtml+xml,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,hu;q=0.8',
    }
    if referer:
        h['Referer'] = referer
        h['Origin'] = '%s://%s' % (urlparse(referer).scheme, urlparse(referer).netloc)
    return h


def fetch(url, referer=None, timeout=20, json_accept=False):
    log('GET %s' % url)
    try:
        if HAVE_REQUESTS:
            resp = _SESSION.get(url, headers=_headers(referer, json_accept), timeout=timeout)
            if resp.status_code != 200:
                log('HTTP %s: %s' % (resp.status_code, url), xbmc.LOGWARNING)
            resp.encoding = resp.apparent_encoding or 'utf-8'
            return resp.text
        req = Request(url, headers=_headers(referer, json_accept))
        return urlopen(req, timeout=timeout).read().decode('utf-8', 'replace')
    except Exception as exc:  # noqa
        log('Letöltési hiba: %s (%s)' % (exc, url), xbmc.LOGERROR)
        return ''


def get_json(path):
    text = fetch(base_url() + path.lstrip('/'), referer=base_url(), json_accept=True)
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError as exc:
        log('JSON hiba (%s): %s' % (path, exc), xbmc.LOGERROR)
        return None


# ---------------------------------------------------------------------------
# Képek
# ---------------------------------------------------------------------------
def image_url(path):
    if not path:
        return None
    if path.startswith('http'):
        return path
    return urljoin(base_url(), path.lstrip('/'))


def badge_url(badge):
    if not badge:
        return None
    return urljoin(base_url(), 'api/images/badge/%s.webp' % badge)


def _match_art(match):
    poster = match.get('poster')
    if poster:
        return image_url(poster)
    teams = match.get('teams') or {}
    home = (teams.get('home') or {}).get('badge')
    if home:
        return badge_url(home)
    return None


# ---------------------------------------------------------------------------
# Listák
# ---------------------------------------------------------------------------
def list_sports():
    data = get_json('api/sports') or []
    out = []
    for s in data:
        if isinstance(s, dict) and s.get('id'):
            out.append({'id': s['id'], 'name': s.get('name') or s['id'].title()})
    log('%d sportág' % len(out))
    return out


def _norm_match(m):
    if not isinstance(m, dict) or not m.get('id'):
        return None
    return {
        'id': m['id'],
        'title': m.get('title') or m['id'],
        'category': m.get('category') or '',
        'date': m.get('date') or 0,
        'popular': bool(m.get('popular')),
        'art': _match_art(m),
        'sources': [s for s in (m.get('sources') or []) if isinstance(s, dict) and s.get('source') and s.get('id')],
    }


def list_matches(path):
    data = get_json(path) or []
    out = []
    for m in data:
        nm = _norm_match(m)
        if nm and nm['sources']:
            out.append(nm)
    log('%d meccs: %s' % (len(out), path))
    return out


def match_label(match):
    """Emberi címke: [élő]/idő + cím."""
    title = match['title']
    ts = match.get('date') or 0
    prefix = ''
    if ts:
        try:
            secs = ts / 1000.0
            now = time.time()
            if secs <= now + 60:
                prefix = '[COLOR red]● ÉLŐ[/COLOR] '
            else:
                prefix = '[%s] ' % time.strftime('%m-%d %H:%M', time.localtime(secs))
        except Exception:  # noqa
            prefix = ''
    return prefix + title


# ---------------------------------------------------------------------------
# Streamek egy meccshez
# ---------------------------------------------------------------------------
def get_streams(match):
    """Az összes forrás összes streamje egy meccshez."""
    streams = []
    for src in match['sources']:
        data = get_json('api/stream/%s/%s' % (src['source'], src['id'])) or []
        for st in data:
            if not isinstance(st, dict):
                continue
            streams.append({
                'source': st.get('source') or src['source'],
                'id': st.get('id') or src['id'],
                'streamNo': st.get('streamNo') or 1,
                'language': st.get('language') or '',
                'hd': bool(st.get('hd')),
                'embedUrl': st.get('embedUrl') or '',
            })
    log('%d stream a(z) "%s" meccshez' % (len(streams), match['title']))
    return streams


def stream_label(st):
    bits = [st['source'].title()]
    bits.append('#%s' % st['streamNo'])
    if st.get('language'):
        bits.append(st['language'])
    bits.append('HD' if st.get('hd') else 'SD')
    return ' · '.join(bits)


# ---------------------------------------------------------------------------
# Lejátszható forrás (m3u8) kinyerése az embedből
# ---------------------------------------------------------------------------
_M3U8_RE = re.compile(r'https?://[^"\'\s<>\\]+?\.m3u8[^"\'\s<>\\]*', re.IGNORECASE)
_JSHLS_RE = re.compile(
    r'(?:source|file|src|hls|url|playlist)\s*[:=]\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
    re.IGNORECASE)
_IFRAME_RE = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
_PACKED_RE = re.compile(
    r"\}\('(.*?)',\s*(\d+),\s*(\d+),\s*'(.*?)'\.split\('\|'\)", re.DOTALL)


def _unpack_packed(text):
    """Dean Edwards p,a,c,k,e,d JS kicsomagolása (függőség nélkül)."""
    out = []
    for m in _PACKED_RE.finditer(text or ''):
        try:
            payload, a, c, keywords = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4).split('|')

            def _b(n):
                first = '' if n < a else _b(int(n // a))
                r = n % a
                return first + (chr(r + 29) if r > 35 else
                                '0123456789abcdefghijklmnopqrstuvwxyz'[r])

            table = {}
            i = c
            while i:
                i -= 1
                key = _b(i)
                table[key] = keywords[i] if i < len(keywords) and keywords[i] else key
            decoded = re.sub(r'\b\w+\b', lambda mm: table.get(mm.group(0), mm.group(0)), payload)
            out.append(decoded)
        except Exception as exc:  # noqa
            log('Unpack hiba: %s' % exc, xbmc.LOGWARNING)
    return '\n'.join(out)


def _scan_m3u8(text):
    return _M3U8_RE.findall(text or '') + _JSHLS_RE.findall(text or '')


def _embed_url(st):
    if st.get('embedUrl'):
        return st['embedUrl']
    return '%sembed/%s/%s/%s' % (embed_base(), st['source'], st['id'], st['streamNo'])


def cookie_header():
    """A munkamenet sütijei 'k=v; k2=v2' formában (a lejátszóhoz)."""
    if not _SESSION:
        return ''
    try:
        return '; '.join('%s=%s' % (c.name, c.value) for c in _SESSION.cookies)
    except Exception:  # noqa
        return ''


_BAD_IFRAME = ('ad.html', '/ads', 'facebook.', 'disqus.', 'google.', 'gravatar.',
               'doubleclick', 'adexchange', 'impression')


def post(url, payload, referer=None, timeout=20):
    """JSON POST (a session-nel, hogy a sütiket is vigye/kapja)."""
    log('POST %s' % url)
    try:
        headers = _headers(referer, json_accept=True)
        headers['Content-Type'] = 'application/json'
        headers['X-Requested-With'] = 'XMLHttpRequest'
        if HAVE_REQUESTS:
            resp = _SESSION.post(url, data=json.dumps(payload), headers=headers, timeout=timeout)
            if resp.status_code not in (200, 201, 202):
                log('POST HTTP %s: %s' % (resp.status_code, url), xbmc.LOGWARNING)
            resp.encoding = resp.apparent_encoding or 'utf-8'
            return resp.text
        req = Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
        return urlopen(req, timeout=timeout).read().decode('utf-8', 'replace')
    except Exception as exc:  # noqa
        log('POST hiba: %s (%s)' % (exc, url), xbmc.LOGERROR)
        return ''


def _urls_from_fetch(resp):
    """A /fetch válaszból m3u8 URL-ek kinyerése (URL, JSON vagy nyers útvonal)."""
    resp = (resp or '').strip()
    if not resp:
        return []
    cands = list(_M3U8_RE.findall(resp))
    # JSON válasz: minden string mezőt megnézünk
    try:
        data = json.loads(resp)

        def _walk(v):
            if isinstance(v, str):
                if '.m3u8' in v or v.startswith('http') or '/' in v:
                    cands.append(v)
            elif isinstance(v, dict):
                for x in v.values():
                    _walk(x)
            elif isinstance(v, list):
                for x in v:
                    _walk(x)
        _walk(data)
    except ValueError:
        # nem JSON: idézőjelektől megtisztított nyers string
        cands.append(resp.strip().strip('"').strip("'"))

    out = []
    for u in cands:
        u = (u or '').strip().strip('"').strip("'")
        if not u:
            continue
        if u.startswith('//'):
            u = 'https:' + u
        elif not u.startswith('http') and ('.m3u8' in u or '/' in u):
            u = 'https://' + u.lstrip('/')
        if '.m3u8' in u.lower():
            out.append(u)
    return out


def resolve(st):
    """
    Visszaad: {'m3u8': [...], 'embed': <url>, 'origin': <origin>, 'cookie': <str>}.

    Elsődleges: a streamed 'POST {origin}/fetch' végpontja (source/id/streamNo),
    amely a valódi .m3u8-hoz vezet (Referer: az embed origin).
    Tartalék: az embed-oldal szkennelése (regex + packed-JS + iframe-követés).
    """
    embed = _embed_url(st)
    origin = '%s://%s' % (urlparse(embed).scheme, urlparse(embed).netloc)
    result = {'m3u8': [], 'embed': embed, 'origin': origin, 'cookie': ''}

    # Az embed-oldal betöltése (sütikért is), majd a /fetch végpont.
    html = fetch(embed, referer=base_url())
    payload = {'source': st['source'], 'id': st['id'],
               'streamNo': int(str(st.get('streamNo') or 1)) if str(st.get('streamNo') or 1).isdigit() else st.get('streamNo')}
    fetch_resp = post(origin + '/fetch', payload, referer=embed)
    if fetch_resp:
        log('/fetch válasz (részlet): %s' % fetch_resp[:300].replace('\n', ' '))
    found = _urls_from_fetch(fetch_resp)

    # Tartalék 1: közvetlen/packed az embed-oldalról
    if not found:
        found = _scan_m3u8(html) or _scan_m3u8(_unpack_packed(html))

    # Tartalék 2: egy szint iframe-követés (reklám-iframe-ek kihagyva)
    if not found:
        for frame in _IFRAME_RE.findall(html):
            furl = urljoin(embed, frame)
            if any(b in furl.lower() for b in _BAD_IFRAME):
                continue
            fhtml = fetch(furl, referer=embed)
            found = _scan_m3u8(fhtml) or _scan_m3u8(_unpack_packed(fhtml))
            if found:
                break

    result['m3u8'] = _dedup(found)
    result['cookie'] = cookie_header()
    log('resolve(%s) -> m3u8=%s origin=%s cookie=%s'
        % (embed, result['m3u8'], origin, 'igen' if result['cookie'] else 'nincs'))
    return result


def hls_headers(origin, cookie=''):
    """A HLS lekérésekhez szükséges fejlécek (Kodi ISA formátum, URL-kódolt)."""
    try:
        from urllib.parse import urlencode
    except ImportError:
        from urllib import urlencode
    headers = {
        'User-Agent': USER_AGENT,
        'Referer': origin + '/',
        'Origin': origin,
    }
    if cookie:
        headers['Cookie'] = cookie
    return urlencode(headers)


def _dedup(seq):
    seen = set()
    out = []
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out
