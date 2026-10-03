# TomSzo AVDV (skin.tomszo.avdv)

Személyes, **csak TV-re** készült, streaming-stílusú Kodi-skin az AVDV boxra
(Kodi 21 / AVDV build). Alapja az **avdvplus.Estuary** (phil65, Ichabod Fletchman);
annak Dolby Vision / HDR-info ablaka és CoreELEC-beállításai változatlanul megmaradtak,
a **kezdőképernyő** teljesen új.

## Kezdőképernyő

- Bal oldalt **ikonsáv**: balra lépve kinyílik (Keresés, Kezdőlap, Filmek, Sorozatok,
  Sport, Anime, Kiegészítők, Kedvencek, Beállítások, Kikapcsolás).
- Felül **nagy kép** (hero): a kijelölt elem háttérképe, logója vagy címe, adatai
  (évad/rész, év, műfaj, hossz, értékelés) és leírása.
- Alul **vízszintes sorok** (widgetek), a kijelölt kártya mindig a sor elején áll;
  lekerekített kártyák, fókuszkeret, piros „ennyit néztél meg” csík.

| Szekció | Sorok (forrás) |
|---|---|
| Kezdőlap | Folytatás, Élő sport (Network4), Felkapott filmek / sorozatok (TMDb Helper), új részek, MagyarAnime-folytatás |
| Filmek | TMDb Helper: felkapott, népszerű, moziban, legjobbra értékelt, hamarosan + saját könyvtár |
| Sorozatok | TMDb Helper: felkapott, népszerű, ma adásban, legjobbra értékelt + saját könyvtár |
| Sport | Network4: élő és hamarosan, kiemelt sportok, Premier League, Bundesliga, NFL, MotoGP, UFC |
| Anime | MagyarAnime (folytatás, kedvencek, futó sorozatok), Muteki, Kintsugi, Naruto-Kun (legfrissebb, kedvencek) |

Egy sor csak akkor látszik, ha a hozzá tartozó kiegészítő telepítve van, és ad vissza
elemet – a hiányzó addon nem okoz hibát, a sor egyszerűen eltűnik.

## Telepítés

1. Telepítsd a privát tárolót (lásd a [fő README-t](../README.md)), és belőle a
   **TomSzo AVDV** skint – vagy közvetlenül a `skin.tomszo.avdv-1.0.1.zip`-et.
2. **Beállítások → Felület → Skin → TomSzo AVDV**.
3. A sorokhoz kellenek: **TMDb Helper** (jurialmunkey tároló), **Network4**
   (TomSzo tároló), és az anime-kiegészítők (privát tároló) – mindegyik a saját
   fiókoddal belépve.

## Fejlesztés

A kezdőképernyő (`xml/Home.xml`, `xml/Includes_TomSzo.xml`) **generált**:
a sorokat a `_tools/build_home.py` `ROWS` listájában lehet szerkeszteni, majd
`python3 _tools/build_home.py`. A grafikák (`media/tomszo/`, ikon, háttér) a
`_tools/make_media.py`-vel készülnek (Pillow + cairosvg).
A `fonts/TSInter-*.ttf` az Inter és a Noto Sans SC / KR (kínai, japán, koreai
karakterek) összeolvasztása – a Kodi nem vált betűtípust karakterenként, így e nélkül
a fordítás nélküli ázsiai címek helyén „NO GLYPH” jelenne meg. Újragyártás:
`_tools/make_fonts.py` (fonttools). A `_tools` mappa nem
kerül bele a zipbe.
