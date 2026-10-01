# TomSzo Touch – mobilos nézetek generátora (Érintés mód)
# Futtatás a skin mappájából: python3 _tools/views.py
#   -> xml/View_56_MobileList.xml  (Mobil lista: sorok kis poszterrel, meta-sorral, leírással)
#   -> xml/View_57_Cards.xml       (Kártyák: függőlegesen görgethető poszterrács)

POSTER_CONTENT = ('Container.Content(movies) | Container.Content(tvshows) | Container.Content(sets) | '
                  'Container.Content(seasons) | Container.Content(musicvideos)')

VARS = '''	<variable name="MobileMetaVar">
		<value condition="String.IsEqual(ListItem.DBType,episode)">$INFO[ListItem.Season,S,]$INFO[ListItem.Episode,E,]$INFO[ListItem.Premiered, · ,]$INFO[ListItem.Duration(mins), · , $LOCALIZE[31982]]</value>
		<value condition="String.IsEqual(ListItem.DBType,tvshow)">$INFO[ListItem.Year]$INFO[ListItem.Genre, · ,]$INFO[ListItem.Property(TotalEpisodes), · , $LOCALIZE[31983]]</value>
		<value condition="!String.IsEmpty(ListItem.Duration)">$INFO[ListItem.Year]$INFO[ListItem.Genre, · ,]$INFO[ListItem.Duration(mins), · , $LOCALIZE[31982]]</value>
		<value condition="!String.IsEmpty(ListItem.Year) | !String.IsEmpty(ListItem.Genre)">$INFO[ListItem.Year]$INFO[ListItem.Genre, · ,]</value>
		<value>$INFO[ListItem.Label2]</value>
	</variable>
	<variable name="MobileTitleVar">
		<value condition="String.IsEqual(ListItem.DBType,episode) + !String.IsEmpty(ListItem.Title)">$INFO[ListItem.Title]</value>
		<value>$INFO[ListItem.Label]</value>
	</variable>
	<variable name="MobilePosterVar">
		<value condition="!String.IsEmpty(ListItem.Art(poster))">$INFO[ListItem.Art(poster)]</value>
		<value condition="!String.IsEmpty(ListItem.Art(tvshow.poster))">$INFO[ListItem.Art(tvshow.poster)]</value>
	</variable>'''


def row(vid, focus):
    """Mobil lista sor (170 px magas)."""
    hasposter = '!String.IsEmpty(ListItem.Art(poster)) | !String.IsEmpty(ListItem.Art(tvshow.poster))'
    out = []
    if focus:
        out.append(f'''				<control type="image">
					<left>8</left>
					<right>8</right>
					<top>6</top>
					<bottom>6</bottom>
					<texture border="30" colordiffuse="FF1C2A2A">tomszo/card.png</texture>
					<visible>Control.HasFocus({vid})</visible>
				</control>''')
    out.append(f'''				<control type="image">
					<left>24</left>
					<top>15</top>
					<width>93</width>
					<height>140</height>
					<texture colordiffuse="FF1C222B">tomszo/mask-poster.png</texture>
				</control>
				<control type="image">
					<left>24</left>
					<top>15</top>
					<width>93</width>
					<height>140</height>
					<aspectratio>scale</aspectratio>
					<texture diffuse="tomszo/mask-poster.png" background="true">$VAR[MobilePosterVar]</texture>
					<visible>{hasposter}</visible>
				</control>
				<control type="image">
					<left>34</left>
					<top>40</top>
					<width>73</width>
					<height>90</height>
					<aspectratio>keep</aspectratio>
					<texture fallback="DefaultFolder.png" background="true">$INFO[ListItem.Icon]</texture>
					<visible>![{hasposter}]</visible>
				</control>
				<control type="label">
					<left>145</left>
					<right>200</right>
					<top>20</top>
					<height>46</height>
					<aligny>center</aligny>
					<font>font32</font>
					<label>$VAR[MobileTitleVar]</label>{"""
					<scroll>true</scroll>""" if focus else ""}
				</control>
				<control type="label">
					<left>145</left>
					<right>200</right>
					<top>66</top>
					<height>34</height>
					<aligny>center</aligny>
					<font>font12</font>
					<textcolor>FFA8B0B8</textcolor>
					<label>$VAR[MobileMetaVar]</label>
				</control>
				<control type="label">
					<left>145</left>
					<right>200</right>
					<top>100</top>
					<height>32</height>
					<aligny>center</aligny>
					<font>font10</font>
					<textcolor>FF7D868F</textcolor>
					<label>$INFO[ListItem.Plot]</label>
				</control>
				<control type="progress">
					<left>145</left>
					<top>142</top>
					<width>320</width>
					<height>5</height>
					<texturebg colordiffuse="30FFFFFF">colors/white.png</texturebg>
					<midtexture colordiffuse="button_focus">colors/white.png</midtexture>
					<info>ListItem.PercentPlayed</info>
					<visible>Integer.IsGreater(ListItem.PercentPlayed,0)</visible>
				</control>
				<control type="image">
					<right>110</right>
					<top>27</top>
					<width>30</width>
					<height>30</height>
					<texture colordiffuse="FFE8B54A">tomszo/tab-favourites.png</texture>
					<visible>!String.IsEmpty(ListItem.Rating)</visible>
				</control>
				<control type="label">
					<right>24</right>
					<top>20</top>
					<width>80</width>
					<height>44</height>
					<aligny>center</aligny>
					<font>font27</font>
					<label>$INFO[ListItem.Rating]</label>
				</control>
				<control type="image">
					<right>28</right>
					<bottom>28</bottom>
					<width>32</width>
					<height>32</height>
					<aspectratio>keep</aspectratio>
					<texture colordiffuse="FF8A939C">$VAR[ListWatchedIconVar]</texture>
				</control>''')
    if not focus:
        out.append('''				<control type="image">
					<left>145</left>
					<right>24</right>
					<bottom>0</bottom>
					<height>1</height>
					<texture colordiffuse="14FFFFFF">colors/white.png</texture>
				</control>''')
    return '\n'.join(out)


def card(vid, focus, poster):
    """Kártyák nézet: poszter (2:3) vagy négyzetes kártya."""
    if poster:
        h_img, mask = 360, 'mask-poster'
        art = '$VAR[AppCardArtVar]'
        img = f'''				<control type="image">
					<left>20</left>
					<top>10</top>
					<width>240</width>
					<height>360</height>
					<aspectratio>scale</aspectratio>
					<texture diffuse="tomszo/mask-poster.png" fallback="DefaultVideo.png" background="true">{art}</texture>
				</control>
				<control type="progress">
					<left>36</left>
					<top>350</top>
					<width>208</width>
					<height>6</height>
					<texturebg colordiffuse="60000000">colors/white.png</texturebg>
					<midtexture colordiffuse="button_focus">colors/white.png</midtexture>
					<info>ListItem.PercentPlayed</info>
					<visible>Integer.IsGreater(ListItem.PercentPlayed,0)</visible>
				</control>'''
    else:
        h_img, mask = 240, 'mask-square'
        img = '''				<control type="image">
					<left>55</left>
					<top>45</top>
					<width>170</width>
					<height>170</height>
					<aspectratio>keep</aspectratio>
					<texture fallback="DefaultFolder.png" background="true">$INFO[ListItem.Icon]</texture>
				</control>'''
    out = [f'''				<control type="image">
					<left>20</left>
					<top>10</top>
					<width>240</width>
					<height>{h_img}</height>
					<texture colordiffuse="FF1C222B">tomszo/{mask}.png</texture>
				</control>''', img]
    if focus:
        out.append(f'''				<control type="image">
					<left>12</left>
					<top>2</top>
					<width>256</width>
					<height>{h_img + 16}</height>
					<texture border="22" colordiffuse="button_focus">tomszo/ring-small.png</texture>
					<visible>Control.HasFocus({vid})</visible>
				</control>''')
    out.append(f'''				<control type="label">
					<left>20</left>
					<top>{h_img + 20}</top>
					<width>240</width>
					<height>36</height>
					<font>font12</font>
					<label>$VAR[AppCardLabelVar]</label>{"""
					<scroll>true</scroll>""" if focus else ""}
				</control>
				<control type="label">
					<left>20</left>
					<top>{h_img + 54}</top>
					<width>240</width>
					<height>32</height>
					<font>font10</font>
					<textcolor>grey</textcolor>
					<label>$VAR[AppCardLabel2Var]</label>
				</control>''')
    return '\n'.join(out)


def view_mobile():
    vid = 56
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!-- TomSzo Touch: Mobil lista nézet (generálva: _tools/views.py) -->
<includes>
{VARS}
	<include name="View_56_MobileList">
		<control type="group">
			<visible>Control.IsVisible({vid})</visible>
			<include>Visible_Fade</include>
			<control type="list" id="{vid}">
				<left>20</left>
				<right>20</right>
				<top>110</top>
				<bottom>60</bottom>
				<orientation>vertical</orientation>
				<onleft>9000</onleft>
				<onright>9000</onright>
				<onup>{vid}</onup>
				<ondown>{vid}</ondown>
				<preloaditems>2</preloaditems>
				<scrolltime tween="quadratic" easing="out">250</scrolltime>
				<viewtype label="$LOCALIZE[31980]">list</viewtype>
				<itemlayout height="170">
{row(vid, False)}
				</itemlayout>
				<focusedlayout height="170">
{row(vid, True)}
				</focusedlayout>
			</control>
		</control>
	</include>
</includes>
'''


def view_cards():
    vid = 57
    sq = f'![{POSTER_CONTENT}]'
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!-- TomSzo Touch: Kártyák nézet (generálva: _tools/views.py) -->
<includes>
	<include name="View_57_Cards">
		<control type="group">
			<visible>Control.IsVisible({vid})</visible>
			<include>Visible_Fade</include>
			<control type="panel" id="{vid}">
				<centerleft>50%</centerleft>
				<width>1680</width>
				<top>110</top>
				<bottom>60</bottom>
				<orientation>vertical</orientation>
				<onleft>9000</onleft>
				<onright>{vid}</onright>
				<onup>{vid}</onup>
				<ondown>{vid}</ondown>
				<preloaditems>1</preloaditems>
				<scrolltime tween="quadratic" easing="out">300</scrolltime>
				<viewtype label="$LOCALIZE[31981]">wall</viewtype>
				<visible>{POSTER_CONTENT}</visible>
				<itemlayout width="280" height="460" condition="{POSTER_CONTENT}">
{card(vid, False, True)}
				</itemlayout>
				<focusedlayout width="280" height="460" condition="{POSTER_CONTENT}">
{card(vid, True, True)}
				</focusedlayout>
				<itemlayout width="280" height="340" condition="{sq}">
{card(vid, False, False)}
				</itemlayout>
				<focusedlayout width="280" height="340" condition="{sq}">
{card(vid, True, False)}
				</focusedlayout>
			</control>
		</control>
	</include>
</includes>
'''


if __name__ == '__main__':
    open('xml/View_56_MobileList.xml', 'w', encoding='utf-8').write(view_mobile())
    open('xml/View_57_Cards.xml', 'w', encoding='utf-8').write(view_cards())
    print('ok')
