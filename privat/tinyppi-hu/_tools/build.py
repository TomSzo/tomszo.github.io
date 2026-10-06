#!/usr/bin/env python3
"""signde PPI (tinyppi, jamal2362 / signde) – TomSzo-változat a privát tárolóba.

Az eredeti script.signde.tinyppi csomagot a signde tárolóból tölti le, és:
  - színes kodeklogókat ad hozzá (media/codecs_color, a _tools/colorize.py készíti),
  - új felbontás- és videókodek-jelvényeket (media/badges, media/badges_white,
    a _tools/make_badges.py készíti),
  - a „Kodek logók” beállításokhoz új csoportot: Színes logók / Felbontás jelvény /
    Videókodek jelvény (magyar súgóval),
  - a hiányzó magyar fordításokat (forditas/script.signde.tinyppi.tsv),
majd a verziót .1-gyel megemeli (17.2.7.5 -> 17.2.7.5.1), és kiírja a privát tárolóba.

Futtatás a repó gyökeréből:  python3 privat/tinyppi-hu/_tools/build.py
"""
import importlib.util
import os
import re
import shutil
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)                 # privat/tinyppi-hu
PRIVAT = os.path.dirname(BASE)               # privat
_spec = importlib.util.spec_from_file_location('bingie_build', os.path.join(PRIVAT, 'bingie-hu', '_tools', 'build.py'))
bingie = importlib.util.module_from_spec(_spec)   # közös segédek: fetch, po_entries, Pkg, update_repo
_spec.loader.exec_module(bingie)

AID = 'script.signde.tinyppi'
SIGNDE = 'https://signde.github.io/repository.signde/addons/zips/'
SUFFIX = '.2'                                # 17.2.7.5.2: vízszintes logósáv a PPI-ben
MEDIA = 'resources/skins/Default/media/'
CACHE = os.environ.get('BINGIE_CACHE', os.path.join(os.path.expanduser('~'), '.cache', 'bingie-hu'))

# Új szövegek: azonosító -> (angol, magyar)
STRINGS = {
    32600: ('Logo style', 'Logók stílusa'),
    32601: ('Colored logos', 'Színes logók'),
    32602: ('Shows the format logos in their own brand colors (Dolby, DTS, HDR10+, IMAX…) '
            'instead of a single tint. While on, the logo colour settings below are ignored.',
            'A formátumlogók saját, márkaszerű színeikben jelennek meg (Dolby, DTS, HDR10+, IMAX…) '
            'egyszínű festés helyett. Bekapcsolva a lenti logószín-beállítások nem érvényesek, '
            'a háttér és az elválasztó színe viszont igen.'),
    32603: ('Resolution badge', 'Felbontás jelvény'),
    32604: ('Adds a resolution badge (4K / 1080p / 720p / SD) below the HDR / video logo.',
            'A HDR / videó logó alá egy felbontás jelvény kerül (4K / 1080p / 720p / SD), '
            'így egy pillantással látod, milyen minőségű a lejátszott fájl.'),
    32605: ('Video codec badge', 'Videókodek jelvény'),
    32606: ('Adds a video codec badge (HEVC / AVC / AV1 / VP9 / MPEG-2 / VC-1) above the audio logo.',
            'A hang logó fölé egy videókodek jelvény kerül (HEVC / AVC / AV1 / VP9 / MPEG-2 / VC-1). '
            'Ebből látszik, milyen tömörítéssel készült a videó.'),
    32607: ('Horizontal logo bar in the PPI overlay', 'Vízszintes logósáv a PPI ablakban'),
    32608: ('While the signde PPI overlay is open, the logos are shown side by side in a modern bar '
            '(HDR / Dolby Vision, resolution, codec, audio) instead of a vertical stack.',
            'A PPI ablak nyitva tartásakor a logók egymás mellett, egy modern sávban jelennek meg '
            '(HDR / Dolby Vision, felbontás, kodek, hang) a függőleges oszlop helyett.'),
}

SETTINGS_GROUP = '''            <group id="4" label="32600">
                <setting id="hu_color_logos" type="boolean" label="32601" help="32602">
                    <level>0</level>
                    <default>true</default>
                    <control type="toggle" />
                </setting>
                <setting id="hu_ppi_horizontal" type="boolean" label="32607" help="32608">
                    <level>0</level>
                    <default>true</default>
                    <control type="toggle" />
                </setting>
                <setting id="hu_resolution_badge" type="boolean" label="32603" help="32604">
                    <level>0</level>
                    <default>true</default>
                    <control type="toggle" />
                </setting>
                <setting id="hu_codec_badge" type="boolean" label="32605" help="32606">
                    <level>0</level>
                    <default>true</default>
                    <control type="toggle" />
                </setting>
            </group>
'''

SPLASH_HELPERS = '''

# --- TomSzo: színes logók, felbontás- és videókodek-jelvény ---------------------
_HU_RESOLUTION = {
    "8k": "res_4K", "4k": "res_4K", "2160": "res_4K",
    "1080": "res_1080", "720": "res_720",
    "576": "res_SD", "540": "res_SD", "480": "res_SD", "sd": "res_SD",
}
_HU_CODEC = {
    "hevc": "vc_HEVC", "h265": "vc_HEVC", "hvc1": "vc_HEVC", "hev1": "vc_HEVC",
    "dvhe": "vc_HEVC", "dvh1": "vc_HEVC",
    "h264": "vc_AVC", "avc1": "vc_AVC", "avc": "vc_AVC",
    "av1": "vc_AV1", "av01": "vc_AV1",
    "vp9": "vc_VP9",
    "mpeg2": "vc_MPEG2", "mpeg2video": "vc_MPEG2",
    "vc1": "vc_VC1", "vc-1": "vc_VC1", "wvc1": "vc_VC1",
}
_HU_WHITE = "FFFFFFFF"


def _hu_setting(name: str, default: bool) -> bool:
    try:
        return xbmcaddon.Addon().getSettingBool(name)
    except Exception:
        return default


def _hu_colored(rel_path: str) -> str:
    """codecs/X.png -> codecs_color/X.png, ha van színes változat."""
    if not rel_path.startswith("codecs/"):
        return rel_path
    colored = "codecs_color/" + rel_path[len("codecs/"):]
    if os.path.exists(os.path.join(_MEDIA_PATH, colored.replace("/", os.sep))):
        return colored
    return rel_path


def _hu_logos(logos: list) -> list:
    """A tinyppi logóihoz hozzáadja a jelvényeket, és színesre cseréli őket."""
    colored = _hu_setting("hu_color_logos", True)
    badge_dir = "badges/" if colored else "badges_white/"
    extra = []
    if _hu_setting("hu_resolution_badge", True):
        res = _HU_RESOLUTION.get(info("VideoPlayer.VideoResolution").lower().strip())
        if res:
            extra.append((badge_dir + res + ".png", "video"))
    if _hu_setting("hu_codec_badge", True):
        codec = _HU_CODEC.get(info("VideoPlayer.VideoCodec").lower().strip())
        if codec:
            extra.append((badge_dir + codec + ".png", "video"))
    video = [item for item in logos if item[1] == "video"]
    audio = [item for item in logos if item[1] != "video"]
    out = video + extra + audio
    if colored:
        out = [(_hu_colored(path), "hu_color") for path, _ in out]
    return out


_HU_HORIZONTAL = False


def _hu_build_horizontal(logos, colors, offset_x, offset_y, screen_w, screen_h,
                         user_scale=1.0, layer_token="", pill_edge=1):
    """Vízszintes, modern logósáv (a PPI ablakhoz): a logók egymás mellett, függőleges
    elválasztókkal, lekerekített panelen; a DV-réteg pirula a videó logó fölött / alatt."""
    scale = _BASE_SCALE * user_scale
    box_w = int(screen_w * 0.085 * scale)
    box_h = int(screen_h * 0.05 * scale)
    gap = int(screen_w * 0.016 * scale)
    pad_x = int(screen_w * 0.012 * scale)
    pad_y = int(screen_h * 0.016 * scale)
    radius = int(screen_h * 0.02 * scale)
    has_video = any(kind in ("video", "hu_color") for _, kind in logos)
    has_pill = has_video and layer_token in ("fel", "mel", "other")
    pill_h = max(1, int(box_h * 0.15))
    pill_margin = max(1, int(screen_h * 0.008 * scale))
    if has_pill:
        pad_y = pill_h + 2 * pill_margin
    count = len(logos)
    panel_w = count * box_w + (count - 1) * gap + 2 * pad_x
    panel_h = box_h + 2 * pad_y
    inset = int(screen_h * 0.0325)
    edge = 35
    offset_x = min(100, max(0, offset_x))
    offset_y = min(100, max(0, offset_y))
    panel_x = inset + max(0, screen_w - panel_w - inset - edge) * offset_x // 100
    panel_y = inset + max(0, screen_h - panel_h - inset - edge) * offset_y // 100
    left, top = panel_x + pad_x, panel_y + pad_y
    controls = list(_panel_controls(panel_x, panel_y, panel_w, panel_h, radius, colors["bg"]))
    div_w = max(1, int(screen_h * 0.0025 * scale))
    div_h = int(box_h * 0.7)
    for i in range(1, count):
        dx = left + i * (box_w + gap) - gap // 2 - div_w // 2
        controls.append(_solid(dx, top + (box_h - div_h) // 2, div_w, div_h, colors["divider"]))
    for i, (logo, kind) in enumerate(logos):
        controls.append(_make_image(logo, left + i * (box_w + gap), top, box_w, box_h,
                                    colors.get(kind, _HU_WHITE)))
    dot = None
    if has_video:
        dot_d = max(1, int(box_h * 0.20))
        dot_pad = max(1, int(box_h * 0.18))
        dot = _make_dot(panel_x + panel_w - dot_pad - dot_d // 2, panel_y + dot_pad + dot_d // 2,
                        dot_d, colors["convert_dot"])
        controls.append(dot)
    if has_pill:
        pill_w = max(1, int(box_w * 0.30))
        pill_x = left + (box_w - pill_w) // 2
        pill_y = panel_y + pill_margin
        if pill_edge != 1:
            pill_y += panel_h - 2 * pill_margin - pill_h
        controls.append(_make_image(_PILL_TEXTURE, pill_x, pill_y, pill_w, pill_h, colors[layer_token]))
    return controls, dot
'''


def patch_splash(text):
    r = bingie.replace_once
    text = r(text, '\ndef _current_logos(', SPLASH_HELPERS + '\n\ndef _current_logos(', 'splash: segédek')
    text = r(text, '''    if audio_logo:
        logos.append((audio_logo, "audio"))
    return logos
''', '''    if audio_logo:
        logos.append((audio_logo, "audio"))
    return _hu_logos(logos)
''', 'splash: _current_logos')
    # elválasztó minden szomszédos logó közé (nem csak kettőnél)
    text = r(text, '''    if count == 2:
        div_h = max(1, int(screen_h * 0.0025 * scale))
        div_y = top + box_h + v_gap // 2 - div_h // 2
        controls.append(_solid(block_x, div_y, box_w, div_h, colors["divider"]))
''', '''    div_h = max(1, int(screen_h * 0.0025 * scale))
    for div_index in range(1, count):
        div_y = top + div_index * (box_h + v_gap) - v_gap // 2 - div_h // 2
        controls.append(_solid(block_x, div_y, box_w, div_h, colors["divider"]))
''', 'splash: elválasztók')
    text = r(text, 'has_video = any(kind == "video" for _, kind in logos)',
             'has_video = any(kind in ("video", "hu_color") for _, kind in logos)', 'splash: has_video')
    text = r(text, '''    if not logos:
        return [], None

    # Overall size multiplier''', '''    if not logos:
        return [], None
    if _HU_HORIZONTAL:
        return _hu_build_horizontal(logos, colors, offset_x, offset_y, screen_w, screen_h,
                                    user_scale, layer_token, pill_edge)

    # Overall size multiplier''', 'splash: vízszintes ág')
    text = r(text, '''                controls, dot = _build_controls(
''', '''                global _HU_HORIZONTAL
                _HU_HORIZONTAL = mode == "tinyppi" and _hu_setting("hu_ppi_horizontal", True)
                controls, dot = _build_controls(
''', 'splash: vízszintes kapcsoló')
    text = r(text, 'controls.append(_make_image(logo, block_x, y, box_w, box_h, colors[kind]))',
             'controls.append(_make_image(logo, block_x, y, box_w, box_h, colors.get(kind, _HU_WHITE)))',
             'splash: színezés')
    return text


def patch_images(text):
    # A méretezett képek gyorsítótár-neve a mappát is tartalmazza, így a codecs/DTS.png
    # és a codecs_color/DTS.png nem keveredhet össze.
    return bingie.replace_once(
        text, '    name = os.path.splitext(os.path.basename(path))[0]\n',
        '    name = os.path.splitext(os.path.basename(path))[0]\n'
        '    name = os.path.basename(os.path.dirname(path)) + "_" + name\n', 'images: cache-név')


def patch_settings(text):
    text = bingie.replace_once(
        text, '        <category id="Splash" label="32301" help="32310">\n',
        '        <category id="Splash" label="32301" help="32310">\n' + SETTINGS_GROUP, 'settings: csoport')
    # a PPI ablak mellett alapból látszanak a (színes) logók
    return bingie.replace_once(
        text, '''<setting id="splash_show_on_tinyppi" type="boolean" label="32319" help="32320">
                    <level>0</level>
                    <default>false</default>''',
        '''<setting id="splash_show_on_tinyppi" type="boolean" label="32319" help="32320">
                    <level>0</level>
                    <default>true</default>''', 'settings: logók a PPI mellett')


def patch_po(text, lang):
    entries = dict(bingie.po_entries(text))
    if lang == 'hu':
        trans = {}
        for line in open(os.path.join(BASE, 'forditas', AID + '.tsv'), encoding='utf-8'):
            k, v = line.rstrip('\n').split('\t', 1)
            trans[k] = v
        # üres msgstr kitöltése
        def fill(m):
            ctx = m.group(1)
            if ctx in trans and m.group(3) == '""':
                return 'msgctxt "%s"\nmsgid %smsgstr "%s"' % (ctx, m.group(2), bingie.po_escape(trans[ctx]))
            return m.group(0)
        text = re.sub(r'msgctxt "([^"]*)"\nmsgid ((?:"(?:[^"\\]|\\.)*"\n)+)msgstr ("(?:[^"\\]|\\.)*")',
                      fill, text)
        en = ENGLISH
        missing = [k for k in trans if k not in entries]
        text = text.rstrip('\n') + '\n\n' + ''.join(
            bingie.po_entry(k, bingie.po_escape(en[k]), bingie.po_escape(trans[k])) for k in missing)
    text = text.rstrip('\n') + '\n\n'
    for sid, (en_txt, hu_txt) in sorted(STRINGS.items()):
        ctx = '#%d' % sid
        if ctx in entries:
            raise SystemExit('Foglalt szövegazonosító: %s' % ctx)
        text += bingie.po_entry(ctx, bingie.po_escape(en_txt),
                                bingie.po_escape(hu_txt) if lang == 'hu' else '')
    return text


ENGLISH = {}


def main():
    xml = open(bingie.fetch(SIGNDE + 'addons.xml', os.path.join(CACHE, 'signde-addons.xml')),
               encoding='utf-8').read()
    ver = re.search(r'id="%s"[^>]*version="([^"]+)"' % re.escape(AID), xml).group(1)
    zpath = bingie.fetch('%s%s/%s-%s.zip' % (SIGNDE, AID, AID, ver), os.path.join(CACHE, '%s-%s.zip' % (AID, ver)))
    with zipfile.ZipFile(zpath) as z:
        files = {n: z.read(n) for n in z.namelist() if not n.endswith('/')}
    pkg = bingie.Pkg(AID, files)
    ENGLISH.update(bingie.po_entries(pkg.get('resources/language/resource.language.en_gb/strings.po')))

    pkg.put('resources/lib/ui/splash.py', patch_splash(pkg.get('resources/lib/ui/splash.py')))
    pkg.put('resources/lib/core/images.py', patch_images(pkg.get('resources/lib/core/images.py')))
    pkg.put('resources/settings.xml', patch_settings(pkg.get('resources/settings.xml')))
    for lang, folder in (('en', 'en_gb'), ('hu', 'hu_hu')):
        rel = 'resources/language/resource.language.%s/strings.po' % folder
        pkg.put(rel, patch_po(pkg.get(rel), lang))
    for sub in ('codecs_color', 'badges', 'badges_white'):
        src = os.path.join(BASE, 'media', sub)
        for name in sorted(os.listdir(src)):
            with open(os.path.join(src, name), 'rb') as f:
                pkg.files[pkg.path(MEDIA + sub + '/' + name)] = f.read()

    newver = ver + SUFFIX
    axml = pkg.get('addon.xml')
    axml = bingie.replace_once(axml, 'version="%s"' % ver, 'version="%s"' % newver, 'addon.xml: verzió')
    axml = bingie.replace_once(axml, 'provider-name="jamal2362, signde"',
                               'provider-name="jamal2362, signde, TomSzo"', 'addon.xml: szerző')
    axml = bingie.replace_once(axml, '<news>\n', '<news>\n            [B]%s (TomSzo)[/B][CR]'
                               '- Vízszintes, modern logósáv a PPI ablakban (alapból bekapcsolva)[CR]'
                               '- Színes kodeklogók (Dolby, DTS, HDR10+, IMAX…)[CR]'
                               '- Felbontás- és videókodek-jelvény (alapból bekapcsolva)[CR]'
                               '- Teljes magyar fordítás[CR][CR]\n' % newver, 'addon.xml: hírek')
    pkg.put('addon.xml', axml)

    outdir = os.path.join(PRIVAT, AID)
    if os.path.isdir(outdir):
        shutil.rmtree(outdir)
    os.makedirs(outdir)
    zout = os.path.join(outdir, '%s-%s.zip' % (AID, newver))
    with zipfile.ZipFile(zout, 'w', zipfile.ZIP_DEFLATED) as z:
        for n in sorted(pkg.files):
            info = zipfile.ZipInfo(n, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, pkg.files[n])
    with open(os.path.join(outdir, 'addon.xml'), 'w', encoding='utf-8') as f:
        f.write(axml)
    for art in ('icon.jpg', 'fanart.jpg'):
        with open(os.path.join(outdir, art), 'wb') as f:
            f.write(pkg.files[pkg.path(art)])
    print('kész: %s %s (%.1f MB)' % (AID, newver, os.path.getsize(zout) / 1e6))
    bingie.update_repo([(AID, newver, axml)])


if __name__ == '__main__':
    main()
