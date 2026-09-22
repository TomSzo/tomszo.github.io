# Változásnapló – nCore TV (fork)

Ez a fájl **kizárólag a fork módosításait** tartalmazza. Az eredeti addon (szerző: **heg**) verziótörténete – 1.0.0-tól 1.1.2-ig – változatlanul a [`changelog.txt`](changelog.txt) alján található.

A formátum a [Keep a Changelog](https://keepachangelog.com/hu/1.1.0/) szerkezetét követi.

> **Mérésekről:** az itt szereplő időadatok *szintetikus* teszteken, egy x86-os fejlesztőgépen készültek (Kodi nélkül, Kodi-stubokkal). Az arányok tájékoztató jellegűek; gyenge ARM-eszközön (pl. Amlogic S905X4) az abszolút értékek többszörösei lehetnek. Valódi nCore-oldalon és valódi eszközön nem mértem.

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
