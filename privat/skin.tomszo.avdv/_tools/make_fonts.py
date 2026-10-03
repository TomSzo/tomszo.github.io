#!/usr/bin/env python3
"""Inter + CJK (kínai, japán, koreai) összeolvasztott betűtípusok (fonts/TSInter-*.ttf).

A Kodi címkénként egyetlen betűtípust használ, nincs tartalék betűtípus: ha egy cím
(pl. TMDb-n magyar fordítás nélküli kínai / japán / koreai sorozat eredeti címe)
olyan karaktert tartalmaz, ami az Interben nincs, "NO GLYPH" doboz jelenik meg.
Ezért az Inter latin betűi mellé a Noto Sans SC / KR (SIL OFL 1.1) gyakori
CJK-karaktereit tesszük ugyanabba a fájlba.

Kell hozzá: fonttools (pip install fonttools), és a két változtatható Noto-fájl:
  https://github.com/google/fonts/raw/main/ofl/notosanssc/NotoSansSC[wght].ttf
  https://github.com/google/fonts/raw/main/ofl/notosanskr/NotoSansKR[wght].ttf
Futtatás a skin mappájából:
  python3 _tools/make_fonts.py <NotoSansSC[wght].ttf> <NotoSansKR[wght].ttf>
"""
import os
import sys

from fontTools import subset
from fontTools.merge import Merger
from fontTools.ttLib import TTFont
from fontTools.ttLib.scaleUpem import scale_upem
from fontTools.varLib.instancer import instantiateVariableFont

SKIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(SKIN, 'fonts')
SRC = os.path.join(SKIN, '_tools', 'fonts-src')   # az eredeti Inter-fájlok (nem kerülnek a zipbe)
WEIGHTS = {'Regular': 400, 'SemiBold': 600, 'Bold': 700, 'ExtraBold': 800}
DROP = ['GSUB', 'GPOS', 'GDEF', 'vhea', 'vmtx', 'VORG', 'BASE', 'STAT', 'meta', 'DSIG']


def charset(codec, lead, trail):
    """Egy kétbájtos kódlap (GB2312, JIS X 0208, KS X 1001) összes karaktere."""
    out = set()
    for a in lead:
        for b in trail:
            try:
                out.update(ord(c) for c in bytes([a, b]).decode(codec))
            except UnicodeDecodeError:
                pass
    return out


def ranges(*pairs):
    out = set()
    for a, b in pairs:
        out.update(range(a, b + 1))
    return out


def unicodes():
    euc = range(0xA1, 0xFF)
    common = ranges((0x3000, 0x303F),   # CJK írásjelek
                    (0x3040, 0x30FF),   # hiragana, katakana
                    (0x31F0, 0x31FF),
                    (0xFF00, 0xFFEF))   # teljes szélességű alakok
    sc = common | charset('gb2312', euc, euc) | charset('euc_jp', euc, euc)
    sc = {u for u in sc if u >= 0x2E80}           # a latin részt az Inter adja
    kr = {u for u in charset('euc_kr', euc, euc) if 0xAC00 <= u <= 0xD7A3}
    kr |= ranges((0x1100, 0x11FF), (0x3130, 0x318F))
    return sc, kr


def piece(path, wght, codes, upem):
    f = TTFont(path)
    f = instantiateVariableFont(f, {'wght': wght})
    opts = subset.Options()
    opts.layout_features = []
    opts.drop_tables += DROP
    opts.name_IDs = []
    opts.notdef_outline = False
    opts.hinting = False
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=codes)
    sub.subset(f)
    scale_upem(f, upem)
    for t in DROP:
        if t in f:
            del f[t]
    return f


def main(sc_path, kr_path):
    sc_codes, kr_codes = unicodes()
    for name, wght in WEIGHTS.items():
        inter = TTFont(os.path.join(SRC, 'Inter-%s.ttf' % name))
        upem = inter['head'].unitsPerEm
        tmp = []
        for i, f in enumerate([piece(sc_path, wght, sc_codes, upem), piece(kr_path, wght, kr_codes, upem)]):
            p = os.path.join(FONTS, '.cjk%d.ttf' % i)
            f.save(p)
            tmp.append(p)
        base = os.path.join(FONTS, '.inter.ttf')
        for t in DROP[3:]:
            if t in inter:
                del inter[t]
        inter.save(base)
        merged = Merger().merge([base] + tmp)
        out = os.path.join(FONTS, 'TSInter-%s.ttf' % name)
        merged.save(out)
        for p in [base] + tmp:
            os.remove(p)
        print('%s: %d karakter, %.1f MB' % (os.path.basename(out), len(merged.getBestCmap()),
                                            os.path.getsize(out) / 1e6))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
