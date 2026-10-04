# Bingie – magyar változat (privát)

A Kodi 21-es (Omega) Bingie skin és kiegészítőinek **teljes magyar fordítása, magyar súgóval**.

**Alap:** a skin (`skin.bingie`) és a TMDb Bingie Helper a [signde tárolóból](https://signde.github.io/repository.signde/)
jön (AVDV/CoreELEC-re igazított változat: tinyppi-bekötés, Atmos / DTS:X / HDR10+ jelölők,
Wikipédia-javítás), a többi kiegészítő a [matke-84/repository.bingie](https://github.com/matke-84/repository.bingie)
tárolóból (a signde-ben ezek tartalomra azonosak). A magyar verziók a signde verziói fölött
vannak (pl. skin 39.2.0.2 → **39.2.0.2.1**, TMDb Helper 2.1.0.3 → **2.1.0.3.1**), így a Kodi akkor is
a magyar változatot választja, ha a signde-tároló is telepítve van.

## Mi van benne?

- **Teljes magyar fordítás** (kb. 1300 szöveg): a skin, a TMDb Bingie Helper, a Bingie Widgets /
  Helper / Toolbox, a képernyővédő, a színválasztó, a skinmentés és az automatikus kiegészítés.
- **Súgó-infódoboz**:
  - a skinbeállításoknál alul mindig látszik, mit csinál a kijelölt beállítás (145 beállítás +
    általános súgó a 109 színgombhoz);
  - a kiegészítők beállítás-ablakában (pl. TMDb Bingie Helper) is van leírásmező, és
    **minden beállításnak van magyar súgója** (kb. 120 új súgószöveg).
- **Magyar alapértékek**: a TMDb Bingie Helper alapból magyarul kéri le a címeket és
  leírásokat; az alap-színtéma színnevei magyarok.
- A kódba égetett néhány angol felirat is magyar.

## Optimalizálás (skin.bingie 2.0.2.2)

- **TV-box gyorsmód** gomb: Skinbeállítások → Általános skinbeállítások → Haladó. Egy kattintással
  kikapcsolja a legnehezebb effekteket (automatikus előzetesek, háttér- és hóanimáció, mozgó
  fókuszkeret, extra / véletlen háttérképek, indítóvideó). Bármelyik egyenként visszakapcsolható.
- A **menüépítő (skinshortcuts) a kezdőképernyőn munkamenetenként egyszer fut**, nem minden
  visszalépéskor (a menü szerkesztése után a skinbeállításokból kilépve úgyis újraépül).
- A **külső képek** (szereplőfotók, epizód- és listaképek, csatornalogók) **háttérben töltődnek**,
  így görgetéskor nem akad meg a felület.

A verziószámok az eredeti után egy `.1`-et kapnak (pl. `skin.bingie` 2.0.2 → **2.0.2.1**),
így ha mindkét tároló telepítve van, a Kodi a magyar változatot választja.

## TMDb Bingie Helper gyorsítás (1.0.3.2 + script.module.bingie 1.0.1.2)

Mérve (Kodi-utánzattal, valódi TMDb / fanart.tv kérésekkel, 20 elemes widget):

| | Eredeti | Gyorsított |
|---|---|---|
| Filmek, üres gyorsítótár – idő / CPU | 2,3–2,6 mp / 5,2–7,1 mp | **1,3 mp / 1,0–1,7 mp** |
| Sorozatok, üres gyorsítótár – idő / CPU | 1,8–1,9 mp / 3,3–3,9 mp | **1,5–1,7 mp / 0,9–1,1 mp** |
| Gyorsítótárból – CPU | 0,25 mp | **0,20 mp** (requests/SSL nem töltődik be) |

- **Párhuzamos szálak: korlátlan helyett 4** (alapérték). Korlátlannál mind a ~40 kérés külön
  kapcsolatot és TLS-kézfogást nyitott; 4 szállal a kapcsolatok újrahasznosulnak.
- **A `requests` csak akkor töltődik be, ha tényleg kell hálózat** – gyorsítótárból kiszolgált
  listáknál minden widget-hívás megspórolja a requests + urllib3 + ssl betöltését.
- **Háttérfigyelő:** ha ~2 mp-ig nem változik a kijelölt elem, 0,2 helyett 0,35 mp-enként kérdez
  (kevesebb Kodi-hívás versenyez a kirajzolással); mozgatáskor azonnal visszagyorsul.

## Angol cím magyar helyett hiányzó fordításnál (TMDb Bingie Helper 1.0.3.3)

Ha egy filmnek vagy sorozatnak nincs magyar címe, a TMDb az eredetit adja (japán, kínai,
koreai, hindi…), amit a skin betűtípusai sokszor nem is tudnak megjeleníteni. Ilyenkor a
kiegészítő az **angol címet** használja (pl. 薬屋のひとりごと → *The Apothecary Diaries*), és
ha nincs magyar leírás, az **angol leírást**. A fordításokat csak a hiányos elemekhez kéri le,
gyorsítótárazva. A már tárolt elemek egyszer újraépülnek (az első betöltés ezért lassabb).

## Dolby Vision / HDR infó: signde PPI (tinyppi) – skin.bingie 2.0.2.3

A [signde PPI](https://github.com/signde/script.tinyppi) (script.signde.tinyppi, jamal2362 /
signde) egy kis, AVDV/CoreELEC-re írt lejátszási infó-ablak (kodek, videó, HDR, Dolby Vision
profil/EL, VS10, hang, rendszer). A skin úgy van bekötve, mint a signde AVDV-s Bingie-je:

- a **lejátszási infó** (Player Process Info, pl. „O” / INFO gomb) a tinyppit nyitja;
- az OSD-n (videóbeállítás mellett) **VS10-gomb**: a tinyppi párbeszédablaka (VS10-mód, infó).

Ha a tinyppi nincs telepítve, minden a régi marad (a VS10-gomb is rejtve).
Telepítés: Fájlkezelő → Forrás: `https://signde.github.io/repository.signde/` → ZIP-ből a
signde tároló → Telepítés tárolóból → signde repository → **signde PPI (avdvplus / p3i)**.
(A VS10-ikonok a signde Bingie-ből valók, GPL-2.)

## Telepítés (AVDV / Kodi 21)

1. Telepítsd a **signde-tárolót** (a skin kötelező függősége, a signde PPI / tinyppi, és a stúdiólogók
   onnan jönnek): Fájlkezelő → Forrás hozzáadása: `https://signde.github.io/repository.signde/`
   → Kiegészítők → Telepítés ZIP fájlból → a signde repository zipje.
2. Legyen fent a **TomSzo Privát Tároló** (lásd a [fő README-t](../README.md)).
3. Kiegészítők → Telepítés tárolóból → **TomSzo Privát Tároló** → Skin → **Bingie**
   (2.0.2.1). A függőségeket a Kodi magától felteszi, a magyar változatokat ebből a tárolóból.
4. Ha a Bingie már fent volt: Kiegészítők → Saját kiegészítők → ... → **Frissítés**, és válaszd a
   2.0.2.1 / 1.0.3.1 stb. verziót a TomSzo tárolóból.
5. A Kodi nyelve legyen magyar (Beállítások → Felület → Régió → Nyelv).

Megjegyzés: ha a matke-tároló később újabb verziót ad ki (pl. 2.0.3), a Kodi arra frissít, és a
fordítás eltűnik, amíg itt is el nem készül az új magyar változat.

## Újraépítés

```sh
python3 privat/bingie-hu/_tools/build.py
```

A szkript letölti az eredeti csomagokat, beteszi a `forditas/` mappa fájljait (`<id>.tsv`:
fordítás, `<id>.sugo.tsv`: beállítás-súgók), elvégzi a skin-módosításokat, és kiírja a
zipeket a privát tárolóba (`privat/<id>/`), majd frissíti a `privat/addons.xml`-t.
