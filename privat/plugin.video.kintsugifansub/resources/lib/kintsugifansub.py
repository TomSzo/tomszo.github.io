# -*- coding: utf-8 -*-
"""
Kintsugi Fansub (kintsugi-fansub.hu) - privát, email+jelszó auto-login kliens.

A Kintsugi csapat a Muteki Fansubból vált ki; ugyanazzal a fiókkal lehet belépni.
A motor (Symfony-szerű backend) szinte azonos a Mutekiével, csak a domain és néhány
HTML-osztály tér el.

Belépés:
    A felhasználó a beállításokban (vagy egy txt-fájlban) megadja az email címét és
    jelszavát. Az addon a /login űrlapon keresztül automatikusan bejelentkezik (a form
    signin[_csrf_token] / _request_token mezőit is kitölti), a kapott munkamenet-sütit
    lemezre menti, és a további kéréseknél/lejátszásnál használja.

Lejátszás:
    GET /episode/watch/id/{id}  ->  <div id="video-player" data-file="...">
    A data-file minőségenként tartalmazza a KÖZVETLEN mp4 URL-eket:
        [720p]https://kintsugi-fansub.hu/stream/..01 (720p) [HASH].mp4|[1080p]https://...
    A kiválasztott minőség mp4-jét a session-cookie fejléccel játsszuk le.
    Felirat: /episode/download/type/cc/id/{id} (a bejelentkezett sütivel letöltve).
"""
import base64
import json
import os
import re

try:
    from urllib.parse import urljoin, quote
except ImportError:  # py2 (nem valószínű Kodi 19+ alatt)
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
DEFAULT_BASE = 'https://kintsugi-fansub.hu/'
DEFAULT_DOMAIN = 'kintsugi-fansub.hu'
# Mindig ez a User-Agent (a tulajdonos Firefox for Android böngészője) - nem állítható.
DEFAULT_UA = 'Mozilla/5.0 (Android 16; Mobile; rv:156.0) Gecko/156.0 Firefox/156.0'

_SESSION = requests.Session() if HAVE_REQUESTS else None
_COOKIES_LOADED = False
_ENSURED = False

# ---------------------------------------------------------------------------
# Visszafogottság (a fansub szerverek kímélése)
#   - két oldal-kérés között legalább _MIN_GAP mp szünet
#   - helyi napi számláló (minden oldal-/felirat-kérés +1; a videó-stream nem)
#   - sikertelen belépés után _LOGIN_COOLDOWN mp-ig nincs újabb próbálkozás
#   - oldal-gyorsítótár (cached_get), felirat-gyorsítótár
# ---------------------------------------------------------------------------
_MIN_GAP = 1.0
_LOGIN_COOLDOWN = 10 * 60
_LAST_REQ = [0.0]


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


def _req(fn, *args, **kw):
    """Minden, az oldalra menő kérés ezen megy át: szünet + számláló."""
    _throttle()
    _bump_request()
    return fn(*args, **kw)


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


def _page_cache_path(url):
    import hashlib
    d = os.path.join(_profile_dir(), 'cache')
    try:
        if not xbmcvfs.exists(d + os.sep):
            xbmcvfs.mkdirs(d)
    except Exception:  # noqa
        pass
    return os.path.join(d, hashlib.md5(url.encode('utf-8')).hexdigest() + '.html')


def cached_get(url, ttl, referer=None):
    """GET gyorsítótárral: ttl mp-en belül a lemezről (csak bejelentkezett oldalt tárolunk)."""
    import time
    p = _page_cache_path(url)
    if ttl > 0:
        try:
            if xbmcvfs.exists(p) and (time.time() - xbmcvfs.Stat(p).st_mtime()) < ttl:
                f = xbmcvfs.File(p)
                try:
                    html = f.read()
                finally:
                    f.close()
                if html and logged_in(html):
                    return html
        except Exception:  # noqa
            pass
    html = get(url, referer=referer)
    if html and logged_in(html):
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
    try:
        shutil.rmtree(os.path.join(_profile_dir(), 'cache'), ignore_errors=True)
    except Exception:  # noqa
        pass


def log(msg, level=xbmc.LOGINFO):
    xbmc.log('[%s] %s' % (ADDON_ID, msg), level)


def user_agent():
    return DEFAULT_UA


def base_url():
    url = (ADDON.getSetting('base_url') or DEFAULT_BASE).strip() or DEFAULT_BASE
    if not url.startswith('http'):
        url = 'https://' + url
    if not url.endswith('/'):
        url += '/'
    return url


# ---------------------------------------------------------------------------
# Profil / cookie-perzisztencia
# ---------------------------------------------------------------------------
def _profile_dir():
    prof = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
    try:
        if not xbmcvfs.exists(prof):
            xbmcvfs.mkdirs(prof)
    except Exception:  # noqa
        pass
    return prof


def _session_path():
    return os.path.join(_profile_dir(), 'session.json')


def save_cookies():
    if not _SESSION:
        return
    try:
        data = [{'name': c.name, 'value': c.value,
                 'domain': c.domain, 'path': c.path}
                for c in _SESSION.cookies]
        f = xbmcvfs.File(_session_path(), 'w')
        try:
            f.write(json.dumps(data))
        finally:
            f.close()
    except Exception as exc:  # noqa
        log('cookie mentés hiba: %s' % exc, xbmc.LOGWARNING)


def load_cookies():
    global _COOKIES_LOADED
    if _COOKIES_LOADED or not _SESSION:
        return
    _COOKIES_LOADED = True
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
                _SESSION.cookies.set(c['name'], c['value'],
                                     domain=c.get('domain') or DEFAULT_DOMAIN,
                                     path=c.get('path') or '/')
            except Exception:  # noqa
                pass
    except Exception as exc:  # noqa
        log('cookie betöltés hiba: %s' % exc, xbmc.LOGWARNING)


def clear_cookies():
    global _COOKIES_LOADED, _ENSURED
    _set_login_failed(False)
    if _SESSION:
        _SESSION.cookies.clear()
    _COOKIES_LOADED = False
    _ENSURED = False
    try:
        p = _session_path()
        if xbmcvfs.exists(p):
            xbmcvfs.delete(p)
    except Exception:  # noqa
        pass


def cookie_header():
    """A session-sütikből 'name=value; name2=value2' fejléc-string (lejátszáshoz)."""
    load_cookies()
    try:
        return '; '.join('%s=%s' % (c.name, c.value) for c in _SESSION.cookies)
    except Exception:  # noqa
        return ''


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def _headers(referer=None, ajax=False):
    h = {'User-Agent': user_agent(),
         'Accept-Language': 'hu-HU,hu;q=0.9,en;q=0.5',
         'Accept': ('application/json, text/javascript, */*; q=0.01' if ajax
                    else 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8')}
    if ajax:
        h['X-Requested-With'] = 'XMLHttpRequest'
    if referer:
        h['Referer'] = referer
    return h


def logged_in(html):
    """Bejelentkezettség: a bejelentkezett nav 'Kijelentkezés'/logout linket mutat."""
    if not html:
        return False
    return ('item-logout' in html) or ('/logout"' in html) or ('name="user-data"' in html)


def _username(html):
    m = re.search(r'name="user-data"\s+content="([^"]+)"', html or '')
    if not m:
        return ''
    try:
        data = json.loads(base64.b64decode(m.group(1)).decode('utf-8', 'replace'))
        return data.get('username') or ''
    except Exception:  # noqa
        return ''


def _attr(s, name):
    m = re.search(r'\b' + re.escape(name) + r'\s*=\s*"([^"]*)"', s or '', re.I)
    if m:
        return m.group(1)
    m = re.search(r'\b' + re.escape(name) + r"\s*=\s*'([^']*)'", s or '', re.I)
    return m.group(1) if m else ''


def _find_login_form(html):
    """A jelszó-mezőt tartalmazó <form> automatikus felismerése (mezőnevek nélkül is).

    A Kintsugi login űrlap mezői: _request_token, signin[_csrf_token], signin[username],
    signin[password], remember. A jelszó-mező (type=password) és a szöveges/email mező
    nevét automatikusan ismerjük fel, a többi rejtett mezőt (tokenek, remember) az
    értékükkel együtt visszaküldjük."""
    for m in re.finditer(r'<form\b([^>]*)>(.*?)</form>', html or '', re.DOTALL | re.I):
        attrs, body = m.group(1), m.group(2)
        if not re.search(r'type\s*=\s*["\']password["\']', body, re.I):
            continue
        fields, user, pwd = {}, None, None
        for im in re.finditer(r'<input\b([^>]*)>', body, re.I):
            ia = im.group(1)
            name = _attr(ia, 'name')
            if not name:
                continue
            itype = (_attr(ia, 'type') or 'text').lower()
            fields[name] = _attr(ia, 'value')
            if itype == 'password' and not pwd:
                pwd = name
            elif itype in ('email', 'text') and '_csrf_token' not in name:
                if itype == 'email' or user is None:
                    user = name
        return {'action': _attr(attrs, 'action') or 'login',
                'method': (_attr(attrs, 'method') or 'post').lower(),
                'fields': fields, 'user': user, 'pwd': pwd}
    return None


# ---------------------------------------------------------------------------
# Hitelesítő adatok: beállítás VAGY txt-fájl (nincs gépelés)
# ---------------------------------------------------------------------------
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
    """Rugalmas email/jelszó kinyerés txt-ből. Visszaad: (email, jelszó) vagy ('','')."""
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
    """Auto-bejelentkezés email+jelszóval a /login űrlapon. Visszaad: sikeres?"""
    if not _SESSION:
        return False
    email, pw = _credentials()
    if not email or not pw:
        log('Nincs email/jelszó (sem beállítás, sem txt).', xbmc.LOGWARNING)
        return False
    if _login_blocked():
        log('Az előző belépés 10 percen belül sikertelen volt - most nem próbálkozunk '
            '(a szerver kímélése). "Munkamenet törlése" után azonnal újrapróbálja.',
            xbmc.LOGWARNING)
        return False
    login_url = urljoin(base_url(), 'login')
    try:
        page = _req(_SESSION.get, login_url, headers=_headers(base_url()), timeout=25).text
    except Exception as exc:  # noqa
        log('login GET hiba: %s' % exc, xbmc.LOGERROR)
        return False
    form = _find_login_form(page)
    if form:
        data = dict(form['fields'])
        action = urljoin(base_url(), form['action'])
        if form.get('user'):
            data[form['user']] = email
        if form.get('pwd'):
            data[form['pwd']] = pw
    else:
        data, action = {}, login_url
    # A "maradjak bejelentkezve" jelölőnégyzet -> tartós munkamenet
    data.setdefault('remember', '1')
    # csrf tartalék (ha az űrlap-felismerés nem hozta): signin[_csrf_token] vagy _csrf_token
    if not any('_csrf_token' in k for k in data):
        cm = (re.search(r'name="(signin\[_csrf_token\])"\s+value="([^"]+)"', page)
              or re.search(r'name="(_csrf_token)"\s+value="([^"]+)"', page))
        if cm:
            data[cm.group(1)] = cm.group(2)
    if not (form and form.get('user')):
        data.setdefault('signin[username]', email)
    if not (form and form.get('pwd')):
        data.setdefault('signin[password]', pw)
    try:
        r = _req(_SESSION.post, action, data=data, headers=_headers(login_url),
                          timeout=30, allow_redirects=True)
        ok = logged_in(r.text)
        if not ok:
            ok = logged_in(_req(_SESSION.get, base_url(), headers=_headers(base_url()),
                                        timeout=25).text)
    except Exception as exc:  # noqa
        log('login POST hiba: %s' % exc, xbmc.LOGERROR)
        return False
    _set_login_failed(not ok)
    if ok:
        save_cookies()
        log('Bejelentkezés sikeres.')
    else:
        log('Bejelentkezés SIKERTELEN (rossz email/jelszó, vagy változott a login űrlap).',
            xbmc.LOGWARNING)
    return ok


def ensure_login():
    """Betölti a mentett sütit; ha nincs, megpróbál bejelentkezni."""
    global _ENSURED
    if _ENSURED:
        return True
    _ENSURED = True
    load_cookies()
    if _SESSION and len(_SESSION.cookies) > 0:
        return True   # feltételezzük, hogy érvényes; a get() ellenőrzi/újralép
    return login()


def get(url, referer=None, timeout=25, ajax=False, auth=True):
    """GET a base_url-höz relatívan. auth=True esetén gondoskodik a belépésről,
    és ha kijelentkezve talál, egyszer újra bejelentkezik és újratölt."""
    if not _SESSION:
        log('Nincs requests modul!', xbmc.LOGERROR)
        return ''
    if auth:
        ensure_login()
    full = urljoin(base_url(), url)
    log('GET %s' % full)
    try:
        r = _req(_SESSION.get, full, headers=_headers(referer, ajax=ajax), timeout=timeout)
        r.encoding = 'utf-8'
        html = r.text
    except Exception as exc:  # noqa
        log('GET hiba: %s (%s)' % (exc, full), xbmc.LOGERROR)
        return ''
    if auth and not ajax and not logged_in(html):
        log('Kijelentkezve érzékelve – újrabejelentkezés.', xbmc.LOGINFO)
        if login():
            try:
                r = _req(_SESSION.get, full, headers=_headers(referer, ajax=ajax), timeout=timeout)
                r.encoding = 'utf-8'
                html = r.text
            except Exception as exc:  # noqa
                log('GET (retry) hiba: %s' % exc, xbmc.LOGERROR)
    return html


def check_login():
    """Diagnosztika: (bejelentkezve?, felhasználónév, főoldal hossza)."""
    html = get('', referer=base_url())
    return logged_in(html), _username(html), len(html or '')


# ---------------------------------------------------------------------------
# Szöveg-segédek
# ---------------------------------------------------------------------------
_ENT = (('&amp;', '&'), ('&#039;', "'"), ('&#39;', "'"), ('&quot;', '"'),
        ('&nbsp;', ' '), ('&lt;', '<'), ('&gt;', '>'), ('&aacute;', 'á'),
        ('&eacute;', 'é'), ('&ouml;', 'ö'), ('&uuml;', 'ü'), ('&oacute;', 'ó'),
        ('&uacute;', 'ú'), ('&iacute;', 'í'), ('&auml;', 'ä'))


def _unent(t):
    """HTML-entitások feloldása tag-eltávolítás nélkül (attribútum-értékekhez)."""
    t = t or ''
    for a, b in _ENT:
        t = t.replace(a, b)
    return t


def _txt(t):
    t = re.sub(r'<[^>]+>', ' ', t or '')
    for a, b in _ENT:
        t = t.replace(a, b)
    return re.sub(r'\s+', ' ', t).strip()


def _abs(u):
    if not u:
        return None
    return u if u.startswith('http') else urljoin(base_url(), u)


# ---------------------------------------------------------------------------
# Projektek (böngészés / keresés) - egyszer letöltjük a /projects oldalt, cache-eljük
# ---------------------------------------------------------------------------
_STATUS_LABEL = {'active': 'Aktív', 'finished': 'Befejezett', 'planned': 'Tervezett',
                 'suspended': 'Felfüggesztett', 'dropped': 'Dobott', 'hidden': 'Rejtett'}


def _projects_cache_path():
    return os.path.join(_profile_dir(), 'projects.html')


def _cache_minutes():
    try:
        return max(0, int(ADDON.getSetting('cache_minutes') or 30))
    except Exception:  # noqa
        return 30


def projects_html(force=False):
    import time
    path = _projects_cache_path()
    ttl = _cache_minutes() * 60
    if not force and ttl > 0:
        try:
            if xbmcvfs.exists(path):
                st = xbmcvfs.Stat(path)
                if (time.time() - st.st_mtime()) < ttl:
                    f = xbmcvfs.File(path)
                    try:
                        raw = f.read()
                    finally:
                        f.close()
                    if raw and 'project-item' in raw:
                        return raw
        except Exception:  # noqa
            pass
    html = get('projects', referer=base_url())
    if html and 'project-item' in html:
        try:
            f = xbmcvfs.File(path, 'w')
            try:
                f.write(html)
            finally:
                f.close()
        except Exception:  # noqa
            pass
    return html


_CARD_RE = re.compile(r'<a\s+href="/project/([^"]+)"\s+class="project-item ([^"]*)"([^>]*)>',
                      re.IGNORECASE)


def parse_projects(html=None):
    """A /projects oldal összes kártyája:
    [{slug,title,status,status_hu,year,season,tags,art,episodes,plot,alt}]."""
    html = html if html is not None else projects_html()
    if not html:
        return []
    matches = list(_CARD_RE.finditer(html))
    out = []
    for idx, m in enumerate(matches):
        slug, klass, rest = m.group(1), m.group(2), m.group(3)
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(html)
        body = html[m.end():end]
        sm = re.search(r'status-(\w+)', klass)
        status = sm.group(1) if sm else ''
        tm = re.search(r'<div class="project-item-title">\s*<span>([^<]+)</span>', body)
        title = _txt(tm.group(1)) if tm else slug
        am = re.search(r'<img\s+src="([^"]+)"', body)
        art = _abs(am.group(1)) if am else None
        # Kintsugi: <span class="project-episodes"><i ...></i><span>12/12 rész</span></span>
        epm = re.search(r'<span class="project-episodes">.*?<span>([^<]+)</span>', body, re.DOTALL)
        episodes = _txt(epm.group(1)) if epm else ''
        pm = re.search(r'<div class="project-description-inner">(.*?)</div>', body, re.DOTALL)
        plot = _txt(pm.group(1)) if pm else ''
        altm = re.search(r'<template class="project-titles">(.*?)</template>', body, re.DOTALL)
        alt = _txt(altm.group(1)) if altm else ''
        out.append({'slug': slug, 'title': title, 'status': status,
                    'status_hu': _STATUS_LABEL.get(status, status),
                    'year': _attr(rest, 'data-year'), 'season': _attr(rest, 'data-season'),
                    'tags': _unent(_attr(rest, 'data-tags')), 'art': art,
                    'episodes': episodes, 'plot': plot, 'alt': alt.lower()})
    return out


def filters_meta(html=None):
    """A /projects szűrőiből: (seasons[(key,label)], genres[str]).

    Kintsugi: <select name="season"> option-jai + <input name="genre[]" value="...">."""
    html = html if html is not None else projects_html()
    seasons, genres = [], []
    sel = re.search(r'<select[^>]*\bname="season"[^>]*>(.*?)</select>', html or '',
                    re.DOTALL | re.I)
    if sel:
        for om in re.finditer(r'<option value="([^"]*)"[^>]*>(.*?)</option>', sel.group(1),
                              re.DOTALL):
            key, label = om.group(1).strip(), _txt(om.group(2))
            if key:  # üres érték = "Minden szezon"
                seasons.append((key, label))
    seen = set()
    for gm in re.finditer(r'name="genre\[\]"\s+value="([^"]+)"', html or ''):
        g = _txt(gm.group(1))
        if g and g.lower() not in seen:
            seen.add(g.lower())
            genres.append(g)
    return seasons, genres


def projects_by_status(status):
    return [p for p in parse_projects() if p['status'] == status]


def projects_all():
    return parse_projects()


def projects_by_season(key):
    """key: '2026-4' (év-évszak) vagy '2026' (csak év)."""
    year, _, season = key.partition('-')
    out = []
    for p in parse_projects():
        if p['year'] != year:
            continue
        if season and p['season'] != season:
            continue
        out.append(p)
    return out


def projects_by_genre(genre):
    g = (genre or '').strip().lower()
    return [p for p in parse_projects()
            if g and g in (t.strip().lower() for t in p['tags'].split(','))]


def search_projects(term):
    term = (term or '').strip().lower()
    if not term:
        return []
    out = []
    for p in parse_projects():
        if term in p['title'].lower() or term in p['alt'] or term in p['tags'].lower():
            out.append(p)
    log('%d találat: "%s"' % (len(out), term))
    return out


# ---------------------------------------------------------------------------
# Projekt oldal -> epizódok
# ---------------------------------------------------------------------------
_EP_ART_RE = re.compile(r'<article class="episode-item[^"]*"\s+data-episode-id="(\d+)"',
                        re.IGNORECASE)


def project_episodes(slug):
    """Egy projekt oldaláról az epizódok:
    {'title','plot','episodes':[{id,title,thumb,date}]}. A date az epizód kiadási
    ISO-időbélyege (rendezéshez), ha megtalálható."""
    html = cached_get('project/%s' % slug, _cache_minutes() * 60,
                      referer=base_url() + 'projects')
    if not html:
        return {'title': '', 'plot': '', 'episodes': []}
    tm = re.search(r'<div class="project-title[^"]*">\s*<span>([^<]+)</span>', html)
    title = _txt(tm.group(1)) if tm else slug
    plot = ''
    pm = re.search(r'<div class="project-description">(.*?)<div class="project-description-footer"',
                   html, re.DOTALL)
    if pm:
        seg = pm.group(1)
        # a borító + megtekintés/letöltés kártya szövegének eltávolítása
        seg = re.sub(r'<div class="project-engagement-card".*?</div>', '', seg, flags=re.DOTALL)
        seg = re.sub(r'<picture\b.*?</picture>', '', seg, flags=re.DOTALL | re.I)
        plot = _txt(seg)
    episodes = []
    seen = set()
    starts = [(m.group(1), m.start()) for m in _EP_ART_RE.finditer(html)]
    for i, (eid, pos) in enumerate(starts):
        if eid in seen:
            continue
        seen.add(eid)
        end = starts[i + 1][1] if i + 1 < len(starts) else len(html)
        block = html[pos:end]
        numm = re.search(r'<span class="episode-number">([^<]+)</span>', block)
        etm = re.search(r'<h3 class="episode-title">([^<]+)</h3>', block)
        num = _txt(numm.group(1)) if numm else ''
        et = _txt(etm.group(1)) if etm else ''
        if num and et:
            label = '%s – %s' % (num, et)
        else:
            label = num or et or ('rész %s' % eid)
        thm = re.search(r'<img\s+src="([^"]+)"', block)
        thumb = _abs(thm.group(1)) if thm else None
        dtm = re.search(r'datetime="([^"]+)"', block)
        date = dtm.group(1) if dtm else ''
        episodes.append({'id': eid, 'title': label, 'thumb': thumb, 'date': date})
    # tartalék: ha az article-darabolás nem talált semmit
    if not episodes:
        for eid in re.findall(r'/episode/watch/id/(\d+)', html):
            if eid in seen:
                continue
            seen.add(eid)
            episodes.append({'id': eid, 'title': 'rész %s' % eid, 'thumb': None, 'date': ''})
    log('%d epizód: project/%s ("%s")' % (len(episodes), slug, title))
    return {'title': title, 'plot': plot, 'episodes': episodes}


# ---------------------------------------------------------------------------
# Legfrissebb részek: az aktív projektek legújabb epizódjai, dátum szerint rendezve
# ---------------------------------------------------------------------------
def latest_episodes(limit=40, max_projects=15):
    """Az aktív (folyamatban lévő) projektek legfrissebb epizódjai, kiadási dátum
    szerint csökkenő sorrendben: [{'id','title','art','date'}].

    Csak a megerősített HTML-t használja (projektlista + projektoldalak), így stabil.
    Minden aktív projektből a legújabb epizódot veszi."""
    active = projects_by_status('active')
    out = []
    for p in active[:max_projects]:
        data = project_episodes(p['slug'])
        eps = data.get('episodes') or []
        if not eps:
            continue
        newest = max(eps, key=lambda e: (e.get('date') or '', _epnum(e.get('title'))))
        out.append({'id': newest['id'],
                    'title': '%s · %s' % (p['title'], newest['title']),
                    'art': newest.get('thumb') or p.get('art'),
                    'date': newest.get('date') or ''})
    out.sort(key=lambda e: e.get('date') or '', reverse=True)
    log('%d legfrissebb rész (aktív projektekből)' % len(out))
    return out[:limit]


def _epnum(title):
    m = re.search(r'(\d+)', title or '')
    return int(m.group(1)) if m else 0


# ---------------------------------------------------------------------------
# Lejátszás: watch oldal -> data-file (közvetlen mp4-ek minőségenként)
# ---------------------------------------------------------------------------
def watch_sources(ep_id):
    """A /episode/watch/id/{id} oldalról:
    {'title','poster','skip','qualities':[(label,url)],'subtitle_url','referer'}."""
    referer = base_url() + 'episode/watch/id/%s' % ep_id
    html = cached_get('episode/watch/id/%s' % ep_id, _cache_minutes() * 60,
                      referer=base_url())
    res = {'title': '', 'poster': None, 'skip': '', 'qualities': [],
           'subtitle_url': base_url() + 'episode/download/type/cc/id/%s' % ep_id,
           'referer': referer}
    if not html:
        return res
    dm = re.search(r'id="video-player"(.*?)>', html, re.DOTALL)
    attrs = dm.group(1) if dm else ''
    res['title'] = _txt(_attr(attrs, 'data-title'))
    poster = _attr(attrs, 'data-poster')
    if poster:
        res['poster'] = _abs(poster.split(' or ')[0].strip())
    res['skip'] = _attr(attrs, 'data-skip')
    data_file = _attr(attrs, 'data-file').replace('&amp;', '&')
    for tok in data_file.split('|'):
        mm = re.match(r'\s*\[([^\]]+)\]\s*(\S.*)$', tok)
        if mm:
            res['qualities'].append((mm.group(1).strip(), mm.group(2).strip()))
    log('watch %s: %d minőség, cím="%s"' % (ep_id, len(res['qualities']), res['title']))
    return res


def _rank(label):
    l = (label or '').lower().strip()
    if l in ('4k', '2160p', 'uhd'):
        return 2160
    if l in ('2k', '1440p', 'qhd'):
        return 1440
    m = re.search(r'(\d{3,4})', l)
    return int(m.group(1)) if m else 0


def best_quality(qualities):
    if not qualities:
        return (None, None)
    return max(qualities, key=lambda t: _rank(t[0]))


def quality_by_label(qualities, want):
    w = (want or '').lower().strip()
    for l, u in qualities:
        if l.lower().strip() == w:
            return (l, u)
    return (None, None)


def play_headers(referer):
    parts = ['User-Agent=%s' % quote(user_agent(), ''),
             'Referer=%s' % quote(referer or base_url(), '')]
    ch = cookie_header()
    if ch:
        parts.append('Cookie=%s' % quote(ch, ''))
    return '&'.join(parts)


def download_subtitle(ep_id):
    """A rész feliratát letölti (bejelentkezett sütivel) és elmenti; visszaadja az elérési utat."""
    if not _SESSION:
        return None
    import time
    for ext in ('ass', 'srt', 'ssa', 'vtt'):
        cp = os.path.join(_profile_dir(), 'sub_%s.%s' % (ep_id, ext))
        try:
            if xbmcvfs.exists(cp) and (time.time() - xbmcvfs.Stat(cp).st_mtime()) < 7 * 86400:
                return cp
        except Exception:  # noqa
            pass
    ensure_login()
    url = base_url() + 'episode/download/type/cc/id/%s' % ep_id
    try:
        r = _req(_SESSION.get, url, headers=_headers(base_url() + 'episode/watch/id/%s' % ep_id),
                         timeout=25, allow_redirects=True)
        data = r.content or b''
    except Exception as exc:  # noqa
        log('felirat letöltés hiba: %s' % exc, xbmc.LOGWARNING)
        return None
    if not data or len(data) < 8:
        return None
    head = data[:200].lstrip()
    ext = 'srt'
    if head[:11].lower() == b'[script inf' or b'\n[Events]' in data[:400] or b'Dialogue:' in data[:400]:
        ext = 'ass'
    cd = r.headers.get('Content-Disposition', '')
    fm = re.search(r'\.(ass|ssa|srt|vtt)"?', cd, re.I)
    if fm:
        ext = fm.group(1).lower()
    path = os.path.join(_profile_dir(), 'sub_%s.%s' % (ep_id, ext))
    try:
        f = xbmcvfs.File(path, 'w')
        try:
            f.write(bytearray(data))
        finally:
            f.close()
        return path
    except Exception as exc:  # noqa
        log('felirat mentés hiba: %s' % exc, xbmc.LOGWARNING)
        return None
