# -*- coding: utf-8 -*-
"""Naruto-Kun.Hu - Kodi videó plugin belépési pont (router)."""
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

from resources.lib import narutokun as nk
from resources.lib import library as lib

ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE = sys.argv[0]


def build_url(**kw):
    return BASE + '?' + urlencode(kw)


def add_dir(label, url, folder=True, art=None, playable=False, plot=None, info=None,
            context=None):
    li = xbmcgui.ListItem(label=label)
    if context:
        li.addContextMenuItems(context)
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
    xbmcgui.Dialog().notification(ADDON.getAddonInfo('name'), msg,
                                  ADDON.getAddonInfo('icon'), t)


# --------------------------------------------------------------------------
# Kedvencek / Előzmények (helyi)
# --------------------------------------------------------------------------
def _anime_key(aid):
    return 'anime:%s' % aid


def _fav_ctx(aid, title, art):
    label = ('[COLOR red]✖[/COLOR] Törlés a kedvencekből' if lib.is_favorite(_anime_key(aid))
             else '[COLOR gold]★[/COLOR] Hozzáadás a kedvencekhez')
    return [(label, 'RunPlugin(%s)' % build_url(action='favtoggle', aid=aid, t=title,
                                                art=art or ''))]


def add_anime(title, aid, art=None, label=None, plot=None):
    add_dir(label or title, build_url(action='anime', aid=aid, t=title, art=art or ''),
            art=art, plot=plot, info={'mediatype': 'tvshow'},
            context=_fav_ctx(aid, title, art))


def view_favorites():
    items = lib.favorites()
    if not items:
        notify('Még nincs kedvenc – egy animén: helyi menü → Hozzáadás a kedvencekhez')
    for it in items:
        add_anime(it['title'], it['params'].get('aid'), it.get('art'))
    end('tvshows')


def view_history():
    items = lib.history()
    if not items:
        notify('Még nincs előzmény')
    for it in items:
        label = it['title']
        if it.get('last'):
            label = '%s  [COLOR grey](utoljára: %s)[/COLOR]' % (label, it['last'])
        add_anime(it['title'], it['params'].get('aid'), it.get('art'), label=label)
    if items:
        add_dir('[COLOR grey]Előzmények törlése[/COLOR]', build_url(action='histclear'),
                folder=False)
    end('tvshows')


def fav_toggle(p):
    added = lib.toggle_favorite(_anime_key(p['aid']), p.get('t'), p.get('art'),
                                {'action': 'anime', 'aid': p['aid']})
    notify('Hozzáadva a kedvencekhez' if added else 'Törölve a kedvencekből', t=2500)
    xbmc.executebuiltin('Container.Refresh')


# --------------------------------------------------------------------------
def view_root():
    if not nk.have_credentials():
        add_dir('[COLOR grey]Belépés: add meg a felhasználóneved/jelszavad (ha kell)[/COLOR]',
                build_url(action='opensettings'), folder=False)
    add_dir('[COLOR yellow]📊 Ma: %d kérés az oldalra[/COLOR]' % nk.today_requests(),
            build_url(action='diag'), folder=False)
    add_dir('[COLOR gold]★ Kedvencek[/COLOR]', build_url(action='favorites'))
    add_dir('Előzmények (legutóbb nézett)', build_url(action='history'))
    add_dir('[COLOR orange]Legfrissebb részek[/COLOR]', build_url(action='latest'))
    for key, label in nk.STATUSES:
        add_dir(label, build_url(action='list', s=key))
    add_dir('Keresés', build_url(action='search'))
    add_dir('[COLOR grey]Gyorsítótár frissítése[/COLOR]', build_url(action='refreshcache'),
            folder=False)
    end('files')


def view_diag():
    ok, who = nk.check_login()
    lines = ['Oldal: %s' % nk.base_url(),
             'Belépési adat forrása: %s' % nk.cred_source(),
             'Bejelentkezve: %s' % (('IGEN (%s)' % who) if ok else 'NEM'),
             'User-Agent (fix): %s' % nk.user_agent(),
             'Mai kérések az oldalra (helyi számláló): %d' % nk.today_requests(),
             'ResolveURL (videa/indavideo feloldás): %s'
             % ('telepítve' if nk.has_resolver() else 'NINCS – telepítsd a privát tárolóból')]
    if not ok:
        lines += ['', 'A nyilvános oldalak belépés nélkül is mennek. Ha valamelyik rész '
                  'belépést kér, add meg a felhasználóneved és jelszavad a beállításokban '
                  '(vagy login.txt-ben az addon_data mappában).']
    xbmcgui.Dialog().textviewer(ADDON.getAddonInfo('name') + ' – állapot', '\n'.join(lines))


def view_list(s, rowstart=0):
    items, nxt = nk.anime_list(s, rowstart)
    if not items:
        notify('Nincs találat')
    for it in items:
        label = it['title']
        if it.get('type') and it['type'].lower() != 'anime':
            label = '%s  [COLOR grey](%s)[/COLOR]' % (label, it['type'])
        add_anime(it['title'], it['id'], it.get('art'), label=label, plot=it.get('alt'))
    if nxt is not None:
        add_dir('[COLOR yellow]Következő oldal »[/COLOR]',
                build_url(action='list', s=s, r=str(nxt)))
    end('tvshows')


def view_search():
    kb = xbmc.Keyboard('', 'Anime keresése')
    kb.doModal()
    if not kb.isConfirmed() or not kb.getText().strip():
        return
    items = nk.search(kb.getText().strip())
    if not items:
        notify('Nincs találat')
    for it in items:
        add_anime(it['title'], it['id'], it.get('art'), plot=it.get('alt'))
    end('tvshows')


def _list_videos(videos, art=None, plot=None):
    for v in videos:
        add_dir(v['title'], build_url(action='play', v=v['id']), folder=False, playable=True,
                art=v.get('thumb') or art, plot=plot, info={'mediatype': 'episode'})


def view_anime(aid, title=None, art=None):
    data = nk.anime_episodes(aid)
    vids = data.get('videos') or []
    title = data.get('title') or title or 'anime %s' % aid
    art = data.get('art') or art
    if vids:
        lib.add_history(_anime_key(aid), title, art, {'action': 'anime', 'aid': str(aid)})
        lib.set_current(_anime_key(aid), {v['id']: v['title'] for v in vids})
    else:
        notify('Ehhez az animéhez nincs online rész')
    if data.get('plot'):
        add_dir('[COLOR gold]📖 Ismertető[/COLOR]  [COLOR grey]%s · %s[/COLOR]'
                % (data.get('status') or '', data.get('episodes') or ''),
                build_url(action='info', aid=aid), folder=False, art=art, plot=data['plot'])
    _list_videos(vids, art=art, plot=data.get('plot'))
    end('episodes')


def view_info(aid):
    data = nk.anime_episodes(aid)
    meta = ' · '.join(x for x in (data.get('alt'), data.get('status'), data.get('episodes')) if x)
    xbmcgui.Dialog().textviewer(data.get('title') or ADDON.getAddonInfo('name'),
                                '%s\n\n%s' % (meta, data.get('plot') or 'Nincs ismertető.'))


def view_latest():
    items = nk.latest()
    if not items:
        notify('Nincs friss online rész')
    _list_videos(items)
    end('episodes')


def play(vid):
    w = nk.watch(vid)
    nk.log('Watch %s: lejátszó = %s' % (vid, w.get('embed')))
    if not w.get('embed'):
        path = nk.save_debug('debug_watch_%s.html' % vid, w.get('html'))
        nk.log('Nincs lejátszó a watch oldalon, mentve: %s' % path, xbmc.LOGWARNING)
        notify('Nincs online lejátszó ennél a résznél (oldal mentve: debug_watch_%s.html)' % vid,
               t=8000)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    media = nk.resolve_embed(w['embed'])
    if not media:
        host = w['embed'].split('/')[2] if '//' in w['embed'] else w['embed']
        hint = ' – telepítsd a ResolveURL-t' if not nk.has_resolver() else ' (%s)' % host
        notify('Nem sikerült a videó feloldása%s' % hint, t=8000)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    li = xbmcgui.ListItem(path=nk.play_url(media))
    li.setInfo('video', {'title': w.get('title') or 'rész %s' % vid, 'mediatype': 'episode'})
    if w.get('poster'):
        li.setArt({'thumb': w['poster'], 'poster': w['poster']})
    if '.m3u8' in media.lower():
        li.setProperty('inputstream', 'inputstream.adaptive')
        li.setMimeType('application/x-mpegURL')
        li.setContentLookup(False)
    lib.mark_played_id(vid, w.get('title'))
    nk.log('Lejátszás: %s -> %s' % (w['embed'], media.split('|')[0]))
    xbmcplugin.setResolvedUrl(HANDLE, True, li)


def router(qs):
    p = dict(parse_qsl(qs))
    action = p.get('action')
    if not action:
        view_root()
    elif action == 'list':
        view_list(p.get('s', ''), int(p.get('r', 0) or 0))
    elif action == 'anime':
        view_anime(p['aid'], p.get('t'), p.get('art'))
    elif action == 'info':
        view_info(p['aid'])
    elif action == 'latest':
        view_latest()
    elif action == 'search':
        view_search()
    elif action == 'favorites':
        view_favorites()
    elif action == 'history':
        view_history()
    elif action == 'favtoggle':
        fav_toggle(p)
    elif action == 'histclear':
        lib.clear_history()
        xbmc.executebuiltin('Container.Refresh')
    elif action == 'refreshcache':
        nk.clear_page_cache()
        notify('Gyorsítótár frissítve')
    elif action == 'diag':
        view_diag()
    elif action == 'clearsession':
        nk.clear_cookies()
        notify('Munkamenet törölve – következő lekéréskor újra bejelentkezik')
    elif action == 'opensettings':
        ADDON.openSettings()
    elif action == 'play':
        play(p['v'])
    else:
        view_root()


if __name__ == '__main__':
    router(sys.argv[2][1:] if len(sys.argv) > 2 else '')
