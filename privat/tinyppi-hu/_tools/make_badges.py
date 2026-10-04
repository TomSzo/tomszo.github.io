#!/usr/bin/env python3
"""Új jelvények a tinyppihez: felbontás (4K / 1080p / 720p / SD) és videókodek (HEVC, AV1,
H.264, VP9…), a tinyppi kodeklogóinak stílusában (512 px széles, átlátszó háttér).

Használat:  python3 make_badges.py <betűtípus.ttf> <kimeneti mappa> [--white]
--white: fehér (a tinyppi saját színezéséhez), különben színes.
"""
import os
import sys
from PIL import Image, ImageDraw, ImageFont

GOLD = [(255, 220, 110), (225, 160, 40)]
BLUE = [(90, 190, 255), (30, 120, 235)]
GREEN = [(120, 225, 130), (40, 170, 80)]
GREY = [(200, 200, 208), (150, 150, 160)]
TEAL = [(80, 230, 210), (20, 160, 170)]
PURPLE = [(200, 140, 255), (130, 80, 230)]

# név: (fő felirat, alcím, színátmenet)
BADGES = {
    'res_4K': ('4K', 'ULTRA HD', GOLD),
    'res_1080': ('1080p', 'FULL HD', BLUE),
    'res_720': ('720p', 'HD', GREEN),
    'res_SD': ('SD', 'STANDARD DEFINITION', GREY),
    'vc_HEVC': ('HEVC', 'H.265', TEAL),
    'vc_AVC': ('AVC', 'H.264', BLUE),
    'vc_AV1': ('AV1', 'AOMEDIA', PURPLE),
    'vc_VP9': ('VP9', 'GOOGLE', GREEN),
    'vc_MPEG2': ('MPEG-2', 'VIDEO', GREY),
    'vc_VC1': ('VC-1', 'VIDEO', GREY),
}


def grad(stops, t):
    if len(stops) == 1:
        return stops[0]
    t = max(0.0, min(1.0, t)) * (len(stops) - 1)
    i = min(int(t), len(stops) - 2)
    f = t - i
    return tuple(int(stops[i][k] + (stops[i + 1][k] - stops[i][k]) * f) for k in range(3))


def make(font_path, main, sub, stops, white):
    W = 512
    big = ImageFont.truetype(font_path, 120)
    small = ImageFont.truetype(font_path, 34)
    mb = big.getbbox(main)
    sb = small.getbbox(sub)
    # a fő felirat ne legyen szélesebb 500 px-nél
    if mb[2] - mb[0] > 500:
        big = ImageFont.truetype(font_path, int(120 * 500 / (mb[2] - mb[0])))
        mb = big.getbbox(main)
    mh, sh, gap = mb[3] - mb[1], sb[3] - sb[1], 18
    H = mh + gap + sh + 4
    mask = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(mask)
    d.text(((W - (mb[2] - mb[0])) // 2 - mb[0], -mb[1]), main, font=big, fill=255)
    # alcím ritkítva, mint a tinyppi logóinál
    sub_s = ' '.join(sub) if len(sub) <= 10 else sub
    sb = small.getbbox(sub_s)
    d.text(((W - (sb[2] - sb[0])) // 2 - sb[0], mh + gap - sb[1]), sub_s, font=small, fill=255)
    out = Image.new('RGBA', (W, H))
    mp, op = mask.load(), out.load()
    for y in range(H):
        for x in range(W):
            a = mp[x, y]
            if a:
                c = (255, 255, 255) if white else (grad(stops, x / W) if y < mh + gap // 2 else (205, 205, 212))
                op[x, y] = (c[0], c[1], c[2], a)
    return out


def main(font_path, out_dir, white=False):
    os.makedirs(out_dir, exist_ok=True)
    for name, (main_t, sub, stops) in BADGES.items():
        make(font_path, main_t, sub, stops, white).save(os.path.join(out_dir, name + '.png'))
        print('kész:', name)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], '--white' in sys.argv)
