# -*- coding: utf-8 -*-
"""
SubVito - Kodi videó plugin belépési pont (router).

Menüszerkezet:
    Főmenü
      ├─ ▶ Folytatás       (a legutóbb nézett rész utáni rész)
      ├─ Legfrissebb részek
      ├─ Évadok            -> évad lista -> részek -> lejátszás
      ├─ Véletlen rész
      ├─ Keresés
      └─ Előzmények
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
    if is_folder is False:
        li.setProperty('IsPlayable', 'true')
    xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=bool(is_folder))


def end(content='videos'):
    xbmcplugin.setContent(HANDLE, content)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


# ---------------------------------------------------------------------------
# Nézetek
# ---------------------------------------------------------------------------
def view_root():
    icon = ADDON.getAddonInfo('icon')
    nxt = subvito.next_episode()
    if nxt:
        add_dir('[COLOR gold]▶ %s: %s[/COLOR]  [COLOR grey](%s)[/COLOR]'
                % (L(30014, 'Folytatás'), nxt['title'], nxt['cat']),
                build_url(action='play', url=nxt['url']), thumb=icon, is_folder=False,
                info=_ep_info(nxt))
    add_dir(L(30011, 'Legfrissebb részek'), build_url(action='latest'), thumb=icon)
    add_dir(L(30010, 'Évadok'), build_url(action='seasons'), thumb=icon)
    add_dir(L(30015, 'Véletlen rész'), build_url(action='random'), thumb=icon,
            is_folder=False)
    add_dir(L(30012, 'Keresés'), build_url(action='search'), thumb=icon)
    add_dir(L(30016, 'Előzmények (legutóbb nézett)'), build_url(action='history'), thumb=icon)
    add_dir('[COLOR yellow]📊 %s[/COLOR]' % (L(30017, 'Ma: %d kérés az oldalra')
                                            % subvito.today_requests()),
            build_url(action='info'), thumb=icon, is_folder=None)
    add_dir('[COLOR grey]%s[/COLOR]' % L(30018, 'Katalógus frissítése'),
            build_url(action='refresh'), thumb=icon, is_folder=None)
    end(content='files')


def _ep_info(ep):
    info = {'mediatype': 'episode', 'tvshowtitle': 'South Park'}
    if ep.get('season'):
        info['season'] = ep['season']
        info['episode'] = ep.get('episode')
    return info


def _add_episode(ep, label=None):
    add_dir(label or ep['title'], build_url(action='play', url=ep['url']),
            thumb=ep.get('thumb'), is_folder=False, info=_ep_info(ep))


def view_history():
    items = subvito.history()
    if not items:
        _notify(L(30020, 'Nincs találat'))
    for ep in items:
        _add_episode(ep, '%s  [COLOR grey](%s)[/COLOR]' % (ep['title'], ep.get('cat', '')))
    if items:
        add_dir('[COLOR grey]%s[/COLOR]' % L(30019, 'Előzmények törlése'),
                build_url(action='histclear'), is_folder=None)
    end(content='episodes')


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
    sn = subvito.season_number(season_url)
    for i, ep in enumerate(episodes):
        _add_episode(dict(ep, season=sn, episode=i + 1))
    end(content='episodes')


def view_latest():
    episodes = subvito.list_latest()
    if not episodes:
        _notify(L(30020, 'Nincs találat'))
    for ep in episodes:
        _add_episode(subvito.episode_meta(ep['url']) or ep)
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
        meta = subvito.episode_meta(ep['url']) or {}
        _add_episode(dict(meta, **ep))
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
        meta = subvito.episode_meta(episode_url)
        if meta:
            info = _ep_info(meta)
            info['title'] = meta['title']
            try:
                li.setInfo('video', info)
            except Exception:  # noqa
                pass
        subvito.add_history(episode_url)
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
    elif action == 'random':
        ep = subvito.random_episode()
        if ep:
            _notify('%s · %s' % (ep['title'], ep['cat']), time=3000)
            play(ep['url'])
        else:
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
    elif action == 'history':
        view_history()
    elif action == 'histclear':
        subvito.clear_history()
        xbmc.executebuiltin('Container.Refresh')
    elif action == 'refresh':
        subvito.clear_cache()
        subvito.get_catalog(force=True)
        _notify(L(30018, 'Katalógus frissítése') + ' OK', time=2500)
        xbmc.executebuiltin('Container.Refresh')
    elif action == 'info':
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'),
                            'User-Agent (fix): %s\n%s' % (subvito.USER_AGENT,
                            L(30017, 'Ma: %d kérés az oldalra') % subvito.today_requests()))
    else:
        view_root()


if __name__ == '__main__':
    router(sys.argv[2][1:] if len(sys.argv) > 2 else '')
