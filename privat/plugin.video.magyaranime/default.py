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
    add_dir('Rész megnyitása azonosítóval', build_url(action='byid'))
    add_dir('[COLOR yellow]Kapcsolat teszt (cookie ellenőrzés)[/COLOR]',
            build_url(action='diag'), folder=False)
    end('files')


def view_diag():
    src, names = ma.cookie_status()
    lines = ['Cookie forrás: %s' % src,
             'Sütik (%d): %s' % (len(names), ', '.join(names) if names else '-'),
             'User-Agent: %s' % ma.user_agent()]
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


def view_anime(aid):
    data = ma.episodes_of_anime(aid)
    eps = data.get('episodes') or []
    if not eps:
        notify('Nincs epizód (vagy nincs bejelentkezve)')
    for ep in eps:
        add_dir(ep['title'], build_url(action='play', vid=ep['vid'], server=ep.get('server', 's1')),
                folder=False, playable=True, art=ep.get('thumb'), info={'mediatype': 'episode'})
    end('episodes')


def view_byid():
    kb = xbmc.Keyboard('', 'Rész azonosító (pl. 66008)')
    kb.doModal()
    if not kb.isConfirmed() or not kb.getText().strip().isdigit():
        end()
        return
    vid = kb.getText().strip()
    data = ma.episodes_of_resz(vid)
    eps = data.get('episodes') or []
    if not eps:
        notify('Nincs epizód (vagy nincs bejelentkezve)')
    for ep in eps:
        add_dir(ep['title'], build_url(action='play', vid=ep['vid'], server=ep.get('server', 's1')),
                folder=False, playable=True, info={'mediatype': 'episode'})
    end('episodes')


def play(vid, server=None):
    data = ma.resolve(vid, prefer_server=server)
    url = data.get('url')
    if not url:
        srv = ', '.join(s.get('server', '?') for s in data.get('servers') or [])
        notify('Nem sikerült a lejátszás%s' % ((' (szerverek: %s)' % srv) if srv else ''), t=7000)
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
    elif action == 'anime':
        view_anime(p['aid'])
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
