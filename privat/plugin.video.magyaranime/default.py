# -*- coding: utf-8 -*-
"""MagyarAnime - Kodi videó plugin belépési pont (router)."""
import sys

try:
    from urllib.parse import urlencode, parse_qsl
except ImportError:
    from urllib import urlencode
    from urlparse import parse_qsl

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

from resources.lib import magyaranime as ma

ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE = sys.argv[0]


def build_url(**kw):
    return BASE + '?' + urlencode(kw)


def add_dir(label, url, folder=True, art=None, playable=False, plot=None, info=None):
    li = xbmcgui.ListItem(label=label)
    icon = ADDON.getAddonInfo('icon')
    li.setArt({'icon': art or icon, 'thumb': art or icon, 'poster': art,
               'fanart': ADDON.getAddonInfo('fanart')})
    vinfo = {'title': label, 'mediatype': 'video'}
    if plot:
        vinfo['plot'] = plot
    if info:
        vinfo.update(info)
    try:
        li.setInfo('video', vinfo)
    except Exception:  # noqa
        pass
    if playable:
        li.setProperty('IsPlayable', 'true')
    xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=folder)


def end(content='videos'):
    xbmcplugin.setContent(HANDLE, content)
    xbmcplugin.endOfDirectory(HANDLE)


def notify(msg, t=4000):
    xbmcgui.Dialog().notification(ADDON.getAddonInfo('name'), msg, ADDON.getAddonInfo('icon'), t)


def _cookie_ok():
    src, names = ma.cookie_status()
    return bool(names)


# --------------------------------------------------------------------------
def view_root():
    if not _cookie_ok():
        add_dir('[COLOR red]! Nincs cookie beállítva – kattints a beállításokhoz[/COLOR]',
                build_url(action='opensettings'), folder=False)
    add_dir('Keresés', build_url(action='search'))
    add_dir('Adatlapok (böngészés)', build_url(action='catmenu'))
    add_dir('Rész megnyitása azonosítóval', build_url(action='byid'))
    add_dir('[COLOR yellow]Kapcsolat teszt (cookie ellenőrzés)[/COLOR]',
            build_url(action='diag'), folder=False)
    end('files')


def view_diag():
    src, names = ma.cookie_status()
    lines = ['Cookie forrás: %s' % src,
             'Sütik (%d): %s' % (len(names), ', '.join(names) if names else '-'),
             'User-Agent: %s' % ma.user_agent(),
             'Feloldó modul: %s' % (ma.has_resolver() or 'nincs (indavideo saját; videa NEM megy)')]
    if names:
        ok, length = ma.check_login()
        lines.append('Főoldal betöltve: %d byte' % length)
        lines.append('Bejelentkezve: %s' % ('IGEN' if ok else 'NEM (más eszköz/IP vagy UA?)'))
    else:
        lines.append('Nincs betölthető cookie – add meg a fájlt vagy a szöveget a beállításokban.')
    xbmcgui.Dialog().textviewer(ADDON.getAddonInfo('name') + ' – teszt', '\n'.join(lines))
    end('files')


def view_search():
    kb = xbmc.Keyboard('', 'Anime keresése')
    kb.doModal()
    if not kb.isConfirmed() or not kb.getText().strip():
        end()
        return
    results = ma.search(kb.getText().strip())
    if not results:
        notify('Nincs találat (be vagy jelentkezve? cookie helyes?)')
    for r in results:
        add_dir(r['title'], build_url(action='anime', aid=r['aid']), art=r.get('art'))
    end('tvshows')


_CAT_FILTER_KEYS = ('allapot', 'szezon', 'besorolas', 'rendezes', 'kezdo')
_CAT_LETTERS = list('abcdefghijklmnopqrstuvwxyz')


_CAT_FILTER_TITLES = {'allapot': 'Állapot szerint', 'szezon': 'Szezon szerint',
                      'besorolas': 'Besorolás szerint', 'rendezes': 'Rendezés szerint',
                      'kezdo': 'Kezdőbetű szerint'}


def view_catmenu():
    add_dir('Aktuális szezon', build_url(action='catalog', allapot='1'))
    add_dir('Összes anime (A→Z)', build_url(action='catalog', allapot='-1', rendezes='1'))
    add_dir('Legújabbak (megjelenés szerint)',
            build_url(action='catalog', allapot='-1', rendezes='4'))
    # Dinamikus szűrő-listák (az oldalról olvasva)
    for which in ('szezon', 'besorolas', 'allapot', 'rendezes', 'kezdo'):
        add_dir(_CAT_FILTER_TITLES[which], build_url(action='catfilter', which=which))
    end('files')


def view_catfilter(which):
    opts = ma.catalog_filters().get(which, [])
    if not opts:
        notify('Nem sikerült betölteni a szűrőt')
    for value, label in opts:
        # Az adott szűrőt alkalmazzuk; az állapotot "Bármely"-re állítjuk,
        # kivéve ha épp az állapotot választjuk.
        params = {'action': 'catalog', which: value}
        if which != 'allapot':
            params['allapot'] = '-1'
        add_dir(label, BASE + '?' + urlencode(params))
    end('files')


def view_catletters():
    add_dir('Bármely', build_url(action='catalog', allapot='-1', kezdo='az'))
    for ch in _CAT_LETTERS:
        add_dir(ch.upper(), build_url(action='catalog', allapot='-1', kezdo=ch))
    end('files')


def _filters_from(p):
    return {k: p[k] for k in _CAT_FILTER_KEYS if p.get(k) not in (None, '')}


def view_catalog(page, filters):
    data = ma.catalog(page, filters or None)
    items = data.get('items') or []
    if not items:
        notify('Nincs adatlap (vagy nincs bejelentkezve)')
    for it in items:
        add_dir(it['title'], build_url(action='anime', aid=it['aid']), art=it.get('art'))
    pg, pages = data.get('page', 1), data.get('pages', 1)
    if pg < pages:
        nxt = dict(filters or {})
        nxt['action'] = 'catalog'
        nxt['page'] = str(pg + 1)
        add_dir('[COLOR yellow]Következő oldal (%d/%d) »[/COLOR]' % (pg + 1, pages),
                BASE + '?' + urlencode(nxt), folder=True)
    end('tvshows')


def view_anime(aid):
    data = ma.episodes_of_anime(aid)
    eps = data.get('episodes') or []
    plot = data.get('plot') or ''
    if not eps:
        notify('Nincs epizód (vagy nincs bejelentkezve)')
    if plot:
        add_dir('[COLOR gold]📖 Ismertető / Információ[/COLOR]',
                build_url(action='animeinfo', aid=str(aid)), folder=False)
    for ep in eps:
        label = ep['title']
        if ep.get('filler'):
            label = '%s  [COLOR grey](%s)[/COLOR]' % (label, ep['filler'])
        add_dir(label, build_url(action='servers', vid=ep['vid']),
                folder=True, art=ep.get('thumb'), plot=ep.get('plot') or plot,
                info={'mediatype': 'episode'})
    end('episodes')


def view_animeinfo(aid):
    info = ma.anime_info(aid)
    parts = []
    if info.get('meta'):
        parts.append(info['meta'])
    parts.append(info.get('plot') or 'Ehhez az animéhez nincs ismertető.')
    xbmcgui.Dialog().textviewer(info.get('title') or ADDON.getAddonInfo('name'),
                                '\n\n'.join(parts))
    end('files')


def view_servers(vid):
    servers = ma.list_servers(vid)
    if not servers:
        notify('Nincs elérhető szerver / forrás')
    for s in servers:
        host = s.get('host') or 'ismeretlen'
        label = host[:1].upper() + host[1:]
        if 'mega' in host.lower():
            label = '[COLOR gray]%s (nem támogatott)[/COLOR]' % label
        add_dir(label, build_url(action='play', vid=vid, server=s['server']),
                folder=False, playable=True, info={'mediatype': 'episode'})
    end('files')


def view_byid():
    kb = xbmc.Keyboard('', 'Rész azonosító (pl. 66008)')
    kb.doModal()
    if not kb.isConfirmed() or not kb.getText().strip().isdigit():
        end()
        return
    vid = kb.getText().strip()
    # A megadott rész alapján az anime adatlapja -> teljes, tiszta rész-lista.
    aid = ma.anime_id_of_resz(vid)
    if aid:
        view_anime(aid)
        return
    # tartalék: ha nincs adatlap-azonosító, a rész-oldal saját listája
    data = ma.episodes_of_resz(vid)
    eps = data.get('episodes') or []
    if not eps:
        notify('Nincs epizód (vagy nincs bejelentkezve)')
    for ep in eps:
        add_dir(ep['title'], build_url(action='servers', vid=ep['vid']),
                folder=True, info={'mediatype': 'episode'})
    end('episodes')


def play(vid, server=None):
    data = ma.resolve(vid, prefer_server=server)
    url = data.get('url')
    if not url:
        if data.get('mega'):
            notify('Ez a rész mega.nz-en van, ami jelenleg nem támogatott. '
                   'Próbálj másik szervert/feliratot, vagy másik részt.', t=9000)
        else:
            hint = '' if ma.has_resolver() else ' – telepítsd a ResolveURL-t (indavideo/videa)'
            notify('Nem sikerült a lejátszás%s' % hint, t=8000)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    li = xbmcgui.ListItem(path=url)
    headers = data.get('headers') or ''
    if data.get('hls'):
        li.setProperty('inputstream', 'inputstream.adaptive')
        li.setProperty('inputstreamaddon', 'inputstream.adaptive')
        li.setProperty('inputstream.adaptive.manifest_type', 'hls')
        if headers:
            li.setProperty('inputstream.adaptive.manifest_headers', headers)
            li.setProperty('inputstream.adaptive.stream_headers', headers)
        li.setMimeType('application/x-mpegURL')
        li.setContentLookup(False)
    elif headers:
        li.setPath(url + '|' + headers)
    ma.log('Lejátszás: %s' % url)
    xbmcplugin.setResolvedUrl(HANDLE, True, li)


def router(qs):
    p = dict(parse_qsl(qs))
    action = p.get('action')
    if not action:
        view_root()
    elif action == 'search':
        view_search()
    elif action == 'catmenu':
        view_catmenu()
    elif action == 'catletters':
        view_catletters()
    elif action == 'catfilter':
        view_catfilter(p.get('which', 'szezon'))
    elif action == 'catalog':
        view_catalog(int(p.get('page', 1)), _filters_from(p))
    elif action == 'anime':
        view_anime(p['aid'])
    elif action == 'animeinfo':
        view_animeinfo(p['aid'])
    elif action == 'servers':
        view_servers(p['vid'])
    elif action == 'byid':
        view_byid()
    elif action == 'diag':
        view_diag()
    elif action == 'play':
        play(p['vid'], p.get('server'))
    elif action == 'opensettings':
        ADDON.openSettings()
        end('files')
    else:
        view_root()


if __name__ == '__main__':
    router(sys.argv[2][1:] if len(sys.argv) > 2 else '')
