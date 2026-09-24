# -*- coding: utf-8 -*-
"""
Network4 (www.network4.hu) - privát, email+jelszó auto-login kliens a saját előfizetéshez.

Belépés (Laravel):
    GET /login  -> <input type="hidden" name="_token" value="...">
    POST /login (_token, email, password, remember) -> munkamenet-sütik
    (XSRF-TOKEN + session), lemezre mentve.

Lejátszás (a böngészős HAR alapján):
    A /sport/watch/<slug> oldalon a THEOplayer egy Uplynk DASH manifestet tölt be:
        https://content.uplynk.com/<cid>.mpd?tc=1&exp=...&...&sig=...
    Az URL szerveroldalon aláírt és kb. 1 óráig érvényes (exp), ezért MINDIG lejátszáskor
    kérjük le frissen. Widevine licenc: Uplynk (alapértelmezés https://content.uplynk.com/wv),
    a Kodi inputstream.adaptive + a készülék hivatalos Widevine CDM-je végzi.
    (A license.theoplayer.com hívás csak a THEOplayer saját lejátszó-licence, nem DRM.)

    Az aláírt .mpd URL és a licenc URL közvetlenül a watch oldal HTML-jében van
    (player.source / chromecastSource: contentProtection.widevine.licenseAcquisitionURL).
    Tartalékként a /user-session-t és a lapon hivatkozott API-kat is átnézzük; ha semmi,
    a letöltött oldalt elmentjük az addon_data mappába hibakereséshez.
"""
import json
import os
import re
import time

try:
    from urllib.parse import urljoin, quote, urlparse
except ImportError:  # py2 (nem valószínű Kodi 19+ alatt)
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
DEFAULT_BASE = 'https://www.network4.hu/'
DEFAULT_DOMAIN = '.network4.hu'
DEFAULT_LICENSE = 'https://content.uplynk.com/wv'
DEFAULT_UA = 'Mozilla/5.0 (Android 16; Mobile; rv:156.0) Gecko/156.0 Firefox/156.0'

_SESSION = requests.Session() if HAVE_REQUESTS else None
_COOKIES_LOADED = False
_ENSURED = False


def log(msg, level=xbmc.LOGINFO):
    xbmc.log('[%s] %s' % (ADDON_ID, msg), level)


def user_agent():
    return (ADDON.getSetting('user_agent') or '').strip() or DEFAULT_UA


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
# Süti-mód: a böngészőből kimásolt sütik (a /login Cloudflare-kihívás mögött van)
# ---------------------------------------------------------------------------
def parse_cookie_input(text):
    """Böngészőből kimásolt sütik -> [(név, érték)]. Elfogadott formák:
      - Cookie fejléc:        a=b; c=d
      - Netscape cookies.txt: tabulátorral tagolt 7 mező
      - JSON export:          [{"name": .., "value": ..}, ..] (Cookie-Editor stb.)"""
    text = (text or '').strip()
    if not text:
        return []
    out = []
    if text[:1] in '[{':
        try:
            d = json.loads(text)
            if isinstance(d, dict):
                d = d.get('cookies') or [d]
            for c in d:
                if isinstance(c, dict) and c.get('name'):
                    dom = str(c.get('domain') or '')
                    if not dom or 'network4' in dom:
                        out.append((str(c['name']), str(c.get('value', ''))))
            return out
        except Exception:  # noqa
            pass
    lines = [l for l in text.splitlines() if l.strip()]
    if any(l.count('\t') >= 6 for l in lines):
        for l in lines:
            if l.startswith('#') and not l.startswith('#HttpOnly_'):
                continue
            f = l.split('\t')
            if len(f) >= 7 and 'network4' in f[0]:
                out.append((f[5].strip(), f[6].strip()))
        return out
    text = re.sub(r'^\s*cookie\s*:\s*', '', ' '.join(lines), flags=re.I)
    for part in text.split(';'):
        if '=' in part:
            n, _, v = part.strip().partition('=')
            if n.strip():
                out.append((n.strip(), v.strip()))
    return out


def _cookie_input():
    """A beállításban megadott süti-szöveg, vagy a süti-fájl / fix cookies.txt tartalma."""
    txt = (ADDON.getSetting('cookie') or '').strip()
    if txt:
        return txt
    for path in [(ADDON.getSetting('cookie_file') or '').strip(),
                 xbmcvfs.translatePath('special://profile/addon_data/%s/cookies.txt' % ADDON_ID)]:
        data = _read_file(path)
        if data and data.strip():
            return data
    return ''


def have_cookie_input():
    return bool(parse_cookie_input(_cookie_input()))


def import_cookies(force=False):
    """A böngészős sütik betöltése a munkamenetbe, ha újak/változtak (vagy force)."""
    if not _SESSION:
        return False
    raw = _cookie_input()
    pairs = parse_cookie_input(raw)
    if not pairs:
        return False
    import hashlib
    h = hashlib.md5(raw.encode('utf-8')).hexdigest()
    mark = os.path.join(_profile_dir(), 'cookie_src.md5')
    if not force and _read_file(mark).strip() == h:
        return False
    for n, v in pairs:
        _SESSION.cookies.set(n, v, domain=DEFAULT_DOMAIN, path='/')
    save_cookies()
    try:
        f = xbmcvfs.File(mark, 'w')
        try:
            f.write(h)
        finally:
            f.close()
    except Exception:  # noqa
        pass
    log('Böngészős sütik betöltve: %s' % ', '.join(n for n, _ in pairs))
    return True


LAST_CHALLENGE = [False]


def is_challenge(html, resp=None):
    """Cloudflare 'Just a moment...' / managed challenge oldal?"""
    if (getattr(resp, 'headers', None) or {}).get('cf-mitigated') == 'challenge':
        return True
    h = html or ''
    return ('_cf_chl_opt' in h
            or ('challenge-platform/h/' in h and '<title>Just a moment' in h))


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def _attr(s, name):
    m = re.search(r'\b' + re.escape(name) + r'\s*=\s*"([^"]*)"', s or '', re.I)
    if m:
        return m.group(1)
    m = re.search(r'\b' + re.escape(name) + r"\s*=\s*'([^']*)'", s or '', re.I)
    return m.group(1) if m else ''


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


def have_auth():
    """Van-e bármilyen belépési mód (böngészős süti vagy email/jelszó)."""
    return have_cookie_input() or have_credentials()


def cred_source():
    """Diagnosztika: honnan jön a belépés (süti / beállítás / fájl / nincs)."""
    if parse_cookie_input((ADDON.getSetting('cookie') or '').strip()):
        return 'böngészős sütik (beállítás)'
    if parse_cookie_input(_cookie_input()):
        return 'böngészős sütik (fájl)'

    if (ADDON.getSetting('email') or '').strip() and (ADDON.getSetting('password') or ''):
        return 'beállítás-mezők'
    cf = (ADDON.getSetting('cred_file') or '').strip()
    if cf and _parse_creds(_read_file(cf))[0]:
        return 'fájl: %s' % cf
    if _parse_creds(_read_file(_cred_fixed_path()))[0]:
        return 'fix fájl (login.txt)'
    return 'nincs'



# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def _origin():
    u = urlparse(base_url())
    return '%s://%s' % (u.scheme, u.netloc)


def _headers(referer=None, ajax=False):
    h = {'User-Agent': user_agent(),
         'Accept-Language': 'hu-HU,hu;q=0.9,en;q=0.5',
         'Accept': ('application/json, text/plain, */*' if ajax
                    else 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8')}
    if ajax:
        h['X-Requested-With'] = 'XMLHttpRequest'
        xsrf = _cookie_value('XSRF-TOKEN')
        if xsrf:
            h['X-XSRF-TOKEN'] = _unquote(xsrf)
    if referer:
        h['Referer'] = referer
    return h


def _unquote(s):
    try:
        from urllib.parse import unquote
    except ImportError:
        from urllib import unquote
    return unquote(s or '')


def _cookie_value(name):
    if not _SESSION:
        return ''
    for c in _SESSION.cookies:
        if c.name == name:
            return c.value
    return ''


def logged_in(html):
    """Bejelentkezettség (Laravel): van kijelentkezés link/űrlap, és nincs jelszó-mezős
    login űrlap az oldalon."""
    if not html:
        return False
    has_logout = bool(re.search(r'/logout\b|kijelentkez', html, re.I))
    has_pwd_form = bool(re.search(r'<input[^>]+type\s*=\s*["\']password["\']', html, re.I))
    return has_logout and not has_pwd_form


def _find_login_form(html):
    """A jelszó-mezőt tartalmazó <form> automatikus felismerése.
    Network4: _token (rejtett), email, password (+ remember)."""
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
            if itype == 'checkbox':
                continue  # a remember-t külön állítjuk
            fields[name] = _unent(_attr(ia, 'value'))
            if itype == 'password' and not pwd:
                pwd = name
            elif itype in ('email', 'text') and name != '_token':
                if itype == 'email' or user is None:
                    user = name
        return {'action': _unent(_attr(attrs, 'action')) or 'login',
                'fields': fields, 'user': user, 'pwd': pwd}
    return None


def _csrf_token(html):
    m = (re.search(r'name=["\']_token["\']\s+value=["\']([^"\']+)', html or '')
         or re.search(r'value=["\']([^"\']+)["\']\s+name=["\']_token["\']', html or '')
         or re.search(r'<meta\s+name=["\']csrf-token["\']\s+content=["\']([^"\']+)', html or ''))
    return m.group(1) if m else ''


def login():
    """Auto-bejelentkezés: GET /login (_token) -> POST /login (_token, email, password)."""
    if not _SESSION:
        return False
    email, pw = _credentials()
    if not email or not pw:
        log('Nincs email/jelszó (sem beállítás, sem txt).', xbmc.LOGWARNING)
        return False
    login_url = urljoin(base_url(), 'login')
    try:
        page = _SESSION.get(login_url, headers=_headers(base_url()), timeout=25).text
    except Exception as exc:  # noqa
        log('login GET hiba: %s' % exc, xbmc.LOGERROR)
        return False
    if is_challenge(page):
        LAST_CHALLENGE[0] = True
        log('A /login Cloudflare-kihívás mögött van - email/jelszós belépés nem lehetséges. '
            'Használd a süti-módot (Beállítások -> Belépés).', xbmc.LOGWARNING)
        save_debug('login.html', page)
        return False
    form = _find_login_form(page)
    data, action = {}, login_url
    if form:
        data = dict(form['fields'])
        action = urljoin(login_url, form['action'])
        if form.get('user'):
            data[form['user']] = email
        if form.get('pwd'):
            data[form['pwd']] = pw
    if not data.get('_token'):
        data['_token'] = _csrf_token(page)
    if not (form and form.get('user')):
        data['email'] = email
    if not (form and form.get('pwd')):
        data['password'] = pw
    data.setdefault('remember', 'on')
    if not data.get('_token'):
        log('Nem találtam _token-t a login oldalon (Cloudflare kihívás?). Hossz: %d'
            % len(page or ''), xbmc.LOGWARNING)
        save_debug('login.html', page)
    h = _headers(login_url)
    h['Origin'] = _origin()
    h['Content-Type'] = 'application/x-www-form-urlencoded'
    try:
        r = _SESSION.post(action, data=data, headers=h, timeout=30, allow_redirects=True)
        if is_challenge(r.text, r):
            LAST_CHALLENGE[0] = True
            log('A login POST Cloudflare-kihívást kapott - használd a süti-módot.',
                xbmc.LOGWARNING)
            save_debug('login_result.html', r.text)
            return False
        ok = logged_in(r.text) and not urlparse(r.url).path.rstrip('/').endswith('/login')
        if not ok:
            ok = logged_in(_SESSION.get(base_url(), headers=_headers(base_url()),
                                        timeout=25).text)
    except Exception as exc:  # noqa
        log('login POST hiba: %s' % exc, xbmc.LOGERROR)
        return False
    if ok:
        save_cookies()
        log('Bejelentkezés sikeres.')
    else:
        log('Bejelentkezés SIKERTELEN (rossz email/jelszó, Cloudflare, vagy változott az '
            'űrlap). HTTP %s, URL: %s' % (r.status_code, r.url), xbmc.LOGWARNING)
        save_debug('login_result.html', r.text)
    return ok


def ensure_login():
    """Betölti a mentett sütit; ha nincs, megpróbál bejelentkezni."""
    global _ENSURED
    if _ENSURED:
        return True
    _ENSURED = True
    load_cookies()
    import_cookies()
    if _SESSION and len(_SESSION.cookies) > 0:
        return True   # feltételezzük, hogy érvényes; a get() ellenőrzi/újralép
    return login()


def get(url, referer=None, timeout=25, ajax=False, auth=True):
    """GET a base_url-höz relatívan; kijelentkezett állapotnál egyszer újra belép."""
    if not _SESSION:
        log('Nincs requests modul!', xbmc.LOGERROR)
        return ''
    if auth:
        ensure_login()
    full = urljoin(base_url(), url)
    log('GET %s' % full)

    def _do():
        r = _SESSION.get(full, headers=_headers(referer or base_url(), ajax=ajax),
                         timeout=timeout)
        r.encoding = 'utf-8'
        return r

    try:
        r = _do()
    except Exception as exc:  # noqa
        log('GET hiba: %s (%s)' % (exc, full), xbmc.LOGERROR)
        return ''
    html = r.text
    if is_challenge(html, r):
        LAST_CHALLENGE[0] = True
        log('Cloudflare-kihívás (%s) - a böngészős sütik (és a böngésző User-Agentje) '
            'kellenek a beállításokban.' % full, xbmc.LOGWARNING)
        save_debug('challenge_%s.html' % (urlparse(full).path.strip('/').replace('/', '_')
                                           or 'root'), html)
        return ''
    relogin = False
    if auth and not ajax and not logged_in(html):
        relogin = True
    if auth and ajax and r.status_code in (401, 419):
        relogin = True
    if relogin and import_cookies(force=True):
        log('Kijelentkezve érzékelve – böngészős sütik újratöltve.')
        try:
            r = _do()
            html = '' if is_challenge(r.text, r) else r.text
            relogin = auth and not ajax and not logged_in(html)
        except Exception as exc:  # noqa
            log('GET (retry) hiba: %s' % exc, xbmc.LOGERROR)
    if relogin and not have_credentials():
        log('Kijelentkezve, és nincs email/jelszó - frissítsd a böngészős sütiket.',
            xbmc.LOGWARNING)
    elif relogin:
        log('Kijelentkezve érzékelve – újrabejelentkezés.')
        if login():
            try:
                html = _do().text
            except Exception as exc:  # noqa
                log('GET (retry) hiba: %s' % exc, xbmc.LOGERROR)
    else:
        save_cookies()
    return html


def user_session():
    """A böngésző is lekéri: GET /user-session (JSON). Visszaad: dict vagy {}."""
    raw = get('user-session', ajax=True)
    try:
        return json.loads(raw) if raw else {}
    except Exception:  # noqa
        return {}


def _find_key(obj, keys, depth=0):
    if depth > 6:
        return None
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in keys and isinstance(v, (str, int)) and v:
                return v
        for v in obj.values():
            r = _find_key(v, keys, depth + 1)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_key(v, keys, depth + 1)
            if r:
                return r
    return None


def check_login():
    """Diagnosztika: (bejelentkezve?, felhasználó, főoldal hossza, user-session kulcsok)."""
    html = get('', referer=base_url())
    us = user_session()
    who = _find_key(us, ('email', 'name', 'username')) or ''
    keys = ', '.join(sorted(us.keys())[:12]) if isinstance(us, dict) else ''
    return logged_in(html), who, len(html or ''), keys


# ---------------------------------------------------------------------------
# Szöveg-segédek
# ---------------------------------------------------------------------------
_ENT = (('&amp;', '&'), ('&#039;', "'"), ('&#39;', "'"), ('&quot;', '"'),
        ('&nbsp;', ' '), ('&lt;', '<'), ('&gt;', '>'), ('&aacute;', 'á'),
        ('&eacute;', 'é'), ('&ouml;', 'ö'), ('&uuml;', 'ü'), ('&oacute;', 'ó'),
        ('&uacute;', 'ú'), ('&iacute;', 'í'), ('&odblac;', 'ő'), ('&udblac;', 'ű'),
        ('&ndash;', '–'), ('&mdash;', '—'), ('&#x2F;', '/'), ('&#47;', '/'))


def _unent(t):
    t = t or ''
    for a, b in _ENT:
        t = t.replace(a, b)
    return t


def _txt(t):
    return re.sub(r'\s+', ' ', _unent(re.sub(r'<[^>]+>', ' ', t or ''))).strip()


def _unescape_js(t):
    """JSON/JS-be ágyazott URL-ek: \\/ -> /, \\u0026 -> &, &amp; -> &."""
    t = (t or '').replace('\\/', '/')
    t = re.sub(r'\\u00([0-9a-fA-F]{2})', lambda m: chr(int(m.group(1), 16)), t)
    return _unent(t)


def _abs(u):
    if not u:
        return None
    if u.startswith('//'):
        return 'https:' + u
    return u if u.startswith('http') else urljoin(base_url(), u)


def _pretty_slug(slug):
    s = re.sub(r'[-_]+', ' ', slug or '').strip()
    return s[:1].upper() + s[1:]


# ---------------------------------------------------------------------------
# Hibakereső mentés
# ---------------------------------------------------------------------------
def debug_dir():
    d = os.path.join(_profile_dir(), 'debug')
    try:
        if not xbmcvfs.exists(d + os.sep):
            xbmcvfs.mkdirs(d)
    except Exception:  # noqa
        pass
    return d


def save_debug(name, text):
    """Oldal mentése az addon_data/<id>/debug mappába (jelszó/süti NEM kerül bele)."""
    try:
        name = re.sub(r'[^A-Za-z0-9._-]+', '_', name)[:120]
        p = os.path.join(debug_dir(), name)
        f = xbmcvfs.File(p, 'w')
        try:
            f.write(text or '')
        finally:
            f.close()
        log('Hibakereső mentés: %s' % p)
        return p
    except Exception as exc:  # noqa
        log('debug mentés hiba: %s' % exc, xbmc.LOGWARNING)
        return ''


# ---------------------------------------------------------------------------
# Sport: kategóriák -> gyűjtemények -> adások
#   /sport/collections                     (sport-cat blokkok, league-card linkek)
#   /sport/collection/details/<slug>       (egy gyűjtemény adásai)
#   /sport/watch/<slug>                    (lejátszó oldal)
# ---------------------------------------------------------------------------
_SLUG = r'([A-Za-z0-9._~%-]+)'
KIND_COLLECTION = 'sport/collection/details/'
KIND_WATCH = 'sport/watch/'


def _link_re(kind):
    return re.compile(r'(?:https?://[^"\'\s<>]*?)?/' + re.escape(kind) + _SLUG)


def parse_links(html, kind=KIND_WATCH):
    """A <kind><slug> linkek kigyűjtése címmel és képpel.
    Visszaad: [{'slug', 'title', 'art'}], oldal-sorrendben, egyedi slug-okkal."""
    out, seen = [], {}
    text = html or ''
    lre = _link_re(kind)
    for m in re.finditer(r'<a\b([^>]*href\s*=\s*["\'][^"\']*/' + re.escape(kind) +
                         r'[^"\']+["\'][^>]*)>(.*?)</a>(?=(.{0,600}))', text, re.DOTALL | re.I):
        attrs, inner, after = m.group(1), m.group(2), m.group(3)
        sm = lre.search(_attr(attrs, 'href'))
        if not sm:
            continue
        # a league-card neve az <a> UTÁN áll: <div class="league-card__name">NFL</div>
        nm = re.search(r'^\s*(?:<[^a][^>]*>\s*)*?<div class="[^"]*__name">(.*?)</div>',
                       after, re.DOTALL)
        title = (_unent(_attr(attrs, 'title')) or _unent(_attr(attrs, 'aria-label'))
                 or _heading(inner) or _named(inner) or (_txt(nm.group(1)) if nm else '')
                 or _unent(_attr(inner, 'alt')) or _txt(inner))
        img = (_attr(inner, 'src') or _attr(inner, 'data-src')
               or _first_srcset(_attr(inner, 'srcset')))
        m2 = re.search(r'background-image\s*:\s*url\(([^)]+)\)', inner + attrs, re.I)
        if not img and m2:
            img = m2.group(1).strip('\'" ')
        _merge(out, seen, sm.group(1), title, img)
    # JSON/JS-be ágyazott linkek (Alpine/Livewire adatok)
    for m in lre.finditer(_unescape_js(text)):
        _merge(out, seen, m.group(1), '', '')
    for it in out:
        if not it['title']:
            it['title'] = _pretty_slug(it['slug'])
    return out


def _named(inner):
    """Kártya-cím a szokásos BEM-osztályokból (…__name / …__title)."""
    m = re.search(r'class="[^"]*__(?:name|title)[^"]*"[^>]*>(.*?)</', inner or '', re.DOTALL)
    return _txt(m.group(1)) if m else ''


def _heading(inner):
    m = re.search(r'<h[1-6][^>]*>(.*?)</h[1-6]>', inner or '', re.DOTALL | re.I)
    return _txt(m.group(1)) if m else ''


def _first_srcset(srcset):
    return (srcset or '').split(',')[0].strip().split(' ')[0] if srcset else ''


def _merge(out, seen, slug, title, img):
    title = (title or '').strip()
    if len(title) > 140:
        title = title[:140].rsplit(' ', 1)[0] + '…'
    if slug in seen:
        it = seen[slug]
        if title and (not it['title'] or len(title) > len(it['title'])):
            it['title'] = title
        if img and not it['art']:
            it['art'] = _abs(_unent(img))
        return
    it = {'slug': slug, 'title': title, 'art': _abs(_unent(img)) if img else None}
    seen[slug] = it
    out.append(it)


def parse_categories(html):
    """A /sport/collections oldal blokkjai: [(cím, [gyűjtemények])].
    'Kiemelt sportok' + minden <div class="sport-cat" aria-label="..."> blokk."""
    text = html or ''
    cats = []
    heads = [(m.start(), _txt(m.group(1)))
             for m in re.finditer(r'<h3 class="sport-cat__title">(.*?)<span', text, re.DOTALL)]
    feat = re.search(r'<h2 class="section-title">\s*Kiemelt[^<]*</h2>', text)
    allh = re.search(r'<h2 class="section-title">\s*Összes[^<]*</h2>', text)
    if feat:
        end = allh.start() if allh and allh.start() > feat.end() else (
            heads[0][0] if heads else len(text))
        items = parse_links(text[feat.end():end], KIND_COLLECTION)
        if items:
            cats.append((_txt(feat.group(0)), items))
    for i, (pos, name) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else len(text)
        items = parse_links(text[pos:end], KIND_COLLECTION)
        if items:
            cats.append((name, items))
    return cats


def collections_page():
    html = get('sport/collections')
    cats = parse_categories(html)
    if not cats and html:
        save_debug('list_sport_collections.html', html)
    return cats


def collection_items(slug):
    """Egy gyűjtemény oldala: (adások [watch], al-gyűjtemények)."""
    path = KIND_COLLECTION + slug
    html = get(path)
    watch = parse_links(html, KIND_WATCH)
    subs = [c for c in parse_links(html, KIND_COLLECTION) if c['slug'] != slug]
    if not watch and html:
        save_debug('collection_%s.html' % slug, html)
    return watch, subs


def page_items(path):
    """Tetszőleges oldal (pl. /sport/epg, /sport) watch-linkjei."""
    html = get(path)
    items = parse_links(html, KIND_WATCH)
    if not items and html:
        save_debug('list_%s.html' % path.strip('/').replace('/', '_'), html)
    return items


# ---------------------------------------------------------------------------
# Stream-kinyerés
# ---------------------------------------------------------------------------
_URL_CHARS = r'[^\s"\'<>\\]'
_MPD_RE = re.compile(r'https?://' + _URL_CHARS + r'+?\.mpd(?:\?' + _URL_CHARS + r'*)?', re.I)
_M3U8_RE = re.compile(r'https?://' + _URL_CHARS + r'+?\.m3u8(?:\?' + _URL_CHARS + r'*)?', re.I)
_LIC_RE = re.compile(r'https?://' + _URL_CHARS + r'*(?:widevine|/wv(?=[/?"\']|$)|'
                     r'license|licence|drm)' + _URL_CHARS + r'*', re.I)
_WV_RE = re.compile(r'widevine["\']?\s*:\s*\{[^}]*?licenseAcquisitionURL["\']?\s*:\s*'
                    r'["\'](https?://[^"\']+)["\']', re.I)
_CID_RE = re.compile(r'["\']?(?:cid|uplynk_?cid|embed_?code|asset_?id)["\']?\s*[:=]\s*'
                     r'["\']([0-9a-f]{32})["\']', re.I)


def find_streams(text):
    """Visszaad: {'mpd': [..], 'hls': [..], 'license': [..], 'cid': [..]}.
    Az Uplynk (content.uplynk.com) manifest kerül előre."""
    t = _unescape_js(text)
    mpd = _uniq(_MPD_RE.findall(t))
    hls = _uniq(_M3U8_RE.findall(t))
    lic = [u for u in _uniq(_LIC_RE.findall(t))
           if 'theoplayer.com' not in u and not re.search(r'\.(?:js|css|png|jpe?g|svg|mpd|m3u8)(?:\?|$)', u)]
    cid = _uniq(_CID_RE.findall(t))
    # THEOplayer: contentProtection: { widevine: { licenseAcquisitionURL: "..." } }
    wv = _uniq(_WV_RE.findall(t))
    lic = wv + [u for u in lic if u not in wv]
    key = lambda u: (0 if 'uplynk.com' in u else 1)
    return {'mpd': sorted(mpd, key=key), 'hls': sorted(hls, key=key),
            'license': lic, 'cid': cid}


def _uniq(seq):
    out = []
    for s in seq:
        s = s.rstrip('.,;)')
        if s not in out:
            out.append(s)
    return out


_API_HINT_RE = re.compile(r'["\'](/(?:api/)?[A-Za-z0-9_/.-]*(?:stream|play|video|source|manifest|'
                          r'token|uplynk|drm)[A-Za-z0-9_/.-]*(?:\?[^"\'<>\s]*)?)["\']', re.I)


def _api_candidates(html):
    out = []
    for p in _API_HINT_RE.findall(_unescape_js(html)):
        if re.search(r'\.(?:js|css|png|jpe?g|svg|webp|avif|woff2?)(?:\?|$)', p):
            continue
        if p not in out:
            out.append(p)
    return out[:6]


def details_title(html):
    """Cím: a chromecastSource metadata.title (a <title> csak 'Network4 Online')."""
    m = re.search(r'metadata\s*:\s*\{\s*title\s*:\s*"((?:[^"\\]|\\.)*)"', html or '')
    if m:
        return _unescape_js(m.group(1)).strip()
    m = (re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)', html or '')
         or re.search(r'<title>(.*?)</title>', html or '', re.DOTALL | re.I))
    t = _txt(m.group(1)) if m else ''
    t = re.sub(r'\s*[|\-–]?\s*Network4( Online)?.*$', '', t, flags=re.I).strip()
    return t


def details_poster(html):
    m = (re.search(r'player\.poster\s*=\s*"([^"]+)"', html or '')
         or re.search(r'\bposter\s*:\s*"([^"]+)"', html or ''))
    if m:
        return _abs(_unescape_js(m.group(1)))
    m = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)', html or '')
    u = _abs(_unent(m.group(1))) if m else None
    return None if (u and 'marshmallow.dev' in u) else u


def resolve(slug_or_url):
    """A details oldalból a lejátszható stream. Visszaad dict-et:
        {'manifest', 'type': 'mpd'|'hls', 'license', 'title', 'poster', 'referer', 'debug'}
    vagy {'error': ..., 'debug': mentett fájl}."""
    s = (slug_or_url or '').strip()
    if s.startswith('http'):
        page_url = s
    elif '/' in s.strip('/'):
        page_url = urljoin(base_url(), s.lstrip('/'))
    else:
        page_url = urljoin(base_url(), KIND_WATCH + s)
    slug = page_url.rstrip('/').split('/')[-1]
    html = get(page_url)
    if not html:
        return {'error': 'Az oldal nem töltődött be.'}
    if not logged_in(html):
        p = save_debug('watch_%s.html' % slug, html)
        return {'error': 'Nincs bejelentkezve (email/jelszó?).', 'debug': p}
    found = find_streams(html)
    sources = ['details HTML']
    if not found['mpd'] and not found['hls']:
        us_raw = get('user-session', referer=page_url, ajax=True)
        f2 = find_streams(us_raw)
        sources.append('user-session')
        for k in found:
            found[k] += [x for x in f2[k] if x not in found[k]]
        if not found['mpd'] and not found['hls']:
            for ep in _api_candidates(html):
                raw = get(ep, referer=page_url, ajax=True)
                sources.append(ep)
                f3 = find_streams(raw)
                for k in found:
                    found[k] += [x for x in f3[k] if x not in found[k]]
                if found['mpd'] or found['hls']:
                    break
        if not found['mpd'] and not found['hls']:
            p = save_debug('watch_%s.html' % slug, html)
            if us_raw:
                save_debug('user-session_%s.json' % slug, us_raw)
            log('Nincs manifest. Átnézett források: %s; cid: %s'
                % (', '.join(sources), ', '.join(found['cid']) or '-'), xbmc.LOGWARNING)
            return {'error': 'Nem találtam lejátszható manifestet az oldalon.', 'debug': p,
                    'cid': found['cid']}
    lic_setting = (ADDON.getSetting('license_url') or '').strip()
    if found['mpd']:
        manifest, mtype = found['mpd'][0], 'mpd'
    else:
        manifest, mtype = found['hls'][0], 'hls'
    lic = lic_setting or (found['license'][0] if found['license'] else '')
    if not lic and 'uplynk.com' in manifest:
        lic = DEFAULT_LICENSE
    if ADDON.getSetting('debug') == 'true':
        save_debug('watch_%s.html' % slug, html)
    log('Manifest (%s): %s | licenc: %s' % (mtype, manifest, lic or '-'))
    return {'manifest': manifest, 'type': mtype, 'license': lic,
            'title': details_title(html) or _pretty_slug(slug),
            'poster': details_poster(html), 'referer': page_url}


def play_headers(referer=None):
    """Kodi/IA fejléc-string (a manifesthez és a licenchez)."""
    h = {'User-Agent': user_agent(), 'Referer': referer or base_url(), 'Origin': _origin()}
    return '&'.join('%s=%s' % (k, quote(v, safe='')) for k, v in h.items())
