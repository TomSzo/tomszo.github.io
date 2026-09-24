# -*- coding: utf-8 -*-
"""Muteki Fansub - Kodi videó plugin belépési pont (router)."""
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

from resources.lib import mutekifansub as mtk

ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
BASE = sys.argv[0]

# A minőség-beállítás enum indexei (settings.xml sorrendjével EGYEZŐ):
# 0 Automatikus (legjobb) | 1 Mindig kérdezzen | 2 4K | 3 2K | 4 1080p | 5 720p | 6 480p
_QUALITY_WANT = {2: '4K', 3: '2K', 4: '1080p', 5: '720p', 6: '480p'}


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
    xbmcgui.Dialog().notification(ADDON.getAddonInfo('name'), msg,
                                  ADDON.getAddonInfo('icon'), t)


def _creds_ok():
    return mtk.have_credentials()


# --------------------------------------------------------------------------
def view_root():
    if not _creds_ok():
        add_dir('[COLOR red]! Add meg az email/jelszó párost a beállításokban[/COLOR]',
                build_url(action='opensettings'), folder=False)
    add_dir('[COLOR gold]★ Legfrissebb részek[/COLOR]', build_url(action='latest'))
    add_dir('Projektek (böngészés)', build_url(action='projmenu'))
    add_dir('Keresés', build_url(action='search'))
    add_dir('[COLOR yellow]Kapcsolat teszt (bejelentkezés ellenőrzése)[/COLOR]',
            build_url(action='diag'), folder=False)
    end('files')


def view_diag():
    ok, name, length = mtk.check_login()
    lines = ['Alap URL: %s' % mtk.base_url(),
             'Belépési adat forrása: %s' % mtk.cred_source(),
             'Email/jelszó megadva: %s' % ('igen' if _creds_ok() else 'NEM'),
             'Főoldal betöltve: %d byte' % length,
             'Bejelentkezve: %s' % ('IGEN' if ok else 'NEM'),
             'Felhasználó: %s' % (name or '—'),
             'User-Agent: %s' % mtk.user_agent()]
    if not ok:
        lines.append('')
        lines.append('Ha NEM vagy bejelentkezve: ellenőrizd az email/jelszót a '
                     'beállításokban. A "Munkamenet törlése" gomb után újra próbál belépni.')
    xbmcgui.Dialog().textviewer(ADDON.getAddonInfo('name') + ' – teszt', '\n'.join(lines))
    end('files')


def view_latest():
    eps = mtk.latest_episodes()
    if not eps:
        notify('Nincs friss rész (be vagy jelentkezve? email/jelszó helyes?)')
    for e in eps:
        add_dir(e['title'], build_url(action='play', ep=e['id']),
                folder=False, playable=True, art=e.get('art'),
                info={'mediatype': 'episode'})
    end('episodes')


def view_projmenu():
    add_dir('[COLOR gold]▶ Aktív projektek[/COLOR]',
            build_url(action='status', s='active'))
    add_dir('Befejezett projektek', build_url(action='status', s='finished'))
    add_dir('Tervezett projektek', build_url(action='status', s='planned'))
    add_dir('Felfüggesztett projektek', build_url(action='status', s='suspended'))
    add_dir('Összes projekt (A→Z)', build_url(action='allproj'))
    add_dir('Szezon szerint', build_url(action='seasons'))
    add_dir('Műfaj szerint', build_url(action='genres'))
    add_dir('[COLOR grey]Projekt-gyorsítótár frissítése[/COLOR]',
            build_url(action='refreshcache'), folder=False)
    end('files')


def _list_projects(items, content='tvshows'):
    if not items:
        notify('Nincs találat (vagy nincs bejelentkezve)')
    for p in items:
        label = p['title']
        if p.get('episodes'):
            label = '%s  [COLOR grey](%s)[/COLOR]' % (label, p['episodes'])
        add_dir(label, build_url(action='project', slug=p['slug']),
                art=p.get('art'), plot=p.get('plot'),
                info={'mediatype': 'tvshow'})
    end(content)


def view_status(s):
    _list_projects(mtk.projects_by_status(s))


def view_allproj():
    _list_projects(sorted(mtk.projects_all(), key=lambda p: p['title'].lower()))


def view_seasons():
    seasons, _ = mtk.filters_meta()
    if not seasons:
        notify('Nem sikerült betölteni a szezonokat')
    for key, label in seasons:
        if label.strip():
            add_dir(label, build_url(action='season', key=key))
    end('files')


def view_season(key):
    _list_projects(mtk.projects_by_season(key))


def view_genres():
    _, genres = mtk.filters_meta()
    if not genres:
        notify('Nem sikerült betölteni a műfajokat')
    for g in genres:
        add_dir(g[:1].upper() + g[1:], build_url(action='genre', g=g))
    end('files')


def view_genre(g):
    _list_projects(mtk.projects_by_genre(g))


def view_project(slug):
    data = mtk.project_episodes(slug)
    eps = data.get('episodes') or []
    plot = data.get('plot') or ''
    if not eps:
        notify('Nincs epizód (vagy nincs bejelentkezve)')
    for ep in eps:
        add_dir(ep['title'], build_url(action='play', ep=ep['id']),
                folder=False, playable=True, art=ep.get('thumb'),
                plot=plot, info={'mediatype': 'episode'})
    end('episodes')


def view_search():
    kb = xbmc.Keyboard('', 'Projekt keresése')
    kb.doModal()
    if not kb.isConfirmed() or not kb.getText().strip():
        end()
        return
    _list_projects(mtk.search_projects(kb.getText().strip()))


def _choose_quality(qualities):
    """Visszaad: (label, url) vagy (None, None) ha megszakítva/nincs."""
    if not qualities:
        return (None, None)
    pref = 0
    try:
        pref = int(ADDON.getSetting('quality') or 0)
    except Exception:  # noqa
        pref = 0
    if pref == 1:  # Mindig kérdezzen
        labels = ['%s' % l for l, _ in qualities]
        i = xbmcgui.Dialog().select('Minőség', labels)
        return qualities[i] if i >= 0 else (None, None)
    if pref in _QUALITY_WANT:
        l, u = mtk.quality_by_label(qualities, _QUALITY_WANT[pref])
        if u:
            return (l, u)
    return mtk.best_quality(qualities)


def play(ep_id):
    src = mtk.watch_sources(ep_id)
    qualities = src.get('qualities') or []
    label, url = _choose_quality(qualities)
    if not url:
        if qualities:
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())  # megszakítva
        else:
            notify('Nem sikerült a lejátszható forrás kinyerése (bejelentkezés?)', t=8000)
            xbmcplugin.setResolvedUrl(HANDLE, False, xbmcgui.ListItem())
        return
    headers = mtk.play_headers(src.get('referer'))
    li = xbmcgui.ListItem(path=url + '|' + headers)
    li.setInfo('video', {'title': src.get('title') or ('rész %s' % ep_id),
                         'mediatype': 'episode'})
    if src.get('poster'):
        li.setArt({'thumb': src['poster'], 'poster': src['poster']})
    if (ADDON.getSetting('subtitles') or 'true') == 'true':
        try:
            sp = mtk.download_subtitle(ep_id)
            if sp:
                li.setSubtitles([sp])
        except Exception as exc:  # noqa
            mtk.log('felirat hiba: %s' % exc, xbmc.LOGWARNING)
    mtk.log('Lejátszás [%s]: %s' % (label, url))
    xbmcplugin.setResolvedUrl(HANDLE, True, li)


def router(qs):
    p = dict(parse_qsl(qs))
    action = p.get('action')
    if not action:
        view_root()
    elif action == 'latest':
        view_latest()
    elif action == 'projmenu':
        view_projmenu()
    elif action == 'status':
        view_status(p.get('s', 'active'))
    elif action == 'allproj':
        view_allproj()
    elif action == 'seasons':
        view_seasons()
    elif action == 'season':
        view_season(p.get('key', ''))
    elif action == 'genres':
        view_genres()
    elif action == 'genre':
        view_genre(p.get('g', ''))
    elif action == 'project':
        view_project(p['slug'])
    elif action == 'search':
        view_search()
    elif action == 'diag':
        view_diag()
    elif action == 'refreshcache':
        mtk.projects_html(force=True)
        notify('Projekt-gyorsítótár frissítve')
        end('files')
    elif action == 'clearsession':
        mtk.clear_cookies()
        notify('Munkamenet törölve – következő lekéréskor újra bejelentkezik')
    elif action == 'play':
        play(p['ep'])
    elif action == 'opensettings':
        ADDON.openSettings()
        end('files')
    else:
        view_root()


if __name__ == '__main__':
    router(sys.argv[2][1:] if len(sys.argv) > 2 else '')
