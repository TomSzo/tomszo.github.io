# -*- coding: utf-8 -*-
"""
Streamed - Kodi videó plugin belépési pont (router).

Menü:
    Főmenü
      ├─ Élő most
      ├─ Népszerű
      ├─ Ma
      └─ Sportágak -> meccsek -> streamek -> lejátszás
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

from resources.lib import streamed

ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE = sys.argv[0]


def L(string_id, fallback):
    try:
        text = ADDON.getLocalizedString(string_id)
        return text if text else fallback
    except Exception:  # noqa
        return fallback


def build_url(**kwargs):
    return BASE + '?' + urlencode(kwargs)


def add_dir(label, url, is_folder=True, art=None, playable=False, plot=None, info=None):
    li = xbmcgui.ListItem(label=label)
    icon = ADDON.getAddonInfo('icon')
    li.setArt({'icon': art or icon, 'thumb': art or icon,
               'poster': art, 'fanart': ADDON.getAddonInfo('fanart')})
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
    xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=is_folder)


def end(content='videos'):
    xbmcplugin.setContent(HANDLE, content)
    xbmcplugin.addSortMethod(HANDLE, xbmcplugin.SORT_METHOD_NONE)
    xbmcplugin.endOfDirectory(HANDLE)


def _notify(message, time=4000):
    xbmcgui.Dialog().notification(ADDON.getAddonInfo('name'), message,
                                  ADDON.getAddonInfo('icon'), time)


# ---------------------------------------------------------------------------
# Nézetek
# ---------------------------------------------------------------------------
def view_root():
    icon = ADDON.getAddonInfo('icon')
    add_dir('[COLOR red]● [/COLOR]' + L(30010, 'Élő most'),
            build_url(action='matches', path='api/matches/live'), art=icon)
    add_dir(L(30011, 'Népszerű'),
            build_url(action='matches', path='api/matches/all/popular'), art=icon)
    add_dir(L(30012, 'Ma'),
            build_url(action='matches', path='api/matches/all-today'), art=icon)
    add_dir(L(30013, 'Sportágak'), build_url(action='sports'), art=icon)
    add_dir(L(30014, 'Összes meccs'),
            build_url(action='matches', path='api/matches/all'), art=icon)
    end(content='files')


def view_sports():
    sports = streamed.list_sports()
    if not sports:
        _notify(L(30020, 'Nincs találat'))
    for s in sports:
        add_dir(s['name'], build_url(action='matches', path='api/matches/%s' % s['id']))
    end(content='files')


def view_matches(path):
    matches = streamed.list_matches(path)
    if not matches:
        _notify(L(30020, 'Nincs találat'))
    for m in matches:
        add_dir(streamed.match_label(m),
                build_url(action='streams', id=m['id'], title=m['title'],
                          src=_pack_sources(m['sources'])),
                art=m.get('art'), plot=m.get('category'))
    end(content='videos')


def view_streams(match):
    streams = streamed.get_streams(match)
    if not streams:
        _notify(L(30021, 'Nincs elérhető stream'))
    for st in streams:
        add_dir(streamed.stream_label(st),
                build_url(action='play', source=st['source'], sid=st['id'],
                          no=st['streamNo'], embed=st.get('embedUrl') or ''),
                is_folder=False, playable=True, info={'mediatype': 'video'})
    end(content='videos')


# ---------------------------------------------------------------------------
# Lejátszás
# ---------------------------------------------------------------------------
def play(st):
    data = streamed.resolve(st)
    urls = data.get('m3u8') or []
    if urls:
        stream_url = urls[0]
        headers = streamed.hls_headers(data['origin'])
        li = xbmcgui.ListItem(path=stream_url)
        li.setProperty('inputstream', 'inputstream.adaptive')
        li.setProperty('inputstreamaddon', 'inputstream.adaptive')
        li.setProperty('inputstream.adaptive.manifest_type', 'hls')
        li.setProperty('inputstream.adaptive.manifest_headers', headers)
        li.setProperty('inputstream.adaptive.stream_headers', headers)
        li.setMimeType('application/x-mpegURL')
        li.setContentLookup(False)
        streamed.log('Lejátszás: %s' % stream_url)
        xbmcplugin.setResolvedUrl(HANDLE, True, li)
        return

    # Nem sikerült m3u8-at kinyerni – jelezzük és naplózzuk az embedet.
    streamed.log('Nincs m3u8. Embed: %s' % data.get('embed'), xbmc.LOGWARNING)
    try:
        host = data['embed'].split('/')[2]
    except Exception:  # noqa
        host = data.get('embed', '')
    _notify(L(30022, 'Nem sikerült kinyerni a streamet (%s)') % host, time=8000)
    xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())


# ---------------------------------------------------------------------------
# Segédek: források csomagolása az URL-ben
# ---------------------------------------------------------------------------
def _pack_sources(sources):
    return ';'.join('%s,%s' % (s['source'], s['id']) for s in sources)


def _unpack_sources(packed):
    out = []
    for part in (packed or '').split(';'):
        if ',' in part:
            source, sid = part.split(',', 1)
            out.append({'source': source, 'id': sid})
    return out


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
def router(paramstring):
    params = dict(parse_qsl(paramstring))
    action = params.get('action')

    if not action:
        view_root()
    elif action == 'sports':
        view_sports()
    elif action == 'matches':
        view_matches(params['path'])
    elif action == 'streams':
        match = {'id': params.get('id'), 'title': params.get('title', ''),
                 'sources': _unpack_sources(params.get('src'))}
        view_streams(match)
    elif action == 'play':
        st = {'source': params['source'], 'id': params['sid'],
              'streamNo': params.get('no', 1), 'embedUrl': params.get('embed') or ''}
        play(st)
    else:
        view_root()


if __name__ == '__main__':
    router(sys.argv[2][1:] if len(sys.argv) > 2 else '')
