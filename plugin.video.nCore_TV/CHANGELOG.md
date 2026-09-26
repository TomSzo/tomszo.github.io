# Változásnapló – nCore TV (fork)

Ez a fájl **kizárólag a fork módosításait** tartalmazza. Az eredeti addon (szerző: **heg**) verziótörténete – 1.0.0-tól 1.1.2-ig – változatlanul a [`changelog.txt`](changelog.txt) alján található.

A formátum a [Keep a Changelog](https://keepachangelog.com/hu/1.1.0/) szerkezetét követi.

> **Mérésekről:** az itt szereplő időadatok *szintetikus* teszteken, egy x86-os fejlesztőgépen készültek (Kodi nélkül, Kodi-stubokkal). Az arányok tájékoztató jellegűek; gyenge ARM-eszközön (pl. Amlogic S905X4) az abszolút értékek többszörösei lehetnek. Valódi nCore-oldalon és valódi eszközön nem mértem.

---

## [1.6.0] – 2026-09-26 (fork: TomSzo)

### Új
- **Magyar címek a listákban** (TMDb): pl. *Dűne (2021)*, *A kis herceg (2015)*; sorozatnál a rész is (*… – S02E03*). **Csak kijelzés** – a keresés, a verziók összevonása, a TMDb Helper és a lejátszás továbbra is az eredeti (angol) kiadásnevet használja. A panel alján az eredeti kiadásnév megmarad. Ha nincs magyar fordítás, az eredeti cím látszik.
- **Magyar, jó minőségű poszter** (TMDb, `w780`): magyar nyelvű poszter előnyben (több közül a legjobbra értékelt), ha nincs: angol, majd felirat nélküli. **Fanart** (`w1280`, felirat nélküli háttér előnyben). A film / sorozat listákban, az Ajánlókban és az adatlapon.
- **Fekete-fehér / színes változat jelzése** a színkódos listákban (pl. *Spider-Noir*): **FEKETE-FEHÉR** (`Black.and.White`, `B&W`, `BW`, `Monochrome`) és **SZÍNES** (`Color`, `Colour`, `Full.Color`, `True-Hue`). Csak a cím utáni részben (évszám / `S01` után) keres, így a címben lévő szó (pl. *The Color Purple*) nem ad hamis jelzést.
- A régi gyorsítótár-bejegyzések (cím / poszter nélkül) automatikusan frissülnek.
- Beállítások → Helyi funkciók: *Magyar címek*, *Magyar poszter és fanart* (mindkettő a *Leírás + pontszámok* bekapcsolt állapotában működik). A posztereket a **Gyors mód** kikapcsolásakor tölti be.

---

## [1.5.2] – 2026-09-26 (fork: TomSzo)

### Javítva (kódátnézés)
- **Vesszős / különleges karakteres cím a verzióválasztóban:** a választott verzió adatlapja `Container.Update(...)`-tel nyílt, a paraméterek kódolása nélkül – a Kodi a vesszőnél szétvágta a parancsot (pl. *„Hé, haver!”*), így csonka adatokkal nyílt meg. Most újrakódolt, idézőjeles URL megy (verzióválasztó, Ajánlók kattintás, „Összes nCore-találat”); a más oldalakról összegyűjtött verziók paraméterei is kódolva.
- **Átmeneti TMDb-hiba nem ragad be:** hibakódnál (pl. 429 – túl sok kérés) a leírás/pontszám üres eredménye eddig 1 napra gyorsítótárba került, a személy-adatlap pedig „0 szerep”-pel 1 napig. Most ilyenkor nincs mentés, a következő megnyitás újrapróbálja.
- **Új filmek IMDb-azonosítója:** a TMDb→IMDb azonosító-tár az üres eredményt is véglegesen eltárolta (friss címeknél a TMDb csak később pótolja) – most az üreset nem menti; a tár mérete korlátozva.
- **Atomi mentés** minden új gyorsítótárnál (ideiglenes fájl + csere): ha a Kodi írás közben leállítja az addont, a fájl nem sérül meg.

### Hozzáadva
- **Beállítások → Fájlok Karbantartása → „Lista-gyorsítótárak törlése”**: `infocache.json`, `extra_versions.json`, `idmap.json`, `person_cache.json`, `versions.json`, `remote_cache.json` (a régi takarítás ezeket nem ismerte).

---

## [1.5.1] – 2026-09-26 (fork: TomSzo)

### Új – szerep szerinti szűrés (Keresés színészre, Szereplők és stáb)
- Egy személyre kattintva **szűrő-menü** jön a darabszámokkal: *Minden szerep*, *Színészként*, *Rendezőként*, *Producerként*, *Íróként* – mindegyik **filmek** és **sorozatok** szerint külön (csak a nem üres sorok). Felül az életrajz a panelen.
- A listák a **TMDb** személy-adataiból jönnek (egy hívás, 1 napos gyorsítótár), újabb elöl; talk show / hírműsor / „önmaga” szereplések nélkül; a munkakör magyarul a cím mellett (pl. *rendező, forgatókönyv, producer*).
- Az Ajánlók-réteg itt is működik: **nCore-elérhetőség** (✔ N verzió / nincs nCore-on), leírás-panel, kattintásra **verzióválasztó**.
- A régi IMDb-filmográfia a menü alján elérhető; ha a TMDb nem ismeri a személyt, automatikusan az jön. Kikapcsolható (Helyi funkciók → Ajánlók).

---

## [1.5.0] – 2026-09-26 (fork: TomSzo)

### Új – Ajánlók menü
- **nCore-elérhetőség minden ajánlott címnél:** `✔ 3 verzió  4K 1080p HU` (sorozatnál `✔ N torrent`), ami nincs fent (vagy csak halott feltöltése van), az szürke „nincs nCore-on” jelzést kap; beállítással el is rejthető. Egy IMDb-keresés címenként (film + sorozat kategóriák), párhuzamosan, 1 óra gyorsítótár. A TMDb-azonosítós listákhoz az IMDb-azonosítót a TMDb adja (tartós gyorsítótár: `idmap.json`).
- **Kattintásra egyből a színkódolt verzióválasztó** (filmeknél): egy verzió esetén rögtön az adatlap. Magyar kategória elöl, azon belül a több seed elöl. A régi találati lista a helyi menüből érhető el („Összes nCore-találat”).
- **Leírás-panel az ajánlólistákban is:** valódi `movies` / `tvshows` tartalomtípus, Lista nézet, pontszámok (IMDb / RT / Metacritic / TMDb), műfaj, és a nCore-elérhetőség a leírás tetején.
- Érintett listák: TMDb Felfedezés (+ témák, streaming, franchise), TMDb Filmek / Sorozatok (+ szolgáltatók), Simkl, Trakt listák, JustWatch, TheTVDB.
- Új beállítások (Helyi funkciók → Ajánlók); mindhárom kikapcsolható.

### Változott – Ajánlók menü átszervezése
- **Kevesebb, átlátható menüpont**, minden lista a **TMDb API**-ból: *Filmek – most népszerű*, *Sorozatok – most népszerű*, **Magyar streaming-kínálat**, *Mozis és digitális újdonságok*, *Legjobbra értékelt filmek*, *Böngészés témák szerint*, *Sorozat-naptár és premierek*, *További források*.
- **Magyar streaming-kínálat** (új): Netflix, HBO Max, Disney+, Amazon Prime Video, Apple TV+, SkyShowtime – **magyar régió** szerint, előfizetéses kínálat; szolgáltatónként *Új filmek*, *Népszerű filmek*, *Friss részek / évadok*, *Új sorozatok*, *Népszerű sorozatok*. Kiváltja a korábbi két, főleg amerikai (US régiós, Hulu / Peacock / Starz…) streaming menüt.
- A törékeny **themoviedb.org weboldal-kiolvasás** („Filmek | Sorozatok (themoviedb.org)” + a hat szolgáltatós sorozatlista) kikerült a menüből – helyette az API-s listák (filmek is, nem csak sorozatok, köztes oldal nélkül). A régi útvonalak a kódban maradtak (meglévő kedvencek miatt).
- **További források** almenü: JustWatch, Simkl, Trakt, TheTVDB.

---

## [1.4.2] – 2026-09-26 (fork: TomSzo)

### Javítva
- **Összevonás a többi oldal verzióival is.** Eddig csak az aktuális oldalon belül vont össze (pl. a *Film HU 1080* listában a Scary Movie régebbi 1080p-s REMUX-a egy későbbi oldalon volt, ezért nem látszott „2 verzió”). Most minden IMDb-azonosítós címhez lekéri ugyanabból a kategóriából a többi feltöltést, a lista kulcsszavára szűrve (pl. csak 1080p / csak REMUX), halottak nélkül. Párhuzamos lekérés, 1 óra gyorsítótár (`extra_versions.json`); kikapcsolható.
- **Egyedülálló sorokban csak a cím és az évszám** (a színkódolt minőség lekerült a sorról; a verzióválasztóban és a panelen megmaradt).

---

## [1.4.1] – 2026-09-26 (fork: TomSzo)

### Változott – film / sorozat adatlap
- **Rövid, ikonos sorok** a torrent teljes neve helyett: *▶ Lejátszás* + színkódolt minőség (és *Folytatás N%*, ha félbehagytad), *▶ Előzetes*, *Szereplők és stáb*, *Más verziók*, *Hasonló tartalmak*, *A film többi része*, *Fájllista*; a mintaképek a lista végén.
- **Előzetes előre került**, és ha a Simklnél nincs, a **TMDb**-ről keres (magyar, majd angol; a hivatalos trailer az első).
- **Panel:** IMDb / RT / Metacritic / TMDb pontszám és műfaj a leírás fölött, alul a kiadás (tiszta cím, forrás, seed, csapat, nyelv). A panel címe marad a torrent teljes neve.
- Javítva: a *Más verziók* sor ikon-paramétere rossz helyre került (eredeti hiba).

---

## [1.4.0] – 2026-09-26 (fork: TomSzo)

### Új
- **Bal oldali leírás-panel a film / sorozat listákban.** A listák valódi `movies` / `tvshows` tartalomtípust kapnak (eddig érvénytelen `series`, ezért a skin nem mutatta a panelt), és automatikusan **Lista nézetre** (Estuary: 50) váltanak. Kikapcsolható, a nézet azonosítója állítható.
- **Leírás és pontszámok a panelen:** TMDb leírás (magyar, ha nincs: angol), műfaj, **IMDb** (szavazatszámmal), **Rotten Tomatoes**, **Metacritic**, TMDb pontszám. Az IMDb pontszám a skin értékelés-körébe is bekerül.
  - A Rotten Tomatoes / Metacritic értékhez **OMDb** vagy **MDBList** API-kulcs kell (ingyenes). Ha a saját mező üres, a **TMDb Helper** beállításaiban megadott kulcsot használja.
  - Gyorsítótár: `infocache.json` (7 nap); párhuzamos lekérés, legfeljebb ~8 mp oldalanként; hálózati hibánál nem ment üres adatot.
- A torrent teljes neve és a nCore-adatok (méret, seed, feltöltés) a leírás alján, elválasztó után.

---

## [1.3.2] – 2026-09-26 (fork: TomSzo)

### Változott
- **Cím + évszám minden verzió-sorban is** (a kis, második sorban, elöl): a TMDb Helper *Source Select*, a lista-verzióválasztó és az összevont sor leírása. Remake-eknél / azonos című filmeknél így soronként látszik, melyik melyik (pl. *Dune (2021)* vs. *Dune (1984)*).
- **Egyedülálló sorok is tiszta címet kapnak**: a torrent teljes neve helyett *Cím (Évszám)* + színkódolt minőség (4K · DV · HDR · HEVC · hang). A teljes kiadásnév a leírás elejére került.

---

## [1.3.1] – 2026-09-26 (fork: TomSzo)

### Változott
- **Tiszta cím a színkódos verzióválasztókban**: a TMDb Helper *Source Select* és a lista-verzióválasztó fejlécében a film címe és évszáma áll (pl. *Dune Part Two (2024) – 3 verzió*), sorozatnál a cím és a rész (*The Last of Us – S02E05*) – a teljes torrentnév helyett. Ugyanez az összevont listasorban és a lejátszás-értesítésben.
- **Halott torrentek szűrése a TMDb Helperben is** (Auto Play és Source Select): a minimum seed beállítás itt is érvényes; ha csak halott találat van, értesítés jelzi.

---

## [1.3.0] – 2026-09-26 (fork: TomSzo)

### Hozzáadva
- **Kiadások összevonása** a Film és a Sorozat listákban: ha ugyanannak a filmnek (IMDb-azonosító, ennek híján cím + év) vagy ugyanannak a résznek / évadpakknak (IMDb + S01E05 / S01) több kiadása van az oldalon, egy sorban jelenik meg „(N verzió)" jelöléssel. A leírásban mind a verzió látszik; kattintásra **színkódolt verzióválasztó** nyílik (4K / REMUX / DV / HDR / hang, méret, seed – a lista sorrendjében), és a választott kiadás adatlapjára visz. Különböző részek nem vonódnak össze. Widgetben nincs összevonás.
- **Halott torrentek elrejtése**: a beállított minimum seed alatti találatok nem jelennek meg (alapértelmezés: a 0 seedesek rejtve).
- Beállítások → Helyi funkciók → *Listák*: minimum seed (0 / 1 / 3 / 5 / 10; 0 = mind látszik), összevonás ki/be.

---

## [1.2.4] – 2026-09-26 (fork: TomSzo)

### Javítva
- **Rendezés-választó: OK után nem nyílt meg a lista.** A kategória-menüpont mappaként nyílt, és amíg a Kodi a „mappa" betöltésére várt, elnyelte a rendezett listára váltó `Container.Update` parancsot. Mostantól a menüpont futtatható elem (nem mappa, nem lejátszható), így az ablak után a lista rendben megnyílik.

---

## [1.2.3] – 2026-09-26 (fork: TomSzo)

### Hozzáadva
- **Rendezés-választó felugró ablak** a Film és a Sorozat kategóriák megnyitásakor (4K, Dolby Vision, REMUX, 1080, 720, SD – HU és EN): *Feltöltés ideje (legújabb / legrégebbi elöl)*, *Seed szerint*, *Letöltések száma*, *Méret (legnagyobb / legkisebb elöl)*, *Név szerint*. Az nCore saját rendezését használja (`miszerint` / `hogyan`), a lapozás megtartja a sorrendet.
- Az ablak az előző választást jelöli ki előre. A lista a rendezett címmel nyílik, így a *Vissza* gomb és a frissítés nem kérdez újra; *Mégse* esetén a kategória-menü marad.
- Beállítások → Helyi funkciók → *Rendezés*: a felugró ablak kikapcsolható, ilyenkor az *Alapértelmezett rendezés* érvényes.

### Eltávolítva
- A Film / Sorozat kategóriákból a négy „REMUX (seed szerint)" menüpont – a felugró ablak kiváltja (REMUX → *Seed szerint*). A **Widgetek** menüben megmaradnak, mert skin-widgetből nem nyílhat ablak.

---

## [1.2.2] – 2026-09-25 (fork: TomSzo)

### Hozzáadva
- **REMUX seed szerint** – új menüpontok a Film és a Sorozat kategóriákban, közvetlenül a sima REMUX alatt: *Film HU/EN REMUX (seed szerint)*, *Sorozat HU/EN REMUX (seed szerint)*. Az nCore saját rendezését használja (`miszerint=seeders&hogyan=DESC`), a lapozás („Következő oldal") megtartja a sorrendet.
- A **Widgetek** menüben is elérhető mind a négy.

---

## [1.2.1] – 2026-09-24 (fork: TomSzo)

### Javítva
- **Nincs auto-pause a lejátszás indításakor.** A folytatási pont meghatározásához a lejátszás korábban megállt, és ha nem folytatás-menüből indult a tartalom (pl. film az elejéről), a videó szünetben ragadt. Mostantól a figyelő ciklus előtt visszaindul, így az elejéről indított tartalom egyből megy.

### Egyéb
- Az addon **leírása bővült** a fork-módosítások listájával, hogy Kodiban is látszódjon.

---

## [1.2.0] – 2026-09-20 (fork: TomSzo)

Első fork-kiadás. Alap: **nCore TV 1.1.2** (eredeti szerző: heg, GPL-3.0-or-later).

### Hozzáadva

#### Beállítások > „Helyi funkciók" (új kategória)
| Beállítás | Azonosító | Alap | Hatás |
|---|---|---|---|
| Lokális lejátszás-követés | `local_tracking_enabled` | be | Kikapcsolva: nincs pozíciómentés (`video_positions`), nincs `full_url`-mentés, nincs zöld `[*]` jelölés, nincs „Ezt a verziót már elindítottad" sor, és a régi mentett pozíciók sem jelennek meg (folytatás, évadpakk-menü, lejátszó indulása). A Trakt/Plex/Simkl felhő-szinkront **nem érinti**. A meglévő DB-adat nem törlődik. |
| Évadpakk-kezelő menü | `season_pack_menu_enabled` | be | Kikapcsolva a többfájlos torrentnél nem ugrik fel az epizódválasztó, alapértelmezett lejátszás indul. |
| Gyors mód | `lite_mode` | be | Nincs távoli borító és fanart a listákban, a leírás a nyers torrentnév (nincs PTN-elemzés). Widget módban a poster megmarad. |
| Háttér-szinkron gyakorisága | `sync_interval_min` | 360 perc | 30 / 60 / 180 / 360 / 720 perc. |
| TMDb Helper: minőségi előny | `tmdbh_quality` | Auto | Auto / REMUX / 2160p / 1080p. |
| TMDb Helper playerek telepítése | (gomb) | – | Lásd lent. |

#### TMDb Helper integráció
- Új akció: `action=tmdbh` – paraméterei: `mode=play|select|search`, `type=movie|episode`, `imdb_id`, `tmdb_id`, `season`, `episode`, `quality`.
  - **`play` (Auto Play):** IMDb-azonosító alapján beolvassa a találati oldalakat (max. 3 oldal), pontozza a jelölteket, a legjobbat kiválasztja, és a `setResolvedUrl`-lel a meglévő `playmovie` akcióra lép tovább.
  - **`select` (Source Select):** ugyanez, de a jelöltekből dialógus segítségével választhatsz; mégse esetén nem indul semmi.
  - **`search`:** minőség szerint rendezett találati lista.
- Epizódnál a `target_episode` (pl. `S01E02`) a meglévő fájlválasztót használja, így az évadpakk-menü nem ugrik fel; az epizód-fájllista csak akkor töltődik le, ha még nincs az adatbázisban.
- Epizódnál a sorozat IMDb-azonosítóját a TMDb-azonosítóból oldja fel (a feloldás a Kodi-munkamenet alatt gyorsítótárazódik).
- Két player-fájl az a4k-openplayers gyűjtemény elnevezési mintáját követve (Auto Play / Source Select; csak a minta, a fájlok tartalma saját): `ncore.json` (Auto Play, priority 100) és `ncore.select.json` (Source Select, priority 101). A fájlok az `resources/players/` alatt találhatók.
- **Telepítő gomb** (Beállítások > Helyi funkciók): bemásolja a fájlokat a TMDb Helper `players` mappájába, visszaolvassa őket JSON-ként, kiírja a pontos célútvonalat, és a régebbi (`ncore_tv.json`, `ncore_tv_remux.json`) fájlokat törli.
- **A playerek `plugin` mezője `xbmc.core`.** Ok: az addon azonosítója (`plugin.video.nCore_TV`) nagybetűs, a Kodi viszont a feltételekben kisbetűsít, így a `System.HasAddon(plugin.video.nCore_TV)` hamisat ad, és a TMDb Helper – amely a `plugin` mező alapján ellenőrzi a telepítettséget – kiszűrte a playert. A tényleges lejátszás továbbra is a `plugin://plugin.video.nCore_TV/...` útvonalon megy. (A megoldás a TMDb Helper dokumentált mintáját követi; a hibát Kodi-naplóból azonosítottam.)

#### Source Select dialógus – részletes, színkódolt címkék
Egy sor két részből áll (`label` és `label2`), a hosszú fájlnév helyett rövid, strukturált tartalommal, hogy ne kelljen görgetni:
- **Felbontás:** 4K (égkék), 1080p (zöld), 720p (sárga), SD (piros), `?` (szürke).
- **Minőség:** REMUX (arany), DV (rózsaszín, a profillal: `DV P5`/`P7`/`P8`, ha a névben szerepel), HDR10+ / HDR10 / HDR / HLG (narancs), PACK (évadpakk).
- **Kiadás** (orchidea): DIR CUT, EXTENDED, THEATRICAL, UNRATED, UNCUT, IMAX, REMASTER, FINAL CUT, SPECIAL ED, REDUX, OPEN MATTE, 3D.
- **Technika:** kodek (HEVC/AVC/AV1/VC-1), hang (TrueHD Atmos, DTS-HD MA, DTS-HD, DTS:X, DD+ Atmos, DD+, DTS, DD) és csatornák (5.1, 7.1).
- **Második sor:** forrás (UHD BD, BluRay, BD50, WEB-DL, WEBRip, HDTV) + szolgáltató (AMZN, NF, DSNP, ATVP, HMAX, iT, MA, …), méret, seeder (piros: 0, narancs: <5, zöld: ≥5), release group (szürke), HU / HU sub (zöld).
- **`TC!` / `TS!` / `CAM!` / `SCR!`** piros jelzés a rossz forrású release-eknél.
- Fejléc: a verziók száma, epizódnál a `S01E02` is.

#### REMUX-keresés és minőség-felismerés
- Új modul: `resources/lib/indexers/quality.py` (Kodi-függés nélküli, tesztelhető).
  - Felismeri: REMUX, felbontás, HDR/DV, teljes lemez (**BD25/BD50** = 1080p, **BD66/BD100** = UHD), rossz forrás (TC/TS/CAM/SCR), a fenti kiadás-címkéket, szolgáltató-jeleket (kis/nagybetű-érzékenyen az `iT` és `MA`), release group-ot.
  - **Pontozás** (nagyobb = jobb): felbontás alappont (4K 400, 1080p 300, 720p 200, SD 100), +150 REMUX (Auto/REMUX előnynél), +100 teljes lemez, +40 DV, +25 HDR/DV jelenlét (a DV egyben HDR-nek számít), +15 csúcs-hang, +20 HU, seeder legfeljebb +90; 0 seeder −600, rossz forrás −900, DV Profile 5 −30 (nincs HDR10 alaprétege). A választott előny (REMUX/2160p/1080p) +1000 pontot ad a megfelelő jelöltnek – előny, nem szűrő.
- **Új szűrőopció** a felbontásszűrőben: „REMUX (bármely felbontás)", a többi opcióval VAGY-kapcsolatban.
- **Új REMUX kategóriák:** Film HU/EN REMUX és Sorozat HU/EN REMUX (a főmenü Film/Sorozat kategóriái között; az nCore `mire=remux` keresésével).
- `sort=quality` és `quality=` URL-paraméter; a lapozás továbbviszi a `quality`, `sort`, `widget`, `content`, `limit` paramétereket.

#### Widget mód
- `widget=1&content=movies|tvshows` paraméter: érvényes tartalomtípus (a korábbi `series` nem létező Kodi-típus volt), gyorsítótár be, nincs frissítés, nincs „Következő oldal" elem.
- Új főmenüpont: **Widgetek (REMUX / 4K / 1080)** – 9 kész lista, amelyeket a skin widget-választójában kiválaszthatsz.
- Minden listaelem kap `poster` art-ot (ha a kép távoli URL) és `mediatype`-ot (widget módban).
- **Dialógusmentes futás:** widgetből hívva a bejelentkezés/2FA/hibaoldal nem dob fel modális ablakot (lejárt süti vagy bekapcsolt 2FA esetén a widget üres marad, amíg egyszer interaktívan meg nem nyitod az addont).

#### Egyéb új fájl
- `resources/lib/nc_http.py`: vékony `requests`-wrapper alapértelmezett timeouttal (`(6, 25)` mp).

### Módosítva
- **Felbontásszűrő:** a `getItems`-ben két helyen duplikált, ~25 soros szűrőblokk egyetlen `quality.allowed()` hívásra cserélve. A régi logikával 2464 kombináción azonos eredményt ad (a lentebb jelzett hibajavításokon kívül).
- **Háttér-szinkron:** a főmenü megnyitásakor 15 percenként indult teljes Trakt/Simkl/Plex-szinkron; most alapból 6 óra, beállításból állítható (legkisebb érték: 30 perc).
- **`checkTorrentSource`** (HEAD-kérés): timeout (6, 12) mp.
- **Lejátszás indulásának észlelése:** 1000 ms helyett 250 ms-onként ellenőriz (`waitForAbort`), az átlagos késés kb. 375 ms-mal rövidebb.
- **`addon.xml`:** verzió 1.2.0, `provider-name` = „heg (fork: TomSzo)", a leírás jelzi, hogy nem hivatalos fork. `changelog.txt` és `<news>`: 1.2.0-s bejegyzés.

### Gyorsítás
Az alábbi mérések szintetikus adaton, x86-on készültek (lásd a fejléc megjegyzését).

| Terület | Előtte | Utána | Mi változott |
|---|---|---|---|
| Indulás | minden plugin-hívásnál 2 blokkoló HTTPS-kérés a GitHubra (egyenként 15 mp timeout) | első használatkor töltődik, 12 órás lemezes gyorsítótár (`remote_cache.json`) | A `static_data` importálásakor futó `requests.get` hívások lusta `_LazyRemote` objektumokra cserélve (színész-keresés hash-ei; főmenü-jelző). Hiba esetén a régi érték vagy az alapérték él. *(Az éles letöltő-ág nincs kipróbálva.)* |
| Adatbázis-inicializálás | ~8,1 ms minden kattintásnál | ~0,2 ms | A ~12 `CREATE TABLE` + ALTER-próba csak séma-verzióváltáskor fut (`PRAGMA user_version`, `SCHEMA_VERSION = 1`). |
| DB-karbantartás indításkor | minden hívásnál: 2 JSON-fájl kiírása + `DELETE … NOT IN (subselect)` | JSON-export csak a két GitHub-akció előtt; orphan-takarítás legfeljebb 6 óránként (Window-property) | A duplikált `force_create_search_table()` hívás megszűnt. |
| SQLite-kapcsolat | minden lekérdezés új kapcsolat + PRAGMA-k | szálanként egy újrahasznált kapcsolat; a WAL-mód folyamatonként egyszer | 50 elemenkénti lekérdezés: 6,4 ms → 0,3 ms. |
| Oldal-feldolgozás | teljes oldal `html.parser` | csak a `box_torrent` blokkok (`SoupStrainer`), a többi lustán (`_FastSoup`) | 250 KB-os szintetikus oldal: 191 ms → 83 ms. A `find_all('box_torrent')`, a lapozó és a hibaoldal-felismerés azonos eredményt ad (tesztelve). |
| `str(torrent)` | elemenként 3–4× szerializálva | egyszer (`_tstr`) | 50 elemnél ~14 ms megtakarítás. |
| Lista-építés (50 elem) | ~385 ms | ~200 ms (gyors mód nélkül) / **~114 ms** (gyors móddal) | A fenti tételek + gyors mód együtt. |
| Lejátszás-figyelő ciklus | 500 ms-onként új `xbmc.Monitor()` | egyetlen példány, `waitForAbort(0.5)` | |
| Hálózati hívások | 62 `requests.get/post` timeout nélkül | mind `nc_get/nc_post` (alap timeout) | Beleértve a bejelentkezési POST-ot. Egy elakadt kapcsolat nem fagyaszthatja le végtelen ideig a listát. |

### Javítva
- **A `dv` részkarakterlánc-illesztés** a DVDRip-et is HDR-nek minősítette (ezért a 1080p DVDRip a „DV/HDR (1080)" szűrőbe került). Most tokenizált felismerés van (`dv`, `dovi`, `dolby vision`, `hdr`, `hdr10`, `hdr10+`, `hlg`).
- **HDR-címke:** a sima `DoVi`/`Dolby Vision` már nem jelenik meg „HDR"-ként.
- **BD50/BD25** korábban felbontás nélküli („?") volt, most 1080p; **BD66/BD100** 4K.
- **`DTSHD`** (`MA` nélkül) már nem „DTS-HD MA".
- **TMDb Helper player láthatósága** (lásd a `xbmc.core` magyarázatot fent).

### Változatlan (szándékosan)
- Az addon belső azonosítója: `plugin.video.nCore_TV` (a beállítások és az adatbázis megmaradása miatt).
- A `track_event()` telemetria (lásd a [README hálózati kapcsolatok](README.md#hálózati-kapcsolatok-és-adatvédelem) szakaszát) – az eredeti működés szerint fut.
- Minden eredeti funkció és menü; a fork kikapcsolásukat vagy kiegészítésüket csak a fenti beállításokkal teszi lehetővé.

### Módosított és új fájlok
| Fájl | Állapot | Változás (sor) |
|---|---|---|
| `resources/lib/indexers/navigator.py` | módosítva | +501 / −137 |
| `resources/lib/indexers/database.py` | módosítva | +57 / −5 |
| `resources/lib/indexers/static_data.py` | módosítva | +59 / −10 |
| `resources/settings.xml` | módosítva | +11 / −0 |
| `default.py` | módosítva | +9 / −0 |
| `addon.xml`, `changelog.txt`, `README.md` | módosítva | verzió, leírás, dokumentáció |
| `resources/lib/indexers/quality.py` | **új** | ~390 sor |
| `resources/lib/nc_http.py` | **új** | ~25 sor |
| `resources/players/ncore.json`, `ncore.select.json` | **új** | TMDb Helper playerek |
| `CHANGELOG.md` | **új** | ez a fájl |

### Ismert korlátok
- Az egész fork **nincs teljes körűen tesztelve Kodiban**; a szintetikus tesztek nem helyettesítik a valódi nCore-oldalt és a valódi eszközt.
- A Source Select dialógus `label2` megjelenése skin-függő.
- A TMDb Helper `{imdb}`, `{tmdb}`, `{season}`, `{episode}` változóira épít; más TMDb Helper-verzióban eltérhet.
- Több fájlt tartalmazó (extrás) filmtorrentnél a bekapcsolt évadpakk-menü felugorhat.
- Gyors módban a „nyers" leírás váltja a PTN-alapú részletes leírást minden nézetben.
- Az időmérések nem a célhardveren készültek.
