# -*- coding: utf-8 -*-
"""Telekom TV GO - menük és lejátszás."""
import sys
import time

from urllib.parse import parse_qsl, urlencode, quote

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib import tvgo as api

URL = sys.argv[0]
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].lstrip('-').isdigit() else -1
PARAMS = dict(parse_qsl(sys.argv[2][1:])) if len(sys.argv) > 2 else {}
NAME = 'Telekom TV GO'
DAYS_BACK = 3        # a webes műsorújság is 3 napra visszamenőleg
DAYS_FORWARD = 3
WEEKDAYS = ('hétfő', 'kedd', 'szerda', 'csütörtök', 'péntek', 'szombat', 'vasárnap')


def url(**kw):
    return URL + '?' + urlencode(kw)


def notify(msg, t=4000):
    xbmcgui.Dialog().notification(NAME, msg, api.ADDON.getAddonInfo('icon'), t)


def _info(li, title, plot='', mediatype='video'):
    if hasattr(li, 'getVideoInfoTag'):
        tag = li.getVideoInfoTag()
        tag.setTitle(title)
        tag.setPlot(plot or title)
        tag.setMediaType(mediatype)
    else:  # Kodi 19
        li.setInfo('video', {'title': title, 'plot': plot or title, 'mediatype': mediatype})


def add(label, target, thumb='', folder=True, plot='', playable=False, fanart=''):
    li = xbmcgui.ListItem(label)
    icon = thumb or ('DefaultFolder.png' if folder else 'DefaultVideo.png')
    li.setArt({'thumb': icon, 'icon': icon, 'poster': icon,
               'fanart': fanart or api.ADDON.getAddonInfo('fanart')})
    if plot or playable:
        _info(li, label, plot)
    if playable:
        li.setProperty('IsPlayable', 'true')
    xbmcplugin.addDirectoryItem(HANDLE, target, li, folder)


def end(content='videos', cache=False):
    xbmcplugin.setContent(HANDLE, content)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=cache)


def fail(exc):
    if isinstance(exc, api.LoginError):
        xbmcgui.Dialog().ok(NAME, str(exc))
    else:
        notify('Hiba: %s' % exc, 6000)
    api.log('hiba: %s' % exc, xbmc.LOGWARNING)


def _hm(epoch):
    return time.strftime('%H:%M', time.localtime(epoch)) if epoch else '--:--'


# ---------------------------------------------------------------------------
# Menük
# ---------------------------------------------------------------------------
def root():
    if not api.have_credentials():
        add('[COLOR yellow]Add meg a Telekom-fiókod email címét és jelszavát (Beállítások)'
            '[/COLOR]', url(action='settings'), 'DefaultAddonService.png', folder=False)
    add('Élő TV', url(action='live'), 'DefaultTVShows.png')
    add('Műsorújság és visszanézés', url(action='guide'), 'DefaultYear.png')
    add('Kapcsolat teszt  [COLOR gray](ma %d kérés)[/COLOR]' % api.today_requests(),
        url(action='diag'), 'DefaultAddonService.png', folder=False)
    end('files')


def _now_map():
    """Csatornaszám -> most futó műsor (egy 3 órás sávból, gyorsítótárazva)."""
    out = {}
    if api.ADDON.getSetting('show_now') == 'false':
        return out
    now = time.time()
    lt = time.localtime(now)
    try:
        block = api._schedule_block(time.strftime('%Y-%m-%d', lt), (lt.tm_hour // 3) * 3,
                                    api.account())
    except api.ApiError as exc:
        api.log('Most futó műsorok nem tölthetők be: %s' % exc, xbmc.LOGWARNING)
        return out
    for p in block:
        if api.parse_time(p['start']) <= now < api.parse_time(p['end']):
            out[str(p['channel'])] = p
    return out


def live():
    try:
        chans = api.channels()
    except api.ApiError as exc:
        fail(exc)
        end()
        return
    now = _now_map()
    hide_radio = api.ADDON.getSetting('hide_radio') != 'false'
    for c in chans:
        if hide_radio and c['is_audio']:
            continue
        p = now.get(str(c['number']))
        label = '[B]%s[/B]  %s' % (c['number'], c['name'])
        plot = c['name']
        if p:
            label += '  [COLOR gray]%s-%s %s[/COLOR]' % (
                _hm(api.parse_time(p['start'])), _hm(api.parse_time(p['end'])), p['title'])
            plot = '%s\n[B]%s[/B]\n%s' % (c['name'], p['title'], p['desc'])
        add(label, url(action='playlive', ch=c['number'], name=c['name']), c['logo'],
            folder=False, plot=plot, playable=True, fanart=p and p.get('image') or '')
    end()


def guide():
    try:
        chans = api.channels()
    except api.ApiError as exc:
        fail(exc)
        end()
        return
    for c in chans:
        if c['is_audio']:
            continue
        add('[B]%s[/B]  %s' % (c['number'], c['name']),
            url(action='days', ch=c['number'], name=c['name'], logo=c['logo']), c['logo'])
    end('files')


def days(ch, name, logo):
    xbmcplugin.setPluginCategory(HANDLE, name)
    today = time.time()
    for d in range(-DAYS_BACK, DAYS_FORWARD + 1):
        t = today + d * 86400
        lt = time.localtime(t)
        rel = {0: 'Ma', -1: 'Tegnap', 1: 'Holnap'}.get(d, '')
        label = '%s%s %s' % (rel + ' - ' if rel else '', time.strftime('%m.%d.', lt),
                             WEEKDAYS[lt.tm_wday])
        if d == 0:
            label = '[B]%s[/B]' % label
        add(label, url(action='day', ch=ch, name=name, t=int(t)), logo)
    end('files')


def day(ch, name, t):
    xbmcplugin.setPluginCategory(HANDLE, name)
    try:
        progs = api.schedule_day(ch, t)
    except api.ApiError as exc:
        fail(exc)
        end()
        return
    if not progs:
        notify('Erre a napra nincs műsoradat')
    now = time.time()
    for p in progs:
        start, stop = api.parse_time(p['start']), api.parse_time(p['end'])
        title = p['title'] + (' - %s' % p['episode'] if p['episode'] and
                              p['episode'] != p['title'] else '')
        plot = '%s-%s  %s\n%s' % (_hm(start), _hm(stop), title, p['desc'])
        if start <= now < stop:
            label = '[COLOR lime]%s ● ÉLŐ[/COLOR]  %s' % (_hm(start), title)
            add(label, url(action='playlive', ch=ch, name=name, pid=p['program_id']),
                p['image'], folder=False, plot=plot, playable=True)
        elif stop <= now:
            label = '[COLOR silver]%s[/COLOR]  %s' % (_hm(start), title)
            add(label, url(action='playcatchup', pid=p['program_id'], st=p['station'],
                           s=p['start'], e=p['end'], title=title, ch=ch),
                p['image'], folder=False, plot=plot, playable=True)
        else:
            label = '[COLOR gray]%s  %s[/COLOR]' % (_hm(start), title)
            add(label, url(action='noop'), p['image'], folder=False, plot=plot)
    end()


# ---------------------------------------------------------------------------
# Lejátszás
# ---------------------------------------------------------------------------
def _kodi_major():
    try:
        return int(xbmc.getInfoLabel('System.BuildVersion').split('.')[0])
    except ValueError:
        return 21


def _hdr(d):
    return '&'.join('%s=%s' % (k, quote(str(v), '')) for k, v in d.items())


def _check_widevine():
    try:
        import inputstreamhelper
    except ImportError:
        return True
    try:
        return inputstreamhelper.Helper('mpd', drm='com.widevine.alpha').check_inputstream()
    except Exception as exc:  # noqa - a helper saját kivételei
        api.log('inputstreamhelper: %s' % exc, xbmc.LOGWARNING)
        return True


def _play(info, title):
    try:
        pb = api.Playback(info)
        manifest, lic, mk_headers, drm = pb.start()
    except api.ApiError as exc:
        fail(exc)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    if not _check_widevine():
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    stream_headers = _hdr({'User-Agent': api.UA, 'Origin': api.ORIGIN,
                           'Referer': api.ORIGIN + '/'})
    li = xbmcgui.ListItem(path=manifest)
    _info(li, title)
    li.setProperty('inputstream', 'inputstream.adaptive')
    if _kodi_major() < 21:
        li.setProperty('inputstream.adaptive.manifest_type', 'mpd')
    li.setMimeType('application/dash+xml')
    li.setContentLookup(False)
    li.setProperty('inputstream.adaptive.manifest_headers', stream_headers)
    li.setProperty('inputstream.adaptive.stream_headers', stream_headers)
    if (drm or 'widevine').lower() != 'none':
        lic_headers = dict(mk_headers)       # mint az SDK: ugyanazok a fejlécek
        li.setProperty('inputstream.adaptive.license_type', 'com.widevine.alpha')
        li.setProperty('inputstream.adaptive.license_key',
                       '%s|%s|R{SSM}|' % (lic, _hdr(lic_headers)))
    xbmcplugin.setResolvedUrl(HANDLE, True, li)
    _keep_alive(pb)


def _keep_alive(pb):
    """Életjel (beacon) küldése, amíg a lejátszás tart - különben a szerver leállíthatja."""
    interval = pb.beacon_interval
    if not interval:
        return
    if interval > 1000:          # ezredmásodperc
        interval //= 1000
    interval = max(15, int(interval))
    monitor = xbmc.Monitor()
    player = xbmc.Player()
    waited = 0
    while not player.isPlaying() and waited < 30 and not monitor.abortRequested():
        monitor.waitForAbort(1)
        waited += 1

    def playing_file():
        try:
            return player.getPlayingFile()
        except RuntimeError:
            return ''

    # csak amíg a MI streamünk megy (csatornaváltáskor az új indítás viszi tovább)
    mine = playing_file()
    last = time.time()
    while player.isPlaying() and playing_file() == mine and not monitor.abortRequested():
        if monitor.waitForAbort(1):
            break
        if time.time() - last >= interval:
            pb.beacon()
            last = time.time()
    pb.beacon(complete=True)
    api.log('Lejátszás vége, munkamenet lezárva')


def play_live(ch, name, pid=None):
    try:
        if not pid:
            cur = api.now_playing(ch)
            pid = cur and cur.get('program_id')
        info = api.playinfo_live(ch, pid)
    except api.ApiError as exc:
        fail(exc)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    _play(info, name)


def play_catchup(pid, station, start, stop, title):
    try:
        info = api.playinfo_catchup(pid, station, start, stop)
    except api.ApiError as exc:
        fail(exc)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    _play(info, title)


# ---------------------------------------------------------------------------
# Egyéb
# ---------------------------------------------------------------------------
def diag():
    lines = ['Eszköz-azonosító: %s' % api.device_id(),
             'Mai kérések: %d' % api.today_requests()]
    if not api.have_credentials():
        lines.append('[COLOR red]Nincs megadva email / jelszó[/COLOR]')
    else:
        try:
            had = bool(api.saved_token().get('access'))
            acc = api.account(force=True)
            lines.append('[COLOR lime]Belépve[/COLOR] (%s)' % ('mentett token' if had else
                                                               'most léptünk be'))
            lines.append('Csatornatérkép: %s' % acc.get('channelMap_id', '-'))
            lines.append('Lejátszó szerver: %s' % ('megvan' if acc.get('request_url') else
                                                   '[COLOR red]hiányzik[/COLOR]'))
            chans = api.channels(force=True)
            lines.append('Csatornák: %d' % len(chans))
        except api.ApiError as exc:
            lines.append('[COLOR red]Hiba:[/COLOR] %s' % exc)
    if api.ADDON.getSetting('debug_dump') == 'true':
        lines.append('')
        lines.append('Nyers válaszok mentése BE: %s' % api.profile())
    xbmcgui.Dialog().textviewer(NAME + ' - kapcsolat', '\n'.join(lines))


def router():
    a = PARAMS.get('action')
    if not a:
        root()
    elif a == 'live':
        live()
    elif a == 'guide':
        guide()
    elif a == 'days':
        days(PARAMS.get('ch', ''), PARAMS.get('name', ''), PARAMS.get('logo', ''))
    elif a == 'day':
        day(PARAMS.get('ch', ''), PARAMS.get('name', ''), int(PARAMS.get('t', 0) or 0))
    elif a == 'playlive':
        play_live(PARAMS.get('ch', ''), PARAMS.get('name', ''), PARAMS.get('pid'))
    elif a == 'playcatchup':
        play_catchup(PARAMS.get('pid', ''), PARAMS.get('st', ''), PARAMS.get('s', ''),
                     PARAMS.get('e', ''), PARAMS.get('title', ''))
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
