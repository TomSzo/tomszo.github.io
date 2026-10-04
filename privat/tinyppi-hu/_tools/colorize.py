#!/usr/bin/env python3
"""A signde PPI (tinyppi) fehér, egyszínű kodeklogóinak színes változata.

A logók fehér alakzatok átlátszó háttéren; a tinyppi egy színnel festi át őket. Itt a logókat
részekre bontjuk (szimbólum, felirat, alcím) és márkaszínekkel / átmenetekkel töltjük ki, a
kontúr (alfa) érintetlen marad, így a logók élesek maradnak.

Használat:  python3 colorize.py <bemeneti codecs mappa> <kimeneti mappa>
"""
import os
import sys
from PIL import Image

# --- színek és átmenetek --------------------------------------------------------------------
WHITE = [(255, 255, 255)]
GREY = [(190, 190, 198)]
DTS_ORANGE = [(255, 176, 32), (255, 110, 20), (230, 40, 30)]
ATMOS = [(64, 156, 255), (122, 92, 255), (190, 70, 230)]
TRUEHD = [(40, 150, 255), (20, 100, 230)]
DDPLUS = [(90, 210, 255), (40, 140, 255)]
DV = [(0, 210, 255), (150, 90, 255), (255, 60, 160), (255, 170, 40)]
HDR10P = [(255, 50, 50), (255, 170, 0), (250, 240, 40), (40, 210, 90), (40, 140, 255), (160, 80, 255)]
GOLD = [(255, 220, 110), (225, 160, 40)]
IMAX_BLUE = [(40, 160, 255), (0, 100, 220)]
GREEN = [(110, 220, 120), (40, 170, 80)]
AMBER = [(255, 200, 80), (240, 140, 30)]

# logónként: a részek színe.  Részek:  'sym' = bal oldali szimbólum, 'word' = felső sor többi
# része, 'sub' = alcím (alsó sor), 'all' = minden; 'right' = a felső sor utolsó eleme (pl. X)
SPEC = {
    'Dolby_Digital': {'sym': WHITE, 'word': WHITE, 'sub': GREY},
    'Dolby_Digital_Plus': {'sym': DDPLUS, 'word': WHITE, 'sub': DDPLUS},
    'Dolby_Digital_Plus_Atmos': {'sym': ATMOS, 'word': WHITE, 'sub': ATMOS},
    'Dolby_TrueHD': {'sym': TRUEHD, 'word': WHITE, 'sub': TRUEHD},
    'Dolby_TrueHD_Atmos': {'sym': ATMOS, 'word': WHITE, 'sub': ATMOS},
    'Dolby_Vision': {'sym': DV, 'word': WHITE, 'sub': WHITE},
    'Dolby_Vision_IMAX': {'sym': DV, 'word': WHITE, 'sub': IMAX_BLUE},
    'DTS': {'sym': DTS_ORANGE, 'word': WHITE},
    'DTS-ES': {'all': DTS_ORANGE},
    'DTS-96-24': {'all': DTS_ORANGE},
    'DTS-Express': {'sym': DTS_ORANGE, 'word': WHITE, 'sub': DTS_ORANGE},
    'DTS-HD-MA': {'sym': DTS_ORANGE, 'word': WHITE, 'sub': GREY},
    'DTS-HD-HRA': {'sym': DTS_ORANGE, 'word': WHITE, 'sub': GREY},
    'DTSX': {'sym': DTS_ORANGE, 'word': WHITE, 'right': DTS_ORANGE},
    'HDR10': {'word': WHITE, 'right': GOLD, 'sub': GREY},
    'HDR10Plus': {'word': WHITE, 'right': HDR10P, 'sub': GREY},
    'HDR10_IMAX': {'word': WHITE, 'right': GOLD, 'sub': IMAX_BLUE},
    'HDR10Plus_IMAX': {'word': WHITE, 'right': HDR10P, 'sub': IMAX_BLUE},
    'HLG': {'all': GOLD},
    'IMAX': {'all': IMAX_BLUE},
    'SDR': {'all': GREY},
    'FLAC': {'all': AMBER},
    'AAC': {'all': GREEN},
    'OPUS': {'all': GREEN},
    'Vorbis': {'all': GREEN},
}


def gradient_color(stops, t):
    if len(stops) == 1:
        return stops[0]
    t = max(0.0, min(1.0, t)) * (len(stops) - 1)
    i = min(int(t), len(stops) - 2)
    f = t - i
    a, b = stops[i], stops[i + 1]
    return tuple(int(a[k] + (b[k] - a[k]) * f) for k in range(3))


def runs(mask_line, min_gap):
    """Összefüggő szakaszok (start, end) egy 1D jelenlét-tömbben, min_gap-nél kisebb rést összevon."""
    out, start, gap = [], None, 0
    for i, v in enumerate(mask_line):
        if v:
            if start is None:
                start = i
            gap = 0
            end = i
        elif start is not None:
            gap += 1
            if gap >= min_gap:
                out.append((start, end))
                start = None
    if start is not None:
        out.append((start, end))
    return out


def regions(img):
    """A logó részei: (felső sor, alsó sor), a felső sor oszlop-szakaszai."""
    a = img.split()[-1]
    w, h = img.size
    px = a.load()
    rows = [any(px[x, y] > 40 for x in range(w)) for y in range(h)]
    rr = runs(rows, max(4, h // 30))
    top = rr[0]
    sub = (rr[1][0], rr[-1][1]) if len(rr) > 1 else None
    cols = [any(px[x, y] > 40 for y in range(top[0], top[1] + 1)) for x in range(w)]
    cr = runs(cols, max(6, w // 60))
    return top, sub, cr


def colorize(src, dst, spec):
    img = Image.open(src).convert('RGBA')
    w, h = img.size
    top, sub, cr = regions(img)
    out = Image.new('RGBA', (w, h))
    sp, op = img.load(), out.load()
    sym_end = cr[0][1] if len(cr) > 1 else -1
    right_start = cr[-1][0] if len(cr) > 1 else w + 1
    if 'right' in spec and len(cr) < 2:
        # nincs rés (pl. HDR10+: az „R” és a „10+” összeér): a jobb oldali 30%-ban a
        # legkevesebb pixelt tartalmazó oszlopnál vágunk
        cnt = [sum(1 for y in range(top[0], top[1] + 1) if sp[x, y][3] > 40) for x in range(w)]
        lo, hi = int(w * 0.66), int(w * 0.90)
        right_start = min(range(lo, hi), key=lambda x: (cnt[x], -x))

    def pick(x, y):
        if 'all' in spec:
            return spec['all'], (x / w)
        if sub and y >= sub[0]:
            return spec.get('sub', WHITE), (x - 0) / w
        if x <= sym_end and 'sym' in spec:
            return spec['sym'], (y - top[0]) / max(1, top[1] - top[0])
        if x >= right_start and 'right' in spec:
            return spec['right'], (x - right_start) / max(1, w - right_start)
        return spec.get('word', WHITE), x / w

    for y in range(h):
        for x in range(w):
            r, g, b, alpha = sp[x, y]
            if alpha == 0:
                continue
            stops, t = pick(x, y)
            c = gradient_color(stops, t)
            op[x, y] = (c[0], c[1], c[2], alpha)
    out.save(dst)


def main(src_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for name in sorted(os.listdir(src_dir)):
        base = name[:-4]
        if not name.endswith('.png'):
            continue
        spec = SPEC.get(base)
        if spec is None:
            Image.open(os.path.join(src_dir, name)).save(os.path.join(out_dir, name))
            continue
        colorize(os.path.join(src_dir, name), os.path.join(out_dir, name), spec)
        print('színezve:', name)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
