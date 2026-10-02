#!/usr/bin/env python3
"""A TomSzo AVDV kezdőképernyőjének generálása (xml/Home.xml + xml/Includes_TomSzo.xml).

Streaming-stílus: bal oldali menüsáv, nagy hero a kijelölt elem képével / logójával /
leírásával, alatta vízszintes widget-sorok szekciónként (Kezdőlap, Filmek, Sorozatok,
Sport, Anime). A sorokat a ROWS lista írja le; a hero-kötések (melyik sor melyik elemét
mutassa) ebből generálódnak, ezért kézzel nem kell az XML-ben szerkeszteni.

Futtatás a skin mappájából:  python3 _tools/build_home.py
"""
import os
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TMDB = 'plugin://plugin.video.themoviedb.helper/'
N4 = 'plugin://plugin.video.network4/'
MA = 'plugin://plugin.video.magyaranime/'
MTK = 'plugin://plugin.video.mutekifansub/'
KTS = 'plugin://plugin.video.kintsugifansub/'
NK = 'plugin://plugin.video.narutokun/'

# Szekciók: kulcs, menüfelirat, ikon, a hero üres állapotának szövege
SECTIONS = [
    ('home', 'Kezdőlap', 'home', 'Üdv itthon!'),
    ('movies', 'Filmek', 'movies', 'Filmek'),
    ('tvshows', 'Sorozatok', 'tv', 'Sorozatok'),
    ('sport', 'Sport', 'sport', 'Sport – Network4'),
    ('anime', 'Anime', 'anime', 'Anime'),
]

# Widget-sorok. art: landscape = könyvtár / TMDb (háttérkép), thumb = az elem saját képe
# (Network4: az addon a közös fanartot adja minden elemhez), poster = álló borító (anime).
# addon: csak akkor látszik, ha az addon telepítve van.
ROWS = [
    # Kezdőlap
    ('home', 'Folytatás', 'special://skin/playlists/inprogress_movies.xsp', 'landscape', None),
    ('home', 'Élő sport – Network4', N4 + '?action=live', 'thumb', 'plugin.video.network4'),
    ('home', 'Felkapott filmek', TMDB + '?info=trending_week&tmdb_type=movie', 'landscape',
     'plugin.video.themoviedb.helper'),
    ('home', 'Felkapott sorozatok', TMDB + '?info=trending_week&tmdb_type=tv', 'landscape',
     'plugin.video.themoviedb.helper'),
    ('home', 'Anime – folytatás', MA + '?action=history', 'poster', 'plugin.video.magyaranime'),
    ('home', 'Új részek a könyvtárban', 'videodb://recentlyaddedepisodes/', 'landscape', None),
    ('home', 'Nemrég hozzáadott filmek', 'videodb://recentlyaddedmovies/', 'landscape', None),
    # Filmek
    ('movies', 'Folytatás', 'special://skin/playlists/inprogress_movies.xsp', 'landscape', None),
    ('movies', 'Nemrég hozzáadott', 'videodb://recentlyaddedmovies/', 'landscape', None),
    ('movies', 'Népszerű most', TMDB + '?info=popular&tmdb_type=movie', 'landscape',
     'plugin.video.themoviedb.helper'),
    ('movies', 'Most a mozikban', TMDB + '?info=now_playing&tmdb_type=movie', 'landscape',
     'plugin.video.themoviedb.helper'),
    ('movies', 'Legjobbra értékelt', TMDB + '?info=top_rated&tmdb_type=movie', 'landscape',
     'plugin.video.themoviedb.helper'),
    ('movies', 'Hamarosan', TMDB + '?info=upcoming&tmdb_type=movie', 'landscape',
     'plugin.video.themoviedb.helper'),
    ('movies', 'Még nem látott', 'special://skin/playlists/unwatched_movies.xsp', 'landscape', None),
    # Sorozatok
    ('tvshows', 'Új részek', 'videodb://recentlyaddedepisodes/', 'landscape', None),
    ('tvshows', 'Folyamatban', 'videodb://inprogresstvshows/', 'landscape', None),
    ('tvshows', 'Felkapott', TMDB + '?info=trending_week&tmdb_type=tv', 'landscape',
     'plugin.video.themoviedb.helper'),
    ('tvshows', 'Ma adásban', TMDB + '?info=airing_today&tmdb_type=tv', 'landscape',
     'plugin.video.themoviedb.helper'),
    ('tvshows', 'Népszerű sorozatok', TMDB + '?info=popular&tmdb_type=tv', 'landscape',
     'plugin.video.themoviedb.helper'),
    ('tvshows', 'Legjobbra értékelt', TMDB + '?info=top_rated&tmdb_type=tv', 'landscape',
     'plugin.video.themoviedb.helper'),
    # Sport (Network4)
    ('sport', 'Élő és hamarosan', N4 + '?action=live', 'thumb', 'plugin.video.network4'),
    ('sport', 'Kiemelt sportok', N4 + '?action=sportcat&i=0', 'thumb', 'plugin.video.network4'),
    ('sport', 'Premier League', N4 + '?action=collection&slug=premier-league', 'thumb',
     'plugin.video.network4'),
    ('sport', 'Bundesliga', N4 + '?action=collection&slug=bundesliga', 'thumb',
     'plugin.video.network4'),
    ('sport', 'NFL', N4 + '?action=collection&slug=nfl', 'thumb', 'plugin.video.network4'),
    ('sport', 'MotoGP', N4 + '?action=collection&slug=motogp', 'thumb', 'plugin.video.network4'),
    ('sport', 'UFC', N4 + '?action=collection&slug=ufc', 'thumb', 'plugin.video.network4'),
    # Anime (privát addonok)
    ('anime', 'MagyarAnime – folytatás', MA + '?action=history', 'poster', 'plugin.video.magyaranime'),
    ('anime', 'MagyarAnime – kedvencek', MA + '?action=favorites', 'poster', 'plugin.video.magyaranime'),
    ('anime', 'MagyarAnime – aktuális szezon', MA + '?action=catalog&allapot=1', 'poster',
     'plugin.video.magyaranime'),
    ('anime', 'Muteki Fansub – legfrissebb részek', MTK + '?action=latest', 'thumb',
     'plugin.video.mutekifansub'),
    ('anime', 'Kintsugi Fansub – legfrissebb részek', KTS + '?action=latest', 'thumb',
     'plugin.video.kintsugifansub'),
    ('anime', 'Naruto-Kun – legfrissebb részek', NK + '?action=latest', 'thumb',
     'plugin.video.narutokun'),
    ('anime', 'Muteki Fansub – kedvencek', MTK + '?action=favorites', 'poster',
     'plugin.video.mutekifansub'),
]

# a sorok azonosítói: 5101.. szekciónként (Kezdőlap 51xx, Filmek 52xx, ...)
SECTION_BASE = {'home': 5100, 'movies': 5200, 'tvshows': 5300, 'sport': 5400, 'anime': 5500}

RAIL = [  # menüsáv: (gomb-id, felirat, ikon, művelet vagy szekció)
    (9001, 'Keresés', 'search', 'ActivateWindow(1107)'),
    (9002, 'Kezdőlap', 'home', 'section:home'),
    (9003, 'Filmek', 'movies', 'section:movies'),
    (9004, 'Sorozatok', 'tv', 'section:tvshows'),
    (9005, 'Sport', 'sport', 'section:sport'),
    (9006, 'Anime', 'anime', 'section:anime'),
    (9007, 'Kiegészítők', 'addons', 'ActivateWindow(Videos,addons://sources/video/,return)'),
    (9008, 'Kedvencek', 'favourites', 'ActivateWindow(favouritesbrowser)'),
    (9009, 'Beállítások', 'settings', 'ActivateWindow(Settings)'),
    (9010, 'Kikapcsolás', 'power', 'ActivateWindow(shutdownmenu)'),
]

RAIL_TOP = 190
RAIL_STEP = 80
ROWS_TOP = 585
X0 = 180                      # a tartalom bal széle (a csukott menüsáv után)

CARD = {'landscape': (400, 225), 'thumb': (400, 225), 'poster': (240, 360)}
GAP = 22


def rows_with_ids():
    count = {}
    out = []
    for section, title, path, art, addon in ROWS:
        count[section] = count.get(section, 0) + 1
        out.append({'id': SECTION_BASE[section] + count[section], 'section': section,
                    'title': title, 'path': path, 'art': art, 'addon': addon})
    return out


def x(s):
    return escape(s, {'"': '&quot;'})


# --- változók és kifejezések ------------------------------------------------------------
def variables(rows):
    sel = lambda r: 'String.IsEqual(Window(home).Property(TSRow),%d)' % r['id']
    li = lambda r, info: 'Container(%d).ListItem.%s' % (r['id'], info)
    out = []

    def var(name, values):
        out.append('\t<variable name="%s">' % name)
        for cond, val in values:
            if cond:
                out.append('\t\t<value condition="%s">%s</value>' % (x(cond), x(val)))
            else:
                out.append('\t\t<value>%s</value>' % x(val))
        out.append('\t</variable>')

    # hero háttér: a sor típusától függő képsorrend
    vals = []
    for r in rows:
        order = {'landscape': ['Art(fanart)', 'Art(landscape)', 'Art(thumb)'],
                 'thumb': ['Art(thumb)', 'Art(landscape)'],
                 'poster': []}[r['art']]
        for a in order:
            vals.append((sel(r) + ' + !String.IsEmpty(%s)' % li(r, a), '$INFO[%s]' % li(r, a)))
    var('TSHeroArt', vals)
    # álló borító (anime-sorok): a hero jobb oldalán
    var('TSHeroPoster', [(sel(r), '$INFO[%s]' % li(r, 'Art(poster)')) for r in rows
                         if r['art'] == 'poster'])
    var('TSHeroLogo', [(sel(r) + ' + !String.IsEmpty(%s)' % li(r, 'Art(clearlogo)'),
                        '$INFO[%s]' % li(r, 'Art(clearlogo)')) for r in rows])
    # cím: sorozat-résznél a sorozat címe, egyébként a cím / felirat
    vals = []
    for r in rows:
        vals.append((sel(r) + ' + !String.IsEmpty(%s)' % li(r, 'TVShowTitle'),
                     '$INFO[%s]' % li(r, 'TVShowTitle')))
        vals.append((sel(r) + ' + !String.IsEmpty(%s)' % li(r, 'Title'), '$INFO[%s]' % li(r, 'Title')))
        vals.append((sel(r), '$INFO[%s]' % li(r, 'Label')))
    var('TSHeroTitle', vals)
    # jellemzők: évad/rész, év, műfaj, hossz, értékelés
    vals = []
    for r in rows:
        i = r['id']
        se = '$INFO[Container(%d).ListItem.Season,S, ]$INFO[Container(%d).ListItem.Episode,E,  ]' % (i, i)
        rest = ('$INFO[Container(%d).ListItem.Genre,,   ]' % i +
                '$INFO[Container(%d).ListItem.Duration(mins),, perc   ]' % i +
                '$INFO[Container(%d).ListItem.Rating,★ ,]' % i)
        # dátum nélküli elemeknél a Kodi 1970-et adhat évnek: azt kihagyjuk
        vals.append((sel(r) + ' + String.IsEqual(Container(%d).ListItem.Year,1970)' % i, se + rest))
        vals.append((sel(r), se + '$INFO[Container(%d).ListItem.Year,,   ]' % i + rest))
    var('TSHeroMeta', vals)
    var('TSHeroPlot', [(sel(r), '$INFO[%s]' % li(r, 'Plot')) for r in rows])
    # üres hero: a szekció neve
    var('TSSectionTitle', [('String.IsEqual(Window(home).Property(TSSection),%s)' % k, t)
                           for k, _, _, t in SECTIONS])
    # kártyaképek (az elemrétegben a ListItem az adott elem)
    var('TSCardLandscape', [
        ('!String.IsEmpty(ListItem.Art(landscape))', '$INFO[ListItem.Art(landscape)]'),
        ('!String.IsEmpty(ListItem.Art(fanart))', '$INFO[ListItem.Art(fanart)]'),
        ('!String.IsEmpty(ListItem.Art(thumb))', '$INFO[ListItem.Art(thumb)]'),
        (None, '$INFO[ListItem.Icon]')])
    var('TSCardThumb', [
        ('!String.IsEmpty(ListItem.Art(thumb))', '$INFO[ListItem.Art(thumb)]'),
        ('!String.IsEmpty(ListItem.Art(landscape))', '$INFO[ListItem.Art(landscape)]'),
        (None, '$INFO[ListItem.Icon]')])
    var('TSCardPoster', [
        ('!String.IsEmpty(ListItem.Art(poster))', '$INFO[ListItem.Art(poster)]'),
        ('!String.IsEmpty(ListItem.Art(tvshow.poster))', '$INFO[ListItem.Art(tvshow.poster)]'),
        ('!String.IsEmpty(ListItem.Art(thumb))', '$INFO[ListItem.Art(thumb)]'),
        (None, '$INFO[ListItem.Icon]')])
    var('TSCardTitle', [
        ('!String.IsEmpty(ListItem.TVShowTitle)', '$INFO[ListItem.TVShowTitle]$INFO[ListItem.Season,  S,]$INFO[ListItem.Episode,E,]'),
        (None, '$INFO[ListItem.Label]')])

    # kifejezések
    out.append('\t<expression name="TSHasLogo">%s</expression>' % x(' | '.join(
        '[%s + !String.IsEmpty(%s)]' % (sel(r), li(r, 'Art(clearlogo)')) for r in rows)))
    out.append('\t<expression name="TSPosterRow">%s</expression>' % x(' | '.join(
        sel(r) for r in rows if r['art'] == 'poster')))
    out.append('\t<expression name="TSRowHasItems">%s</expression>' % x(' | '.join(
        '[%s + Integer.IsGreater(Container(%d).NumItems,0)]' % (sel(r), r['id']) for r in rows)))
    out.append('\t<expression name="TSRailOpen">ControlGroup(9000).HasFocus</expression>')
    return out


# --- elemrétegek (kártyák) ---------------------------------------------------------------
def card_layout(kind, focused):
    w, h = CARD[kind]
    var = {'landscape': 'TSCardLandscape', 'thumb': 'TSCardThumb', 'poster': 'TSCardPoster'}[kind]
    mask = 'tomszo/mask_poster.png' if kind == 'poster' else 'tomszo/mask_card.png'
    L = []
    L.append('<control type="group">')
    L.append('<top>%d</top>' % 18)
    if focused:
        L.append('<animation type="Focus" reversible="false"><effect type="zoom" start="100" end="108" '
                 'time="180" tween="cubic" easing="out" center="%d,%d"/></animation>' % (w // 2, h // 2))
        L.append('<animation type="Conditional" condition="!Control.HasFocus($PARAM[list_id])" reversible="true">'
                 '<effect type="zoom" start="108" end="100" time="1" center="%d,%d"/></animation>' % (w // 2, h // 2))
    # alap (ha nincs kép)
    L.append('<control type="image"><width>%d</width><height>%d</height>'
             '<texture colordiffuse="FF1E1E24" diffuse="%s">tomszo/white.png</texture></control>' % (w, h, mask))
    L.append('<control type="label"><left>16</left><top>0</top><width>%d</width><height>%d</height>'
             '<font>ts_card</font><align>center</align><aligny>center</aligny><wrapmultiline>true</wrapmultiline>'
             '<label>$VAR[TSCardTitle]</label><textcolor>FFE6E6EA</textcolor></control>' % (w - 32, h))
    L.append('<control type="image"><width>%d</width><height>%d</height><aspectratio>scale</aspectratio>'
             '<fadetime>200</fadetime><texture background="true" diffuse="%s">$VAR[%s]</texture></control>'
             % (w, h, mask, var))
    if kind != 'poster':
        # cím a kép alján, sötét átmenettel (a háttérképeken nincs felirat)
        L.append('<control type="image"><top>%d</top><width>%d</width><height>110</height>'
                 '<texture>tomszo/grad_card.png</texture>'
                 '<visible>$PARAM[overlay]</visible></control>' % (h - 110, w))
        L.append('<control type="label"><left>18</left><top>%d</top><width>%d</width><height>40</height>'
                 '<font>ts_card</font><label>$VAR[TSCardTitle]</label><textcolor>FFFFFFFF</textcolor>'
                 '<shadowcolor>A0000000</shadowcolor><scroll>%s</scroll>'
                 '<visible>$PARAM[overlay]</visible></control>'
                 % (h - 50, w - 36, 'true' if focused else 'false'))
    # haladásjelző
    L.append('<control type="progress"><left>14</left><top>%d</top><width>%d</width><height>8</height>'
             '<texturebg colordiffuse="60FFFFFF" border="4">tomszo/bar.png</texturebg>'
             '<lefttexture/><midtexture colordiffuse="FFE5262C" border="4">tomszo/bar.png</midtexture><righttexture/>'
             '<info>ListItem.PercentPlayed</info>'
             '<visible>Integer.IsGreater(ListItem.PercentPlayed,0)</visible></control>' % (h - 18, w - 28))
    if focused:
        L.append('<control type="image"><left>-6</left><top>-6</top><width>%d</width><height>%d</height>'
                 '<texture border="22">tomszo/frame.png</texture>'
                 '<visible>Control.HasFocus($PARAM[list_id])</visible></control>' % (w + 12, h + 12))
    L.append('</control>')
    return ''.join(L)


def row_include(kind):
    """Egy widget-sor: cím + vízszintes lista KÖZVETLENÜL a grouplistben (csoportba
    csomagolva a Kodi nem navigálna le/fel a sorok között)."""
    w, h = CARD[kind]
    item_w = w + GAP
    list_h = h + 60
    shown = ('$PARAM[visible] + [Integer.IsGreater(Container($PARAM[list_id]).NumItems,0) | '
             'Container($PARAM[list_id]).IsUpdating]')
    L = []
    L.append('\t<include name="TSRow_%s">' % kind)
    L.append('\t\t<param name="overlay">true</param>')
    L.append('\t\t<definition>')
    L.append('\t\t\t<control type="label" id="$PARAM[list_id]1"><left>%d</left><width>1500</width><height>58</height>'
             '<font>ts_row</font><textcolor>FFE6E6EA</textcolor><aligny>bottom</aligny>'
             '<label>$PARAM[title]</label><visible>%s</visible></control>' % (X0, x(shown)))
    L.append('\t\t\t<control type="fixedlist" id="$PARAM[list_id]">')
    L.append('\t\t\t\t<left>%d</left><width>%d</width><height>%d</height>' % (X0, 1920 - X0, list_h))
    L.append('\t\t\t\t<visible>%s</visible>' % x(shown))
    L.append('\t\t\t\t<orientation>horizontal</orientation>')
    L.append('\t\t\t\t<focusposition>0</focusposition><movement>0</movement>')
    L.append('\t\t\t\t<scrolltime tween="cubic" easing="out">320</scrolltime>')
    L.append('\t\t\t\t<onleft>9000</onleft>')
    L.append('\t\t\t\t<onfocus>SetProperty(TSRow,$PARAM[list_id],home)</onfocus>')
    L.append('\t\t\t\t<onback>9000</onback>')
    L.append('\t\t\t\t<preloaditems>2</preloaditems>')
    L.append('\t\t\t\t<itemlayout width="%d" height="%d">%s</itemlayout>' % (item_w, list_h, card_layout(kind, False)))
    L.append('\t\t\t\t<focusedlayout width="%d" height="%d">%s</focusedlayout>' % (item_w, list_h, card_layout(kind, True)))
    L.append('\t\t\t\t<content target="videos" limit="30" browse="auto">$PARAM[path]</content>')
    L.append('\t\t\t</control>')
    L.append('\t\t</definition>')
    L.append('\t</include>')
    return L


# --- hero, sorok, menüsáv ------------------------------------------------------------------
def hero():
    return '''	<include name="TSHero">
		<control type="group" id="3000">
			<control type="image">
				<left>420</left><top>0</top><width>1500</width><height>844</height>
				<aspectratio>scale</aspectratio>
				<fadetime>500</fadetime>
				<texture background="true">$VAR[TSHeroArt]</texture>
				<visible>!$EXP[TSPosterRow]</visible>
			</control>
			<control type="image">
				<left>420</left><top>0</top><width>900</width><height>844</height>
				<texture>tomszo/grad_left.png</texture>
			</control>
			<control type="image">
				<left>420</left><top>330</top><width>1500</width><height>520</height>
				<texture>tomszo/grad_bottom.png</texture>
			</control>
			<control type="image">
				<left>0</left><top>0</top><width>1920</width><height>260</height>
				<texture>tomszo/grad_top.png</texture>
			</control>
			<control type="image">
				<right>140</right><top>110</top><width>290</width><height>435</height>
				<aspectratio>scale</aspectratio>
				<fadetime>300</fadetime>
				<texture background="true" diffuse="tomszo/mask_poster.png">$VAR[TSHeroPoster]</texture>
				<visible>$EXP[TSPosterRow] + $EXP[TSRowHasItems]</visible>
			</control>
			<control type="grouplist">
				<left>180</left><top>96</top><width>1050</width><height>470</height>
				<orientation>vertical</orientation>
				<itemgap>14</itemgap>
				<visible>$EXP[TSRowHasItems]</visible>
				<control type="image">
					<width>640</width><height>190</height>
					<aspectratio align="left" aligny="bottom">keep</aspectratio>
					<fadetime>300</fadetime>
					<texture background="true">$VAR[TSHeroLogo]</texture>
					<visible>$EXP[TSHasLogo]</visible>
				</control>
				<control type="textbox">
					<width>1050</width><height min="0" max="200">auto</height>
					<font>ts_hero</font>
					<textcolor>FFFFFFFF</textcolor>
					<shadowcolor>80000000</shadowcolor>
					<label>$VAR[TSHeroTitle]</label>
					<visible>!$EXP[TSHasLogo]</visible>
				</control>
				<control type="label">
					<width>1050</width><height>40</height>
					<font>ts_meta</font>
					<textcolor>FFB4B4BE</textcolor>
					<label>$VAR[TSHeroMeta]</label>
				</control>
				<control type="textbox">
					<width>960</width><height min="0" max="132">auto</height>
					<font>ts_text</font>
					<textcolor>FFDCDCE2</textcolor>
					<label>$VAR[TSHeroPlot]</label>
				</control>
			</control>
			<control type="group">
				<visible>!$EXP[TSRowHasItems]</visible>
				<control type="label">
					<left>180</left><top>200</top><width>1400</width><height>110</height>
					<font>ts_hero</font><textcolor>FFFFFFFF</textcolor>
					<label>$VAR[TSSectionTitle]</label>
				</control>
				<control type="label">
					<left>180</left><top>310</top><width>1400</width><height>50</height>
					<font>ts_meta</font><textcolor>FFB4B4BE</textcolor>
					<label>Válassz a lenti sorokból – vagy balra a menü.</label>
				</control>
			</control>
		</control>
		<control type="label">
			<right>70</right><top>40</top><width>300</width><height>50</height>
			<align>right</align>
			<font>ts_meta</font><textcolor>FFDCDCE2</textcolor>
			<label>$INFO[System.Time]</label>
		</control>
	</include>'''


def rows_include(rows):
    L = ['\t<include name="TSRows">',
         '\t\t<control type="grouplist" id="4000">',
         '\t\t\t<left>0</left><top>%d</top><width>1920</width><bottom>0</bottom>' % ROWS_TOP,
         '\t\t\t<orientation>vertical</orientation>',
         '\t\t\t<itemgap>0</itemgap>',
         '\t\t\t<scrolltime tween="cubic" easing="out">380</scrolltime>',
         '\t\t\t<usecontrolcoords>true</usecontrolcoords>',
         '\t\t\t<onleft>9000</onleft>']
    for r in rows:
        vis = 'String.IsEqual(Window(home).Property(TSSection),%s)' % r['section']
        if r['addon']:
            vis += ' + System.HasAddon(%s)' % r['addon']
        L.append('\t\t\t<include content="TSRow_%s">' % r['art'])
        L.append('\t\t\t\t<param name="list_id" value="%d"/>' % r['id'])
        L.append('\t\t\t\t<param name="title" value="%s"/>' % x(r['title']))
        L.append('\t\t\t\t<param name="path" value="%s"/>' % x(r['path']))
        L.append('\t\t\t\t<param name="visible" value="%s"/>' % x(vis))
        if r['art'] == 'thumb' and 'action=collection' in r['path']:
            L.append('\t\t\t\t<param name="overlay" value="false"/>')   # a Network4-borítókon van felirat
        L.append('\t\t\t</include>')
    L += ['\t\t</control>']
    firsts = {}
    for r in rows:
        firsts.setdefault(r['section'], r['id'])
    first_focused = ' | '.join('Control.HasFocus(%d)' % i for i in firsts.values())
    L += ['\t\t<control type="image">',
          '\t\t\t<left>0</left><top>%d</top><width>1920</width><height>90</height>' % (ROWS_TOP - 10),
          '\t\t\t<texture flipy="true">tomszo/grad_card.png</texture>',
          '\t\t\t<visible>!$EXP[TSRailOpen] + ![%s]</visible>' % x(first_focused),
          '\t\t\t<animation effect="fade" time="200">VisibleChange</animation>',
          '\t\t</control>',
          # nyitott menünél egyetlen sötét réteg (a kártyák elemenkénti halványítása
          # átlátszóvá tenné a képeket, és kilátszana alóluk a tartalék felirat)
          '\t\t<control type="image">',
          '\t\t\t<left>0</left><top>0</top><width>1920</width><height>1080</height>',
          '\t\t\t<texture colordiffuse="A0000000">tomszo/white.png</texture>',
          '\t\t\t<visible>$EXP[TSRailOpen]</visible>',
          '\t\t\t<animation effect="fade" time="250">VisibleChange</animation>',
          '\t\t</control>',
          '\t</include>']
    return L


def rail(rows):
    first = {}
    for r in rows:
        first.setdefault(r['section'], r['id'])
    L = ['\t<include name="TSRail">',
         '\t\t<control type="image">',
         '\t\t\t<left>0</left><top>0</top><width>640</width><height>1080</height>',
         '\t\t\t<texture>tomszo/grad_rail.png</texture>',
         '\t\t\t<visible>$EXP[TSRailOpen]</visible>',
         '\t\t\t<animation effect="fade" time="200">VisibleChange</animation>',
         '\t\t</control>',
         '\t\t<control type="image">',
         '\t\t\t<left>32</left><top>40</top><width>56</width><height>56</height>',
         '\t\t\t<texture>special://skin/resources/icon.png</texture>',
         '\t\t</control>',
         '\t\t<control type="group" id="9000">',
         '\t\t\t<defaultcontrol always="false">9002</defaultcontrol>']
    for n, (bid, label, icon, action) in enumerate(RAIL):
        y = RAIL_TOP + n * RAIL_STEP
        up = RAIL[n - 1][0] if n else RAIL[-1][0]
        down = RAIL[n + 1][0] if n + 1 < len(RAIL) else RAIL[0][0]
        if action.startswith('section:'):
            sec = action.split(':', 1)[1]
            clicks = ['SetProperty(TSSection,%s,home)' % sec,
                      'SetProperty(TSRow,%d,home)' % first.get(sec, 0),
                      'SetFocus(4000)']
            active = 'String.IsEqual(Window(home).Property(TSSection),%s)' % sec
        else:
            clicks = [action]
            active = 'false'
        L.append('\t\t\t<control type="button" id="%d">' % bid)
        L.append('\t\t\t\t<left>22</left><top>%d</top><width>340</width><height>70</height>' % y)
        L.append('\t\t\t\t<texturefocus border="22" colordiffuse="FFFFFFFF">tomszo/pill.png</texturefocus>')
        L.append('\t\t\t\t<texturenofocus/>')
        L.append('\t\t\t\t<label/>')
        L.append('\t\t\t\t<onup>%d</onup><ondown>%d</ondown><onright>4000</onright><onleft>noop</onleft>' % (up, down))
        for c in clicks:
            L.append('\t\t\t\t<onclick>%s</onclick>' % c)
        L.append('\t\t\t</control>')
        # aktív szekció jelölése
        L.append('\t\t\t<control type="image"><left>22</left><top>%d</top><width>6</width><height>40</height>'
                 '<texture colordiffuse="FFE5262C" border="3">tomszo/bar.png</texture><visible>%s</visible></control>'
                 % (y + 15, active))
        L.append('\t\t\t<control type="image"><left>44</left><top>%d</top><width>40</width><height>40</height>'
                 '<texture colordiffuse="$VAR[TSRailIcon%d]">tomszo/icon_%s.png</texture></control>' % (y + 15, bid, icon))
        L.append('\t\t\t<control type="label"><left>104</left><top>%d</top><width>250</width><height>70</height>'
                 '<font>ts_menu</font><aligny>center</aligny><label>%s</label>'
                 '<textcolor>$VAR[TSRailText%d]</textcolor><visible>$EXP[TSRailOpen]</visible>'
                 '<animation effect="fade" time="150">VisibleChange</animation></control>' % (y, x(label), bid))
    L += ['\t\t</control>', '\t</include>']
    # ikon- és szövegszínek: fókuszban fekete (fehér gomb), aktív szekció fehér, egyébként szürke
    for bid, label, icon, action in RAIL:
        sec = action.split(':', 1)[1] if action.startswith('section:') else None
        act = 'String.IsEqual(Window(home).Property(TSSection),%s)' % sec if sec else 'false'
        for kind in ('Icon', 'Text'):
            L.append('\t<variable name="TSRail%s%d">' % (kind, bid))
            L.append('\t\t<value condition="Control.HasFocus(%d)">FF0A0A0C</value>' % bid)
            L.append('\t\t<value condition="%s">FFFFFFFF</value>' % act)
            L.append('\t\t<value>FF9A9AA6</value>')
            L.append('\t</variable>')
    return L


def home_xml():
    return '''<?xml version="1.0" encoding="UTF-8"?>
<!-- GENERÁLT FÁJL: _tools/build_home.py - kézzel ne szerkeszd -->
<window>
	<defaultcontrol always="false">4000</defaultcontrol>
	<backgroundcolor>FF000000</backgroundcolor>
	<onload condition="String.IsEmpty(Window(home).Property(TSSection))">SetProperty(TSSection,home,home)</onload>
	<onload condition="String.IsEmpty(Window(home).Property(TSRow))">SetProperty(TSRow,5101,home)</onload>
	<controls>
		<include>TSHero</include>
		<include>TSRows</include>
		<include>TSRail</include>
	</controls>
</window>
'''


# Tesztmód (--test): a plugin-sorok a helyi videókönyvtárra mutatnak, hogy a skin
# Python-addonok nélkül is kipróbálható legyen (pl. virtuális képernyőn).
TEST_PATHS = {'landscape': 'videodb://movies/titles/', 'thumb': 'videodb://recentlyaddedepisodes/',
              'poster': 'videodb://movies/titles/'}


def test_rows(rows):
    for r in rows:
        if r['path'].startswith('plugin://'):
            r['path'] = TEST_PATHS[r['art']]
            if 'tmdb_type=tv' in r['title'] or 'Sorozat' in r['title'] or r['section'] == 'tvshows':
                r['path'] = 'videodb://tvshows/titles/'
            r['addon'] = None
    return rows


def main(argv):
    out = ROOT
    if '--out' in argv:
        out = argv[argv.index('--out') + 1]
    rows = rows_with_ids()
    if '--test' in argv:
        rows = test_rows(rows)
    inc = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<!-- GENERÁLT FÁJL: _tools/build_home.py - kézzel ne szerkeszd -->',
           '<includes>']
    inc += variables(rows)
    for kind in ('landscape', 'thumb', 'poster'):
        inc += row_include(kind)
    inc.append(hero())
    inc += rows_include(rows)
    inc += rail(rows)
    inc.append('</includes>')
    with open(os.path.join(out, 'xml', 'Includes_TomSzo.xml'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(inc) + '\n')
    with open(os.path.join(out, 'xml', 'Home.xml'), 'w', encoding='utf-8') as f:
        f.write(home_xml())
    # az include-fájl regisztrálása
    path = os.path.join(out, 'xml', 'Includes.xml')
    s = open(path, encoding='utf-8').read()
    if 'Includes_TomSzo.xml' not in s:
        s = s.replace('<includes>', '<includes>\n\t<include file="Includes_TomSzo.xml" />', 1)
        open(path, 'w', encoding='utf-8').write(s)
    print('%d sor, %d szekció' % (len(rows), len(SECTIONS)))


if __name__ == '__main__':
    import sys
    main(sys.argv[1:])
