# -*- coding: utf-8 -*-
"""
Kedvenc mappák - mappák és almappák a kedvenceidnek.

    plugin://plugin.program.kedvencmappak/                  gyökér
    plugin://plugin.program.kedvencmappak/?folder=<id>      egy mappa tartalma
    ...?action=run&id=<id>                                  elem futtatása (parancs)
    ...?action=<művelet>&id=<id>                            szerkesztés (helyi menüből)
"""
import sys

try:
    from urllib.parse import parse_qsl, urlencode
except ImportError:  # py2
    from urlparse import parse_qsl
    from urllib import urlencode

import xbmc
import xbmcgui
import xbmcplugin

from resources.lib import store

URL = sys.argv[0]
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].lstrip('-').isdigit() else -1
PARAMS = dict(parse_qsl(sys.argv[2][1:])) if len(sys.argv) > 2 else {}
TITLE = 'Kedvenc mappák'


def url(**kw):
    return URL + '?' + urlencode(kw)


def notify(msg, t=3000):
    xbmcgui.Dialog().notification(TITLE, msg, store.ADDON.getAddonInfo('icon'), t)


def refresh():
    xbmc.executebuiltin('Container.Refresh')


def setting_on(key, default=True):
    v = store.ADDON.getSetting(key)
    return default if v == '' else v == 'true'


# ---------------------------------------------------------------------------
# Lista
# ---------------------------------------------------------------------------
def _ctx_common(n):
    nid = n['id']
    return [
        ('Átnevezés', 'RunPlugin(%s)' % url(action='rename', id=nid)),
        ('Ikon megváltoztatása', 'RunPlugin(%s)' % url(action='icon', id=nid)),
        ('Mozgatás fel', 'RunPlugin(%s)' % url(action='up', id=nid)),
        ('Mozgatás le', 'RunPlugin(%s)' % url(action='down', id=nid)),
        ('Áthelyezés másik mappába...', 'RunPlugin(%s)' % url(action='moveto', id=nid)),
    ]


def list_folder(fid):
    nodes = store.load()
    folder = store.get(nodes, fid) if fid else None
    if fid and not folder:
        notify('A mappa már nem létezik')
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)
        return
    parent = fid or ''
    kids = store.children(nodes, parent)
    # mappák elöl, a sorrend a tárolt sorrend
    for n in [k for k in kids if k['type'] == 'folder']:
        nf, ni = store.count(nodes, n['id'])
        li = xbmcgui.ListItem(n['label'])
        thumb = n.get('thumb') or store.FOLDER_ICON
        li.setArt({'thumb': thumb, 'icon': thumb, 'poster': thumb,
                   'fanart': n.get('fanart') or store.ADDON.getAddonInfo('fanart')})
        li.setLabel2('%d mappa, %d elem' % (nf, ni) if nf else '%d elem' % ni)
        tag = li.getVideoInfoTag() if hasattr(li, 'getVideoInfoTag') else None
        if tag:
            tag.setPlot('%d almappa, %d elem' % (nf, ni))
        ctx = [('Új almappa itt...', 'RunPlugin(%s)' % url(action='newfolder', parent=n['id'])),
               ('Kitűzés a Kodi Kedvencek közé', 'RunPlugin(%s)' % url(action='pin', id=n['id']))]
        ctx += _ctx_common(n)
        ctx.append(('[COLOR red]Mappa törlése[/COLOR]',
                    'RunPlugin(%s)' % url(action='delete', id=n['id'])))
        li.addContextMenuItems(ctx)
        xbmcplugin.addDirectoryItem(HANDLE, store.folder_url(n['id']), li, True)
    for n in [k for k in kids if k['type'] == 'item']:
        li = xbmcgui.ListItem(n['label'])
        art = {'thumb': n.get('thumb') or 'DefaultFile.png', 'icon': n.get('thumb') or
               'DefaultFile.png'}
        if n.get('fanart'):
            art['fanart'] = n['fanart']
        li.setArt(art)
        ctx = list(_ctx_common(n))
        ctx.append(('[COLOR red]Eltávolítás a mappából[/COLOR]',
                    'RunPlugin(%s)' % url(action='delete', id=n['id'])))
        li.addContextMenuItems(ctx)
        if n.get('kind') == 'dir' and n.get('path', '').startswith('plugin://'):
            # plugin-mappa: közvetlenül böngészhető (a Vissza gomb ide hoz vissza)
            xbmcplugin.addDirectoryItem(HANDLE, n['path'], li, True)
        else:
            li.setProperty('IsPlayable', 'false')
            xbmcplugin.addDirectoryItem(HANDLE, url(action='run', id=n['id']), li, False)
    if setting_on('show_tools'):
        _tool(u'[B]+ Új mappa[/B]', url(action='newfolder', parent=parent), 'DefaultAddSource.png')
        _tool(u'Kodi Kedvencek importálása ide...', url(action='import', parent=parent),
              'DefaultFavourites.png')
        if not fid:
            _tool(u'Mentés / visszaállítás...', url(action='backup'), 'DefaultAddonService.png')
    xbmcplugin.setPluginCategory(HANDLE, store.folder_path(nodes, fid) if fid else TITLE)
    xbmcplugin.setContent(HANDLE, 'files')
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=False)


def _tool(label, target, icon):
    li = xbmcgui.ListItem(label)
    li.setArt({'thumb': icon, 'icon': icon})
    li.setProperty('SpecialSort', 'bottom')
    xbmcplugin.addDirectoryItem(HANDLE, target, li, False)


# ---------------------------------------------------------------------------
# Műveletek
# ---------------------------------------------------------------------------
def run(nid):
    n = store.get(store.load(), nid)
    if not n:
        notify('Az elem már nem létezik')
        return
    if n.get('kind') == 'dir':
        cmd = 'ActivateWindow(%s,"%s",return)' % (n.get('window') or 'videos', n['path'])
    else:
        cmd = n.get('cmd', '')
    store.log('futtatás: %s' % cmd)
    xbmc.executebuiltin(cmd)


def new_folder(parent):
    d = xbmcgui.Dialog()
    name = d.input('Új mappa neve')
    if not name:
        return
    nodes = store.load()
    node = store.add_folder(nodes, name, parent)
    store.save(nodes)
    if not parent and setting_on('ask_kodi_fav') and d.yesno(
            TITLE, 'Kiteszed a(z) "%s" mappát a Kodi Kedvencek közé is?' % name):
        pin(node['id'])
    refresh()


def pin(nid):
    nodes = store.load()
    n = store.get(nodes, nid)
    if not n:
        return
    res = store.add_to_kodi_favourites(n['label'], store.folder_url(nid), n.get('thumb'))
    notify({'ok': 'Kitűzve a Kodi Kedvencek közé: %s' % n['label'],
            'exists': 'Már a Kodi Kedvencek között van',
            'error': 'Nem sikerült a Kodi Kedvencek közé tenni'}[res])


def rename(nid):
    nodes = store.load()
    n = store.get(nodes, nid)
    if not n:
        return
    name = xbmcgui.Dialog().input('Új név', n['label'])
    if name and name != n['label']:
        n['label'] = name
        store.save(nodes)
        refresh()


def change_icon(nid):
    nodes = store.load()
    n = store.get(nodes, nid)
    if not n:
        return
    d = xbmcgui.Dialog()
    opts = ['Kép választása fájlból...', 'Első elem képe', 'Alapértelmezett ikon']
    sel = d.select('Ikon: %s' % n['label'], opts)
    if sel == 0:
        img = d.browse(2, 'Kép választása', 'files', '.png|.jpg|.jpeg|.gif|.webp')
        if not img:
            return
        n['thumb'] = img
    elif sel == 1:
        first = [k for k in store.children(nodes, nid) if k.get('thumb')] if \
            n['type'] == 'folder' else []
        if not first:
            notify('Nincs képpel rendelkező elem a mappában')
            return
        n['thumb'] = first[0]['thumb']
    elif sel == 2:
        n['thumb'] = ''
    else:
        return
    store.save(nodes)
    refresh()


def move(nid, delta):
    nodes = store.move(store.load(), nid, delta)
    store.save(nodes)
    refresh()


def move_to(nid):
    nodes = store.load()
    n = store.get(nodes, nid)
    if not n:
        return
    choices = [('', '[B]Gyökér (Kedvenc mappák)[/B]')] + \
        store.folder_choices(nodes, exclude=nid if n['type'] == 'folder' else None)
    choices = [c for c in choices if c[0] != n.get('parent', '')]
    if not choices:
        return
    sel = xbmcgui.Dialog().select('Áthelyezés ide: %s' % n['label'], [c[1] for c in choices])
    if sel < 0:
        return
    store.save(store.reparent(nodes, nid, choices[sel][0]))
    refresh()


def delete(nid):
    nodes = store.load()
    n = store.get(nodes, nid)
    if not n:
        return
    if n['type'] == 'folder':
        nf, ni = store.count(nodes, nid)
        sub = len(store.descendants(nodes, nid))
        msg = 'Törlöd a(z) "%s" mappát?' % n['label']
        if sub:
            msg += '\nA tartalma is törlődik (%d elem / almappa).' % sub
        if not xbmcgui.Dialog().yesno(TITLE, msg):
            return
    elif setting_on('confirm_delete') and not xbmcgui.Dialog().yesno(
            TITLE, 'Eltávolítod: "%s"?' % n['label']):
        return
    store.save(store.remove(nodes, nid))
    refresh()


def import_kodi(parent):
    favs = store.kodi_favourites()
    if not favs:
        notify('A Kodi Kedvencek üres')
        return
    nodes = store.load()
    entries = [store.favourite_to_entry(f) for f in favs]
    pairs = [(f, e) for f, e in zip(favs, entries) if e and
             not (e.get('path') or '').startswith('plugin://%s' % store.ADDON_ID)]
    labels = []
    for f, e in pairs:
        li = xbmcgui.ListItem(f.get('title', ''))
        li.setArt({'thumb': f.get('thumbnail') or 'DefaultFavourites.png'})
        labels.append(li)
    sel = xbmcgui.Dialog().multiselect('Melyik kedvenceket teszed ide?', labels, useDetails=True)
    if not sel:
        return
    added = 0
    for i in sel:
        e = pairs[i][1]
        if not store.is_duplicate(nodes, parent, e):
            store.add_item(nodes, parent, e)
            added += 1
    store.save(nodes)
    notify('%d kedvenc importálva' % added)
    refresh()


def backup():
    import os
    d = xbmcgui.Dialog()
    sel = d.select('Mentés / visszaállítás', ['Mentés fájlba...', 'Visszaállítás fájlból...',
                                               'Visszaállítás az előző állapotra (.bak)'])
    src = store._path(store.DATA)
    if sel == 0:
        folder = d.browse(3, 'Hova mentsem?', 'files')
        if folder:
            target = os.path.join(folder, 'kedvencmappak_backup.json')
            ok = store.xbmcvfs.copy(src, target)
            notify('Mentve: %s' % target if ok else 'A mentés nem sikerült')
    elif sel in (1, 2):
        path = d.browse(1, 'Mentés kiválasztása', 'files', '.json') if sel == 1 else src + '.bak'
        if not path or not store.xbmcvfs.exists(path):
            if sel == 2:
                notify('Nincs korábbi állapot')
            return
        if not d.yesno(TITLE, 'A jelenlegi mappák felülíródnak. Folytatod?'):
            return
        store.xbmcvfs.copy(src, src + '.bak')
        store.xbmcvfs.copy(path, src)
        notify('Visszaállítva')
        refresh()


def router():
    action = PARAMS.get('action')
    nid = PARAMS.get('id', '')
    if not action:
        list_folder(PARAMS.get('folder', ''))
    elif action == 'run':
        run(nid)
    elif action == 'newfolder':
        new_folder(PARAMS.get('parent', ''))
    elif action == 'pin':
        pin(nid)
    elif action == 'rename':
        rename(nid)
    elif action == 'icon':
        change_icon(nid)
    elif action == 'up':
        move(nid, -1)
    elif action == 'down':
        move(nid, 1)
    elif action == 'moveto':
        move_to(nid)
    elif action == 'delete':
        delete(nid)
    elif action == 'import':
        import_kodi(PARAMS.get('parent', ''))
    elif action == 'backup':
        backup()


if __name__ == '__main__':
    router()
