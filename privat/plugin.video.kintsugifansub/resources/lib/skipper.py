# -*- coding: utf-8 -*-
"""
Opening / ending automatikus átugrása (Muteki / Kintsugi).

A watch oldal lejátszója megadja az átugorható szakaszokat másodpercben:
    data-skip="73.97-164.02,1305.99-1395.96"
(1. szakasz: opening, 2.: ending; a data-has-scene-after-end="1" jelzi, hogy az ending
után még jelenet jön - ezért az ending VÉGÉRE ugrunk, nem a videó végére).

A lejátszás elindítása (setResolvedUrl) után a plugin figyeli a lejátszót, és amikor a
pozíció egy szakasz elejére ér, a szakasz végére teker. Minden szakaszt csak egyszer ugrik
át, így ha a néző visszatekerve újra meg akarja nézni, nem ugrik el megint.
"""
import re

import xbmc
import xbmcaddon

ADDON = xbmcaddon.Addon()
_SEG_RE = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*$')


def parse_skip(value):
    """'73.97-164.02,1305.99-1395.96' -> [(73.97, 164.02), (1305.99, 1395.96)]."""
    out = []
    for part in (value or '').split(','):
        m = _SEG_RE.match(part)
        if not m:
            continue
        a, b = float(m.group(1)), float(m.group(2))
        if b - a >= 3:          # értelmetlenül rövid szakaszt nem ugrunk
            out.append((a, b))
    return sorted(out)


def enabled():
    return (ADDON.getSetting('skip_segments') or 'true') == 'true'


def watch(segments, notify=None, start_timeout=40, window=4.0):
    """A lejátszás végéig fut: a szakaszok elején a végükre teker.

    window: a szakasz elejétől számított ennyi másodpercen belül ugrik (ha a néző a
    szakasz közepére teker, azt szándékosnak vesszük és nem ugrunk)."""
    if not segments:
        return
    player = xbmc.Player()
    monitor = xbmc.Monitor()
    # 1) megvárjuk, hogy a lejátszás elinduljon
    waited = 0.0
    while not player.isPlayingVideo():
        if monitor.waitForAbort(0.5):
            return
        waited += 0.5
        if waited > start_timeout:
            return
    try:
        path = player.getPlayingFile()
    except Exception:  # noqa
        path = ''
    try:
        total = player.getTotalTime() or 0
    except Exception:  # noqa
        total = 0
    done = set()
    # 2) figyelés, amíg ugyanaz a fájl szól
    while not monitor.abortRequested() and player.isPlayingVideo():
        try:
            if path and player.getPlayingFile() != path:
                return          # közben másik videó indult
            t = player.getTime()
        except Exception:  # noqa
            return
        for i, (a, b) in enumerate(segments):
            if i in done:
                continue
            if a <= t < min(b, a + window):
                done.add(i)
                try:
                    player.seekTime(b)
                except Exception:  # noqa
                    pass
                if notify:
                    first_half = (a < total / 2) if total else (i == 0)
                    notify('Opening átugorva' if first_half else 'Ending átugorva')
            elif t >= b:
                done.add(i)     # már túl vagyunk rajta (pl. folytatásnál)
        if len(done) == len(segments):
            return
        if monitor.waitForAbort(0.5):
            return
