# -*- coding: utf-8 -*-
"""
SubVito - Kodi videó plugin belépési pont (router).

Menüszerkezet:
    Főmenü
      ├─ Évadok            -> évad lista -> részek -> lejátszás
      ├─ Legfrissebb részek
      └─ Keresés
"""
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

from resources.lib import subvito

ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE = sys.argv[0]


def L(string_id, fallback):
    """Lokalizált szöveg, tartalék szöveggel."""
    try:
        text = ADDON.getLocalizedString(string_id)
        return text if text else fallback
    except Exception:  # noqa
        return fallback


def build_url(**kwargs):
    return BASE + '?' + urlencode(kwargs)


def add_dir(label, url, thumb=None, is_folder=True, info=None, plot=None):
    li = xbmcgui.ListItem(label=label)
    art = {'icon': thumb or 'DefaultVideo.png',
           'thumb': thumb or ADDON.getAddonInfo('icon'),
           'poster': thumb,
           'fanart': ADDON.getAddonInfo('fanart')}
    li.setArt({k: v for k, v in art.items() if v})
    vinfo = {'title': label, 'mediatype': 'video'}
    if plot:
        vinfo['plot'] = plot
    if info:
        vinfo.update(info)
    try:
        li.setInfo('video', vinfo)
    except Exception:  # noqa
        pass
    if not is_folder:
        li.setProperty('IsPlayable', 'true')
    xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=is_folder)


def end(content='videos'):
    xbmcplugin.setContent(HANDLE, content)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


# ---------------------------------------------------------------------------
# Nézetek
# ---------------------------------------------------------------------------
def view_root():
    add_dir(L(30010, 'Évadok'), build_url(action='seasons'),
            thumb=ADDON.getAddonInfo('icon'))
    add_dir(L(30011, 'Legfrissebb részek'), build_url(action='latest'),
            thumb=ADDON.getAddonInfo('icon'))
    add_dir(L(30012, 'Keresés'), build_url(action='search'),
            thumb=ADDON.getAddonInfo('icon'))
    end(content='files')


def view_seasons():
    cats = subvito.list_categories()
    if not cats:
        _notify(L(30020, 'Nincs találat'))
    for cat in cats:
        count = len(cat.get('episodes') or [])
        label = cat['label']
        if count:
            label = '%s  (%d)' % (label, count)
        add_dir(label, build_url(action='episodes', url=cat['url']),
                thumb=ADDON.getAddonInfo('icon'))
    end(content='seasons')


def view_episodes(season_url):
    episodes = subvito.list_episodes(season_url)
    if not episodes:
        _notify(L(30020, 'Nincs találat'))
    for ep in episodes:
        add_dir(ep['title'], build_url(action='play', url=ep['url']),
                thumb=ep.get('thumb'), is_folder=False,
                info={'mediatype': 'episode'})
    end(content='episodes')


def view_latest():
    episodes = subvito.list_latest()
    if not episodes:
        _notify(L(30020, 'Nincs találat'))
    for ep in episodes:
        add_dir(ep['title'], build_url(action='play', url=ep['url']),
                thumb=ep.get('thumb'), is_folder=False,
                info={'mediatype': 'episode'})
    end(content='episodes')


def view_search():
    kb = xbmc.Keyboard('', L(30012, 'Keresés'))
    kb.doModal()
    if not kb.isConfirmed():
        end()
        return
    query = kb.getText().strip()
    if not query:
        end()
        return
    episodes = subvito.search(query)
    if not episodes:
        _notify(L(30020, 'Nincs találat'))
    for ep in episodes:
        add_dir(ep['title'], build_url(action='play', url=ep['url']),
                thumb=ep.get('thumb'), is_folder=False,
                info={'mediatype': 'episode'})
    end(content='episodes')


# ---------------------------------------------------------------------------
# Lejátszás
# ---------------------------------------------------------------------------
def _make_play_item(stream_url, subs=None):
    li = xbmcgui.ListItem(path=stream_url)
    lower = stream_url.lower()
    if '.m3u8' in lower:
        li.setProperty('inputstream', 'inputstream.adaptive')
        # Kodi 19 kompatibilitás: régi property is beállítva
        li.setProperty('inputstreamaddon', 'inputstream.adaptive')
        li.setProperty('inputstream.adaptive.manifest_type', 'hls')
        li.setMimeType('application/x-mpegURL')
        li.setContentLookup(False)
    if subs:
        try:
            li.setSubtitles(subs)
        except Exception:  # noqa
            pass
    return li


def play(episode_url):
    data = subvito.resolve(episode_url)
    media = data.get('media') or []
    subs = data.get('subs') or []

    if media:
        stream = media[0]
        subvito.log('Lejátszás: %s' % stream)
        li = _make_play_item(stream, subs)
        xbmcplugin.setResolvedUrl(HANDLE, True, li)
        return

    # Nincs közvetlen média. Ha van iframe beágyazás, jelezzük a felhasználónak,
    # és naplózzuk, hogy a beágyazó szolgáltatót később támogatni tudjuk.
    iframes = data.get('iframes') or []
    if iframes:
        subvito.log('Nem sikerült közvetlen forrást kinyerni. Iframe(k): %s' % iframes,
                    xbmc.LOGWARNING)
        msg = L(30021, 'Beágyazott lejátszó – jelezd a fejlesztőnek: %s')
        try:
            host = iframes[0].split('/')[2]
        except Exception:  # noqa
            host = iframes[0]
        try:
            msg = msg % host
        except Exception:  # noqa
            msg = host
        _notify(msg, time=8000)
    else:
        _notify(L(30022, 'Nem található lejátszható forrás'))

    xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())


def _notify(message, time=4000):
    xbmcgui.Dialog().notification(ADDON.getAddonInfo('name'), message,
                                  ADDON.getAddonInfo('icon'), time)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
def router(paramstring):
    params = dict(parse_qsl(paramstring))
    action = params.get('action')

    if not action:
        view_root()
    elif action == 'seasons':
        view_seasons()
    elif action == 'episodes':
        view_episodes(params['url'])
    elif action == 'latest':
        view_latest()
    elif action == 'search':
        view_search()
    elif action == 'play':
        play(params['url'])
    else:
        view_root()


if __name__ == '__main__':
    router(sys.argv[2][1:] if len(sys.argv) > 2 else '')
