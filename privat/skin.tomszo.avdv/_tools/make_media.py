#!/usr/bin/env python3
"""A TomSzo AVDV skin saját grafikái (media/tomszo/*.png).

Kell hozzá: Pillow és cairosvg (pip install pillow cairosvg).
Futtatás a skin mappájából:  python3 _tools/make_media.py
Az eredményt a repó tartalmazza, a skin futásához nem kell ez a szkript.
"""
import io
import os

import cairosvg
from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'media', 'tomszo')

# Menüikonok (24x24-es vonalas rajz, a webOS-appok ikonjaival egyező stílus)
ICONS = {
    'search': '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
    'home': '<path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/>',
    'movies': '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 9h18M8 5v4M16 5v4M8 15v4M16 15v4"/>',
    'tv': '<rect x="3" y="5" width="18" height="12" rx="2"/><path d="M8 21h8M12 17v4"/>',
    'sport': '<circle cx="12" cy="12" r="9"/><path d="M12 7l4.3 3.1-1.6 5H9.3l-1.6-5z"/>'
             '<path d="M12 3v4M21 10l-4.7.1M17.5 19.5l-2.8-4.4M6.5 19.5l2.8-4.4M3 10l4.7.1"/>',
    'anime': '<path d="M12 3l2.6 5.6 6 .7-4.5 4.1 1.2 6L12 16.4 6.7 19.4l1.2-6L3.4 9.3l6-.7z"/>',
    'addons': '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/>'
              '<rect x="3" y="14" width="7" height="7" rx="1.5"/><path d="M17.5 14v7M14 17.5h7"/>',
    'favourites': '<path d="M12 20s-7-4.4-9.2-8.7C1.3 8.2 3.2 4.5 6.7 4.5c2 0 3.3 1.1 4.3 2.5 1-1.4 '
                  '2.3-2.5 4.3-2.5 3.5 0 5.4 3.7 3.9 6.8C19 15.6 12 20 12 20z"/>',
    'settings': '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 '
                '2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 '
                '0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 '
                '1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 '
                '2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 '
                '1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 '
                '1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    'power': '<path d="M12 3v9"/><path d="M6.3 6.3a8 8 0 1 0 11.4 0"/>',
    'play': '<path d="M7 4v16l13-8z" fill="white"/>',
    'info': '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',
}


def icon(name, path, size=96):
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="%d" height="%d" '
           'fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" '
           'stroke-linejoin="round">%s</svg>' % (size, size, path))
    png = cairosvg.svg2png(bytestring=svg.encode('utf-8'))
    Image.open(io.BytesIO(png)).save(os.path.join(OUT, 'icon_%s.png' % name))


def gradient(name, w, h, horizontal, a0, a1):
    """Fekete átmenet: a0 -> a1 átlátszóság (0..255) a megadott irányban."""
    img = Image.new('RGBA', (w, h))
    px = img.load()
    n = w if horizontal else h
    for i in range(n):
        t = i / float(n - 1)
        t = t * t * (3 - 2 * t)          # lágy (smoothstep) átmenet
        a = int(round(a0 + (a1 - a0) * t))
        for j in range(h if horizontal else w):
            if horizontal:
                px[i, j] = (0, 0, 0, a)
            else:
                px[j, i] = (0, 0, 0, a)
    img.save(os.path.join(OUT, name))


def rail_gradient():
    """A nyitott menüsáv háttere: 380 px-ig szinte tömör, utána lágyan átlátszó."""
    w, h = 700, 8
    img = Image.new('RGBA', (w, h))
    px = img.load()
    for i in range(w):
        if i < 380:
            a = 245
        else:
            t = (i - 380) / float(w - 380)
            a = int(245 * (1 - t * t * (3 - 2 * t)))
        for j in range(h):
            px[i, j] = (0, 0, 0, a)
    img.save(os.path.join(OUT, 'grad_rail.png'))


def branding():
    """A skin ikonja (resources/icon.png) és háttérképe (resources/fanart.jpg)."""
    from PIL import ImageFont, ImageFilter
    res = os.path.join(os.path.dirname(OUT), '..', 'resources')
    font = os.path.join(os.path.dirname(OUT), '..', '_tools', 'fonts-src', 'Inter-ExtraBold.ttf')
    size = 512
    ic = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(ic)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=96, fill=(12, 12, 16, 255))
    f = ImageFont.truetype(font, 250)
    d.text((size // 2, size // 2 - 30), 'TS', font=f, fill=(255, 255, 255, 255), anchor='mm')
    d.rounded_rectangle([150, 380, 362, 404], radius=12, fill=(229, 38, 44, 255))
    ic.save(os.path.join(res, 'icon.png'))
    fa = Image.new('RGB', (1920, 1080), (6, 6, 8))
    glow = Image.new('RGB', (1920, 1080), (0, 0, 0))
    ImageDraw.Draw(glow).ellipse([1100, -300, 2300, 900], fill=(120, 14, 20))
    fa = Image.blend(fa, glow.filter(ImageFilter.GaussianBlur(220)), 0.55)
    d = ImageDraw.Draw(fa)
    d.text((180, 470), 'TomSzo AVDV', font=ImageFont.truetype(font, 110), fill=(255, 255, 255))
    d.text((186, 610), 'streaming-stílusú skin TV-re', font=ImageFont.truetype(font, 44), fill=(170, 170, 180))
    fa.save(os.path.join(res, 'fanart.jpg'), quality=88)


def rounded(name, w, h, r, outline=0, fill=True):
    """Lekerekített téglalap (fehér) - maszknak, kitöltésnek vagy keretnek."""
    scale = 4
    img = Image.new('RGBA', (w * scale, h * scale), (255, 255, 255, 0))
    d = ImageDraw.Draw(img)
    box = [0, 0, w * scale - 1, h * scale - 1]
    if fill:
        d.rounded_rectangle(box, radius=r * scale, fill=(255, 255, 255, 255))
    if outline:
        d.rounded_rectangle(box, radius=r * scale, outline=(255, 255, 255, 255),
                            width=outline * scale)
    img.resize((w, h), Image.LANCZOS).save(os.path.join(OUT, name))


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, path in ICONS.items():
        icon(name, path)
    Image.new('RGBA', (8, 8), (255, 255, 255, 255)).save(os.path.join(OUT, 'white.png'))
    gradient('grad_left.png', 900, 8, True, 255, 0)        # a hero bal oldala
    gradient('grad_bottom.png', 8, 520, False, 0, 255)     # a hero alja
    gradient('grad_top.png', 8, 260, False, 200, 0)        # felső sáv (óra)
    gradient('grad_card.png', 8, 140, False, 0, 230)       # kártya címe alatt
    rail_gradient()                                        # nyitott menü háttere
    rounded('mask_card.png', 400, 225, 14)                 # kártya-maszk (16:9)
    rounded('mask_poster.png', 240, 360, 14)               # poszter-maszk (2:3)
    rounded('frame.png', 96, 96, 18, outline=6, fill=False)  # fókuszkeret (9 szeletes)
    rounded('pill.png', 96, 96, 22)                        # gomb / kiemelés (9 szeletes)
    rounded('bar.png', 16, 16, 4)                          # haladásjelző
    branding()
    print('kész:', OUT)


if __name__ == '__main__':
    main()
