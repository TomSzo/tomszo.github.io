#!/usr/bin/env python3
"""Bingie (matke-84, Kodi 21) – magyar változat építése a privát tárolóba.

Az eredeti csomagokat a matke-84/repository.bingie tárolóból tölti le (omega ág),
és mindegyikbe beteszi:
  - a teljes magyar fordítást (resource.language.hu_hu/strings.po) a forditas/*.tsv-ből,
  - a beállítások magyar súgószövegeit (help="..." + új szövegazonosítók),
  - a skinbe egy súgó-infódobozt a skinbeállításoknál és a kiegészítő-beállítások ablakában,
  - néhány, a kódba égetett angol felirat magyarítását,
majd a verziószámot .1-gyel (pl. 2.0.2 -> 2.0.2.1) megemeli, hogy a Kodi a magyar
változatot válassza a matke-tárolóval szemben, és kiírja a zipeket a privát tárolóba
(privat/<id>/<id>-<verzió>.zip), végül frissíti a privat/addons.xml(.md5)-öt.

Futtatás a repó gyökeréből:  python3 privat/bingie-hu/_tools/build.py
"""
import hashlib
import io
import os
import re
import shutil
import sys
import urllib.request
import zipfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)                 # privat/bingie-hu
PRIVAT = os.path.dirname(BASE)               # privat
FORD = os.path.join(BASE, 'forditas')
CACHE = os.environ.get('BINGIE_CACHE', os.path.join(os.path.expanduser('~'), '.cache', 'bingie-hu'))
UPSTREAM = 'https://raw.githubusercontent.com/matke-84/repository.bingie/main/omega/'
# a signde (AVDV/CoreELEC) tárolója: a skin és a TMDb Bingie Helper innen jön – a matke-féle
# csomagokra épül, AVDV-s kiegészítésekkel (tinyppi, Atmos/DTS:X/HDR10+ jelölők, Wikipédia-javítás)
SIGNDE = 'https://signde.github.io/repository.signde/addons/zips/'
FROM_SIGNDE = {'skin.bingie', 'plugin.video.tmdb.bingie.helper'}
SUFFIX = '.1'                                # a magyar kiadás sorszáma (alap)
# kiegészítőnként eltérő sorszám, ha egy csomag újabb magyar kiadást kapott
REVISION = {'skin.bingie': '.2', 'plugin.video.tmdb.bingie.helper': '.1', 'script.module.bingie': '.2'}
# ezeket nem építjük újra (nincs bennük szöveg) – a matke-tárolóból jönnek
SKIP = {'repository.bingie', 'resource.images.studios.coloured'}
HELP_BASE = 33000                            # kiegészítők: új súgó-szövegazonosítók innen
SKIN_HELP_BASE = 31700                       # skin: 31000-31999 között kell lennie


# --- segédek -----------------------------------------------------------------------------
def fetch(url, dest):
    if not os.path.exists(dest):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with urllib.request.urlopen(url) as r, open(dest + '.tmp', 'wb') as f:
            shutil.copyfileobj(r, f)
        os.replace(dest + '.tmp', dest)
    return dest


def read_tsv(name):
    path = os.path.join(FORD, name)
    if not os.path.exists(path):
        return {}
    out = {}
    for line in open(path, encoding='utf-8'):
        line = line.rstrip('\n')
        if line:
            k, v = line.split('\t', 1)
            out[k] = v
    return out


def po_entries(text):
    """(msgctxt, msgid) párok egy .po fájlból, sorrendben (üres sor nélküli blokkokat is kezel)."""
    out = []
    for m in re.finditer(r'msgctxt "([^"]*)"\s*\nmsgid ((?:"(?:[^"\\]|\\.)*"\s*)+)', text):
        out.append((m.group(1), ''.join(re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(2)))))
    return out


def po_escape(s):
    """A .tsv már .po-escapelt szöveget tartalmaz (\\n, \\"); csak a sima idézőjelet védjük."""
    return re.sub(r'(?<!\\)"', '\\"', s)


def po_header(addon_id):
    return ('# Kodi Media Center language file\n# Addon Name: %s\n# Magyar fordítás: TomSzo\n'
            'msgid ""\nmsgstr ""\n"Project-Id-Version: %s\\n"\n"Language-Team: Hungarian\\n"\n'
            '"MIME-Version: 1.0\\n"\n"Content-Type: text/plain; charset=UTF-8\\n"\n'
            '"Content-Transfer-Encoding: 8bit\\n"\n"Language: hu_HU\\n"\n'
            '"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n\n' % (addon_id, addon_id))


def po_entry(ctx, msgid, msgstr):
    return 'msgctxt "%s"\nmsgid "%s"\nmsgstr "%s"\n\n' % (ctx, msgid, msgstr)


def replace_once(text, old, new, what):
    n = text.count(old)
    if n != 1:
        raise SystemExit('Javítás nem alkalmazható (%s): %d találat' % (what, n))
    return text.replace(old, new)


# --- a csomagok átalakítása ------------------------------------------------------------
class Pkg:
    def __init__(self, addon_id, files):
        self.id = addon_id
        self.files = files                   # útvonal (a zipen belül) -> bájtok

    def path(self, rel):
        return '%s/%s' % (self.id, rel)

    def get(self, rel):
        return self.files[self.path(rel)].decode('utf-8-sig')

    def put(self, rel, text):
        self.files[self.path(rel)] = text.encode('utf-8')

    def has(self, rel):
        return self.path(rel) in self.files

    def lang_dir(self):
        for p in self.files:
            m = re.match(r'%s/(.*?)resource\.language\.en_gb/strings\.po$' % re.escape(self.id), p)
            if m:
                return m.group(1)
        return 'resources/language/' if self.id != 'skin.bingie' else 'language/'


def translate(pkg, extra=None):
    """Magyar strings.po a forditas/<id>.tsv-ből (+ extra: új azonosító -> szöveg)."""
    hu = read_tsv(pkg.id + '.tsv')
    extra = extra or {}
    if not hu and not extra:
        return
    ld = pkg.lang_dir()
    en_rel = ld + 'resource.language.en_gb/strings.po'
    en = po_entries(pkg.get(en_rel)) if pkg.has(en_rel) else []
    missing = [c for c, _ in en if c.lstrip('#') not in hu]
    if missing:
        raise SystemExit('%s: hiányzó fordítás: %s' % (pkg.id, missing[:10]))
    out = [po_header(pkg.id)]
    for ctx, msgid in en:
        out.append(po_entry(ctx, msgid, po_escape(hu[ctx.lstrip('#')])))
    en_extra = []
    for num, text in sorted(extra.items()):
        out.append(po_entry('#%d' % num, po_escape(text), po_escape(text)))
        en_extra.append(po_entry('#%d' % num, po_escape(text), ''))
    pkg.put(ld + 'resource.language.hu_hu/strings.po', ''.join(out))
    if en_extra:                             # az új azonosítók az angol fájlba is (msgid = magyar)
        base = pkg.get(en_rel) if pkg.has(en_rel) else po_header(pkg.id).replace('hu_HU', 'en_GB')
        pkg.put(en_rel, base.rstrip('\n') + '\n\n' + ''.join(en_extra))


def settings_help(pkg):
    """A beállítások help="" attribútumainak kitöltése a forditas/<id>.sugo.tsv alapján."""
    helps = read_tsv(pkg.id + '.sugo.tsv')
    if not helps or not pkg.has('resources/settings.xml'):
        return {}
    s = pkg.get('resources/settings.xml')
    extra = {}
    num = HELP_BASE
    for sid, text in helps.items():
        num += 1
        extra[num] = text
        pat = re.compile(r'<setting\b[^>]*\bid="%s"[^>]*>' % re.escape(sid))
        m = pat.search(s)
        if not m:
            raise SystemExit('%s: nincs ilyen beállítás: %s' % (pkg.id, sid))
        tag = re.sub(r'\s+help="[^"]*"', '', m.group(0))
        tag = re.sub(r'(\s*/?>)$', lambda e: ' help="%d"%s' % (num, e.group(1)), tag)
        s = s[:m.start()] + tag + s[m.end():]
    pkg.put('resources/settings.xml', s)
    return extra


def convert_old_settings(pkg):
    """Régi (version nélküli) settings.xml átírása az új formátumra, hogy legyen súgó."""
    if pkg.id == 'screensaver.bingie':
        pkg.put('resources/settings.xml', '''<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<settings version="1">
	<section id="screensaver.bingie">
		<category id="general" label="32000">
			<group id="1">
				<setting id="choose" type="action" label="32001" help="">
					<level>0</level>
					<data>RunScript(screensaver.bingie, mode=choose)</data>
					<control type="button" format="action"><close>true</close></control>
				</setting>
				<setting id="label" type="action" label="32002" help="">
					<level>0</level>
					<data>RunScript(screensaver.bingie, mode=label)</data>
					<control type="button" format="action"><close>true</close></control>
				</setting>
			</group>
		</category>
	</section>
</settings>
''')
    elif pkg.id == 'script.bingie.helper':
        pkg.put('resources/settings.xml', '''<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<settings version="1">
	<section id="script.bingie.helper">
		<category id="general" label="128">
			<group id="1" label="14092">
				<setting id="log" type="boolean" label="666" help="">
					<level>0</level>
					<default>false</default>
					<control type="toggle"/>
				</setting>
				<setting id="debuglog" type="boolean" label="20191" help="">
					<level>0</level>
					<default>false</default>
					<control type="toggle"/>
				</setting>
			</group>
		</category>
	</section>
</settings>
''')
        # nincs saját nyelvi mappája: kell egy angol alap a súgó-azonosítókhoz
        pkg.put('resources/language/resource.language.en_gb/strings.po', po_header(pkg.id).replace('hu_HU', 'en_GB'))


# a kódba égetett angol feliratok
CODE_PATCHES = {
    'script.bingie.helper': [
        ('default.py', "Dialog().ok('Error', 'This is a tool to provide features to a skin and requires skin integration.')",
         "Dialog().ok('Hiba', 'Ez egy segédeszköz, amely a skin funkcióit szolgálja ki, ezért skin-integrációt igényel.')"),
    ],
    'script.bingie.toolbox': [
        ('resources/lib/main_module.py', 'xbmcgui.ListItem(label="None")', 'xbmcgui.ListItem(label="Nincs")'),
        ('resources/lib/skinsettings.py', 'notification("Invalid input", "Please enter a number...")',
         'notification("Érvénytelen érték", "Adj meg egy számot…")'),
    ],
    'script.module.bingie': [
        # a requests (+ urllib3, ssl) csak akkor töltődjön be, ha tényleg kell hálózat:
        # gyorsítótárból kiszolgált listáknál ez minden widget-hívásnál megspórolható
        ('resources/modules/bingie/reqapi.py', '\nimport requests\n', '\n'),
    ],
    'plugin.video.tmdb.bingie.helper': [
        # háttérfigyelő: ha ~2 mp-ig nem változik a kijelölt elem, ritkábban kérdez (0,2 -> 0,35 mp),
        # változáskor azonnal visszaáll; kevesebb Kodi-hívás = kevesebb verseny a kirajzolással
        ('resources/tmdbbingiehelper/lib/monitor/service.py',
         '''    def _on_listitem(self):
        self.listitem_funcs.on_listitem()
        self._on_idle(POLL_MIN_INCREMENT)''',
         '''    def _on_listitem(self):
        self.listitem_funcs.on_listitem()
        self._on_idle(self._hu_listitem_wait())

    def _hu_listitem_wait(self):
        cur = (getattr(self.listitem_funcs, '_cur_item', None), getattr(self.listitem_funcs, '_cur_window', None))
        if cur != getattr(self, '_hu_last', None):
            self._hu_last, self._hu_idle = cur, 0
            return POLL_MIN_INCREMENT
        self._hu_idle = getattr(self, '_hu_idle', 0) + 1
        return POLL_MIN_INCREMENT if self._hu_idle < 10 else 0.35'''),
        # magyar cím / leírás hiányában angol (a TMDb ilyenkor az eredeti, pl. japán/kínai/koreai
        # címet adja, amit a Kodi betűtípusai sokszor nem is tudnak megjeleníteni)
        ('resources/tmdbbingiehelper/lib/items/builder.py',
         """            details = self.tmdb_api.get_details_request(tmdb_type, tmdb_id, season, episode, cache_refresh=cache_refresh)
""",
         """            details = self.tmdb_api.get_details_request(tmdb_type, tmdb_id, season, episode, cache_refresh=cache_refresh)
            if details and season is None:
                details = hu_latin_fallback(self.tmdb_api, tmdb_type, tmdb_id, details)
"""),
        ('resources/tmdbbingiehelper/lib/items/builder.py',
         """        return f'v2.{language}.{tmdb_type}.{tmdb_id}.{season}.{episode}'""",
         """        return f'v2hu1.{language}.{tmdb_type}.{tmdb_id}.{season}.{episode}'"""),
        ('resources/tmdbbingiehelper/lib/items/builder.py', '\nCACHE_DAYS = 10000\n', '''
CACHE_DAYS = 10000

# minden, ami nem latin betű / írásjel / szám (TomSzo – magyar kiadás)
HU_NONLATIN = re.compile('[^\\x00-\\x7f\\u00a0-\\u024f\\u1e00-\\u1eff\\u2000-\\u206f\\u20a0-\\u20cf\\u2100-\\u214f]')


def hu_latin_fallback(tmdb_api, tmdb_type, tmdb_id, details):
    """Ha a beállított nyelven nincs cím (a TMDb az eredeti, nem latin betűs címet adja) vagy
    leírás, az angol fordítást használja. A fordításokat csak ilyenkor kéri le (gyorsítótárazva)."""
    if tmdb_type not in ('movie', 'tv'):
        return details
    if (getattr(tmdb_api, 'iso_language', '') or 'en') == 'en':
        return details
    key = 'title' if tmdb_type == 'movie' else 'name'
    need_title = bool(HU_NONLATIN.search(details.get(key) or ''))
    need_plot = not details.get('overview')
    if not need_title and not need_plot:
        return details
    try:
        trans = (tmdb_api.get_request_lc(tmdb_type, tmdb_id, 'translations') or {}).get('translations') or []
    except Exception:
        return details

    def pick(field):
        for country in ('US', 'GB', None):
            for t in trans:
                if t.get('iso_639_1') != 'en' or (country and t.get('iso_3166_1') != country):
                    continue
                v = (t.get('data') or {}).get(field)
                if v and (field == 'overview' or not HU_NONLATIN.search(v)):
                    return v

    if need_title:
        details[key] = pick(key) or details.get(key)
    if need_plot:
        details['overview'] = pick('overview') or details.get('overview')
    return details
'''),
        ('resources/tmdbbingiehelper/lib/api/wikipedia/api.py', "Dialog().select('Links', links)",
         "Dialog().select('Hivatkozások', links)"),
        ('resources/tmdbbingiehelper/lib/api/wikipedia/api.py', "Dialog().select('Languages',",
         "Dialog().select('Nyelvek',"),
        ('resources/tmdbbingiehelper/lib/api/tmdb/discover.py', "Dialog().input('Rename',",
         "Dialog().input('Átnevezés',"),
        ('resources/tmdbbingiehelper/lib/script/method/maintenance.py', "'Kodi Library cached to memory'",
         "'Kodi-könyvtár betöltve a memóriába'"),
    ],
}


def default_patches(pkg):
    """Magyar alapértékek: a TMDb-adatok (címek, leírások) magyarul jöjjenek."""
    if pkg.id == 'plugin.video.tmdb.bingie.helper':
        s = pkg.get('resources/settings.xml')
        m = re.search(r'<setting id="language"[^>]*>.*?</setting>', s, re.S)
        block = m.group(0)
        if '<option label="30031">31</option>' not in block:
            raise SystemExit('TMDb nyelvi beállítás: nincs magyar opció')
        block2 = replace_once(block, '<default>18</default>', '<default>31</default>', 'TMDb nyelv alapérték')
        s = s.replace(block, block2)
        # párhuzamos szálak: korlátlan helyett 4 (mérve: hideg listánál 3-6x kevesebb CPU, a
        # kapcsolatok újrahasznosulnak, kevesebb TLS-kézfogás; a falióra-idő sem nő)
        m = re.search(r'<setting id="max_threads"[^>]*>.*?</setting>', s, re.S)
        s = s.replace(m.group(0), replace_once(m.group(0), '<default>0</default>', '<default>4</default>', 'max_threads'))
        pkg.put('resources/settings.xml', s)


def code_patches(pkg):
    default_patches(pkg)
    for rel, old, new in CODE_PATCHES.get(pkg.id, []):
        pkg.put(rel, replace_once(pkg.get(rel), old, new, '%s/%s' % (pkg.id, rel)))


# --- skin: súgó-infódoboz -----------------------------------------------------------------
INFOBOX = '''
        <!-- Magyar súgó: a kijelölt beállítás leírása (TomSzo) -->
        <control type="group">
            <left>%(left)d</left><top>%(top)d</top><width>%(width)d</width><height>%(height)d</height>
            <control type="image">
                <width>%(width)d</width><height>%(height)d</height>
                <texture border="15">diffuse/bgpanel.png</texture>
                <colordiffuse>$INFO[Skin.String(GeneralPanelsColor)]</colordiffuse>
            </control>
            <control type="image">
                <left>24</left><top>22</top><width>34</width><height>34</height>
                <texture colordiffuse="$INFO[Skin.String(ButtonFocusColor)]">common/settings1.png</texture>
            </control>
            <control type="textbox">
                <left>76</left><top>14</top><width>%(tw)d</width><height>%(th)d</height>
                <font>Reg24</font>
                <textcolor>$INFO[Skin.String(GeneralTextColor)]</textcolor>
                <label>$VAR[HU_Sugo]</label>
                <autoscroll delay="4000" time="2500" repeat="6000">true</autoscroll>
            </control>
        </control>
'''


def skin_patches(pkg, items):
    """Súgóváltozó, infódobozok, beégetett feliratok."""
    helps = read_tsv('skin.bingie.sugo.tsv')
    extra = {}
    num = SKIN_HELP_BASE
    values = []
    for cid, text in helps.items():
        num += 1
        extra[num] = text
        values.append('        <value condition="Control.HasFocus(%s)">$LOCALIZE[%d]</value>' % (cid, num))
    num += 1
    extra[num] = 'Színválasztó: megnyitja a palettát, ahonnan színt választhatsz, vagy megadhatod a színkódot. Az új szín azonnal látszik.'
    colors = sorted(k for k, v in items.items() if v[0] == 'ColorButton')
    cond = ' | '.join('Control.HasFocus(%s)' % c for c in colors)
    values.append('        <value condition="%s">$LOCALIZE[%d]</value>' % (cond, num))
    inc = ('<?xml version="1.0" encoding="utf-8"?>\n<!-- Magyar súgószövegek a skinbeállításokhoz (TomSzo, generált) -->\n'
           '<includes>\n    <variable name="HU_Sugo">\n%s\n    </variable>\n</includes>\n' % '\n'.join(values))
    pkg.put('1080i/IncludesHuSugo.xml', inc)
    s = pkg.get('1080i/Includes.xml')
    s = replace_once(s, '<includes>', '<includes>\n    <include file="IncludesHuSugo.xml" />', 'Includes.xml')
    pkg.put('1080i/Includes.xml', s)

    # skinbeállítások ablak: a lista alatt
    s = pkg.get('1080i/SkinSettings.xml')
    box = INFOBOX % {'left': 60, 'top': 955, 'width': 1800, 'height': 110, 'tw': 1700, 'th': 84}
    s = replace_once(s, '        <include condition="Skin.HasSetting(DebugGrid)',
                     box + '        <include condition="Skin.HasSetting(DebugGrid)', 'SkinSettings.xml')
    pkg.put('1080i/SkinSettings.xml', s)
    # oldalpanel-változat (a kezdőképernyőről nyíló skinbeállítás)
    s = pkg.get('1080i/Custom_1105_SkinSettings.xml')
    box = INFOBOX % {'left': 677, 'top': 935, 'width': 1196, 'height': 130, 'tw': 1096, 'th': 104}
    s = replace_once(s, '\n    </controls>', box + '\n    </controls>', 'Custom_1105_SkinSettings.xml')
    pkg.put('1080i/Custom_1105_SkinSettings.xml', s)

    # kiegészítő-beállítások ablak: leírásmező (id=6, a Kodi tölti ki a help szöveggel)
    s = pkg.get('1080i/DialogAddonSettings.xml')
    for old, new in [('<posy>169</posy>', '<posy>109</posy>'), ('<height>730</height>', '<height>850</height>')]:
        if s.count(old) != 2:
            raise SystemExit('DialogAddonSettings.xml: váratlan szerkezet (%s)' % old)
        s = s.replace(old, new)
    s = replace_once(s, '<posy>205</posy>', '<posy>145</posy>', 'DialogAddonSettings fejléc')
    if s.count('<posy>303</posy>') != 2:
        raise SystemExit('DialogAddonSettings.xml: váratlan szerkezet (303)')
    s = s.replace('<posy>303</posy>', '<posy>243</posy>')
    s = replace_once(s, '<posy>304</posy>', '<posy>244</posy>', 'DialogAddonSettings görgetősáv')
    s = replace_once(s, '<posx>320</posx>\n                <posy>800</posy>',
                     '<posx>320</posx>\n                <posy>838</posy>', 'DialogAddonSettings gombok')
    desc = '''
            <!-- Magyar súgó: a kijelölt beállítás leírása (TomSzo) -->
            <control type="image">
                <posx>329</posx><posy>732</posy><width>1263</width><height>92</height>
                <texture border="5">dialogs/default/inner.png</texture>
            </control>
            <control type="textbox" id="6">
                <posx>349</posx><posy>740</posy><width>1223</width><height>78</height>
                <font>Reg24</font>
                <textcolor>$INFO[Skin.String(GeneralTextColor)]</textcolor>
                <autoscroll delay="4000" time="2500" repeat="6000">true</autoscroll>
            </control>
'''
    s = replace_once(s, '            <control type="button" id="7">', desc + '            <control type="button" id="7">',
                     'DialogAddonSettings leírásmező')
    pkg.put('1080i/DialogAddonSettings.xml', s)

    # az alap-színtéma színnevei (ezek jelennek meg a színgombok mellett)
    names = {'Amber': 'Borostyán', 'Black': 'Fekete', 'Blue': 'Kék', 'Dark grey': 'Sötétszürke',
             'Green': 'Zöld', 'Grey': 'Szürke', 'Light grey': 'Világosszürke', 'Light red': 'Világospiros',
             'None': 'Nincs', 'Onyx': 'Ónix', 'Orange': 'Narancs', 'Pink': 'Rózsaszín', 'Red': 'Piros',
             'White': 'Fehér', 'Yellow': 'Sárga'}
    s = pkg.get('extras/skinthemes/Reset.theme')
    s = re.sub(r"(\.name', ')([^']*)(')", lambda m: m.group(1) + names.get(m.group(2), m.group(2)) + m.group(3), s)
    s = replace_once(s, "('DESCRIPTION', 'Reset theme to default.')",
                     "('DESCRIPTION', 'Minden szín visszaállítása az alapértelmezettre.')", 'Reset.theme')
    pkg.put('extras/skinthemes/Reset.theme', s)

    # beégetett widgetnevek
    s = pkg.get('1080i/IncludesHomeWidgets.xml')
    for en, hu in [('"Recently Watched"', '"Nemrég nézett"'), ('"Channels"', '"Csatornák"'),
                   ('"Recordings"', '"Felvételek"')]:
        s = s.replace('name="widgetName" value=%s' % en, 'name="widgetName" value=%s' % hu)
    pkg.put('1080i/IncludesHomeWidgets.xml', s)
    return extra


# képek, amelyek külső forrásból (internet / könyvtár) jönnek: háttérben töltődjenek,
# hogy görgetéskor ne akadjon a felület
ASYNC_TEXTURES = {
    'Includes.xml': ('$VAR[VideoListThumbVar]', 2),
    'IncludesBingie.xml': ('ListItem.Property(Cast.1.Thumb)', 1),
    'IncludesHomeBingie.xml': ('ListItem.Property(Cast.1.Thumb)', 1),
    'IncludesDialogVideoInfo.xml': ('$VAR[LandscapeImage]', 2),
    'View_525_Bingie_Episodes.xml': ('$VAR[LandscapeImage]', 1),
    'View_527_Bingie_Seasons.xml': ('$VAR[LandscapeImage]', 1),
    'DialogVideoManager.xml': ('$VAR[VideoListPosterVar]', 2),
    'MyPVRGuide.xml': ('$VAR[PVRThumb]', 1),
    'View_10_SimplePVR.xml': ('$VAR[PVRThumb]', 1),
    'IncludesOSDDialogs.xml': ('.Icon]', 5),
}

GYORSMOD = [
    'Skin.Reset(BingieAutoTrailer)', 'Skin.Reset(SpotLightTrailers)', 'Skin.Reset(BackgroundAnimation)',
    'Skin.Reset(EnableSnowAnimation)', 'Skin.SetBool(EnableFixedFrameWidgets)', 'Skin.Reset(AutoHidePlotOnIdle)',
    'Skin.Reset(EnableNativeExtraFanart)', 'Skin.Reset(RandomizeBackground)', 'Skin.Reset(animateMusicArt)',
    'Skin.SetString(SplashAnimationResolution,1080p)', 'Skin.SetString(splash_screen,none)',
    'Skin.SetString(splash_screen.label,$LOCALIZE[231])',
]


def skin_optimize(pkg):
    """Sebességjavítások a skinben (a viselkedés nem változik)."""
    extra = {31690: 'TV-box gyorsmód (nehéz effektek kikapcsolása)',
             31691: 'Kész: előzetesek, animációk és indítóvideó kikapcsolva.',
             31692: 'TV-box gyorsmód'}
    # 1) külső képek háttérbetöltése
    for name, (needle, count) in ASYNC_TEXTURES.items():
        s = pkg.get('1080i/' + name)
        pat = re.compile(r'<texture(?![^>]*background=)([^>]*)>([^<]*%s[^<]*)</texture>' % re.escape(needle))
        s, n = pat.subn(r'<texture background="true"\1>\2</texture>', s)
        if n != count:
            raise SystemExit('%s: %d háttérbetöltés helyett %d' % (name, count, n))
        pkg.put('1080i/' + name, s)
    # 2) a skinshortcuts-menüépítő a kezdőképernyőn munkamenetenként egyszer fusson
    #    (a menü csak a skinbeállításokban szerkeszthető, onnan kilépve úgyis újraépül)
    s = pkg.get('1080i/Home.xml')
    s = replace_once(s, '<onload>RunScript(script.skinshortcuts,type=buildxml',
                     '<onload condition="String.IsEmpty(Window(Home).Property(HU_MenuBuilt))">'
                     'RunScript(script.skinshortcuts,type=buildxml', 'Home.xml buildxml')
    s = replace_once(s, '<onload condition="String.IsEmpty(Window(Home).Property(widgetstyle))">',
                     '<onload>SetProperty(HU_MenuBuilt,1,Home)</onload>\n    '
                     '<onload condition="String.IsEmpty(Window(Home).Property(widgetstyle))">', 'Home.xml jelző')
    pkg.put('1080i/Home.xml', s)
    s = pkg.get('1080i/Custom_1105_SkinSettings.xml')
    s = replace_once(s, '<onunload>ClearProperty(SkinSettingSection,Home)</onunload>',
                     '<onunload>ClearProperty(SkinSettingSection,Home)</onunload>\n'
                     '    <onunload>ClearProperty(HU_MenuBuilt,Home)</onunload>', 'Custom_1105 jelző')
    pkg.put('1080i/Custom_1105_SkinSettings.xml', s)
    # 3) TV-box gyorsmód gomb (Általános skinbeállítások → Haladó)
    s = pkg.get('1080i/IncludesSkinSettings.xml')
    btn = ('\n        <!-- TV-box gyorsmód (TomSzo) -->\n        <control type="button" id="31690">\n'
           '            <include>SkinSettings_Button</include>\n            <label>$LOCALIZE[31690]</label>\n'
           + ''.join('            <onclick>%s</onclick>\n' % a for a in GYORSMOD) +
           '            <onclick>Notification($LOCALIZE[31692],$LOCALIZE[31691],5000)</onclick>\n        </control>')
    anchor = '            <label>$LOCALIZE[35226]</label>\n        </control>'
    s = replace_once(s, anchor, anchor + btn, 'gyorsmód gomb')
    pkg.put('1080i/IncludesSkinSettings.xml', s)
    return extra


TINYPPI = 'script.signde.tinyppi'
HAS_PPI = 'System.HasAddon(%s)' % TINYPPI
EXTRA = os.path.join(BASE, 'extra')          # saját fájlok a skinbe (pl. VS10-ikonok a signde Bingie-ből, GPL-2)


def skin_tinyppi(pkg):
    """signde PPI (tinyppi, jamal2362 / signde) bekötése, ahogy a signde AVDV-s Bingie-je csinálja:
    a lejátszási infó (PlayerProcessInfo) ablak a tinyppit nyitja, az OSD-n VS10-gomb.
    Ha a tinyppi nincs telepítve, minden marad a régiben."""
    s = pkg.get('1080i/DialogPlayerProcessInfo.xml')
    if TINYPPI in s:                         # a signde-féle skinben már be van kötve
        skin_vs10_window(pkg)
        skin_ppi_button(pkg)
        return
    s = replace_once(s, '<window>\n', '<window>\n'
                     '\t<!-- signde PPI (tinyppi), ha telepítve van; különben a skin saját ablaka -->\n'
                     '\t<onload condition="%s">RunScript(%s)</onload>\n'
                     '\t<onload condition="%s">Close</onload>\n' % (HAS_PPI, TINYPPI, HAS_PPI), 'PPI ablak')
    pkg.put('1080i/DialogPlayerProcessInfo.xml', s)
    pkg.put('1080i/Custom_1160_OSD_PPI_VS10.xml', '''<?xml version="1.0" encoding="UTF-8"?>
<window type="dialog" id="1160">
    <!-- Az OSD VS10-gombja: a signde PPI párbeszédablaka (VS10-mód, lejátszási infó) -->
    <onload>RunScript(script.signde.tinyppi,dialog)</onload>
    <onload>Close</onload>
    <controls />
</window>
''')
    button = (
        '{t}<control type="button" id="8499">\n'
        '{t}\t<description>VS10 / signde PPI</description>\n'
        '{t}\t<width>$PARAM[{size}]</width>\n{t}\t<height>$PARAM[{size}]</height>\n'
        '{t}\t<label/>\n{t}\t<font/>\n'
        '{t}\t<texturefocus colordiffuse="$INFO[Skin.String({fc})]">osd/vs10_fo.png</texturefocus>\n'
        '{t}\t<texturenofocus colordiffuse="$INFO[Skin.String({c})]">osd/vs10.png</texturenofocus>\n'
        '{t}\t<onclick>ActivateWindow(1160)</onclick>\n'
        '{t}\t<visible>Player.HasVideo</visible>\n'
        '{t}\t<visible>System.AddonIsEnabled(service.coreelec.settings) + ' + HAS_PPI + '</visible>\n'
        '{t}</control>\n')
    s = pkg.get('1080i/IncludesOSD.xml')
    old = '\t\t\t\t<onclick>ActivateWindow(123)</onclick>\n\t\t\t\t<visible>Player.HasVideo</visible>\n\t\t\t</control>\n'
    s = replace_once(s, old, old + button.format(t='\t\t\t', size='size', fc='OSDButtonsFocusColor',
                                                 c='OSDButtonsColor'), 'OSD VS10 (alap)')
    old = ('                    <onclick>ActivateWindow(123)</onclick>\n'
           '\t\t\t\t\t<visible>Skin.HasSetting(bingie_osd_buttons_video)</visible>\n'
           '\t\t\t\t\t<visible>Player.HasVideo</visible>\n                </control>\n')
    s = replace_once(s, old, old + button.format(t='\t\t\t\t', size='topsize', fc='OSDBingieButtonsFocusColor',
                                                 c='OSDBingieButtonsColor'), 'OSD VS10 (Bingie)')
    pkg.put('1080i/IncludesOSD.xml', s)
    for name in ('vs10.png', 'vs10_fo.png'):
        with open(os.path.join(EXTRA, 'media', 'osd', name), 'rb') as f:
            pkg.files[pkg.path('media/osd/' + name)] = f.read()
    skin_ppi_button(pkg)


def skin_vs10_window(pkg):
    """A signde-skin VS10-ablakából (Custom_1160) hiányzik az id: a Kodi az id nélküli egyéni ablakot
    be sem tölti, így az OSD VS10-gombjának ActivateWindow(1160)-a nem csinál semmit."""
    rel = '1080i/Custom_1160_OSD_PPI_VS10.xml'
    if not pkg.has(rel):
        return
    s = pkg.get(rel)
    if re.search(r'<window\b[^>]*\bid=', s):
        return
    pkg.put(rel, replace_once(s, '<window>', '<window type="dialog" id="1160">', 'VS10 ablak id'))


def skin_ppi_button(pkg):
    """PPI-gomb az OSD-n a VS10-gomb után: a signde PPI (tinyppi) lejátszási infó-ablaka.
    Csak ha a tinyppi telepítve van; ikon: a VS10-ikon stílusában (extra/media/osd/ppi*.png)."""
    s = pkg.get('1080i/IncludesOSD.xml')
    if 'id="8498"' in s:
        return
    button = (
        '{t}<control type="button" id="8498">\n'
        '{t}\t<description>signde PPI</description>\n'
        '{t}\t<width>$PARAM[{size}]</width>\n{t}\t<height>$PARAM[{size}]</height>\n'
        '{t}\t<label/>\n{t}\t<font/>\n'
        '{t}\t<texturefocus colordiffuse="$INFO[Skin.String({fc})]">osd/ppi_fo.png</texturefocus>\n'
        '{t}\t<texturenofocus colordiffuse="$INFO[Skin.String({c})]">osd/ppi.png</texturenofocus>\n'
        '{t}\t<onclick>Dialog.Close(VideoOSD)</onclick>\n'
        '{t}\t<onclick>RunScript(' + TINYPPI + ')</onclick>\n'
        '{t}\t<visible>Player.HasVideo + ' + HAS_PPI + '</visible>\n'
        '{t}</control>\n')
    n = 0
    for m in reversed(list(re.finditer(r'([ \t]*)<control type="button" id="8499">.*?</control>\n', s, re.S))):
        t = m.group(1)
        topsize = '$PARAM[topsize]' in m.group(0)
        btn = button.format(t=t, size='topsize' if topsize else 'size',
                            fc='OSDBingieButtonsFocusColor' if topsize else 'OSDButtonsFocusColor',
                            c='OSDBingieButtonsColor' if topsize else 'OSDButtonsColor')
        s = s[:m.end()] + btn + s[m.end():]
        n += 1
    if n != 2:
        raise SystemExit('PPI-gomb: %d VS10-gombot találtam (2 kellene)' % n)
    s = replace_once(s, '<value condition="Control.HasFocus(8499)">VS10</value>',
                     '<value condition="Control.HasFocus(8499)">VS10</value>\n'
                     '        <value condition="Control.HasFocus(8498)">LEJÁTSZÁSI INFÓ (PPI)</value>', 'PPI-gomb felirat')
    pkg.put('1080i/IncludesOSD.xml', s)
    for name in ('ppi.png', 'ppi_fo.png'):
        with open(os.path.join(EXTRA, 'media', 'osd', name), 'rb') as f:
            pkg.files[pkg.path('media/osd/' + name)] = f.read()


def skin_setting_items(pkg):
    """A skinbeállítások vezérlői: id -> (típus, felirat)."""
    s = pkg.get('1080i/IncludesSkinSettings.xml')
    items = {}
    for m in re.finditer(r'<control type="(radiobutton|button|togglebutton|spincontrolex|edit)" id="(\d+)">', s):
        items.setdefault(m.group(2), (m.group(1), ''))
    for m in re.finditer(r'<include content="SkinSettings_(ActionButton|ColorButton|AddonButton)">(.*?)</include>', s, re.S):
        p = dict(re.findall(r'<param name="(\w+)" value="([^"]*)"', m.group(2)))
        items.setdefault(p['id'], (m.group(1), ''))
    return items


# --- addon.xml -------------------------------------------------------------------------
META = {
    'skin.bingie': ('Kodi-skin Netflix-elrendezéssel.',
                    'Bingie – a kedvenc filmjeid és sorozataid otthona! Magyar fordítással és súgóval (TomSzo).'),
    'plugin.video.tmdb.bingie.helper': ('TMDb Bingie Helper',
                                        'Filmek, sorozatok és színészek adatai a TMDb-ről, listák a TMDb, TVDb, '
                                        'MDbList és Trakt szolgáltatásokból. A Bingie skin widgetjeinek és adatlapjainak motorja.'),
    'plugin.program.autocompletion': ('Automatikus kiegészítés a képernyő-billentyűzethez (skin-támogatás kell)',
                                      'Keresési javaslatok a képernyő-billentyűzethez gépelés közben (skin-támogatás kell).'),
    'screensaver.bingie': ('Bingie képernyővédő', 'Netflix-stílusú képernyővédő a Bingie skinhez.'),
    'script.bingie.helper': ('Bingie Helper', 'Segédprogram a Bingie skin egyes funkcióihoz.'),
    'script.bingie.toolbox': ('Bingie Toolbox', 'Eszköztár a Bingie skinhez.'),
    'script.bingie.widgets': ('Bingie Widgets', 'Widgetek a Bingie skinhez.'),
    'script.module.bingie': ('Bingie modul', 'Közös kód a TMDb Bingie Helperhez.'),
    'script.skin.helper.colorpicker': ('Színválasztó Kodi-skinekhez', 'Színválasztó Kodi-skinekhez (Skin Helper csomag).'),
    'script.skin.helper.skinbackup': ('Skinmentés Kodi-skinekhez', 'Skinbeállítások mentése, visszaállítása és színtémák kezelése.'),
}


def patch_addon_xml(pkg, version):
    s = pkg.get('addon.xml')
    s = re.sub(r'(<addon\b[^>]*\bversion=")([^"]+)(")', lambda m: m.group(1) + version + m.group(3), s, count=1)
    summ, desc = META[pkg.id]
    s = re.sub(r'\s*<(summary|description|disclaimer)\s+lang="hu_HU">.*?</\1>', '', s, flags=re.S)
    add = ('\n\t\t<summary lang="hu_HU">%s</summary>\n\t\t<description lang="hu_HU">%s</description>'
           '\n\t\t<disclaimer lang="hu_HU">Magyar fordítás és súgó: TomSzo (privát tároló). '
           'Eredeti: matke-84/repository.bingie.</disclaimer>' % (summ, desc))
    s = replace_once(s, '<extension point="xbmc.addon.metadata">', '<extension point="xbmc.addon.metadata">' + add,
                     pkg.id + ' addon.xml metadata')
    pkg.put('addon.xml', s)
    return s


# --- fő folyamat --------------------------------------------------------------------------
def upstream_list():
    """(id, verzió, alap-URL) a matke-tárolóból; a FROM_SIGNDE csomagok a signde-tárolóból."""
    matke = ET.parse(fetch(UPSTREAM + 'addons.xml', os.path.join(CACHE, 'addons.xml'))).getroot()
    signde = ET.parse(fetch(SIGNDE + 'addons.xml', os.path.join(CACHE, 'signde-addons.xml'))).getroot()
    sver = {a.get('id'): a.get('version') for a in signde}
    out = []
    for a in matke:
        aid = a.get('id')
        if aid in SKIP:
            continue
        if aid in FROM_SIGNDE:
            if aid not in sver:
                raise SystemExit('A signde-tárolóban nincs: %s' % aid)
            out.append((aid, sver[aid], SIGNDE))
        else:
            out.append((aid, a.get('version'), UPSTREAM))
    return out


def main():
    built = []
    for aid, ver, base in upstream_list():
        zpath = fetch('%s%s/%s-%s.zip' % (base, aid, aid, ver), os.path.join(CACHE, '%s-%s.zip' % (aid, ver)))
        with zipfile.ZipFile(zpath) as z:
            files = {n: z.read(n) for n in z.namelist() if not n.endswith('/')}
        pkg = Pkg(aid, files)
        extra = {}
        if aid == 'skin.bingie':
            extra = skin_optimize(pkg)
            skin_tinyppi(pkg)
            extra.update(skin_patches(pkg, skin_setting_items(pkg)))
        else:
            convert_old_settings(pkg)
            extra = settings_help(pkg)
        translate(pkg, extra)
        code_patches(pkg)
        newver = ver + REVISION.get(aid, SUFFIX)
        xml = patch_addon_xml(pkg, newver)
        outdir = os.path.join(PRIVAT, aid)
        if os.path.isdir(outdir):
            shutil.rmtree(outdir)
        os.makedirs(outdir)
        zout = os.path.join(outdir, '%s-%s.zip' % (aid, newver))
        with zipfile.ZipFile(zout, 'w', zipfile.ZIP_DEFLATED) as z:
            for n in sorted(pkg.files):          # rögzített dátum: azonos tartalom = azonos zip
                info = zipfile.ZipInfo(n, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                z.writestr(info, pkg.files[n])
        with open(os.path.join(outdir, 'addon.xml'), 'w', encoding='utf-8') as f:
            f.write(xml)
        for art in ('icon.png', 'fanart.jpg', 'resources/icon.png', 'resources/fanart.jpg'):
            if pkg.has(art):
                dst = os.path.join(outdir, art)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(dst, 'wb') as f:
                    f.write(pkg.files[pkg.path(art)])
        built.append((aid, newver, xml))
        print('kész: %s %s (%.1f MB)' % (aid, newver, os.path.getsize(zout) / 1e6))
    update_repo(built)


def update_repo(built):
    """A privát tároló addons.xml-je: a meglévő <addon> blokkok + a most épített (tisztán, újraírva)."""
    path = os.path.join(PRIVAT, 'addons.xml')
    s = open(path, encoding='utf-8-sig').read()
    blocks = re.findall(r'<addon\b.*?</addon>', s, re.S)
    ours = {aid for aid, _, _ in built}
    keep = [b for b in blocks if re.search(r'<addon\b[^>]*\bid="([^"]+)"', b).group(1) not in ours]
    for aid, _, xml in built:
        keep.append(re.search(r'<addon\b.*</addon>', xml.lstrip('\ufeff'), re.S).group(0))
    out = '<?xml version="1.0" encoding="UTF-8"?>\n<addons>\n' + '\n'.join(keep) + '\n</addons>\n'
    ET.fromstring(out.encode('utf-8'))      # érvényes XML-e
    open(path, 'w', encoding='utf-8').write(out)
    open(path + '.md5', 'w').write(hashlib.md5(out.encode('utf-8')).hexdigest())
    print('privat/addons.xml frissítve (%d kiegészítő, összesen %d)' % (len(built), len(keep)))

if __name__ == '__main__':
    main()
