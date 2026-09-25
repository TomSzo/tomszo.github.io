# -*- coding: utf-8 -*-
"""Network4 / Arena4+ (privát) - menük és lejátszás."""
import calendar
import sys
import time

try:
    from urllib.parse import parse_qsl, urlencode, quote
except ImportError:  # py2
    from urlparse import parse_qsl
    from urllib import urlencode, quote

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib import net4api as api

URL = sys.argv[0]
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].lstrip('-').isdigit() else -1
PARAMS = dict(parse_qsl(sys.argv[2][1:])) if len(sys.argv) > 2 else {}
NAME = 'Network4'
DEFAULT_LICENSE = 'https://content.uplynk.com/wv'


def url(**kw):
    return URL + '?' + urlencode(kw)


def notify(msg, t=4000, icon=None):
    xbmcgui.Dialog().notification(NAME, msg, icon or api.ADDON.getAddonInfo('icon'), t)


def _info(li, title, plot='', mediatype='video'):
    if hasattr(li, 'getVideoInfoTag'):
        tag = li.getVideoInfoTag()
        tag.setTitle(title)
        tag.setPlot(plot or title)
        tag.setMediaType(mediatype)
    else:  # Kodi 19
        li.setInfo('video', {'title': title, 'plot': plot or title, 'mediatype': mediatype})


def add(label, target, thumb='', folder=True, plot='', playable=False, ctx=None):
    li = xbmcgui.ListItem(label)
    icon = thumb or ('DefaultFolder.png' if folder else 'DefaultVideo.png')
    li.setArt({'thumb': icon, 'icon': icon, 'poster': icon,
               'fanart': api.ADDON.getAddonInfo('fanart')})
    if plot or playable:
        _info(li, label, plot)
    if playable:
        li.setProperty('IsPlayable', 'true')
    if ctx:
        li.addContextMenuItems(ctx)
    xbmcplugin.addDirectoryItem(HANDLE, target, li, folder)


def end(content='videos', cache=True):
    xbmcplugin.setContent(HANDLE, content)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=cache)


def fail(exc):
    """Hiba kijelzése érthetően."""
    if isinstance(exc, api.ChallengeError):
        msg = ('A Network4 szervere Cloudflare-ellenőrzést kért. Ezt az addon nem kerüli meg.\n'
               'Próbáld: Beállítások → API User-Agent: "Network4 mobilalkalmazás".')
        xbmcgui.Dialog().ok(NAME, msg)
    elif isinstance(exc, api.LoginError):
        xbmcgui.Dialog().ok(NAME, str(exc))
    else:
        notify('Hiba: %s' % exc, 6000)
    api.log('hiba: %s' % exc, xbmc.LOGWARNING)


# ---------------------------------------------------------------------------
# Menük
# ---------------------------------------------------------------------------
def root():
    if not api.have_credentials():
        add('[COLOR yellow]Add meg az email címet és a jelszót (Beállítások)[/COLOR]',
            url(action='settings'), 'DefaultAddonService.png', folder=False)
    add('Élő közvetítések', url(action='live'), 'DefaultTVShows.png')
    add('Videótár', url(action='collections'), 'DefaultMovies.png')
    add('Keresés', url(action='search'), 'DefaultAddonsSearch.png')
    add('Kapcsolat teszt  [COLOR gray](ma %d kérés)[/COLOR]' % api.today_requests(),
        url(action='diag'), 'DefaultAddonService.png', folder=False)
    end('files')


def _local(iso):
    """'2026-09-25T18:00:00.000000Z' (UTC) -> 'szept. 25. 20:00' helyi idő szerint."""
    if not iso:
        return ''
    try:
        t = calendar.timegm(time.strptime(iso[:19], '%Y-%m-%dT%H:%M:%S'))
        lt = time.localtime(t)
        months = ('jan.', 'febr.', 'márc.', 'ápr.', 'máj.', 'jún.', 'júl.', 'aug.', 'szept.',
                  'okt.', 'nov.', 'dec.')
        return '%s %d. %02d:%02d' % (months[lt.tm_mon - 1], lt.tm_mday, lt.tm_hour, lt.tm_min)
    except (ValueError, TypeError):
        return ''


def live():
    try:
        events = api.live_events()
    except api.ApiError as exc:
        fail(exc)
        end(cache=False)
        return
    if not events:
        notify('Most nincs élő vagy közelgő közvetítés')
    for e in events:
        if e['status'] == 'live':
            label = '[COLOR lime]● ÉLŐ[/COLOR]  %s' % e['title']
        else:
            label = '[COLOR silver]%s[/COLOR]  %s' % (_local(e['start']) or 'hamarosan', e['title'])
        if e['desc']:
            label += '  [COLOR gray]%s[/COLOR]' % e['desc']
        plot = '%s\n%s\nKezdés: %s' % (e['title'], e['desc'], _local(e['start']) or '-')
        add(label, url(action='playlive', slug=e['slug'], title=e['title']), e['thumb'],
            folder=False, plot=plot, playable=True)
    end(cache=False)


def collections():
    try:
        cols = api.collections()
    except api.ApiError as exc:
        fail(exc)
        end(cache=False)
        return
    for c in cols:
        add(c['title'], url(action='collection', slug=c['slug']), c['thumb'])
    end('files')


PAGE = 30


def _vod_items(vods, start=0):
    for v in vods[start:start + PAGE]:
        label = v['title'] + ('  [COLOR gray]%s[/COLOR]' % v['desc'] if v['desc'] else '')
        add(label, url(action='playvod', u=v['url'], title=v['title']), v['thumb'],
            folder=False, plot=v['plot'] or v['desc'], playable=True)


def collection(slug, start):
    try:
        vods = api.collection_items(slug)
    except api.ApiError as exc:
        fail(exc)
        end(cache=False)
        return
    if not vods:
        notify('Ebben a gyűjteményben nincs videó')
    _vod_items(vods, start)
    if start + PAGE < len(vods):
        add('[B]Tovább >>[/B]  (%d-%d / %d)' % (start + PAGE + 1,
                                                min(start + 2 * PAGE, len(vods)), len(vods)),
            url(action='collection', slug=slug, start=start + PAGE), 'DefaultFolder.png')
    end()


def search(term=None):
    term = term or xbmcgui.Dialog().input('Keresés (Network4)')
    if not term:
        end(cache=False)
        return
    try:
        vods = api.search(term)
    except api.ApiError as exc:
        fail(exc)
        end(cache=False)
        return
    if not vods:
        notify('Nincs találat: %s' % term)
    _vod_items(vods, 0)
    end(cache=False)


# ---------------------------------------------------------------------------
# Lejátszás
# ---------------------------------------------------------------------------
def _kodi_major():
    try:
        return int(xbmc.getInfoLabel('System.BuildVersion').split('.')[0])
    except ValueError:
        return 21


def resolve(stream, title):
    li = xbmcgui.ListItem(path=stream + '|User-Agent=%s' % quote(api.FIREFOX_UA, ''))
    _info(li, title)
    low = stream.lower().split('?')[0]
    if api.ADDON.getSetting('use_ia') != 'false' and (low.endswith('.mpd') or
                                                      low.endswith('.m3u8')):
        li.setPath(stream)
        li.setProperty('inputstream', 'inputstream.adaptive')
        headers = 'User-Agent=%s' % quote(api.FIREFOX_UA, '')
        li.setProperty('inputstream.adaptive.stream_headers', headers)
        li.setProperty('inputstream.adaptive.manifest_headers', headers)
        if low.endswith('.mpd'):
            if _kodi_major() < 21:
                li.setProperty('inputstream.adaptive.manifest_type', 'mpd')
            li.setMimeType('application/dash+xml')
            lic = api.ADDON.getSetting('license_url') or DEFAULT_LICENSE
            li.setProperty('inputstream.adaptive.license_type', 'com.widevine.alpha')
            li.setProperty('inputstream.adaptive.license_key',
                           '%s|%s|R{SSM}|' % (lic, headers))
        else:
            if _kodi_major() < 21:
                li.setProperty('inputstream.adaptive.manifest_type', 'hls')
            li.setMimeType('application/vnd.apple.mpegurl')
        li.setContentLookup(False)
    api.log('Lejátszás: %s' % stream.split('?')[0])
    xbmcplugin.setResolvedUrl(HANDLE, True, li)


def play_vod(viewer, title):
    try:
        stream = api.vod_stream(viewer)
    except api.ApiError as exc:
        fail(exc)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    resolve(stream, title)


def play_live(slug, title):
    try:
        src = api.live_sources(slug)
    except api.ApiError as exc:
        fail(exc)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    stream = src.get('live')
    if src.get('replay') and api.ADDON.getSetting('ask_replay') != 'false':
        sel = xbmcgui.Dialog().select(title, ['Élő (most)', 'Kezdés az elejéről'])
        if sel < 0:
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
            return
        if sel == 1:
            stream = src['replay']
    if not stream:
        notify('Ez a közvetítés még nem indult el')
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    resolve(stream, title)


# ---------------------------------------------------------------------------
# Egyéb
# ---------------------------------------------------------------------------
def diag():
    lines = ['User-Agent (API): %s' % api.api_user_agent(),
             'Mai kérések: %d' % api.today_requests()]
    if not api.have_credentials():
        lines.append('[COLOR red]Nincs megadva email / jelszó[/COLOR]')
    else:
        try:
            had = bool(api.saved_token())
            events = api.live_events()
            lines.append('[COLOR lime]Belépve[/COLOR] (%s)' % ('mentett token' if had else
                                                               'most léptünk be'))
            lines.append('Élő / közelgő közvetítés: %d' % len(events))
        except api.ChallengeError:
            lines.append('[COLOR red]Cloudflare-kihívás[/COLOR] - próbáld a mobilalkalmazás '
                         'User-Agentet a beállításokban')
        except api.ApiError as exc:
            lines.append('[COLOR red]Hiba:[/COLOR] %s' % exc)
    xbmcgui.Dialog().textviewer(NAME + ' - kapcsolat', '\n'.join(lines))


def router():
    a = PARAMS.get('action')
    if not a:
        root()
    elif a == 'live':
        live()
    elif a == 'collections':
        collections()
    elif a == 'collection':
        collection(PARAMS.get('slug', ''), int(PARAMS.get('start', 0) or 0))
    elif a == 'search':
        search(PARAMS.get('q'))
    elif a == 'playvod':
        play_vod(PARAMS.get('u', ''), PARAMS.get('title', ''))
    elif a == 'playlive':
        play_live(PARAMS.get('slug', ''), PARAMS.get('title', ''))
    elif a == 'diag':
        diag()
    elif a == 'settings':
        api.ADDON.openSettings()
    elif a == 'clearsession':
        api.clear_token()
        notify('Munkamenet törölve - a következő kérésnél újra belép')
    elif a == 'clearcache':
        notify('%d gyorsítótár-fájl törölve' % api.clear_cache())


if __name__ == '__main__':
    router()
