# -*- coding: utf-8 -*-
"""
Helyi könyvtár: Kedvencek és Előzmények (legutóbb nézett sorozatok).

Közös modul a TomSzo anime addonokban (MagyarAnime, Muteki, Kintsugi) - a fájl
mindhárom addonban azonos. Csak az addon profil-mappájába ír JSON-t, az oldallal
nem kommunikál (nem fogyaszt napi limitet, nem kell hozzá bejelentkezés).

Egy elem: {'key', 'title', 'art', 'params': {router-paraméterek}, 'last', 'ts'}
    key    - egyedi azonosító, pl. 'anime:123' vagy 'project:slug'
    params - ezekkel a paraméterekkel nyílik meg újra (pl. {'action': 'anime', 'aid': '123'})
    last   - (előzményeknél) a legutóbb elindított rész címe
"""
import json
import os
import time

import xbmc
import xbmcaddon
import xbmcvfs

ADDON = xbmcaddon.Addon()
FAVORITES = 'favorites.json'
HISTORY = 'history.json'
HISTORY_MAX = 50


def _path(name):
    prof = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
    try:
        if not xbmcvfs.exists(prof):
            xbmcvfs.mkdirs(prof)
    except Exception:  # noqa
        pass
    return os.path.join(prof, name)


def _load(name):
    try:
        p = _path(name)
        if not xbmcvfs.exists(p):
            return []
        f = xbmcvfs.File(p)
        try:
            raw = f.read()
        finally:
            f.close()
        data = json.loads(raw or '[]')
        return [d for d in data if isinstance(d, dict) and d.get('key')]
    except Exception as exc:  # noqa
        xbmc.log('[%s] %s olvasási hiba: %s' % (ADDON.getAddonInfo('id'), name, exc),
                 xbmc.LOGWARNING)
        return []


def _save(name, items):
    try:
        f = xbmcvfs.File(_path(name), 'w')
        try:
            f.write(json.dumps(items, ensure_ascii=False))
        finally:
            f.close()
    except Exception as exc:  # noqa
        xbmc.log('[%s] %s mentési hiba: %s' % (ADDON.getAddonInfo('id'), name, exc),
                 xbmc.LOGWARNING)


def _item(key, title, art, params):
    return {'key': key, 'title': title or key, 'art': art or '',
            'params': dict(params or {}), 'ts': int(time.time())}


# ---------------------------------------------------------------------------
# Kedvencek
# ---------------------------------------------------------------------------
def favorites():
    return _load(FAVORITES)


def is_favorite(key):
    return any(d['key'] == key for d in favorites())


def add_favorite(key, title, art, params):
    items = [d for d in favorites() if d['key'] != key]
    items.insert(0, _item(key, title, art, params))
    _save(FAVORITES, items)


def remove_favorite(key):
    _save(FAVORITES, [d for d in favorites() if d['key'] != key])


def toggle_favorite(key, title, art, params):
    """Visszaad: True, ha most került be; False, ha most került ki."""
    if is_favorite(key):
        remove_favorite(key)
        return False
    add_favorite(key, title, art, params)
    return True


# ---------------------------------------------------------------------------
# Előzmények (legutóbb megnyitott / nézett sorozatok, a legfrissebb elöl)
# ---------------------------------------------------------------------------
def history():
    return _load(HISTORY)


def add_history(key, title, art, params, last=None):
    """Sorozat megnyitása / rész indítása -> a lista elejére kerül.
    A korábbi 'last' (utoljára nézett rész) megmarad, ha most nincs új."""
    old = [d for d in history() if d['key'] == key]
    it = _item(key, title or (old[0]['title'] if old else ''),
               art or (old[0].get('art') if old else ''), params or (old[0]['params'] if old else {}))
    it['last'] = last or (old[0].get('last', '') if old else '')
    items = [it] + [d for d in history() if d['key'] != key]
    _save(HISTORY, items[:HISTORY_MAX])


def mark_played(key, episode_label):
    """Egy rész elindult: a sorozat 'last' mezője frissül és a lista elejére kerül."""
    if not key:
        return
    old = [d for d in history() if d['key'] == key]
    if old:
        add_history(key, old[0]['title'], old[0].get('art'), old[0]['params'], episode_label)


# A lejátszási URL-ek szándékosan NEM kapnak sorozat-paramétert (a Kodi a "megnézve"
# jelölést URL szerint tárolja, ne vesszenek el). Helyette a sorozat megnyitásakor
# elmentjük, melyik rész-azonosító melyik sorozathoz / címhez tartozik.
CURRENT = 'current.json'


def set_current(key, episodes):
    """episodes: {rész-azonosító: rész-cím} az éppen megnyitott sorozatból."""
    try:
        f = xbmcvfs.File(_path(CURRENT), 'w')
        try:
            f.write(json.dumps({'key': key, 'eps': {str(k): v for k, v in episodes.items()}},
                               ensure_ascii=False))
        finally:
            f.close()
    except Exception:  # noqa
        pass


def mark_played_id(ep_id, fallback_label=None):
    """Egy rész elindult: ha a legutóbb megnyitott sorozathoz tartozik, frissül az előzmény."""
    try:
        f = xbmcvfs.File(_path(CURRENT))
        try:
            cur = json.loads(f.read() or '{}')
        finally:
            f.close()
    except Exception:  # noqa
        return
    eps = cur.get('eps') or {}
    if cur.get('key') and str(ep_id) in eps:
        mark_played(cur['key'], fallback_label or eps[str(ep_id)])


def remove_history(key):
    _save(HISTORY, [d for d in history() if d['key'] != key])


def clear_history():
    _save(HISTORY, [])
