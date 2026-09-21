# -*- coding: utf-8 -*-
"""
MagyarAnime (magyaranime.eu) - privát, cookie-alapú kliens.

Belépés: a felhasználó a böngészőből kinyert munkamenet-sütijét
(PHPSESSID + loginkey) adja meg a beállításokban. Az addon ezzel dolgozik.

Lejátszás:
    GET  /resz/{vid}/                         -> CSRF (meta magyaranime) + data-server
    POST data/lejatszo/data_player.php        {server, vid, csrf_token}
      -> JSON: output (player HTML), servers[], hls (bool), hls_url (base64), ...
    A videó vagy közvetlen mp4 az output-ban, vagy HLS a hls_url-ből,
    vagy indavideo iframe (amit feloldunk).
"""
import base64
import json
import re

try:
    from urllib.parse import urljoin, urlparse, quote
except ImportError:
    from urlparse import urljoin, urlparse
    from urllib import quote

import xbmc
import xbmcaddon
import xbmcvfs

try:
    import requests
    HAVE_REQUESTS = True
except ImportError:
    HAVE_REQUESTS = False

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
DEFAULT_BASE = 'https://magyaranime.eu/'
# Alapértelmezett UA: modern Android Firefox (a legtöbb felhasználó innen exportál).
# A pontos, bejelentkezett böngésző UA-ját a beállításokban lehet megadni.
DEFAULT_UA = 'Mozilla/5.0 (Android 16; Mobile; rv:156.0) Gecko/156.0 Firefox/156.0'
USER_AGENT = DEFAULT_UA


def user_agent():
    return (ADDON.getSetting('user_agent') or '').strip() or DEFAULT_UA

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


def cookie_file_path():
    """A fix cookie-fájl helye (ide másolható a cookie.txt / export)."""
    prof = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
    return prof, xbmcvfs.translatePath('special://profile/addon_data/%s/cookie.txt' % ADDON_ID)


def _parse_cookie_text(text):
    """Cookie kinyerése: JSON (Cookie-Editor export), Netscape cookies.txt, vagy sima szöveg."""
    text = (text or '').strip()
    if not text:
        return {}
    # 1) JSON (Cookie-Editor "Export")
    if text[:1] in '[{':
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                data = data.get('cookies') or data.get('data') or list(data.values())
            jar = {}
            for c in data:
                if isinstance(c, dict) and c.get('name'):
                    jar[c['name']] = c.get('value', '')
            if jar:
                return jar
        except Exception:  # noqa
            pass
    # 2) Netscape cookies.txt (tab-tagolt)
    if '\t' in text:
        jar = {}
        for line in text.splitlines():
            if line.startswith('#') or not line.strip():
                continue
            p = line.split('\t')
            if len(p) >= 7 and p[5]:
                jar[p[5]] = p[6]
        if jar:
            return jar
    # 3) sima "name=value; name=value"
    jar = {}
    for part in text.replace('\n', ';').split(';'):
        if '=' in part:
            k, v = part.split('=', 1)
            jar[k.strip()] = v.strip()
    return jar


def _read_file(path):
    try:
        if path and xbmcvfs.exists(path):
            fh = xbmcvfs.File(path)
            data = fh.read()
            fh.close()
            return data
    except Exception as exc:  # noqa
        log('Cookie-fájl olvasási hiba (%s): %s' % (path, exc), xbmc.LOGWARNING)
    return ''


def _cookies():
    """
    Cookie forrás sorrend:
      1) 'cookie' beállítás (kézzel beírt string)
      2) 'cookie_file' beállítás (kiválasztott fájl: JSON export / cookies.txt)
      3) fix fájl: addon_data/<id>/cookie.txt
    """
    raw = (ADDON.getSetting('cookie') or '').strip()
    if raw:
        return _parse_cookie_text(raw)
    for path in [(ADDON.getSetting('cookie_file') or '').strip(),
                 xbmcvfs.translatePath('special://profile/addon_data/%s/cookie.txt' % ADDON_ID)]:
        data = _read_file(path)
        if data:
            jar = _parse_cookie_text(data)
            if jar:
                log('Cookie betöltve: %s (%d süti)' % (path, len(jar)))
                return jar
    return {}


def cookie_status():
    """Diagnosztika: (forrás_leírás, [sütinevek]). Nem ad vissza értékeket."""
    raw = (ADDON.getSetting('cookie') or '').strip()
    if raw:
        return 'szöveg-mező', list(_parse_cookie_text(raw).keys())
    cf = (ADDON.getSetting('cookie_file') or '').strip()
    data = _read_file(cf)
    if data:
        return 'fájl: %s' % cf, list(_parse_cookie_text(data).keys())
    fixed = xbmcvfs.translatePath('special://profile/addon_data/%s/cookie.txt' % ADDON_ID)
    data = _read_file(fixed)
    if data:
        return 'fix fájl (cookie.txt)', list(_parse_cookie_text(data).keys())
    return 'nincs', []


def check_login():
    """Betölti a főoldalt a jelenlegi sütivel. Visszaad: (bejelentkezve?, hossz)."""
    html = get('', referer=base_url())
    return logged_in(html), len(html or '')


def _headers(referer=None, ajax=False):
    h = {'User-Agent': user_agent(),
         'Accept-Language': 'hu-HU,hu;q=0.9,en;q=0.5'}
    if ajax:
        h['X-Requested-With'] = 'XMLHttpRequest'
        h['Accept'] = 'application/json, text/javascript, */*; q=0.01'
    if referer:
        h['Referer'] = referer
    return h


def get(url, referer=None, timeout=25):
    url = urljoin(base_url(), url)
    log('GET %s' % url)
    try:
        r = _SESSION.get(url, headers=_headers(referer), cookies=_cookies(), timeout=timeout)
        r.encoding = r.apparent_encoding or 'utf-8'
        return r.text
    except Exception as exc:  # noqa
        log('GET hiba: %s (%s)' % (exc, url), xbmc.LOGERROR)
        return ''


def post(url, data, referer=None, timeout=30):
    url = urljoin(base_url(), url)
    log('POST %s data=%s' % (url, data))
    try:
        r = _SESSION.post(url, data=data, headers=_headers(referer, ajax=True),
                          cookies=_cookies(), timeout=timeout)
        r.encoding = r.apparent_encoding or 'utf-8'
        return r.text
    except Exception as exc:  # noqa
        log('POST hiba: %s (%s)' % (exc, url), xbmc.LOGERROR)
        return ''


def logged_in(html):
    """Bejelentkezettség ellenőrzése egy oldal HTML-je alapján."""
    if not html:
        return False
    low = html.lower()
    # pozitív jel: kijelentkezés/logout link jelenléte
    if 'kijelentkezes' in low or 'logout' in low or 'felhasznalo/adatok' in low:
        return True
    return False


# ---------------------------------------------------------------------------
# Keresés / böngészés
# ---------------------------------------------------------------------------
_LEIRAS_RE = re.compile(r'href="[^"]*?/?leiras/(\d+)/?"', re.IGNORECASE)
_RESZ_RE = re.compile(r'href="[^"]*?/?resz/(\d+)/?"', re.IGNORECASE)
_META_CSRF_RE = re.compile(r'<meta\s+name="magyaranime"\s+content="([^"]+)"', re.IGNORECASE)


def _clean(t):
    t = re.sub(r'<[^>]+>', ' ', t or '')
    for a, b in (('&amp;', '&'), ('&#039;', "'"), ('&quot;', '"'), ('&nbsp;', ' ')):
        t = t.replace(a, b)
    return re.sub(r'\s+', ' ', t).strip()


def search_raw(term):
    """A keresés nyers HTML-je (hibakereséshez)."""
    return post('web/kereso/', {'search_text': term}, referer=base_url() + 'web/kereso/') or ''


def dump_debug(term):
    """Kereső-oldal + a találatokat betöltő JS fájlok mentése (hibakereséshez)."""
    ref = base_url() + 'web/kereso/'
    parts = ['===== POST web/kereso (shell) =====\n' + (search_raw(term) or '(ures)')]
    for u in ('data/search/search.js', 'js/kereso/kereso_v2.js',
              'js/magyaranime_simple.js'):
        parts.append('\n\n===== %s =====\n%s' % (u, get(u, referer=ref) or '(ures/hiba)'))
    return '\n'.join(parts)


def search(term):
    """Keresés címre. Visszaad: [{aid, title, art}]."""
    html = post('web/kereso/', {'search_text': term}, referer=base_url() + 'web/kereso/')
    if not html:
        return []
    results = []
    seen = set()
    # anime-adatlap linkek + a link szövege
    for m in re.finditer(r'<a[^>]+href="[^"]*?/?leiras/(\d+)/?"[^>]*>(.*?)</a>', html,
                         re.DOTALL | re.IGNORECASE):
        aid = m.group(1)
        if aid in seen:
            continue
        title = _clean(m.group(2))
        # kép a link belsejéből
        img = re.search(r'src="([^"]+)"', m.group(2))
        art = urljoin(base_url(), img.group(1)) if img else None
        if title:
            seen.add(aid)
            results.append({'aid': aid, 'title': title, 'art': art})
    log('%d keresési találat: "%s"' % (len(results), term))
    return results


_EP_TITLE_RE = re.compile(r'<a href="resz/(\d+)/"\s+oncontextmenu="return false;">([^<]+)</a>',
                          re.IGNORECASE)
_EP_THUMB_RE = re.compile(r"window\.location='resz/(\d+)/';\"[^>]*>\s*<img[^>]*data-src=\"([^\"]+)\"",
                          re.IGNORECASE)


def episodes_of_anime(aid):
    """Egy anime részei közvetlenül az adatlapról (/leiras/{aid}/): cím + bélyegkép."""
    html = get('leiras/%s/' % aid, referer=base_url())
    if not html:
        return {'title': '', 'episodes': []}
    tm = re.search(r'<h2 class="gen-title[^"]*">([^<]+)</h2>', html)
    title = _clean(tm.group(1)) if tm else ''
    thumbs = {v: urljoin(base_url(), t) for v, t in _EP_THUMB_RE.findall(html)}
    eps = []
    seen = set()
    for v, etitle in _EP_TITLE_RE.findall(html):
        if v in seen:
            continue
        seen.add(v)
        eps.append({'vid': v, 'title': _clean(etitle), 'server': 's1', 'thumb': thumbs.get(v)})
    if not eps:
        m = _RESZ_RE.search(html)
        if m:
            return episodes_of_resz(m.group(1))
    log('%d rész (adatlap): leiras/%s ("%s")' % (len(eps), aid, title))
    return {'title': title, 'episodes': eps}


def episodes_of_resz(vid):
    """A /resz/{vid}/ oldal epizódlistája + anime cím."""
    html = get('resz/%s/' % vid, referer=base_url())
    if not html:
        return {'title': '', 'episodes': [], 'html': ''}
    title = ''
    tm = re.search(r'<div id="InfoBox".*?<h2>.*?leiras/\d+/">.*?</i>\s*([^<]+)</a>', html, re.DOTALL)
    if tm:
        title = _clean(tm.group(1))
    episodes = []
    seen = set()
    for block in re.findall(r'<li[^>]*class="[^"]*videoChange[^"]*"[^>]*>.*?</li>', html, re.DOTALL):
        vm = re.search(r'data-vid="(\d+)"', block)
        if not vm:
            continue
        evid = vm.group(1)
        if evid in seen:
            continue
        seen.add(evid)
        sm = re.search(r'data-server="([^"]*)"', block)
        tm2 = re.search(r'episode-title">([^<]+)<', block)
        episodes.append({'vid': evid,
                         'server': (sm.group(1) if sm else 's1'),
                         'title': _clean(tm2.group(1)) if tm2 else ('rész %s' % evid)})
    log('%d rész: resz/%s ("%s")' % (len(episodes), vid, title))
    return {'title': title, 'episodes': episodes, 'html': html}


# ---------------------------------------------------------------------------
# Lejátszás
# ---------------------------------------------------------------------------
_MP4_RE = re.compile(r'https?:\\?/\\?/[^"\'\s<>]+?\.mp4[^"\'\s<>]*', re.IGNORECASE)
_SRC_RE = re.compile(r'<source[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
_IFRAME_RE = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)


def _unescape_url(u):
    return (u or '').replace('\\/', '/').replace('&amp;', '&')


def player_data(server, vid, csrf, referer):
    txt = post('data/lejatszo/data_player.php',
               {'server': server, 'vid': vid, 'csrf_token': csrf}, referer=referer)
    if not txt:
        return None
    try:
        return json.loads(txt)
    except ValueError:
        log('data_player.php nem JSON (részlet): %s' % txt[:300], xbmc.LOGWARNING)
        return None


def _extract_from_output(output):
    """A player HTML-jéből lejátszható forrás(ok) kinyerése."""
    urls = []
    for m in _SRC_RE.finditer(output):
        urls.append(_unescape_url(m.group(1)))
    for m in _MP4_RE.finditer(output):
        urls.append(_unescape_url(m.group(0)))
    iframes = [_unescape_url(u) for u in _IFRAME_RE.findall(output)]
    return _dedup(urls), iframes


def resolve(vid, prefer_server=None):
    """
    Visszaad: {'url':..., 'hls':bool, 'headers':str, 'servers':[...], 'embed':...}.
    A megadott résznél végigmegy a szervereken, míg lejátszható forrást talál.
    """
    result = {'url': None, 'hls': False, 'headers': '', 'servers': [], 'embed': None}
    page = get('resz/%s/' % vid, referer=base_url())
    if not page:
        return result
    csrf_m = _META_CSRF_RE.search(page)
    csrf = csrf_m.group(1) if csrf_m else ''
    dv = re.search(r'id="VideoPlayer"[^>]*data-server="([^"]*)"', page)
    default_server = dv.group(1) if dv else 's1'

    referer = base_url() + 'resz/%s/' % vid
    tried = []
    order = [prefer_server] if prefer_server else []
    order += [default_server, 's1', 's2', 's3', 's4', 's5']

    for server in order:
        if not server or server in tried:
            continue
        tried.append(server)
        data = player_data(server, vid, csrf, referer)
        if not data:
            continue
        if data.get('servers'):
            result['servers'] = data['servers']
        if data.get('error'):
            log('data_player error (%s): %s' % (server, data.get('error')), xbmc.LOGWARNING)
            continue
        # 1) HLS
        if data.get('hls') and data.get('hls_url'):
            try:
                hls = base64.b64decode(data['hls_url']).decode('utf-8', 'replace')
            except Exception:  # noqa
                hls = ''
            if hls:
                result.update({'url': hls, 'hls': True,
                               'headers': _hls_headers(referer)})
                log('resolve(%s) HLS: %s' % (vid, hls))
                return result
        # 2) output-ból mp4 / iframe
        output = data.get('output') or ''
        urls, iframes = _extract_from_output(output)
        mp4 = [u for u in urls if '.mp4' in u.lower()]
        if mp4:
            result.update({'url': mp4[0], 'headers': _hls_headers(referer)})
            log('resolve(%s) MP4: %s' % (vid, mp4[0]))
            return result
        # 3) indavideo / videa / egyéb beágyazott lejátszó
        for fr in iframes:
            result['embed'] = fr
            low = fr.lower()
            media = None
            if 'indavideo' in low:
                media = indavideo_resolve(fr)      # saját, gyors út (nincs függőség)
            if not media:
                media = resolve_via_module(fr)     # ResolveURL/URLResolver, ha telepítve
            if media:
                hls = '.m3u8' in media.lower()
                result.update({'url': media, 'hls': hls, 'headers': _hls_headers(referer)})
                log('resolve(%s) beágyazott feloldva: %s' % (vid, media))
                return result
        # bármilyen m3u8 az output-ban
        m3 = re.search(r'https?://[^"\'\s]+?\.m3u8[^"\'\s]*', output)
        if m3:
            result.update({'url': m3.group(0), 'hls': True, 'headers': _hls_headers(referer)})
            return result

    log('resolve(%s): nem sikerült forrást kinyerni. Szerverek: %s'
        % (vid, [s.get('server') for s in result['servers']]), xbmc.LOGWARNING)
    return result


def _hls_headers(referer):
    return '&'.join(['User-Agent=%s' % quote(user_agent(), ''),
                     'Referer=%s' % quote(referer, ''),
                     'Origin=%s' % quote(base_url().rstrip('/'), '')])


def has_resolver():
    """Van-e telepített ResolveURL/URLResolver modul? Visszaadja a nevét vagy ''-t."""
    try:
        import resolveurl  # noqa
        return 'ResolveURL'
    except ImportError:
        pass
    try:
        import urlresolver  # noqa
        return 'URLResolver'
    except ImportError:
        return ''


def resolve_via_module(url):
    """Beágyazott lejátszó (indavideo/videa/stb.) feloldása a telepített modullal."""
    mod = None
    try:
        import resolveurl as mod
    except ImportError:
        try:
            import urlresolver as mod
        except ImportError:
            log('Nincs ResolveURL/URLResolver – nem feloldható: %s' % url, xbmc.LOGWARNING)
            return None
    try:
        hmf = mod.HostedMediaFile(url)
        if hmf and hmf.valid_url():
            u = hmf.resolve()
            if u:
                return u
        log('ResolveURL nem tudta feloldani: %s' % url, xbmc.LOGWARNING)
    except Exception as exc:  # noqa
        log('ResolveURL hiba (%s): %s' % (url, exc), xbmc.LOGWARNING)
    return None


# ---------------------------------------------------------------------------
# indavideo feloldó (nyilvános amfphp API)
# ---------------------------------------------------------------------------
def indavideo_resolve(embed_url):
    """indavideo embedből közvetlen mp4 (a legjobb minőség)."""
    try:
        m = re.search(r'/(?:player/video|video)/([0-9a-zA-Z-]+)', embed_url)
        vid = m.group(1) if m else embed_url.rstrip('/').split('/')[-1]
        api = 'https://amfphp.indavideo.hu/SYm0json.php/player.getVideoData/%s' % vid
        txt = get(api, referer=embed_url)
        data = json.loads(txt)
        d = data.get('data') or data
        files = d.get('video_files') or []
        if isinstance(files, dict):
            files = list(files.values())
        tokens = d.get('filesh') or {}
        if not files:
            log('indavideo: nincs video_files (válasz eleje: %s)' % (txt or '')[:400],
                xbmc.LOGWARNING)
        best = None
        best_h = -1
        for f in files:
            hm = re.search(r'\.(\d{3,4})\.mp4', f)
            h = int(hm.group(1)) if hm else 0
            url = f
            if tokens:
                q = str(h)
                tok = tokens.get(q) or (list(tokens.values())[0] if tokens else None)
                if tok:
                    url = f + ('&' if '?' in f else '?') + 'token=' + tok
            if h >= best_h:
                best_h = h
                best = url
        return best
    except Exception as exc:  # noqa
        log('indavideo feloldás hiba: %s' % exc, xbmc.LOGWARNING)
        return None


def _dedup(seq):
    seen = set()
    out = []
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out
