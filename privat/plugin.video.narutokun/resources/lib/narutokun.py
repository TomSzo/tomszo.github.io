# -*- coding: utf-8 -*-
"""
Naruto-Kun.Hu (naruto-kun.hu) - privát kliens a csapat online animéihez.

Az oldal PHP-Fusion, iso-8859-2 kódolású. Belépés (a nem nyilvános oldalakhoz):
    POST news.php  user_name, user_pass, remember_me=y, login=Bejelentkezés
    -> PHP-Fusion sütik, lemezre mentve. Ha egy oldal a belépő űrlapot
    (loginpageform) adja vissza, egyszer belépünk és újratöltjük.

    Lista:    infusions/nkwt_adatlap/adatlap.php?page=anime&sortby=aktualis[&rowstart=12]
              <a class="album-preview" href="...page=anime&id=71"> <img src=...>
              <p class="album-preview-title">Akame ga Kill!</p>
    Keresés:  adatlap.php?page=anime&search=<szó>
    Adatlap:  adatlap.php?page=anime&id=71  (ismertető, epizódcímek "1. rész: ...")
    Részek:   _videos.php?cat=71&page=N     (az adatlap AJAX-szal tölti; watch linkek)
    Rész:     adatlap.php?page=watch&id=1380
              <iframe src="//videa.hu/player?v=..."> + <p class="stream-box-title">
    Friss:    index.php hírei ("Online megtekintés" -> page=watch&id=...)

A videót a beágyazott lejátszó (videa, indavideo, ...) adja; ezt a ResolveURL
oldja fel. Visszafogottság: 1 mp szünet a kérések között, oldal-gyorsítótár,
helyi napi számláló (mint a Muteki/Kintsugi addonoknál).
"""
import json
import os
import re

try:
    from html import unescape as _html_unescape
except ImportError:  # py2
    from HTMLParser import HTMLParser
    _html_unescape = HTMLParser().unescape

try:
    from urllib.parse import urljoin, quote
except ImportError:
    from urlparse import urljoin
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
BASE = 'https://naruto-kun.hu/'
ADATLAP = 'infusions/nkwt_adatlap/adatlap.php'
ENCODING = 'iso-8859-2'
# Mindig ez a User-Agent (a tulajdonos Firefox for Android böngészője) - nem állítható.
DEFAULT_UA = 'Mozilla/5.0 (Android 16; Mobile; rv:156.0) Gecko/156.0 Firefox/156.0'

_SESSION = requests.Session() if HAVE_REQUESTS else None

# Visszafogottság
_MIN_GAP = 1.0
_LAST_REQ = [0.0]
_MAX_VIDEO_PAGES = 30


def log(msg, level=xbmc.LOGINFO):
    xbmc.log('[%s] %s' % (ADDON_ID, msg), level)


def user_agent():
    return DEFAULT_UA


def base_url():
    return BASE


def _profile_dir():
    prof = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
    try:
        if not xbmcvfs.exists(prof):
            xbmcvfs.mkdirs(prof)
    except Exception:  # noqa
        pass
    return prof


def _cache_minutes():
    try:
        return max(0, int(ADDON.getSetting('cache_minutes') or 30))
    except Exception:  # noqa
        return 30


# ---------------------------------------------------------------------------
# HTTP: szünet + számláló + gyorsítótár
# ---------------------------------------------------------------------------
def _throttle():
    import time
    gap = time.time() - _LAST_REQ[0]
    if gap < _MIN_GAP:
        xbmc.sleep(int((_MIN_GAP - gap) * 1000))
    _LAST_REQ[0] = time.time()


def _counter_path():
    return os.path.join(_profile_dir(), 'requests.json')


def today_requests():
    import datetime
    try:
        f = xbmcvfs.File(_counter_path())
        try:
            d = json.loads(f.read() or '{}')
        finally:
            f.close()
    except Exception:  # noqa
        d = {}
    return int(d.get('count', 0)) if d.get('date') == datetime.date.today().isoformat() else 0


def _bump_request():
    import datetime
    n = today_requests() + 1
    try:
        f = xbmcvfs.File(_counter_path(), 'w')
        try:
            f.write(json.dumps({'date': datetime.date.today().isoformat(), 'count': n}))
        finally:
            f.close()
    except Exception:  # noqa
        pass


def _headers(referer=None):
    h = {'User-Agent': user_agent(),
         'Accept-Language': 'hu-HU,hu;q=0.9,en;q=0.5',
         'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
    if referer:
        h['Referer'] = referer
    return h


# ---------------------------------------------------------------------------
# Munkamenet (sütik) + belépés
# ---------------------------------------------------------------------------
_LOGIN_COOLDOWN = 10 * 60
_COOKIES_LOADED = [False]
_LOGIN_TRIED = [False]


def _session_path():
    return os.path.join(_profile_dir(), 'session.json')


def save_cookies():
    if not _SESSION:
        return
    try:
        data = [{'name': c.name, 'value': c.value, 'domain': c.domain, 'path': c.path}
                for c in _SESSION.cookies]
        f = xbmcvfs.File(_session_path(), 'w')
        try:
            f.write(json.dumps(data))
        finally:
            f.close()
    except Exception as exc:  # noqa
        log('cookie mentés hiba: %s' % exc, xbmc.LOGWARNING)


def load_cookies():
    if _COOKIES_LOADED[0] or not _SESSION:
        return
    _COOKIES_LOADED[0] = True
    try:
        p = _session_path()
        if not xbmcvfs.exists(p):
            return
        f = xbmcvfs.File(p)
        try:
            raw = f.read()
        finally:
            f.close()
        for c in json.loads(raw or '[]'):
            try:
                _SESSION.cookies.set(c['name'], c['value'], domain=c.get('domain') or
                                     'naruto-kun.hu', path=c.get('path') or '/')
            except Exception:  # noqa
                pass
    except Exception as exc:  # noqa
        log('cookie betöltés hiba: %s' % exc, xbmc.LOGWARNING)


def clear_cookies():
    _set_login_failed(False)
    if _SESSION:
        _SESSION.cookies.clear()
    _COOKIES_LOADED[0] = False
    _LOGIN_TRIED[0] = False
    try:
        if xbmcvfs.exists(_session_path()):
            xbmcvfs.delete(_session_path())
    except Exception:  # noqa
        pass


def _login_block_path():
    return os.path.join(_profile_dir(), 'login_failed.txt')


def _login_blocked():
    import time
    try:
        p = _login_block_path()
        if xbmcvfs.exists(p):
            return (time.time() - xbmcvfs.Stat(p).st_mtime()) < _LOGIN_COOLDOWN
    except Exception:  # noqa
        pass
    return False


def _set_login_failed(failed):
    p = _login_block_path()
    try:
        if failed:
            f = xbmcvfs.File(p, 'w')
            try:
                f.write('1')
            finally:
                f.close()
        elif xbmcvfs.exists(p):
            xbmcvfs.delete(p)
    except Exception:  # noqa
        pass


def is_login_page(html):
    return bool(html) and ("name='loginpageform'" in html or 'name="loginpageform"' in html)


def logged_in(html):
    return bool(html) and 'logout=yes' in html


def _read_file(path):
    try:
        if path and xbmcvfs.exists(path):
            fh = xbmcvfs.File(path)
            try:
                return fh.read()
            finally:
                fh.close()
    except Exception as exc:  # noqa
        log('fájl olvasási hiba (%s): %s' % (path, exc), xbmc.LOGWARNING)
    return ''


_CRED_KEY_RE = re.compile(
    r'\s*(email|username|user|felhasznalonev|felhasznalo|password|jelszo|pass|pw)\s*[:=]\s*(.+?)\s*$',
    re.IGNORECASE)


def _parse_creds(text):
    """Rugalmas felhasználónév/jelszó kinyerés txt-ből. Visszaad: (email, jelszó) vagy ('','')."""
    text = (text or '').strip()
    if not text:
        return '', ''
    # 1) JSON: {"email":..,"password":..} vagy {"username":..}
    if text[:1] in '{[':
        try:
            d = json.loads(text)
            if isinstance(d, list) and d:
                d = d[0]
            if isinstance(d, dict):
                e = d.get('email') or d.get('username') or d.get('user') or ''
                p = d.get('password') or d.get('pass') or d.get('pw') or ''
                if e and p:
                    return str(e).strip(), str(p)
        except Exception:  # noqa
            pass
    lines = [l for l in re.split(r'[\r\n]+', text) if l.strip()]
    # 2) kulcs=érték sorok (email=.., password=..)
    kv = {}
    for line in lines:
        m = _CRED_KEY_RE.match(line)
        if m:
            kv[m.group(1).lower()] = m.group(2)
    if kv:
        e = (kv.get('email') or kv.get('username') or kv.get('user')
             or kv.get('felhasznalonev') or kv.get('felhasznalo') or '')
        p = (kv.get('password') or kv.get('jelszo') or kv.get('pass') or kv.get('pw') or '')
        if e and p:
            return e.strip(), p
    # 3) egyetlen sor "email<elválasztó>jelszó"
    if len(lines) == 1:
        for sep in (':', '|', ';', ',', '\t'):
            if sep in lines[0]:
                a, _, b = lines[0].partition(sep)
                if a.strip() and b.strip():
                    return a.strip(), b.strip()
    # 4) két sor: első = email, második = jelszó
    if len(lines) >= 2:
        return lines[0].strip(), lines[1].strip()
    return '', ''


def _cred_fixed_path():
    return xbmcvfs.translatePath('special://profile/addon_data/%s/login.txt' % ADDON_ID)


def _credentials():
    """(email, jelszó) - előbb a beállítás-mezők, aztán a megadott txt, végül a fix login.txt."""
    email = (ADDON.getSetting('email') or '').strip()
    pw = (ADDON.getSetting('password') or '')
    if email and pw:
        return email, pw
    for path in [(ADDON.getSetting('cred_file') or '').strip(), _cred_fixed_path()]:
        data = _read_file(path)
        if data:
            e, p = _parse_creds(data)
            if e and p:
                return e, p
    return email, pw


def have_credentials():
    e, p = _credentials()
    return bool(e and p)


def cred_source():
    """Diagnosztika: honnan jön a belépés ('beállítás' / 'fájl: ...' / 'nincs')."""
    if (ADDON.getSetting('email') or '').strip() and (ADDON.getSetting('password') or ''):
        return 'beállítás-mezők'
    cf = (ADDON.getSetting('cred_file') or '').strip()
    if cf and _parse_creds(_read_file(cf))[0]:
        return 'fájl: %s' % cf
    if _parse_creds(_read_file(_cred_fixed_path()))[0]:
        return 'fix fájl (login.txt)'
    return 'nincs'


def login():
    """PHP-Fusion belépés. Visszaad: sikeres?"""
    if not _SESSION:
        return False
    user, pw = _credentials()
    if not user or not pw:
        log('Nincs felhasználónév/jelszó (sem beállítás, sem txt).', xbmc.LOGWARNING)
        return False
    if _login_blocked():
        log('Az előző belépés 10 percen belül sikertelen volt - most nem próbálkozunk.',
            xbmc.LOGWARNING)
        return False
    data = {'user_name': user.encode(ENCODING, 'replace'),
            'user_pass': pw.encode(ENCODING, 'replace'),
            'remember_me': 'y', 'login': u'Bejelentkezés'.encode(ENCODING)}
    _throttle()
    _bump_request()
    try:
        r = _SESSION.post(urljoin(BASE, 'news.php'), data=data, timeout=30,
                          headers=dict(_headers(urljoin(BASE, 'login.php')),
                                       Origin=BASE.rstrip('/')))
        html = r.content.decode(ENCODING, 'replace')
    except Exception as exc:  # noqa
        log('login hiba: %s' % exc, xbmc.LOGERROR)
        return False
    ok = logged_in(html) and not is_login_page(html)
    _set_login_failed(not ok)
    if ok:
        save_cookies()
        log('Bejelentkezés sikeres.')
    else:
        log('Bejelentkezés SIKERTELEN (felhasználónév/jelszó?).', xbmc.LOGWARNING)
    return ok


def _raw_get(url, referer, timeout):
    _throttle()
    _bump_request()
    r = _SESSION.get(url, headers=_headers(referer or BASE), timeout=timeout)
    return r.content.decode(ENCODING, 'replace')


def get(path, referer=None, timeout=25):
    """GET a naruto-kun.hu-ról (iso-8859-2 -> unicode). Ha a belépő űrlap jön vissza,
    egyszer belép (ha van felhasználónév/jelszó) és újratölti."""
    if not _SESSION:
        log('Nincs requests modul!', xbmc.LOGERROR)
        return ''
    load_cookies()
    url = urljoin(BASE, path)
    log('GET %s' % url)
    try:
        html = _raw_get(url, referer, timeout)
    except Exception as exc:  # noqa
        log('GET hiba: %s (%s)' % (exc, url), xbmc.LOGERROR)
        return ''
    if is_login_page(html) and not _LOGIN_TRIED[0] and have_credentials():
        _LOGIN_TRIED[0] = True
        log('Belépés szükséges: %s' % url)
        if login():
            try:
                html = _raw_get(url, referer, timeout)
            except Exception as exc:  # noqa
                log('GET (újra) hiba: %s' % exc, xbmc.LOGERROR)
    elif not is_login_page(html):
        save_cookies()
    return html


def check_login():
    """Diagnosztika: (bejelentkezve?, felhasználónév)."""
    html = get('news.php')
    m = re.search(r'<p class="navigation-widget-info-title">([^<]+)</p>', html or '')
    return logged_in(html), (_txt(m.group(1)) if m else '')


def _page_cache_path(path):
    import hashlib
    d = os.path.join(_profile_dir(), 'cache')
    try:
        if not xbmcvfs.exists(d + os.sep):
            xbmcvfs.mkdirs(d)
    except Exception:  # noqa
        pass
    return os.path.join(d, hashlib.md5(path.encode('utf-8')).hexdigest() + '.html')


def cached_get(path, ttl, referer=None, valid=None):
    """GET gyorsítótárral (ttl mp). valid(html) -> csak érvényes oldalt tárolunk."""
    import time
    p = _page_cache_path(path)
    if ttl > 0:
        try:
            if xbmcvfs.exists(p) and (time.time() - xbmcvfs.Stat(p).st_mtime()) < ttl:
                f = xbmcvfs.File(p)
                try:
                    html = f.read()
                finally:
                    f.close()
                if html and (valid is None or valid(html)):
                    return html
        except Exception:  # noqa
            pass
    html = get(path, referer=referer)
    if html and (valid is None or valid(html)):
        try:
            f = xbmcvfs.File(p, 'w')
            try:
                f.write(html)
            finally:
                f.close()
        except Exception:  # noqa
            pass
    return html


def clear_page_cache():
    import shutil
    shutil.rmtree(os.path.join(_profile_dir(), 'cache'), ignore_errors=True)


# ---------------------------------------------------------------------------
# Szöveg-segédek
# ---------------------------------------------------------------------------
def _txt(t):
    t = re.sub(r'<[^>]+>', ' ', t or '')
    return re.sub(r'\s+', ' ', _html_unescape(t)).strip()


def _abs(u):
    if not u:
        return None
    u = _html_unescape(u.strip())
    if u.startswith('//'):
        return 'https:' + u
    # az oldal relatív linkjei az infusions/nkwt_adatlap/ mappából indulnak
    return u if u.startswith('http') else urljoin(BASE + ADATLAP, u)


def _is_page(html):
    """Érvényes (tárolható) oldal: az oldal saját tartalma, és nem a belépő űrlap."""
    return bool(html) and 'nkwt' in html.lower() and not is_login_page(html)


# ---------------------------------------------------------------------------
# Listák (adatlapok)
# ---------------------------------------------------------------------------
STATUSES = (('aktualis', 'Aktuális projektek'), ('befejezett', 'Befejezett projektek'),
            ('felfuggesztett', 'Felfüggesztett projektek'), ('archivum', 'Archívum'),
            ('tervezett', 'Tervezett projektek'), ('', 'Összes anime (A→Z)'))
PAGE_SIZE = 12

_CARD_RE = re.compile(r'<a class="album-preview" href="([^"]*page=anime&(?:amp;)?id=(\d+))"'
                      r'(.*?)</a>', re.DOTALL)


def parse_list(html):
    """Adatlap-kártyák: [{'id','title','alt','art','type','status'}] + következő rowstart."""
    items, seen = [], set()
    for m in _CARD_RE.finditer(html or ''):
        aid, body = m.group(2), m.group(3)
        if aid in seen:
            continue
        seen.add(aid)
        tm = re.search(r'<p class="album-preview-title">(.*?)</p>', body, re.DOTALL)
        am = re.search(r'<p class="album-preview-text">(.*?)</p>', body, re.DOTALL)
        im = re.search(r'<img src="([^"]+)"', body)
        stickers = [_txt(s) for s in
                    re.findall(r'<p class="text-sticker small negative"[^>]*>([^<]+)</p>', body)]
        items.append({'id': aid, 'title': _txt(tm.group(1)) if tm else 'anime %s' % aid,
                      'alt': _txt(am.group(1)) if am else '',
                      'art': _abs(im.group(1)) if im else None,
                      'type': stickers[0] if stickers else '',
                      'status': stickers[1] if len(stickers) > 1 else ''})
    return items


def next_rowstart(html, rowstart):
    starts = [int(x) for x in re.findall(r'rowstart=(\d+)', html or '')]
    later = [s for s in starts if s > rowstart]
    return min(later) if later else None


def anime_list(sortby='aktualis', rowstart=0):
    path = '%s?page=anime' % ADATLAP
    if sortby:
        path += '&sortby=%s' % sortby
    if rowstart:
        path += '&rowstart=%d' % rowstart
    html = cached_get(path, _cache_minutes() * 60, valid=_is_page)
    return parse_list(html), next_rowstart(html, rowstart)


def search(term):
    path = '%s?page=anime&search=%s' % (ADATLAP, quote(term.encode(ENCODING, 'replace')))
    html = get(path)
    return parse_list(html)


# ---------------------------------------------------------------------------
# Adatlap + részek
# ---------------------------------------------------------------------------
def parse_info(html):
    """Adatlap: {'title','alt','plot','art','ep_titles':{szám: cím},'status','episodes'}."""
    h = html or ''
    tm = re.search(r'<h2 class="section-title">\s*(.*?)\s*</h2>', h, re.DOTALL)
    am = re.search(r'<p class="section-pretitle">(.*?)</p>', h, re.DOTALL)
    im = re.search(r'<p class="price-title big">\s*<img src="([^"]+)"', h)
    pm = re.search(r'Ismertet[^<]*</p>.*?<p class="tab-box-item-paragraph">(.*?)</p>', h, re.DOTALL)
    sm = re.search(r'Projekt st[^<]*</p>.*?<span class="bold">(.*?)</span>', h, re.DOTALL)
    em = re.search(r'Publik[^<]*</p>.*?<span class="bold">(.*?)</span>', h, re.DOTALL)
    eps = {}
    for num, title in re.findall(
            r"<p class='bullet-item-text'><strong>\s*(\d+)\.\s*r[^:<]*:\s*</strong>\s*(.*?)\s*</p>",
            h, re.DOTALL):
        eps[int(num)] = _txt(title)
    return {'title': _txt(tm.group(1)) if tm else '', 'alt': _txt(am.group(1)) if am else '',
            'plot': _txt(pm.group(1)) if pm else '', 'art': _abs(im.group(1)) if im else None,
            'status': _txt(sm.group(1)) if sm else '', 'episodes': _txt(em.group(1)) if em else '',
            'ep_titles': eps}


_WATCH_RE = re.compile(r'page=watch&(?:amp;)?id=(\d+)')


def parse_videos(html):
    """Watch-linkek címmel és képpel: [{'id','title','thumb'}] (oldal-sorrendben)."""
    out, seen = [], set()
    h = html or ''
    for m in re.finditer(r'<a[^>]+href="[^"]*page=watch&(?:amp;)?id=(\d+)"[^>]*>(.*?)</a>',
                         h, re.DOTALL):
        vid, body = m.group(1), m.group(2)
        if vid in seen:
            continue
        seen.add(vid)
        tm = (re.search(r'class="video-box-title">(.*?)</p>', body, re.DOTALL)
              or re.search(r'<p[^>]*title[^>]*>(.*?)</p>', body, re.DOTALL))
        im = re.search(r'<img src="([^"]+)"', body)
        title = _txt(tm.group(1)) if tm else _txt(body)
        out.append({'id': vid, 'title': title or 'rész %s' % vid,
                    'thumb': _abs(im.group(1)) if im else None})
    for vid in _WATCH_RE.findall(h):        # tartalék: cím nélküli linkek
        if vid not in seen:
            seen.add(vid)
            out.append({'id': vid, 'title': 'rész %s' % vid, 'thumb': None})
    return out


def _epnum(title):
    m = re.search(r'(\d+)\.?\s*$', title or '')
    return int(m.group(1)) if m else None


def anime_episodes(aid):
    """Egy anime adatlapja + az összes online része (a _videos.php lapjairól).
    Az összerakott eredményt is gyorsítótárazzuk, így újranyitáskor 0 kérés."""
    import time
    ttl = _cache_minutes() * 60
    jp = os.path.join(_profile_dir(), 'cache', 'anime_%s.json' % aid)
    if ttl > 0:
        try:
            if xbmcvfs.exists(jp) and (time.time() - xbmcvfs.Stat(jp).st_mtime()) < ttl:
                f = xbmcvfs.File(jp)
                try:
                    data = json.loads(f.read() or '{}')
                finally:
                    f.close()
                if data.get('videos') is not None:
                    data['ep_titles'] = {int(k): v for k, v in data.get('ep_titles', {}).items()}
                    return data
        except Exception:  # noqa
            pass
    info = parse_info(cached_get('%s?page=anime&id=%s' % (ADATLAP, aid), ttl, valid=_is_page))
    eps, seen = [], set()
    for page in range(1, _MAX_VIDEO_PAGES + 1):
        html = cached_get('infusions/nkwt_adatlap/_videos.php?cat=%s&page=%d' % (aid, page), ttl,
                          referer=BASE + '%s?page=anime&id=%s' % (ADATLAP, aid),
                          valid=lambda h: not is_login_page(h))
        new = [v for v in parse_videos(html) if v['id'] not in seen]
        if not new:
            break
        for v in new:
            seen.add(v['id'])
            n = _epnum(v['title'])
            if n is not None and info['ep_titles'].get(n):
                v['title'] = '%s – %s' % (v['title'], info['ep_titles'][n])
            eps.append(v)
    log('anime %s: %d online rész' % (aid, len(eps)))
    info['videos'] = eps
    if info.get('title'):
        try:
            _page_cache_path('x')          # a cache mappa létrehozása
            f = xbmcvfs.File(jp, 'w')
            try:
                f.write(json.dumps(info))
            finally:
                f.close()
        except Exception:  # noqa
            pass
    return info


def latest():
    """A főoldal hírei közül az online részek: [{'id','title','thumb'}]."""
    html = cached_get('news.php', min(_cache_minutes(), 10) * 60, valid=_is_page)
    out, seen = [], set()
    blocks = re.split(r"<a name='news_\d+' id='news_\d+'></a>", html or '')[1:]
    for b in blocks:
        wm = _WATCH_RE.search(b)
        if not wm or wm.group(1) in seen:
            continue
        seen.add(wm.group(1))
        tm = re.match(r'(.*?)</b>', b, re.DOTALL)
        im = re.search(r"<img src='(images/news/thumbs/[^']+)'", b)
        out.append({'id': wm.group(1), 'title': _txt(tm.group(1)) if tm else 'rész',
                    'thumb': urljoin(BASE, im.group(1)) if im else None})
    return out


# ---------------------------------------------------------------------------
# Lejátszás
# ---------------------------------------------------------------------------
def parse_watch(html):
    """Watch oldal: {'title','embed','next','anime_id','poster'}."""
    h = html or ''
    fm = re.search(r'<div class="stream-box-video">\s*<iframe[^>]+src="([^"]+)"', h, re.DOTALL)
    tm = re.search(r'<p class="stream-box-title">(.*?)</p>', h, re.DOTALL)
    nm = re.search(r'page=watch&(?:amp;)?id=(\d+)">K[^<]*vetkez', h)
    am = re.search(r'Adatlap: <a href="[^"]*page=anime&(?:amp;)?id=(\d+)"', h)
    pm = re.search(r'<figure class="stream-box-game-image[^"]*">\s*<img src="([^"]+)"', h)
    return {'title': _txt(tm.group(1)) if tm else '', 'embed': _abs(fm.group(1)) if fm else None,
            'next': nm.group(1) if nm else None, 'anime_id': am.group(1) if am else None,
            'poster': _abs(pm.group(1)) if pm else None}


def watch(vid):
    return parse_watch(cached_get('%s?page=watch&id=%s' % (ADATLAP, vid), _cache_minutes() * 60,
                                  valid=_is_page))


def has_resolver():
    try:
        import resolveurl  # noqa
        return True
    except ImportError:
        return False


def resolve_embed(url):
    """A beágyazott lejátszó (videa, indavideo, ...) feloldása ResolveURL-lel."""
    try:
        import resolveurl
    except ImportError:
        log('Nincs ResolveURL - nem feloldható: %s' % url, xbmc.LOGWARNING)
        return None
    try:
        hmf = resolveurl.HostedMediaFile(url)
        if hmf and hmf.valid_url():
            return hmf.resolve() or None
    except Exception as exc:  # noqa
        log('ResolveURL hiba (%s): %s' % (url, exc), xbmc.LOGWARNING)
    return None


def merge_headers(extra, ours):
    """'a=1&b=2' fejléc-sztringek egyesítése; a mieink (User-Agent!) felülírják."""
    out, order = {}, []
    for chunk in (extra, ours):
        for part in (chunk or '').split('&'):
            k, sep, v = part.partition('=')
            if sep and k:
                if k.lower() not in out:
                    order.append(k.lower())
                out[k.lower()] = (k, v)
    return '&'.join('%s=%s' % out[k] for k in order)


def play_url(media):
    """A feloldott URL + fejlécek, fix User-Agenttel."""
    base, _, extra = (media or '').partition('|')
    return base + '|' + merge_headers(extra, 'User-Agent=%s' % quote(user_agent(), ''))
