# TomSzo Touch – app-szerű kezdőképernyő (Érintés mód) generátor
# Futtatás a skin mappájából: python3 _tools/homeapp.py  ->  xml/Includes_HomeApp.xml
P='Window(home).Property(app_tab)'; C='Window(home).Property(app_chip)'
def tab(t):
    if t=='home': return f'[String.IsEmpty({P}) | String.IsEqual({P},home)]'
    return f'String.IsEqual({P},{t})'
def chip(n):
    if n==1: return f'[String.IsEmpty({C}) | String.IsEqual({C},1)]'
    return f'String.IsEqual({C},{n})'
# fülek: id, cím string, ikon, chipek (string id, panel, útvonal)
TABS=[('home',31973,'tomszo/tab-home.png',[
        (31960,5000,'special://skin/playlists/inprogress_movies.xsp'),
        (31961,5000,'videodb://inprogresstvshows/'),
        (31962,5000,'videodb://recentlyaddedmovies/'),
        (31963,5000,'videodb://recentlyaddedepisodes/')]),
      ('movies',31974,'tomszo/tab-movies.png',[
        (31964,5000,'videodb://movies/titles/'),
        (31965,5000,'special://skin/playlists/unwatched_movies.xsp'),
        (31962,5000,'videodb://recentlyaddedmovies/'),
        (31966,5000,'videodb://movies/sets/')]),
      ('tvshows',31975,'tomszo/tab-tvshows.png',[
        (31964,5000,'videodb://tvshows/titles/'),
        (31967,5000,'videodb://inprogresstvshows/'),
        (31963,5000,'videodb://recentlyaddedepisodes/'),
        (31965,5000,'special://skin/playlists/unwatched_tvshows.xsp')]),
      ('addons',31976,'tomszo/tab-addons.png',[
        (31968,5000,'addons://sources/video/'),
        (31969,5001,'addons://sources/executable/'),
        (31970,5002,'addons://sources/audio/')]),
      ('favourites',31977,'tomszo/tab-favourites.png',[
        (31964,5000,'favourites://')])]
PANELS=[(5000,'videos'),(5001,'programs'),(5002,'music')]
SQUARE=f'[{tab("addons")} | {tab("favourites")}]'
o=[]; w=o.append
w('<?xml version="1.0" encoding="UTF-8"?>')
w('<!-- TomSzo Touch: app-szerű kezdőképernyő Érintés módhoz.')
w('     Generálva (homeapp.py). Fent cím + szűrőgombok, középen függőlegesen görgethető')
w('     kártyarács (egy görgetési irány = akadásmentes húzás), alul fix menüsáv. -->')
w('<includes>')
# --- változók
w('\t<variable name="AppTitleVar">')
for t,s,_,_ in TABS[1:]: w(f'\t\t<value condition="{tab(t)}">$LOCALIZE[{s}]</value>')
w(f'\t\t<value>$LOCALIZE[{TABS[0][1]}]</value>\n\t</variable>')
for pid,_ in PANELS:
    w(f'\t<variable name="AppFeedPath{pid}">')
    for t,_,_,chips in TABS:
        for n,(s,p,path) in enumerate(chips,1):
            if p==pid: w(f'\t\t<value condition="{tab(t)} + {chip(n)}">{path}</value>')
    w('\t</variable>')
w('''	<variable name="AppCardArtVar">
		<value condition="!String.IsEmpty(ListItem.Art(poster))">$INFO[ListItem.Art(poster)]</value>
		<value condition="!String.IsEmpty(ListItem.Art(tvshow.poster))">$INFO[ListItem.Art(tvshow.poster)]</value>
		<value condition="!String.IsEmpty(ListItem.Art(thumb))">$INFO[ListItem.Art(thumb)]</value>
		<value>$INFO[ListItem.Icon]</value>
	</variable>
	<variable name="AppCardLabelVar">
		<value condition="!String.IsEmpty(ListItem.TVShowTitle) + String.IsEqual(ListItem.DBType,episode)">$INFO[ListItem.TVShowTitle]</value>
		<value>$INFO[ListItem.Label]</value>
	</variable>
	<variable name="AppCardLabel2Var">
		<value condition="String.IsEqual(ListItem.DBType,episode)">$INFO[ListItem.Season,S,]$INFO[ListItem.Episode,E,]$INFO[ListItem.Title, · ,]</value>
		<value condition="String.IsEqual(ListItem.DBType,tvshow)">$INFO[ListItem.Year]$INFO[ListItem.Property(UnWatchedEpisodes), · ,]</value>
		<value>$INFO[ListItem.Year]</value>
	</variable>''')
# --- kártya elrendezések
def poster(pid,focus):
    r=[f'\t\t\t<control type="image"><left>20</left><top>10</top><width>240</width><height>360</height><texture colordiffuse="FF1C222B">tomszo/mask-poster.png</texture></control>',
       f'\t\t\t<control type="image"><left>20</left><top>10</top><width>240</width><height>360</height><aspectratio>scale</aspectratio><texture diffuse="tomszo/mask-poster.png" fallback="DefaultVideo.png" background="true">$VAR[AppCardArtVar]</texture></control>',
       f'\t\t\t<control type="progress"><left>36</left><top>350</top><width>208</width><height>6</height><texturebg colordiffuse="60000000">colors/white.png</texturebg><midtexture colordiffuse="button_focus">colors/white.png</midtexture><info>ListItem.PercentPlayed</info><visible>Integer.IsGreater(ListItem.PercentPlayed,0)</visible></control>',
       f'\t\t\t<control type="label"><left>20</left><top>380</top><width>240</width><height>36</height><font>font12</font><label>$VAR[AppCardLabelVar]</label>{"<scroll>true</scroll>" if focus else ""}</control>',
       f'\t\t\t<control type="label"><left>20</left><top>414</top><width>240</width><height>32</height><font>font10</font><textcolor>grey</textcolor><label>$VAR[AppCardLabel2Var]</label></control>']
    if focus: r.insert(2,f'\t\t\t<control type="image"><left>12</left><top>2</top><width>256</width><height>376</height><texture border="22" colordiffuse="button_focus">tomszo/ring-small.png</texture><visible>Control.HasFocus({pid})</visible></control>')
    return r
def square(pid,focus):
    r=[f'\t\t\t<control type="image"><left>20</left><top>10</top><width>240</width><height>240</height><texture colordiffuse="FF1C222B">tomszo/mask-square.png</texture></control>',
       f'\t\t\t<control type="image"><left>55</left><top>45</top><width>170</width><height>170</height><aspectratio>keep</aspectratio><texture fallback="DefaultAddon.png" background="true">$INFO[ListItem.Icon]</texture></control>',
       f'\t\t\t<control type="label"><left>20</left><top>262</top><width>240</width><height>36</height><align>center</align><font>font12</font><label>$INFO[ListItem.Label]</label>{"<scroll>true</scroll>" if focus else ""}</control>']
    if focus: r.insert(1,f'\t\t\t<control type="image"><left>12</left><top>2</top><width>256</width><height>256</height><texture border="22" colordiffuse="button_focus">tomszo/ring-small.png</texture><visible>Control.HasFocus({pid})</visible></control>')
    return r
# --- fő include
w('\t<include name="HomeApp">')
w('\t\t<include>DefaultBackground</include>')
# fejléc
w('''		<control type="label">
			<left>60</left>
			<top>34</top>
			<width>1000</width>
			<height>70</height>
			<font>font52_title</font>
			<label>$VAR[AppTitleVar]</label>
		</control>
		<control type="grouplist" id="200">
			<right>30</right>
			<top>14</top>
			<width>900</width>
			<height>110</height>
			<orientation>horizontal</orientation>
			<align>right</align>
			<itemgap>0</itemgap>
			<usecontrolcoords>true</usecontrolcoords>
			<onleft>200</onleft>
			<onright>200</onright>
			<ondown>300</ondown>
			<control type="label">
				<width>auto</width>
				<height>110</height>
				<aligny>center</aligny>
				<font>font37</font>
				<textcolor>grey</textcolor>
				<label>$INFO[System.Time]   </label>
			</control>
			<include content="IconButton">
				<param name="control_id" value="201" />
				<param name="height" value="110" />
				<param name="onclick" value="ActivateWindow(fullscreenvideo)" />
				<param name="icon" value="osd/fullscreen/buttons/play.png" />
				<param name="label" value="$LOCALIZE[31979]" />
				<param name="visible" value="Player.HasMedia" />
			</include>
			<include content="IconButton">
				<param name="control_id" value="202" />
				<param name="height" value="110" />
				<param name="onclick" value="ActivateWindow(1107)" />
				<param name="icon" value="icons/search.png" />
				<param name="label" value="$LOCALIZE[137]" />
			</include>
			<include content="IconButton">
				<param name="control_id" value="203" />
				<param name="height" value="110" />
				<param name="onclick" value="ActivateWindow(shutdownmenu)" />
				<param name="icon" value="icons/power.png" />
				<param name="label" value="$LOCALIZE[33060]" />
			</include>
		</control>''')
# chipek
w('''		<control type="grouplist" id="300">
			<left>60</left>
			<right>60</right>
			<top>134</top>
			<height>64</height>
			<orientation>horizontal</orientation>
			<itemgap>16</itemgap>
			<usecontrolcoords>true</usecontrolcoords>
			<onup>200</onup>
			<ondown>5100</ondown>''')
cid=310
for t,_,_,chips in TABS:
    if len(chips)<2: continue
    for n,(s,p,path) in enumerate(chips,1):
        w(f'''			<control type="togglebutton" id="{cid}">
				<width>auto</width>
				<height>64</height>
				<textoffsetx>32</textoffsetx>
				<align>center</align>
				<aligny>center</aligny>
				<font>font27</font>
				<label>$LOCALIZE[{s}]</label>
				<altlabel>$LOCALIZE[{s}]</altlabel>
				<texturenofocus border="32" colordiffuse="FF1C222B">tomszo/pill.png</texturenofocus>
				<texturefocus border="32" colordiffuse="FF2A3440">tomszo/pill.png</texturefocus>
				<alttexturenofocus border="32" colordiffuse="button_focus">tomszo/pill.png</alttexturenofocus>
				<alttexturefocus border="32" colordiffuse="button_focus">tomszo/pill.png</alttexturefocus>
				<usealttexture>{chip(n)}</usealttexture>
				<onclick>SetProperty(app_chip,{n},home)</onclick>
				<visible>{tab(t)}</visible>
			</control>''')
        cid+=1
w('\t\t</control>')
# kártyarácsok
w('''		<control type="group" id="5100">
			<centerleft>50%</centerleft>
			<width>1680</width>
			<top>{top}</top>
			<bottom>150</bottom>'''.replace('{top}','214'))
for pid,target in PANELS:
    vis={5000:f'![{tab("addons")} + [{chip(2)} | {chip(3)}]]',5001:f'{tab("addons")} + {chip(2)}',5002:f'{tab("addons")} + {chip(3)}'}[pid]
    w(f'''			<control type="panel" id="{pid}">
				<left>0</left>
				<top>0</top>
				<right>0</right>
				<bottom>0</bottom>
				<orientation>vertical</orientation>
				<onup>300</onup>
				<ondown>9000</ondown>
				<onleft>{pid}</onleft>
				<onright>{pid}</onright>
				<onback>9000</onback>
				<preloaditems>1</preloaditems>
				<scrolltime tween="quadratic" easing="out">300</scrolltime>
				<visible>{vis}</visible>''')
    for kind,cond,wd,ht,fn in (('item',f'!{SQUARE}',280,460,poster),('focused',f'!{SQUARE}',280,460,poster),('item',SQUARE,280,320,square),('focused',SQUARE,280,320,square)):
        tag='itemlayout' if kind=='item' else 'focusedlayout'
        w(f'\t\t\t\t<{tag} width="{wd}" height="{ht}" condition="{cond}">')
        for line in fn(pid,kind=='focused'): w('\t\t'+line)
        w(f'\t\t\t\t</{tag}>')
    w(f'\t\t\t\t<content target="{target}">$VAR[AppFeedPath{pid}]</content>')
    w('\t\t\t</control>')
empty=' | '.join(f'[Control.IsVisible({p}) + Integer.IsEqual(Container({p}).NumItems,0) + !Container({p}).IsUpdating]' for p,_ in PANELS)
w(f'''			<control type="group">
				<visible>{empty}</visible>
				<control type="label">
					<left>0</left>
					<right>0</right>
					<top>220</top>
					<height>60</height>
					<align>center</align>
					<font>font37</font>
					<label>$LOCALIZE[31971]</label>
				</control>
				<control type="label">
					<left>0</left>
					<right>0</right>
					<top>290</top>
					<height>40</height>
					<align>center</align>
					<font>font27</font>
					<textcolor>grey</textcolor>
					<label>$LOCALIZE[31972]</label>
				</control>
			</control>
		</control>''')
# alsó menüsáv
active=f'[String.IsEqual(ListItem.Property(id),{P}) | [String.IsEqual(ListItem.Property(id),home) + String.IsEmpty({P})]]'
def tablayout(focus):
    def img(col,vis): return f'''				<control type="image">
					<centerleft>50%</centerleft>
					<top>22</top>
					<width>52</width>
					<height>52</height>
					<aspectratio>keep</aspectratio>
					<texture colordiffuse="{col}">$INFO[ListItem.Icon]</texture>
					<visible>{vis}</visible>
				</control>'''
    def lbl(col,vis): return f'''				<control type="label">
					<left>0</left>
					<right>0</right>
					<top>86</top>
					<height>36</height>
					<align>center</align>
					<font>font12</font>
					<textcolor>{col}</textcolor>
					<label>$INFO[ListItem.Label]</label>
					<visible>{vis}</visible>
				</control>'''
    pill=f'''				<control type="image">
					<centerleft>50%</centerleft>
					<top>16</top>
					<width>120</width>
					<height>64</height>
					<texture border="32" colordiffuse="550F9D76">tomszo/pill.png</texture>
					<visible>{active}</visible>
				</control>'''
    r=[pill,img('FFF0F0F0',active),img('FF8A939C','!'+active)]
    if focus:
        r+=[lbl('button_focus','Control.HasFocus(9000)'),lbl('FFF0F0F0',active+' + !Control.HasFocus(9000)'),lbl('FF8A939C','!'+active+' + !Control.HasFocus(9000)')]
    else:
        r+=[lbl('FFF0F0F0',active),lbl('FF8A939C','!'+active)]
    return r
w(f'''		<control type="image">
			<left>0</left>
			<right>0</right>
			<bottom>0</bottom>
			<height>140</height>
			<texture colordiffuse="FF0E1217">colors/white.png</texture>
		</control>
		<control type="image">
			<left>0</left>
			<right>0</right>
			<bottom>140</bottom>
			<height>2</height>
			<texture colordiffuse="FF1E252E">colors/white.png</texture>
		</control>
		<control type="list" id="9000">
			<centerleft>50%</centerleft>
			<width>1800</width>
			<bottom>0</bottom>
			<height>140</height>
			<orientation>horizontal</orientation>
			<onup>5100</onup>
			<ondown>noop</ondown>
			<onleft>9000</onleft>
			<onright>9000</onright>
			<scrolltime>0</scrolltime>
			<itemlayout width="300" height="140">''')
o.extend(tablayout(False))
w('\t\t\t</itemlayout>\n\t\t\t<focusedlayout width="300" height="140">')
o.extend(tablayout(True))
w('\t\t\t</focusedlayout>\n\t\t\t<content>')
for t,s,icon,_ in TABS:
    w(f'''				<item>
					<label>$LOCALIZE[{s}]</label>
					<icon>{icon}</icon>
					<property name="id">{t}</property>
					<onclick>ClearProperty(app_chip,home)</onclick>
					<onclick>SetProperty(app_tab,{t},home)</onclick>
				</item>''')
w('''				<item>
					<label>$LOCALIZE[31978]</label>
					<icon>tomszo/tab-settings.png</icon>
					<property name="id">settings</property>
					<onclick>ActivateWindow(settings)</onclick>
				</item>
			</content>
		</control>
	</include>
</includes>''')
open('xml/Includes_HomeApp.xml','w',encoding='utf-8').write('\n'.join(o)+'\n')
