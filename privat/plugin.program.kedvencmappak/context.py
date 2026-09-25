# -*- coding: utf-8 -*-
"""Helyi menü: "Kedvenc mappába..." - az aktuális elem elhelyezése egy mappában."""
import sys

import xbmc
import xbmcgui

from resources.lib import store


def _info():
    li = getattr(sys, 'listitem', None)

    def lab(name):
        return xbmc.getInfoLabel('ListItem.%s' % name)

    path = ''
    label = ''
    thumb = ''
    fanart = ''
    if li is not None:
        try:
            path = li.getPath()
            label = li.getLabel()
            thumb = li.getArt('thumb') or li.getArt('poster') or li.getArt('icon')
            fanart = li.getArt('fanart')
        except Exception:  # noqa
            pass
    return {
        'label': label or lab('Label'),
        'path': path or lab('FileNameAndPath'),
        'folderpath': lab('FolderPath'),
        'isfolder': xbmc.getCondVisibility('ListItem.IsFolder'),
        'addon_id': lab('Property(Addon.ID)'),
        'thumb': thumb or lab('Art(thumb)') or lab('Art(poster)') or lab('Icon'),
        'fanart': fanart or lab('Art(fanart)'),
        'window_id': xbmcgui.getCurrentWindowId(),
        'container': xbmc.getInfoLabel('Container.FolderPath'),
    }


def main():
    info = _info()
    entry = store.entry_from_listitem(info)
    dialog = xbmcgui.Dialog()
    if not entry:
        dialog.notification('Kedvenc mappák', 'Ezt az elemet nem lehet elmenteni',
                            xbmcgui.NOTIFICATION_WARNING)
        return
    store.log('helyi menü: %s -> %s' % (info, entry))
    nodes = store.load()
    choices = store.folder_choices(nodes)
    labels = ['[B]+ Új mappa...[/B]'] + [c[1] for c in choices]
    sel = dialog.select('Kedvenc mappába: %s' % entry['label'], labels)
    if sel < 0:
        return
    if sel == 0:
        name = dialog.input('Új mappa neve')
        if not name:
            return
        parent = store.add_folder(nodes, name)['id']
        store.save(nodes)
        if store.ADDON.getSetting('ask_kodi_fav') != 'false' and dialog.yesno(
                'Kedvenc mappák', 'Kiteszed a(z) "%s" mappát a Kodi Kedvencek közé is?' % name):
            store.add_to_kodi_favourites(name, store.folder_url(parent), '')
    else:
        parent = choices[sel - 1][0]
    if store.is_duplicate(nodes, parent, entry):
        dialog.notification('Kedvenc mappák', 'Már benne van: %s' % entry['label'])
        return
    store.add_item(nodes, parent, entry)
    store.save(nodes)
    dialog.notification('Kedvenc mappák', '%s  →  %s' % (entry['label'],
                                                         store.folder_path(nodes, parent)),
                        store.ADDON.getAddonInfo('icon'), 3000)


if __name__ == '__main__':
    main()
