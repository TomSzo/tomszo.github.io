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


def get(url, referer=None, timeout=25, ajax=False):
    url = urljoin(base_url(), url)
    log('GET %s' % url)
    try:
        r = _SESSION.get(url, headers=_headers(referer, ajax=ajax),
                         cookies=_cookies(), timeout=timeout)
        r.encoding = 'utf-8'  # magyaranime UTF-8; a talalgatas elrontja az ekezeteket
        return r.text
    except Exception as exc:  # noqa
        log('GET hiba: %s (%s)' % (exc, url), xbmc.LOGERROR)
        return ''


def post(url, data, referer=None, timeout=30, ajax=True):
    url = urljoin(base_url(), url)
    log('POST %s data=%s' % (url, data))
    try:
        r = _SESSION.post(url, data=data, headers=_headers(referer, ajax=ajax),
                          cookies=_cookies(), timeout=timeout)
        r.encoding = 'utf-8'  # magyaranime UTF-8; a talalgatas elrontja az ekezeteket
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


def _search_index():
    """A teljes anime-index JSON-ja (ugyanaz, amit az oldal fejléc-keresője használ)."""
    txt = get('data/search/data_search.php', referer=base_url() + 'web/kereso/', ajax=True)
    if not txt:
        log('data_search.php üres válasz', xbmc.LOGWARNING)
        return []
    try:
        data = json.loads(txt)
    except ValueError:
        log('data_search.php nem JSON (%d byte, részlet): %s' % (len(txt), txt[:200]),
            xbmc.LOGWARNING)
        return []
    if isinstance(data, dict):
        data = data.get('data') or data.get('aaData') or list(data.values())
    if not isinstance(data, list) or not data:
        log('data_search.php index üres/ismeretlen (%d byte, részlet): %s'
            % (len(txt), txt[:200]), xbmc.LOGWARNING)
        return []
    log('anime-index betöltve: %d elem' % len(data))
    return data


def _poster(aid):
    return urljoin(base_url(), '_public/images_v2/boritokepek/%s.webp' % aid)


def search(term):
    """Keresés az anime-indexben (cím / japán / szinonim / egyéb). Visszaad: [{aid,title,art}]."""
    term = (term or '').strip().lower()
    if not term:
        return []
    results = []
    seen = set()
    for it in _search_index():
        if not isinstance(it, dict):
            continue
        aid = str(it.get('id') or '').strip()
        if not aid or aid in seen:
            continue
        fields = (it.get('name'), it.get('name_jap'), it.get('name_syn'),
                  it.get('name_other'), it.get('myanimelist'))
        if any(f and term in str(f).lower() for f in fields):
            title = _clean(it.get('name') or it.get('name_jap') or ('anime %s' % aid))
            seen.add(aid)
            results.append({'aid': aid, 'title': title, 'art': _poster(aid)})
    log('%d keresési találat (index): "%s"' % (len(results), term))
    return results[:300]


# ---------------------------------------------------------------------------
# Adatlapok (böngészés / katalógus)
# ---------------------------------------------------------------------------
_CAT_CARD_RE = re.compile(
    r"window\.open\('leiras/(\d+)/[^)]*\)[^>]*>\s*"
    r'<img[^>]+src="([^"]+)"[^>]*>.*?'
    r'<div class="movie-title">\s*(.*?)\s*</div>',
    re.DOTALL | re.IGNORECASE)
_CAT_PAGES_RE = re.compile(r'Jelenlegi oldal:\s*</b>\s*(\d+)\s*/\s*(\d+)', re.IGNORECASE)

# Az adatlapok űrlap alapértelmezései (a böngészőben is ez a kiindulás).
CATALOG_DEFAULTS = {'allapot': '1', 'szezon': '1', 'besorolas': '1',
                    'rendezes': '1', 'kezdo': 'az'}


def catalog(page=1, filters=None):
    """Anime-katalógus egy oldala. Visszaad: {'items':[{aid,title,art}], 'page', 'pages'}."""
    page = max(1, int(page or 1))
    data = dict(CATALOG_DEFAULTS)
    if filters:
        data.update(filters)
    ref = base_url() + 'anime/adatlapok/'
    if page <= 1 and not filters:
        html = get('anime/adatlapok/', referer=base_url())
    else:
        data['page'] = str(page)
        html = post('anime/adatlapok/', data, referer=ref, ajax=False)
    items = []
    seen = set()
    for aid, art, title in _CAT_CARD_RE.findall(html or ''):
        if aid in seen:
            continue
        seen.add(aid)
        art = art if art.startswith('http') else urljoin(base_url(), art)
        items.append({'aid': aid, 'title': _clean(title), 'art': art})
    pm = _CAT_PAGES_RE.search(html or '')
    pages = int(pm.group(2)) if pm else 1
    log('%d adatlap (oldal %d/%d)' % (len(items), page, pages))
    return {'items': items, 'page': page, 'pages': pages}


_CAT_SELECT_RE = re.compile(
    r'<select name="(allapot|szezon|besorolas|rendezes|kezdo)"[^>]*>(.*?)</select>',
    re.DOTALL | re.IGNORECASE)
_CAT_OPTION_RE = re.compile(r'<option value="([^"]*)"[^>]*>\s*(.*?)\s*</option>',
                            re.DOTALL | re.IGNORECASE)


def catalog_filters():
    """A katalógus-oldal szűrő-legördülőinek opciói: {name: [(value, label), ...]}."""
    html = get('anime/adatlapok/', referer=base_url())
    out = {}
    for name, block in _CAT_SELECT_RE.findall(html or ''):
        opts = []
        for value, label in _CAT_OPTION_RE.findall(block):
            label = _clean(label)
            if value != '' and label:
                opts.append((value, label))
        if opts:
            out[name] = opts
    return out


_EP_TITLE_RE = re.compile(r'<a href="resz/(\d+)/"\s+oncontextmenu="return false;">([^<]+)</a>',
                          re.IGNORECASE)
_EP_THUMB_DATASRC_RE = re.compile(
    r"window\.location='resz/(\d+)/';\"[^>]*>\s*<img[^>]*?\bdata-src=\"([^\"]+)\"",
    re.IGNORECASE)
_EP_THUMB_SRC_RE = re.compile(
    r"window\.location='resz/(\d+)/';\"[^>]*>\s*<img(?![^>]*\bdata-src)[^>]*?\bsrc=\"([^\"]+)\"",
    re.IGNORECASE)


# Egy epizód "filler" jelölése (Filler / Half-Filler / Canon) a cím utáni badge-ből.
_EP_FILLER_RE = re.compile(
    r'<a href="resz/(\d+)/"\s+oncontextmenu="return false;">[^<]*</a>(.*?)</h3>',
    re.DOTALL | re.IGNORECASE)
# Az anime ismertetője (leírás) az adatlapon.
_DESC_RE = re.compile(r'<div class="leiras_text"[^>]*>(.*?)</div>', re.DOTALL | re.IGNORECASE)


def _plot_text(fragment):
    """A leiras_text HTML-jét olvasható szöveggé alakítja (a <br>-ekből sortörés)."""
    t = re.sub(r'(?i)<\s*br\s*/?>', '\n', fragment or '')
    t = re.sub(r'(?i)<b>\s*Ismertető:\s*</b>\s*', '', t)
    t = re.sub(r'<[^>]+>', '', t)
    for a, b in (('&amp;', '&'), ('&#039;', "'"), ('&quot;', '"'), ('&nbsp;', ' '),
                 ('&lt;', '<'), ('&gt;', '>')):
        t = t.replace(a, b)
    t = re.sub(r'[ \t]+\n', '\n', t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip()


def _collect_ep_window(html):
    """Egy adatlap-ablak nyers epizód-jelöltjei: [(vid, epnum, thumb, title, filler)].

    FONTOS: a rész SORSZÁMA a CÍMBŐL jön ("N. rész"), NEM a bélyegkép nevéből - mert
    egyes animék bélyegképe indavideo-URL (pics.indavideo.hu/.../5-1.jpg), amiben nincs
    epizódszám. A cím-link (resz/<vid> -> "N. rész") viszont mindig megvan.
    A 'filler' a rész típusa (Filler / Half-Filler / Canon), ha az oldal jelöli."""
    # bélyegképek vid szerint: elsőként a valódi data-src, majd (ha nincs) a sima src
    thumbs = {}
    for vid, thumb in _EP_THUMB_DATASRC_RE.findall(html):
        thumbs.setdefault(vid, thumb)
    for vid, thumb in _EP_THUMB_SRC_RE.findall(html):
        thumbs.setdefault(vid, thumb)
    # filler-jelölés vid szerint (csak a valódi filler/canon badge-ek)
    fillers = {}
    for vid, tail in _EP_FILLER_RE.findall(html):
        bm = re.search(r'badge bg-\w+">([^<]+)</span>', tail)
        if bm:
            b = _clean(bm.group(1))
            if 'filler' in b.lower() or 'canon' in b.lower():
                fillers.setdefault(vid, b)
    out = []
    for vid, ttext in _EP_TITLE_RE.findall(html):
        t = _clean(ttext)
        mnum = re.search(r'(\d+)', t)
        if not mnum:
            continue  # pl. "Film"/"OVA" felirat szám nélkül - kihagyjuk
        out.append((vid, int(mnum.group(1)), thumbs.get(vid), t, fillers.get(vid)))
    return out


def anime_info(aid):
    """Az anime adatlap-fejléce a textviewerhez: {title, plot, meta}."""
    html = get('leiras/%s/' % aid, referer=base_url())
    if not html:
        return {'title': '', 'plot': '', 'meta': ''}
    tm = re.search(r'<h2 class="gen-title[^"]*">([^<]+)</h2>', html)
    title = _clean(tm.group(1)) if tm else ''
    dm = _DESC_RE.search(html)
    plot = _plot_text(dm.group(1)) if dm else ''
    lines = []
    em = re.search(r'Epizódok:\s*([0-9]+\s*/\s*[0-9]+)', html)
    if em:
        lines.append('Epizódok: %s' % re.sub(r'\s+', '', em.group(1)))
    sm = re.search(r'>\s*(\d{4}\s+(?:Tavasz|Nyár|Ősz|Tél))\s*<', html)
    if sm:
        lines.append('Évad: %s' % sm.group(1))
    pgm = re.search(r'<span>\s*((?:PG-\d+|R\+?|G|NC-17|R-17\+?|PG)\b[^<]*)</span>', html)
    if pgm:
        lines.append('Korhatár: %s' % _clean(pgm.group(1)))
    malm = re.search(r'MAL:\s*<span>([^<]+)</span>', html)
    if malm:
        lines.append('MAL: %s' % _clean(malm.group(1)))
    mam = re.search(r'MA:\s*<span>([^<]+)</span>', html)
    if mam:
        lines.append('MA: %s' % _clean(mam.group(1)))
    return {'title': title, 'plot': plot, 'meta': '\n'.join(lines)}


def episodes_of_anime(aid):
    """Egy anime ÖSSZES része az adatlapról. Az adatlap ~26-os ablakot mutat, ezért a
    'epizod_szam' POST-tal végiglapozzuk a hiányzó epizódszámokat.

    A TISZTA AJAX-ablakok (epizod_szam POST) az elsődleges forrás: ezekben CSAK az adott
    anime részei vannak, nincs 'kapcsolódó animék' idegen szekció. A nyitóoldalt és a
    rész-oldal listáját csak végső esetben használjuk."""
    html = get('leiras/%s/' % aid, referer=base_url())
    if not html:
        return {'title': '', 'episodes': []}
    tm = re.search(r'<h2 class="gen-title[^"]*">([^<]+)</h2>', html)
    title = _clean(tm.group(1)) if tm else ''
    mx = re.search(r'id="epizod_szam"[^>]*data-max="(\d+)"', html)
    max_ep = int(mx.group(1)) if mx else 0
    csrf_m = _META_CSRF_RE.search(html)
    csrf = csrf_m.group(1) if csrf_m else ''
    referer = base_url() + 'leiras/%s/' % aid

    # Az anime ismertetője (a részekhez plot-ként is odaadjuk).
    dm = _DESC_RE.search(html)
    plot = _plot_text(dm.group(1)) if dm else ''

    acc = {}

    def _add(cands):
        for vid, epnum, thumb, ep_title, filler in cands:
            if epnum in acc:
                continue
            acc[epnum] = {'vid': vid, 'title': ep_title or ('%d. rész' % epnum),
                          'thumb': urljoin(base_url(), thumb) if thumb else None,
                          'server': 's1', 'filler': filler, 'plot': plot}

    def _window(center):
        html2 = post('leiras/%s/' % aid,
                     {'epizod_szam': str(center), 'csrf_token': csrf},
                     referer=referer, ajax=False)
        if html2:
            _add(_collect_ep_window(html2))

    # Az ablak: epizod_szam=N -> [N-9 .. N+16] (26 rész). N=need+9-cel az ablak a 'need'
    # résznél kezdődik; 26-os lépéssel hézagmentesen csempézünk.
    top = max_ep or 100000
    need, guard = 1, 0
    while need <= top and guard < 80:
        guard += 1
        before = len(acc)
        _window(need + 9)
        if not max_ep and len(acc) == before:
            break  # ismeretlen max: állj le, amint egy ablak semmit sem ad
        need += 26

    # Hézag-kitöltés CSAK ha már van eredmény és tényleg hiányzik rész (nem pörgünk üresen).
    if max_ep and acc:
        g = 0
        for e in [n for n in range(1, max_ep + 1) if n not in acc]:
            if g >= 15:
                break
            g += 1
            _window(e + 9)

    # Ha az ablakok semmit sem adtak: a nyitóoldal, majd a rész-oldal (idegen rész kiszűrve).
    if not acc:
        _add(_collect_ep_window(html))
    if not acc:
        m = _RESZ_RE.search(html)
        if m:
            return episodes_of_resz(m.group(1), limit=max_ep or None)

    eps = [acc[n] for n in sorted(acc) if not max_ep or n <= max_ep]
    log('%d rész (adatlap, max %s): leiras/%s ("%s")' % (len(eps), max_ep or '?', aid, title))
    return {'title': title, 'plot': plot, 'episodes': eps}


def anime_id_of_resz(vid):
    """Egy rész (resz/{vid}) alapján az anime adatlap-azonosítója (leiras/{aid})."""
    html = get('resz/%s/' % vid, referer=base_url())
    if not html:
        return None
    m = re.search(r'id="InfoBox".*?leiras/(\d+)/', html, re.DOTALL)
    if m:
        return m.group(1)
    m = _LEIRAS_RE.search(html)
    return m.group(1) if m else None


def episodes_of_resz(vid, limit=None):
    """A /resz/{vid}/ oldal epizódlistája + anime cím.

    A rész-oldal a saját epizódok UTÁN idegen ('kapcsolódó animék') részeket is
    felsorolhat (a lista végén). Ha 'limit' meg van adva (pl. az adatlap data-max
    értéke), csak az első 'limit' részt adjuk vissza - így az idegen rész kimarad."""
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
    note = ''
    if limit and limit > 0:
        if len(episodes) > limit:
            episodes = episodes[:limit]
            note = ' [max %d-re vagva]' % limit
    else:
        # Nincs megbizhato max: ha a rész-sorszámok UJRAINDULNAK (pl. 9 -> 1), ott
        # kezdodik az idegen ('kapcsolódó') blokk, ezert addig vagunk.
        prev, cut = None, None
        for i, ep in enumerate(episodes):
            mnum = re.match(r'\s*(\d+)', ep.get('title') or '')
            n = int(mnum.group(1)) if mnum else None
            if n is None:
                prev = None
                continue
            if prev is not None and n <= prev:
                cut = i
                break
            prev = n
        if cut:
            episodes = episodes[:cut]
            note = ' [ujrainduló sorszámnál vagva: %d]' % cut
    log('%d rész: resz/%s ("%s")%s' % (len(episodes), vid, title, note))
    return {'title': title, 'episodes': episodes, 'html': html}


# ---------------------------------------------------------------------------
# Lejátszás
# ---------------------------------------------------------------------------
_MP4_RE = re.compile(r'https?:\\?/\\?/[^"\'\s<>]+?\.mp4[^"\'\s<>]*', re.IGNORECASE)
_SRC_RE = re.compile(r'<source[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
_IFRAME_RE = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)


def _unescape_url(u):
    return (u or '').replace('\\/', '/').replace('&amp;', '&')


# ---------------------------------------------------------------------------
# Napi forrás-lekérés számláló (helyi)
# A magyaranime a data_player.php HÍVÁSOKAT számolja a napi limitbe (nem a
# lejátszásokat). Ezért minden data_player.php kérésnél +1-et számolunk helyben.
# Naponta nullázódik. NINCS plusz kérés – csak a meglévő hívásokat számoljuk.
# ---------------------------------------------------------------------------
def _daily_limit_path():
    prof = ADDON.getAddonInfo('profile')
    try:
        if not xbmcvfs.exists(prof):
            xbmcvfs.mkdirs(prof)
    except Exception:  # noqa
        pass
    return prof.rstrip('/') + '/daily_limit.json'


def load_daily_limit():
    """Visszaad: {'date','count','ts'} vagy None."""
    try:
        p = _daily_limit_path()
        if not xbmcvfs.exists(p):
            return None
        f = xbmcvfs.File(p)
        try:
            raw = f.read()
        finally:
            f.close()
        return json.loads(raw) if raw else None
    except Exception:  # noqa
        return None


def today_count():
    """A MAI forrás-lekérések száma (ha a mentett dátum nem ma, akkor 0)."""
    import datetime
    d = load_daily_limit() or {}
    if d.get('date') == datetime.date.today().isoformat():
        return int(d.get('count', 0))
    return 0


def bump_request_count():
    """Egy data_player.php kérés megtörtént -> +1 a mai számlálóhoz."""
    import time as _time
    import datetime
    today = datetime.date.today().isoformat()
    d = load_daily_limit() or {}
    if d.get('date') != today:
        d = {'date': today, 'count': 0}
    d['count'] = int(d.get('count', 0)) + 1
    d['ts'] = int(_time.time())
    try:
        f = xbmcvfs.File(_daily_limit_path(), 'w')
        try:
            f.write(json.dumps(d))
        finally:
            f.close()
    except Exception as exc:  # noqa
        log('napi számláló mentés hiba: %s' % exc, xbmc.LOGWARNING)
    log('Napi forrás-lekérés (helyi): %d' % d['count'])
    return d['count']


def player_data(server, vid, csrf, referer):
    txt = post('data/lejatszo/data_player.php',
               {'server': server, 'vid': vid, 'csrf_token': csrf}, referer=referer)
    if not txt:
        return None
    # A kérés elérte a szervert -> ez beleszámít a napi limitbe. Helyi +1.
    bump_request_count()
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
            err = str(data.get('error'))
            log('data_player error (%s): %s' % (server, err), xbmc.LOGWARNING)
            # Napi limit: MINDEN szerver ugyanezt adja, ezért NE pörgessük tovább
            # (különben feleslegesen tovább terheljük a limitet). Jelezzük a hívónak.
            if 'limit' in err.lower():
                result['limit_error'] = err
                return result
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
            if 'mega.nz' in low or 'mega.co.nz' in low:
                result['mega'] = True
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


_HOSTS = ('indavideo', 'videa', 'mega.nz', 'mega.co.nz', 'dailymotion', 'streamtape',
          'doodstream', 'dood', 'mp4upload', 'rumble', 'ok.ru', 'vk.com', 'sibnet',
          'youtube', 'streamsb', 'filemoon', 'vidoza', 'voe')


def _host_of(url):
    u = (url or '').lower()
    for h in _HOSTS:
        if h in u:
            return h.replace('.nz', '').replace('.co', '').replace('.ru', '').replace('.com', '')
    m = re.search(r'https?://([^/]+)/', url or '')
    return (m.group(1) if m else 'ismeretlen')


# Felbontás-kinyerés a forrás URL-jéből / a player kimenetéből.
_RES_P_RE = re.compile(r'(?<!\d)(\d{3,4})\s*[pP](?![a-z])')      # "720p", "1080p"
_RES_WH_RE = re.compile(r'(\d{3,4})\s*[xX]\s*(\d{3,4})')          # "1280x720"


def _quality_label(text):
    """Egy szövegből (URL/output) kiolvasott felbontás, pl. '1080p' - vagy '' ha nincs."""
    if not text:
        return ''
    m = _RES_P_RE.search(text)
    if m and 144 <= int(m.group(1)) <= 4320:
        return '%sp' % m.group(1)
    # magyaranime MP4: ...nev.720.mp4 (szam kozvetlenul a kiterjesztes elott, 'p' nelkul)
    m = re.search(r'\.(\d{3,4})\.(?:mp4|mkv|webm|m3u8)', text, re.IGNORECASE)
    if m and 144 <= int(m.group(1)) <= 4320:
        return '%sp' % m.group(1)
    m = _RES_WH_RE.search(text)
    if m:
        return '%sp' % m.group(2)  # a magasság a felbontás
    return ''


def _hq_to_res(hq):
    """A data_player 'hq' mezoje -> felbontas, pl. 'hq720' -> '720p'. Ures, ha nincs szam."""
    m = re.search(r'(\d{3,4})', hq or '')
    return ('%sp' % m.group(1)) if m else ''


def _hls_qualities(hls_url, referer):
    """Egy HLS master manifest elérhető felbontásai csökkenő sorrendben, pl.
    ['1080p','720p','480p']. Ha csak egy (média-)lista, üres marad."""
    try:
        txt = get(hls_url, referer=referer)
    except Exception:  # noqa
        return []
    heights = set()
    for m in re.finditer(r'RESOLUTION=\d+x(\d+)', txt or '', re.IGNORECASE):
        heights.add(int(m.group(1)))
    return ['%dp' % h for h in sorted(heights, reverse=True)]


def _classify(data, referer):
    """Egy data_player.php válaszból: (kind, host, quality). Nem hív extra data_player-t."""
    if data.get('hls') and data.get('hls_url'):
        try:
            hls = base64.b64decode(data['hls_url']).decode('utf-8', 'replace')
        except Exception:  # noqa
            hls = ''
        q = '/'.join(_hls_qualities(hls, referer)) if hls else ''
        return 'hls', 'Közvetlen (HLS)', q
    output = data.get('output') or ''
    urls, iframes = _extract_from_output(output)
    mp4 = [u for u in urls if '.mp4' in u.lower()]
    if mp4:
        return 'mp4', 'Közvetlen (MP4)', _quality_label(mp4[0])
    if iframes:
        return 'embed', _host_of(iframes[0]), _quality_label(iframes[0])
    return None, None, ''


def list_servers(vid):
    """Egy részhez elérhető szerverek/források listája: [{server, host, kind, embed, quality}].

    FONTOS (napi limit!): a magyaranime napi videó-lejátszási limitet számol, és minden
    data_player.php hívás beleszámíthat. Ezért itt MINDÖSSZE EGY data_player.php hívást
    teszünk (a default szerverre), a többi szervert a válasz 'servers' tömbjéből listázzuk
    (nevek + minőség a 'hq'-ból), külön lekérdezés NÉLKÜL. A tényleges feloldás csak akkor
    fut, amikor a felhasználó ténylegesen elindít egy forrást."""
    out = []
    page = get('resz/%s/' % vid, referer=base_url())
    if not page:
        return out
    csrf_m = _META_CSRF_RE.search(page)
    csrf = csrf_m.group(1) if csrf_m else ''
    dv = re.search(r'id="VideoPlayer"[^>]*data-server="([^"]*)"', page)
    default_server = dv.group(1) if dv else 's1'
    referer = base_url() + 'resz/%s/' % vid

    # AZ EGYETLEN data_player.php hívás.
    data = player_data(default_server, vid, csrf, referer)
    if not data:
        return out
    def_kind, def_host, def_q = _classify(data, referer)

    servers = data.get('servers') if isinstance(data.get('servers'), list) else []
    hq = {}
    titles = {}
    order_ids = []
    for s in servers:
        sid = s.get('server')
        if sid and sid not in order_ids:
            order_ids.append(sid)
            hq[sid] = _hq_to_res(s.get('hq'))
            titles[sid] = _clean(s.get('title') or '')

    seen = set()
    # A default szerver elöl, a TÉNYLEGES típusával/minőségével (ezt már ismerjük).
    if def_kind:
        out.append({'server': default_server, 'host': def_host, 'kind': def_kind,
                    'embed': None, 'quality': def_q or hq.get(default_server, '')})
        seen.add(default_server)
    # A többi valós szerver a 'servers' tömbből - extra hívás nélkül (nevek + minőség).
    for sid in order_ids:
        if sid in seen:
            continue
        seen.add(sid)
        out.append({'server': sid, 'host': titles.get(sid) or ('Szerver %s' % sid),
                    'kind': 'server', 'embed': None, 'quality': hq.get(sid, '')})
    log('list_servers(%s): %d forrás (1 data_player hívás)' % (vid, len(out)))
    return out


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


def _embed_variants(url):
    """Néhány beágyazott URL-t át kell írni, hogy a ResolveURL felismerje.
    Pl. a mega.nz 'embed' formátumát a ResolveURL a '/file/' alakban ismeri."""
    variants = [url]
    low = url.lower()
    if 'mega' in low and '/embed/' in low:
        # https://mega.nz/embed/{id}#{kulcs} -> https://mega.nz/file/{id}#{kulcs}
        variants.insert(0, re.sub(r'/embed/', '/file/', url, count=1))
        # klasszikus alak is: https://mega.nz/#!{id}!{kulcs}
        m = re.search(r'/embed/([0-9A-Za-z_-]+)#([0-9A-Za-z_-]+)', url)
        if m:
            variants.append('https://mega.nz/#!%s!%s' % (m.group(1), m.group(2)))
    return variants


def resolve_via_module(url):
    """Beágyazott lejátszó (mega, videa, indavideo, stb.) feloldása a telepített modullal."""
    mod = None
    try:
        import resolveurl as mod
    except ImportError:
        try:
            import urlresolver as mod
        except ImportError:
            log('Nincs ResolveURL/URLResolver – nem feloldható: %s' % url, xbmc.LOGWARNING)
            return None
    for u in _embed_variants(url):
        try:
            hmf = mod.HostedMediaFile(u)
            if hmf and hmf.valid_url():
                res = hmf.resolve()
                if res:
                    log('ResolveURL feloldva (%s): %s' % (u, res))
                    return res
        except Exception as exc:  # noqa
            log('ResolveURL hiba (%s): %s' % (u, exc), xbmc.LOGWARNING)
    log('ResolveURL nem tudta feloldani: %s' % url, xbmc.LOGWARNING)
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
