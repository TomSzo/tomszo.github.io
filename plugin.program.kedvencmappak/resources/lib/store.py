# -*- coding: utf-8 -*-
"""
Kedvenc mappák - adattár és Kodi-segédek.

Az adatok az addon profil-mappájában: data.json
    {"version": 1, "nodes": [node, ...]}
Egy node (a lista sorrendje = a megjelenítés sorrendje):
    {"id": "a1b2c3", "parent": "" | <mappa id>, "type": "folder" | "item",
     "label": "...", "thumb": "...", "fanart": "...",
     # csak elemeknél:
     "kind": "dir" | "cmd",        # dir: böngészhető útvonal, cmd: Kodi builtin parancs
     "path": "plugin://...",        # dir esetén az útvonal
     "window": "videos",            # dir esetén melyik ablakban nyíljon (nem plugin:// útnál)
     "cmd": "PlayMedia(...)"}       # cmd esetén a futtatandó parancs
"""
import json
import os
import time
import uuid

try:
    from urllib.parse import unquote
except ImportError:  # py2
    from urllib import unquote

import xbmc
import xbmcaddon
import xbmcvfs

ADDON = xbmcaddon.Addon('plugin.program.kedvencmappak')
ADDON_ID = ADDON.getAddonInfo('id')
DATA = 'data.json'
FOLDER_ICON = 'DefaultFolder.png'


def log(msg, level=xbmc.LOGINFO):
    xbmc.log('[%s] %s' % (ADDON_ID, msg), level)


def _path(name):
    prof = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
    try:
        if not xbmcvfs.exists(prof):
            xbmcvfs.mkdirs(prof)
    except Exception:  # noqa
        pass
    return os.path.join(prof, name)


# ---------------------------------------------------------------------------
# Betöltés / mentés
# ---------------------------------------------------------------------------
def load():
    try:
        p = _path(DATA)
        if xbmcvfs.exists(p):
            f = xbmcvfs.File(p)
            try:
                data = json.loads(f.read() or '{}')
            finally:
                f.close()
            nodes = [n for n in data.get('nodes', []) if isinstance(n, dict) and n.get('id')]
            return nodes
    except Exception as exc:  # noqa
        log('data.json olvasási hiba: %s' % exc, xbmc.LOGERROR)
    return []


def save(nodes):
    p = _path(DATA)
    tmp = p + '.tmp'
    f = xbmcvfs.File(tmp, 'w')
    try:
        f.write(json.dumps({'version': 1, 'saved': int(time.time()), 'nodes': nodes},
                           ensure_ascii=False, indent=1))
    finally:
        f.close()
    # biztonságos csere: előbb a régi mentése .bak-ba
    try:
        if xbmcvfs.exists(p):
            xbmcvfs.copy(p, p + '.bak')
            xbmcvfs.delete(p)
        xbmcvfs.rename(tmp, p)
    except Exception:  # noqa
        xbmcvfs.copy(tmp, p)
        xbmcvfs.delete(tmp)


def new_id(nodes):
    ids = set(n['id'] for n in nodes)
    while True:
        i = uuid.uuid4().hex[:8]
        if i not in ids:
            return i


# ---------------------------------------------------------------------------
# Fa-műveletek
# ---------------------------------------------------------------------------
def get(nodes, nid):
    for n in nodes:
        if n['id'] == nid:
            return n
    return None


def children(nodes, parent):
    return [n for n in nodes if n.get('parent', '') == (parent or '')]


def folders(nodes):
    return [n for n in nodes if n['type'] == 'folder']


def descendants(nodes, nid):
    out, todo = [], [nid]
    while todo:
        cur = todo.pop()
        for n in nodes:
            if n.get('parent') == cur:
                out.append(n['id'])
                if n['type'] == 'folder':
                    todo.append(n['id'])
    return out


def folder_path(nodes, nid):
    """'Filmek / Akció' - a mappa teljes neve."""
    names, cur, guard = [], get(nodes, nid), 0
    while cur and guard < 50:
        names.append(cur['label'])
        cur = get(nodes, cur.get('parent', ''))
        guard += 1
    return ' / '.join(reversed(names))


def folder_choices(nodes, exclude=None):
    """[(id, 'Mappa / Almappa'), ...] ábécé szerint; exclude: ez és a leszármazottai kimarad."""
    skip = set()
    if exclude:
        skip = set(descendants(nodes, exclude)) | {exclude}
    out = [(n['id'], folder_path(nodes, n['id'])) for n in folders(nodes) if n['id'] not in skip]
    return sorted(out, key=lambda x: x[1].lower())


def add_folder(nodes, label, parent='', thumb=''):
    node = {'id': new_id(nodes), 'parent': parent or '', 'type': 'folder',
            'label': label, 'thumb': thumb or '', 'fanart': ''}
    nodes.append(node)
    return node


def add_item(nodes, parent, entry):
    node = dict(entry)
    node.update({'id': new_id(nodes), 'parent': parent or '', 'type': 'item'})
    nodes.append(node)
    return node


def is_duplicate(nodes, parent, entry):
    key = (entry.get('kind'), entry.get('path') or entry.get('cmd'))
    return any(n['type'] == 'item' and n.get('parent', '') == (parent or '') and
               (n.get('kind'), n.get('path') or n.get('cmd')) == key for n in nodes)


def remove(nodes, nid):
    gone = set(descendants(nodes, nid)) | {nid}
    return [n for n in nodes if n['id'] not in gone]


def move(nodes, nid, delta):
    """Fel (-1) / le (+1) a testvérek között."""
    node = get(nodes, nid)
    if not node:
        return nodes
    sibs = [i for i, n in enumerate(nodes) if n.get('parent', '') == node.get('parent', '')
            and n['type'] == node['type']]
    pos = [i for i in sibs if nodes[i]['id'] == nid][0]
    k = sibs.index(pos) + delta
    if 0 <= k < len(sibs):
        j = sibs[k]
        nodes[pos], nodes[j] = nodes[j], nodes[pos]
    return nodes


def reparent(nodes, nid, parent):
    node = get(nodes, nid)
    if node and parent != nid and parent not in descendants(nodes, nid):
        node['parent'] = parent or ''
        nodes.remove(node)
        nodes.append(node)      # az új mappa végére
    return nodes


def count(nodes, nid):
    kids = children(nodes, nid)
    return len([k for k in kids if k['type'] == 'folder']), len([k for k in kids
                                                                  if k['type'] == 'item'])


# ---------------------------------------------------------------------------
# JSON-RPC (Kodi Kedvencek)
# ---------------------------------------------------------------------------
def rpc(method, params=None):
    req = {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}}
    try:
        resp = json.loads(xbmc.executeJSONRPC(json.dumps(req)))
    except Exception as exc:  # noqa
        log('JSON-RPC hiba (%s): %s' % (method, exc), xbmc.LOGERROR)
        return None
    if 'error' in resp:
        log('JSON-RPC hiba (%s): %s' % (method, resp['error']), xbmc.LOGWARNING)
        return None
    return resp.get('result')


def kodi_favourites():
    res = rpc('Favourites.GetFavourites',
              {'properties': ['window', 'path', 'thumbnail', 'windowparameter']})
    return (res or {}).get('favourites') or []


def favourite_to_entry(fav):
    """Egy Kodi-kedvenc (JSON-RPC) -> elem."""
    t = fav.get('type')
    entry = {'label': fav.get('title', ''), 'thumb': fav.get('thumbnail', ''), 'fanart': ''}
    if t == 'media':
        entry.update(kind='cmd', cmd='PlayMedia("%s")' % fav.get('path', ''))
    elif t == 'window':
        param = fav.get('windowparameter') or ''
        if param.startswith('plugin://'):
            entry.update(kind='dir', path=param, window=fav.get('window') or 'videos')
        elif param:
            entry.update(kind='cmd', cmd='ActivateWindow(%s,"%s",return)'
                         % (fav.get('window'), param))
        else:
            entry.update(kind='cmd', cmd='ActivateWindow(%s)' % fav.get('window'))
    elif t == 'script':
        entry.update(kind='cmd', cmd='RunScript("%s")' % fav.get('path', ''))
    elif t == 'androidapp':
        entry.update(kind='cmd', cmd='StartAndroidActivity("%s")' % fav.get('path', ''))
    else:
        return None
    return entry


def folder_url(nid):
    return 'plugin://%s/?folder=%s' % (ADDON_ID, nid)


def in_kodi_favourites(url):
    return any((f.get('windowparameter') or '').rstrip('/') == url.rstrip('/')
               for f in kodi_favourites())


def add_to_kodi_favourites(title, url, thumb):
    """Mappa kitűzése a Kodi Kedvencek közé. (Az AddFavourite váltó művelet: ha már
    benne van, kivenné - ezért előbb ellenőrzünk.)"""
    if in_kodi_favourites(url):
        return 'exists'
    res = rpc('Favourites.AddFavourite', {'title': title, 'type': 'window', 'window': 'videos',
                                          'windowparameter': url,
                                          'thumbnail': thumb or ADDON.getAddonInfo('icon')})
    return 'ok' if res == 'OK' else 'error'


# ---------------------------------------------------------------------------
# Tetszőleges lista-elem -> tárolható bejegyzés (a helyi menühöz)
# ---------------------------------------------------------------------------
_WINDOWS = {10025: 'videos', 10502: 'music', 10001: 'programs', 10002: 'pictures',
            10040: 'addonbrowser', 10060: 'favouritesbrowser'}


def _window_for(path, window_id):
    p = path.lower()
    if p.startswith(('plugin://plugin.audio', 'musicdb://', 'library://music')):
        return 'music'
    if p.startswith(('plugin://plugin.program', 'plugin://script.')):
        return 'programs'
    if p.startswith(('plugin://plugin.image',)):
        return 'pictures'
    if p.startswith(('plugin://plugin.video', 'videodb://', 'library://video')):
        return 'videos'
    w = _WINDOWS.get(window_id)
    return w if w in ('videos', 'music', 'programs', 'pictures') else 'videos'


def entry_from_listitem(info):
    """info: {'label','path','folderpath','isfolder','addon_id','thumb','fanart',
    'window_id','container'} -> bejegyzés vagy None."""
    label = info.get('label') or ''
    path = info.get('path') or info.get('folderpath') or ''
    entry = {'label': label, 'thumb': info.get('thumb') or '', 'fanart': info.get('fanart') or ''}

    # 1) Kodi Kedvencek ablak: a pontos adatot a JSON-RPC adja (cím szerint)
    if info.get('window_id') == 10060 or path.startswith('favourites://'):
        for fav in kodi_favourites():
            if fav.get('title') == label:
                e = favourite_to_entry(fav)
                if e:
                    e['thumb'] = e.get('thumb') or entry['thumb']
                    return e
        if path.startswith('favourites://'):
            entry.update(kind='cmd', cmd=unquote(path[len('favourites://'):]))
            return entry
    # 2) addon (Kiegészítők böngésző / addon lista)
    aid = info.get('addon_id')
    if aid and (not path or path.startswith('addons://') or
                path.rstrip('/') == 'plugin://%s' % aid):
        entry.update(kind='cmd', cmd='RunAddon(%s)' % aid)
        return entry
    if not path:
        return None
    # 3) mappa
    if info.get('isfolder'):
        entry.update(kind='dir', path=path, window=_window_for(path, info.get('window_id')))
        return entry
    # 4) lejátszható / futtatható elem
    if path.startswith('script://') or path.lower().endswith('.py'):
        entry.update(kind='cmd', cmd='RunScript("%s")' % path.replace('script://', ''))
    else:
        entry.update(kind='cmd', cmd='PlayMedia("%s")' % path)
    return entry
