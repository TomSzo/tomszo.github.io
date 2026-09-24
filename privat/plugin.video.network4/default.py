# -*- coding: utf-8 -*-
"""Network4 - Kodi videó plugin belépési pont (router)."""
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

from resources.lib import network4 as n4

ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE = sys.argv[0]
IA = 'inputstream.adaptive'
DRM = 'com.widevine.alpha'


def build_url(**kw):
    return BASE + '?' + urlencode(kw)


def add_dir(label, url, folder=True, art=None, playable=False, plot=None):
    li = xbmcgui.ListItem(label=label)
    icon = ADDON.getAddonInfo('icon')
    li.setArt({'icon': art or icon, 'thumb': art or icon, 'poster': art,
               'fanart': art or ADDON.getAddonInfo('fanart')})
    vinfo = {'title': label, 'mediatype': 'video'}
    if plot:
        vinfo['plot'] = plot
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
    xbmcgui.Dialog().notification(ADDON.getAddonInfo('name'), msg,
                                  ADDON.getAddonInfo('icon'), t)


# --------------------------------------------------------------------------
def view_root():
    if not n4.have_credentials():
        add_dir('[COLOR red]! Add meg az email/jelszó párost a beállításokban[/COLOR]',
                build_url(action='opensettings'), folder=False)
    for i, (name, items) in enumerate(n4.collections_page()):
        label = '[COLOR gold]★ %s[/COLOR]' % name if i == 0 else name
        add_dir('%s  [COLOR grey](%d)[/COLOR]' % (label, len(items)),
                build_url(action='cat', i=str(i)))
    add_dir('Sport műsorújság (EPG)', build_url(action='page', path='sport/epg'))
    add_dir('Oldal megnyitása linkkel / slug-gal', build_url(action='manual'),
            folder=False)
    add_dir('[COLOR yellow]Kapcsolat teszt (bejelentkezés ellenőrzése)[/COLOR]',
            build_url(action='diag'), folder=False)
    add_dir('[COLOR grey]Oldal mentése hibakereséshez[/COLOR]',
            build_url(action='dump'), folder=False)
    end('files')


def view_cat(i):
    cats = n4.collections_page()
    try:
        _, items = cats[int(i)]
    except (ValueError, IndexError):
        items = []
    for c in items:
        add_dir(c['title'], build_url(action='coll', slug=c['slug']), art=c.get('art'))
    end('files')


def view_coll(slug):
    watch, subs = n4.collection_items(slug)
    for c in subs:
        add_dir('[COLOR grey]» %s[/COLOR]' % c['title'],
                build_url(action='coll', slug=c['slug']), art=c.get('art'))
    _list_watch(watch)


def view_page(path):
    _list_watch(n4.page_items(path))


def _list_watch(items):
    if not items:
        notify('Nincs adás – az oldalt a hibakereső mappába mentettem', t=8000)
    for it in items:
        add_dir(it['title'], build_url(action='play', slug=it['slug']),
                folder=False, playable=True, art=it.get('art'))
    end('videos')


def view_diag():
    ok, who, length, keys = n4.check_login()
    lines = ['Alap URL: %s' % n4.base_url(),
             'Belépési adat forrása: %s' % n4.cred_source(),
             'Email/jelszó megadva: %s' % ('igen' if n4.have_credentials() else 'NEM'),
             'Főoldal betöltve: %d byte' % length,
             'Bejelentkezve: %s' % ('IGEN' if ok else 'NEM'),
             'Felhasználó: %s' % (who or '—'),
             'user-session kulcsok: %s' % (keys or '—'),
             'inputstream.adaptive: %s' % (_ia_version() or 'NINCS telepítve'),
             'Hibakereső mappa: %s' % n4.debug_dir()]
    if not ok:
        lines += ['', 'Ha NEM vagy bejelentkezve: ellenőrizd az email/jelszót. A sikertelen '
                  'belépés oldalát a hibakereső mappába mentettem (login_result.html).']
    xbmcgui.Dialog().textviewer(ADDON.getAddonInfo('name') + ' – teszt', '\n'.join(lines))


def _ask_slug():
    kb = xbmc.Keyboard(ADDON.getSetting('last_slug') or '',
                       'network4.hu/sport/watch/... link vagy slug')
    kb.doModal()
    if not kb.isConfirmed() or not kb.getText().strip():
        return ''
    s = kb.getText().strip()
    ADDON.setSetting('last_slug', s)
    return s


def view_manual():
    s = _ask_slug()
    if s:
        xbmc.executebuiltin('PlayMedia(%s)' % build_url(action='play', slug=s))


def view_dump():
    s = _ask_slug()
    if not s:
        return
    if s.startswith('http') or '/' in s.strip('/'):
        page = s if s.startswith('http') else s.lstrip('/')
    else:
        page = n4.KIND_WATCH + s
    html = n4.get(page)
    slug = page.rstrip('/').split('/')[-1]
    p1 = n4.save_debug('page_%s.html' % slug, html)
    p2 = n4.save_debug('user-session_%s.json' % slug, n4.get('user-session', ajax=True))
    f = n4.find_streams(html)
    xbmcgui.Dialog().textviewer('Mentve', '\n'.join([
        'Bejelentkezve: %s' % ('IGEN' if n4.logged_in(html) else 'NEM'),
        'Oldal: %s (%d byte)' % (p1, len(html or '')), 'user-session: %s' % p2, '',
        'Talált .mpd: %d, .m3u8: %d, licenc URL: %d, Uplynk cid: %s' % (
            len(f['mpd']), len(f['hls']), len(f['license']), ', '.join(f['cid']) or '—'),
        '', 'A fájlokat a Kodi fájlkezelőjével (profil mappa -> addon_data) vagy SMB-n '
        'keresztül tudod kimásolni. Jelszót és sütit NEM tartalmaznak.']))


# --------------------------------------------------------------------------
def _ia_version():
    try:
        return xbmcaddon.Addon(IA).getAddonInfo('version')
    except Exception:  # noqa
        return ''


def _ver_tuple(v):
    out = []
    for p in (v or '0').split('.')[:3]:
        try:
            out.append(int(''.join(c for c in p if c.isdigit()) or 0))
        except ValueError:
            out.append(0)
    return tuple(out + [0] * (3 - len(out)))


def _check_helper(mtype, drm):
    """Nem-Android rendszeren (CoreELEC) az inputstreamhelper telepíti/ellenőrzi a
    Widevine CDM-et. Androidon a rendszer hivatalos Widevine-ja van, ott kihagyjuk."""
    if xbmc.getCondVisibility('System.Platform.Android'):
        return True
    try:
        import inputstreamhelper
    except ImportError:
        return True
    try:
        return inputstreamhelper.Helper('mpd' if mtype == 'mpd' else 'hls',
                                        drm=drm).check_inputstream()
    except Exception as exc:  # noqa
        n4.log('inputstreamhelper hiba: %s' % exc, xbmc.LOGWARNING)
        return True


def play(slug):
    src = n4.resolve(slug)
    if src.get('error'):
        msg = src['error']
        if src.get('debug'):
            msg += '\n\nAz oldalt elmentettem:\n%s' % src['debug']
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'), msg)
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    ia_ver = _ia_version()
    if not ia_ver:
        xbmcgui.Dialog().ok(ADDON.getAddonInfo('name'),
                            'Az inputstream.adaptive nincs telepítve/engedélyezve.')
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    lic = src.get('license')
    if lic and not _check_helper(src['type'], DRM):
        xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    headers = n4.play_headers(src.get('referer'))
    li = xbmcgui.ListItem(path=src['manifest'])
    li.setInfo('video', {'title': src.get('title') or slug, 'mediatype': 'video'})
    if src.get('poster'):
        li.setArt({'thumb': src['poster'], 'poster': src['poster'], 'fanart': src['poster']})
    li.setMimeType('application/dash+xml' if src['type'] == 'mpd'
                   else 'application/vnd.apple.mpegurl')
    li.setContentLookup(False)
    li.setProperty('inputstream', IA)
    v = _ver_tuple(ia_ver)
    if v < (21, 0, 0):
        li.setProperty('inputstream.adaptive.manifest_type', src['type'])
    li.setProperty('inputstream.adaptive.manifest_headers', headers)
    li.setProperty('inputstream.adaptive.stream_headers', headers)
    if lic:
        if v >= (21, 4, 4):
            li.setProperty('inputstream.adaptive.drm_legacy',
                           '%s|%s|%s' % (DRM, lic, headers))
        else:
            li.setProperty('inputstream.adaptive.license_type', DRM)
            li.setProperty('inputstream.adaptive.license_key',
                           '%s|%s&Content-Type=application%%2Foctet-stream|R{SSM}|'
                           % (lic, headers))
    n4.log('Lejátszás: %s (IA %s, licenc: %s)' % (src['manifest'], ia_ver, lic or '-'))
    xbmcplugin.setResolvedUrl(HANDLE, True, li)


def router(qs):
    p = dict(parse_qsl(qs))
    action = p.get('action')
    if not action:
        view_root()
    elif action == 'cat':
        view_cat(p.get('i', '0'))
    elif action == 'coll':
        view_coll(p['slug'])
    elif action == 'page':
        view_page(p.get('path', 'sport/epg'))
    elif action == 'list':  # 0.1.0 kompatibilitás
        view_page(p.get('path', 'sport'))
    elif action == 'manual':
        view_manual()
    elif action == 'dump':
        view_dump()
    elif action == 'diag':
        view_diag()
    elif action == 'clearsession':
        n4.clear_cookies()
        notify('Munkamenet törölve – következő lekéréskor újra bejelentkezik')
    elif action == 'play':
        play(p['slug'])
    elif action == 'opensettings':
        ADDON.openSettings()
    else:
        view_root()


if __name__ == '__main__':
    router(sys.argv[2][1:] if len(sys.argv) > 2 else '')
