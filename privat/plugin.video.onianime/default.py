# -*- coding: utf-8 -*-
"""OniAnime - Kodi videó plugin belépési pont (router).

Kérés-takarékos: egy művelet = egy API-kérés; a lejátszás 0 további kérés.
Lásd resources/lib/onianime.py fejléc-megjegyzését.
"""
import sys

try:
    from urllib.parse import urlencode, parse_qsl, quote
except ImportError:  # Py2
    from urllib import urlencode, quote
    from urlparse import parse_qsl

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

from resources.lib import onianime as oni

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


def notify(msg, t=5000):
    xbmcgui.Dialog().notification(ADDON.getAddonInfo('name'), msg, ADDON.getAddonInfo('icon'), t)


# --------------------------------------------------------------------------
def view_root():
    add_dir('Keresés', build_url(action='search'))
    add_dir('Böngészés (katalógus)', build_url(action='catalog', page='1'))
    end('files')


def view_search():
    kb = xbmc.Keyboard('', 'Anime keresése')
    kb.doModal()
    if not kb.isConfirmed() or not kb.getText().strip():
        end()
        return
    data = oni.search(kb.getText().strip())
    items = data.get('items') or []
    if not items:
        notify('Nincs találat')
    for it in items:
        _add_anime(it)
    end('tvshows')


def view_catalog(page):
    data = oni.catalog(page)
    items = data.get('items') or []
    if not items:
        notify('Nincs adat (vagy hálózati hiba)')
    for it in items:
        _add_anime(it)
    pg, pages = data.get('page', 1), data.get('pages', 1)
    if pg < pages:
        add_dir('[COLOR yellow]Következő oldal (%d/%d) »[/COLOR]' % (pg + 1, pages),
                build_url(action='catalog', page=str(pg + 1)), folder=True)
    end('tvshows')


def _add_anime(it):
    label = it['title']
    extra = []
    if it.get('type'):
        extra.append(it['type'])
    if it.get('avail'):
        extra.append(it['avail'])
    if extra:
        label = '%s  [COLOR grey](%s)[/COLOR]' % (label, ' · '.join(extra))
    plot = it.get('plot') or ''
    add_dir(label, build_url(action='anime', aid=it['aid']),
            art=it.get('art'), plot=plot, info={'mediatype': 'tvshow'})


def view_anime(aid):
    data = oni.episodes(aid)
    eps = data.get('episodes') or []
    art = data.get('art') or ''
    if not eps:
        notify('Nincs epizód (vagy hálózati hiba)')
    for ep in eps:
        tags = []
        if ep.get('hasSub'):
            tags.append('Felirat')
        if ep.get('hasDub'):
            tags.append('Szinkron')
        label = '%d. rész' % ep['ep']
        if ep.get('title'):
            label += ' - %s' % ep['title']
        if tags:
            label += '  [COLOR grey](%s)[/COLOR]' % '/'.join(tags)
        add_dir(label,
                build_url(action='parts', aid=aid, ep=str(ep['ep']),
                          voice='sub', hasdub=('1' if ep.get('hasDub') else '0')),
                folder=True, art=(ep.get('thumb') or art),
                plot=ep.get('plot') or '', info={'mediatype': 'episode'})
    end('episodes')


def view_parts(aid, ep, voice, hasdub):
    # Ha a felirat-listát nézzük és van szinkron is, kínáljunk egy külön menüpontot,
    # ami CSAK kattintásra kér le adatot (nem terheljük feleslegesen a szervert).
    if voice == 'sub' and hasdub == '1':
        add_dir('[COLOR gold]🎙 Szinkron verzió[/COLOR]',
                build_url(action='parts', aid=aid, ep=ep, voice='dub', hasdub='0'),
                folder=True)
    sources = oni.parts(aid, ep, voice)
    if not sources:
        notify('Nincs elérhető forrás ehhez a részhez')
    vlabel = 'Szinkron' if voice == 'dub' else 'Felirat'
    for s in sources:
        q = s.get('label') or 'Videó'
        label = '[COLOR yellow][%s][/COLOR] %s' % (q, vlabel)
        add_dir(label, build_url(action='play', url=s['url']),
                folder=False, playable=True, info={'mediatype': 'episode'})
    end('files')


def play(url):
    if not url:
        notify('Hiányzó videó-URL')
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    # A videa.hu közvetlen MP4 - fejléccel (UA + Referer) a biztos lejátszásért.
    headers = 'User-Agent=%s&Referer=%s' % (quote(oni.user_agent(), ''),
                                            quote('https://videa.hu/', ''))
    path = url + '|' + headers
    li = xbmcgui.ListItem(path=path)
    li.setMimeType('video/mp4')
    li.setContentLookup(False)
    oni.log('Lejátszás: %s' % url)
    xbmcplugin.setResolvedUrl(HANDLE, True, li)


def router(qs):
    p = dict(parse_qsl(qs))
    action = p.get('action')
    if not action:
        view_root()
    elif action == 'search':
        view_search()
    elif action == 'catalog':
        view_catalog(int(p.get('page', 1)))
    elif action == 'anime':
        view_anime(p['aid'])
    elif action == 'parts':
        view_parts(p['aid'], p['ep'], p.get('voice', 'sub'), p.get('hasdub', '0'))
    elif action == 'play':
        play(p.get('url'))
    elif action == 'opensettings':
        ADDON.openSettings()
        end('files')
    else:
        view_root()


if __name__ == '__main__':
    router(sys.argv[2][1:] if len(sys.argv) > 2 else '')
